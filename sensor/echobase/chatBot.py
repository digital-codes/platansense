import echoBase
import adpcm
import time 
from protoEngine import ProtoEngine
import binascii
import json
import os
import machine

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


# create audio
eb = echoBase.EchoBase()# debug=True)
eb.init(sample_rate=8000)
eb.setShift(0)
eb.setSpeakerVolume(90)
eb.play("/media/test8000.wav")


# go online
baseUrl = "https://llama.ok-lab-karlsruhe.de/platane/php"

pt = ProtoEngine("karlsruhe.freifunk.net", baseUrl, deviceId, deviceKey)
#pt.setDebug(True)
pt.connect()    
pt.join()
if pt.state == "connected":
    print("Join OK")
else:
    print("Join failed")


# record audio
print("Recording audio for upload...")
reclen_ = 100000  # 100k ~ 6 seconds at 8kHz,16bit   
recbuf_ = bytearray(reclen_)
eb.record(recbuf_,reclen_)   
print("Recording done")
# compress
recbuf = bytearray(reclen_//4) # max size after decode
reclen = adpcm.encode_into(recbuf_, recbuf)
print("Decoded ADPCM data into buffer, size:", reclen)


# upload audio
resp = pt.upload(recbuf)
name = resp.get("uuid", None)
if not name:
    print("Upload failed")
    pt.disconnect()
    raise BaseException("Upload failed")

print("Upload OK, name:", name)
name = "longAudio"
resp = pt.check(name)
print("Check OK, size:", resp.get("size",0))
chunks = resp.get("chunks", 0)
chunkSize = resp.get("chunksize", 0)
print(f"Chunks: {chunks}, Chunk Size: {chunkSize}")
dtbuf = [bytearray(4*chunkSize),  # max size after decode
         bytearray(4*chunkSize)]  # max size after decode
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
    resp = pt.download(name, c)
    #print("Downloaded chunk data:", resp)
    dt = binascii.a2b_base64(resp.get("data", ""))
    w = adpcm.decode_into(dt, dtbuf[bufsel%2])
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
    eb.play(dtbuf[bufsel%2],w,useIrq=True)
    bufsel += 1
    print("Playing chunk", c)
    
while eb.getPlayStatus():
    time.sleep_ms(1)
time.sleep(1)
    
pt.disconnect()
if pt.state != "offline":
    print("Disconnect failed")
else:
    print("Disconnect OK")
        
