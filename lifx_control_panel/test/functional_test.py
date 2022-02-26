import unittest
from lifx_control_panel.utilities.utils import (
    hsbk_to_rgb,
    hsv_to_rgb,
    tuple2hex,
    str2list,
    str2tuple,
)

from utilities.utils import Color


class TestFunctions(unittest.TestCase):
    def setUp(self):
        pass

    def _cmp_color(self, c, h, s, b, k):
        self.assertEqual(c.hue, h)
        self.assertEqual(c.saturation, s)
        self.assertEqual(c.brightness, b)
        self.assertEqual(c.kelvin, k)

    def test_color(self):
        c1 = Color(0, 0, 0, 0)
        self._cmp_color(c1, 0, 0, 0, 0)
        for v in c1:
            self.assertEqual(v, 0)

        c2 = Color(65535, 65535, 65535, 9000)
        self._cmp_color(c2, 65535, 65535, 65535, 9000)

        c3 = c1 + c2
        self._cmp_color(c3, 65535, 65535, 65535, 9000)

        self.assertEqual(c3 - c2, c1)

        self.assertEqual(str(c1), "[0, 0, 0, 0]")

        c3[0] = 12345
        self._cmp_color(c3, 12345, 65535, 65535, 9000)

        for i, v in enumerate(c3):
            self.assertEqual(v, c3[i])

    def test_conversion(self):
        c1 = Color(0, 0, 0, 0)
        rgb1 = hsbk_to_rgb(c1)
        self.assertEqual(rgb1, (0, 0, 0))

        hsv1 = hsv_to_rgb(*(0, 0, 0))
        self.assertEqual(hsv1, rgb1)

    def test_str_conversion(self):
        rgb1 = (1, 2, 3)
        self.assertEqual(tuple2hex(rgb1), "#010203")

        strlist_int = "[1, 2, 3]"
        self.assertEqual(str2list(strlist_int, int), [1, 2, 3])
        self.assertEqual(str2tuple(strlist_int, int), (1, 2, 3))


if __name__ == "__main__":
    unittest.main()
