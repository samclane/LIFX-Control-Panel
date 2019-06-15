# -*- coding: utf-8 -*-
import concurrent.futures
import queue
import threading

import lifxlan


class AsyncBulbInterface(threading.Thread):
    """ Asynchronous networking layer between LIFX devices and the GUI. """

    def __init__(self, event, heartbeat_ms):
        threading.Thread.__init__(self)

        self.stopped = event

        self.hb_rate = heartbeat_ms

        self.device_list = []
        self.color_queue = {}
        self.color_cache = {}
        self.power_queue = {}
        self.power_cache = {}

    def set_device_list(self, device_list):
        """ Set internet device list to passed list of LIFX devices. """
        self.device_list = device_list
        for dev in device_list:
            self.color_queue[dev.get_label()] = queue.Queue()
            self.color_cache[dev.label] = dev.color
            self.power_queue[dev.label] = queue.Queue()
            self.power_cache[dev.label] = dev.power_level

    def query_device(self, target):
        """ Check if target has new state. If it does, push it to the queue and cache the value. """
        try:
            pwr = target.get_power()
            if pwr != self.power_cache[target.label]:
                self.power_queue[target.label].put(pwr)
                self.power_cache[target.label] = pwr
            clr = target.get_color()
            if clr != self.color_cache[target.label]:
                self.color_queue[target.label].put(clr)
                self.color_cache[target.label] = clr
        except lifxlan.WorkflowException:
            pass

    def run(self):
        """ Continuous loop that has a thread query each device every HEARTBEAT ms. """
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.device_list)) as executor:
            while not self.stopped.wait(self.hb_rate / 1000):
                executor.map(self.query_device, self.device_list)
