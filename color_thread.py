#!/usr/bin/env python
# coding=utf-8
import logging
import threading
from time import sleep

from PIL import ImageGrab, Image
from lifxlan import LifxLAN, utils


def avg_screen_color(initial_color):
    im = ImageGrab.grab()
    color = im.resize((1, 1), Image.HAMMING).getpixel((0, 0))
    return utils.RGBtoHSBK(color, temperature=initial_color[3])


class ColorThread(threading.Thread):
    def __init__(self, *args, **kwargs):
        super(ColorThread, self).__init__(*args, **kwargs)
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()


class ColorThreadRunner:
    def __init__(self, bulb, color_function, parent, continuous=True):
        self.bulb = bulb
        self.color_function = color_function
        self.parent = parent  # couple to parent frame
        self.logger = logging.getLogger(parent.logger.name + '.{}'.format(color_function.__name__))
        self.prev_color = parent.get_color_values_hsbk()
        self.continuous = continuous
        self.t = ColorThread(target=self.match_color, args=(self.bulb,))
        self.t.setDaemon(True)
        self.logger.info(
            'Initialized Thread: Function: {} // Continuous: {}'.format(self.bulb.get_label(), self.continuous))

    def match_color(self, bulb):
        self.logger.debug('Starting color match.')
        self.prev_color = self.parent.get_color_values_hsbk()  # coupling to LightFrame from gui.py here
        duration_secs = 1 / 15
        transition_time_ms = duration_secs * 1000
        while not self.t.stopped():
            try:
                color = self.color_function(initial_color=self.prev_color)
                bulb.set_color(color, transition_time_ms,
                               True if duration_secs < 1 else False)
                self.prev_color = color
            except OSError:
                # This is dirty, but we really don't care, just keep going
                continue
            sleep(duration_secs)
            if not self.continuous:
                self.stop()
        self.logger.debug('Color match finished.')

    def start(self):
        self.logger.debug('Thread started.')
        if self.t.stopped():
            self.t = ColorThread(target=self.match_color, args=(self.bulb,))
            self.t.setDaemon(True)
        self.t.start()

    def stop(self):
        self.logger.debug('Thread stopped')
        self.t.stop()


### Testing stuff ###

def match_color_test(bulb):
    duration_secs = 0.25
    transition_time_ms = duration_secs * 1000
    while True:  # Blocking!
        bulb.set_color(avg_screen_color([0, 0, 0, 9000]), transition_time_ms, True if duration_secs < 1 else False)
        sleep(duration_secs)


def main():
    num_lights = 1
    print("Discovering lights...")
    lifx = LifxLAN(num_lights)
    # get devices
    devices = lifx.get_lights()
    bulb = devices[0]
    print("Selected {}".format(bulb.get_label()))
    # get original state
    original_power = bulb.get_power()
    original_color = bulb.get_color_values_hsbk()
    bulb.set_power("on")

    match_color_test(bulb)


if __name__ == "__main__":
    main()
