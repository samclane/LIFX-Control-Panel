"""End-to-end zone painting through a real LightFrame, driven by synthetic mouse events."""

import logging
import tkinter
import unittest
from tkinter import ttk

from lifx_control_panel import frames
from test.dummy_devices import MultiZoneDummy

NUM_ZONES = 61  # a LIFX Beam
RED, GREEN, BLUE = 0, 21845, 43690


class FakeMaster(ttk.Frame):
    """The handful of attributes LightFrame reaches back into its master for."""

    def __init__(self, root):
        super().__init__(root)
        self.logger = logging.getLogger("root")
        self.audio_interface = type(
            "A", (), {"initialized": False, "get_music_color": lambda *a: None}
        )()
        self.bulb_interface = type("B", (), {"power_queue": {}, "color_queue": {}})()


class TestZonePainting(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tkinter.Tk()
        except tkinter.TclError as exc:  # no display (headless CI)
            self.skipTest(f"Tk unavailable: {exc}")
        logging.disable(logging.CRITICAL)
        self.addCleanup(logging.disable, logging.NOTSET)
        self.addCleanup(self.root.destroy)
        master = FakeMaster(self.root)
        master.pack()
        self.bulb = MultiZoneDummy(label="Beam", num_zones=NUM_ZONES)
        self.bulb.get_product_features = lambda: {
            "min_kelvin": 1500,
            "max_kelvin": 9000,
        }
        self.frame = frames.LightFrame(master, self.bulb)
        self.root.update()

    def pick_color(self, hue):
        """Drag the hue slider, the way a user chooses the next color to paint with."""
        self.frame.hsbk[0].set(hue)
        self.frame.hsbk[1].set(65535)
        self.frame.hsbk[2].set(40000)
        self.frame.update_color_from_ui()
        self.root.update()

    def stroke(self, zone_from, zone_to):
        canvas, width = self.frame.zone_canvas, self.frame.zone_width
        canvas.event_generate("<Button-1>", x=int(zone_from * width) + 2, y=5)
        self.root.update()
        for zone in range(zone_from, zone_to + 1):
            canvas.event_generate("<B1-Motion>", x=int(zone * width) + 2, y=5)
            self.root.update()
        canvas.event_generate("<ButtonRelease-1>", x=int(zone_to * width) + 2, y=5)
        self.root.update()
        self.root.after(300, self.root.quit)
        self.root.mainloop()  # commit_paint runs on a worker thread

    def test_each_stroke_adds_a_color(self):
        """Regression: choosing a color on the sliders used to push it to the whole strip
        and reset zone_colors, so every stroke painted the color the strip had just
        become and nothing ever appeared to change."""
        for hue, (start, end) in zip((RED, GREEN, BLUE), ((0, 9), (20, 29), (40, 49))):
            self.pick_color(hue)
            self.assertEqual(
                len(set(self.bulb.get_color_zones()[start : end + 1])),
                1,
                "picking a color must not repaint the strip on its own",
            )
            self.stroke(start, end)
            painted = self.bulb.get_color_zones()[start : end + 1]
            self.assertEqual(
                [color[0] for color in painted],  # zones come back as plain HSBK tuples
                [hue] * len(painted),
                f"stroke with hue {hue} did not reach the bulb",
            )
        # background + the three stroke colors
        self.assertEqual(len(set(self.bulb.get_color_zones())), 4)


if __name__ == "__main__":
    unittest.main()
