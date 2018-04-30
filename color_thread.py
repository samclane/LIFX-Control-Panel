#!/usr/bin/env python
# coding=utf-8
import threading
from time import sleep
from PIL import ImageGrab, Image

from lifxlan import LifxLAN, utils


def avg_screen_color(temp=9000):
    im = ImageGrab.grab()
    color = im.resize((1, 1), Image.ANTIALIAS).getpixel((0, 0))
    return utils.RGBtoHSBK(color, temperature=temp)


class ColorThread(threading.Thread):
    def __init__(self, *args, **kwargs):
        super(ColorThread, self).__init__(*args, **kwargs)
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()


class ColorThreadRunner:
    def __init__(self, bulb, color_fuction, temp=9000):
        self.bulb = bulb
        self.color_function = color_fuction
        self.temp = temp
        self.t = ColorThread(target=self.match_color, args=(self.bulb,))
        self.t.setDaemon(True)

    def match_color(self, bulb):
        duration_secs = 0.25
        transition_time_ms = duration_secs * 1000
        while not self.t.stopped():
            try:
                bulb.set_color(self.color_function(temp=self.temp), transition_time_ms,
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


def match_color_test(bulb):
    duration_secs = 0.25
    transition_time_ms = duration_secs * 1000
    while True:  # Blocking!
        bulb.set_color(avg_screen_color(), transition_time_ms, True if duration_secs < 1 else False)
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
