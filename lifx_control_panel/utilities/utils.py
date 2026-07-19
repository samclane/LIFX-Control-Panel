# -*- coding: utf-8 -*-
"""General utility classes and functions."""
import colorsys
import os
import subprocess
import sys
from functools import lru_cache
from math import log, floor
from typing import NamedTuple, Union, Tuple, List

import mss


class Color(NamedTuple):
    """ A single color vector in HSBK color-space. """

    hue: int
    saturation: int
    brightness: int
    kelvin: int


# Derived types
TypeRGB = Union[Tuple[int, int, int], Color]
TypeHSBK = Union[Tuple[int, int, int, int], Color]


def hsbk_to_rgb(hsvk: TypeHSBK) -> TypeRGB:
    """ Convert Tuple in HSBK color-space to RGB space.
    Converted from PHP https://gist.github.com/joshrp/5200913 """
    # pylint: disable=invalid-name
    iH, iS, iV, iK = hsvk
    dS = (100 * iS / 65535) / 100.0  # Saturation: 0.0-1.0
    dV = (100 * iV / 65535) / 100.0  # Lightness: 0.0-1.0
    dC = dV * dS  # Chroma: 0.0-1.0
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

    dM = dV - dC
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


def hsv_to_rgb(h: float, s: float = 1, v: float = 1) -> TypeRGB:
    """ Convert a Hue-angle to an RGB value for display. """
    return tuple(int(c * 255) for c in colorsys.hsv_to_rgb(float(h) / 360, s, v))


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


def str2list(string: str, type_func) -> List:
    """ Takes a Python list-formatted string and returns a list of elements of type type_func """
    return list(map(type_func, string.strip("()[]").split(",")))


def str2tuple(string: str, type_func) -> Tuple:
    """ Takes a Python list-formatted string and returns a tuple of type type_func """
    return tuple(str2list(string, type_func))


# Multi monitor methods
@lru_cache(maxsize=None)
def get_primary_monitor() -> Tuple[int, ...]:
    """ Return the system's default primary monitor rectangle bounds. """
    # primary monitor has top left as 0, 0
    return next(rect for rect in get_display_rects() if rect[:2] == (0, 0))


def resource_path(relative_path) -> Union[int, bytes]:
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS  # pylint: disable=protected-access,no-member
    except Exception:  # pylint: disable=broad-except
        # repo root = two dirs up from this file (lifx_control_panel/utilities/utils.py).
        # CWD-independent, unlike the old os.path.abspath("../").
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    return os.path.join(base_path, relative_path)


def get_display_rects():
    """ Return a list of tuples of monitor rectangles. """
    with mss.mss() as sct:
        return [tuple(m.values()) for m in sct.monitors]


# ponytail: a Startup-folder .lnk instead of a registry Run entry — the app reads
# config.ini relative to cwd, and only a shortcut can set the working directory.
STARTUP_LNK = os.path.join(
    os.environ.get("APPDATA", ""),
    r"Microsoft\Windows\Start Menu\Programs\Startup",
    "LIFX-Control-Panel.lnk",
)


def get_launch_on_startup() -> bool:
    """ The shortcut's existence is the setting; no config entry to drift out of sync. """
    return os.path.exists(STARTUP_LNK)


def set_launch_on_startup(enable: bool):
    """ Create or remove the Startup-folder shortcut. """
    if not enable:
        if os.path.exists(STARTUP_LNK):
            os.remove(STARTUP_LNK)
        return
    if getattr(sys, "frozen", False):  # PyInstaller exe
        target, args = sys.executable, ""
    else:
        target = sys.executable.replace("python.exe", "pythonw.exe")
        args = '"{}"'.format(os.path.abspath(sys.argv[0]))
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');"
            "$s.TargetPath='{target}';$s.Arguments='{args}';"
            "$s.WorkingDirectory='{cwd}';$s.Save()".format(
                lnk=STARTUP_LNK, target=target, args=args, cwd=os.getcwd()
            ),
        ],
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
