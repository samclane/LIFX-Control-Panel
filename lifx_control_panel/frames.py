import logging
import threading
import tkinter
from tkinter import ttk, _setit
from typing import Union, List, Tuple, Dict, Mapping

import lifxlan
import win32api

from lifxlan import (
    ORANGE,
    YELLOW,
    GREEN,
    CYAN,
    BLUE,
    PURPLE,
    PINK,
    WHITE,
    COLD_WHITE,
    WARM_WHITE,
    GOLD,
)

from lifx_control_panel import RED, FRAME_PERIOD_MS
from lifx_control_panel.ui.colorscale import ColorScale
from lifx_control_panel.ui.settings import config
from lifx_control_panel.utilities import color_thread
from lifx_control_panel.utilities.color_thread import (
    get_screen_as_image,
    normalize_rectangles,
)
from lifx_control_panel.utilities.utils import (
    Color,
    tuple2hex,
    hsbk_to_rgb,
    hsv_to_rgb,
    kelvin_to_rgb,
    get_primary_monitor,
    str2list,
    str2tuple,
    get_display_rects,
)
from lifx_control_panel.utilities.multizone import set_zone_colors

MAX_KELVIN_DEFAULT = 9000

MIN_KELVIN_DEFAULT = 1500

# LIFX documents a budget of about 20 messages a second per device; ColorScale fires
# <B1-Motion> per pixel, which without this puts ~1800/sec on the wire during a slider drag.
COLOR_SEND_INTERVAL_MS = 50

# ~1 in 5 messages is lost to a strip on a weak link, in bursts. Six tries at lifxlan's
# one-second ack timeout covers a multi-second burst; it runs on a worker thread.
ZONE_COMMIT_ATTEMPTS = 6


class LightFrame(ttk.Labelframe):  # pylint: disable=too-many-ancestors
    """Holds control and state information about a single device."""

    label: str
    target: Union[lifxlan.Group, lifxlan.Device]
    ###
    screen_region_lf: ttk.LabelFrame
    screen_region_entries: Dict[str, ttk.Entry]
    avg_screen_btn: ttk.Button
    dominant_screen_btn: ttk.Button
    music_button: ttk.Button
    preset_colors_lf: ttk.LabelFrame
    color_var: tkinter.StringVar
    default_colors: Mapping[str, Color]
    preset_dropdown: ttk.OptionMenu
    tk_user_def_color_var: tkinter.StringVar
    user_dropdown: ttk.OptionMenu
    current_color: tkinter.Canvas
    hsbk: Tuple[tkinter.IntVar, tkinter.IntVar, tkinter.IntVar, tkinter.IntVar]
    hsbk_labels: Tuple[ttk.Entry, ttk.Entry, ttk.Entry, ttk.Entry]
    hsbk_entry_vars: Tuple[
        tkinter.StringVar, tkinter.StringVar, tkinter.StringVar, tkinter.StringVar
    ]
    hsbk_scale: Tuple[ColorScale, ColorScale, ColorScale, ColorScale]
    hsbk_display: Tuple[tkinter.Canvas, tkinter.Canvas, tkinter.Canvas, tkinter.Canvas]
    threads: Dict[str, color_thread.ColorThreadRunner]
    tk_power_var: tkinter.BooleanVar
    option_on: ttk.Radiobutton
    option_off: ttk.Radiobutton
    logger: logging.Logger
    min_kelvin: int = MIN_KELVIN_DEFAULT
    max_kelvin: int = MAX_KELVIN_DEFAULT
    # Class-level so set_color is safe to call before/during __init__
    _color_send_job = None
    _pending_color = None

    def __init__(self, master, target: lifxlan.Device):
        super().__init__(
            master,
            padding="8 6 8 8",
            labelwidget=ttk.Label(master, text="<LABEL_ERR>", style="Title.TLabel"),
        )
        self.icon_update_flag: bool = True
        # Initialize LightFrames
        bulb_power, init_color = self._get_light_info(target)

        # Reconfigure label with correct name
        self.configure(
            labelwidget=ttk.Label(master, text=self.label, style="Title.TLabel")
        )
        self.grid(column=1, row=0, sticky=(tkinter.N, tkinter.W, tkinter.E, tkinter.S))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.target = target

        # Setup logger
        self._setup_logger()

        # Initialize vars to hold on/off state
        self.setup_power_controls(bulb_power)

        # Initialize vars to hold and display bulb color
        self.setup_color_controls(init_color)

        # Add buttons for pre-made colors
        self._setup_color_dropdowns()

        # Add buttons for special routines
        self.special_functions_lf = ttk.LabelFrame(
            self, text="Special Functions", padding="3 3 12 12"
        )
        ####

        self._setup_special_functions()

        ####
        # Add custom screen region (real ugly)
        self._setup_screen_region_select()

        # Per-zone editing for multizone devices (Beam, Z strip)
        if hasattr(target, "get_color_zones"):  # hasattr also matches test dummies
            self._setup_zone_controls()

        self._pad_children()

        # Start update loop
        self.update_status_from_bulb()

    def _pad_children(self, parent=None):
        """Give every gridded widget the same breathing room, instead of padding each
        of the ~40 grid() calls individually."""
        for child in (parent or self).winfo_children():
            if child.winfo_manager() == "grid":
                child.grid_configure(padx=4, pady=3)
            if isinstance(child, ttk.LabelFrame):
                self._pad_children(child)

    def _get_light_info(self, target: lifxlan.Device) -> Tuple[int, Color]:
        # WorkflowException propagates up to scan_for_lights, which retries the frame build
        self.label = target.get_label()
        bulb_power: int = target.get_power()
        if hasattr(
            target, "get_color_zones"
        ):  # multizone; hasattr also matches test dummies
            # fetch once and reuse in _setup_zone_controls: a lossy bulb (e.g. Beam on
            # weak Wi-Fi) gets one timeout window during frame build, not two
            self.initial_zones = [Color(*zone) for zone in target.get_color_zones()]
            init_color = self.initial_zones[0]
        else:
            target: lifxlan.Light
            init_color = Color(*target.get_color())
        # get_product_features() populates lazily; raw .product_features can still be None
        features = target.get_product_features()
        self.min_kelvin = features.get("min_kelvin") or MIN_KELVIN_DEFAULT
        self.max_kelvin = features.get("max_kelvin") or MAX_KELVIN_DEFAULT
        return bulb_power, init_color

    def _setup_zone_controls(self):
        """Clickable strip of zone swatches; click/drag paints zones with the current slider color."""
        zones = (
            self.initial_zones
        )  # fetched in _get_light_info; avoid a second round-trip
        zones_lf = ttk.LabelFrame(
            self, text="Zones (click/drag to paint)", padding="3 3 12 12"
        )
        canvas_width = 200
        self.zone_width: float = canvas_width / len(zones)
        self.zone_canvas = tkinter.Canvas(
            zones_lf,
            width=canvas_width,
            height=20,
            borderwidth=1,
            relief=tkinter.GROOVE,
        )
        self.zone_rects = [
            self.zone_canvas.create_rectangle(
                index * self.zone_width,
                0,
                (index + 1) * self.zone_width,
                20,
                fill=tuple2hex(hsbk_to_rgb(zone)),
                outline="",
            )
            for index, zone in enumerate(zones)
        ]
        # The canvas is the source of truth while painting; commit_paint pushes it to the bulb
        self.zone_colors: List[Color] = list(zones)
        self._zone_commit_lock = threading.Lock()
        self._commit_seq = 0
        self._last_painted_zone = None
        self.zone_canvas.bind("<Button-1>", self.paint_zone)
        self.zone_canvas.bind("<B1-Motion>", self.paint_zone)
        self.zone_canvas.bind("<ButtonRelease-1>", self.commit_paint)
        self.zone_canvas.pack()
        zones_lf.grid(row=8, columnspan=4)

    def paint_zone(self, event):
        """Paint the zone under the cursor with the color currently in the HSBK sliders.

        Canvas only -- nothing is sent until the mouse comes up. A drag crosses a zone every
        few pixels, and one packet per crossing (~90/s here) buries a device rated for about
        20 messages a second: it stops acking, stops answering reads, and stays that way.
        """
        index = int(event.x // self.zone_width)
        if not 0 <= index < len(self.zone_rects):
            return
        if index == self._last_painted_zone:  # <B1-Motion> fires per pixel
            return
        self._last_painted_zone = index
        color = self.get_color_values_hsbk()
        self.zone_colors[index] = color
        self.zone_canvas.itemconfig(
            self.zone_rects[index], fill=tuple2hex(hsbk_to_rgb(color))
        )

    def commit_paint(self, *_):
        """On mouse release, send the whole painted strip to the bulb as one acked message."""
        self._last_painted_zone = None  # so re-clicking the same zone repaints
        self.stop_threads()
        # Flush any throttled whole-device color first, or it would land 50ms later and
        # repaint the strip uniform on top of the zones we're about to send.
        if self._color_send_job is not None:
            self.after_cancel(self._color_send_job)
            self._flush_color()
        self._commit_seq += 1
        self.logger.debug("commit_paint -> %d zones", len(self.zone_colors))
        threading.Thread(
            target=self._commit_zones,
            args=(list(self.zone_colors), self._commit_seq),
            daemon=True,
        ).start()

    def _commit_zones(self, colors, seq):
        """Retry a zone commit off the GUI thread.

        Packet loss to a strip comes in bursts of a second or more, so landing a commit can
        take several seconds of retries -- far too long to block tkinter for.
        """
        with self._zone_commit_lock:
            if seq != self._commit_seq:
                return  # a newer gesture was queued while this one waited; don't undo it
            try:
                set_zone_colors(self.target, colors, attempts=ZONE_COMMIT_ATTEMPTS)
            except lifxlan.WorkflowException as exc:
                self.logger.warning("Couldn't commit painted zones: %s", exc)

    def _setup_screen_region_select(self):
        self.screen_region_lf = ttk.LabelFrame(
            self, text="Screen Avg. Region", padding="3 3 12 12"
        )
        self.screen_region_entries = {
            "left": ttk.Entry(self.screen_region_lf, width=6),
            "width": ttk.Entry(self.screen_region_lf, width=6),
            "top": ttk.Entry(self.screen_region_lf, width=6),
            "height": ttk.Entry(self.screen_region_lf, width=6),
        }
        region = config["AverageColor"][
            (
                self.label
                if self.label in config["AverageColor"].keys()
                else "defaultmonitor"
            )
        ]
        if region == "full":
            region = ["full"] * 4
        elif region[:19] == "get_primary_monitor":
            region = get_primary_monitor()
        else:
            region = str2list(region, int)
        self.screen_region_entries["left"].insert(tkinter.END, region[0])
        self.screen_region_entries["top"].insert(tkinter.END, region[1])
        self.screen_region_entries["width"].insert(tkinter.END, region[2])
        self.screen_region_entries["height"].insert(tkinter.END, region[3])
        self._grid_horiz_coordinate_box("left", 7, "width")
        self._grid_horiz_coordinate_box("top", 8, "height")
        ttk.Button(
            self.screen_region_lf, text="Save", command=self.save_monitor_bounds
        ).grid(row=9, column=1, sticky="ew")
        self.screen_region_lf.grid(row=7, columnspan=4, sticky="ew")

    def _grid_horiz_coordinate_box(self, text: str, row, arg2):
        ttk.Label(self.screen_region_lf, text=text).grid(row=row, column=0, sticky="e")

        self.screen_region_entries[text].grid(row=row, column=1)
        ttk.Label(self.screen_region_lf, text=arg2).grid(row=row, column=2, sticky="e")
        self.screen_region_entries[arg2].grid(row=row, column=3)

    def _setup_special_functions(self):
        # Color cycle
        self.threads["cycle"] = color_thread.ColorThreadRunner(
            self.target, color_thread.ColorCycle(), self
        )

        def start_color_cycle():
            self.color_cycle_btn.config(style="Running.TButton")
            self.threads["cycle"].start()

        self.color_cycle_btn = ttk.Button(
            self.special_functions_lf,
            text="Color Cycle",
            command=start_color_cycle,
        )
        self.color_cycle_btn.grid(row=7, column=1, sticky="ew")
        # Screen Avg.
        self.threads["screen"] = color_thread.ColorThreadRunner(
            self.target,
            color_thread.avg_screen_color,
            self,
            func_bounds=self.get_monitor_bounds,
        )

        def start_screen_avg():
            """Allow the screen avg. to be run in a separate thread. Also highlights the button while running."""
            self.avg_screen_btn.config(style="Running.TButton")
            self.threads["screen"].start()

        self.avg_screen_btn = ttk.Button(
            self.special_functions_lf,
            text="Avg. Screen Color",
            command=start_screen_avg,
        )
        self.avg_screen_btn.grid(row=6, column=0, sticky="ew")
        ttk.Button(
            self.special_functions_lf,
            text="Pick Color",
            command=self.get_color_from_palette,
        ).grid(row=8, column=0, sticky="ew")
        # Screen Dominant
        self.threads["dominant"] = color_thread.ColorThreadRunner(
            self.target,
            color_thread.dominant_screen_color,
            self,
            func_bounds=self.get_monitor_bounds,
        )

        def start_screen_dominant():
            self.dominant_screen_btn.config(style="Running.TButton")
            self.threads["dominant"].start()

        self.dominant_screen_btn = ttk.Button(
            self.special_functions_lf,
            text="Dominant Screen Color",
            command=start_screen_dominant,
        )
        self.dominant_screen_btn.grid(row=6, column=1, sticky="ew")
        # Audio
        self.threads["audio"] = color_thread.ColorThreadRunner(
            self.target, self.master.audio_interface.get_music_color, self
        )

        def start_audio():
            """Allow the audio to be run in a separate thread. Also highlights the button while running."""
            self.music_button.config(style="Running.TButton")
            self.threads["audio"].start()

        self.music_button = ttk.Button(
            self.special_functions_lf,
            text="Music Color",
            command=start_audio,
            state=(
                "disabled" if not self.master.audio_interface.initialized else "normal"
            ),
        )
        self.music_button.grid(row=7, column=0, sticky="ew")
        self.threads["eyedropper"] = color_thread.ColorThreadRunner(
            self.target, self.eyedropper, self, continuous=False
        )
        ttk.Button(
            self.special_functions_lf,
            text="Color Eyedropper",
            command=self.threads["eyedropper"].start,
        ).grid(row=8, column=1, sticky="ew")
        ttk.Button(
            self.special_functions_lf, text="Stop effects", command=self.stop_threads
        ).grid(row=9, column=0, columnspan=2, sticky="ew")
        self.special_functions_lf.columnconfigure((0, 1), weight=1, uniform="fx")
        self.special_functions_lf.grid(row=6, columnspan=4, sticky="ew")

    def _setup_color_dropdowns(self):
        self.preset_colors_lf = ttk.LabelFrame(
            self, text="Preset Colors", padding="3 3 12 12"
        )
        self.color_var = tkinter.StringVar(self, value="Presets")
        self.default_colors = {
            "RED": RED,
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
            "GOLD": GOLD,
        }
        self.preset_dropdown = ttk.OptionMenu(
            self.preset_colors_lf, self.color_var, "Presets", *self.default_colors
        )
        self.preset_dropdown.grid(row=0, column=0, sticky="ew")
        self.preset_dropdown.configure(width=13)
        self.color_var.trace_add("write", self.change_preset_dropdown)
        self.tk_user_def_color_var = tkinter.StringVar(self, value="User Presets")
        self.user_dropdown = ttk.OptionMenu(
            self.preset_colors_lf,
            self.tk_user_def_color_var,
            "User Presets",
            *(
                [*config["PresetColors"].keys()]
                if any(config["PresetColors"].keys())
                else [None]
            ),
        )
        self.user_dropdown.grid(row=0, column=1, sticky="ew")
        self.user_dropdown.config(width=13)
        self.tk_user_def_color_var.trace_add("write", self.change_user_dropdown)
        self.preset_colors_lf.columnconfigure((0, 1), weight=1, uniform="preset")
        self.preset_colors_lf.grid(row=5, columnspan=4, sticky="ew")

    def setup_color_controls(self, init_color: Color):
        self.logger.info("Initial light color HSBK: %s", init_color)
        self.current_color = tkinter.Canvas(
            self,
            background=tuple2hex(hsbk_to_rgb(init_color)),
            width=46,
            height=22,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#909090",
        )
        self.current_color.grid(row=0, column=2, columnspan=2)
        self.hsbk = (
            tkinter.IntVar(self, init_color.hue, "Hue"),
            tkinter.IntVar(self, init_color.saturation, "Saturation"),
            tkinter.IntVar(self, init_color.brightness, "Brightness"),
            tkinter.IntVar(self, init_color.kelvin, "Kelvin"),
        )
        for i in self.hsbk:
            i.trace_add("write", self.trigger_icon_update)
        self.hsbk_entry_vars = tuple(
            tkinter.StringVar(self, str(var.get())) for var in self.hsbk
        )
        self.hsbk_labels = tuple(
            ttk.Entry(self, textvariable=svar, width=7, justify=tkinter.RIGHT)
            for svar in self.hsbk_entry_vars
        )
        for key, entry in enumerate(self.hsbk_labels):
            entry.bind("<Return>", lambda _, k=key: self.commit_entry(k))
            entry.bind("<FocusOut>", lambda _, k=key: self.commit_entry(k))
        self.hsbk_scale: Tuple[ColorScale, ColorScale, ColorScale, ColorScale] = (
            ColorScale(
                self,
                to=65535.0,
                variable=self.hsbk[0],
                command=self.update_color_from_ui,
            ),
            ColorScale(
                self,
                from_=0,
                to=65535,
                variable=self.hsbk[1],
                command=self.update_color_from_ui,
                gradient="wb",
            ),
            ColorScale(
                self,
                from_=0,
                to=65535,
                variable=self.hsbk[2],
                command=self.update_color_from_ui,
                gradient="bw",
            ),
            ColorScale(
                self,
                from_=self.min_kelvin,
                to=self.max_kelvin,
                variable=self.hsbk[3],
                command=self.update_color_from_ui,
                gradient="kelvin",
            ),
        )

        def gray(value: int):
            return (int(255 * (value / 65535)),) * 3

        self.hsbk_display: Tuple[
            tkinter.Canvas, tkinter.Canvas, tkinter.Canvas, tkinter.Canvas
        ] = tuple(
            tkinter.Canvas(
                self,
                background=tuple2hex(swatch),
                width=22,
                height=22,
                borderwidth=0,
                highlightthickness=1,
                highlightbackground="#909090",
            )
            for swatch in (
                hsv_to_rgb(360 * (init_color.hue / 65535)),
                gray(init_color.saturation),
                gray(init_color.brightness),
                kelvin_to_rgb(init_color.kelvin),
            )
        )
        scale: ColorScale
        for key, scale in enumerate(self.hsbk_scale):
            ttk.Label(self, text=str(self.hsbk[key])).grid(
                row=key + 1, column=0, sticky="e"
            )
            scale.grid(row=key + 1, column=1, sticky="ew")
            self.hsbk_labels[key].grid(row=key + 1, column=2)
            self.hsbk_display[key].grid(row=key + 1, column=3)
        self.threads: Dict[str, color_thread.ColorThreadRunner] = {}

    def setup_power_controls(self, bulb_power: int):
        self.tk_power_var = tkinter.BooleanVar(self)
        self.tk_power_var.set(bool(bulb_power))
        self.option_on = ttk.Radiobutton(
            self,
            text="On",
            variable=self.tk_power_var,
            value=True,
            command=self.update_power,
        )
        self.option_off = ttk.Radiobutton(
            self,
            text="Off",
            variable=self.tk_power_var,
            value=False,
            command=self.update_power,
        )
        self.option_on.grid(row=0, column=0, sticky="w")
        self.option_off.grid(row=0, column=1, sticky="w")

    def _setup_logger(self):
        self.logger = logging.getLogger(
            self.master.logger.name + "." + self.__class__.__name__ + f"({self.label})"
        )
        self.logger.setLevel(logging.DEBUG)
        self.logger.info(
            "%s logger initialized: %s // Device: %s",
            self.__class__.__name__,
            self.logger.name,
            self.label,
        )

    def restart(self):
        """Get updated information for the bulb when clicked."""
        self.update_status_from_bulb()
        self.logger.info("Light frame Restarted.")

    def get_label(self):
        """Getter method for the label attribute. Often is monkey-patched."""
        return self.label

    def trigger_icon_update(self, *_, **__):
        """Just sets a flag for now. Could be more advanced in the future."""
        self.icon_update_flag = True

    def get_color_values_hsbk(self):
        """Get color values entered into GUI"""
        return Color(*tuple(v.get() for v in self.hsbk))

    def stop_threads(self):
        """Stop all ColorRunner threads"""
        for button in (
            self.music_button,
            self.avg_screen_btn,
            self.dominant_screen_btn,
            self.color_cycle_btn,
        ):
            button.config(style="TButton")
        for thread in self.threads.values():
            thread.stop()

    def update_power(self):
        """Send new power state to bulb when UI is changed."""
        self.stop_threads()
        self.target.set_power(self.tk_power_var.get())

    def update_color_from_ui(self, *_, **__):
        """Send new color state to bulb when UI is changed."""
        self.stop_threads()
        if hasattr(self, "zone_rects"):
            # On a strip the sliders choose the color paint_zone will apply -- they are a
            # palette, not a device command. Pushing it to the bulb here would flood the
            # whole strip with that color and reset zone_colors, so every stroke painted
            # the color the strip had just become and appeared to do nothing. Use the
            # presets or the palette button to set the whole strip at once.
            self._show_paint_color()
            return
        self.set_color(self.get_color_values_hsbk(), rapid=True)

    def _show_paint_color(self):
        """Reflect the sliders in the swatches without touching the bulb or the zones."""
        for key in range(len(self.hsbk)):
            self.update_display(key)
        self.update_label()
        self.current_color.config(
            background=tuple2hex(hsbk_to_rgb(self.get_color_values_hsbk()))
        )

    def _send_color(self, color, rapid):
        """The one place a whole-device color actually goes out on the wire."""
        try:
            self.target.set_color(
                color,
                duration=(
                    0 if rapid else float(config["AverageColor"]["duration"]) * 1000
                ),
                rapid=rapid,
            )
        except lifxlan.WorkflowException as exc:
            if not rapid:
                raise exc

    def _flush_color(self):
        """Send the newest color a drag has produced since the last tick."""
        self._color_send_job = None
        if self._pending_color is not None:
            color, self._pending_color = self._pending_color, None
            self._send_color(color, rapid=True)

    def set_color(self, color, rapid=False):
        """Should be called whenever the bulb wants to change color. Sends bulb command and updates UI accordingly."""
        self.stop_threads()
        if rapid:
            # ColorScale fires <B1-Motion> per pixel, so one packet per event puts ~1800
            # msg/sec on a device that absorbs about 20. The backlog then keeps applying for
            # seconds *after* the drag, overwriting whatever was sent next -- which is why
            # painting zones stopped taking once a slider had been touched. Coalesce to the
            # newest value per tick; the trailing send guarantees the final value lands.
            self._pending_color = color
            if self._color_send_job is None:
                self._color_send_job = self.after(
                    COLOR_SEND_INTERVAL_MS, self._flush_color
                )
        else:
            if self._color_send_job is not None:
                self.after_cancel(self._color_send_job)
                self._color_send_job = None
            self._pending_color = None
            self._send_color(color, rapid=False)
        # Keep the sliders in sync with the chosen color. paint_zone reads them as its source,
        # and for multizone the heartbeat no longer syncs a device color, so presets/palette
        # would otherwise leave the sliders (and thus painting) stuck at the dim init color.
        # Also refresh the swatches/entries here: update_status_from_bulb used to be the only
        # thing driving them, and it no longer sees a color for multizone devices.
        for key, value in enumerate(color):
            if self.hsbk[key].get() != value:
                self.hsbk[key].set(value)
            self.update_display(key)
        self.update_label()
        if hasattr(self, "zone_rects"):  # whole-device set makes all zones uniform
            self.zone_colors = [Color(*color)] * len(self.zone_rects)
            for rect in self.zone_rects:
                self.zone_canvas.itemconfig(rect, fill=tuple2hex(hsbk_to_rgb(color)))
        if not rapid:
            self.logger.debug(
                "Color changed to HSBK: %s", color
            )  # Don't pollute log with rapid color changes

    def update_label(self):
        """Refresh entry fields to match current HSBK values."""
        for key, svar in enumerate(self.hsbk_entry_vars):
            svar.set(str(self.hsbk[key].get()))

    def commit_entry(self, key: int):
        """Apply a manually-typed HSBK value from its entry field, clamped to range."""
        scale = self.hsbk_scale[key]
        try:
            val = int(float(self.hsbk_entry_vars[key].get()))
        except ValueError:
            val = self.hsbk[key].get()
        val = min(max(val, int(scale.min)), int(scale.max))
        self.hsbk_entry_vars[key].set(str(val))
        self.hsbk[key].set(val)
        self.update_color_from_ui()

    def update_display(self, key: int):
        """Update color swatches to match current device state"""
        h, s, b, k = self.get_color_values_hsbk()  # pylint: disable=invalid-name
        if key == 0:
            self.hsbk_display[0].config(
                background=tuple2hex(hsv_to_rgb(360 * (h / 65535)))
            )
        elif key == 1:
            s = 65535 - s  # pylint: disable=invalid-name
            self.hsbk_display[1].config(
                background=tuple2hex(
                    (
                        int(255 * (s / 65535)),
                        int(255 * (s / 65535)),
                        int(255 * (s / 65535)),
                    )
                )
            )
        elif key == 2:
            self.hsbk_display[2].config(
                background=tuple2hex(
                    (
                        int(255 * (b / 65535)),
                        int(255 * (b / 65535)),
                        int(255 * (b / 65535)),
                    )
                )
            )
        elif key == 3:
            self.hsbk_display[3].config(background=tuple2hex(kelvin_to_rgb(k)))

    def get_color_from_palette(self):
        """Asks users for color selection using standard color palette dialog."""
        color = tkinter.colorchooser.askcolor(
            initialcolor=hsbk_to_rgb(self.get_color_values_hsbk())
        )[0]
        if color:
            # RGBtoHBSK sometimes returns >65535, so we have to truncate
            hsbk = [min(c, 65535) for c in lifxlan.RGBtoHSBK(color, self.hsbk[3].get())]
            self.set_color(hsbk)
            self.logger.info("Color set to HSBK %s from palette.", hsbk)

    def update_status_from_bulb(self, run_once=False):
        """
        Periodically update status from the bulb to keep UI in sync.
        run_once - Don't call `after` statement at end. Keeps a million workers from being instanced.
        """
        require_icon_update = False
        power_queue = self.master.bulb_interface.power_queue
        if (
            self.label in power_queue
            and not self.master.bulb_interface.power_queue[self.label].empty()
        ):
            power = self.master.bulb_interface.power_queue[self.label].get()
            require_icon_update = True
            self.tk_power_var.set(bool(power))  # radiobuttons follow the var

        color_queue = self.master.bulb_interface.color_queue
        if (
            self.label in color_queue
            and not self.master.bulb_interface.color_queue[self.label].empty()
        ):
            hsbk = self.master.bulb_interface.color_queue[self.label].get()
            require_icon_update = True
            for key, _ in enumerate(self.hsbk):
                self.hsbk[key].set(hsbk[key])
                self.update_display(key)
            self.update_label()
            self.current_color.config(background=tuple2hex(hsbk_to_rgb(hsbk)))

        if require_icon_update:
            self.trigger_icon_update()
        if not run_once:
            self.after(FRAME_PERIOD_MS, self.update_status_from_bulb)

    def eyedropper(self, *_, **__):
        """Allows user to select a color pixel from the screen."""
        self.master.master.withdraw()  # Hide window
        state_left = win32api.GetKeyState(
            0x01
        )  # Left button down = 0 or 1. tkinter.Button up = -127 or -128
        while True:
            action = win32api.GetKeyState(0x01)
            if action != state_left:  # tkinter.Button state changed
                state_left = action
                if action >= 0:
                    break
            lifxlan.sleep(0.001)
        # tkinter.Button state changed
        screen_img = get_screen_as_image()
        cursor_pos = win32api.GetCursorPos()
        # Convert display coords to image coords
        cursor_pos = normalize_rectangles(
            get_display_rects() + [(cursor_pos[0], cursor_pos[1], 0, 0)]
        )[-1][:2]
        color = screen_img.getpixel(cursor_pos)
        self.master.master.deiconify()  # Reshow window
        self.logger.info("Eyedropper color found RGB %s", color)
        return lifxlan.RGBtoHSBK(color, temperature=self.get_color_values_hsbk().kelvin)

    def change_preset_dropdown(self, *_, **__):
        """Change device color to selected preset option."""
        color = Color(*globals()[self.color_var.get()])
        self.set_color(color, False)

    def change_user_dropdown(self, *_, **__):
        """Change device color to selected user-defined option."""
        color = str2tuple(config["PresetColors"][self.tk_user_def_color_var.get()], int)
        self.set_color(color, rapid=False)

    def update_user_dropdown(self):
        """Add newly defined color to the user color dropdown menu."""
        # self.tk_user_def_color_var.set('')
        self.user_dropdown["menu"].delete(0, "end")

        for choice in config["PresetColors"]:
            self.user_dropdown["menu"].add_command(
                label=choice, command=_setit(self.tk_user_def_color_var, choice)
            )

    def get_monitor_bounds(self):
        """Return the 4 rectangle coordinates from the entry boxes in the UI"""
        return (
            f"[{self.screen_region_entries['left'].get()}, {self.screen_region_entries['top'].get()}, "
            f"{self.screen_region_entries['width'].get()}, {self.screen_region_entries['height'].get()}]"
        )

    def save_monitor_bounds(self):
        """Write monitor bounds entered into the UI into the config file."""
        config["AverageColor"][self.label] = self.get_monitor_bounds()
        # Write to config file
        with open("config.ini", "w", encoding="utf-8") as cfg:
            config.write(cfg)


class GroupFrame(LightFrame):
    def _get_light_info(self, target: lifxlan.Group) -> Tuple[int, Color]:
        init_color: Color = Color(*lifxlan.WARM_WHITE)
        # WorkflowException propagates up to scan_for_lights, which retries the frame build
        devices: List[Union[lifxlan.Group, lifxlan.Light, lifxlan.MultiZoneLight]] = (
            target.get_device_list()
        )
        if not devices:
            logging.error("No devices found in group list")
            self.label = "<No Group Found>"
            self.min_kelvin, self.max_kelvin = 0, 99999  # arbitrary range
            return 0, Color(0, 0, 0, 0)

        self.label = devices[0].get_group_label()
        bulb_power: int = devices[0].get_power()
        # Find an init_color- ensure device has color attribute, otherwise fallback
        color_devices: List[
            Union[lifxlan.Group, lifxlan.Light, lifxlan.MultiZoneLight]
        ] = list(filter(lambda d: d.supports_color(), devices))
        if color_devices and hasattr(color_devices[0], "get_color"):
            init_color = Color(*color_devices[0].get_color())
        # get_product_features() populates lazily; raw .product_features can still be None
        self.min_kelvin = min(
            device.get_product_features().get("min_kelvin") or MIN_KELVIN_DEFAULT
            for device in devices
        )
        self.max_kelvin = max(
            device.get_product_features().get("max_kelvin") or MAX_KELVIN_DEFAULT
            for device in devices
        )
        return bulb_power, init_color

    def update_status_from_bulb(self, run_once=False):
        return
