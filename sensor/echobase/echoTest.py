import echoBase
import adpcm
import time 


eb = echoBase.EchoBase()#debug=True)
eb.init(sample_rate=8000)
eb.setSpeakerVolume(90)
eb.play("/media/test8000.wav")
#eb.record("/media/mist.bin",100000)


with open("/media/test_8000.adpcm", "rb") as f:
    raw = f.read()
print("Read ADPCM data, size:", len(raw))
buf = bytearray(4*len(raw)) # max size after decode
w = adpcm.decode_into(raw, buf)
print("Decoded ADPCM data into buffer, size:", w)
eb.play(buf,w)
print("Played ADPCM decoded data")
time.sleep(1)

# same with irq 
eb.play(buf,w,useIrq=True)
while eb.getPlayStatus():
    print(".", end="")
    time.sleep_ms(50)
time.sleep(1)


# mic gain 0..7
# mix pga gain 0..10

eb.setShift(0)

reclen = 100000  # 100k ~ 6 seconds at 8kHz,16bit   
recbuf = bytearray(reclen)
for gain in range(7,8):
    eb.setMicGain(gain)
    for pgain in range(7,11):
        print("Mic gain:",gain,"PGA gain:",pgain)
        eb.setMicPGAGain(pgain)
        eb.record(recbuf,reclen)   
        eb.play(recbuf,reclen)

