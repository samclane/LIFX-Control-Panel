import os
from tkinter import *
from tkinter import ttk
from tkinter.colorchooser import *

from lifxlan import LifxLAN, WHITE, WARM_WHITE, COLD_WHITE, GOLD, utils, errors

import audio
import color_thread

HEARTBEAT_RATE = 3000  # 3 seconds


class LifxFrame(ttk.Frame):
    def __init__(self, master):
        ttk.Frame.__init__(self, master, padding="3 3 12 12")
        self.master = master
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)
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
        self.lightvar.trace('w', self.change_dropdown)  # Keep lightvar in sync with drop-down selection

        if len(self.lightsdict):
            self.change_dropdown()

    def change_dropdown(self, *args):
        """ Change current display frame when dropdown menu is changed. """
        self.current_light = self.lightsdict[self.lightvar.get()]
        self.lf = LightFrame(self, self.current_light)

    def on_closing(self):
        self.master.destroy()
        os._exit(1)


class LightFrame(ttk.Labelframe):
    def __init__(self, master, bulb):
        # Initialize frame
        ttk.Labelframe.__init__(self, master, padding="3 3 12 12", text=bulb.get_label())
        self.grid(column=1, row=0, sticky=(N, W, E, S))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.bulb = bulb

        # Initialize vars to hold on/off state
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

        # Initialize vars to hold and display bulb color
        hsbk = h, s, b, k = bulb.get_color()
        self.hsbk = (IntVar(self, h, "Hue"),
                     IntVar(self, s, "Saturation"),
                     IntVar(self, b, "Brightness"),
                     IntVar(self, k, "Kelvin"))
        self.hsbk_labels = (
            Label(self, text='%.3g' % (360 * (self.hsbk[0].get() / 65535))),
            Label(self, text=str('%.3g' % (100 * self.hsbk[1].get() / 65535)) + "%"),
            Label(self, text=str('%.3g' % (100 * self.hsbk[2].get() / 65535)) + "%"),
            Label(self, text=str(self.hsbk[3].get()) + " K")
        )
        self.hsbk_scale = (
            Scale(self, from_=0, to=65535, orient=HORIZONTAL, variable=self.hsbk[0], command=self.update_color,
                  showvalue=False),
            Scale(self, from_=0, to=65535, orient=HORIZONTAL, variable=self.hsbk[1], command=self.update_color,
                  showvalue=False),
            Scale(self, from_=0, to=65535, orient=HORIZONTAL, variable=self.hsbk[2], command=self.update_color,
                  showvalue=False),
            Scale(self, from_=2500, to=9000, orient=HORIZONTAL, variable=self.hsbk[3], command=self.update_color,
                  showvalue=False))
        for key, scale in enumerate(self.hsbk_scale):
            Label(self, text=self.hsbk[key]).grid(row=key + 1, column=0)
            scale.grid(row=key + 1, column=1)
            self.hsbk_labels[key].grid(row=key + 1, column=2)

        # Add buttons for pre-made colors and routines
        Button(self, text="White", command=lambda: self.set_color(WHITE)).grid(row=5, column=0)
        Button(self, text="Warm White", command=lambda: self.set_color(WARM_WHITE)).grid(row=5, column=1)
        Button(self, text="Cold White", command=lambda: self.set_color(COLD_WHITE)).grid(row=5, column=2)
        Button(self, text="Gold", command=lambda: self.set_color(GOLD)).grid(row=6, column=0)
        self.acm = color_thread.ColorThreadRunner(self.bulb, color_thread.avg_screen_color, hsbk)
        Button(self, text="Avg. Screen Color", command=self.acm.start).grid(row=6, column=1)
        Button(self, text="Pick Color", command=self.get_color_hbsk).grid(row=6, column=2)
        self.audio_matcher = color_thread.ColorThreadRunner(self.bulb, audio.get_music_color, hsbk)
        Button(self, text="Music Color*", command=self.audio_matcher.start).grid(row=7, column=0)
        Label(self, text="*=Work in progress").grid(row=8, column=1)

        self.after(HEARTBEAT_RATE, self.update_status_from_bulb)

    def stop_threads(self):
        """ Stop all ColorRunner threads """
        self.acm.stop()
        self.audio_matcher.stop()

    def update_power(self):
        """ Send new power state to bulb when UI is changed. """
        self.stop_threads()
        self.bulb.set_power(self.powervar.get())

    def update_color(self, *args):
        """ Send new color state to bulb when UI is changed. """
        self.stop_threads()
        self.bulb.set_color([c.get() for c in self.hsbk], rapid=True)
        for key, val in enumerate(self.hsbk):
            self.update_label(key)

    def set_color(self, color):
        """ Should be called whenever the bulb wants to change color. Sends bulb command and updates UI accordingly. """
        self.stop_threads()
        self.bulb.set_color(color)
        for key, val in enumerate(self.hsbk):
            self.hsbk[key].set(color[key])
            self.update_label(key)

    def update_label(self, key):
        """ Update scale labels, formatted accordingly. """
        if key == 0:  # H
            self.hsbk_labels[0].config(text=str('%.3g' % (360 * (self.hsbk[0].get() / 65535))))
        elif key == 1:  # S
            self.hsbk_labels[1].config(text=str('%.3g' % (100 * (self.hsbk[1].get() / 65535))) + "%")
        elif key == 2:  # B
            self.hsbk_labels[2].config(text=str('%.3g' % (100 * (self.hsbk[2].get() / 65535))) + "%")
        elif key == 3:  # K
            self.hsbk_labels[3].config(text=str(self.hsbk[3].get()) + " K")

    def get_color_hbsk(self):
        """ Asks users for color selection using standard color palette dialog. """
        color = askcolor()[0]
        if color:
            # RGBtoHBSK sometimes returns >65535, so we have to truncate
            hbsk = [min(c, 65535) for c in utils.RGBtoHSBK(color, self.hsbk[3].get())]
            self.set_color(hbsk)

    def update_status_from_bulb(self):
        """ Periodically update status from the bulb to keep UI in sync. """
        try:
            self.powervar.set(self.bulb.get_power())
        except OSError:
            pass
        except errors.WorkflowException:
            pass
        if self.powervar.get() == 0:
            # Light is off
            self.option_off.select()
            self.option_on.selection_clear()
        else:
            self.option_on.select()
            self.option_off.selection_clear()
        try:
            hsbk = self.bulb.get_color()
            for key, val in enumerate(self.hsbk):
                self.hsbk[key].set(hsbk[key])
        except OSError:
            pass
        except errors.WorkflowException:
            pass
        self.after(HEARTBEAT_RATE, self.update_status_from_bulb)


if __name__ == "__main__":
    root = Tk()
    root.title("LIFX Manager")
    mainframe = LifxFrame(root)

    root.mainloop()
