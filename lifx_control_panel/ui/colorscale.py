import logging
import tkinter as tk
from typing import List

from ..utilities.utils import tuple2hex, hsv_to_rgb, kelvin_to_rgb


class ColorScale(tk.Canvas):
    """
    A canvas that displays a color scale.
    """

    def __init__(
        self,
        parent,
        val=0,
        height=13,
        width=100,
        variable=None,
        from_=0,
        to=360,
        command=None,
        gradient="hue",
        **kwargs,
    ):
        """
        Create a ColorScale.
        Keyword arguments:
            * parent: parent window
            * val: initially selected value
            * height: canvas length in y direction
            * width: canvas length in x direction
            * variable: IntVar linked to the alpha value
            * from_: The minimum value the slider can take on
            * to: The maximum value of the slider
            * command: A function callback, invoked every time the slider is moved
            * gradient: The type of background coloration
            * **kwargs: Any other keyword argument accepted by a tkinter Canvas
        """
        tk.Canvas.__init__(self, parent, width=width, height=height, **kwargs)
        self.parent = parent
        self.max = to
        self.min = from_
        self.range = self.max - self.min
        self._variable = variable
        self.command = command
        self.color_grad = gradient
        self.logger = logging.getLogger(self.parent.__class__.__name__ + ".ColorScale")
        if variable is not None:
            try:
                val = int(variable.get())
            except Exception as e:
                self.logger.exception(e)
        else:
            self._variable = tk.IntVar(self)
        val = max(min(self.max, val), self.min)
        self._variable.set(val)
        self._variable.trace("w", self._update_val)

        self.gradient = tk.PhotoImage(master=self, width=int(width), height=int(height))

        self.bind("<Configure>", lambda _: self._draw_gradient(val))
        self.bind("<ButtonPress-1>", self._on_click)
        # self.bind('<ButtonRelease-1>', self._on_release)
        self.bind("<B1-Motion>", self._on_move)

    def _draw_gradient(self, val):
        """Draw the gradient and put the cursor on val."""
        self.delete("gradient")
        self.delete("cursor")
        del self.gradient
        width = self.winfo_width()
        height = self.winfo_height()

        self.gradient = tk.PhotoImage(master=self, width=width, height=height)

        line: List[str] = []

        def gradfunc(x_coord):
            return line.append(tuple2hex((0, 0, 0)))

        if self.color_grad == "bw":

            def gradfunc(x_coord):
                line.append(tuple2hex((int(float(x_coord) / width * 255),) * 3))

        elif self.color_grad == "wb":

            def gradfunc(x_coord):
                line.append(tuple2hex((int((1 - (float(x_coord) / width)) * 255),) * 3))

        elif self.color_grad == "kelvin":

            def gradfunc(x_coord):
                line.append(
                    tuple2hex(
                        kelvin_to_rgb(
                            int(((float(x_coord) / width) * self.range) + self.min)
                        )
                    )
                )

        elif self.color_grad == "hue":

            def gradfunc(x_coord):
                line.append(tuple2hex(hsv_to_rgb(float(x_coord) / width * 360)))

        else:
            raise ValueError(f"gradient value {self.color_grad} not recognized")

        for x_coord in range(width):
            gradfunc(x_coord)
        line: str = "{" + " ".join(line) + "}"
        self.gradient.put(" ".join([line for _ in range(height)]))
        self.create_image(0, 0, anchor="nw", tags="gradient", image=self.gradient)
        self.lower("gradient")

        x_start: float = self.min
        try:
            x_start = (val - self.min) / float(self.range) * width
        except ZeroDivisionError:
            x_start = self.min
        self.create_line(
            x_start, 0, x_start, height, width=4, fill="white", tags="cursor"
        )
        self.create_line(x_start, 0, x_start, height, width=2, tags="cursor")

    def _on_click(self, event):
        """Move selection cursor on click."""
        x_coord = event.x
        if x_coord >= 0:
            width = self.winfo_width()
            self.update_slider_value(width, x_coord)

    def update_slider_value(self, width, x_coord):
        """Update the slider value based on slider x coordinate."""
        height = self.winfo_height()
        for x_start in self.find_withtag("cursor"):
            self.coords(x_start, x_coord, 0, x_coord, height)
        self._variable.set(round((float(self.range) * x_coord) / width + self.min, 2))
        if self.command is not None:
            self.command()

    def _on_move(self, event):
        """Make selection cursor follow the cursor."""
        x_coord = event.x
        if x_coord >= 0:
            width = self.winfo_width()
            x_coord = min(max(abs(x_coord), 0), width)
            self.update_slider_value(width, x_coord)

    def _update_val(self, *_):
        val = int(self._variable.get())
        val = min(max(val, self.min), self.max)
        self.set(val)
        self.event_generate("<<HueChanged>>")

    def get(self):
        """Return val of color under cursor."""
        coords = self.coords("cursor")
        width = self.winfo_width()
        return round(self.range * coords[0] / width, 2)

    def set(self, val):
        """Set cursor position on the color corresponding to the value"""
        width = self.winfo_width()
        try:
            x_coord = (val - self.min) / float(self.range) * width
        except ZeroDivisionError:
            return
        for x_start in self.find_withtag("cursor"):
            self.coords(x_start, x_coord, 0, x_coord, self.winfo_height())
        self._variable.set(val)
