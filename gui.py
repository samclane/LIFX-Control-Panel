from tkinter import *
from tkinter import ttk
from tkinter.colorchooser import *

from lifxlan import LifxLAN, WHITE, WARM_WHITE, COLD_WHITE, GOLD, utils

import average_color

HEARTBEAT_RATE = 3000  # 3 seconds


class LifxFrame(ttk.Frame):
    def __init__(self, master):
        ttk.Frame.__init__(self, master, padding="3 3 12 12")
        self.master = master
        self.grid(column=0, row=0, sticky=(N, W, E, S))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.lightvar = StringVar(self)

        self.lifx = LifxLAN(verbose=False)
        self.lights = self.lifx.get_lights()
        self.lightsdict = {}

        for key, light in enumerate(self.lights):
            self.lightsdict[light.get_label()] = light

        self.lightvar.set(self.lights[0].get_label())
        self.current_light = self.lightsdict[self.lightvar.get()]

        self.dropdownMenu = OptionMenu(self, self.lightvar, *(light.get_label() for light in self.lights))
        Label(self, text="Light: ").grid(row=0, column=1)
        self.dropdownMenu.grid(row=1, column=1)
        self.lightvar.trace('w', self.change_dropdown)

        if len(self.lightsdict):
            self.change_dropdown()

    def change_dropdown(self, *args):
        self.current_light = self.lightsdict[self.lightvar.get()]
        self.lf = LightFrame(self, self.current_light)


class LightFrame(ttk.Labelframe):
    def __init__(self, master, bulb):
        ttk.Labelframe.__init__(self, master, padding="3 3 12 12", text=bulb.get_label())
        self.grid(column=1, row=0, sticky=(N, W, E, S))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.bulb = bulb

        self.powervar = BooleanVar(self)
        self.powervar.set(bulb.get_power())
        self.option_on = Radiobutton(self, text="On", variable=self.powervar, value=65535, command=self.update_power)
        self.option_off = Radiobutton(self, text="Off", variable=self.powervar, value=0, command=self.update_power)
        if self.powervar.get() == 0:
            # Light is off
            self.option_off.select()
            self.option_on.selection_clear()
        else:
            self.option_on.select()
            self.option_off.selection_clear()
        self.option_on.grid(row=0, column=0)
        self.option_off.grid(row=0, column=1)

        h, s, b, k = bulb.get_color()
        self.hsbk = (IntVar(self, h, "Hue"),
                     IntVar(self, s, "Saturation"),
                     IntVar(self, b, "Brightness"),
                     IntVar(self, k, "Kelvin"))
        self.hsbk_scale = (
            Scale(self, from_=0, to=65535, orient=HORIZONTAL, variable=self.hsbk[0], command=self.update_color),
            Scale(self, from_=0, to=65535, orient=HORIZONTAL, variable=self.hsbk[1], command=self.update_color),
            Scale(self, from_=0, to=65535, orient=HORIZONTAL, variable=self.hsbk[2], command=self.update_color),
            Scale(self, from_=2500, to=9000, orient=HORIZONTAL, variable=self.hsbk[3], command=self.update_color))
        for key, scale in enumerate(self.hsbk_scale):
            Label(self, text=self.hsbk[key]._name).grid(row=key + 1, column=0)
            scale.grid(row=key + 1, column=1)

        Button(self, text="White", command=lambda: self.set_color(WHITE)).grid(row=5, column=0)
        Button(self, text="Warm White", command=lambda: self.set_color(WARM_WHITE)).grid(row=5, column=1)
        Button(self, text="Cold White", command=lambda: self.set_color(COLD_WHITE)).grid(row=5, column=2)
        Button(self, text="Gold", command=lambda: self.set_color(GOLD)).grid(row=6, column=0)
        self.acm = average_color.AverageColorMatcher(self.bulb)
        Button(self, text="Avg. Color", command=self.acm.start).grid(row=6, column=1)
        Button(self, text="Pick Color", command=self.get_color_hbsk).grid(row=6, column=2)

        self.after(HEARTBEAT_RATE, self.update_status_from_bulb)

    def update_power(self):
        self.acm.stop()
        self.bulb.set_power(self.powervar.get())

    def update_color(self, *args):
        self.acm.stop()
        self.bulb.set_color([c.get() for c in self.hsbk], rapid=True)

    def set_color(self, color):
        self.acm.stop()
        self.bulb.set_color(color)
        for key, val in enumerate(self.hsbk):
            self.hsbk[key].set(color[key])

    def get_color_hbsk(self):
        color = askcolor()
        hbsk = [min(c, 65535) for c in utils.RGBtoHSBK(color[0], self.hsbk[3].get())]
        self.set_color(hbsk)

    def update_status_from_bulb(self):
        self.powervar.set(self.bulb.get_power())
        if self.powervar.get() == 0:
            # Light is off
            self.option_off.select()
            self.option_on.selection_clear()
        else:
            self.option_on.select()
            self.option_off.selection_clear()
        hsbk = (h, s, b, k) = self.bulb.get_color()
        for key, val in enumerate(self.hsbk):
            self.hsbk[key].set(hsbk[key])
        self.after(HEARTBEAT_RATE, self.update_status_from_bulb)


if __name__ == "__main__":
    root = Tk()
    root.title("LIFX Manager")
    mainframe = LifxFrame(root)

    root.mainloop()
