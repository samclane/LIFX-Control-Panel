import unittest

import lifxlan

from test.dummy_devices import *
from utilities.multizone import (
    MAX_EXTENDED_ZONES,
    SetExtendedColorZones,
    set_zone_colors,
    supports_extended,
)
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


class TestMultiZone(unittest.TestCase):
    def test_paint_single_zone(self):
        # frames.LightFrame.paint_zone relies on set_zone_color(i, i) touching exactly one
        # zone: protocol SetColorZones end_index is inclusive
        bulb = MultiZoneDummy(label="Beam", num_zones=8)
        color = Color(1, 2, 3, 3500)
        bulb.set_zone_color(3, 3, color, rapid=True)
        zones = bulb.get_color_zones()
        self.assertEqual(zones[3], color)
        for i in (0, 1, 2, 4, 5, 6, 7):
            self.assertNotEqual(zones[i], color)

    def test_extended_sets_whole_strip_in_one_message(self):
        # The point of extended multizone: a 61-zone Beam costs one packet, not 61 -- more
        # than that and the device's ~20 msg/sec budget is blown and it stops responding.
        bulb = MultiZoneDummy(label="Beam", num_zones=61)
        wanted = [Color(index * 1000, 65535, 32768, 3500) for index in range(61)]
        set_zone_colors(bulb, wanted)
        self.assertEqual(bulb.get_color_zones(), [tuple(c) for c in wanted])
        self.assertEqual(bulb.acked_messages, [SetExtendedColorZones])

    def test_extended_payload_is_fixed_length(self):
        # Message 510 always carries all 82 color slots regardless of colors_count
        msg = SetExtendedColorZones(
            "d0:73:d5:40:c6:de",
            1234,
            0,
            {
                "duration": 0,
                "apply": 1,
                "zone_index": 0,
                "colors": [Color(1, 2, 3, 3500)],
            },
        )
        # duration(4) + apply(1) + zone_index(2) + colors_count(1) + 82 * HSBK(8)
        self.assertEqual(len(msg.payload), 8 + MAX_EXTENDED_ZONES * 8)
        self.assertEqual(msg.message_type, 510)

    def test_legacy_fallback_coalesces_runs(self):
        bulb = MultiZoneDummy(label="Old Z", num_zones=8, firmware=(2, 76))
        sends = []
        inner = bulb.set_zone_color
        bulb.set_zone_color = lambda *a, **kw: (sends.append(a[:2]), inner(*a, **kw))[1]
        red, blue = Color(0, 65535, 65535, 3500), Color(43690, 65535, 65535, 3500)
        wanted = [red] * 3 + [blue] * 5
        set_zone_colors(bulb, wanted)
        self.assertEqual(bulb.get_color_zones(), wanted)
        self.assertEqual(sends, [(0, 2), (3, 7)])  # one message per run, not per zone

    def test_legacy_verdict_is_cached(self):
        bulb = MultiZoneDummy(label="Old Z", num_zones=2, firmware=(2, 76))
        set_zone_colors(bulb, [Color(1, 2, 3, 3500)] * 2)
        self.assertFalse(bulb.supports_extended_multizone)
        # a second call must not pay the extended timeout again
        bulb.req_with_ack = lambda *a, **kw: self.fail(
            "retried extended after fallback"
        )
        set_zone_colors(bulb, [Color(4, 5, 6, 3500)] * 2)

    def test_busy_device_is_not_downgraded_to_legacy(self):
        # A capable Beam drops acks while its queue is backed up. Treating that as old
        # firmware would pin it to the legacy per-zone flood -- the thing that overloads it.
        bulb = MultiZoneDummy(label="Beam", num_zones=8)
        bulb.req_with_ack = lambda *a, **kw: (_ for _ in ()).throw(
            lifxlan.WorkflowException("busy")
        )
        with self.assertRaises(lifxlan.WorkflowException):
            set_zone_colors(bulb, [Color(1, 2, 3, 3500)] * 8)
        self.assertTrue(bulb.supports_extended_multizone)

    def test_attempts_budget_is_honored(self):
        # Measured on a real Beam: 2 attempts landed 9/14 commits, 6 attempts landed 14/14.
        bulb = MultiZoneDummy(label="Beam", num_zones=8)
        tries = []

        def flaky(*a, **kw):
            tries.append(1)
            raise lifxlan.WorkflowException("dropped")

        bulb.req_with_ack = flaky
        with self.assertRaises(lifxlan.WorkflowException):
            set_zone_colors(bulb, [Color(1, 2, 3, 3500)] * 8, attempts=6)
        self.assertEqual(len(tries), 6)

    def test_unanswered_firmware_query_is_not_cached(self):
        bulb = MultiZoneDummy(label="Beam", num_zones=8)
        bulb.req_with_resp = lambda *a, **kw: (_ for _ in ()).throw(
            lifxlan.WorkflowException("busy")
        )
        self.assertTrue(supports_extended(bulb))
        self.assertIsNone(getattr(bulb, "supports_extended_multizone", None))

    def test_legacy_retries_then_raises(self):
        bulb = MultiZoneDummy(label="Old Z", num_zones=2, firmware=(2, 76))
        attempts = []

        def flaky(start, end, color, duration=0, **kw):
            attempts.append(start)
            raise lifxlan.WorkflowException("no ack")

        bulb.set_zone_color = flaky
        with self.assertRaises(lifxlan.WorkflowException):
            set_zone_colors(bulb, [Color(1, 2, 3, 3500)] * 2)
        self.assertEqual(attempts, [0, 0])  # one run, tried twice


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
