#import unit
import time

# plain bme/bmp280 not work on custom pins
# works with ./sensors/m5stack/driver/bmp280.py
from machine import I2C, Pin

from VL53L0X import VL53L0X

# i2c possibly shared with pbhub ...
tof_scl = Pin(1)  # SCL pin for I2C
tof_sda = Pin(2)  # SDA pin for I2C
tof_i2c = I2C(0, scl=tof_scl, sda=tof_sda, freq=400000)
tof_addr = 0x29
#tof_0 = BME280(tof_i2c, addr=tof_addr)
tof_0 = VL53L0X(i2c = tof_i2c, address=tof_addr)

tof_0.start()
while True:
    print(tof_0.read())
    time.sleep(1)
