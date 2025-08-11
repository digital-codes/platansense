import M5
import sys
import time
import machine 

import adpcm

# MAX98357A/
# I2S and Left Justified Mode
# The MAX98357A follows standard I2S timing by allowing
# a delay of one BCLK cycle after the LRCLK transition
# before the beginning of a new data word (Figure 6 and
# Figure 7). The MAX98357B follows the left justified timing
# specification by aligning the LRCLK transitions with the
# beginning of a new data word (Figure 8 and Figure 9).
# LRCLK ONLY supports 8kHz, 16kHz, 32kHz, 44.1kHz,
# 48kHz, 88.2kHz, and 96kHz frequencies. LRCLK clocks
# at 11.025kHz, 12kHz, 22.05kHz and 24kHz are NOT
# supported. Do not remove LRCLK while BLCK is pres-
# ent. Removing LRCLK while BCLK is present can cause
# unexpected output behavior, including a large DC output
# voltage.
#
# TDM Mode
# TDM mode is automatically detected by monitoring the
# short channel sync pulse on LRCLK. The frequency
# detector circuit detects the bit depth. In TDM mode,
# the MAX98357A/MAX98357B has a fixed gain of 12dB.
#
# Drive SD_MODE high to select the left word of the stereo
# input data.


M5.begin()
M5.update()
time.sleep(1)

# https://uiflow-micropython.readthedocs.io/en/master/hardware/speaker.html#class-speaker
# stop MIC when using spkr
M5.Mic.end()
M5.Speaker.end()
M5.update()

directGrove = False  # True for direct Grove connection, False for PBHub

if directGrove:
    sdo = 1
    bck = 2
    ws = 5 
else: # pbhub
    sdo = 8  # black, PB
    bck = 7  # black, PA
    ws = 39  # red, PA

i2s_port = 1
sr = 16000 # 44100  # do not use 22050  or 11025
# deinit
machine.I2S(i2s_port,sck=bck,sd=sdo,ws=ws,mode=1,bits=16,format=0,rate=sr,ibuf=0).deinit()

wavFile = "output_16k_loud.wav"

CHUNK_SIZE = 4096

spk = M5.createSpeaker()
spk.config(
    pin_data_out=sdo,
    pin_bck=bck,
    pin_ws=ws,
    sample_rate=sr,
    stereo=False,
    magnification=1,  # 16 is quire loud. normally us 1 or 2
    dma_buf_len=CHUNK_SIZE,
    dma_buf_count=8,
    task_priority=2,
    task_pinned_core=255,
    i2s_port=i2s_port,
)
M5.update()

print("Speaker configured", spk)
# why ?
#M5.Speaker.end()
M5.update()


if not spk.begin():
    print("Failed to start speaker")
    sys.exit()
    
spk.setVolume(250)  # Set volume to 250
print("Speaker started + initialized, volume set to ", spk.getVolume())



with open(wavFile, "rb") as f:
    wav = f.read()
print("WAV file loaded, size:", len(wav))

shift = 0

queued = False

loops = 0

while True:
    M5.update()
    with open(wavFile, "rb") as f:
        f.read(44)  # Skip WAV header
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                while spk.isPlaying():
                    M5.update()
                    time.sleep_ms(10)  # allow other tasks to run
                break

            chunk  = bytearray(chunk)
            encoded = adpcm.encode(chunk)
            print(f"encoded size: {len(encoded)}")
            # Write chunk, handling partial writes if necessary
            if shift != 0:
                machine.I2S.shift(buf=chunk,bits=16,shift=shift)
            written = 0
            while written < len(chunk):
                spk.playRaw(chunk,sr,False,1,-1) 
                print(".", end="")
                written += len(chunk)
                while spk.isPlaying():
                    M5.update()
                    time.sleep_ms(10)  # allow other tasks to run
                    print(",", end="")
                    pass
                
        print("Playing WAV file done")
        time.sleep(2)
        loops += 1
        if loops > 2:
            break

print("Playing  done")

spk.end()
M5.Speaker.end()
M5.update()
print("Speaker ended")  

i2s = machine.I2S(i2s_port,sck=bck, sd=sdo, ws=ws, mode=machine.I2S.TX, bits=16, format=machine.I2S.MONO, rate=sr, ibuf=0).deinit()  # Clean up I2S
