import configparser
import itertools
import logging
from shutil import copyfile
from tkinter import *
from tkinter.colorchooser import *

from desktopmagic.screengrab_win32 import getDisplayRects
from lifxlan import *
from lifxlan.utils import RGBtoHSBK

from helpers import resource_path
from keypress import Keystroke_Watcher

config = configparser.ConfigParser()
if not os.path.isfile("config.ini"):
    copyfile(resource_path("default.ini"), "config.ini")
config.read("config.ini")


# boilerplate code from http://effbot.org/tkinterbook/tkinter-dialog-windows.htm
class Dialog(Toplevel):
    def __init__(self, parent, title=None):
        Toplevel.__init__(self, parent)
        self.transient(parent)
        if title:
            self.title(title)
        self.parent = parent
        self.result = None
        body = Frame(self)
        self.initial_focus = self.body(body)
        body.pack(padx=5, pady=5)
        self.buttonbox()
        self.grab_set()
        if not self.initial_focus:
            self.initial_focus = self
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.geometry("+%d+%d" % (parent.winfo_rootx() + 50,
                                  parent.winfo_rooty() + 50))
        self.initial_focus.focus_set()
        self.wait_window(self)

    # construction hooks
    def body(self, master):
        # create dialog body.  return widget that should have initial focus. This method should be overridden
        pass

    def buttonbox(self):
        # add standard button box. override if you don't want the standard buttons
        box = Frame(self)
        w = Button(box, text="OK", width=10, command=self.ok, default=ACTIVE)
        w.pack(side=LEFT, padx=5, pady=5)
        w = Button(box, text="Cancel", width=10, command=self.cancel)
        w.pack(side=LEFT, padx=5, pady=5)

        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)

        box.pack()

    # standard button semantics
    def ok(self, event=None):
        if not self.validate():
            self.initial_focus.focus_set()  # put focus back
            return
        self.withdraw()
        self.update_idletasks()
        self.apply()
        self.cancel()

    def cancel(self, event=None):
        # put focus back to the parent window
        self.parent.focus_set()
        self.destroy()
        return 0

    # command hooks
    def validate(self):
        return 1  # override

    def apply(self):
        pass  # override


class SettingsDisplay(Dialog):
    def body(self, master):
        self.root_window = master.master.master
        self.logger = logging.getLogger(self.root_window.logger.name + '.SettingsDisplay')
        # Labels
        Label(master, text="Avg. Monitor Default: ").grid(row=0, column=0)
        Label(master, text="Add Preset Color: ").grid(row=1, column=0)
        Label(master, text="Add keyboard shortcut").grid(row=2, column=0)

        # Widgets
        # Avg monitor color match
        self.avg_monitor = StringVar(master, value=config["AverageColor"]["DefaultMonitor"])
        options = []
        lst = getDisplayRects()
        for i in range(1, len(lst) + 1):
            els = [list(x) for x in itertools.combinations(lst, i)]
            options.extend(els)
        self.avg_monitor_dropdown = OptionMenu(master, self.avg_monitor, *lst, 'all')

        # Custom preset color
        self.preset_color_name = Entry(master)
        self.preset_color_name.insert(END, "Enter color name...")
        self.preset_color_button = Button(master, text="Choose and add!", command=self.get_color)

        # Add keybindings
        lightnames = list(self.root_window.lightsdict.keys())
        self.keybind_bulb_selection = StringVar(master, value=lightnames[0])
        self.keybind_bulb_dropdown = OptionMenu(master, self.keybind_bulb_selection,
                                                *lightnames)
        self.keybind_keys_select = Entry(master)
        self.keybind_keys_select.insert(END, "Add key-combo...")
        self.keybind_keys_select.config(state='readonly')
        self.keybind_keys_select.bind('<FocusIn>', self.on_keybind_keys_click)
        self.keybind_color_selection = StringVar(master)
        self.keybind_color_dropdown = OptionMenu(master, self.keybind_color_selection,
                                                 *self.root_window.framesdict[
                                                     self.keybind_bulb_selection.get()].default_colors)
        self.keybind_add_button = Button(master, text="Add keybind",
                                         command=lambda *args: self.register_keybinding(
                                             self.keybind_bulb_selection.get(), self.keybind_keys_select.get(),
                                             self.keybind_color_selection.get()))

        # Insert
        self.avg_monitor_dropdown.grid(row=0, column=1)
        self.preset_color_name.grid(row=1, column=1)
        self.preset_color_button.grid(row=1, column=2)
        self.keybind_bulb_dropdown.grid(row=2, column=1)
        self.keybind_keys_select.grid(row=2, column=2)
        self.keybind_color_dropdown.grid(row=2, column=3)
        self.keybind_add_button.grid(row=2, column=4)

    def validate(self):
        config["AverageColor"]["DefaultMonitor"] = str(self.avg_monitor.get())

        # Write to config file
        with open('config.ini', 'w') as cfg:
            config.write(cfg)

        self.k.shutdown()

        return 1

    def get_color(self):
        color = askcolor()[0]
        if color:
            # RGBtoHBSK sometimes returns >65535, so we have to truncate
            hsbk = [min(c, 65535) for c in RGBtoHSBK(color)]
            config["PresetColors"][self.preset_color_name.get()] = str(hsbk)

    def register_keybinding(self, bulb: str, keys: str, color: str):
        color = eval(color)  # should match color to variable w/ same name
        # self.root_window.keylogger.register_function(keys, lambda *args: self.root_window.lightsdict[bulb].set_color(color))
        self.root_window.save_keybind(bulb, keys, color)
        config["Keybinds"][str(keys)] = str(bulb + ":" + str(color))

    def on_keybind_keys_click(self, event):
        self.update()
        self.update_idletasks()
        self.k = Keystroke_Watcher(self, sticky=True)
        try:
            self.keybind_keys_select.config(state='normal')
            self.update()
            self.update_idletasks()
            while self.focus_get() == self.keybind_keys_select:
                self.keybind_keys_select.delete(0, 'end')
                self.keybind_keys_select.insert(END, self.k.get_key_combo_code())
                self.update()
                self.update_idletasks()
        finally:
            try:  # Might try and change this if next press is OK button, which will throw an error
                self.keybind_keys_select.config(state='readonly')
            except TclError:
                pass
            self.k.shutdown()
