import tkinter as tk

from utils import tuple2hex, HueToRGB, KelvinToRGB


class ColorScale(tk.Canvas):

    def __init__(self, parent, val=0, height=13, width=100, variable=None, from_=0, to=360, command=None,
                 gradient='hue', **kwargs):
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

        self.gradient = tk.PhotoImage(master=self, width=width, height=height)

        self.bind('<Configure>', lambda e: self._draw_gradient(val))
        self.bind('<ButtonPress-1>', self._on_click)
        self.bind('<ButtonRelease-1>', self._on_release)
        self.bind('<B1-Motion>', self._on_move)

    def _draw_gradient(self, val):
        """Draw the gradient and put the cursor on val."""
        self.delete("gradient")
        self.delete("cursor")
        del self.gradient
        width = self.winfo_width()
        height = self.winfo_height()

        self.gradient = tk.PhotoImage(master=self, width=width, height=height)

        line = []

        if self.color_grad == 'bw':
            def f(i):
                line.append(tuple2hex((int(float(i) / width * 255),) * 3))
        elif self.color_grad == 'wb':
            def f(i):
                line.append(tuple2hex((int((1 - (float(i) / width)) * 255),) * 3))
        elif self.color_grad == 'kelvin':
            def f(i):
                line.append(tuple2hex(KelvinToRGB(((float(i) / width) * self.range) + self.min)))
        elif self.color_grad == 'hue':
            def f(i):
                line.append(tuple2hex(HueToRGB(float(i) / width * 360)))
        else:
            raise ValueError("gradient value {} not recognized".format(self.color_grad))

        for i in range(width):
            f(i)
        line = "{" + " ".join(line) + "}"
        self.gradient.put(" ".join([line for j in range(height)]))
        self.create_image(0, 0, anchor="nw", tags="gradient", image=self.gradient)
        self.lower("gradient")

        x = (val - self.min) / float(self.range) * width
        self.create_line(x, 0, x, height, width=4, fill='white', tags="cursor")
        self.create_line(x, 0, x, height, width=2, tags="cursor")

    def _on_click(self, event):
        """Move selection cursor on click."""
        x = event.x
        if x >= 0:
            width = self.winfo_width()
            for s in self.find_withtag("cursor"):
                self.coords(s, x, 0, x, self.winfo_height())
            self._variable.set(round((float(self.range) * x) / width + self.min, 2))
            if self.command is not None:
                self.command()

    def _on_move(self, event):
        """Make selection cursor follow the cursor."""
        if event.x >= 0:
            w = self.winfo_width()
            x = min(max(abs(event.x), 0), w)
            for s in self.find_withtag("cursor"):
                self.coords(s, x, 0, x, self.winfo_height())
            self._variable.set(round((float(self.range) * x) / w + self.min, 2))
            if self.command is not None:
                self.command()

    def _on_release(self, event):
        """ Tell the master BulbIconList to update immediately after value is changed. """
        self.master.master.update_icons()

    def _update_val(self, *args):
        val = int(self._variable.get())
        val = min(max(val, self.min), self.max)
        self.set(val)
        self.event_generate("<<HueChanged>>")

    def get(self):
        """Return val of color under cursor."""
        coords = self.coords('cursor')
        width = self.winfo_width()
        return round(self.range * coords[0] / width, 2)

    def set(self, val):
        """Set cursor position on the color corresponding to the value"""
        width = self.winfo_width()
        x = (val - self.min) / float(self.range) * width
        for s in self.find_withtag("cursor"):
            self.coords(s, x, 0, x, self.winfo_height())
        self._variable.set(val)
