#!/usr/bin/env python
# coding=utf-8
import threading
from time import sleep
from PIL import ImageGrab, Image

from lifxlan import LifxLAN, utils


def get_avg_color(temp=9000):
    im = ImageGrab.grab()
    color = im.resize((1, 1), Image.ANTIALIAS).getpixel((0, 0))
    return utils.RGBtoHSBK(color, temperature=temp)


def match_color_test(bulb):
    duration_secs = 0.25
    transition_time_ms = duration_secs * 1000
    while True:  # Blocking!
        bulb.set_color(get_avg_color(), transition_time_ms, True if duration_secs < 1 else False)
        sleep(duration_secs)


class AverageColorThread(threading.Thread):
    def __init__(self, *args, **kwargs):
        super(AverageColorThread, self).__init__(*args, **kwargs)
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def stopped(self):
        return self._stop.isSet()


class AverageColorMatcher:
    def __init__(self, bulb, temp=9000):
        self.bulb = bulb
        self.temp = temp
        self.t = AverageColorThread(target=self.match_color, args=(self.bulb,))
        self.t.setDaemon(True)

    def match_color(self, bulb):
        duration_secs = 0.25
        transition_time_ms = duration_secs * 1000
        while not self.t.stopped():
            bulb.set_color(get_avg_color(temp=self.temp), transition_time_ms, True if duration_secs < 1 else False)
            sleep(duration_secs)

    def start(self):
        if self.t.stopped():
            self.t = AverageColorThread(target=self.match_color, args=(self.bulb,))
            self.t.setDaemon(True)
        self.t.start()

    def stop(self):
        self.t.stop()


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
