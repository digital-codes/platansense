import os, sys, io
import M5
from M5 import *
from unit import PDMUnit
import time

# works with uiflow micropython 2.2.8 version https://github.com/m5stack/uiflow-micropython/releases/tag/2.2.8 
# make sure to flash from offset 0x0 , not 0x1000

# works. playback sample rate must be set to 11025*2. no idea why

M5.begin()

completed = False

try:
    import adpcm
    codec = True
except ImportError:
    print("ADPCM codec not found, using raw audio format.")
    codec = False   

# Define pins
PIN_CLK = 6 # Atom S3r on pbhub port c
PIN_DATA = 5 # Atom S3r on pbhub port c

SR = 4000 # * 44100 // 4
BS = SR * 4 * 10 # 44100 * 10  # Buffer size for recording

print("Sample rate:", SR)

# pin_data_in=port[1],
# pin_ws=port[0]

pdm_0 = PDMUnit((PIN_CLK,PIN_DATA), i2s_port=0, sample_rate=SR)
print("PDMUnit initialized.")
pdm_0.begin()
M5.update()
time.sleep(1)
M5.update()
rec_data = bytearray(BS)
def recording():
    global completed
    global rec_data
    print("Recording...")
    pdm_0.record(rec_data, SR, False)
    print(pdm_0.isRecording())
    time.sleep_ms(150)
    print(pdm_0.isRecording())
    while pdm_0.isRecording():
        #print(".")
        time.sleep_ms(100)
    print("Recording finished.")
    completed = True
    pdm_0.end()

recording()
M5.update()
while not completed:
    M5.update()


print("Recording done, saving data...")
# num_bytes = i2s.readinto(rec_data)  # Read data into buffer

# print(f"Read {num_bytes} bytes from I2S microphone.")
if codec:
    # Encode the recorded data using ADPCM
    adpcm_data = bytearray(len(rec_data) // 4)
    l = adpcm.encode_into(rec_data, adpcm_data)
    print(f"Encoded {len(rec_data)} bytes using ADPCM, result length: {len(adpcm_data)},{l}.")
    with open(f"recorded_audio_{2*SR}.adpcm", "wb") as f:
        f.write(adpcm_data)  # Save encoded data to file
    # sox -t ima -r 8000 -c 1 recorded_audio_8000.adpcm recorded_audio.wav
    # sox recorded_audio.wav -c 2 -r 8000 -b 16 trimmed.wav trim 0.2
    # sox trimmed.wav -c 2 -r 8000 -b 16 decoded.pcm.wav gain -n
    # play decoded.pcm.wav
else:
    print(f"Recorded {len(rec_data)} bytes in raw format.")
    # Save raw audio data directly  
    with open("recorded_audio.raw", "wb") as f:
        f.write(rec_data)  # Save recorded data to file

# Usage example:
# i2s = init_i2s_mic()
# buf = bytearray(1024)
# num_bytes = i2s.readinto(buf)
