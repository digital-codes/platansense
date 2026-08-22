import math
import echoBase
import adpcm
import time 
from protoEngine import ProtoEngine
import binascii
import json
import os
import machine
import neopixel
from machine import Timer


# check config and read key
_CONF_FILE = "config.json"
files = os.listdir("/")
if _CONF_FILE in files:
    with open(_CONF_FILE) as f:
        cfdata = json.load(f)
else:
    raise BaseException("No Config")        

# verify id
if machine.unique_id().hex() != cfdata["id"]:
    raise BaseException("Invalid ID")
deviceId = cfdata["id"]

try:
    # get ble key
    deviceKey = cfdata["ble"]["key"]
    # generate device name
    _deviceName = f"{cfdata['model']}_{cfdata['device']:04}" 
    print("Devicename:",_deviceName)
except:
    raise BaseException("Invalid Config")        



class DisPlay:
    def __init__(self, config, i2c=None):
        self.i2c = i2c
        if config.get("io") and config["io"].get("led") is not None:
            neoPin = config["io"]["led"]
            p = machine.Pin(neoPin)
            self.hardware = neopixel.NeoPixel(p,1)
            self.type = "neopixel"
        elif config.get("io") and config.get("io").get("lcd") == "s3atom":
            import st7789py
            # import framebuf # only for text
            import time
            if config.get("type") == "AtomS3R":
                print("Initializing S3R LCD")
                # LCD Pin Configuration for S3R LCD
                LCD_CS = 14     # spi cs
                LCD_DC = 42 # 33     # data/control  RS pin?
                LCD_SCLK = 15   # spi clk
                LCD_MOSI = 21   # spi mosi
                LCD_RST = 48 # 34    # reset
                # LCD_BL = 45     # back light on S3R via I2C
                from blctl import LP5562
                if i2c is None:
                    i2c = machine.I2C(0, scl=machine.Pin(0), sda=machine.Pin(45), freq=400000)
                backlight = LP5562(i2c_inst=self.i2c, addr=0x30)
                backlight.init()
                backlight.backlight_on()

            # Initialize SPI. must use SPI1
            spi = machine.SPI(1, baudrate=10000000, sck=machine.Pin(LCD_SCLK), mosi=machine.Pin(LCD_MOSI))

            # Initialize CS, DC, and RST pins
            # cs = machine.Pin(LCD_CS, machine.Pin.OUT)
            dc = machine.Pin(LCD_DC, machine.Pin.OUT)

            rst = machine.Pin(LCD_RST, machine.Pin.OUT)

            # Reset the LCD
            rst.value(1)
            time.sleep(0.1)
            rst.value(0)
            time.sleep(0.1)
            rst.value(1)
            time.sleep(0.1)

            # Initialize PWM for backlight
            # bl = machine.PWM(machine.Pin(LCD_BL))
            # bl.freq(500)  # 500 Hz
            # bl.duty_u16(50000)  # Maximum brightness (0-65535)

            display = st7789py.ST7789(spi, 128, 128, xstart=3, ystart=2,reset=rst, dc=dc)
            display.init()
            # init for usb connector down
            display._set_mem_access_mode(3,0,0,True)
            self.hardware = display
            self.type = "lcd"
            self.convertColor = st7789py.color565
        else:
            self.type = None

    def getI2C(self):
        return self.i2c
        
    def fill(self, color):
        if self.type == "neopixel":
            self.hardware.fill(color)
            self.hardware.write()
        elif self.type == "lcd":
            col = self.convertColor(color[0],color[1],color[2])
            self.hardware.fill(col)
        else:
            return
        
    def fill_rect(self, x, y, w, h, color):
        if self.type == "neopixel":
            self.hardware.fill(color)
            self.hardware.write()
        elif self.type == "lcd":
            col = self.convertColor(color[0],color[1],color[2])
            self.hardware.fill_rect(x, y, w, h, col)
        else:
            return
        

        
RGB = DisPlay(cfdata)

def rgbFill(color):
    global RGB
    print("Set RGB to",color)
    RGB.fill(color)

def rgbRect(x,y,w,h,color):
    global RGB
    print("Set Rect RGB to",color)
    RGB.fill_rect(x,y,w,h,color)


rgbFill((40,40,40))  # off

# go online
baseUrl = "http://192.168.4.1/platane/php"  # replace with the correct local IP address of the server

print("Connecting to server at", baseUrl,"with device ID", deviceId," ssid",cfdata["wlan"]["ssid"])
print("Join id and key:",deviceId, deviceKey)
pt = ProtoEngine(cfdata["wlan"]["ssid"], cfdata["wlan"]["key"], baseUrl, deviceId, deviceKey)
pt.setDebug(True)
rgbFill((80,20,20)) 
print("Connecting...")
pt.connect()    
print("Joining...")
pt.join()
if pt.state == "connected":
    print("Join OK")
    rgbFill((0,80,80)) 
else:
    print("Join failed")
    rgbFill((80,0,0)) 
    raise BaseException("Join failed")


rgbFill((40,40,0xc0))  # off

# create audio
print("Initializing mic...")
eb = echoBase.EchoBase(debug=True)
# i2c_sda=38, i2c_scl=39, i2s_di=7, i2s_ws=6,  i2s_do=5, i2s_bck=8, i2c=None, i2c_id=0
# esp32mx
# i2c_sda=25, i2c_scl=21, i2s_di=23, i2s_ws=19,  i2s_do=22, i2s_bck=33, i2c=None, i2c_id=0


#eb.init(sample_rate=8000,i2c_sda = cfdata["io"]["i2c"]["sda"], i2c_scl = cfdata["io"]["i2c"]["scl"],
#eb.init(sample_rate=8000,i2c_sda = cfdata["io"]["i2c"]["scl"], i2c_scl = cfdata["io"]["i2c"]["sda"],
#        i2s_di=23, i2s_ws=19,  i2s_do=22, i2s_bck=33)
eb.init(sample_rate=8000)
# eb.setShift(1)
#eb.setSpeakerVolume(100)

# init btn 
btn = machine.Pin(cfdata["io"]["btn"], machine.Pin.IN, machine.Pin.PULL_UP)

orange = (0xFF, 0xA5, 0x00)
green = (0x00, 0xFF, 0x00)
blue = (0x00, 0x00, 0xFF)
white = (0xFF, 0xFF, 0xFF)
red = (0xFF, 0x00, 0x00)

print("Ready. Press button to record and upload audio. Hold button for less than 200 ms to send stop command.")

while True:

    btn_state = btn.value()
    if btn_state == 1:
        rgbFill(white)
    else:
        rgbFill(blue)  

    # wait for open btn
    while btn_state == 0:
        time.sleep_ms(10)
        btn_state = btn.value()
    print("Button released...")
    time.sleep_ms(10)
    rgbFill(white)

    # wait for press
    while btn_state == 1:
        time.sleep_ms(10)
        btn_state = btn.value()

    # is pressed
    t0 = time.ticks_ms()
    print("Button pressed...")
    rgbFill(blue)  
    
    # wait for button release
    while btn.value() == 0:
        time.sleep_ms(10)
        btn_state = btn.value()

    # is released
    if time.ticks_diff(time.ticks_ms(), t0) < 500:
        print("Button held for less than 500 ms, stop...")
        rgbFill(orange)  
        try:
            stop_resp = pt.stop()  # Replace "sensor_name" with the actual sensor name
            print("Stop command sent successfully")
            print(f"Response: {stop_resp}")
        except Exception as e:
            print(f"Error sending stop command: {e}")
            rgbFill(red)
            time.sleep(1)  
        print("Start over...")
        continue

    # record audio
    print("Recording audio for upload...")
    rgbFill(green)  
    reclen_ = 100000  # 100k ~ 6 seconds at 8kHz,16bit   
    recbuf_ = bytearray(reclen_)
        
    eb.record(recbuf_,reclen_)
    while eb.getRecordStatus():
        time.sleep_ms(100)

    rgbFill((40,40,40))  # off
    print("Recording done", reclen_)
    # compress on upload
    format = "adpcm"  # "wav" or "adpcm"
    if format == "adpcm":
        recbuf = bytearray(reclen_//4) # max size after decode
        reclen = adpcm.encode_into(recbuf_, recbuf)
        print("Decoded ADPCM data into buffer, size:", reclen)
    else:
        recbuf = recbuf_
        reclen = reclen_

    # upload audio
    rgbFill(orange)  
    resp = pt.upload(recbuf,format=format)
    time.sleep(1)

    name = resp.get("uuid", None)
    if not name:
        print("Upload failed")
        pt.disconnect()
        raise BaseException("Upload failed")
        rgbFill(red)
        time.sleep(1)  

    
pt.disconnect()
if pt.state != "offline":
    print("Disconnect failed")
else:
    print("Disconnect OK")
        
machine.soft_reset()
