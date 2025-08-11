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
pbhub_i2c = I2C(0, scl=pbhub_scl, sda=pbhub_sda, freq=100000)
pbhub_0 = PBHUBUnit(pbhub_i2c,pbhub_addr)

# usonic  is digital in on port 1, trigger pin 0, echo pin 1
triggerPort = (1,0)
echoPort = (1,1)

# initialize the ultrasonic sensor
pbhub_0.digital_write(triggerPort[0], triggerPort[1], 0)  # Set trigger low
pbhub_0.digital_read(echoPort[0], echoPort[1])


while True:
    # trigger the ultrasonic sensor
    pbhub_0.digital_write(triggerPort[0], triggerPort[1], 0)  # Set trigger low
    time.sleep_ms(1)
    # time.sleep_us(5)
    pbhub_0.digital_write(triggerPort[0], triggerPort[1], 1)  # Set trigger low
    time.sleep_ms(1)
    # time.sleep_us(10)
    pbhub_0.digital_write(triggerPort[0], triggerPort[1], 0)  # Set trigger low

    # Wait for echo to go HIGH
    timeout_start = time.ticks_ms()
    echoFailed = False
    while pbhub_0.digital_read(echoPort[0], echoPort[1]) == 0:
        if time.ticks_diff(time.ticks_ms(), timeout_start) > 100:
            print("Timeout waiting for echo start")
            echoFailed = True
            break

    if echoFailed:
        print("Echo failed, too close probably")
        time.sleep_ms(300)  # Wait for 300 milliseconds before the next reading
        continue
    
    # Measure HIGH duration
    start = time.ticks_us()
    while pbhub_0.digital_read(echoPort[0], echoPort[1]) == 1:
        if time.ticks_diff(time.ticks_us(), start) > 50000:  # 50 ms max pulse
            break
    end = time.ticks_us()

    pulse_width = time.ticks_diff(end, start)
    # assume > 3m is off
    if pulse_width > 30000:  # 3m in microseconds
        print("Distance: > 300 cm (out of range)")
    else:
        distance_cm = (pulse_width / 2) / 29.1  # speed of sound
        print("Distance: {:.2f} cm".format(distance_cm))

    time.sleep_ms(300)  # Wait for 300 milliseconds before the next reading










    # maxDelay = 50 # Maximum delay for echo in milliseconds
    # delayStep = 3  # Delay step in milliseconds
    # # Wait for echo to go high
    # detected = False
    # while maxDelay > 0:
    #     if pbhub_0.digital_read(echoPort[0], echoPort[1]) == 1:
    #         detected = True
    #         break
    #     maxDelay -= delayStep
    #     time.sleep_ms(delayStep)

    # print('Detected:', detected, 'Max Delay:', maxDelay )

    # time.sleep_ms(300)  # Wait for 300 milliseconds before the next reading

