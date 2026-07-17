import unittest
from utilities.utils import (
    Color,
    hsbk_to_rgb,
    hsv_to_rgb,
    kelvin_to_rgb,
    tuple2hex,
    str2list,
    str2tuple,
)


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

        c3 = c2._replace(hue=12345)
        self._cmp_color(c3, 12345, 65535, 65535, 9000)

        for i, v in enumerate(c3):
            self.assertEqual(v, c3[i])

    def test_conversion(self):
        c1 = Color(0, 0, 0, 0)
        rgb1 = hsbk_to_rgb(c1)
        self.assertEqual(rgb1, (0, 0, 0))

        hsv1 = hsv_to_rgb(*(0, 0, 0))
        self.assertEqual(hsv1, rgb1)

    def test_hsbk_to_rgb_hues(self):
        # Pure hues at full saturation/brightness, neutral kelvin
        self.assertEqual(hsbk_to_rgb(Color(0, 65535, 65535, 3500)), (255, 0, 0))
        self.assertEqual(hsbk_to_rgb(Color(21845, 65535, 65535, 3500)), (0, 255, 0))
        self.assertEqual(hsbk_to_rgb(Color(43690, 65535, 65535, 3500)), (0, 0, 255))

    def test_hsbk_to_rgb_brightness(self):
        # Half brightness halves the output
        self.assertEqual(hsbk_to_rgb(Color(0, 65535, 32768, 3500)), (127, 0, 0))

    def test_hsbk_to_rgb_desaturated(self):
        # Zero saturation falls through to the kelvin white point
        self.assertEqual(
            hsbk_to_rgb(Color(0, 0, 65535, 6500)), kelvin_to_rgb(6500)
        )

    def test_kelvin_to_rgb(self):
        # Known white points: warm is red-heavy, cool is blue-heavy
        self.assertEqual(kelvin_to_rgb(1500), (255, 108, 0))
        self.assertEqual(kelvin_to_rgb(3500), (255, 192, 140))
        self.assertEqual(kelvin_to_rgb(6500), (255, 254, 250))
        self.assertEqual(kelvin_to_rgb(9000), (209, 222, 255))
        # Every component stays in displayable range across the LIFX span
        for kelvin in range(1500, 9001, 500):
            for component in kelvin_to_rgb(kelvin):
                self.assertTrue(0 <= component <= 255, f"{kelvin}K -> {component}")

    def test_str_conversion(self):
        rgb1 = (1, 2, 3)
        self.assertEqual(tuple2hex(rgb1), "#010203")

        strlist_int = "[1, 2, 3]"
        self.assertEqual(str2list(strlist_int, int), [1, 2, 3])
        self.assertEqual(str2tuple(strlist_int, int), (1, 2, 3))


if __name__ == "__main__":
    unittest.main()
