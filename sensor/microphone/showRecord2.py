import numpy as np
import wave
from scipy.signal import detrend

import matplotlib.pyplot as plt


# Parameters (adjust if needed)
channels = 1
sample_width = 2  # bytes (16-bit PCM)
sample_rate = 11025*2  # Hz

# Read raw I2S data
with open('recorded_audio.raw', 'rb') as f:
    raw_data = f.read()

# Convert raw bytes to numpy array
audio = np.frombuffer(raw_data, dtype=np.int16)

# Save as WAV
with wave.open('record.wav', 'wb') as wf:
    wf.setnchannels(channels)
    wf.setsampwidth(sample_width)
    wf.setframerate(sample_rate)
    wf.writeframes(audio.tobytes())

# Plot waveform
plt.figure(figsize=(10, 4))
plt.plot(audio)
plt.title('Audio Waveform')
plt.xlabel('Sample')
plt.ylabel('Amplitude')
plt.tight_layout()
plt.savefig('waveform.png')
plt.show()


