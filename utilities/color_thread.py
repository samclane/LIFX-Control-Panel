#!/usr/bin/env python
# coding=utf-8
import logging
import threading
from collections import deque
from functools import lru_cache
from statistics import mode

from PIL import Image
from desktopmagic.screengrab_win32 import *
from lifxlan import utils

from ui.settings import config
from utilities.utils import str2list

@lru_cache(maxsize=32)
def get_monitor_from_bounds(func):
    return func() or config["AverageColor"]["DefaultMonitor"]


N_POINTS = 1  # Maybe make this a setting in the future
window = deque([0, 0, 0, 0] for _ in range(N_POINTS))


def column(matrix, i):
    return [row[i] for row in matrix]


def avg_screen_color(initial_color, func_bounds=lambda: None):
    global window
    monitor = get_monitor_from_bounds(func_bounds)
    if "full" in monitor:
        im = getScreenAsImage()
    else:
        im = getRectAsImage(str2list(monitor, int))
    color = im.resize((1, 1), Image.HAMMING).getpixel((0, 0))
    color_hsbk = list(utils.RGBtoHSBK(color, temperature=initial_color[3]))
    window.rotate(1)
    window[0] = color_hsbk
    # Take the sliding window across each parameter
    for p in range(1, 4):  # Skip Hue ([0]); averaging it only makes things weird
        color_hsbk[p] = int(sum(column(window, p)) / N_POINTS)
    return color_hsbk


def mode_screen_color(initial_color):  # UNUSED
    """ Probably a more accurate way to get screen color, but is incredibly slow. """
    im = getRectAsImage(getDisplayRects()[1]).resize((500, 500))
    color = mode(im.load()[x, y] for x in range(im.width) for y in range(im.height) if
                 im.load()[x, y] != (255, 255, 255) and im.load()[x, y] != (0, 0, 0))
    return utils.RGBtoHSBK(color, temperature=initial_color[3])


class ColorThread(threading.Thread):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, daemon=True, **kwargs)
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()


class ColorThreadRunner:
    def __init__(self, bulb, color_function, parent, continuous=True, **kwargs):
        self.bulb = bulb
        self.color_function = color_function
        self.kwargs = kwargs
        self.parent = parent  # couple to parent frame
        self.logger = logging.getLogger(parent.logger.name + '.Thread({})'.format(color_function.__name__))
        self.prev_color = parent.get_color_values_hsbk()
        self.continuous = continuous
        self.t = ColorThread(target=self.match_color, args=(self.bulb,))
        try:
            label = self.bulb.get_label()
        except Exception:
            label = "<LABEL-ERR>"
        self.logger.info(
            'Initialized Thread: Bulb: {} // Continuous: {}'.format(label, self.continuous))

    def match_color(self, bulb):
        self.logger.debug('Starting color match.')
        self.prev_color = self.parent.get_color_values_hsbk()  # coupling to LightFrame from gui.py here
        while not self.t.stopped():
            try:
                color = self.color_function(initial_color=self.prev_color, **self.kwargs)
                bulb.set_color(color, duration=0 if self.continuous else self.get_duration() * 1000,
                               rapid=self.continuous)
                self.prev_color = color
            except OSError:
                # This is dirty, but we really don't care, just keep going
                self.logger.info("Hit an os error")
                continue
            if not self.continuous:
                self.stop()
        self.logger.debug('Color match finished.')

    def start(self):
        if self.t.stopped():
            self.t = ColorThread(target=self.match_color, args=(self.bulb,))
            self.t.setDaemon(True)
        try:
            self.t.start()
            self.logger.debug('Thread started.')
        except RuntimeError:
            self.logger.error('Tried to start ColorThread again.')

    def stop(self):
        self.t.stop()

    @staticmethod
    def get_duration():
        return float(config["AverageColor"]["duration"])


def install_thread_excepthook():
    """
    Workaround for sys.excepthook thread bug
    (https://sourceforge.net/tracker/?func=detail&atid=105470&aid=1230540&group_label=5470).
    Call once from __main__ before creating any threads.
    If using psyco, call psycho.cannotcompile(threading.Thread.run)
    since this replaces a new-style class method.
    """
    import sys
    run_old = threading.Thread.run

    def run(*args, **kwargs):
        try:
            run_old(*args, **kwargs)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            sys.excepthook(*sys.exc_info())

    threading.Thread.run = run


install_thread_excepthook()
