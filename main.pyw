# -*- coding: utf-8 -*-
"""Main LIFX-Control-Panel GUI control

This module contains several ugly God-classes that control the GUI functions and reactions.

Notes
-----
    This is the "main" function of the app, and can be run simply with 'python main.pyw'
"""
import concurrent.futures
import logging
import os
import queue
import sys
import threading
import tkinter
import tkinter.colorchooser
import tkinter.font as font
import traceback
import win32api
from collections import OrderedDict
from tkinter import _setit, messagebox, ttk
from win32gui import GetCursorPos

import lifxlan
from PIL import Image as pImage
from lifxlan import (ORANGE,
                     YELLOW,
                     GREEN,
                     CYAN,
                     BLUE,
                     PURPLE,
                     PINK,
                     WHITE,
                     COLD_WHITE,
                     WARM_WHITE,
                     GOLD)

import utilities.utils
from _constants import BUILD_DATE, AUTHOR, DEBUGGING, VERSION
from ui import SysTrayIcon, settings
from ui.colorscale import ColorScale
from ui.settings import config
from ui.splashscreen import Splash
from utilities import audio, color_thread
from utilities.keypress import KeybindManager
from desktopmagic.screengrab_win32 import getScreenAsImage, normalizeRects

RED = [0, 65535, 65535, 3500]  # Fixes RED from appearing BLACK

audio.init(config)

HEARTBEAT_RATE_MS = 3000  # 3 seconds
FRAME_PERIOD_MS = 1500  # 1.5 seconds
LOGFILE = 'lifx-control-panel.log'

# determine if application is a script file or frozen exe
if getattr(sys, 'frozen', False):
    APPLICATION_PATH = os.path.dirname(sys.executable)
elif __file__:
    APPLICATION_PATH = os.path.dirname(__file__)
else:
    raise Exception("Application path not set. This should never happen.")

LOGFILE = os.path.join(APPLICATION_PATH, LOGFILE)

SPLASHFILE = utilities.utils.resource_path('res//splash_vector_png.png')


class AsyncBulbInterface(threading.Thread):
    """ Asynchronous networking layer between LIFX devices and the GUI. """

    def __init__(self, event):
        threading.Thread.__init__(self)
        self.stopped = event
        self.device_list = []
        self.color_queue = {}
        self.color_cache = {}
        self.power_queue = {}
        self.power_cache = {}

    def set_device_list(self, device_list):
        """ Set internet device list to passed list of LIFX devices. """
        self.device_list = device_list
        for dev in device_list:
            self.color_queue[dev.get_label()] = queue.Queue()
            self.color_cache[dev.label] = dev.color
            self.power_queue[dev.label] = queue.Queue()
            self.power_cache[dev.label] = dev.power_level

    def query_device(self, target):
        """ Check if target has new state. If it does, push it to the queue and cache the value. """
        try:
            pwr = target.get_power()
            if pwr != self.power_cache[target.label]:
                self.power_queue[target.label].put(pwr)
                self.power_cache[target.label] = pwr
            clr = target.get_color()
            if clr != self.color_cache[target.label]:
                self.color_queue[target.label].put(clr)
                self.color_cache[target.label] = clr
        except lifxlan.WorkflowException:
            pass

    def run(self):
        """ Continuous loop that has a thread query each device every HEARTBEAT ms. """
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.device_list)) as executor:
            while not self.stopped.wait(HEARTBEAT_RATE_MS / 1000):
                executor.map(self.query_device, self.device_list)


class LifxFrame(ttk.Frame):  # pylint: disable=too-many-ancestors
    """ Parent frame of application. Holds icons for each Device/Group. """

    def __init__(self, master, lifx_instance, bulb_interface):
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
        self.lifx = lifx_instance
        self.bulb_interface = bulb_interface

        # Setup logger
        self.logger = logging.getLogger(master.logger.name + '.' + self.__class__.__name__)
        self.logger.info('Root logger initialized: %s', self.logger.name)
        self.logger.info('Binary Version: %s', VERSION)
        self.logger.info('Config Version: %s', config["Info"]["Version"])
        self.logger.info('Build time: %s', config["Info"]["BuildDate"])

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
        self.lightsdict = OrderedDict()  # LifxLight objects
        self.framesdict = {}  # corresponding LightFrame GUI
        self.current_lightframe = None  # currently selected and visible LightFrame
        self.current_light = None
        self.bulb_icons = BulbIconList(self)
        self.group_icons = BulbIconList(self, is_group=True)

        self.scan_for_lights()

        if any(self.lightsdict):
            self.lightvar.set(next(iter(self.lightsdict.keys())))
            self.current_light = self.lightsdict[self.lightvar.get()]
        else:
            messagebox.showerror("No lights found.", "No LIFX devices were found on your LAN. Exiting.")
            self.on_closing()

        self.bulb_icons.grid(row=1, column=1, sticky='w')
        self.bulb_icons.canvas.bind('<Button-1>', self.on_bulb_canvas_click)
        self.lightvar.trace('w', self.bulb_changed)  # Keep lightvar in sync with drop-down selection

        self.group_icons.grid(row=2, column=1, sticky='w')
        self.group_icons.canvas.bind('<Button-1>', self.on_bulb_canvas_click)

        # Setup tray icon
        tray_options = (('Adjust Lights', None, lambda *_, **__: self.master.deiconify()),)

        def lambda_factory(self_):
            """ Build an anonymous function call w/ correct 'self' scope"""
            return lambda *_, **__: self_.on_closing()

        def run_tray_icon():
            """ Allow SysTrayIcon in a separate thread """
            SysTrayIcon.SysTrayIcon(utilities.utils.resource_path('res/icon_vector_9fv_icon.ico'), "LIFX-Control-Panel",
                                    tray_options,
                                    on_quit=lambda_factory(self))

        self.systray_thread = threading.Thread(target=run_tray_icon, daemon=True)
        self.systray_thread.start()
        self.master.bind('<Unmap>', lambda *_, **__: self.master.withdraw())  # Minimize to taskbar

        # Setup keybinding listener
        self.key_listener = KeybindManager(self)
        for keypress, function in dict(config['Keybinds']).items():
            light, color = function.split(':')
            color = utilities.utils.Color(*globals()[color]) if color in globals().keys() else utilities.utils.str2list(
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
        stop_event = self.bulb_interface.stopped
        if not stop_event.isSet():
            stop_event.set()
        device_list = self.lifx.get_lights()
        if self.bulb_interface:
            del self.bulb_interface
        self.bulb_interface = AsyncBulbInterface(stop_event)
        self.bulb_interface.set_device_list(device_list)
        self.bulb_interface.daemon = True
        stop_event.clear()
        self.bulb_interface.start()

        for light in device_list:
            try:
                product = lifxlan.product_map[light.get_product()]
                label = light.get_label()
                light.get_color()
                self.lightsdict[label] = light
                self.logger.info('Light found: %s: "%s"', product, label)
                if label not in self.bulb_icons.bulb_dict.keys():
                    self.bulb_icons.draw_bulb_icon(light, label)
                if label not in self.framesdict.keys():
                    self.framesdict[label] = LightFrame(self, light)
                    self.current_lightframe = self.framesdict[label]
                    try:
                        self.bulb_icons.set_selected_bulb(label)
                    except KeyError:
                        self.group_icons.set_selected_bulb(label)
                    self.logger.info("Building new frame: %s", self.framesdict[label].get_label())
                group_label = light.get_group_label()
                if group_label not in self.lightsdict.keys():
                    self.lightsdict[group_label] = self.lifx.get_devices_by_group(group_label)
                    self.lightsdict[group_label].get_label = lambda: group_label  # pylint: disable=cell-var-from-loop
                    # Giving an attribute here is a bit dirty, but whatever
                    self.lightsdict[group_label].label = group_label
                    self.group_icons.draw_bulb_icon(None, group_label)
                    self.logger.info("Group found: %s", group_label)
                    self.framesdict[group_label] = LightFrame(self, self.lightsdict[group_label])
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
        if not canvas.master.is_group:  # Lightframes
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
                if not frame.is_group and frame.icon_update_flag:
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
        audio.init(config)
        for frame in self.framesdict.values():
            frame.music_button.config(state='normal' if audio.initialized else 'disabled')
        self.key_listener.restart()

    @staticmethod
    def show_about():
        """ Show the about info-box above the master window. """
        messagebox.showinfo("About", "LIFX-Control-Panel\n"
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


class LightFrame(ttk.Labelframe):  # pylint: disable=too-many-ancestors
    """ Holds control and state information about a single device. """

    def __init__(self, master, target):
        self.is_group = isinstance(target, lifxlan.Group)
        self.icon_update_flag = True
        # Initialize frame
        try:
            if self.is_group:
                devices = target.get_device_list()
                self.label = devices[0].get_group_label()
                bulb_power = devices[0].get_power()
                init_color = utilities.utils.Color(*devices[0].get_color())
            else:  # is bulb
                self.label = target.get_label()
                bulb_power = target.get_power()
                init_color = utilities.utils.Color(*target.get_color())
        except lifxlan.WorkflowException as exc:
            messagebox.showerror("Error building LightFrame",
                                 "Error thrown when trying to get label from bulb:\n{}".format(exc))
            self.master.on_closing()
        ttk.Labelframe.__init__(self, master, padding="3 3 12 12",
                                labelwidget=tkinter.Label(master, text=self.label, font=font.Font(size=12),
                                                          fg="#0046d5",
                                                          relief=tkinter.RIDGE))
        self.grid(column=1, row=0, sticky=(tkinter.N, tkinter.W, tkinter.E, tkinter.S))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.target = target

        # Setup logger
        self.logger = logging.getLogger(
            self.master.logger.name + '.' + self.__class__.__name__ + '({})'.format(self.label))
        self.logger.setLevel(logging.DEBUG)
        self.logger.info(
            'LightFrame logger initialized: %s // Device: %s', self.logger.name, self.label)

        # Initialize vars to hold on/off state
        self.powervar = tkinter.BooleanVar(self)
        self.powervar.set(bulb_power)
        self.option_on = tkinter.Radiobutton(self, text="On", variable=self.powervar, value=65535,
                                             command=self.update_power)
        self.option_off = tkinter.Radiobutton(self, text="Off", variable=self.powervar, value=0,
                                              command=self.update_power)
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
        self.logger.info('Initial light color HSBK: %s', init_color)
        self.current_color = tkinter.Canvas(self,
                                            background=utilities.utils.tuple2hex(utilities.utils.HSBKtoRGB(init_color)),
                                            width=40, height=20,
                                            borderwidth=3,
                                            relief=tkinter.GROOVE)
        self.current_color.grid(row=0, column=2)
        self.hsbk = (tkinter.IntVar(self, init_color.hue, "Hue"),
                     tkinter.IntVar(self, init_color.saturation, "Saturation"),
                     tkinter.IntVar(self, init_color.brightness, "Brightness"),
                     tkinter.IntVar(self, init_color.kelvin, "Kelvin"))
        for i in self.hsbk:
            i.trace('w', self.trigger_icon_update)
        self.hsbk_labels = (
            tkinter.Label(self, text='%.3g' % (360 * (self.hsbk[0].get() / 65535))),
            tkinter.Label(self, text=str('%.3g' % (100 * self.hsbk[1].get() / 65535)) + "%"),
            tkinter.Label(self, text=str('%.3g' % (100 * self.hsbk[2].get() / 65535)) + "%"),
            tkinter.Label(self, text=str(self.hsbk[3].get()) + " K")
        )
        self.hsbk_scale = (
            ColorScale(self, to=65535., variable=self.hsbk[0], command=self.update_color_from_ui),
            ColorScale(self, from_=0, to=65535, variable=self.hsbk[1], command=self.update_color_from_ui,
                       gradient='wb'),
            ColorScale(self, from_=0, to=65535, variable=self.hsbk[2], command=self.update_color_from_ui,
                       gradient='bw'),
            ColorScale(self, from_=2500, to=9000, variable=self.hsbk[3], command=self.update_color_from_ui,
                       gradient='kelvin'))
        relief = tkinter.GROOVE
        self.hsbk_display = (
            tkinter.Canvas(self, background=utilities.utils.tuple2hex(
                utilities.utils.hueToRGB(360 * (init_color.hue / 65535))), width=20, height=20,
                           borderwidth=3,
                           relief=relief),
            tkinter.Canvas(self, background=utilities.utils.tuple2hex((
                int(255 * (init_color.saturation / 65535)), int(255 * (init_color.saturation / 65535)),
                int(255 * (init_color.saturation / 65535)))),
                           width=20, height=20, borderwidth=3, relief=relief),
            tkinter.Canvas(self, background=utilities.utils.tuple2hex((
                int(255 * (init_color.brightness / 65535)), int(255 * (init_color.brightness / 65535)),
                int(255 * (init_color.brightness / 65535)))),
                           width=20, height=20, borderwidth=3, relief=relief),
            tkinter.Canvas(self, background=utilities.utils.tuple2hex(utilities.utils.kelvinToRGB(init_color.kelvin)),
                           width=20, height=20,
                           borderwidth=3, relief=relief)
        )
        for key, scale in enumerate(self.hsbk_scale):
            tkinter.Label(self, text=self.hsbk[key]).grid(row=key + 1, column=0)
            scale.grid(row=key + 1, column=1)
            self.hsbk_labels[key].grid(row=key + 1, column=2)
            self.hsbk_display[key].grid(row=key + 1, column=3)

        self.threads = {}

        # Add buttons for pre-made colors
        self.preset_colors_lf = ttk.LabelFrame(self, text="Preset Colors", padding="3 3 12 12")
        self.color_var = tkinter.StringVar(self, value="Presets")

        self.default_colors = {"RED": RED,
                               "ORANGE": ORANGE,
                               "YELLOW": YELLOW,
                               "GREEN": GREEN,
                               "CYAN": CYAN,
                               "BLUE": BLUE,
                               "PURPLE": PURPLE,
                               "PINK": PINK,
                               "WHITE": WHITE,
                               "COLD_WHITE": COLD_WHITE,
                               "WARM_WHITE": WARM_WHITE,
                               "GOLD": GOLD}

        self.preset_dropdown = tkinter.OptionMenu(self.preset_colors_lf, self.color_var, *self.default_colors)
        self.preset_dropdown.grid(row=0, column=0)
        self.preset_dropdown.configure(width=13)
        self.color_var.trace('w', self.change_preset_dropdown)

        self.uservar = tkinter.StringVar(self, value="User Presets")
        self.user_dropdown = tkinter.OptionMenu(self.preset_colors_lf, self.uservar, *(
            [*config["PresetColors"].keys()] if any(config["PresetColors"].keys()) else [None]))
        self.user_dropdown.grid(row=0, column=1)
        self.user_dropdown.config(width=13)
        self.uservar.trace('w', self.change_user_dropdown)

        self.preset_colors_lf.grid(row=5, columnspan=4)

        # Add buttons for special routines
        self.special_functions_lf = ttk.LabelFrame(self, text="Special Functions", padding="3 3 12 12")
        self.threads['screen'] = color_thread.ColorThreadRunner(self.target, color_thread.avg_screen_color, self,
                                                                func_bounds=self.get_monitor_bounds)

        def start_screen_avg():
            """ Allow the screen avg. to be run in a separate thread. Also turns button green while running. """
            self.avg_screen_btn.config(bg="Green")
            self.threads['screen'].start()

        self.avg_screen_btn = tkinter.Button(self.special_functions_lf, text="Avg. Screen Color",
                                             command=start_screen_avg)
        self.avg_screen_btn.grid(row=6, column=0)
        tkinter.Button(self.special_functions_lf, text="Pick Color", command=self.get_color_from_palette).grid(row=6,
                                                                                                               column=1)
        self.threads['audio'] = color_thread.ColorThreadRunner(self.target, audio.get_music_color, self)

        def start_audio():
            """ Allow the audio to be run in a separate thread. Also turns button green while running. """
            self.music_button.config(bg="Green")
            self.threads['audio'].start()

        self.music_button = tkinter.Button(self.special_functions_lf, text="Music Color", command=start_audio,
                                           state='normal' if audio.initialized else 'disabled')
        self.music_button.grid(row=7, column=0)
        self.threads['eyedropper'] = color_thread.ColorThreadRunner(self.target, self.eyedropper, self,
                                                                    continuous=False)
        tkinter.Button(self.special_functions_lf, text="Color Eyedropper", command=self.threads['eyedropper'].start) \
            .grid(row=7, column=1)
        tkinter.Button(self.special_functions_lf, text="Stop effects", command=self.stop_threads).grid(row=8, column=0)
        self.special_functions_lf.grid(row=6, columnspan=4)

        # Add custom screen region (real ugly)
        self.screen_region_lf = ttk.LabelFrame(self, text="Screen Avg. Region", padding="3 3 12 12")

        self.screen_region_entries = {
            'x1': tkinter.Entry(self.screen_region_lf, width=6),
            'x2': tkinter.Entry(self.screen_region_lf, width=6),
            'y1': tkinter.Entry(self.screen_region_lf, width=6),
            'y2': tkinter.Entry(self.screen_region_lf, width=6)
        }
        region = config['AverageColor'][self.label if self.label in config["AverageColor"].keys() else 'defaultmonitor']
        if region == "full":
            region = ["full"] * 4
        elif region[:19] == "get_primary_monitor":
            region = utilities.utils.get_primary_monitor()
        else:
            region = utilities.utils.str2list(region, int)
        self.screen_region_entries['x1'].insert(tkinter.END, region[0])
        self.screen_region_entries['y1'].insert(tkinter.END, region[1])
        self.screen_region_entries['x2'].insert(tkinter.END, region[2])
        self.screen_region_entries['y2'].insert(tkinter.END, region[3])
        tkinter.Label(self.screen_region_lf, text="x1").grid(row=7, column=0, sticky='e')
        self.screen_region_entries['x1'].grid(row=7, column=1, padx=(0, 10))
        tkinter.Label(self.screen_region_lf, text="x2").grid(row=7, column=2)
        self.screen_region_entries['x2'].grid(row=7, column=3)
        tkinter.Label(self.screen_region_lf, text="y1").grid(row=8, column=0, sticky='e')
        self.screen_region_entries['y1'].grid(row=8, column=1, padx=(0, 10))
        tkinter.Label(self.screen_region_lf, text="y2").grid(row=8, column=2)
        self.screen_region_entries['y2'].grid(row=8, column=3)
        self.save_region = tkinter.Button(self.screen_region_lf, text="Save", command=self.save_monitor_bounds) \
            .grid(row=9, column=1, sticky='w')
        self.screen_region_lf.grid(row=7, columnspan=4)

        # Start update loop
        self.update_status_from_bulb()

    def restart(self):
        """ Get updated information for the bulb when clicked. """
        self.update_status_from_bulb()
        self.logger.info("Light frame Restarted.")

    def get_label(self):
        """ Getter method for the label attribute. Often is monkey-patched. """
        return self.label

    def trigger_icon_update(self, *_, **__):
        """ Just sets a flag for now. Could be more advanced in the future. """
        self.icon_update_flag = True

    def get_color_values_hsbk(self):
        """ Get color values entered into GUI"""
        return utilities.utils.Color(*tuple(v.get() for v in self.hsbk))

    def stop_threads(self):
        """ Stop all ColorRunner threads """
        self.music_button.config(bg="SystemButtonFace")
        self.avg_screen_btn.config(bg="SystemButtonFace")
        for thread in self.threads.values():
            thread.stop()

    def update_power(self):
        """ Send new power state to bulb when UI is changed. """
        self.stop_threads()
        self.target.set_power(self.powervar.get())

    def update_color_from_ui(self, *_, **__):
        """ Send new color state to bulb when UI is changed. """
        self.stop_threads()
        self.set_color(self.get_color_values_hsbk(), rapid=True)

    def set_color(self, color, rapid=False):
        """ Should be called whenever the bulb wants to change color. Sends bulb command and updates UI accordingly. """
        self.stop_threads()
        try:
            self.target.set_color(color, duration=0 if rapid else float(config["AverageColor"]["duration"]) * 1000,
                                  rapid=rapid)
        except lifxlan.WorkflowException as exc:
            if rapid:  # If we're going fast we don't care if we miss a packet.
                pass
            else:
                raise exc
        if not rapid:
            self.logger.debug('Color changed to HSBK: %s', color)  # Don't pollute log with rapid color changes

    def update_label(self, key):
        """ Update scale labels, formatted accordingly. """
        if key == 0:  # H
            self.hsbk_labels[0].config(text=str('%.3g' % (360 * (self.hsbk[0].get() / 65535))))
        elif key == 1:  # tkinter.S
            self.hsbk_labels[1].config(text=str('%.3g' % (100 * (self.hsbk[1].get() / 65535))) + "%")
        elif key == 2:  # B
            self.hsbk_labels[2].config(text=str('%.3g' % (100 * (self.hsbk[2].get() / 65535))) + "%")
        elif key == 3:  # K
            self.hsbk_labels[3].config(text=str(self.hsbk[3].get()) + " K")

    def update_display(self, key):
        """ Update color swatches to match current device state """
        h, s, b, k = self.get_color_values_hsbk()  # pylint: disable=invalid-name
        if key == 0:
            self.hsbk_display[0].config(
                background=utilities.utils.tuple2hex(utilities.utils.hueToRGB(360 * (h / 65535))))
        elif key == 1:
            s = 65535 - s  # pylint: disable=invalid-name
            self.hsbk_display[1].config(
                background=utilities.utils.tuple2hex(
                    (int(255 * (s / 65535)), int(255 * (s / 65535)), int(255 * (s / 65535)))))
        elif key == 2:
            self.hsbk_display[2].config(
                background=utilities.utils.tuple2hex(
                    (int(255 * (b / 65535)), int(255 * (b / 65535)), int(255 * (b / 65535)))))
        elif key == 3:
            self.hsbk_display[3].config(background=utilities.utils.tuple2hex(utilities.utils.kelvinToRGB(k)))

    def get_color_from_palette(self):
        """ Asks users for color selection using standard color palette dialog. """
        color = tkinter.colorchooser.askcolor(initialcolor=utilities.utils.HSBKtoRGB(self.get_color_values_hsbk()))[0]
        if color:
            # RGBtoHBSK sometimes returns >65535, so we have to truncate
            hsbk = [min(c, 65535) for c in lifxlan.RGBtoHSBK(color, self.hsbk[3].get())]
            self.set_color(hsbk)
            self.logger.info("Color set to HSBK %s from palette.", hsbk)

    def update_status_from_bulb(self, run_once=False):
        """
        Periodically update status from the bulb to keep UI in sync.
        :param run_once: Don't call `after` statement at end. Keeps a million workers from being instanced.
        """
        if self.is_group:
            return
        require_icon_update = False
        if not self.master.bulb_interface.power_queue[self.label].empty():
            power = self.master.bulb_interface.power_queue[self.label].get()
            require_icon_update = True
            self.powervar.set(power)
            if self.powervar.get() == 0:
                # Light is off
                self.option_off.select()
                self.option_on.selection_clear()
            else:
                self.option_on.select()
                self.option_off.selection_clear()

        if not self.master.bulb_interface.color_queue[self.label].empty():
            hsbk = self.master.bulb_interface.color_queue[self.label].get()
            require_icon_update = True
            for key, _ in enumerate(self.hsbk):
                self.hsbk[key].set(hsbk[key])
                self.update_label(key)
                self.update_display(key)
            self.current_color.config(background=utilities.utils.tuple2hex(utilities.utils.HSBKtoRGB(hsbk)))

        if require_icon_update:
            self.trigger_icon_update()
        if not run_once:
            self.after(FRAME_PERIOD_MS, self.update_status_from_bulb)

    def eyedropper(self, *_, **__):
        """ Allows user to select a color pixel from the screen. """
        self.master.master.withdraw()  # Hide window
        state_left = win32api.GetKeyState(0x01)  # Left button down = 0 or 1. tkinter.Button up = -127 or -128
        while True:
            action = win32api.GetKeyState(0x01)
            if action != state_left:  # tkinter.Button state changed
                state_left = action
                if action < 0:  # tkinter.Button down
                    pass
                else:  # tkinter.Button up
                    break
            lifxlan.sleep(0.001)
        # tkinter.Button state changed
        screen_img = getScreenAsImage()
        cursor_pos = GetCursorPos()
        # Convert display coords to image coords
        cursor_pos = normalizeRects(utilities.utils.getDisplayRects() +
                                    [(cursor_pos[0], cursor_pos[1], 0, 0)])[-1][:2]
        color = screen_img.getpixel(cursor_pos)
        self.master.master.deiconify()  # Reshow window
        self.logger.info("Eyedropper color found RGB %s", color)
        return lifxlan.RGBtoHSBK(color, temperature=self.get_color_values_hsbk().kelvin)

    def change_preset_dropdown(self, *_, **__):
        """ Change device color to selected preset option. """
        color = utilities.utils.Color(*globals()[self.color_var.get()])
        self.preset_dropdown.config(bg=utilities.utils.tuple2hex(utilities.utils.HSBKtoRGB(color)),
                                    activebackground=utilities.utils.tuple2hex(utilities.utils.HSBKtoRGB(color)))
        self.set_color(color, False)

    def change_user_dropdown(self, *_, **__):
        """ Change device color to selected user-defined option. """
        color = utilities.utils.str2list(config["PresetColors"][self.uservar.get()], int)
        self.user_dropdown.config(bg=utilities.utils.tuple2hex(utilities.utils.HSBKtoRGB(color)),
                                  activebackground=utilities.utils.tuple2hex(utilities.utils.HSBKtoRGB(color)))
        self.set_color(color, rapid=False)

    def update_user_dropdown(self):
        """ Add newly defined color to the user color dropdown menu. """
        # self.uservar.set('')
        self.user_dropdown["menu"].delete(0, 'end')

        new_choices = [key for key in config['PresetColors']]
        for choice in new_choices:
            self.user_dropdown["menu"].add_command(label=choice, command=_setit(self.uservar, choice))

    def get_monitor_bounds(self):
        """ Return the 4 rectangle coordinates from the entry boxes in the UI """
        return f"[{self.screen_region_entries['x1'].get()}, {self.screen_region_entries['y1'].get()}, " \
            f"{self.screen_region_entries['x2'].get()}, {self.screen_region_entries['y2'].get()}]"

    def save_monitor_bounds(self):
        """ Write monitor bounds entered in the UI into the config file. """
        config["AverageColor"][self.label] = self.get_monitor_bounds()
        # Write to config file
        with open('config.ini', 'w') as cfg:
            config.write(cfg)


class BulbIconList(tkinter.Frame):  # pylint: disable=too-many-ancestors
    """ Holds the dynamic icons for each Device and Group """

    def __init__(self, *args, is_group=False, **kwargs):
        # Parameters
        self.is_group = is_group

        # Constants
        self.window_width = 285
        self.icon_width = 50
        self.icon_height = 75
        self.pad = 5
        self.highlight_color = 95

        # Icon Coding
        self.color_code = {
            "BULB_TOP": 11,
            "BACKGROUND": 15
        }

        # Initialization
        super().__init__(*args, width=self.window_width, height=self.icon_height, **kwargs)
        self.scrollx = 0
        self.scrolly = 0
        self.bulb_dict = {}
        self.canvas = tkinter.Canvas(self, width=self.window_width, height=self.icon_height,
                                     scrollregion=(0, 0, self.scrollx, self.scrolly))
        hbar = tkinter.Scrollbar(self, orient=tkinter.HORIZONTAL)
        hbar.pack(side=tkinter.BOTTOM, fill=tkinter.X)
        hbar.config(command=self.canvas.xview)
        self.canvas.config(width=self.window_width, height=self.icon_height)
        self.canvas.config(xscrollcommand=hbar.set)
        self.canvas.pack(side=tkinter.LEFT, expand=True, fill=tkinter.BOTH)
        self.current_icon_width = 0
        path = self.icon_path()
        self.original_icon = pImage.open(path).load()
        self._current_icon = None

    @property
    def current_icon(self):
        """ Returns the name of the currently selected Device/Group """
        return self._current_icon

    def icon_path(self):
        """ Returns the correct icon path for single Device or Group """
        if self.is_group:
            path = utilities.utils.resource_path("res/group.png")
        else:
            path = utilities.utils.resource_path("res/lightbulb.png")
        return path

    def draw_bulb_icon(self, bulb, label):
        """ Given a bulb and a name, add the icon to the end of the row. """
        # Make room on canvas
        self.scrollx += self.icon_width
        self.canvas.configure(scrollregion=(0, 0, self.scrollx, self.scrolly))
        # Build icon
        path = self.icon_path()
        sprite = tkinter.PhotoImage(file=path, master=self.master)
        image = self.canvas.create_image(
            (self.current_icon_width + self.icon_width - self.pad, self.icon_height / 2 + 2 * self.pad), image=sprite,
            anchor=tkinter.SE, tags=[label])
        text = self.canvas.create_text(self.current_icon_width + self.pad / 2, self.icon_height / 2 + 2 * self.pad,
                                       text=label[:8], anchor=tkinter.NW, tags=[label])
        self.bulb_dict[label] = (sprite, image, text)
        self.update_icon(bulb)
        # update sizing info
        self.current_icon_width += self.icon_width

    def update_icon(self, bulb: lifxlan.Light):
        """ If changes have been detected in the interface, update the bulb state. """
        if self.is_group:
            return
        try:
            # this is ugly, but only way to update icon accurately
            bulb_color = self.master.bulb_interface.color_cache[bulb.label]
            bulb_power = self.master.bulb_interface.power_cache[bulb.label]
            bulb_brightness = bulb_color[2]
            sprite, image, _ = self.bulb_dict[bulb.label]
        except TypeError:
            # First run will give us None; Is immediately corrected on next pass
            return
        # Calculate what number, 0-11, corresponds to current brightness
        brightness_scale = (int((bulb_brightness / 65535) * 10) * (bulb_power > 0)) - 1
        color_string = ''
        for y in range(sprite.height()):  # pylint: disable=invalid-name
            color_string += '{'
            for x in range(sprite.width()):  # pylint: disable=invalid-name
                # If the tick is < brightness, color it. Otherwise, set it back to the default color
                icon_rgb = self.original_icon[x, y][:3]
                if all([(v <= brightness_scale or v == self.color_code["BULB_TOP"]) for v in icon_rgb]) and \
                        self.original_icon[x, y][3] == 255:
                    bulb_color = bulb_color[0], bulb_color[1], bulb_color[2], bulb_color[3]
                    color = utilities.utils.HSBKtoRGB(bulb_color)
                elif all([v in (self.color_code["BACKGROUND"], self.highlight_color) for v in icon_rgb]) and \
                        self.original_icon[x, y][3] == 255:
                    color = sprite.get(x, y)[:3]
                else:
                    color = icon_rgb
                color_string += utilities.utils.tuple2hex(color) + ' '
            color_string += '} '
        # Write the final colorstring to the sprite, then update the GUI
        sprite.put(color_string, (0, 0, sprite.height(), sprite.width()))
        self.canvas.itemconfig(image, image=sprite)

    def set_selected_bulb(self, lightname):
        """ Highlight the newly selected bulb icon when changed. """
        if self._current_icon:
            self.clear_selected()
        sprite, image, _ = self.bulb_dict[lightname]
        color_string = ''
        for y in range(sprite.height()):  # pylint: disable=invalid-name
            color_string += '{'
            for x in range(sprite.width()):  # pylint: disable=invalid-name
                icon_rgb = sprite.get(x, y)[:3]
                if all([(v == self.color_code["BACKGROUND"]) for v in icon_rgb]) and self.original_icon[x, y][3] == 255:
                    color = (self.highlight_color,) * 3
                else:
                    color = icon_rgb
                color_string += utilities.utils.tuple2hex(color) + ' '
            color_string += '} '
        sprite.put(color_string, (0, 0, sprite.height(), sprite.width()))
        self.canvas.itemconfig(image, image=sprite)
        self._current_icon = lightname

    def clear_selected(self):
        """ Reset background to original state (from highlighted). """
        sprite, image, _ = self.bulb_dict[self._current_icon]
        color_string = ''
        for y in range(sprite.height()):  # pylint: disable=invalid-name
            color_string += '{'
            for x in range(sprite.width()):  # pylint: disable=invalid-name
                icon_rgb = sprite.get(x, y)[:3]
                if all([(v == self.highlight_color) for v in icon_rgb]) and self.original_icon[x, y][3] == 255:
                    color = (self.color_code["BACKGROUND"],) * 3
                else:
                    color = icon_rgb
                color_string += utilities.utils.tuple2hex(color) + ' '
            color_string += '} '
        sprite.put(color_string, (0, 0, sprite.height(), sprite.width()))
        self.canvas.itemconfig(image, image=sprite)
        self._current_icon = None


def main():
    """ Start the GUI, bulb_interface, loggers, exception handling, and finally run the app """
    try:
        root = tkinter.Tk()
        root.title("LIFX-Control-Panel")
        root.resizable(False, False)

        # Setup main_icon
        root.iconbitmap(utilities.utils.resource_path('res/icon_vector_9fv_icon.ico'))

        root.logger = logging.getLogger('root')
        root.logger.setLevel(logging.DEBUG)
        file_handler = logging.FileHandler(LOGFILE, mode='w')
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

        LifxFrame(root, lifxlan.LifxLAN(verbose=DEBUGGING), AsyncBulbInterface(threading.Event()))

        # Run main app
        root.mainloop()

    except Exception as exc:  # pylint: disable=broad-except
        root.logger.exception(exc)
        messagebox.showerror("Unhandled Exception", "Unhandled runtime exception: {}\n\n"
                                                    "Please report this at: {}".format(traceback.format_exc(),
                                                                                       r"https://github.com/samclane"
                                                                                       r"/LIFX-Control-Panel/issues"))
        os._exit(1)  # pylint: disable=protected-access


if __name__ == "__main__":
    main()
