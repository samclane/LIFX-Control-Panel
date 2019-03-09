import logging
import threading
import tkinter.font as font
import traceback
from collections import OrderedDict
from tkinter import *
from tkinter import _setit, messagebox, ttk
from tkinter.colorchooser import *
from win32gui import GetCursorPos

from PIL import Image as pImage
from lifxlan import *
from lifxlan import errors

from _constants import *
from ui import SysTrayIcon, settings
from ui.colorscale import ColorScale
from ui.settings import config
from ui.splashscreen import Splash
from utilities import audio, color_thread
from utilities.keypress import Keystroke_Watcher
from utilities.utils import *

RED = [0, 65535, 65535, 3500]  # Overwrite color, which appears black otherwise

audio.init(config)

HEARTBEAT_RATE = 3000  # 3 seconds
LOGFILE = 'lifx-control-panel.log'

# determine if application is a script file or frozen exe
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
elif __file__:
    application_path = os.path.dirname(__file__)

LOGFILE = os.path.join(application_path, LOGFILE)

SPLASHFILE = resource_path('res//splash_vector_png.png')


class Color:
    __slots__ = ['hue', 'saturation', 'brightness', 'kelvin']

    def __init__(self, hue, saturation, brightness, kelvin):
        self.hue = hue
        self.saturation = saturation
        self.brightness = brightness
        self.kelvin = kelvin

    def __getitem__(self, item):
        return self.__getattribute__(self.__slots__[item])

    def __len__(self):
        return 4

    def __setitem__(self, key, value):
        self.__setattr__(self.__slots__[key], value)

    def __str__(self):
        return "[{}, {}, {}, {}]".format(self.hue,
                                         self.saturation,
                                         self.brightness,
                                         self.kelvin)

    def __repr__(self):
        return [self.hue,
                self.saturation,
                self.brightness,
                self.kelvin
                ].__repr__()


class LifxFrame(ttk.Frame):
    def __init__(self, master, lifx_instance):  # We take a lifx instance so we can theoretically inject our own.
        self.splashscreen = Splash(master, SPLASHFILE)
        self.splashscreen.__enter__()
        # Setup frame and grid
        ttk.Frame.__init__(self, master, padding="3 3 12 12")
        self.master = master
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.grid(column=0, row=0, sticky=(N, W, E, S))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.lifx = lifx_instance

        # Setup logger
        self.logger = logging.getLogger(master.logger.name + '.' + self.__class__.__name__)
        self.logger.info('Root logger initialized: {}'.format(self.logger.name))
        self.logger.info('Binary Version: {}'.format(VERSION))
        self.logger.info('Config Version: {}'.format(config["Info"]["Version"]))
        self.logger.info('Build time: {}'.format(config["Info"]["BuildDate"]))

        # Setup menu
        self.menubar = Menu(master)
        self.menubar.add_command(label="Settings", command=self.show_settings)
        self.menubar.add_command(label="About", command=self.show_about)
        self.master.config(menu=self.menubar)

        # Initialize LIFX objects
        self.lightvar = StringVar(self)
        self.lightsdict = OrderedDict()  # LifxLight objects
        self.framesdict = {}  # corresponding LightFrame GUI
        self.current_lightframe = None  # currently selected and visible LightFrame
        self.current_light = None
        self.bulb_icons = BulbIconList(self)
        self.group_icons = BulbIconList(self, is_group=True)

        for x, light in enumerate(self.lifx.get_lights()):
            try:
                product = product_map[light.get_product()]
                label = light.get_label()
                light.get_color()
                self.lightsdict[label] = light
                self.logger.info('Light found: {}:({})'.format(product, label))
                self.bulb_icons.draw_bulb_icon(light, label)
                group_label = light.get_group_label()
                if not (group_label in self.lightsdict.keys()):
                    self.lightsdict[group_label] = self.lifx.get_devices_by_group(group_label)
                    # Giving an attribute here is a bit dirty, but whatever
                    self.lightsdict[group_label].label = group_label
                    self.group_icons.draw_bulb_icon(group, group_label)
                    self.logger.info("Group found: {}".format(group_label))
            except WorkflowException as e:
                self.logger.warning("Error when communicating with LIFX device: {}".format(e))

        if len(self.lightsdict):  # if any lights are found
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
        tray_options = (('Adjust Lights', None, lambda *_: self.master.deiconify()),)

        def lambda_factory(self_):
            return lambda *_: self_.on_closing()

        def run_tray_icon():
            SysTrayIcon.SysTrayIcon(resource_path('res/icon_vector_9fv_icon.ico'), "LIFX-Control-Panel", tray_options,
                                    on_quit=lambda_factory(self))

        self.systray_thread = threading.Thread(target=run_tray_icon, daemon=True)
        self.systray_thread.start()
        self.master.bind('<Unmap>', lambda *_: self.master.withdraw())  # Minimize to taskbar

        # Setup keybinding listener
        self.keylogger = Keystroke_Watcher(self)
        for keypress, function in dict(config['Keybinds']).items():
            light, color = function.split(':')
            color = Color(*eval(color, {}))
            self.save_keybind(light, keypress, color)

        # Stop splashscreen and start main function
        self.splashscreen.__exit__(None, None, None)

        # if any lights are found, show the first display
        if len(self.lightsdict):
            for l in self.lightsdict.values():
                self.framesdict[l.label] = LightFrame(self, l)
                self.logger.info("Building new frame: {}".format(self.framesdict[l.label].get_label()))
            self.current_lightframe = self.framesdict[l.label]
            try:
                self.bulb_icons.set_selected_bulb(l.label)
            except KeyError:
                self.group_icons.set_selected_bulb(l.label)

        # Start icon callback
        self.after(HEARTBEAT_RATE, self.update_icons)

        # Minimize if in config
        if eval(config["AppSettings"]["start_minimized"], {}):
            self.master.withdraw()

    def bulb_changed(self, *args):
        """ Change current display frame when dropdown menu is changed. """
        self.master.unbind('<Unmap>')  # unregister unmap so grid_remove doesn't trip it
        new_light_label = self.lightvar.get()
        if self.current_lightframe is not None:
            self.current_lightframe.stop()
            self.logger.debug('Stopping current frame: {}'.format(self.current_lightframe.get_label()))
        self.current_light = self.lightsdict[new_light_label]
        # loop below removes all other frames; not just the current one (this fixes sync bugs for some reason)
        for frame in self.framesdict.values():
            frame.grid_remove()
        self.framesdict[new_light_label].grid()  # should bring to front
        self.logger.info(
            "Brought existing frame to front: {}".format(self.framesdict[new_light_label].get_label()))
        self.current_lightframe = self.framesdict[new_light_label]
        self.current_lightframe.restart()
        if not self.current_lightframe.get_label() == self.lightvar.get():
            self.logger.error("Mismatch between LightFrame ({}) and Dropdown ({})".format(
                self.current_lightframe.get_label(), self.lightvar.get()))
        self.master.bind('<Unmap>', lambda *_: self.master.withdraw())  # reregister callback

    def on_bulb_canvas_click(self, event):
        canvas = event.widget
        # Convert to Canvas coords as we are using a Scrollbar, so Frame coords doesn't always match up.
        x = canvas.canvasx(event.x)
        y = canvas.canvasy(event.y)
        item = canvas.find_closest(x, y)
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
        if self.master.winfo_viewable():
            for fr in self.framesdict.values():
                if not fr.is_group and fr.icon_update_flag:
                    self.bulb_icons.update_icon(fr.target)
                    fr.icon_update_flag = False
        self.after(HEARTBEAT_RATE, self.update_icons)

    def save_keybind(self, light, keypress, color):
        def lambda_factory(self, light, color):
            """ https://stackoverflow.com/questions/938429/scope-of-lambda-functions-and-their-parameters """
            return lambda *_: self.lightsdict[light].set_color(color,
                                                               duration=float(config["AverageColor"]["duration"]))

        func = lambda_factory(self, light, color)
        self.keylogger.register_function(keypress, func)

    def delete_keybind(self, keycombo):
        self.keylogger.unregister_function(keycombo)

    def show_settings(self):
        self.keylogger.shutdown()
        s = settings.SettingsDisplay(self, "Settings")
        self.current_lightframe.update_user_dropdown()
        audio.init(config)
        for f in self.framesdict.values():
            f.music_button.config(state='normal' if audio.initialized else 'disabled')
        self.keylogger.restart()

    def show_about(self):
        messagebox.showinfo("About", "LIFX-Control-Panel\n"
                                     "Version {}\n"
                                     "{}, {}\n"
                                     "Bulb Icons by Quixote\n"
                                     "Please consider donating at ko-fi.com/sawyermclane"
                            .format(VERSION, AUTHOR, BUILD_DATE))

    def on_closing(self):
        self.logger.info('Shutting down.\n')
        self.master.destroy()
        sys.exit(0)


class LightFrame(ttk.Labelframe):
    def __init__(self, master, target):
        self.is_group = isinstance(target, Group)
        self.icon_update_flag = True
        # Initialize frame
        try:
            if self.is_group:
                devices = target.get_device_list()
                self.label = devices[0].get_group_label()
                bulb_power = devices[0].get_power()
                init_color = Color(*devices[0].get_color())
            else:  # is bulb
                self.label = target.get_label()
                bulb_power = target.get_power()
                init_color = Color(*target.get_color())
        except WorkflowException as e:
            messagebox.showerror("Error building LightFrame",
                                 "Error thrown when trying to get label from bulb:\n{}".format(e))
            self.master.on_closing()
        ttk.Labelframe.__init__(self, master, padding="3 3 12 12",
                                labelwidget=Label(master, text=self.label, font=font.Font(size=12), fg="#0046d5",
                                                  relief=RIDGE))
        self.grid(column=1, row=0, sticky=(N, W, E, S))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.target = target

        # Setup logger
        self.logger = logging.getLogger(
            self.master.logger.name + '.' + self.__class__.__name__ + '({})'.format(self.label))
        self.logger.setLevel(logging.DEBUG)
        self.logger.info(
            'LightFrame logger initialized: {} // Device: {}'.format(self.logger.name, self.label))

        # Initialize vars to hold on/off state
        self.powervar = BooleanVar(self)
        self.powervar.set(bulb_power)
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
        self.logger.info('Initial light color HSBK: {}'.format(init_color))
        self.current_color = Canvas(self, background=tuple2hex(HSBKtoRGB(init_color)), width=40, height=20,
                                    borderwidth=3,
                                    relief=GROOVE)
        self.current_color.grid(row=0, column=2)
        self.hsbk = (IntVar(self, init_color.hue, "Hue"),
                     IntVar(self, init_color.saturation, "Saturation"),
                     IntVar(self, init_color.brightness, "Brightness"),
                     IntVar(self, init_color.kelvin, "Kelvin"))
        for i in self.hsbk:
            i.trace('w', self.trigger_icon_update)
        self.hsbk_labels = (
            Label(self, text='%.3g' % (360 * (self.hsbk[0].get() / 65535))),
            Label(self, text=str('%.3g' % (100 * self.hsbk[1].get() / 65535)) + "%"),
            Label(self, text=str('%.3g' % (100 * self.hsbk[2].get() / 65535)) + "%"),
            Label(self, text=str(self.hsbk[3].get()) + " K")
        )
        self.hsbk_scale = (
            ColorScale(self, to=65535., variable=self.hsbk[0], command=self.update_color_from_ui),
            ColorScale(self, from_=0, to=65535, variable=self.hsbk[1], command=self.update_color_from_ui,
                       gradient='wb'),
            ColorScale(self, from_=0, to=65535, variable=self.hsbk[2], command=self.update_color_from_ui,
                       gradient='bw'),
            ColorScale(self, from_=2500, to=9000, variable=self.hsbk[3], command=self.update_color_from_ui,
                       gradient='kelvin'))
        relief = GROOVE
        self.hsbk_display = (
            Canvas(self, background=tuple2hex(HueToRGB(360 * (init_color.hue / 65535))), width=20, height=20,
                   borderwidth=3,
                   relief=relief),
            Canvas(self, background=tuple2hex((
                int(255 * (init_color.saturation / 65535)), int(255 * (init_color.saturation / 65535)),
                int(255 * (init_color.saturation / 65535)))),
                   width=20, height=20, borderwidth=3, relief=relief),
            Canvas(self, background=tuple2hex((
                int(255 * (init_color.brightness / 65535)), int(255 * (init_color.brightness / 65535)),
                int(255 * (init_color.brightness / 65535)))),
                   width=20, height=20, borderwidth=3, relief=relief),
            Canvas(self, background=tuple2hex(KelvinToRGB(init_color.kelvin)), width=20, height=20,
                   borderwidth=3, relief=relief)
        )
        for key, scale in enumerate(self.hsbk_scale):
            Label(self, text=self.hsbk[key]).grid(row=key + 1, column=0)
            scale.grid(row=key + 1, column=1)
            self.hsbk_labels[key].grid(row=key + 1, column=2)
            self.hsbk_display[key].grid(row=key + 1, column=3)

        self.threads = {}

        # Add buttons for pre-made colors
        self.preset_colors_lf = ttk.LabelFrame(self, text="Preset Colors", padding="3 3 12 12")
        self.colorVar = StringVar(self, value="Presets")
        self.default_colors = ["RED",
                               "ORANGE",
                               "YELLOW",
                               "GREEN",
                               "CYAN",
                               "BLUE",
                               "PURPLE",
                               "PINK",
                               "WHITE",
                               "COLD_WHITE",
                               "WARM_WHITE",
                               "GOLD"]
        self.preset_dropdown = OptionMenu(self.preset_colors_lf, self.colorVar, *self.default_colors)
        self.preset_dropdown.grid(row=0, column=0)
        self.preset_dropdown.configure(width=13)
        self.colorVar.trace('w', self.change_preset_dropdown)

        self.uservar = StringVar(self, value="User Presets")
        self.user_dropdown = OptionMenu(self.preset_colors_lf, self.uservar, *(
            [*config["PresetColors"].keys()] if len(config["PresetColors"].keys()) else [None]))
        self.user_dropdown.grid(row=0, column=1)
        self.user_dropdown.config(width=13)
        self.uservar.trace('w', self.change_user_dropdown)

        self.preset_colors_lf.grid(row=5, columnspan=4)

        # Add buttons for special routines
        self.special_functions_lf = ttk.LabelFrame(self, text="Special Functions", padding="3 3 12 12")
        self.threads['screen'] = color_thread.ColorThreadRunner(self.target, color_thread.avg_screen_color, self,
                                                                func_bounds=self.get_monitor_bounds)

        def start_screen_avg():
            self.avg_screen_btn.config(bg="Green")
            self.threads['screen'].start()

        self.avg_screen_btn = Button(self.special_functions_lf, text="Avg. Screen Color", command=start_screen_avg)
        self.avg_screen_btn.grid(row=6, column=0)
        Button(self.special_functions_lf, text="Pick Color", command=self.get_color_from_palette).grid(row=6, column=1)
        self.threads['audio'] = color_thread.ColorThreadRunner(self.target, audio.get_music_color, self)

        def start_audio():
            self.music_button.config(bg="Green")
            self.threads['audio'].start()

        self.music_button = Button(self.special_functions_lf, text="Music Color", command=start_audio,
                                   state='normal' if audio.initialized else 'disabled')
        self.music_button.grid(row=7, column=0)
        self.threads['eyedropper'] = color_thread.ColorThreadRunner(self.target, self.eyedropper, self,
                                                                    continuous=False)
        Button(self.special_functions_lf, text="Color Eyedropper", command=self.threads['eyedropper'].start) \
            .grid(row=7, column=1)
        Button(self.special_functions_lf, text="Stop effects", command=self.stop_threads).grid(row=8, column=0)
        self.special_functions_lf.grid(row=6, columnspan=4)

        # Add custom screen region (real ugly)
        self.screen_region_lf = ttk.LabelFrame(self, text="Screen Avg. Region", padding="3 3 12 12")

        self.screen_region_entires = {
            'x1': Entry(self.screen_region_lf, width=6),
            'x2': Entry(self.screen_region_lf, width=6),
            'y1': Entry(self.screen_region_lf, width=6),
            'y2': Entry(self.screen_region_lf, width=6)
        }
        if self.label in config["AverageColor"].keys():
            region = eval(config['AverageColor'][self.label],
                          {"full": "full", "get_primary_monitor": get_primary_monitor})
        else:
            region = eval(config['AverageColor']['defaultmonitor'],
                          {"full": "full", "get_primary_monitor": get_primary_monitor})
        if isinstance(region, str):
            region = ["full"] * 4
        self.screen_region_entires['x1'].insert(END, region[0])
        self.screen_region_entires['y1'].insert(END, region[1])
        self.screen_region_entires['x2'].insert(END, region[2])
        self.screen_region_entires['y2'].insert(END, region[3])
        Label(self.screen_region_lf, text="x1").grid(row=7, column=0, sticky='e')
        self.screen_region_entires['x1'].grid(row=7, column=1, padx=(0, 10))
        Label(self.screen_region_lf, text="x2").grid(row=7, column=2)
        self.screen_region_entires['x2'].grid(row=7, column=3)
        Label(self.screen_region_lf, text="y1").grid(row=8, column=0, sticky='e')
        self.screen_region_entires['y1'].grid(row=8, column=1, padx=(0, 10))
        Label(self.screen_region_lf, text="y2").grid(row=8, column=2)
        self.screen_region_entires['y2'].grid(row=8, column=3)
        self.save_region = Button(self.screen_region_lf, text="Save", command=self.save_monitor_bounds) \
            .grid(row=9, column=1, sticky='w')
        self.screen_region_lf.grid(row=7, columnspan=4)

        # Start update loop
        self.started = True
        self.update_status_from_bulb()

    def restart(self):
        self.started = True
        self.update_status_from_bulb()
        self.logger.info("Light frame Restarted.")

    def stop(self):
        self.started = False
        self.logger.info("Light frame Stopped.")

    def get_label(self):
        return self.label

    def trigger_icon_update(self, *args):
        """ Just sets a flag for now. Could be more advanced in the future. """
        self.icon_update_flag = True

    def get_color_values_hsbk(self):
        """ Get color values entered into GUI"""
        return Color(*tuple(v.get() for v in self.hsbk))

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

    def update_color_from_ui(self, *args):
        """ Send new color state to bulb when UI is changed. """
        self.stop_threads()
        self.set_color(self.get_color_values_hsbk(), rapid=True)

    def set_color(self, color, rapid=False):
        """ Should be called whenever the bulb wants to change color. Sends bulb command and updates UI accordingly. """
        self.stop_threads()
        try:
            self.target.set_color(color, duration=0 if rapid else float(config["AverageColor"]["duration"]) * 1000,
                                  rapid=rapid)
        except WorkflowException as e:
            if rapid:  # If we're going fast we don't care if we miss a packet.
                pass
            else:
                raise e
        self.update_status_from_bulb(run_once=True)  # Force UI to update from bulb
        if not rapid:
            self.logger.debug('Color changed to HSBK: {}'.format(color))  # Don't pollute log with rapid color changes

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

    def update_display(self, key):
        hsbk = h, s, b, k = self.get_color_values_hsbk()
        if key == 0:
            self.hsbk_display[0].config(background=tuple2hex(HueToRGB(360 * (h / 65535))))
        elif key == 1:
            s = 65535 - s
            self.hsbk_display[1].config(
                background=tuple2hex((int(255 * (s / 65535)), int(255 * (s / 65535)), int(255 * (s / 65535)))))
        elif key == 2:
            self.hsbk_display[2].config(
                background=tuple2hex((int(255 * (b / 65535)), int(255 * (b / 65535)), int(255 * (b / 65535)))))
        elif key == 3:
            self.hsbk_display[3].config(background=tuple2hex(KelvinToRGB(k)))

    def get_color_from_palette(self):
        """ Asks users for color selection using standard color palette dialog. """
        color = askcolor(initialcolor=HSBKtoRGB(self.get_color_values_hsbk()))[0]
        if color:
            # RGBtoHBSK sometimes returns >65535, so we have to truncate
            hsbk = [min(c, 65535) for c in utils.RGBtoHSBK(color, self.hsbk[3].get())]
            self.set_color(hsbk)
            self.logger.info("Color set to HSBK {} from palette.".format(hsbk))

    def update_status_from_bulb(self, run_once=False):
        """
        Periodically update status from the bulb to keep UI in sync.
        :param run_once: Don't call `after` statement at end. Keeps a million workers from being instanced.
        """
        require_icon_update = False
        if not self.started:
            return
        if not self.is_group:
            try:
                old_pwr = self.target.power_level
                new_pwr = self.target.get_power()
                if new_pwr != old_pwr:
                    require_icon_update = True
                self.powervar.set(new_pwr)
            except OSError:
                self.logger.warning("Error updating bulb power: OS")
                return
            except errors.WorkflowException:
                self.logger.warning("Error updating bulb power: Workflow")
                return
            if self.powervar.get() == 0:
                # Light is off
                self.option_off.select()
                self.option_on.selection_clear()
            else:
                self.option_on.select()
                self.option_off.selection_clear()
            try:
                hsbk = self.target.get_color()
                if hsbk != self.get_color_values_hsbk():
                    require_icon_update = True
                for key, val in enumerate(self.hsbk):
                    self.hsbk[key].set(hsbk[key])
                    self.update_label(key)
                    self.update_display(key)
                self.current_color.config(background=tuple2hex(HSBKtoRGB(hsbk)))
            except OSError:
                self.logger.warning("Error updating bulb color: OS")
            except errors.WorkflowException:
                self.logger.warning("Error updating bulb color: Workflow")
        if require_icon_update:
            self.trigger_icon_update()
        if self.started and not run_once:
            self.after(HEARTBEAT_RATE, self.update_status_from_bulb)

    def eyedropper(self, initial_color):
        """ Allows user to select a color pixel from the screen. """
        self.master.master.withdraw()  # Hide window
        state_left = win32api.GetKeyState(0x01)  # Left button down = 0 or 1. Button up = -127 or -128
        while True:
            a = win32api.GetKeyState(0x01)
            if a != state_left:  # Button state changed
                state_left = a
                if a < 0:  # Button down
                    pass
                else:  # Button up
                    break
            sleep(0.001)
        # Button state changed
        im = getScreenAsImage()
        cursorpos = GetCursorPos()
        cursorpos = normalizeRects(getDisplayRects() + [(cursorpos[0], cursorpos[1], 0, 0)])[-1][
                    :2]  # Convert display coords to image coords
        color = im.getpixel(cursorpos)
        self.master.master.deiconify()  # Reshow window
        self.logger.info("Eyedropper color found RGB {}".format(color))
        return utils.RGBtoHSBK(color, temperature=self.get_color_values_hsbk().kelvin)

    def change_preset_dropdown(self, *args):
        color = Color(*eval(self.colorVar.get()))
        self.preset_dropdown.config(bg=tuple2hex(HSBKtoRGB(color)),
                                    activebackground=tuple2hex(HSBKtoRGB(color)))
        self.set_color(color, False)

    def change_user_dropdown(self, *args):
        color = Color(*eval(config["PresetColors"][self.uservar.get()], {}))
        self.user_dropdown.config(bg=tuple2hex(HSBKtoRGB(color)),
                                  activebackground=tuple2hex(HSBKtoRGB(color)))
        self.set_color(color, rapid=False)

    def update_user_dropdown(self):
        # self.uservar.set('')
        self.user_dropdown["menu"].delete(0, 'end')

        new_choices = [key for key in config['PresetColors']]
        for choice in new_choices:
            self.user_dropdown["menu"].add_command(label=choice, command=_setit(self.uservar, choice))

    def get_monitor_bounds(self):
        return f"[{self.screen_region_entires['x1'].get()}, {self.screen_region_entires['y1'].get()}, " \
            f"{self.screen_region_entires['x2'].get()}, {self.screen_region_entires['y2'].get()}]"

    def save_monitor_bounds(self):
        config["AverageColor"][self.label] = self.get_monitor_bounds()
        # Write to config file
        with open('config.ini', 'w') as cfg:
            config.write(cfg)


class BulbIconList(Frame):
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
        self.COLOR_CODE = {
            "BULB_TOP": 11,
            "BACKGROUND": 15
        }

        # Initialization
        super().__init__(*args, width=self.window_width, height=self.icon_height, **kwargs)
        self.scrollx = 0
        self.scrolly = 0
        self.bulb_dict = {}
        self.canvas = Canvas(self, width=self.window_width, height=self.icon_height,
                             scrollregion=(0, 0, self.scrollx, self.scrolly))
        hbar = Scrollbar(self, orient=HORIZONTAL)
        hbar.pack(side=BOTTOM, fill=X)
        hbar.config(command=self.canvas.xview)
        self.canvas.config(width=self.window_width, height=self.icon_height)
        self.canvas.config(xscrollcommand=hbar.set)
        self.canvas.pack(side=LEFT, expand=True, fill=BOTH)
        self.current_icon_width = 0
        path = self.icon_path()
        self.original_icon = pImage.open(path).load()
        self._current_icon = None

    @property
    def current_icon(self):
        return self._current_icon

    def icon_path(self):
        if self.is_group:
            path = resource_path("res/group.png")
        else:
            path = resource_path("res/lightbulb.png")
        return path

    def draw_bulb_icon(self, bulb, label):
        # Make room on canvas
        self.scrollx += self.icon_width
        self.canvas.configure(scrollregion=(0, 0, self.scrollx, self.scrolly))
        # Build icon
        path = self.icon_path()
        sprite = PhotoImage(file=path, master=self.master)
        image = self.canvas.create_image(
            (self.current_icon_width + self.icon_width - self.pad, self.icon_height / 2 + 2 * self.pad), image=sprite,
            anchor=SE, tags=[label])
        text = self.canvas.create_text(self.current_icon_width + self.pad / 2, self.icon_height / 2 + 2 * self.pad,
                                       text=label[:8], anchor=NW, tags=[label])
        self.bulb_dict[label] = (sprite, image, text)
        self.update_icon(bulb)
        # update sizing info
        self.current_icon_width += self.icon_width

    def update_icon(self, bulb: lifxlan.Light):
        # Get updated info from local bulb object
        if self.is_group:
            return
        try:
            bulb_color = bulb.get_color()
            bulb_power = bulb.get_power()
            bulb_brightness = bulb_color[2]
            sprite, image, text = self.bulb_dict[bulb.label]
        except WorkflowException:
            return
        # Calculate what number, 0-11, corresponds to current brightness
        brightness_scale = (int((bulb_brightness / 65535) * 10) * (bulb_power > 0)) - 1
        color_string = ''
        for y in range(sprite.height()):
            color_string += '{'
            for x in range(sprite.width()):
                # If the tick is < brightness, color it. Otherwise, set it back to the default color
                icon_rgb = self.original_icon[x, y][:3]
                if all([(v <= brightness_scale or v == self.COLOR_CODE["BULB_TOP"]) for v in icon_rgb]) and \
                        self.original_icon[x, y][3] == 255:
                    bulb_color = bulb_color[0], bulb_color[1], bulb_color[2], bulb_color[3]
                    color = HSBKtoRGB(bulb_color)
                elif all([v in (self.COLOR_CODE["BACKGROUND"], self.highlight_color) for v in icon_rgb]) and \
                        self.original_icon[x, y][3] == 255:
                    color = sprite.get(x, y)[:3]
                else:
                    color = icon_rgb
                color_string += tuple2hex(color) + ' '
            color_string += '} '
        # Write the final colorstring to the sprite, then update the GUI
        sprite.put(color_string, (0, 0, sprite.height(), sprite.width()))
        self.canvas.itemconfig(image, image=sprite)

    def set_selected_bulb(self, lightname):
        if self._current_icon:
            self.clear_selected()
        sprite, image, text = self.bulb_dict[lightname]
        color_string = ''
        for y in range(sprite.height()):
            color_string += '{'
            for x in range(sprite.width()):
                icon_rgb = sprite.get(x, y)[:3]
                if all([(v == self.COLOR_CODE["BACKGROUND"]) for v in icon_rgb]) and self.original_icon[x, y][3] == 255:
                    color = (self.highlight_color,) * 3
                else:
                    color = icon_rgb
                color_string += tuple2hex(color) + ' '
            color_string += '} '
        sprite.put(color_string, (0, 0, sprite.height(), sprite.width()))
        self.canvas.itemconfig(image, image=sprite)
        self._current_icon = lightname

    def clear_selected(self):
        sprite, image, text = self.bulb_dict[self._current_icon]
        color_string = ''
        for y in range(sprite.height()):
            color_string += '{'
            for x in range(sprite.width()):
                icon_rgb = sprite.get(x, y)[:3]
                if all([(v == self.highlight_color) for v in icon_rgb]) and self.original_icon[x, y][3] == 255:
                    color = (self.COLOR_CODE["BACKGROUND"],) * 3
                else:
                    color = icon_rgb
                color_string += tuple2hex(color) + ' '
            color_string += '} '
        sprite.put(color_string, (0, 0, sprite.height(), sprite.width()))
        self.canvas.itemconfig(image, image=sprite)
        self._current_icon = None


root = None


def main():
    global root
    root = Tk()
    root.title("LIFX-Control-Panel")
    root.resizable(False, False)

    # Setup main_icon
    root.iconbitmap(resource_path('res/icon_vector_9fv_icon.ico'))

    root.logger = logging.getLogger('root')
    root.logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(LOGFILE, mode='w')
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    root.logger.addHandler(fh)
    sh = logging.StreamHandler()
    sh.setLevel(logging.DEBUG)
    sh.setFormatter(formatter)
    root.logger.addHandler(sh)
    root.logger.info('Logger initialized.')

    def custom_handler(type_, value, tb):
        global root
        root.logger.exception("Uncaught exception: {}:{}:{}".format(repr(type_), str(value), repr(tb)))

    sys.excepthook = custom_handler

    mainframe = LifxFrame(root, LifxLAN(verbose=DEBUGGING))

    # Run main app
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        root.logger.exception(e)
        messagebox.showerror("Unhandled Exception", "Unhandled runtime exception: {}\n\n"
                                                    "Please report this at: {}".format(traceback.format_exc(),
                                                                                       r"https://github.com/samclane/LIFX-Control-Panel/issues"))
        os._exit(1)
