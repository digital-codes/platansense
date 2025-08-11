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

# rgb is digital in on port 0, pin probably 0
rgbPort = (5,0)

pbhub_0.set_rgb_led_num(rgbPort[0],8) # true if triggered

while True:
    for i in range(8):
        pbhub_0.set_rgb_color_pos(rgbPort[0], i, 0x101000)  # Set each LED to green
        time.sleep_ms(100)  
        pbhub_0.set_rgb_color_pos(rgbPort[0], i, 0x000000)  # Turn off the first LED
        time.sleep_ms(300)  

