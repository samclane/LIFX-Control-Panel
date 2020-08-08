# -*- coding: utf-8 -*-
"""Audio Processing Tools

Tools for real-time audio processing and color-following. For co-use with color_threads.py

Notes
-----
    Not really complete yet; still need to integrate with other screen averaging functions.
"""
import audioop
from collections import deque
from math import ceil
from tkinter import messagebox

import pyaudio

# Audio processing constants
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 2
RATE = 44100

# RMS -> Brightness control constants
SCALE = 8  # Change if too dim/bright
EXPONENT = 2  # Change if too little/too much difference between loud and quiet sounds
N_POINTS = 15  # Length of sliding average window for smoothing


class AudioInterface:
    """ Instantiate a connection to audio device (selected in Settings). Also provides a color-following function for
     music intensity. """

    def __init__(self):
        self.interface = pyaudio.PyAudio()
        self.num_devices = 0
        self.stream = None
        self.initialized = False
        self.window = deque([0] * N_POINTS)

    def init_audio(self, config):
        """ Attempt to make a connection to the audio device given in config.ini or Stereo Mix. Will attempt
         to automatically find a Stereo Mix """
        if self.initialized:
            self.interface.close(self.stream)
            self.num_devices = 0
        try:
            # Find input device index
            info = self.interface.get_host_api_info_by_index(0)
            self.num_devices = info.get("deviceCount")
            # If a setting is found, use it. Otherwise try and find Stereo Mix
            if config.has_option("Audio", "InputIndex"):
                input_device_index = int(config["Audio"]["InputIndex"])
            else:
                input_device_index = self.get_stereo_mix_index()
                config["Audio"]["InputIndex"] = str(input_device_index)
                with open("config.ini", "w") as cfg:
                    config.write(cfg)
            if input_device_index is None:
                raise OSError("No Input channel found. Disabling Sound Integration.")
            self.stream = self.interface.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK,
                input_device_index=input_device_index,
            )
            self.initialized = True
        except (ValueError, OSError) as exc:
            if self.initialized:  # only show error if main app has already started
                messagebox.showerror("Invalid Sound Input", exc)
            self.initialized = False

    def get_stereo_mix_index(self):
        """ Naively get stereo mix, as it's probably the best input """
        device_index = None
        for i in range(0, self.num_devices):
            if (
                "stereo mix"
                in self.interface.get_device_info_by_host_api_device_index(0, i)[
                    "name"
                ].lower()
            ):
                device_index = self.interface.get_device_info_by_host_api_device_index(
                    0, i
                )["index"]
        return device_index

    def get_device_names(self):
        """ Get names of all audio devices"""
        devices = {}
        for i in range(0, self.num_devices):
            info = self.interface.get_device_info_by_host_api_device_index(0, i)
            devices[info["index"]] = info["name"]
        return devices

    def get_music_color(self, initial_color, alpha=0.99):
        """ Calculate the RMS power of the waveform, and return that as the initial_color with the calculated brightness
        """
        data = self.stream.read(CHUNK)
        frame_rms = audioop.rms(data, 2)
        level = min(frame_rms / (2.0 ** 16) * SCALE, 1.0)
        level = level ** EXPONENT
        level = int(level * 65535)
        self.window.rotate(1)  # FILO Queue
        # window = deque([a*x for x in window])  # exp decay
        self.window[0] = level
        brightness = ceil(sum(self.window) / N_POINTS)
        return initial_color[0], initial_color[1], brightness, initial_color[3]
