import ast
import unittest

from test.dummy_devices import DummyBulb, DummyColor, MultiZoneDummy


class TestSavedStateRoundTrip(unittest.TestCase):
    """ Round-trips the SavedState serialization format used by LifxFrame.save_state/restore_state. """

    @staticmethod
    def _serialize(power, color):
        return f"{power};{color}"

    @staticmethod
    def _deserialize(state):
        power, color = state.split(";", 1)
        return int(power), ast.literal_eval(color)

    def test_round_trip(self):
        bulb = DummyBulb(color=DummyColor(100, 200, 300, 3500), label="Desk")
        bulb.set_power(65535)
        state = self._serialize(bulb.get_power(), tuple(bulb.get_color()))

        power, color = self._deserialize(state)
        restored = DummyBulb(label="Desk")
        restored.set_color(color)
        restored.set_power(power)

        self.assertEqual(tuple(restored.get_color()), (100, 200, 300, 3500))
        self.assertEqual(restored.get_power(), 65535)

    def test_multizone_round_trip(self):
        bulb = MultiZoneDummy(label="Beam", num_zones=4)
        zones = [DummyColor(i * 1000, 65535, 32768, 3500) for i in range(4)]
        bulb.set_zone_colors(zones)
        bulb.set_power(65535)
        state = self._serialize(bulb.get_power(), [tuple(z) for z in bulb.get_color_zones()])

        power, color = self._deserialize(state)
        self.assertIsInstance(color, list)
        restored = MultiZoneDummy(label="Beam", num_zones=4)
        restored.set_zone_colors(color)
        restored.set_power(power)

        self.assertEqual([tuple(z) for z in restored.get_color_zones()],
                         [tuple(z) for z in zones])
        self.assertEqual(restored.get_power(), 65535)


if __name__ == "__main__":
    unittest.main()
