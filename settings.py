import configparser
import itertools
import logging
from shutil import copyfile
from tkinter import *
from tkinter import messagebox
from tkinter.colorchooser import *
import tkinter.ttk as ttk

from desktopmagic.screengrab_win32 import getDisplayRects
from lifxlan import *
from lifxlan.utils import RGBtoHSBK

from utils import resource_path
from keypress import Keystroke_Watcher

VERSION = '1.3.1'
AUTHOR = 'Sawyer McLane'
BUILD_DATE = '5/26/2018'

config = configparser.ConfigParser()
if not os.path.isfile("config.ini"):
    copyfile(resource_path("default.ini"), "config.ini")
config.read("config.ini")
if int(config["Info"]["Version"].replace('.', '')) < int(VERSION.replace('.', '')):  # check version number
    root = Tk()  # temp root window
    root.withdraw()
    messagebox.showerror("Old config detected", "Your old config file is old. Replacing with newer.")
    root.destroy()
    # reread new config (don't keep old data)
    copyfile(resource_path("default.ini"), "config.ini")
    config.clear()
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


class MultiListbox(Frame):
    """ https://www.safaribooksonline.com/library/view/python-cookbook/0596001673/ch09s05.html """

    def __init__(self, master, lists):
        Frame.__init__(self, master)
        self.lists = []
        for l, w in lists:
            frame = Frame(self);
            frame.pack(side=LEFT, expand=YES, fill=BOTH)
            Label(frame, text=l, borderwidth=1, relief=RAISED).pack(fill=X)
            lb = Listbox(frame, width=w, borderwidth=0, selectborderwidth=0,
                         relief=FLAT, exportselection=FALSE)
            lb.pack(expand=YES, fill=BOTH)
            self.lists.append(lb)
            lb.bind('<B1-Motion>', lambda e, s=self: s._select(e.y))
            lb.bind('<Button-1>', lambda e, s=self: s._select(e.y))
            lb.bind('<Leave>', lambda e: 'break')
            lb.bind('<B2-Motion>', lambda e, s=self: s._b2motion(e.x, e.y))
            lb.bind('<Button-2>', lambda e, s=self: s._button2(e.x, e.y))
        frame = Frame(self);
        frame.pack(side=LEFT, fill=Y)
        Label(frame, borderwidth=1, relief=RAISED).pack(fill=X)
        sb = Scrollbar(frame, orient=VERTICAL, command=self._scroll)
        sb.pack(expand=YES, fill=Y)
        self.lists[0]['yscrollcommand'] = sb.set

    def _select(self, y):
        row = self.lists[0].nearest(y)
        self.selection_clear(0, END)
        self.selection_set(row)
        return 'break'

    def _button2(self, x, y):
        for l in self.lists: l.scan_mark(x, y)
        return 'break'

    def _b2motion(self, x, y):
        for l in self.lists: l.scan_dragto(x, y)
        return 'break'

    def _scroll(self, *args):
        for l in self.lists:
            l.yview(*args)

    def curselection(self):
        return self.lists[0].curselection()

    def delete(self, first, last=None):
        for l in self.lists:
            l.delete(first, last)

    def get(self, first, last=None):
        result = []
        for l in self.lists:
            result.append(l.get(first, last))
        if last: return map(*([None] + result))
        return result

    def index(self, index):
        self.lists[0].index(index)

    def insert(self, index, *elements):
        for e in elements:
            i = 0
            for l in self.lists:
                l.insert(index, e[i])
                i = i + 1

    def size(self):
        return self.lists[0].size()

    def see(self, index):
        for l in self.lists:
            l.see(index)

    def selection_anchor(self, index):
        for l in self.lists:
            l.selection_anchor(index)

    def selection_clear(self, first, last=None):
        for l in self.lists:
            l.selection_clear(first, last)

    def selection_includes(self, index):
        return self.lists[0].selection_includes(index)

    def selection_set(self, first, last=None):
        for l in self.lists:
            l.selection_set(first, last)


class SettingsDisplay(Dialog):
    def body(self, master):
        self.root_window = master.master.master
        self.logger = logging.getLogger(self.root_window.logger.name + '.SettingsDisplay')
        self.k = Keystroke_Watcher(self, sticky=True)
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
        self.keybind_keys_select.bind('<FocusOut>', lambda *_: self.keybind_keys_select.config(state='readonly'))
        self.keybind_color_selection = StringVar(master, value="Color")
        self.keybind_color_dropdown = OptionMenu(master, self.keybind_color_selection,
                                                 *self.root_window.framesdict[
                                                     self.keybind_bulb_selection.get()].default_colors)
        self.keybind_add_button = Button(master, text="Add keybind",
                                         command=lambda *_: self.register_keybinding(
                                             self.keybind_bulb_selection.get(), self.keybind_keys_select.get(),
                                             self.keybind_color_selection.get()))
        self.keybind_delete_button = Button(master, text="Delete keybind", command=self.delete_keybind)

        # Insert
        self.avg_monitor_dropdown.grid(row=0, column=1)
        ttk.Separator(master, orient=HORIZONTAL).grid(row=0, sticky='esw', columnspan=100)
        self.preset_color_name.grid(row=1, column=1)
        self.preset_color_button.grid(row=1, column=2)
        ttk.Separator(master, orient=HORIZONTAL).grid(row=1, sticky='esw', columnspan=100)
        self.keybind_bulb_dropdown.grid(row=2, column=1)
        self.keybind_keys_select.grid(row=2, column=2)
        self.keybind_color_dropdown.grid(row=2, column=3)
        self.keybind_add_button.grid(row=2, column=4)
        self.mlb = MultiListbox(master, (('Bulb', 5), ('Keybind', 5), ('Color', 5)))
        for keypress, fnx in dict(config['Keybinds']).items():
            label, color = fnx.split(':')
            self.mlb.insert(END, (label, keypress, color))
        self.mlb.grid(row=3, columnspan=100, sticky='esw')
        self.keybind_delete_button.grid(row=4, column=0)

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
        self.root_window.save_keybind(bulb, keys, color)
        config["Keybinds"][str(keys)] = str(bulb + ":" + str(color))
        self.mlb.insert(END, (str(bulb), str(keys), str(color)))
        self.keybind_keys_select.config(state='normal')
        self.keybind_keys_select.delete(0, 'end')
        self.keybind_keys_select.config(state='readonly')

    def on_keybind_keys_click(self, event):
        """ Call when cursor is in key-combo entry """
        self.update()
        self.update_idletasks()
        self.k.restart()
        self.keybind_keys_select.config(state='normal')
        self.update()
        self.update_idletasks()
        while self.focus_get() == self.keybind_keys_select:
            self.keybind_keys_select.delete(0, 'end')
            self.keybind_keys_select.insert(END, self.k.get_key_combo_code())
            self.update()
            self.update_idletasks()

    def delete_keybind(self):
        _, keybind, _ = self.mlb.get(ACTIVE)
        self.mlb.delete(ACTIVE)
        self.root_window.delete_keybind(keybind)
        config.remove_option("Keybinds", keybind)
