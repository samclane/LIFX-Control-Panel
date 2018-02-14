#!/usr/bin/env python
# coding=utf-8
from time import sleep
from lifxlan import BLUE, GREEN, LifxLAN
import pyautogui
from PIL import Image, ImageColor
import colorsys

def get_avg_color():
    screenshot = pyautogui.screenshot()
    screenshot2 = screenshot.resize((1, 1))
    color = screenshot2.getpixel((0, 0))
    print('#{:02x}{:02x}{:02x}'.format(*color))
    hsv_color = colorsys.rgb_to_hsv(*color)
    print(hsv_color)
    hsv_fixed = [hsv_color[0]*65535, hsv_color[1]*65535, hsv_color[2]*(65535/255)]
    return hsv_fixed + [9000]

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

    duration_secs = 0.25
    transition_time_ms = duration_secs*1000
    while True:
        bulb.set_color(get_avg_color(), transition_time_ms, True if duration_secs < 1 else False)
        sleep(duration_secs)

if __name__=="__main__":
    main()