import audioop
import pyaudio
from tkinter import messagebox

# Audio processing constants
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 2
RATE = 44100

# RMS -> Brightness control constants
SCALE = 15  # Change if too dim/bright
EXPONENT = 2  # Change if too little/too much difference between loud and quiet sounds

# Init stream on module load
p = pyaudio.PyAudio()

numdevices = 0
stream = None
initialized = False


def get_stereo_mix_index():
    """ Naively get stereo mix, as it's probably the best input """
    device_index = None
    for i in range(0, numdevices):
        if "stereo mix" in p.get_device_info_by_host_api_device_index(0, i)['name'].lower():
            device_index = p.get_device_info_by_host_api_device_index(0, i)['index']
    return device_index


def get_names():
    ret_dict = {}
    for i in range(0, numdevices):
        info = p.get_device_info_by_host_api_device_index(0, i)
        ret_dict[info["index"]] = info["name"]
    return ret_dict


def init(config, logger=None):
    global numdevices, stream, initialized
    if initialized:
        p.close(stream)
        numdevices = 0
    try:
        # Find input device index
        info = p.get_host_api_info_by_index(0)
        numdevices = info.get('deviceCount')
        if config.has_option("Audio", "InputIndex"):
            input_device_index = int(config["Audio"]["InputIndex"])
        else:
            input_device_index = get_stereo_mix_index()
            config["Audio"]["InputIndex"] = str(input_device_index)
            with open('config.ini', 'w') as cfg:
                config.write(cfg)
        if input_device_index is None:
            raise OSError("No Input channel found. Disabling Sound Integration.")
        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK,
                        input_device_index=input_device_index)
        initialized = True
    except (ValueError, OSError) as e:
        if initialized:  # only show error if main app has already started
            messagebox.showerror("Invalid Sound Input", e)
        initialized = False


def get_music_color(initial_color):
    data = stream.read(CHUNK)
    frame_rms = audioop.rms(data, 2)
    level = min(frame_rms / (2.0 ** 16) * SCALE, 1.0)
    level = level ** EXPONENT
    level = int(level * 65535)
    return initial_color[0], initial_color[1], level, initial_color[3]
