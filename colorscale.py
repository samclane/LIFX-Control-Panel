import tkinter as tk
from collections import namedtuple

from utils import tuple2hex, HueToRGB, KelvinToRGB

cRGB = namedtuple('cRGB', 'r g b')
cHBSK = namedtuple('cHBSK', 'h b s k')


class ColorScale(tk.Canvas):

    def __init__(self, parent, val=0, height=13, width=100, variable=None, from_=0, to=360, command=None,
                 gradient='hue', **kwargs):
        """
        Create a GradientBar.
        Keyword arguments:
            * parent: parent window
            * val: initially selected value
            * variable: IntVar linked to the alpha value
            * from_: The minimum value the slider can take on
            * to: The maximum value of the slider
            * command: A function callback, invoked every time the slider is moved
            * gradient: The type of background coloration
            * height, width, and any keyword argument accepted by a tkinter Canvas
        """
        tk.Canvas.__init__(self, parent, width=width, height=height, **kwargs)
        self.parent = parent
        self.max = to
        self.min = from_
        self.range = self.max - self.min
        self._variable = variable
        self.command = command
        self.color_grad = gradient
        self.xpad = 4
        if variable is not None:
            try:
                val = int(variable.get())
            except Exception as e:
                print(e)
        else:
            self._variable = tk.IntVar(self)
        val = max(min(self.max, val), self.min)
        self._variable.set(val)
        self._variable.trace("w", self._update_val)

        self.gradient = tk.PhotoImage(master=self, width=width - self.xpad, height=height)

        self.bind('<Configure>', lambda e: self._draw_gradient(val))
        self.bind('<ButtonPress-1>', self._on_click)
        self.bind('<B1-Motion>', self._on_move)

    def _draw_gradient(self, val):
        """Draw the gradient and put the cursor on val."""
        self.delete("gradient")
        self.delete("cursor")
        del self.gradient
        width = self.winfo_width() - self.xpad
        height = self.winfo_height()

        self.gradient = tk.PhotoImage(master=self, width=width, height=height)

        line = []

        if self.color_grad == 'bw':
            def f(i):
                line.append(tuple2hex((int(float(i) / width * 255),) * 3))
        elif self.color_grad == 'kelvin':
            def f(i):
                line.append(tuple2hex(KelvinToRGB(((float(i) / width) * self.range) + self.min)))
        else:  # self.color_grad == 'hue'
            def f(i):
                line.append(tuple2hex(HueToRGB(float(i) / width * 360)))

        for i in range(width):
            f(i)
        line = "{" + " ".join(line) + "}"
        self.gradient.put(" ".join([line for j in range(height)]))
        self.create_image(self.xpad, 0, anchor="nw", tags="gradient", image=self.gradient)
        self.lower("gradient")

        x = (val - self.min) / float(self.range) * width + self.xpad
        self.create_line(x, 0, x, height, width=4, fill='white', tags="cursor")
        self.create_line(x, 0, x, height, width=2, tags="cursor")

    def _on_click(self, event):
        """Move selection cursor on click."""
        x = event.x
        if x >= 0:
            width = self.winfo_width() - self.xpad
            for s in self.find_withtag("cursor"):
                self.coords(s, x, 0, x, self.winfo_height())
            self._variable.set(round((float(self.range) * x) / width + self.min, 2))
            if self.command is not None:
                self.command()

    def _on_move(self, event):
        """Make selection cursor follow the cursor."""
        if event.x >= 0:
            w = self.winfo_width() - self.xpad
            x = min(max(abs(event.x), 0), w)
            for s in self.find_withtag("cursor"):
                self.coords(s, x, 0, x, self.winfo_height())
            self._variable.set(round((float(self.range) * x) / w + self.min, 2))
            if self.command is not None:
                self.command()

    def _update_val(self, *args):
        val = int(self._variable.get())
        val = min(max(val, self.min), self.max)
        self.set(val)
        self.event_generate("<<HueChanged>>")

    def get(self):
        """Return val of color under cursor."""
        coords = self.coords('cursor')
        width = self.winfo_width() - self.xpad
        return round(self.range * coords[0] / width, 2)

    def set(self, val):
        """Set cursor position on the color corresponding to the value"""
        width = self.winfo_width() - self.xpad
        x = (val - self.min) / float(self.range) * width
        for s in self.find_withtag("cursor"):
            self.coords(s, x, 0, x, self.winfo_height())
        self._variable.set(val)
