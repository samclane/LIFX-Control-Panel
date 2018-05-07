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
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK,
                    input_device_index=2)
    initialized = True
except OSError:
    initialized = False


def get_music_color(initial_color):
    data = stream.read(CHUNK)
    frame_rms = audioop.rms(data, 2)
    level = min(frame_rms / (2.0 ** 16) * SCALE, 1.0)
    level = level ** EXPONENT
    level = int(level * 65535)
    return (initial_color[0], initial_color[1], level, initial_color[3])
