import os, sys, io
import time
from machine import I2S, Pin

# works with uiflow micropython 2.2.8 version https://github.com/m5stack/uiflow-micropython/releases/tag/2.2.8 
# make sure to flash from offset 0x0 , not 0x1000

# works. playback sample rate must be set to 11025*2. no idea why


bck = 1 
sdi = 2 
i2s_port = 0
sr = 22050 # 44100 
bs = sr * 10 * 2

rec_buf = bytearray(bs)  # Buffer for recording

audioFile = "record.wav"

# deinit
try:
    I2S(i2s_port, sck=bck, sd=sdi, ws=0, mode=I2S.RX, bits=16, format=I2S.MONO, rate=sr, ibuf=0).deinit()
except Exception as e:
    print(f"Error deinitializing I2S: {e}. Continuing...")

time.sleep(1)

# Set up I2S for input
i2s = I2S(
    i2s_port,
    sck=Pin(bck),
    ws=Pin(bck),
    sd=Pin(sdi),
    mode=I2S.RX,
    bits=16,
    format=I2S.MONO,
    rate=sr,
    ibuf=8*4096  # Bigger buffer helps smooth out timing issues
)


print("Recording audio...")
num_bytes = i2s.readinto(rec_buf)  # Read data into buffer
print(f"Recorded {num_bytes} bytes.")
print("Recording done, saving data...")

# print(f"Read {num_bytes} bytes from I2S microphone.")
with open(audioFile, "wb") as f:
    f.write(rec_buf)  # Save recorded data to file

# Usage example:
# i2s = init_i2s_mic()
# buf = bytearray(1024)
# num_bytes = i2s.readinto(buf)
