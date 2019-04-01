# -*- coding: utf-8 -*-
"""Keyboard shortcut interface

Contains single class for interfacing with user IO and binding to functions
"""

import logging

from PyHook3 import HookManager
from PyHook3.HookManager import HookConstants


class KeybindManager:
    """ Interface with Mouse/Keyboard and register functions to keyboard shortcuts. """

    def __init__(self, master, sticky=False):
        self.logger = logging.getLogger(master.logger.name + '.Keystroke_Watcher')
        self.hook_manager = HookManager()
        self.hook_manager.KeyDown = self._on_key_down
        self.hook_manager.KeyUp = self._on_key_up
        self.function_map = {}
        self.keys_held = set()
        self.sticky = sticky
        self.hook_manager.HookKeyboard()

    def get_key_combo_code(self):
        """ Converts the keys currently being held into a string representing the combination """
        return '+'.join([HookConstants.IDToName(key) for key in self.keys_held])

    def register_function(self, key_combo, function):
        """ Register function callback to key_combo """
        self.function_map[key_combo.lower()] = function
        self.logger.info(
            "Registered function <%s> to keycombo <%s>.", function.__name__, key_combo.lower())

    def unregister_function(self, key_combo):
        """ Stop tracking function at key_combo """
        self.logger.info(
            "Unregistered function <%s> at keycombo <%s>", self.function_map[key_combo.lower()].__name__,
            key_combo.lower())
        del self.function_map[key_combo.lower()]

    def _on_key_down(self, event):
        """ Simply adds the key to keys held. """
        try:
            self.keys_held.add(event.KeyID)
        except Exception as exc:
            # Log error but don't do anything; PyHook is prone to throw some exceptions with no consequences
            self.logger.error("Error in _on_key_down, %s", exc)
        return True

    def _on_key_up(self, event):
        """ If a function for the given key_combo is found, call it """
        key_combo = self.get_key_combo_code().lower()
        try:
            if key_combo in self.function_map.keys():
                self.logger.info(
                    "Shortcut <%s> pressed. Calling function <%s>.", key_combo,
                    self.function_map[key_combo].__name__)
                self.function_map[key_combo]()
        finally:
            if not self.sticky and event.KeyID in self.keys_held:
                self.keys_held.remove(event.KeyID)
        return True

    def shutdown(self):
        """ Stop following keyboard events. """
        self.hook_manager.UnhookKeyboard()

    def restart(self):
        """ Clear keys held and rehook keyboard. """
        self.keys_held = set()
        self.hook_manager.HookKeyboard()
