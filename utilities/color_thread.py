# -*- coding: utf-8 -*-
"""Multi-Threaded Color Changer

Contains several basic "Color-Following" functions, as well as custom Stop/Start threads for these effects.
"""
import logging
import threading
from functools import lru_cache

import numexpr as ne
import numpy as np
from PIL import Image
from desktopmagic.screengrab_win32 import getRectAsImage, getScreenAsImage
from lifxlan import utils

from ui.settings import config
from utilities.utils import str2list, timeit


@lru_cache(maxsize=32)
def get_monitor_bounds(func):
    """ Returns the rectangular coordinates of the desired Avg. Screen area. Can pass a function to find the result
    procedurally """
    return func() or config["AverageColor"]["DefaultMonitor"]


@timeit  # TODO Remove before release
def avg_screen_color(initial_color, func_bounds=lambda: None):
    """ Capture an image of the monitor defined by func_bounds, then get the average color of the image in HSBK"""
    monitor = get_monitor_bounds(func_bounds)
    if "full" in monitor:
        screenshot = getScreenAsImage()
    else:
        screenshot = getRectAsImage(str2list(monitor, int))
    # Resizing the image to 1x1 pixel will give us the average for the whole image (via HAMMING interpolation)
    color = screenshot.resize((1, 1), Image.HAMMING).getpixel((0, 0))
    color_hsbk = list(utils.RGBtoHSBK(color, temperature=initial_color[3]))
    return color_hsbk


@timeit  # TODO Remove before release
def unique_screen_color(initial_color, func_bounds=lambda: None):
    """
    https://stackoverflow.com/questions/50899692/most-dominant-color-in-rgb-image-opencv-numpy-python
    """
    monitor = get_monitor_bounds(func_bounds)
    if "full" in monitor:
        screenshot = getScreenAsImage()
    else:
        screenshot = getRectAsImage(str2list(monitor, int))
    screenshot = screenshot.resize((screenshot.width // 4, screenshot.height // 4), Image.HAMMING)
    a = np.array(screenshot)
    a2D = a.reshape(-1, a.shape[-1])
    col_range = (256, 256, 256)  # generically : a2D.max(0)+1
    eval_params = {'a0': a2D[:, 0], 'a1': a2D[:, 1], 'a2': a2D[:, 2],
                   's0': col_range[0], 's1': col_range[1]}
    a1D = ne.evaluate('a0*s0*s1+a1*s0+a2', eval_params)
    color = np.unravel_index(np.bincount(a1D).argmax(), col_range)
    color_hsbk = list(utils.RGBtoHSBK(color, temperature=initial_color[3]))
    # color_hsbk[2] = initial_color[2]  # TODO Decide this
    return color_hsbk


class ColorThread(threading.Thread):
    """ A Simple Thread which runs when the _stop event isn't set """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, daemon=True, **kwargs)
        self._stop = threading.Event()

    def stop(self):
        """ Stop thread by setting event """
        self._stop.set()

    def stopped(self):
        """ Check if thread has been stopped """
        return self._stop.isSet()


class ColorThreadRunner:
    """ Manages an asynchronous color-change with a Device. Can be run continuously, stopped and started. """

    def __init__(self, bulb, color_function, parent, continuous=True, **kwargs):
        self.bulb = bulb
        self.color_function = color_function
        self.kwargs = kwargs
        self.parent = parent  # couple to parent frame
        self.logger = logging.getLogger(parent.logger.name + '.Thread({})'.format(color_function.__name__))
        self.prev_color = parent.get_color_values_hsbk()
        self.continuous = continuous
        self.thread = ColorThread(target=self.match_color, args=(self.bulb,))
        try:
            label = self.bulb.get_label()
        except:  # pylint: disable=bare-except
            # If anything goes wrong in getting the label just set it to ERR; we really don't care except for logging.
            label = "<LABEL-ERR>"
        self.logger.info(
            'Initialized Thread: Bulb: %s // Continuous: %s', label, self.continuous)

    def match_color(self, bulb):
        """ ColorThread target which calls the 'change_color' function on the bulb. """
        self.logger.debug('Starting color match.')
        self.prev_color = self.parent.get_color_values_hsbk()  # coupling to LightFrame from gui.py here
        while not self.thread.stopped():
            try:
                color = self.color_function(initial_color=self.prev_color, **self.kwargs)
                bulb.set_color(color, duration=self.get_duration() * 1000,
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
        """ Start the match_color thread"""
        if self.thread.stopped():
            self.thread = ColorThread(target=self.match_color, args=(self.bulb,))
            self.thread.setDaemon(True)
        try:
            self.thread.start()
            self.logger.debug('Thread started.')
        except RuntimeError:
            self.logger.error('Tried to start ColorThread again.')

    def stop(self):
        """ Stop the match_color thread"""
        self.thread.stop()

    @staticmethod
    def get_duration():
        """ Read the transition duration from the config file. """
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
        """ Monkey-patch for the run function that installs local excepthook """
        try:
            run_old(*args, **kwargs)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:  # pylint: disable=bare-except
            sys.excepthook(*sys.exc_info())

    threading.Thread.run = run


install_thread_excepthook()
