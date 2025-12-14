import echoBase
import adpcm
import time 
from protoEngine import ProtoEngine
import binascii
import json
import os
import machine
import neopixel


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
        

        
RGB = DisPlay(cfdata)

def rgbFill(color):
    global RGB
    print("Set RGB to",color)
    RGB.fill(color)

rgbFill((40,40,40))  # off

# create audio
eb = echoBase.EchoBase()# debug=True)
eb.init(sample_rate=8000)
eb.setShift(0)
eb.setSpeakerVolume(90)

rgbFill((40,40,0xc0))  # off
eb.play("/media/test8000mono.wav")
rgbFill((40,40,40))  # off


# set format
format = "wav"  # or "adpcm"

# go online
baseUrl = "https://llama.ok-lab-karlsruhe.de/platane/php"

pt = ProtoEngine("karlsruhe.freifunk.net", baseUrl, deviceId, deviceKey)
#pt.setDebug(True)
rgbFill((80,20,20)) 
pt.connect()    
pt.join()
if pt.state == "connected":
    print("Join OK")
    rgbFill((40,40,40)) 
else:
    print("Join failed")
    rgbFill((80,0,0)) 


# record audio
print("Recording audio for upload...")
reclen_ = 100000  # 100k ~ 6 seconds at 8kHz,16bit   
recbuf_ = bytearray(reclen_)
rgbFill((0,0xc0,40)) 
eb.record(recbuf_,reclen_)
rgbFill((40,40,40))  # off
print("Recording done")
# compress
if format == "adpcm":
    recbuf = bytearray(reclen_//4) # max size after decode
    reclen = adpcm.encode_into(recbuf_, recbuf)
    print("Decoded ADPCM data into buffer, size:", reclen)
else:
    recbuf = recbuf_
    reclen = reclen_

# upload audio
rgbFill((0xa0,0xa0,0)) 
resp = pt.upload(recbuf,format=format)
rgbFill((40,40,40))  # off
time.sleep(1)

rgbFill((0xa0,0xa0,0))
name = resp.get("uuid", None)
if not name:
    print("Upload failed")
    pt.disconnect()
    raise BaseException("Upload failed")
rgbFill((40,40,40))  # off

print("Upload OK, name:", name)
# overwrite name for long audio test 
#name = "longAudio"
while True:
    rgbFill((0xa0,0,0xa0))
    resp = pt.check(name, format=format)
    if resp.get("status") == "ready":
        break
    print("File not ready, retrying in 1s...")
    rgbFill((40,40,40)) 
    time.sleep(1)
print("Check OK, size:", resp.get("size",0))
chunks = resp.get("chunks", 0)
chunkSize = resp.get("chunksize", 0)
print(f"Chunks: {chunks}, Chunk Size: {chunkSize}")
bufMult = 4 if format == "adpcm" else 1
dtbuf = [bytearray(bufMult*chunkSize),  # max size after decode
         bytearray(bufMult*chunkSize)]  # max size after decode
bufsel = 0
eb.setSpeakerVolume(100)

for c in range(chunks):
    if pt.state != "connected":
        print("Connection lost, stopping download")
        break
    # print(f"Downloading chunk {c+1}/{chunks}...")
    #task = asyncio.create_task(coroutine=getData(name, c))
    #await task
    #resp = task.result()
    rgbFill((0,0xa0,0xa0))  # off
    resp = pt.download(name, c, format=format)
    #print("Downloaded chunk data:", resp)
    dt = binascii.a2b_base64(resp.get("data", ""))
    if format == "wav":
        w = len(dt)
        idx = bufsel % 2
        # copy data into buffer (do not assign reference)
        dtbuf[idx][:w] = dt
    else:
        w = adpcm.decode_into(dt, dtbuf[bufsel%2])
    rgbFill((80,80,80))  # off
    while True:
        irqstate = machine.disable_irq()
        if not eb.getPlayStatus():
            machine.enable_irq(irqstate)
            break
        machine.enable_irq(irqstate)
        time.sleep_ms(1)
    #decompress
    #print("Decoded chunk data, size:", w)
    # play
    rgbFill((40,40,0xc0))  # off
    eb.play(dtbuf[bufsel%2],w,useIrq=True)
    bufsel += 1
    print("Playing chunk", c)
    
while eb.getPlayStatus():
    time.sleep_ms(1)
time.sleep(1)
rgbFill((40,40,40))  # off
    
pt.disconnect()
if pt.state != "offline":
    print("Disconnect failed")
else:
    print("Disconnect OK")
        
