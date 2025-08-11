from machine import I2S, Pin
import time

# AtomS3Rext:
directGrove = False  # True for direct Grove connection, False for PBHub

if directGrove:
    sdo = 1
    bck = 2
    ws = 5 
else: # pbhub
    sdo = 8  # black, PB
    bck = 7  # black, PA
    ws = 39  # red, PA

i2s_port = 0
sr = 16000 # 44100 

if sr == 44100:
    wavFile = "output_44k_loud.wav"
else:
    wavFile = "output_16k_loud.wav"

# deinit
try:
    I2S(i2s_port, sck=bck, sd=sdo, ws=ws, mode=I2S.TX, bits=16, format=I2S.MONO, rate=sr, ibuf=0).deinit()
except Exception as e:
    print(f"Error deinitializing I2S: {e}. Continuing...")

time.sleep(1)

CHUNK_SIZE = 4096

# Set up I2S for output
i2s = I2S(
    i2s_port,
    sck=Pin(bck),
    ws=Pin(ws),
    sd=Pin(sdo),
    mode=I2S.TX,
    bits=16,
    format=I2S.MONO,
    rate=sr,
    ibuf=8*CHUNK_SIZE  # Bigger buffer helps smooth out timing issues
)

shift = 0

while True:
    with open(wavFile, "rb") as f:
        f.read(44)  # Skip WAV header
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break

            chunk  = bytearray(chunk)
            #print(f"Read chunk of size: {len(chunk)}, {len(buf) // 2} samples")
            print(f"Writing chunk of size: {len(chunk)}")
            # Write chunk, handling partial writes if necessary
            if shift != 0:
                I2S.shift(buf=chunk,bits=16,shift=shift)
            written = 0
            while written < len(chunk):
                n = i2s.write(chunk[written:])
                written += n



i2s.deinit()


