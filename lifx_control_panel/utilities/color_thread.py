# -*- coding: utf-8 -*-
"""Multi-Threaded Color Changer

Contains several basic "Color-Following" functions, as well as custom Stop/Start threads for these effects.
"""
import logging
import sys
import threading
from typing import List, Tuple
import time

import mss
from PIL import Image
from lifxlan import utils

from .utils import str2list, Color
from ..ui.settings import config

from lifx_control_panel.utilities.utils import hsv_to_rgb


def get_monitor_bounds(func):
    """ Returns the rectangular coordinates of the desired Avg. Screen area. Can pass a function to find the result
    procedurally """
    return func() or config["AverageColor"]["DefaultMonitor"]


def get_screen_as_image():
    """Grabs the entire primary screen as an image"""
    with mss.mss() as sct:
        monitor = sct.monitors[0]
        bbox = (
            monitor["left"],
            monitor["top"],
            monitor["left"] + monitor["width"],
            monitor["top"] + monitor["height"],
        )
        sct_img = sct.grab(bbox)
        return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")


def get_rect_as_image(bounds: Tuple[int, int, int, int]):
    """ Grabs a rectangular area of the primary screen as an image """
    with mss.mss() as sct:
        monitor = {
            "left": bounds[0],
            "top": bounds[1],
            "width": bounds[2],
            "height": bounds[3],
        }
        sct_img = sct.grab(monitor)
        return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")


def normalize_rectangles(rects: List[Tuple[int, int, int, int]]):
    """ Normalize the rectangles to the monitor size """
    x_min = min(rect[0] for rect in rects)
    y_min = min(rect[1] for rect in rects)
    return [
        (-x_min + left, -y_min + top, -x_min + right, -y_min + bottom,)
        for left, top, right, bottom in rects
    ]


class ColorCycle:
    def __init__(self):
        self.initial_color = Color(255, 0, 0, 0)
        self.last_change = time.time()
        self.pos = 0
        self.cycle_color = hsv_to_rgb(self.pos, 1, 1)

    def get_color(self, *args, **kwargs):
        if time.time() - self.last_change > 0.1:
            self.pos = (self.pos + 1) % 360
            self.cycle_color = hsv_to_rgb(self.pos, 1, self.initial_color[2] / 65535)
            self.last_change = time.time()
        return list(
            utils.RGBtoHSBK(self.cycle_color, temperature=self.initial_color[3])
        )

    def __call__(self, initial_color):
        self.initial_color = initial_color
        return self.get_color()

    def __name__(self):
        return "ColorCycle"


def _screen_rgb_to_hsbk(rgb, temperature):
    """Convert a captured screen pixel to HSBK, desaturating near-black pixels.

    RGBtoHSBK derives hue/saturation from (cmax-cmin)/cmax, so a noise pixel like
    (1, 0, 1) comes out fully-saturated magenta. Treat anything that dark as black.
    """
    hue, saturation, brightness, kelvin = utils.RGBtoHSBK(rgb, temperature=temperature)
    if max(rgb) < 10:  # ponytail: fixed threshold; make configurable if it clips dim scenes
        saturation = 0
    return [hue, saturation, brightness, kelvin]


def avg_screen_color(initial_color, func_bounds=lambda: None):
    """ Capture an image of the monitor defined by func_bounds, then get the average color of the image in HSBK """
    monitor = get_monitor_bounds(func_bounds)
    if "full" in monitor:
        screenshot = get_screen_as_image()
    else:
        screenshot = get_rect_as_image(str2list(monitor, int))
    # Resizing the image to 1x1 pixel will give us the average for the whole image (via HAMMING interpolation)
    color = screenshot.resize((1, 1), Image.HAMMING).getpixel((0, 0))
    return _screen_rgb_to_hsbk(color, initial_color[3])


def dominant_screen_color(initial_color, func_bounds=lambda: None):
    """
    Gets the dominant color of the screen defined by func_bounds
    https://stackoverflow.com/questions/50899692/most-dominant-color-in-rgb-image-opencv-numpy-python
    """
    monitor = get_monitor_bounds(func_bounds)
    if "full" in monitor:
        screenshot = get_screen_as_image()
    else:
        screenshot = get_rect_as_image(str2list(monitor, int))

    downscale_width, downscale_height = screenshot.width // 4, screenshot.height // 4
    screenshot = screenshot.resize((downscale_width, downscale_height), Image.HAMMING)

    color = max(
        screenshot.getcolors(downscale_width * downscale_height),
        key=lambda count_pixel: count_pixel[0],
    )[1]

    return _screen_rgb_to_hsbk(color, initial_color[3])


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
        self.logger = logging.getLogger(
            parent.logger.name + f".Thread({color_function.__name__})"
        )
        self.prev_color = parent.get_color_values_hsbk()
        self.continuous = continuous
        self.thread = ColorThread(target=self.match_color, args=(self.bulb,))
        try:
            label = self.bulb.get_label()
        except:  # pylint: disable=bare-except
            # If anything goes wrong in getting the label just set it to ERR; we really don't care except for logging.
            label = "<LABEL-ERR>"
        self.logger.info(
            "Initialized Thread: Bulb: %s // Continuous: %s", label, self.continuous
        )

    def match_color(self, bulb):
        """ ColorThread target which calls the 'change_color' function on the bulb. """
        self.logger.debug("Starting color match.")
        self.prev_color = (
            self.parent.get_color_values_hsbk()
        )  # coupling to LightFrame from gui.py here
        while not self.thread.stopped():
            try:
                color = list(
                    self.color_function(initial_color=self.prev_color, **self.kwargs)
                )
                color[2] = self.limit_brightness(
                    color[2] + self.get_brightness_offset()
                )
                bulb.set_color(
                    color, duration=self.get_duration() * 1000, rapid=self.continuous
                )
                self.prev_color = color
            except OSError:
                # This is dirty, but we really don't care, just keep going
                self.logger.info("Hit an os error")
                continue
            if not self.continuous:
                self.stop()
        self.logger.debug("Color match finished.")

    def start(self):
        """ Start the match_color thread"""
        if self.thread.stopped():
            self.thread = ColorThread(target=self.match_color, args=(self.bulb,))
        try:
            self.thread.start()
            self.logger.debug("Thread started.")
        except RuntimeError:
            self.logger.error("Tried to start ColorThread again.")

    def stop(self):
        """ Stop the match_color thread"""
        self.thread.stop()

    @staticmethod
    def get_duration():
        """ Read the transition duration from the config file. """
        return float(config["AverageColor"]["duration"])

    @staticmethod
    def get_brightness_offset():
        """ Read the brightness offset from the config file. """
        return int(config["AverageColor"]["brightnessoffset"])

    @staticmethod
    def limit_brightness(brightness):
        """ Cap brightness at the configured max; snap to 0 below the configured min cutoff. """
        brightness = min(
            brightness, config["AverageColor"].getint("maxbrightness", fallback=65535)
        )
        if brightness < config["AverageColor"].getint("minbrightnesscutoff", fallback=0):
            brightness = 0
        return brightness


# Route uncaught thread exceptions through sys.excepthook so they land in the app log.
threading.excepthook = lambda args: sys.excepthook(
    args.exc_type, args.exc_value, args.exc_traceback
)
