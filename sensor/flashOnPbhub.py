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

# flash is digital in on port 5
flashPort = (5,0)

# flash can be turned on and off via digital write
# short flashes can be done using rgb_set_brightness


while True:
    # pulse
    print("Flashing")
    pbhub_0.set_rgb_brightness(flashPort[0], 0)  # value doesn't matter
    time.sleep_ms(1300)


