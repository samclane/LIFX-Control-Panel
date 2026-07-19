import unittest

from test.dummy_devices import DummyBulb, DummyColor
from utilities.utils import str2tuple


class TestSavedStateRoundTrip(unittest.TestCase):
    """ Round-trips the SavedState serialization format used by LifxFrame.save_state/restore_state. """

    def test_round_trip(self):
        bulb = DummyBulb(color=DummyColor(100, 200, 300, 3500), label="Desk")
        bulb.set_power(65535)
        state = f"{bulb.get_power()};{tuple(bulb.get_color())}"

        restored = DummyBulb(label="Desk")
        power, color = state.split(";")
        restored.set_color(str2tuple(color, int))
        restored.set_power(int(power))

        self.assertEqual(tuple(restored.get_color()), (100, 200, 300, 3500))
        self.assertEqual(restored.get_power(), 65535)


if __name__ == "__main__":
    unittest.main()
