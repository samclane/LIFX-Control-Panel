# -*- coding: utf-8 -*-
"""Multi-Threaded Color Changer

Contains several basic "Color-Following" functions, as well as custom Stop/Start threads for these effects.
"""
import logging
import threading
from functools import lru_cache
from statistics import mode

from PIL import Image
from desktopmagic.screengrab_win32 import getRectAsImage, getScreenAsImage, getDisplayRects
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


def mode_screen_color(initial_color):  # UNUSED
    """ Probably a more accurate way to get screen color, but is incredibly slow. """
    screenshot = getRectAsImage(getDisplayRects()[1]).resize((500, 500))
    color = mode(screenshot.load()[x, y] for x in range(screenshot.width) for y in range(screenshot.height) if
                 screenshot.load()[x, y] != (255, 255, 255) and screenshot.load()[x, y] != (0, 0, 0))
    return utils.RGBtoHSBK(color, temperature=initial_color[3])


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
