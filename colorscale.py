from collections import namedtuple
from utils import tuple2hex, HueToRGB
import tkinter as tk

cRGB = namedtuple('cRGB', 'r g b')
cHBSK = namedtuple('cHBSK', 'h b s k')


class ColorScale(tk.Canvas):

    def __init__(self, parent, hue=0, height=13, width=100, variable=None, to=360, command=None, **kwargs):
        """
        Create a GradientBar.
        Keyword arguments:
            * parent: parent window
            * hue: initially selected hue value
            * variable: IntVar linked to the alpha value
            * height, width, and any keyword argument accepted by a tkinter Canvas
        """
        tk.Canvas.__init__(self, parent, width=width, height=height, **kwargs)
        self.parent = parent
        self.max = to
        self._variable = variable
        self.command = command
        if variable is not None:
            try:
                hue = int(variable.get())
            except Exception as e:
                print(e)
        else:
            self._variable = tk.IntVar(self)
        hue = max(min(self.max, hue), 0)
        self._variable.set(hue)
        self._variable.trace("w", self._update_hue)

        self.gradient = tk.PhotoImage(master=self, width=width, height=height)

        self.bind('<Configure>', lambda e: self._draw_gradient(hue))
        self.bind('<ButtonPress-1>', self._on_click)
        self.bind('<B1-Motion>', self._on_move)

    def _draw_gradient(self, hue):
        """Draw the gradient and put the cursor on hue."""
        self.delete("gradient")
        self.delete("cursor")
        del self.gradient
        width = self.winfo_width()
        height = self.winfo_height()

        self.gradient = tk.PhotoImage(master=self, width=width, height=height)

        line = []
        for i in range(width):
            line.append(tuple2hex(HueToRGB(float(i) / width * 360)))
        line = "{" + " ".join(line) + "}"
        self.gradient.put(" ".join([line for j in range(height)]))
        self.create_image(0, 0, anchor="nw", tags="gradient", image=self.gradient)
        self.lower("gradient")

        x = hue / float(self.max) * width
        self.create_line(x, 0, x, height, width=4, tags="cursor")

    def _on_click(self, event):
        """Move selection cursor on click."""
        x = event.x
        self.coords('cursor', x, 0, x, self.winfo_height())
        self._variable.set(round((float(self.max) * x) / self.winfo_width(), 2))
        if self.command is not None:
            self.command()


    def _on_move(self, event):
        """Make selection cursor follow the cursor."""
        w = self.winfo_width()
        x = min(max(abs(event.x), 0), w)
        self.coords('cursor', x, 0, x, self.winfo_height())
        self._variable.set(round((float(self.max) * x) / w, 2))
        if self.command is not None:
            self.command()


    def _update_hue(self, *args):
        hue = int(self._variable.get())
        hue = min(max(hue, 0), self.max)
        self.set(hue)
        self.event_generate("<<HueChanged>>")

    def get(self):
        """Return hue of color under cursor."""
        coords = self.coords('cursor')
        return round(self.max * coords[0] / self.winfo_width(), 2)

    def set(self, hue):
        """Set cursor position on the color corresponding to the hue value"""
        x = hue / float(self.max) * self.winfo_width()
        self.coords('cursor', x, 0, x, self.winfo_height())
        self._variable.set(hue)

    def grid_remove(self):
        self.unbind('<Configure>')
        self.unbind('<ButtonPress-1>')
        self.unbind('<B1-Motion>')
        for t in self._variable.trace_vinfo():
            self._variable.trace_vdelete(*t)
        super().grid_remove()
