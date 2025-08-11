#import unit
import time
import M5
#from M5 import *
from unit import PBHUBUnit

M5.begin()

from machine import I2C, Pin

pbhub_addr = 0x61  # Default address for PBHUB
pbhub_scl = Pin(1)  # SCL pin for I2C
pbhub_sda = Pin(2)  # SDA pin for I2C
pbhub_i2c = I2C(0, scl=pbhub_scl, sda=pbhub_sda, freq=400000)
pbhub_0 = PBHUBUnit(pbhub_i2c,pbhub_addr)

# pir is digital in on port 0, pin probably 0
pirPort = (0,1)

while True:
    pir_detected = pbhub_0.digital_read(pirPort[0], pirPort[1]) # true if triggered
    print('PIR Status:', pir_detected)
    time.sleep_ms(300)
    continue

