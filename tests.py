""" This is not a standard test file (yet), but used to simulate a multi-device environment. """

import time
from random import randint, sample, randrange, choice

from gui import Color as DummyColor
from lifxlan import product_map
from helpers import resource_path

# Helpers
def randomMAC():
    return [0x00, 0x16, 0x3e,
            randint(0x00, 0x7f),
            randint(0x00, 0xff),
            randint(0x00, 0xff)]


def randomIP():
    return ".".join(map(str, (randint(0, 255) for _ in range(4))))


# Dummy classes
class DummyDevice:
    def __init__(self, label="No label"):
        self.label = label
        self.power = False
        self.mac_addr = randomMAC()
        self.ip_addr = randomIP()
        self.build_timestamp = 1521690429000000000
        self.version = 2.75
        self.wifi_signal_mw = 32.0
        self.wifi_tx_bytes = 0
        self.wifi_rx_bytes = 0
        self.wifi_build_timestamp = 0
        self.wifi_version = 0.0
        self.vendor = 1
        self.product = choice([int(key) for key in product_map.keys()])
        self.location_label = "My Home"
        self.location_tuple = sample(range(255), 16)
        self.location_updated_at = 1516997252637000000
        self.group_label = "Room 1"
        self.group_tuple = sample(range(255), 16)
        self.group_updated_at = 1516997252642000000
        self.is_light = True

        self._start_time = time.time()

    def set_label(self, val: str):
        self.label = val

    def set_power(self, val: bool, rapid: bool = False):
        self.power = val
        return self.get_power()

    def get_mac_address(self):
        return self.mac_addr

    def get_ip_addr(self):
        return self.ip_addr

    def get_service(self):
        return 1  # returns in, 1 = UDP

    def get_port(self):
        return 56700

    def get_label(self):
        return self.label

    def get_power(self):
        return self.power

    def get_host_firmware_tuple(self):
        return self.build_timestamp, self.version

    def get_host_firmware_build_timestamp(self):
        return self.build_timestamp

    def get_host_firmware_version(self):
        return self.version

    def get_wifi_info_tuple(self):
        return self.wifi_signal_mw, self.wifi_tx_bytes, self.wifi_rx_bytes

    def get_wifi_signal_mw(self):
        return self.wifi_signal_mw

    def get_wifi_tx_bytes(self):
        return self.wifi_tx_bytes

    def get_wifi_rx_bytes(self):
        return self.wifi_rx_bytes

    def get_wifi_firmware_tuple(self):
        return self.wifi_build_timestamp, self.wifi_version

    def get_wifi_firmware_build_timestamp(self):
        return self.wifi_build_timestamp

    def get_wifi_firmware_version(self):
        return self.wifi_version

    def get_version_tuple(self):
        return self.vendor, self.product, self.version

    def get_location(self):
        return self.location_label

    def get_location_tuple(self):
        return self.location_tuple, self.location_label, self.location_updated_at

    def get_location_label(self):
        return self.location_label

    def get_location_updated_at(self):
        return self.location_updated_at

    def get_group(self):
        return self.group_label

    def get_group_tuple(self):
        return self.group_tuple, self.group_label, self.group_updated_at

    def get_group_label(self):
        return self.group_label

    def get_group_updated_a(self):
        return self.group_updated_at

    def get_vendor(self):
        return self.vendor

    def get_product(self):
        return self.product

    def get_version(self):
        return self.version

    def get_info_tuple(self):
        return time.time(), self.get_uptime(), self.get_downtime()

    def get_time(self):
        return time.time()

    def get_uptime(self):
        return time.time() - self._start_time

    def get_downtime(self):  # no way to make this work. Shouldn't need it
        return 0

    def is_light(self):
        return True

    def supports_color(self):
        return True

    def supports_temperature(self):
        return True

    def supports_multizone(self):
        return True

    def supports_infrared(self):
        return True


class DummyBulb(DummyDevice):
    def __init__(self,
                 color=None,
                 label="N/A"):
        super().__init__(label)
        if color:
            self.color = color
        else:
            self.color = DummyColor(randrange(0, 65535), randrange(0, 65535), randrange(0, 65535),
                                    randrange(2500, 9000))
        self.power: int = 0

    # Official api

    def set_power(self, val: bool, duration: int = 0, rapid: bool = False):
        if duration:
            prev_power = self.power
            # Timer(duration, self.set_power, args=[prev_power, 0, rapid]).start()
        self.power = val

    def set_color(self, val: DummyColor, duration: int = 0, rapid: bool = False):
        if duration:
            prev_color = self.color
            # Timer(duration, self.set_color, args=[prev_color, 0, rapid]).start()
        self.color = val
        return self.get_color()

    def set_waveform(self, is_transient, color, period, cycles, duty_cycle, waveform):
        pass

    def get_power(self):
        return self.power

    def get_color(self):
        return self.color

    def get_infared(self):
        return self.infared_brightness

    def set_infared(self, val: int):
        self.infared_brightness = val

    def set_hue(self, hue, duration=0, rapid=False):
        if duration:
            prev_hue = self.color.hue
            # Timer(duration, self.set_hue, args=[prev_hue, 0, rapid]).start()
        self.color.hue = hue

    def set_brightness(self, brightness, duration=0, rapid=False):
        if duration:
            prev_brightness = self.color.brightness
            # Timer(duration, self.set_brightness, args=[prev_brightness, 0, rapid]).start()
        self.color.brightness = brightness

    def set_saturation(self, saturation, duration=0, rapid=False):
        if duration:
            prev_saturation = self.color.saturation
            # Timer(duration, self.set_saturation, args=[prev_saturation, 0, rapid]).start()
        self.color.saturation = saturation

    def set_colortemp(self, kelvin, duration=0, rapid=False):
        if duration:
            prev_kelvin = self.color.kelvin
            # Timer(duration, self.set_colortemp, args=[prev_kelvin, 0, rapid]).start()
        self.color.kelvin = kelvin


class MultiZoneDummy(DummyBulb):
    def __init__(self, color=DummyColor(0, 0, 0, 2500), label="N/A"):
        super().__init__(color, label)

    # Multizone API

    def get_color_zones(self, start=0, end=0):
        pass

    def set_zone_color(self, start, end, color, duration=0, rapid=False, apply=1):
        pass

    def set_zone_colors(self, colors, duration=0, rapid=False):
        pass


class TileDummy(DummyBulb):
    pass


class TileChainDummy(DummyBulb):
    def __init__(self, color=DummyColor(0, 0, 0, 2500), label="N/A", x=1, y=1):
        super().__init__(color, label)
        self.tiles = []
        self.cache = []
        self.x = x
        self.y = y

    def get_tile_info(self, refresh_cache=False):
        if refresh_cache:
            self.cache = self.tiles
            return self.tiles
        return self.cache

    def get_tile_count(self, refresh_cache=False):
        if refresh_cache:
            self.cache = self.tiles
            return len(self.tiles)
        return len(self.cache)

    def get_tile_colors(self, start_index, tile_count=0, x=0, y=0, width=0):
        return [tile.get_color() for tile in self.tiles[start_index:start_index + tile_count]]

    def set_tile_colors(self, start_index, colors, duration=0, tile_count=0, x=0, y=0, width=0, rapid=False):
        if duration:
            prev_colors = self.get_tile_colors(start_index, tile_count, x, y, width)
            # Timer(duration, self.set_tile_colors,
            # args=[start_index, prev_colors, 0, tile_count, x, y, width, rapid]).start()
        for index, tile in enumerate(self.tiles[start_index:start_index + tile_count]):
            tile.set_color(colors[index])

    def get_tilechain_colors(self):
        return [tile.get_color() for tile in self.tiles]

    def set_tilechain_colors(self, tilechain_colors, duration=0, rapid=False):
        if duration:
            prev_colors = self.get_tile_colors(0, len(self.tiles))
            # Timer(duration, self.set_tile_colors, args=[0, prev_colors, 0, len(self.tiles)]).start()
        for index, tile in enumerate(self.tiles):
            tile.set_color(tilechain_colors[index])

    def project_matrix(self, hsvk_matrix, duration, rapid):
        pass

    def get_canvas_dimensions(self, refresh_cache):
        return self.x, self.y

    def recenter_coordinates(self):
        pass

    def set_tile_coordinates(self, tile_index, x, y):
        pass

    def get_tile_map(self, refresh_cache):
        pass


class LifxLANDummy:
    def __init__(self, verbose=False):
        self.devices = {}

    # Non-offical api to manipulate for testing
    def add_dummy_light(self, light: DummyBulb):
        self.devices[light.get_label()] = light

    # Official api
    def get_lights(self):
        return tuple(light for light in self.devices.values())

    def get_color_lights(self):
        return tuple(light for light in self.devices.values() if light.supports_color())

    def get_infrared_lights(self):
        return tuple(light for light in self.devices.values() if light.supports_infrared())

    def get_multizone_lights(self):
        return tuple(light for light in self.devices.values() if light.supports_multizone())

    def get_tilechain_lights(self):
        return tuple(light for light in self.devices.values() if type(light) is TileChainDummy)

    def get_device_by_name(self, name):
        return self.devices[name]

    def get_devices_by_names(self, names):
        return Group(list(light for light in self.devices.values() if light.get_label() in names))

    def get_devices_by_group(self, group_id):
        return Group(list(light for light in self.devices.values() if light.get_group() == group_id))

    def get_devices_by_location(self, location: str):
        return Group(list(light for light in self.devices.values() if light.get_location() == location))

    def set_power_all_lights(self, power, duration=0, rapid=False):
        for light in self.devices:
            prev_power = light.power
            # Timer(duration, self.set_power_all_lights, args=[prev_power, 0, rapid]).start()
            light.set_power(power)

    def set_color_all_lights(self, color, duration=0, rapid=False):
        for light in self.devices:
            prev_color = light.color
            # Timer(duration, self.set_color_all_lights, args=[prev_color, 0, rapid]).start()
            light.set_color(color)

    def set_waveform_all_lights(self, is_transient, color, period, cycles, duty_cycle, wavform, rapid=False):
        for light in self.devices:
            light.set_waveform(is_transient, color, period, cycles, duty_cycle, wavform, rapid)

    def get_power_all_lights(self):
        return dict([((light, light.get_power()) for light in self.devices)])

    def get_color_all_lights(self):
        return dict([((light, light.get_color()) for light in self.devices)])


class Group:
    def __init__(self, devices: list, label: str = "N/A"):
        self.devices = devices
        self.label = label

    def add_device(self, device: DummyDevice):
        self.devices.append(device)

    def remove_device(self, device: DummyDevice):
        self.devices.remove(device)

    def remove_device_by_name(self, device_name: str):
        for index, device in enumerate(self.devices):
            if device.get_label() == device_name:
                del self.devices[index]
                break

    def get_device_list(self):
        return self.devices

    def set_power(self, power, duration=0, rapid=False):
        for device in self.devices:
            device.set_power(power, duration, rapid)

    def set_color(self, color, duration=0, rapid=False):
        for device in self.devices:
            device.set_color(color, duration, rapid)

    def set_hue(self, hue, duration, rapid=False):
        for device in self.devices:
            device.set_hue(hue, duration, rapid)

    def set_brightness(self, brightness, duration, rapid=False):
        for device in self.devices:
            device.set_hue(brightness, duration, rapid)

    def set_saturation(self, saturation, duration, rapid=False):
        for device in self.devices:
            device.set_hue(saturation, duration, rapid)

    def set_colortemp(self, kelvin, duration, rapid=False):
        for device in self.devices:
            device.set_hue(kelvin, duration, rapid)

    def set_infrared(self, infrared, duration, rapid=False):
        for device in self.devices:
            device.set_hue(infrared, duration, rapid)

    def set_zone_color(self, start, end, color, duration=0, rapid=False, apply=1):
        for device in self.devices[start:end]:
            device.set_color(color, duration, rapid)

    def set_zone_colors(self, colors, duration=0, rapid=False):
        for index, device in enumerate(self.devices):
            device.set_color(colors[index], duration, rapid)


if __name__ == "__main__":
    from lifxlan import LifxLAN
    from gui import LifxFrame
    from tkinter import *

    # Build mixed list of fake and real lights
    lifx = LifxLANDummy()
    lifx.add_dummy_light(DummyBulb(label="A Light"))
    lifx.add_dummy_light(DummyBulb(label="B Light"))
    lifx.add_dummy_light(TileChainDummy(label="C Tile"))
    lifx.add_dummy_light(DummyBulb(label="D Light"))
    lifx.add_dummy_light(DummyBulb(label="E Light"))
    lifx.add_dummy_light(DummyBulb(label="F Light"))
    lifx.add_dummy_light(DummyBulb(label="G Light"))
    for light in LifxLAN().get_lights():
        lifx.add_dummy_light(light)

    root = Tk()
    root.title("LIFX-Control-Panel")

    # Setup main_icon
    root.iconbitmap(resource_path('res//icon_vector_9fv_icon.ico'))

    mainframe = LifxFrame(root, lifx)

    # Setup exception logging
    logger = mainframe.logger


    def myHandler(type, value, tb):
        logger.exception("Uncaught exception: {}".format(str(value)))


    sys.excepthook = myHandler

    # Run main app
    root.mainloop()
