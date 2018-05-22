from pyHook import HookManager
from pyHook.HookManager import HookConstants
from win32gui import PumpMessages, PostQuitMessage
import logging


class Keystroke_Watcher:
    def __init__(self, master):
        self.hm = HookManager()
        self.hm.KeyDown = self.on_key_down
        self.hm.KeyUp = self.on_key_up
        self.hm.HookKeyboard()
        self.logger = logging.getLogger(master.logger.name + '.Keystroke_Watcher')
        self.function_map = {}

        self.keys_held = set()

    def register_function(self, key_combo, function):
        self.function_map[key_combo] = function

    def on_key_down(self, event):
        try:
            self.keys_held.add(event.KeyID)
        finally:
            return True

    def get_key_combo_code(self):
        return '+'.join([HookConstants.IDToName(key) for key in self.keys_held])

    def on_key_up(self, event):
        keycombo = self.get_key_combo_code()
        # print(keycombo)
        try:
            if keycombo in self.function_map.keys():
                self.logger.info(
                    "Shortcut {} pressed. Calling function {}.".format(keycombo, self.function_map[keycombo].__name__))
                self.function_map[keycombo]()
        finally:
            self.keys_held.remove(event.KeyID)
            return True

    def shutdown(self):
        PostQuitMessage(0)
        self.hm.UnhookKeyboard()
