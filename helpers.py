from functools import lru_cache
from math import log, floor

from desktopmagic.screengrab_win32 import *


def HSBKtoRGB(hsvk):
    iH, iS, iV, iK = hsvk
    dS = (100 * iS / 65535) / 100.0
    dV = (100 * iV / 65535) / 100.0
    dC = dV * dS
    dH = (360 * iH / 65535) / 60.0
    dT = dH

    while dT >= 2.0:
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

    """    
    rgb_prime = int(dR * 255), int(dG * 255), int(dB * 255)
    rgb_k = KelvinToRGB(iK)
    return_rgb = tuple(int(min(255, a+b)) for (a, b) in zip(rgb_prime, rgb_k))  # Light model
    return_rgb = tuple(int((a+b)/2) for (a, b) in zip(rgb_prime, rgb_k))  # Gradient model
    return return_rgb
    """

    return int(dR * 255), int(dG * 255), int(dB * 255)


def HueToRGB(h, s=1, v=1):
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


def KelvinToRGB(temperature):
    temperature /= 100
    # calc red
    if temperature < 66:
        red = 255
    else:
        red = temperature - 60
        red = 329.698727446 * (red ** -0.1332047592)
        if red < 0: red = 0
        if red > 255: red = 255
    # calc green
    if temperature < 66:
        green = temperature
        green = 99.4708025861 * log(green) - 161.1195681661
        if green < 0:
            green = 0
        if green > 255:
            green = 255
    else:
        green = temperature - 60
        green = 288.1221695283 * (green ** -0.0755148492)
        if green < 0:
            green = 0
        if green > 255:
            green = 255
    # calc blue
    if temperature >= 66:
        blue = 255
    else:
        if temperature < 19:
            blue = 0
        else:
            blue = temperature - 10
            blue = 138.5177312231 * log(blue) - 305.0447927307
            if blue < 0:
                blue = 0
            if blue > 255:
                blue = 255
    return int(red), int(green), int(blue)


def tuple2hex(tuple):
    """ Takes a color in tuple form an converts it to hex. """
    return '#%02x%02x%02x' % tuple


# Multi monitor methods
@lru_cache(maxsize=None)
def get_primary_monitor():
    return [rect for rect in getDisplayRects() if rect[:2] == (0, 0)][0]  # primary monitor has top left as 0, 0
