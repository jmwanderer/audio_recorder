"""PyAudio Example: Record a few seconds of audio and save to a wave file."""

import wave
import sys
import pyaudio

RATE=8000
# Open the recording source
pa = pyaudio.PyAudio()
a_stream = pa.open(format=pyaudio.paInt16, channels=2, rate=RATE, input=True)

# Set up the wave file
wave_file = wave.open('output.wav', 'wb')
wave_file.setnchannels(2)
wave_file.setsampwidth(2)
wave_file.setframerate(RATE)

# Capture 5 seconds of sound
for _ in range(0, RATE // 1000 * 5):
    wave_file.writeframes(a_stream.read(1000))
wave_file.close()
a_stream.close()
pa.terminate()
