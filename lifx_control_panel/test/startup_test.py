import os
import tempfile
import unittest

from utilities import utils


class StartupShortcutTest(unittest.TestCase):
    def test_set_get_roundtrip(self):
        original = utils.STARTUP_LNK
        with tempfile.TemporaryDirectory() as tmp:
            utils.STARTUP_LNK = os.path.join(tmp, "LIFX-Control-Panel.lnk")
            try:
                self.assertFalse(utils.get_launch_on_startup())
                utils.set_launch_on_startup(True)
                self.assertTrue(utils.get_launch_on_startup())
                utils.set_launch_on_startup(False)
                self.assertFalse(utils.get_launch_on_startup())
                utils.set_launch_on_startup(False)  # idempotent
            finally:
                utils.STARTUP_LNK = original


if __name__ == "__main__":
    unittest.main()
