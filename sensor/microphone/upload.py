import os, sys, io
import M5
from M5 import *
from unit import PDMUnit
import time
import network
import machine
import requests
import random
import binascii

try:
    import adpcm
    codec = True
except ImportError:
    print("ADPCM codec not found, using raw audio format.")
    codec = False   


# works with uiflow micropython 2.2.8 version https://github.com/m5stack/uiflow-micropython/releases/tag/2.2.8 
# make sure to flash from offset 0x0 , not 0x1000

# works. playback sample rate must be set to 11025*2. no idea why

M5.begin()

nic = network.WLAN(network.WLAN.IF_STA)
while not nic.active():
    print("Waiting for network interface to become active...")
    time.sleep(1)
nic.connect('karlsruhe.freifunk.net', '')
while not nic.isconnected():
    print("Waiting for network connection...")
    time.sleep(1)
       
print("Network connected:", nic.ifconfig()) 

url = "https://llama.ok-lab-karlsruhe.de/platane/php/audioRx.php"
payload = {}
#hdrs = {"Accept": "*/*","Accept-Language": "de,en-US;q=0.7,en;q=0.3","Accept-Encoding": "gzip, deflate, br, zstd","Content-Type": "application/json"}
hdrs = {
    "Accept": "application/json",
    "Accept-Language": "de,en-US;q=0.7,en;q=0.3",
    "Accept-Encoding": "identity",
    "Content-Type": "application/json"
}



M5.begin()

completed = False
savefile = False

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
    print(f"Encoded {l} bytes using ADPCM.")
    # adpcm_data = adpcm.encode(rec_data)
    if l == -1:
        print("ADPCM encoding failed, using raw format instead.")
        raise RuntimeError("ADPCM encoding failed")
    print(f"Encoded {len(rec_data)} bytes using ADPCM, result length: {len(adpcm_data)},{l}.")
    savename = f"recorded_audio_{2*SR}.adpcm"
    if savefile:
        with open(savename, "wb") as f:
            f.write(adpcm_data)  # Save encoded data to file
        print(f"Audio data saved to {savename}")
        # sox -t ima -r 8000 -c 1 recorded_audio_8000.adpcm recorded_audio.wav
        # sox recorded_audio.wav -c 2 -r 8000 -b 16 trimmed.wav trim 0.2
        # sox trimmed.wav -c 2 -r 8000 -b 16 decoded.pcm.wav gain -n
        # play decoded.pcm.wav
else:
    print(f"Recorded {len(rec_data)} bytes in raw format.")
    savename = f"recorded_audio_{2*SR}.raw"
    # Save raw audio data directly
    if savefile:
        with open(savename, "wb") as f:
            f.write(rec_data)  # Save recorded data to file
    print(f"Audio data saved to {savename}")

# Prepare data for upload
print("Preparing data for upload...")
print(("Uploading to:", url ))

filename_bytes = bytearray([random.randint(41, 90) for _ in range(16)])
filename = f"{filename_bytes.hex()}_{SR*2}"
# Ensure filename is valid UTF-8 (hex is always valid)
payload["codec"] = "adpcm" if codec else "raw"
payload["filename"] = f"adpcm_{filename}" if codec else f"raw_{filename}"
payload["sample_rate"] = SR
payload["sample_size"] = len(rec_data) if not codec else len(adpcm_data)
print(f"Payload: {payload}")
payload["audio"] = binascii.b2a_base64(adpcm_data).decode('utf-8') if codec else binascii.b2a_base64(rec_data[:SR*16]).decode('utf-8')
r = requests.post(url,headers=hdrs,json=payload)

# Check response status
try:
    print("Raw response content (hex):", r.content.hex())
    print("Response headers:", r.headers)
    if r.status_code == 200:
        print("Upload successful")
        try:
            print("Response (JSON):", r.json())
        except Exception as json_err:
            print("Failed to decode JSON:", json_err)
            print("Response (text):", r.text)
    else:
        print("Upload failed:", r.status_code)
        print("Response (text):", r.text)
except Exception as e:
    print("Error processing response:", e)
    print("Response (hex):", r.content.hex())
    print("Response (text):", r.text)
    
    
# Usage example:
# i2s = init_i2s_mic()
# buf = bytearray(1024)
# num_bytes = i2s.readinto(buf)
