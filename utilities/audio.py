import audioop

import pyaudio

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

try:
    # Find input device index
    info = p.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')
    input_device_index = None
    for i in range(0, numdevices):
        if "stereo mix" in p.get_device_info_by_host_api_device_index(0, i)['name'].lower():
            input_device_index = p.get_device_info_by_host_api_device_index(0, i)['index']
    if input_device_index is None:
        raise OSError("No stereo mix found")
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK,
                    input_device_index=input_device_index)
    initialized = True
except OSError:
    initialized = False


def get_music_color(initial_color):
    data = stream.read(CHUNK)
    frame_rms = audioop.rms(data, 2)
    level = min(frame_rms / (2.0 ** 16) * SCALE, 1.0)
    level = level ** EXPONENT
    level = int(level * 65535)
    print(level)
    return (initial_color[0], initial_color[1], level, initial_color[3])
