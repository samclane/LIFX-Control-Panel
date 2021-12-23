# -*- coding: utf-8 -*-
"""General utility classes and functions

Contains several classes and functions for quality of life. Used indiscriminately throughout the module.

Notes
-----
    Functions should attempt to not contain stateful information, as this module will be called by other modules
    throughout the program, including other Threads, and as such states may not be coherent.
"""
import os
import sys
import time
from functools import lru_cache
from math import log, floor
from typing import Union, Tuple

import mss


class Color:
    """ Container class for a single color vector in HSBK color-space. """

    __slots__ = ["hue", "saturation", "brightness", "kelvin"]

    def __init__(self, hue: int, saturation: int, brightness: int, kelvin: int):
        self.hue = hue
        self.saturation = saturation
        self.brightness = brightness
        self.kelvin = kelvin

    def __getitem__(self, item) -> int:
        return self.__getattribute__(self.__slots__[item])

    def __len__(self) -> int:
        return 4

    def __setitem__(self, key, value):
        self.__setattr__(self.__slots__[key], value)

    def __str__(self) -> str:
        return f"[{self.hue}, {self.saturation}, {self.brightness}, {self.kelvin}]"

    def __repr__(self) -> str:
        return [self.hue, self.saturation, self.brightness, self.kelvin].__repr__()

    def __eq__(self, other) -> bool:
        return (
            self.hue == other.hue
            and self.brightness == other.brightness
            and self.saturation == other.saturation
            and self.kelvin == other.kelvin
        )

    def __add__(self, other):
        return Color(
            self.hue + other[0],
            self.saturation + other[1],
            self.brightness + other[2],
            self.kelvin + other[3],
        )

    def __sub__(self, other):
        return self.__add__([-v for v in other])

    def __iter__(self):
        return iter([self.hue, self.saturation, self.brightness, self.kelvin])


# Derived types
TypeRGB = Union[Tuple[int, int, int], Color]
TypeHSBK = Union[Tuple[int, int, int, int], Color]


def hsbk_to_rgb(hsbk: TypeHSBK) -> TypeRGB:
    """ Convert Tuple in HSBK color-space to RGB space.
    Converted from PHP https://gist.github.com/joshrp/5200913 """
    # pylint: disable=invalid-name
    iH, iS, iB, iK = hsbk
    dS = (100 * iS / 65535) / 100.0  # Saturation: 0.0-1.0
    dB = (100 * iB / 65535) / 100.0  # Lightness: 0.0-1.0
    dC = dB * dS  # Chroma: 0.0-1.0
    dH = (360 * iH / 65535) / 60.0  # H-prime: 0.0-6.0
    dT = dH  # Temp variable

    while dT >= 2.0:  # php modulus does not work with float
        dT -= 2.0
    dX = dC * (1 - abs(dT - 1))

    dHf = floor(dH)
    if dHf == 0:
        dR = dC
        dG = dX
        dB = 0.0
    elif dHf == 1:
        dR = dX
        dG = dC
        dB = 0.0
    elif dHf == 2:
        dR = 0.0
        dG = dC
        dB = dX
    elif dHf == 3:
        dR = 0.0
        dG = dX
        dB = dC
    elif dHf == 4:
        dR = dX
        dG = 0.0
        dB = dC
    elif dHf == 5:
        dR = dC
        dG = 0.0
        dB = dX
    else:
        dR = 0.0
        dG = 0.0
        dB = 0.0

    dM = dB - dC
    dR += dM
    dG += dM
    dB += dM

    # Finally, factor in Kelvin
    # Adopted from:
    # https://github.com/tort32/LightServer/blob/master/src/main/java/com/github/tort32/api/nodemcu/protocol/RawColor.java#L125
    rgb_hsb = int(dR * 255), int(dG * 255), int(dB * 255)
    rgb_k = kelvin_to_rgb(iK)
    a = iS / 65535.0
    b = (1.0 - a) / 255
    x = int(rgb_hsb[0] * (a + rgb_k[0] * b))
    y = int(rgb_hsb[1] * (a + rgb_k[1] * b))
    z = int(rgb_hsb[2] * (a + rgb_k[2] * b))
    return x, y, z


def hue_to_rgb(h: float, s: float = 1, v: float = 1) -> TypeRGB:
    """ Convert a Hue-angle to an RGB value for display. """
    # pylint: disable=invalid-name
    h = float(h)
    s = float(s)
    v = float(v)
    h60 = h / 60.0
    h60f = floor(h60)
    hi = int(h60f) % 6
    f = h60 - h60f
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)
    r, g, b = 0, 0, 0
    if hi == 0:
        r, g, b = v, t, p
    elif hi == 1:
        r, g, b = q, v, p
    elif hi == 2:
        r, g, b = p, v, t
    elif hi == 3:
        r, g, b = p, q, v
    elif hi == 4:
        r, g, b = t, p, v
    elif hi == 5:
        r, g, b = v, p, q
    r, g, b = int(r * 255), int(g * 255), int(b * 255)
    return r, g, b


def kelvin_to_rgb(temperature: int) -> TypeRGB:
    """ Convert a Kelvin (K) color-temperature to an RGB value for display."""
    # pylint: disable=invalid-name
    temperature /= 100
    if temperature <= 66:
        red = 255
        green = temperature
        green = 99.4708025861 * log(green + 0.0000000001) - 161.1195681661
    else:
        red = temperature - 60
        red = 329.698727466 * (red ** -0.1332047592)
        red = max(red, 0)
        red = min(red, 255)
        green = temperature - 60
        green = 288.1221695283 * (green ** -0.0755148492)
    green = max(green, 0)
    green = min(green, 255)
    # calc blue
    if temperature >= 66:
        blue = 255
    elif temperature <= 19:
        blue = 0
    else:
        blue = temperature - 10
        blue = 138.5177312231 * log(blue) - 305.0447927307
        blue = max(blue, 0)
        blue = min(blue, 255)
    return int(red), int(green), int(blue)


def tuple2hex(tuple_: TypeRGB) -> str:
    """ Takes a color in tuple form and converts it to hex. """
    return "#%02x%02x%02x" % tuple_


def str2list(string: str, type_func) -> list:
    """ Takes a Python list-formatted string and returns a list of elements of type type_func """
    return list(map(type_func, string.strip("()[]").split(",")))


def str2tuple(string: str, type_func) -> tuple:
    """ Takes a Python list-formatted string and returns a tuple of type type_func """
    return tuple(map(type_func, string.strip("()[]").split(",")))


# Multi monitor methods
@lru_cache(maxsize=None)
def get_primary_monitor() -> Tuple[int, int, int, int]:
    """ Return the system's default primary monitor rectangle bounds. """
    return [rect for rect in get_display_rects() if rect[:2] == (0, 0)][
        0
    ]  # primary monitor has top left as 0, 0


def resource_path(relative_path) -> Union[int, bytes]:
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS  # pylint: disable=protected-access,no-member
    except Exception:  # pylint: disable=broad-except
        base_path = os.path.abspath("../")

    return os.path.join(base_path, relative_path)


# Misc


def timeit(method):
    def timed(*args, **kw):
        t_start = time.time()
        result = method(*args, **kw)
        t_end = time.time()
        if "log_time" in kw:
            name = kw.get("log_name", method.__name__.upper())
            kw["log_time"][name] = int((t_end - t_start) * 1000)
        else:
            print("%r  %2.2f ms" % (method.__name__, (t_end - t_start) * 1000))
        return result

    return timed


def get_display_rects():
    with mss.mss() as sct:
        return [tuple(m.values()) for m in sct.monitors]
