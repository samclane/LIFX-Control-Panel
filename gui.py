from tkinter import *
from tkinter import ttk

from lifxlan import LifxLAN


class LifxFrame(ttk.Frame):
    def __init__(self, master):
        ttk.Frame.__init__(self, master, padding="3 3 12 12")
        self.grid(column=0, row=0, sticky=(N, W, E, S))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.lightvar = StringVar(self)

        print("Discovering lights")
        self.lifx = LifxLAN(verbose=False)
        self.lights = self.lifx.get_lights()
        self.lightsdict = {}

        for key, light in enumerate(self.lights):
            self.lightsdict[light.get_label()] = light

        self.lightvar.set(self.lights[0].get_label())
        self.current_light = self.lightsdict[self.lightvar.get()]

        self.dropdownMenu = OptionMenu(self, self.lightvar, *(light.get_label() for light in self.lights))
        Label(self, text="Light: ").grid(row=1, column=1)
        self.dropdownMenu.grid(row=2, column=1)
        self.lightvar.trace('w', self.change_dropdown)

    def change_dropdown(self, *args):
        self.current_light = self.lightsdict[self.lightvar.get()]
        self.lf = LightFrame(self, self.current_light)


class LightFrame(ttk.Frame):
    def __init__(self, master, bulb):
        ttk.Frame.__init__(self, master, padding="3 3 12 12")
        self.grid(column=0, row=0, sticky=(N, W, E, S))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.bulb = bulb

        self.powervar = BooleanVar(self)
        self.powervar.set(bulb.get_power())
        self.option_on = Radiobutton(self, text="On", variable=self.powervar, value=65535, command=self.change_power)
        self.option_off = Radiobutton(self, text="Off", variable=self.powervar, value=0, command=self.change_power)
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
        Scale(self, from_=0, to=65535, orient=HORIZONTAL, variable=self.hsbk[0], command=self.change_color),
        Scale(self, from_=0, to=65535, orient=HORIZONTAL, variable=self.hsbk[1], command=self.change_color),
        Scale(self, from_=0, to=65535, orient=HORIZONTAL, variable=self.hsbk[2], command=self.change_color),
        Scale(self, from_=2500, to=9000, orient=HORIZONTAL, variable=self.hsbk[3], command=self.change_color))
        for key, scale in enumerate(self.hsbk_scale):
            scale.set(self.hsbk[key].get())
            scale.grid(row=key + 1, column=0)

    def change_power(self):
        self.bulb.set_power(self.powervar.get())

    def change_color(self, *args):
        self.bulb.set_color([c.get() for c in self.hsbk], rapid=True)


if __name__ == "__main__":
    root = Tk()
    root.title("LIFX Manager")
    mainframe = LifxFrame(root)

    root.mainloop()
