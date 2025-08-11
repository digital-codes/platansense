from Crypto.Cipher import AES
import random
import secrets
import os
import base64
from Cryptodome.Util.Padding import pad, unpad

# device is
device = 123
idString = f"{devNum:06}"
# shared key
#key1 = b'0123456789ABCDEF'  # 16 bytes key
key1=secrets.token_bytes(16)
print(f"KEY: {key1.hex()}")

fout = f"{idString}.png"
cmd = f"qrencode -m5 -s5 \'{idString} {key1.hex()}\' -o {fout}"
print(cmd)
os.system(cmd)

