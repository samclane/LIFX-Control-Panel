import os
import sys
import unittest

# color_thread uses package-relative imports, so make the repo root importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from lifx_control_panel.utilities.color_thread import (
    ColorCycle,
    ColorThreadRunner,
    _screen_rgb_to_hsbk,
    get_monitor_bounds,
    normalize_rectangles,
    config,
)
from lifx_control_panel.utilities.utils import Color


class TestNormalizeRectangles(unittest.TestCase):
    def test_shifts_origin_to_zero(self):
        rects = [(-1920, 0, 0, 1080), (0, 0, 1920, 1080)]
        self.assertEqual(
            normalize_rectangles(rects),
            [(0, 0, 1920, 1080), (1920, 0, 3840, 1080)],
        )

    def test_already_normalized_is_unchanged(self):
        rects = [(0, 0, 800, 600)]
        self.assertEqual(normalize_rectangles(rects), rects)


class TestGetMonitorBounds(unittest.TestCase):
    def test_uses_func_result_when_truthy(self):
        self.assertEqual(get_monitor_bounds(lambda: "[0, 0, 100, 100]"), "[0, 0, 100, 100]")


class TestScreenRgbToHsbk(unittest.TestCase):
    def test_near_black_noise_is_desaturated(self):
        # (1, 0, 1) would otherwise convert to fully-saturated magenta
        hsbk = _screen_rgb_to_hsbk((1, 0, 1), 3500)
        self.assertEqual(hsbk[1], 0)

    def test_real_colors_keep_saturation(self):
        hsbk = _screen_rgb_to_hsbk((255, 0, 0), 3500)
        self.assertEqual(hsbk[1], 65535)


class TestColorCycle(unittest.TestCase):
    def _tick(self, cycle):
        # Backdate the throttle so get_color advances immediately
        cycle.last_change = 0
        return cycle.get_color()

    def test_respects_brightness(self):
        cycle = ColorCycle()
        cycle.initial_color = Color(0, 65535, 0, 3500)
        hsbk = self._tick(cycle)
        self.assertEqual(hsbk[2], 0)  # zero input brightness stays dark

        cycle.initial_color = Color(0, 65535, 65535, 3500)
        hsbk = self._tick(cycle)
        self.assertEqual(hsbk[2], 65535)

    def test_hue_advances_and_wraps(self):
        cycle = ColorCycle()
        cycle.initial_color = Color(0, 65535, 65535, 3500)
        cycle.pos = 359
        self._tick(cycle)
        self.assertEqual(cycle.pos, 0)
        self._tick(cycle)
        self.assertEqual(cycle.pos, 1)

    def test_throttles_within_interval(self):
        cycle = ColorCycle()
        cycle.initial_color = Color(0, 65535, 65535, 3500)
        self._tick(cycle)
        pos = cycle.pos
        cycle.get_color()  # last_change is fresh, so no advance
        self.assertEqual(cycle.pos, pos)


class TestLimitBrightness(unittest.TestCase):
    def setUp(self):
        self._saved = dict(config["AverageColor"])

    def tearDown(self):
        config["AverageColor"].clear()
        config["AverageColor"].update(self._saved)

    def test_defaults_only_clamp_to_full_range(self):
        config["AverageColor"].pop("maxbrightness", None)
        config["AverageColor"].pop("minbrightnesscutoff", None)
        self.assertEqual(ColorThreadRunner.limit_brightness(70000), 65535)
        self.assertEqual(ColorThreadRunner.limit_brightness(100), 100)

    def test_max_caps_brightness(self):
        config["AverageColor"]["maxbrightness"] = "30000"
        self.assertEqual(ColorThreadRunner.limit_brightness(50000), 30000)

    def test_below_min_cutoff_snaps_to_zero(self):
        config["AverageColor"]["minbrightnesscutoff"] = "10000"
        self.assertEqual(ColorThreadRunner.limit_brightness(9999), 0)
        self.assertEqual(ColorThreadRunner.limit_brightness(10000), 10000)


if __name__ == "__main__":
    unittest.main()
