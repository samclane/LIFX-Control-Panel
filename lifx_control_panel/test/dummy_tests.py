import unittest

from test.dummy_devices import *
from utilities.utils import Color


class TestLAN(unittest.TestCase):
    def setUp(self):
        self.lifx = LifxLANDummy()
        self.light_labels = ["Bedroom Lamp", "Patio-Lights", "Andy's Room"]

    def test_add_lights(self):
        for label in self.light_labels:
            self.lifx.add_dummy_light(DummyBulb(label=label))
        for label in self.light_labels:
            self.assertIn(label, self.lifx.devices.keys())

    def test_set_color_all_lights(self):
        color = Color(1, 2, 3, 3501)
        self.lifx.set_color_all_lights(color)
        for device in self.lifx.get_devices_by_names(self.light_labels).devices:
            self.assertEqual(color, device.get_color())

    def test_set_power_all_lights(self):
        power = 1
        self.lifx.set_power_all_lights(power)
        for device in self.lifx.get_devices_by_names(self.light_labels).devices:
            self.assertEqual(power, device.get_power())


class TestDevice(unittest.TestCase):
    def setUp(self):
        self.device = DummyDevice("TestDevice")

    def test_set_label(self):
        current = self.device.get_label()
        label = "TestDevice"
        self.device.set_label(label)
        self.assertEqual(label, self.device.get_label())
        self.device.set_label(current)
        self.assertEqual(current, self.device.get_label())


class TestBulb(unittest.TestCase):
    def setUp(self):
        self.bulb = DummyBulb(label="TestBulb")

    def test_set_label(self):
        current = self.bulb.get_label()
        label = "TestBulb"
        self.bulb.set_label(label)
        self.assertEqual(label, self.bulb.get_label())
        self.bulb.set_label(current)
        self.assertEqual(current, self.bulb.get_label())

    def test_power_duration(self):
        self.skipTest("DummyDevice duration not implemented")
        self.bulb.set_power(False)
        self.assertEqual(self.bulb.get_power(), False, "Bulb init off")
        duration = 3
        self.bulb.set_power(True, duration)
        self.assertEqual(self.bulb.get_power(), True, "Duration on")
        time.sleep(duration + 1)
        self.assertEqual(self.bulb.get_power(), False, "Reset to off")

    def test_color_duration(self):
        self.skipTest("DummyDevice duration not implemented")
        color_a = Color(1, 2, 3, 3501)
        color_b = Color(4, 5, 6, 6311)
        self.bulb.set_color(color_a)
        self.assertEqual(self.bulb.get_color(), color_a, "bulb init color")
        duration = 2
        self.bulb.set_color(color_b, duration)
        self.assertEqual(self.bulb.get_color(), color_b, "bulb change color")
        time.sleep(duration + 1)
        self.assertEqual(self.bulb.get_color(), color_a, "bulb reset color")


if __name__ == "__main__":
    unittest.main()
