import sys
import time

from machine import I2S
from machine import Pin
from machine import I2C
import math
import struct

from es8311 import ES8311

# more info:
# https://components.espressif.com/components/espressif/esp_codec_dev/versions/1.5.4/readme
#https://github.com/espressif/esp-adf/blob/fcce23e3d5ecf7ba75ce9f4e3761489dc9e0299e/components/esp_codec_dev/test_apps/codec_dev_test/main/my_codec.c

# Using esp32s3r
# din:5, lrclk: 6, dout:7, sclk:8
# scl: 39, sda: 38

# ESP32
sck_pin = Pin(8)   # Serial clock output
ws_pin = Pin(6)    # Word clock output
sdo_pin = Pin(7)    # Serial data output
sdi_pin = Pin(5)    # Serial data input

scl_pin = Pin(39)  # I2C clock
sda_pin = Pin(38)  # I2C data

sr = 16000 # 44100  # do not use 22050  or 11025
# deinit


# configure codec ES8311 (i2c control interface)
# adapt pins & I2C bus to your board
i2c = I2C(0, scl=scl_pin, sda=sda_pin, freq=400000)

codec = ES8311(i2c)
codec.debug = True

codec.reset()
codec.init_default(bits=16, fmt="i2s", slave=True)
codec.start(adc=False, dac=True)   # playback only

codec.set_volume(100)
codec.mute(False)

# ... now drive I2S peripheral of the MCU for audio playback
time.sleep(1)



i2s_port = 0
sr = 16000 # 44100 # 16000 # 44100  # do not use 22050  or 11025

CHUNK_SIZE = 4096

# deinit        
I2S(i2s_port,sck=sck_pin,sd=sdo_pin,ws=ws_pin,mode=1,bits=16,format=0,rate=sr,ibuf=0).deinit()
# init 
audio_out = I2S(i2s_port,
                sck=sck_pin, ws=ws_pin, sd=sdo_pin,
                mode=I2S.TX,
                bits=16,
                format=I2S.MONO,
                rate=sr ,
                ibuf=8*CHUNK_SIZE  # Bigger buffer helps smooth out timing issues
                )

print("I2S configured", audio_out)

#wavFile = "/media/click.wav"
wavFile = "/media/test8000.wav"
shift = 0
loop = 2
while True:
    with open(wavFile, "rb") as f:
        f.read(44)  # Skip WAV header
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break

            chunk  = bytearray(chunk)
            #print(f"Read chunk of size: {len(chunk)}, {len(buf) // 2} samples")
            print(f"Writing chunk of size: {len(chunk)}")
            # Write chunk, handling partial writes if necessary
            if shift != 0:
                audio_out.shift(buf=chunk,bits=16,shift=shift)
            written = 0
            while written < len(chunk):
                n = audio_out.write(chunk[written:])
                written += n
    loop -= 1
    time.sleep(1)    
    if loop <= 0:
        break


    
#num_written = audio_out.write(buf) # blocks until buf emptied
#print("Wrote", num_written, "bytes to I2S")

codec.stop()
audio_out.deinit()
codec.reset()   
print("Done")
