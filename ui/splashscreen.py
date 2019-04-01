# -*- coding: utf-8 -*-
"""Splash-screen class

Displays LIFX-Control-Panel's icon while GUI loads
"""
from tkinter import Toplevel, Canvas, PhotoImage


class Splash:
    """ From http://code.activestate.com/recipes/576936/ """

    def __init__(self, root, file):
        self.__root = root
        self.__file = file
        # Save the variables for later cleanup.
        self.__window = None
        self.__canvas = None
        self.__splash = None

    def __enter__(self):
        # Hide the root while it is built.
        self.__root.withdraw()
        # Create components of splash screen.
        window = Toplevel(self.__root)
        canvas = Canvas(window)
        splash = PhotoImage(master=window, file=self.__file)
        # Get the screen's width and height.
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        # Get the images's width and height.
        img_width = splash.width()
        img_height = splash.height()
        # Compute positioning for splash screen.
        xpos = (screen_width - img_width) // 2
        ypos = (screen_height - img_height) // 2
        # Configure the window showing the logo.
        window.overrideredirect(True)
        window.geometry('+{}+{}'.format(xpos, ypos))
        # Setup canvas on which image is drawn.
        canvas.configure(width=img_width, height=img_height, highlightthickness=0)
        canvas.grid()
        # Show the splash screen on the monitor.
        canvas.create_image(img_width // 2, img_height // 2, image=splash)
        window.update()
        # Save the variables for later cleanup.
        self.__window = window
        self.__canvas = canvas
        self.__splash = splash

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Free used resources in reverse order.
        del self.__splash
        self.__canvas.destroy()
        self.__window.destroy()
        # Give control back to the root program.
        self.__root.update_idletasks()
        self.__root.deiconify()
