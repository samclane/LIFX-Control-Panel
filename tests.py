""" This is not a standard test file (yet), but used to simulate a multi-device environment. """

from collections import namedtuple

DummyColor = namedtuple('hsbk_color', 'hue saturation brightness kelvin')


class DummyBulb:
    def __init__(self, color=DummyColor(0, 0, 0, 2500), label="No Label"):
        self.color = color
        self.label = label
        self.power = False

    # Official api
    def get_label(self):
        return self.label

    def get_power(self):
        return self.power

    def set_power(self, val: bool):
        self.power = val
        return self.get_power()

    def get_color(self):
        return self.color

    def set_color(self, val: DummyColor, rapid: bool = False):
        self.color = val
        return self.get_color()


class LifxLANDummy:
    def __init__(self, verbose=False):
        self.dummy_lights = {}

    # Non-offical api to manipulate for testing
    def add_dummy_light(self, light: DummyBulb):
        self.dummy_lights[light.get_label()] = light

    # Official api
    def get_lights(self):
        return tuple(light for light in self.dummy_lights.values())


if __name__ == "__main__":
    from lifxlan import LifxLAN
    from gui import LifxFrame
    from tkinter import *
    from resources import main_icon
    import base64
    import os

    # Build mixed list of fake and real lights
    lifx = LifxLANDummy()
    lifx.add_dummy_light(DummyBulb(label="A Light"))
    lifx.add_dummy_light(DummyBulb(label="B Light"))
    for light in LifxLAN().get_lights():
        lifx.add_dummy_light(light)

    root = Tk()
    root.title("LIFX Manager")

    # Setup main_icon
    icondata = base64.b64decode(main_icon)
    tempfile = "main_icon.ico"
    iconfile = open(tempfile, 'wb')
    iconfile.write(icondata)
    iconfile.close()
    root.wm_iconbitmap(tempfile)
    os.remove(tempfile)

    mainframe = LifxFrame(root, lifx)

    # Setup exception logging
    logger = mainframe.logger


    def myHandler(type, value, tb):
        logger.exception("Uncaught exception: {}".format(str(value)))


    sys.excepthook = myHandler

    # Run main app
    root.mainloop()
