import echoBase
eb = echoBase.EchoBase(debug=True)
eb.init(sample_rate=8000)
eb.setSpeakerVolume(90)
eb.play("/media/test8000.wav")
#eb.record("/media/mist.bin",100000)

# mic gain 0..7
# mix pga gain 0..10

reclen = 100000  # 100k ~ 6 seconds at 8kHz,16bit   
recbuf = bytearray(reclen)
for gain in range(7,8):
    eb.setMicGain(gain)
    for pgain in range(7,11):
        print("Mic gain:",gain,"PGA gain:",pgain)
        eb.setMicPGAGain(pgain)
        eb.record(recbuf,reclen)   
        eb.play(recbuf,reclen)

