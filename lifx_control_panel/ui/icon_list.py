from __future__ import annotations

import tkinter
from PIL import Image as pImage

import lifxlan
from ..utilities import utils

WINDOW_WIDTH = 285
ICON_WIDTH = 50
ICON_HEIGHT = 75
ICON_PADDING = 5
HIGHLIGHT_SATURATION = 95
COLOR_CODE = {"BULB_TOP": 11, "BACKGROUND": 15}


class BulbIconList(tkinter.Frame):  # pylint: disable=too-many-instance-attributes
    """ Holds the dynamic icons for each Device and Group """

    def __init__(self, *args, is_group: bool = False, **kwargs):
        # Parameters
        self.is_group = is_group

        # Integer DPI zoom so icons match the DPI-scaled fonts. Derived from the parent's
        # DPI (96 = 100%); zoom/NEAREST keep the exact palette values update_icon and
        # set_selected_bulb key off of (interpolation would blend them and break coloring).
        master = args[0] if args else kwargs.get("master")
        self.scale = max(1, round(master.winfo_fpixels("1i") / 96))
        self.icon_width = ICON_WIDTH * self.scale
        self.icon_height = ICON_HEIGHT * self.scale
        self.icon_padding = ICON_PADDING * self.scale
        window_width = WINDOW_WIDTH * self.scale

        # Initialization
        super().__init__(*args, width=window_width, height=self.icon_height, **kwargs)
        self.scroll_x = 0
        self.scroll_y = 0
        self.bulb_dict: dict[str, tuple[tkinter.PhotoImage, int, int]] = {}
        self.canvas = tkinter.Canvas(
            self,
            width=window_width,
            height=self.icon_height,
            scrollregion=(0, 0, self.scroll_x, self.scroll_y),
        )
        h_scroll = tkinter.Scrollbar(self, orient=tkinter.HORIZONTAL)
        h_scroll.pack(side=tkinter.BOTTOM, fill=tkinter.X)
        h_scroll.config(command=self.canvas.xview)
        self.canvas.config(width=window_width, height=self.icon_height)
        self.canvas.config(xscrollcommand=h_scroll.set)
        self.canvas.pack(side=tkinter.LEFT, expand=True, fill=tkinter.BOTH)
        self.current_icon_width = 0
        path = self.icon_path()
        source = pImage.open(path)
        if self.scale > 1:  # NEAREST keeps palette values aligned 1:1 with the zoomed sprite
            source = source.resize(
                (source.width * self.scale, source.height * self.scale), pImage.NEAREST
            )
        self.original_icon = source.load()
        self._current_icon = None

    @property
    def current_icon(self):
        """ Returns the name of the currently selected Device/Group """
        return self._current_icon

    def icon_path(self):
        """ Returns the correct icon path for single Device or Group """
        return (
            utils.resource_path("res/group.png")
            if self.is_group
            else utils.resource_path("res/lightbulb.png")
        )

    def draw_bulb_icon(self, bulb, label):
        """ Given a bulb and a name, add the icon to the end of the row. """
        # Make room on canvas
        self.scroll_x += self.icon_width
        self.canvas.configure(scrollregion=(0, 0, self.scroll_x, self.scroll_y))
        # Build icon
        path = self.icon_path()
        sprite = tkinter.PhotoImage(file=path, master=self.master)
        if self.scale > 1:  # integer nearest-neighbor zoom; preserves palette values
            sprite = sprite.zoom(self.scale)
        image = self.canvas.create_image(
            (
                self.current_icon_width + self.icon_width - self.icon_padding,
                self.icon_height / 2 + 2 * self.icon_padding,
            ),
            image=sprite,
            anchor=tkinter.SE,
            tags=[label],
        )
        text = self.canvas.create_text(
            self.current_icon_width + self.icon_padding / 2,
            self.icon_height / 2 + 2 * self.icon_padding,
            text=label[:8],
            anchor=tkinter.NW,
            tags=[label],
        )
        self.bulb_dict[label] = (sprite, image, text)
        self.update_icon(bulb)
        # update sizing info
        self.current_icon_width += self.icon_width

    def update_icon(self, bulb: lifxlan.Device):
        """ If changes have been detected in the interface, update the bulb state. """
        if self.is_group:
            return
        try:
            # this is ugly, but only way to update icon accurately
            bulb_color = self.master.bulb_interface.color_cache[bulb.label]
            bulb_power = self.master.bulb_interface.power_cache[bulb.label]
            bulb_brightness = bulb_color[2]
            sprite, image, _ = self.bulb_dict[bulb.label]
        except (TypeError, KeyError):
            # TypeError: first run gives None; KeyError: bulb missed during a rescan
            # (WorkflowException in set_device_list) so the new cache lacks its label.
            # Both are corrected on a later pass.
            return
        # Calculate what number, 0-11, corresponds to current brightness
        brightness_scale = (int((bulb_brightness / 65535) * 10) * (bulb_power > 0)) - 1
        color_string = ""
        for y in range(sprite.height()):  # pylint: disable=invalid-name
            color_string += "{"
            for x in range(sprite.width()):  # pylint: disable=invalid-name
                # If the tick is < brightness, color it. Otherwise, set it back to the default color
                icon_rgb = self.original_icon[x, y][:3]
                if (
                    all(
                        (v <= brightness_scale or v == COLOR_CODE["BULB_TOP"])
                        for v in icon_rgb
                    )
                    and self.original_icon[x, y][3] == 255
                ):
                    color = utils.hsbk_to_rgb(bulb_color)
                elif (
                    all(
                        v in (COLOR_CODE["BACKGROUND"], HIGHLIGHT_SATURATION)
                        for v in icon_rgb
                    )
                    and self.original_icon[x, y][3] == 255
                ):
                    color = sprite.get(x, y)[:3]
                else:
                    color = icon_rgb
                color_string += utils.tuple2hex(color) + " "
            color_string += "} "
        # Write the final colorstring to the sprite, then update the GUI
        sprite.put(color_string, (0, 0, sprite.height(), sprite.width()))
        self.canvas.itemconfig(image, image=sprite)

    def set_selected_bulb(self, light_name):
        """ Highlight the newly selected bulb icon when changed. """
        if self._current_icon:
            self.clear_selected()
        sprite, image, _ = self.bulb_dict[light_name]
        color_string = ""
        for y in range(sprite.height()):  # pylint: disable=invalid-name
            color_string += "{"
            for x in range(sprite.width()):  # pylint: disable=invalid-name
                icon_rgb = sprite.get(x, y)[:3]
                if (
                    all(v == COLOR_CODE["BACKGROUND"] for v in icon_rgb)
                    and self.original_icon[x, y][3] == 255
                ):
                    color = (HIGHLIGHT_SATURATION,) * 3
                else:
                    color = icon_rgb
                color_string += utils.tuple2hex(color) + " "
            color_string += "} "
        sprite.put(color_string, (0, 0, sprite.height(), sprite.width()))
        self.canvas.itemconfig(image, image=sprite)
        self._current_icon = light_name

    def clear_selected(self):
        """ Reset background to original state (from highlighted). """
        sprite, image, _ = self.bulb_dict[self._current_icon]
        color_string = ""
        for y in range(sprite.height()):  # pylint: disable=invalid-name
            color_string += "{"
            for x in range(sprite.width()):  # pylint: disable=invalid-name
                icon_rgb = sprite.get(x, y)[:3]
                if (
                    all(v == HIGHLIGHT_SATURATION for v in icon_rgb)
                    and self.original_icon[x, y][3] == 255
                ):
                    color = (COLOR_CODE["BACKGROUND"],) * 3
                else:
                    color = icon_rgb
                color_string += utils.tuple2hex(color) + " "
            color_string += "} "
        sprite.put(color_string, (0, 0, sprite.height(), sprite.width()))
        self.canvas.itemconfig(image, image=sprite)
        self._current_icon = None
