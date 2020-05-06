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
        for dev in device_list:
            self.color_queue[dev.get_label()] = queue.Queue()
            if dev.supports_multizone():
                # Convert "device" to a MultiZoneLight object
                # Should be a nicer way to convert objects
                _label = dev.get_label()
                dev = lifxlan.MultiZoneLight(dev.get_mac_addr(),
                                             dev.get_ip_addr(),
                                             dev.get_service(),
                                             dev.get_port())
                dev.label = _label
                color = dev.get_color_zones()[0]
            else:
                color = dev.color
            self.color_cache[dev.label] = color
            self.power_queue[dev.label] = queue.Queue()
            self.power_cache[dev.label] = dev.power_level or dev.get_power()

            self.device_list.append(dev)

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
