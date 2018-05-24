from pyHook import HookManager
from pyHook.HookManager import HookConstants
import logging
import inspect

class Keystroke_Watcher:
    def __init__(self, master, sticky=False):
        self.hm = HookManager()
        self.hm.KeyDown = self.on_key_down
        self.hm.KeyUp = self.on_key_up
        self.hm.HookKeyboard()
        self.logger = logging.getLogger(master.logger.name + '.Keystroke_Watcher')
        self.function_map = {}
        self.sticky = sticky

        self.keys_held = set()

    def register_function(self, key_combo, function):
        self.function_map[key_combo.lower()] = function
        self.logger.info(
            "Registered function <{}> to keycombo <{}>.".format(inspect.getsource(function).strip(), key_combo.lower()))

    def on_key_down(self, event):
        try:
            self.keys_held.add(event.KeyID)
        finally:
            return True

    def get_key_combo_code(self):
        return '+'.join([HookConstants.IDToName(key) for key in self.keys_held])

    def on_key_up(self, event):
        keycombo = self.get_key_combo_code().lower()
        print(keycombo)
        try:
            if keycombo in self.function_map.keys():
                self.logger.info(
                    "Shortcut <{}> pressed. Calling function <{}>.".format(keycombo, inspect.getsource(
                        self.function_map[keycombo]).strip()))
                self.function_map[keycombo]()
        finally:
            if not self.sticky:
                self.keys_held.remove(event.KeyID)
            return True

    def shutdown(self):
        self.hm.UnhookKeyboard()

    def restart(self):
        self.keys_held = set()
        self.hm.HookKeyboard()
