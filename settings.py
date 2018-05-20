from tkinter import *
import configparser
import os
from shutil import copyfile
import itertools

from desktopmagic.screengrab_win32 import getDisplayRects
from helpers import resource_path

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
        # Labels
        Label(master, text="Avg. Monitor Default: ").grid(row=0, column=0)

        # Widgets
        self.avg_monitor = StringVar(self, value=config["AverageColor"]["DefaultMonitor"])
        options = []
        lst = getDisplayRects()
        for i in range(1, len(lst) + 1):
            els = [list(x) for x in itertools.combinations(lst, i)]
            options.extend(els)
        self.avg_monitor_dd = OptionMenu(master, self.avg_monitor, *lst, 'all')

        # Insert
        self.avg_monitor_dd.grid(row=0, column=1)

    def validate(self):
        self.avg_monitor = str(self.avg_monitor.get())
        config["AverageColor"]["DefaultMonitor"] = self.avg_monitor
        # Write to config file
        with open('config.ini', 'w') as cfg:
            config.write(cfg)

        return 1
