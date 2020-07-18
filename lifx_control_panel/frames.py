import logging
import tkinter
from tkinter import ttk, font as font, messagebox, _setit
from typing import Union, List, Tuple, Dict

import lifxlan
import win32api
from desktopmagic.screengrab_win32 import getScreenAsImage, normalizeRects, getDisplayRects
from lifxlan import ORANGE, YELLOW, GREEN, CYAN, BLUE, PURPLE, PINK, WHITE, COLD_WHITE, WARM_WHITE, GOLD
from win32gui import GetCursorPos

from lifx_control_panel import RED, FRAME_PERIOD_MS
from lifx_control_panel.ui.colorscale import ColorScale
from lifx_control_panel.ui.settings import config
from lifx_control_panel.utilities import color_thread
from lifx_control_panel.utilities.utils import Color, tuple2hex, HSBKtoRGB, hueToRGB, kelvinToRGB, get_primary_monitor, \
    str2list, str2tuple


class LightFrame(ttk.Labelframe):  # pylint: disable=too-many-ancestors
    """ Holds control and state information about a single device. """
    label: str
    target: Union[lifxlan.Group, lifxlan.Device]

    def __init__(self, master, target: Union[lifxlan.Group, lifxlan.Device]):
        ttk.Labelframe.__init__(self, master, padding="3 3 12 12",
                                labelwidget=tkinter.Label(master, text="<LABEL_ERR>", font=font.Font(size=12),
                                                          fg="#0046d5",
                                                          relief=tkinter.RIDGE))
        self.is_group: bool = isinstance(target, lifxlan.Group)
        self.icon_update_flag: bool = True
        # Initialize LightFrames
        bulb_power: int = 0
        init_color: Color = Color(*lifxlan.WARM_WHITE)
        try:
            if self.is_group:
                devices: List[lifxlan.Device] = target.get_device_list()
                self.label = devices[0].get_group_label()
                bulb_power = devices[0].get_power()
                # Find an init_color- ensure device has color attribute, otherwise fallback
                color_devices: List[lifxlan.Device] = list(filter(lambda d: d.supports_color(), devices))
                if len(color_devices) and hasattr(color_devices[0], 'get_color'):
                    init_color = Color(*color_devices[0].get_color())
            else:  # is bulb
                self.label = target.get_label()
                bulb_power = target.get_power()
                if target.supports_multizone():
                    init_color = Color(*target.get_color_zones()[0])
                else:
                    init_color = Color(*target.get_color())
        except lifxlan.WorkflowException as exc:
            messagebox.showerror("Error building {}}",
                                 "Error thrown when trying to get label from bulb:\n{}".format(self.__class__.__name__,
                                                                                               exc))
            self.master.on_closing()
            # TODO Let this fail safely and try again later

        # Reconfigure label with correct name
        self.configure(labelwidget=tkinter.Label(master, text=self.label, font=font.Font(size=12),
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
            '%s logger initialized: %s // Device: %s', self.__class__.__name__,self.logger.name, self.label)

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
                                            background=tuple2hex(HSBKtoRGB(init_color)),
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
        self.hsbk_labels: Tuple[tkinter.Label]*4 = (
            tkinter.Label(self, text='%.3g' % (360 * (self.hsbk[0].get() / 65535))),
            tkinter.Label(self, text=str('%.3g' % (100 * self.hsbk[1].get() / 65535)) + "%"),
            tkinter.Label(self, text=str('%.3g' % (100 * self.hsbk[2].get() / 65535)) + "%"),
            tkinter.Label(self, text=str(self.hsbk[3].get()) + " K")
        )
        self.hsbk_scale: Tuple[ColorScale]*4 = (
            ColorScale(self, to=65535., variable=self.hsbk[0], command=self.update_color_from_ui),
            ColorScale(self, from_=0, to=65535, variable=self.hsbk[1], command=self.update_color_from_ui,
                       gradient='wb'),
            ColorScale(self, from_=0, to=65535, variable=self.hsbk[2], command=self.update_color_from_ui,
                       gradient='bw'),
            ColorScale(self, from_=2500, to=9000, variable=self.hsbk[3], command=self.update_color_from_ui,
                       gradient='kelvin'))
        relief = tkinter.GROOVE
        self.hsbk_display: Tuple[tkinter.Canvas]*4 = (
            tkinter.Canvas(self, background=tuple2hex(
                hueToRGB(360 * (init_color.hue / 65535))), width=20, height=20,
                           borderwidth=3,
                           relief=relief),
            tkinter.Canvas(self, background=tuple2hex((
                int(255 * (init_color.saturation / 65535)), int(255 * (init_color.saturation / 65535)),
                int(255 * (init_color.saturation / 65535)))),
                           width=20, height=20, borderwidth=3, relief=relief),
            tkinter.Canvas(self, background=tuple2hex((
                int(255 * (init_color.brightness / 65535)), int(255 * (init_color.brightness / 65535)),
                int(255 * (init_color.brightness / 65535)))),
                           width=20, height=20, borderwidth=3, relief=relief),
            tkinter.Canvas(self, background=tuple2hex(kelvinToRGB(init_color.kelvin)),
                           width=20, height=20,
                           borderwidth=3, relief=relief)
        )
        scale: ColorScale
        for key, scale in enumerate(self.hsbk_scale):
            tkinter.Label(self, text=self.hsbk[key]).grid(row=key + 1, column=0)
            scale.grid(row=key + 1, column=1)
            self.hsbk_labels[key].grid(row=key + 1, column=2)
            self.hsbk_display[key].grid(row=key + 1, column=3)

        self.threads: Dict[str, color_thread.ColorThreadRunner] = {}

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
        ####

        # Screen Avg.
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
        # Screen Dominant
        self.threads['dominant'] = color_thread.ColorThreadRunner(self.target, color_thread.dominant_screen_color, self,
                                                                  func_bounds=self.get_monitor_bounds)

        def start_screen_dominant():
            self.dominant_screen_btn.config(bg="Green")
            self.threads['dominant'].start()

        self.dominant_screen_btn = tkinter.Button(self.special_functions_lf, text="Dominant Screen Color",
                                                  command=start_screen_dominant)
        self.dominant_screen_btn.grid(row=7, column=0)

        # Audio
        self.threads['audio'] = color_thread.ColorThreadRunner(self.target, self.master.audio_interface.get_music_color,
                                                               self)

        def start_audio():
            """ Allow the audio to be run in a separate thread. Also turns button green while running. """
            self.music_button.config(bg="Green")
            self.threads['audio'].start()

        self.music_button = tkinter.Button(self.special_functions_lf, text="Music Color", command=start_audio,
                                           state='normal' if self.master.audio_interface.initialized else 'disabled')
        self.music_button.grid(row=8, column=0)
        self.threads['eyedropper'] = color_thread.ColorThreadRunner(self.target, self.eyedropper, self,
                                                                    continuous=False)
        tkinter.Button(self.special_functions_lf, text="Color Eyedropper", command=self.threads['eyedropper'].start) \
            .grid(row=7, column=1)
        tkinter.Button(self.special_functions_lf, text="Stop effects", command=self.stop_threads).grid(row=8, column=1)
        self.special_functions_lf.grid(row=6, columnspan=4)

        ####
        # Add custom screen region (real ugly)
        self.screen_region_lf = ttk.LabelFrame(self, text="Screen Avg. Region", padding="3 3 12 12")

        self.screen_region_entries: Dict[str, tkinter.Entry] = {
            'x1': tkinter.Entry(self.screen_region_lf, width=6),
            'x2': tkinter.Entry(self.screen_region_lf, width=6),
            'y1': tkinter.Entry(self.screen_region_lf, width=6),
            'y2': tkinter.Entry(self.screen_region_lf, width=6)
        }
        region = config['AverageColor'][self.label if self.label in config["AverageColor"].keys() else 'defaultmonitor']
        if region == "full":
            region = ["full"] * 4
        elif region[:19] == "get_primary_monitor":
            region = get_primary_monitor()
        else:
            region = str2list(region, int)
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
        tkinter.Button(self.screen_region_lf, text="Save", command=self.save_monitor_bounds) \
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
        return Color(*tuple(v.get() for v in self.hsbk))

    def stop_threads(self):
        """ Stop all ColorRunner threads """
        self.music_button.config(bg="SystemButtonFace")
        self.avg_screen_btn.config(bg="SystemButtonFace")
        self.dominant_screen_btn.config(bg="SystemButtonFace")
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

    def update_label(self, key: int):
        """ Update scale labels, formatted accordingly. """
        return [
            self.hsbk_labels[0].config(text=str('%.3g' % (360 * (self.hsbk[0].get() / 65535)))),
            self.hsbk_labels[1].config(text=str('%.3g' % (100 * (self.hsbk[1].get() / 65535))) + "%"),
            self.hsbk_labels[2].config(text=str('%.3g' % (100 * (self.hsbk[2].get() / 65535))) + "%"),
            self.hsbk_labels[3].config(text=str(self.hsbk[3].get()) + " K")
        ][key]

    def update_display(self, key):
        """ Update color swatches to match current device state """
        h, s, b, k = self.get_color_values_hsbk()  # pylint: disable=invalid-name
        if key == 0:
            self.hsbk_display[0].config(
                background=tuple2hex(hueToRGB(360 * (h / 65535))))
        elif key == 1:
            s = 65535 - s  # pylint: disable=invalid-name
            self.hsbk_display[1].config(
                background=tuple2hex(
                    (int(255 * (s / 65535)), int(255 * (s / 65535)), int(255 * (s / 65535)))))
        elif key == 2:
            self.hsbk_display[2].config(
                background=tuple2hex(
                    (int(255 * (b / 65535)), int(255 * (b / 65535)), int(255 * (b / 65535)))))
        elif key == 3:
            self.hsbk_display[3].config(background=tuple2hex(kelvinToRGB(k)))

    def get_color_from_palette(self):
        """ Asks users for color selection using standard color palette dialog. """
        color = tkinter.colorchooser.askcolor(initialcolor=HSBKtoRGB(self.get_color_values_hsbk()))[0]
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
            self.current_color.config(background=tuple2hex(HSBKtoRGB(hsbk)))

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
        cursor_pos = normalizeRects(getDisplayRects() +
                                    [(cursor_pos[0], cursor_pos[1], 0, 0)])[-1][:2]
        color = screen_img.getpixel(cursor_pos)
        self.master.master.deiconify()  # Reshow window
        self.logger.info("Eyedropper color found RGB %s", color)
        return lifxlan.RGBtoHSBK(color, temperature=self.get_color_values_hsbk().kelvin)

    def change_preset_dropdown(self, *_, **__):
        """ Change device color to selected preset option. """
        color = Color(*globals()[self.color_var.get()])
        self.preset_dropdown.config(bg=tuple2hex(HSBKtoRGB(color)),
                                    activebackground=tuple2hex(HSBKtoRGB(color)))
        self.set_color(color, False)

    def change_user_dropdown(self, *_, **__):
        """ Change device color to selected user-defined option. """
        color = str2tuple(config["PresetColors"][self.uservar.get()], int)
        self.user_dropdown.config(bg=tuple2hex(HSBKtoRGB(color)),
                                  activebackground=tuple2hex(HSBKtoRGB(color)))
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


class MultiZoneFrame(LightFrame):
    pass