import pyaudio
import audioop

# Audio processing constants
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 2
RATE = 44100

# RMS -> Brightness control constants
SCALE = 100
EXPONENT = 2

# Init stream on module load
p = pyaudio.PyAudio()

stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK,
                input_device_index=2)


def get_music_color(initial_color):
    data = stream.read(CHUNK)
    frame_rms = audioop.rms(data, 2)
    level = min(frame_rms / (2.0 ** 16) * SCALE, 1.0)
    level = level ** EXPONENT
    level = int(level * 65535)
    return (initial_color[0], initial_color[1], level, initial_color[3])
