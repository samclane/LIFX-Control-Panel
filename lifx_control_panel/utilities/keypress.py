# -*- coding: utf-8 -*-
"""Keyboard shortcut interface

Contains single class for interfacing with user IO and binding to functions
"""

import logging

import keyboard


class KeybindManager:
    """ Interface with Mouse/Keyboard and register functions to keyboard shortcuts. """

    def __init__(self, master, sticky=False):
        self.logger = logging.getLogger(master.logger.name + ".Keystroke_Watcher")
        self.keys_held = set()
        self.sticky = sticky
        self.hooks = {}
        keyboard.on_press(lambda e: self.keys_held.add(e.name))
        keyboard.on_release(lambda e: self.keys_held.discard(e.name))

    @property
    def key_combo_code(self) -> str:
        """ Converts the keys currently being held into a string representing the combination """
        return "+".join(self.keys_held)

    def register_function(self, key_combo, function):
        """ Register function callback to key_combo """
        cb = keyboard.add_hotkey(key_combo, function)
        self.hooks[key_combo] = cb
        self.logger.info(
            "Registered function <%s> to keycombo <%s>.",
            function.__name__,
            key_combo.lower(),
        )

    def unregister_function(self, key_combo):
        """ Stop tracking function at key_combo """
        keyboard.remove_hotkey(key_combo)
        self.logger.info(
            "Unregistered function at keycombo <%s>", key_combo.lower(),
        )

    def _on_key_down(self, event: keyboard.KeyboardEvent):
        """ Simply adds the key to keys held. """
        try:
            self.keys_held.add(event.name)
        except Exception as exc:
            self.logger.error("Error in _on_key_down, %s", exc)
        return True

    def _on_key_up(self, event: keyboard.KeyboardEvent):
        """ If a function for the given key_combo is found, call it """
        if not self.sticky and event.name in self.keys_held:
            self.keys_held.discard(event.name)

    def shutdown(self):
        """ Stop following keyboard events. """
        keyboard.unhook_all()

    def restart(self):
        """ Clear keys held and rehook keyboard. """
        self.keys_held = set()
        for keycombo, cb in self.hooks.items():
            keyboard.register_hotkey(keycombo, cb)
