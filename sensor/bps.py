#import unit
import time

# plain bme/bmp280 not work on custom pins
# works with ./sensors/m5stack/driver/bmp280.py
from bmp280 import BMP280
from machine import I2C, Pin

# i2c possibly shared with pbhub ...
bps_scl = Pin(1)  # SCL pin for I2C
bps_sda = Pin(2)  # SDA pin for I2C
bps_i2c = I2C(0, scl=bps_scl, sda=bps_sda, freq=400000)
bps_addr = 118
#bps_0 = BME280(bps_i2c, addr=bps_addr)
bps_0 = BMP280(i2c = bps_i2c, addr=bps_addr)


while True:
    (temp,pres) = bps_0.measure()
    print((str('temperature:') + str((temp))))
    print((str('pressure:') + str((pres))))
    time.sleep_ms(1000)
    continue

