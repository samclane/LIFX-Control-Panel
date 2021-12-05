# -*- coding: utf-8 -*-
"""Main lifx_control_panel GUI control

This module contains several ugly God-classes that control the GUI functions and reactions.

Notes
-----
    This is the "main" function of the app, and can be run simply with 'python main.pyw'
"""
import logging
import os
import sys
import threading
import tkinter
import tkinter.colorchooser
import traceback
from collections import OrderedDict
from logging.handlers import RotatingFileHandler
from tkinter import messagebox, ttk
from typing import List, Dict, Union

import lifxlan
import pystray
if os.name == 'nt':
    import pystray._win32
from PIL import Image

from lifx_control_panel import HEARTBEAT_RATE_MS, FRAME_PERIOD_MS, LOGFILE
from lifx_control_panel._constants import BUILD_DATE, AUTHOR, DEBUGGING, VERSION
from lifx_control_panel.frames import LightFrame, MultiZoneFrame, GroupFrame
from lifx_control_panel.ui import settings
from lifx_control_panel.ui.icon_list import BulbIconList
from lifx_control_panel.ui.settings import config
from lifx_control_panel.ui.splashscreen import Splash
from lifx_control_panel.utilities import audio
from lifx_control_panel.utilities.async_bulb_interface import AsyncBulbInterface
from lifx_control_panel.utilities.keypress import KeybindManager
from lifx_control_panel.utilities.utils import (resource_path,
                                                Color,
                                                str2tuple)

# determine if application is a script file or frozen exe
APPLICATION_PATH = os.path.dirname(__file__)

LOGFILE = os.path.join(APPLICATION_PATH, LOGFILE)

SPLASHFILE = resource_path('res/splash_vector.png')


class LifxFrame(ttk.Frame):  # pylint: disable=too-many-ancestors
    """ Parent frame of application. Holds icons for each Device/Group. """
    bulb_interface: AsyncBulbInterface
    current_lightframe: LightFrame

    def __init__(self, master, lifx_instance: lifxlan.LifxLAN, bulb_interface: AsyncBulbInterface):
        # We take a lifx instance so we can inject our own for testing.

        # Start showing splash_screen while processing
        self.splashscreen = Splash(master, SPLASHFILE)
        self.splashscreen.__enter__()

        # Setup frame and grid
        ttk.Frame.__init__(self, master, padding="3 3 12 12")
        self.master = master
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.grid(column=0, row=0, sticky=(tkinter.N, tkinter.W, tkinter.E, tkinter.S))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.lifx: lifxlan.LifxLAN = lifx_instance
        self.bulb_interface = bulb_interface
        self.audio_interface = audio.AudioInterface()
        self.audio_interface.init_audio(config)

        # Setup logger
        self.logger = logging.getLogger(master.logger.name + '.' + self.__class__.__name__)
        self.logger.info('Root logger initialized: %s', self.logger.name)
        self.logger.info('Binary Version: %s', VERSION)
        self.logger.info('Build time: %s', BUILD_DATE)

        # Setup menu
        self.menubar = tkinter.Menu(master)
        filemenu = tkinter.Menu(self.menubar, tearoff=0)
        filemenu.add_command(label="Rescan", command=self.scan_for_lights)
        filemenu.add_command(label="Settings", command=self.show_settings)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.on_closing)
        self.menubar.add_cascade(label="File", menu=filemenu)
        self.menubar.add_command(label="About", command=self.show_about)
        self.master.config(menu=self.menubar)

        # Initialize LIFX objects
        self.lightvar = tkinter.StringVar(self)
        self.lightsdict: Dict[str, lifxlan.Light] = OrderedDict()  # LifxLight objects
        self.framesdict: Dict[str, LightFrame] = {}  # corresponding LightFrame GUI
        self.current_lightframe: LightFrame  # currently selected and visible LightFrame
        self.current_light: lifxlan.Light
        self.bulb_icons = BulbIconList(self)
        self.group_icons = BulbIconList(self, is_group=True)

        self.scan_for_lights()

        if any(self.lightsdict):
            self.lightvar.set(next(iter(self.lightsdict.keys())))
            self.current_light = self.lightsdict[self.lightvar.get()]
        else:
            messagebox.showwarning("No lights found.", "No LIFX devices were found on your LAN. Try using File->Rescan"
                                                       " to search again.")

        self.bulb_icons.grid(row=1, column=1, sticky='w')
        self.bulb_icons.canvas.bind('<Button-1>', self.on_bulb_canvas_click)
        self.lightvar.trace('w', self.bulb_changed)  # Keep lightvar in sync with drop-down selection

        self.group_icons.grid(row=2, column=1, sticky='w')
        self.group_icons.canvas.bind('<Button-1>', self.on_bulb_canvas_click)

        # Setup tray icon
        def lambda_quit(self_):
            """ Build an anonymous function call w/ correct 'self' scope"""
            return lambda *_, **__: self_.on_closing()

        def lambda_adjust(self_):
            return lambda *_, **__: self_.master.deiconify()

        def run_tray_icon():
            """ Allow SysTrayIcon in a separate thread """
            image = Image.open(resource_path('res/icon_vector.ico'))

            icon = pystray.Icon("LIFX Control Panel", image, menu=pystray.Menu(
                pystray.MenuItem('Open',
                                 lambda_adjust(self),
                                 default=True),
                pystray.MenuItem('Quit',
                                 lambda_quit(self)),
            ))
            icon.run()

        self.systray_thread = threading.Thread(target=run_tray_icon, daemon=True)
        self.systray_thread.start()
        self.master.bind('<Unmap>', lambda *_, **__: self.master.withdraw())  # Minimize to taskbar

        # Setup keybinding listener
        self.key_listener = KeybindManager(self)
        for keypress, function in dict(config['Keybinds']).items():
            light, color = function.split(':')
            color = Color(*globals()[color]) if color in globals().keys() else str2tuple(
                color, int)
            self.save_keybind(light, keypress, color)

        # Stop splashscreen and start main function
        self.splashscreen.__exit__(None, None, None)

        # Start icon callback
        self.after(FRAME_PERIOD_MS, self.update_icons)

        # Minimize if in config
        if config.getboolean("AppSettings", "start_minimized"):
            self.master.withdraw()

    def scan_for_lights(self):
        """ Communicating with the interface Thread, attempt to find any new devices """
        # Stop and restart the bulb interface
        stop_event: threading.Event = self.bulb_interface.stopped
        if not stop_event.isSet():
            stop_event.set()
        device_list: List[Union[lifxlan.Group, lifxlan.Light, lifxlan.MultiZoneLight]] = self.lifx.get_devices()
        if self.bulb_interface:
            del self.bulb_interface
        self.bulb_interface = AsyncBulbInterface(stop_event, HEARTBEAT_RATE_MS)
        self.bulb_interface.set_device_list(device_list)
        self.bulb_interface.daemon = True
        stop_event.clear()
        self.bulb_interface.start()

        light: lifxlan.Device
        for light in self.bulb_interface.device_list:
            try:
                product: str = lifxlan.product_map[light.get_product()]
                label: str = light.get_label()
                # light.get_color()
                self.lightsdict[label] = light
                self.logger.info('Light found: %s: "%s"', product, label)
                if label not in self.bulb_icons.bulb_dict.keys():
                    self.bulb_icons.draw_bulb_icon(light, label)
                if label not in self.framesdict.keys():
                    if light.supports_multizone():
                        self.framesdict[label] = MultiZoneFrame(self, light)
                    else:
                        self.framesdict[label] = LightFrame(self, light)
                    self.current_lightframe = self.framesdict[label]
                    try:
                        self.bulb_icons.set_selected_bulb(label)
                    except KeyError:
                        self.group_icons.set_selected_bulb(label)
                    self.logger.info("Building new frame: %s", self.framesdict[label].get_label())
                group_label = light.get_group_label()
                if group_label not in self.lightsdict.keys():
                    self.lightsdict[group_label]: lifxlan.Group = self.lifx.get_devices_by_group(group_label)
                    self.lightsdict[group_label].get_label = lambda: group_label  # pylint: disable=cell-var-from-loop
                    # Giving an attribute here is a bit dirty, but whatever
                    self.lightsdict[group_label].label = group_label
                    self.group_icons.draw_bulb_icon(None, group_label)
                    self.logger.info("Group found: %s", group_label)
                    self.framesdict[group_label] = GroupFrame(self, self.lightsdict[group_label])
                    self.logger.info("Building new frame: %s", self.framesdict[group_label].get_label())
            except lifxlan.WorkflowException as exc:
                self.logger.warning("Error when communicating with LIFX device: %s", exc)

    def bulb_changed(self, *_, **__):
        """ Change current display frame when bulb icon is clicked. """
        self.master.unbind('<Unmap>')  # unregister unmap so grid_remove doesn't trip it
        new_light_label = self.lightvar.get()
        self.current_light = self.lightsdict[new_light_label]
        # loop below removes all other frames; not just the current one (this fixes sync bugs for some reason)
        for frame in self.framesdict.values():
            frame.grid_remove()
        self.framesdict[new_light_label].grid()  # should bring to front
        self.logger.info(
            "Brought existing frame to front: %s", self.framesdict[new_light_label].get_label())
        self.current_lightframe = self.framesdict[new_light_label]
        self.current_lightframe.restart()
        if not self.current_lightframe.get_label() == self.lightvar.get():
            self.logger.error("Mismatch between LightFrame (%s) and Dropdown (%s)", self.current_lightframe.get_label(),
                              self.lightvar.get())
        self.master.bind('<Unmap>', lambda *_, **__: self.master.withdraw())  # reregister callback

    def on_bulb_canvas_click(self, event):
        """ Called whenever somebody clicks on one of the Device/Group icons. Switches LightFrame being shown. """
        canvas = event.widget
        # Convert to Canvas coords as we are using a Scrollbar, so Frame coords doesn't always match up.
        x_canv = canvas.canvasx(event.x)
        y_canv = canvas.canvasy(event.y)
        item = canvas.find_closest(x_canv, y_canv)
        lightname = canvas.gettags(item)[0]
        self.lightvar.set(lightname)
        if not canvas.master.is_group:  # BulbIconList
            self.bulb_icons.set_selected_bulb(lightname)
            if self.group_icons.current_icon:
                self.group_icons.clear_selected()
        else:
            self.group_icons.set_selected_bulb(lightname)
            if self.bulb_icons.current_icon:
                self.bulb_icons.clear_selected()

    def update_icons(self):
        """ If the window isn't minimized, redraw icons to reflect their current power/color state. """
        if self.master.winfo_viewable():
            for frame in self.framesdict.values():
                if not isinstance(frame, GroupFrame) and frame.icon_update_flag:
                    self.bulb_icons.update_icon(frame.target)
                    frame.icon_update_flag = False
        self.after(FRAME_PERIOD_MS, self.update_icons)

    def save_keybind(self, light, keypress, color):
        """ Builds a new anonymous function changing light to color when keypress is entered. """

        def lambda_factory(self, light, color):
            """ https://stackoverflow.com/questions/938429/scope-of-lambda-functions-and-their-parameters """
            return lambda *_, **__: self.lightsdict[light].set_color(color,
                                                                     duration=float(config["AverageColor"]["duration"]))

        func = lambda_factory(self, light, color)
        self.key_listener.register_function(keypress, func)

    def delete_keybind(self, keycombo):
        """ Deletes anyonymous function from key_listener. Don't know why this is needed. """
        self.key_listener.unregister_function(keycombo)

    def show_settings(self):
        """ Show the settings dialog box over the master window. """
        self.key_listener.shutdown()
        settings.SettingsDisplay(self, "Settings")
        self.current_lightframe.update_user_dropdown()
        self.audio_interface.init_audio(config)
        for frame in self.framesdict.values():
            frame.music_button.config(state='normal' if self.audio_interface.initialized else 'disabled')
        self.key_listener.restart()

    @staticmethod
    def show_about():
        """ Show the about info-box above the master window. """
        messagebox.showinfo("About", "lifx_control_panel\n"
                                     "Version {}\n"
                                     "{}, {}\n"
                                     "Bulb Icons by Quixote\n"
                                     "Please consider donating at ko-fi.com/sawyermclane"
                            .format(VERSION, AUTHOR, BUILD_DATE))

    def on_closing(self):
        """ Should always be called before the application exits. Shuts down all threads and closes the program. """
        self.logger.info('Shutting down.\n')
        self.master.destroy()
        self.bulb_interface.stopped.set()
        sys.exit(0)


def main():
    """ Start the GUI, bulb_interface, loggers, exception handling, and finally run the app """
    root = None
    try:
        root = tkinter.Tk()
        root.title("lifx_control_panel")
        root.resizable(False, False)

        # Setup main_icon
        root.iconbitmap(resource_path('res/icon_vector.ico'))

        root.logger = logging.getLogger('root')
        root.logger.setLevel(logging.DEBUG)
        file_handler = RotatingFileHandler(LOGFILE, maxBytes=5 * 1024 * 1024, backupCount=1)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        root.logger.addHandler(file_handler)
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.DEBUG)
        stream_handler.setFormatter(formatter)
        root.logger.addHandler(stream_handler)
        root.logger.info('Logger initialized.')

        def custom_handler(type_, value, trace_back):
            """ A custom exception handler that logs exceptions in the root window's logger. """
            root.logger.exception(
                "Uncaught exception: %s:%s:%s", repr(type_), str(value), repr(trace_back))

        sys.excepthook = custom_handler

        lifxlan.light_products.append(38)  # TODO Hotfix for missing LIFX Beam

        LifxFrame(root, lifxlan.LifxLAN(verbose=DEBUGGING), AsyncBulbInterface(threading.Event(), HEARTBEAT_RATE_MS))

        # Run main app
        root.mainloop()

    except Exception as exc:  # pylint: disable=broad-except
        if root and hasattr(root, "logger"):
            root.logger.exception(exc)
        else:
            logging.exception(exc)
        messagebox.showerror("Unhandled Exception", "Unhandled runtime exception: {}\n\n"
                                                    "Please report this at: {}".format(traceback.format_exc(),
                                                                                       r"https://github.com/samclane"
                                                                                       r"/lifx_control_panel/issues"))
        os._exit(1)  # pylint: disable=protected-access


if __name__ == "__main__":
    main()
