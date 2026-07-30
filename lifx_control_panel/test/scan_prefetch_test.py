"""Covers the round-trip-saving shortcuts scan_for_lights relies on."""

import logging
import unittest

import lifxlan

from lifx_control_panel.__main__ import LifxFrame
from lifx_control_panel.frames import _cached, _cached_color
from lifx_control_panel.utilities.utils import Color
from test.dummy_devices import DummyBulb, MultiZoneDummy


class Stub:
    """Just enough of LifxFrame for the unbound _prefetch_state call."""

    logger = logging.getLogger("scan_prefetch_test")


class FlakyBulb(DummyBulb):
    def get_color(self):
        raise lifxlan.WorkflowException("no reply")


class PrefetchTest(unittest.TestCase):
    def test_returns_group_label(self):
        bulb = DummyBulb(label="Kitchen")
        self.assertEqual(
            LifxFrame._prefetch_state(Stub(), bulb), bulb.get_group_label()
        )

    def test_multizone_takes_the_split_path(self):
        # get_color() reads back black on a strip, so the prefetch must not use it
        strip = MultiZoneDummy(label="Beam")
        self.assertEqual(
            LifxFrame._prefetch_state(Stub(), strip), strip.get_group_label()
        )

    def test_unreachable_device_reports_no_group(self):
        with self.assertLogs(Stub.logger, "WARNING") as logs:  # also keeps it off stderr
            self.assertIsNone(LifxFrame._prefetch_state(Stub(), FlakyBulb(label="Gone")))
        self.assertEqual(len(logs.records), 3)  # SCAN_ATTEMPTS


class CachedTest(unittest.TestCase):
    def test_prefers_cached_value(self):
        self.assertEqual(_cached(DummyBulb(label="Lamp"), "label", self.fail), "Lamp")

    def test_zero_power_is_not_treated_as_missing(self):
        bulb = DummyBulb(label="Lamp")
        bulb.power_level = 0
        self.assertEqual(_cached(bulb, "power_level", self.fail), 0)

    def test_falls_back_when_absent_or_unset(self):
        bulb = DummyBulb(label="Lamp")
        bulb.color = None  # prefetch failed for this device
        self.assertEqual(_cached(bulb, "color", lambda: "fetched"), "fetched")
        # attribute lifxlan has but the dummies don't
        self.assertEqual(_cached(bulb, "product_features", lambda: "fetched"), "fetched")


class CachedColorTest(unittest.TestCase):
    def test_plain_bulb_uses_the_cache(self):
        bulb = DummyBulb(label="Lamp")
        bulb.get_color = self.fail
        self.assertEqual(_cached_color(bulb), Color(*bulb.color))

    def test_strip_never_uses_its_zone_list(self):
        # get_color_zones() overwrites .color with every zone; Color(*that) would blow up
        strip = MultiZoneDummy(label="Beam", num_zones=61)
        single = Color(1, 2, 3, 4)
        strip.color = strip.get_color_zones()  # as lifxlan leaves it
        strip.get_color = lambda: single  # real strips still answer LightGet with one color
        self.assertEqual(_cached_color(strip), single)


if __name__ == "__main__":
    unittest.main()
