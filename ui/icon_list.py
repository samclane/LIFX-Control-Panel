import tkinter

import lifxlan
from PIL import Image as pImage

import utilities.utils


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
