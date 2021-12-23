# -*- coding: utf-8 -*-
"""UI Logic and Interface Elements for Settings

This module contains several ugly God-classes that control the settings GUI functions and reactions.

Notes
-----
    Uses a really funky design pattern for a dialog that I copied from an old project. It's bad and I should probably
    ript it out
"""
import configparser
import logging
from tkinter import ttk
from tkinter import (
    Toplevel,
    Frame,
    Button,
    ACTIVE,
    LEFT,
    YES,
    Label,
    Listbox,
    FLAT,
    X,
    BOTH,
    RAISED,
    FALSE,
    VERTICAL,
    Y,
    Scrollbar,
    END,
    BooleanVar,
    Checkbutton,
    StringVar,
    OptionMenu,
    Scale,
    HORIZONTAL,
    Entry,
)
from tkinter.colorchooser import askcolor

import mss
from lifxlan.utils import RGBtoHSBK

from ..utilities.keypress import KeybindManager
from ..utilities.utils import resource_path, str2list

config = configparser.ConfigParser()  # pylint: disable=invalid-name
config.read([resource_path("default.ini"), "config.ini"])

# Compare datetimes
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"


# boilerplate code from http://effbot.org/tkinterbook/tkinter-dialog-windows.htm
class Dialog(Toplevel):
    """ Template for dialogs that include an Ok and Cancel button, and return validated user input data. """

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
        self.geometry("+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))
        self.initial_focus.focus_set()
        self.wait_window(self)

    # construction hooks
    def body(self, master):
        """create dialog body.  return widget that should have initial focus. This method should be overridden"""

    def buttonbox(self):
        """ add standard button box. override if you don't want the standard buttons """
        box = Frame(self)
        # pylint: disable=invalid-name
        ok = Button(box, text="OK", width=10, command=self.ok, default=ACTIVE)
        ok.pack(side=LEFT, padx=5, pady=5)
        cancel = Button(box, text="Cancel", width=10, command=self.cancel)
        cancel.pack(side=LEFT, padx=5, pady=5)

        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)

        box.pack()

    def ok(self, _=None):  # pylint: disable=invalid-name
        """ Standard ok semantics """
        if not self.validate():
            self.initial_focus.focus_set()  # put focus back
            return
        self.withdraw()
        self.update_idletasks()
        self.apply()
        self.cancel()

    def cancel(self, _=None):
        """put focus back to the parent window"""
        self.parent.focus_set()
        self.destroy()
        return 0

    # command hooks
    def validate(self):  # pylint: disable=no-self-use
        """ Override """
        return 1  # override

    def apply(self):
        """ Override """


class MultiListbox(Frame):  # pylint: disable=too-many-ancestors
    """ Shows information about items in a column-format
    https://www.safaribooksonline.com/library/view/python-cookbook/0596001673/ch09s05.html """

    def __init__(self, master, lists):
        Frame.__init__(self, master)
        self.lists = []
        for list_, widget in lists:
            frame = Frame(self)
            frame.pack(side=LEFT, expand=YES, fill=BOTH)
            Label(frame, text=list_, borderwidth=1, relief=RAISED).pack(fill=X)
            list_box = Listbox(
                frame,
                width=widget,
                borderwidth=0,
                selectborderwidth=0,
                relief=FLAT,
                exportselection=FALSE,
            )
            list_box.pack(expand=YES, fill=BOTH)
            self.lists.append(list_box)
            list_box.bind("<B1-Motion>", lambda e, s=self: s._select(e.y))
            list_box.bind("<Button-1>", lambda e, s=self: s._select(e.y))
            list_box.bind("<Leave>", lambda e: "break")
            list_box.bind("<B2-Motion>", lambda e, s=self: s._b2motion(e.x, e.y))
            list_box.bind("<Button-2>", lambda e, s=self: s._button2(e.x, e.y))
        frame = Frame(self)
        frame.pack(side=LEFT, fill=Y)
        Label(frame, borderwidth=1, relief=RAISED).pack(fill=X)
        scroll = Scrollbar(frame, orient=VERTICAL, command=self._scroll)
        scroll.pack(expand=YES, fill=Y)
        self.lists[0]["yscrollcommand"] = scroll.set

    def _select(self, y):  # pylint: disable=invalid-name
        """ Select a row when clicked """
        row = self.lists[0].nearest(y)
        self.selection_clear(0, END)
        self.selection_set(row)
        return "break"

    def _button2(self, x, y):  # pylint: disable=invalid-name
        for list_ in self.lists:
            list_.scan_mark(x, y)
        return "break"

    def _b2motion(self, x, y):  # pylint: disable=invalid-name
        for list_ in self.lists:
            list_.scan_dragto(x, y)
        return "break"

    def _scroll(self, *args):
        """ Move the list down """
        for list_ in self.lists:
            list_.yview(*args)

    def curselection(self):
        """ Return currently selected list item """
        return self.lists[0].curselection()

    def delete(self, first, last=None):
        """ Remove an item from the list and GUI """
        for list_ in self.lists:
            list_.delete(first, last)

    def get(self, first, last=None):
        """ Get specific item from the list """
        result = [list_.get(first, last) for list_ in self.lists]
        if last:
            return map(*([None] + result))
        return result

    def index(self, index):
        """ Get index of item at index"""
        self.lists[0].index(index)

    def insert(self, index, *elements):
        """ Insert element into list"""
        for elm in elements:
            for i, list_ in enumerate(self.lists):
                list_.insert(index, elm[i])

    def size(self):
        """ Size of internal list at call time """
        return self.lists[0].size()

    def see(self, index):
        """ Wrapper for see function that calls on each list """
        for list_ in self.lists:
            list_.see(index)

    def selection_anchor(self, index):
        for list_ in self.lists:
            list_.selection_anchor(index)

    def selection_clear(self, first, last=None):
        """ Clear selection highlight """
        for list_ in self.lists:
            list_.selection_clear(first, last)

    def selection_includes(self, index):
        """ Check if item at index is in user selection """
        return self.lists[0].selection_includes(index)

    def selection_set(self, first, last=None):
        """ Manually change the selection """
        for list_ in self.lists:
            list_.selection_set(first, last)


class SettingsDisplay(Dialog):
    """ Settings form User Interface"""

    def body(self, master):
        self.root_window = master.master.master  # This is really gross. I'm sorry.
        self.logger = logging.getLogger(
            self.root_window.logger.name + ".SettingsDisplay"
        )
        self.key_listener = KeybindManager(self, sticky=True)
        # Labels
        Label(master, text="Start Minimized?: ").grid(row=0, column=0)
        Label(master, text="Avg. Monitor Default: ").grid(row=1, column=0)
        Label(master, text="Smooth Transition Time (sec): ").grid(row=2, column=0)
        Label(master, text="Brightness Offset: ").grid(row=3, column=0)
        Label(master, text="Add Preset Color: ").grid(row=4, column=0)
        Label(master, text="Audio Input Source: ").grid(row=5, column=0)
        Label(master, text="Add keyboard shortcut").grid(row=6, column=0)

        # Widgets
        # Starting minimized
        self.start_mini = BooleanVar(
            master, value=config.getboolean("AppSettings", "start_minimized")
        )
        self.start_mini_check = Checkbutton(master, variable=self.start_mini)

        # Avg monitor color match
        self.avg_monitor = StringVar(
            master, value=config["AverageColor"]["DefaultMonitor"]
        )
        with mss.mss() as sct:
            options = [
                "full",
                "get_primary_monitor",
                *[tuple(m.values()) for m in sct.monitors],
            ]
        # lst = get_display_rects()
        # for i in range(1, len(lst) + 1):
        #    els = [list(x) for x in itertools.combinations(lst, i)]
        #    options.extend(els)
        self.avg_monitor_dropdown = OptionMenu(master, self.avg_monitor, *options)

        self.duration_scale = Scale(
            master, from_=0, to_=2, resolution=1 / 15, orient=HORIZONTAL
        )
        self.duration_scale.set(float(config["AverageColor"]["Duration"]))

        self.brightness_offset = Scale(
            master, from_=0, to_=65535, resolution=1, orient=HORIZONTAL
        )
        self.brightness_offset.set(int(config["AverageColor"]["brightnessoffset"]))

        # Custom preset color
        self.preset_color_name = Entry(master)
        self.preset_color_name.insert(END, "Enter color name...")
        self.preset_color_button = Button(
            master, text="Choose and add!", command=self.get_color
        )

        # Audio dropdown
        device_names = self.master.audio_interface.get_device_names()
        try:
            init_string = (
                " "
                + config["Audio"]["InputIndex"]
                + " "
                + device_names[int(config["Audio"]["InputIndex"])]
            )
        except ValueError:
            init_string = " None"
        self.audio_source = StringVar(
            master, init_string
        )  # AudioSource index is grabbed from [1], so add a space at [0]
        as_choices = device_names.items()
        self.as_dropdown = OptionMenu(master, self.audio_source, *as_choices)

        # Add keybindings
        light_names = list(self.root_window.device_map.keys())
        self.keybind_bulb_selection = StringVar(master, value=light_names[0])
        self.keybind_bulb_dropdown = OptionMenu(
            master, self.keybind_bulb_selection, *light_names
        )
        self.keybind_keys_select = Entry(master)
        self.keybind_keys_select.insert(END, "Add key-combo...")
        self.keybind_keys_select.config(state="readonly")
        self.keybind_keys_select.bind("<FocusIn>", self.on_keybind_keys_click)
        self.keybind_keys_select.bind(
            "<FocusOut>", lambda *_: self.keybind_keys_select.config(state="readonly")
        )
        self.keybind_color_selection = StringVar(master, value="Color")
        self.keybind_color_dropdown = OptionMenu(
            master,
            self.keybind_color_selection,
            *self.root_window.frame_map[
                self.keybind_bulb_selection.get()
            ].default_colors,
            *(
                [*config["PresetColors"].keys()]
                if any(config["PresetColors"].keys())
                else [None]
            )
        )
        self.keybind_add_button = Button(
            master,
            text="Add keybind",
            command=lambda *_: self.register_keybinding(
                self.keybind_bulb_selection.get(),
                self.keybind_keys_select.get(),
                self.keybind_color_selection.get(),
            ),
        )
        self.keybind_delete_button = Button(
            master, text="Delete keybind", command=self.delete_keybind
        )

        # Insert
        self.start_mini_check.grid(row=0, column=1)
        ttk.Separator(master, orient=HORIZONTAL).grid(
            row=0, sticky="esw", columnspan=100
        )
        self.avg_monitor_dropdown.grid(row=1, column=1)
        self.duration_scale.grid(row=2, column=1)
        self.brightness_offset.grid(row=3, column=1)
        ttk.Separator(master, orient=HORIZONTAL).grid(
            row=3, sticky="esw", columnspan=100
        )
        self.preset_color_name.grid(row=4, column=1)
        self.preset_color_button.grid(row=4, column=2)
        ttk.Separator(master, orient=HORIZONTAL).grid(
            row=4, sticky="esw", columnspan=100
        )
        self.as_dropdown.grid(row=5, column=1)
        ttk.Separator(master, orient=HORIZONTAL).grid(
            row=5, sticky="esw", columnspan=100
        )
        self.keybind_bulb_dropdown.grid(row=6, column=1)
        self.keybind_keys_select.grid(row=6, column=2)
        self.keybind_color_dropdown.grid(row=6, column=3)
        self.keybind_add_button.grid(row=6, column=4)
        self.mlb = MultiListbox(master, (("Bulb", 5), ("Keybind", 5), ("Color", 5)))
        for keypress, fnx in dict(config["Keybinds"]).items():
            label, color = fnx.split(":")
            self.mlb.insert(END, (label, keypress, color))
        self.mlb.grid(row=7, columnspan=100, sticky="esw")
        self.keybind_delete_button.grid(row=8, column=0)

    def validate(self) -> int:
        config["AppSettings"]["start_minimized"] = str(self.start_mini.get())
        config["AverageColor"]["DefaultMonitor"] = str(self.avg_monitor.get())
        config["AverageColor"]["Duration"] = str(self.duration_scale.get())
        config["AverageColor"]["BrightnessOffset"] = str(self.brightness_offset.get())
        config["Audio"]["InputIndex"] = str(self.audio_source.get()[1])
        # Write to config file
        with open("config.ini", "w", encoding="utf-8") as cfg:
            config.write(cfg)

        self.key_listener.shutdown()

        return 1

    def get_color(self):
        """ Present user with color palette dialog and return color in HSBK """
        color = askcolor()[0]
        if color:
            # RGBtoHBSK sometimes returns >65535, so we have to clamp
            hsbk = [min(c, 65535) for c in RGBtoHSBK(color)]
            config["PresetColors"][self.preset_color_name.get()] = str(hsbk)

    def register_keybinding(self, bulb: str, keys: str, color: str):
        """ Get the keybind from the input box and pass the color off to the root window. """
        try:
            color = self.root_window.frame_map[
                self.keybind_bulb_selection.get()
            ].default_colors[color]
        except KeyError:  # must be using a custom color
            color = str2list(config["PresetColors"][color], int)
        self.root_window.save_keybind(bulb, keys, color)
        config["Keybinds"][str(keys)] = str(bulb + ":" + str(color))
        self.mlb.insert(END, (str(bulb), str(keys), str(color)))
        self.keybind_keys_select.config(state="normal")
        self.keybind_keys_select.delete(0, "end")
        self.keybind_keys_select.insert(END, "Add key-combo...")
        self.keybind_keys_select.config(state="readonly")
        self.preset_color_name.focus_set()  # Set focus to a dummy widget to reset the Entry

    def on_keybind_keys_click(self, event):
        """ Call when cursor is in key-combo entry """
        self.update()
        self.update_idletasks()
        self.key_listener.restart()
        self.keybind_keys_select.config(state="normal")
        self.update()
        self.update_idletasks()
        while self.focus_get() == self.keybind_keys_select:
            self.keybind_keys_select.delete(0, "end")
            self.keybind_keys_select.insert(END, self.key_listener.key_combo_code)
            self.update()
            self.update_idletasks()

    def delete_keybind(self):
        """ Delete keybind currently selected in the multi-list box. """
        _, keybind, _ = self.mlb.get(ACTIVE)
        self.mlb.delete(ACTIVE)
        self.root_window.delete_keybind(keybind)
        config.remove_option("Keybinds", keybind)
