from __future__ import annotations
from dataclasses import dataclass, field

import tkinter
from typing import Dict, Union
from PIL import Image as pImage

import lifxlan
from ..utilities import utils


@dataclass
class BulbIconListSettings:
    """ Encapsulates all constants for the bulb icon list """

    window_width: int
    icon_width: int
    icon_height: int
    icon_padding: int
    highlight_saturation: int
    color_code: dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        self.window_width = max(0, self.window_width)
        self.icon_width = max(0, self.icon_width)
        self.icon_height = max(0, self.icon_height)
        self.icon_padding = max(0, self.icon_padding)
        self.highlight_saturation = min(max(0, self.highlight_saturation), 255)


class BulbIconList(tkinter.Frame):  # pylint: disable=too-many-instance-attributes
    """ Holds the dynamic icons for each Device and Group """

    def __init__(self, *args, is_group: bool = False, **kwargs):
        # Parameters
        self.is_group = is_group

        # Constants
        self.settings = BulbIconListSettings(
            window_width=285,
            icon_width=50,
            icon_height=75,
            icon_padding=5,
            highlight_saturation=95,
            color_code={"BULB_TOP": 11, "BACKGROUND": 15},
        )

        # Initialization
        super().__init__(
            *args,
            width=self.settings.window_width,
            height=self.settings.icon_height,
            **kwargs
        )
        self.scroll_x = 0
        self.scroll_y = 0
        self.bulb_dict: dict[str, tuple[tkinter.PhotoImage, int, int]] = {}
        self.canvas = tkinter.Canvas(
            self,
            width=self.settings.window_width,
            height=self.settings.icon_height,
            scrollregion=(0, 0, self.scroll_x, self.scroll_y),
        )
        h_scroll = tkinter.Scrollbar(self, orient=tkinter.HORIZONTAL)
        h_scroll.pack(side=tkinter.BOTTOM, fill=tkinter.X)
        h_scroll.config(command=self.canvas.xview)
        self.canvas.config(
            width=self.settings.window_width, height=self.settings.icon_height
        )
        self.canvas.config(xscrollcommand=h_scroll.set)
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
        return (
            utils.resource_path("res/group.png")
            if self.is_group
            else utils.resource_path("res/lightbulb.png")
        )

    @property
    def icon_paths(self) -> Dict[type, Union[int, bytes]]:
        """ Returns a dictionary of the icon paths for each device type """
        return {
            lifxlan.Group: utils.resource_path("res/group.png"),
            lifxlan.Light: utils.resource_path("res/lightbulb.png"),
            lifxlan.MultiZoneLight: utils.resource_path("res/multizone.png"),
        }

    def draw_bulb_icon(self, bulb, label):
        """ Given a bulb and a name, add the icon to the end of the row. """
        # Make room on canvas
        self.scroll_x += self.settings.icon_width
        self.canvas.configure(scrollregion=(0, 0, self.scroll_x, self.scroll_y))
        # Build icon
        path = self.icon_path()
        sprite = tkinter.PhotoImage(file=path, master=self.master)
        image = self.canvas.create_image(
            (
                self.current_icon_width
                + self.settings.icon_width
                - self.settings.icon_padding,
                self.settings.icon_height / 2 + 2 * self.settings.icon_padding,
            ),
            image=sprite,
            anchor=tkinter.SE,
            tags=[label],
        )
        text = self.canvas.create_text(
            self.current_icon_width + self.settings.icon_padding / 2,
            self.settings.icon_height / 2 + 2 * self.settings.icon_padding,
            text=label[:8],
            anchor=tkinter.NW,
            tags=[label],
        )
        self.bulb_dict[label] = (sprite, image, text)
        self.update_icon(bulb)
        # update sizing info
        self.current_icon_width += self.settings.icon_width

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
        except TypeError:
            # First run will give us None; Is immediately corrected on next pass
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
                        (
                            v <= brightness_scale
                            or v == self.settings.color_code["BULB_TOP"]
                        )
                        for v in icon_rgb
                    )
                    and self.original_icon[x, y][3] == 255
                ):
                    bulb_color = (
                        bulb_color[0],
                        bulb_color[1],
                        bulb_color[2],
                        bulb_color[3],
                    )
                    color = utils.hsbk_to_rgb(bulb_color)
                elif (
                    all(
                        v
                        in (
                            self.settings.color_code["BACKGROUND"],
                            self.settings.highlight_saturation,
                        )
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
                    all(v == self.settings.color_code["BACKGROUND"] for v in icon_rgb)
                    and self.original_icon[x, y][3] == 255
                ):
                    color = (self.settings.highlight_saturation,) * 3
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
                    all(v == self.settings.highlight_saturation for v in icon_rgb)
                    and self.original_icon[x, y][3] == 255
                ):
                    color = (self.settings.color_code["BACKGROUND"],) * 3
                else:
                    color = icon_rgb
                color_string += utils.tuple2hex(color) + " "
            color_string += "} "
        sprite.put(color_string, (0, 0, sprite.height(), sprite.width()))
        self.canvas.itemconfig(image, image=sprite)
        self._current_icon = None
