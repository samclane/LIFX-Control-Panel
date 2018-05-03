#!/usr/bin/env python
# coding=utf-8
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
    def __init__(self, bulb, color_function, initial_color):
        self.bulb = bulb
        self.color_function = color_function
        self.initial_color = initial_color
        self.t = ColorThread(target=self.match_color, args=(self.bulb,))
        self.t.setDaemon(True)

    def match_color(self, bulb):
        duration_secs = 1 / 30
        transition_time_ms = duration_secs * 1000
        while not self.t.stopped():
            try:
                bulb.set_color(self.color_function(initial_color=self.initial_color), transition_time_ms,
                               True if duration_secs < 1 else False)
            except OSError:
                # This is dirty, but we really don't care, just keep going
                continue
            sleep(duration_secs)

    def start(self):
        if self.t.stopped():
            self.t = ColorThread(target=self.match_color, args=(self.bulb,))
            self.t.setDaemon(True)
        self.t.start()

    def stop(self):
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
    original_color = bulb.get_color()
    bulb.set_power("on")

    match_color_test(bulb)


if __name__ == "__main__":
    main()
