import M5
import sys
import time
import machine 
import adpcm

buf = bytearray(1000000)
with open("test_8000.adpcm", "rb") as f:
    raw = f.read()
w = adpcm.decode_into(raw, buf)

print("Decoded ADPCM data into buffer, size:", w)

M5.begin()
M5.update()
time.sleep(1)

directGrove = False  # True for direct Grove connection, False for PBHub

if directGrove:
    sdo = 1
    bck = 2
    ws = 5 
else:  # pbhub
    sdo = 8  # black, PB
    bck = 7  # black, PA
    ws = 39  # red, PA

i2s_port = 1
sr = 8000
CHUNK_SIZE = 4096

LOOP = True

# deinit
machine.I2S(i2s_port, sck=bck, sd=sdo, ws=ws, mode=1, bits=16, format=0, rate=sr, ibuf=0).deinit()

spk = M5.createSpeaker()
spk.config(
    pin_data_out=sdo,
    pin_bck=bck,
    pin_ws=ws,
    sample_rate=sr,
    stereo=False,
    magnification=8,  # 16 is quite loud. normally use 1 or 2
    dma_buf_len=CHUNK_SIZE,
    dma_buf_count=8,
    task_priority=2,
    task_pinned_core=255,
    i2s_port=i2s_port,
)
M5.update()
print("Speaker configured", spk)
spk.setVolume(255)  # Set volume to 255
print("Speaker started + initialized, volume set to ", spk.getVolume())

while True:
    spk.playRaw(buf[:w], sr)

    while spk.isPlaying():
        M5.update()
        time.sleep_ms(10)  # allow other tasks to run   
    time.sleep(2)

    if not LOOP:
        break

print("Playback finished.")
time.sleep(1)
machine.I2S(i2s_port, sck=bck, sd=sdo, ws=ws, mode=1, bits=16, format=0, rate=sr, ibuf=0).deinit()
time.sleep(1)

