import unittest

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


if __name__ == "__main__":
    unittest.main()
