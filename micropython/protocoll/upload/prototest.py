import requests
import os 
try:
    platform = os.popen("uname").read().strip().lower()
    if "linux" in platform:
        print("Using Linux")
        # import pycryptodome and pycryptodomex. do not use pycrypto
        from Crypto.Cipher import AES
        aesMode = AES.MODE_CBC 
        import secrets
        import base64
    else:
        raise "No uname"
except ImportError:
    platform = "unknown"
    print("Using default")
    from cryptolib import aes as AES
    aesMode = 2  # AES.MODE_CBC

import binascii
import json
import random

MODE = "real" # "fake"

BACKEND_URL = "http://localhost:9000/sensorUpload.php"
DEVICE_ID = "1"
DEVICE_KEY = "00112233445566778899aabbccddeeff"  # hex

def pkcs7_pad(msg_bytes):
    pad_len = 16 - (len(msg_bytes) % 16)
    return msg_bytes + bytes([pad_len] * pad_len)

# Step 1: Join
if MODE != "fake":
    resp = requests.post(BACKEND_URL, json={
        "command": "join",
        "id": DEVICE_ID,
        "key": DEVICE_KEY
    })
    if resp.status_code != 200:
        print("Join failed:", resp.text)
        raise SystemExit
    join_data = resp.json()
    resp.close()
else:
    print("Running in fake mode, skipping join")
    join_data = {
        "challenge": "123412340000ABCD", # binascii.hexlify(bytearray([random.randint(0, 255) for i in range(16)])).decode(),
        "iv": binascii.hexlify(bytearray([random.randint(0, 255) for i in range(16)])).decode(),
        "session": "fake_session_id"
    }

print("Join response:", json.dumps(join_data))

challenge_hex = join_data['challenge']
iv_hex = join_data['iv']
session_id = join_data.get('session', None)


# Step 3: Encrypt challenge
key_bin = binascii.unhexlify(DEVICE_KEY)
iv_bin = binascii.unhexlify(iv_hex)
challenge_bin = binascii.unhexlify(challenge_hex)

if platform == "unknown":
    aes = AES(key_bin, aesMode, iv_bin)
else:
    aes = AES.new(key_bin, aesMode, iv_bin)


padded_msg = pkcs7_pad(challenge_bin)  # pad challenge to 16 bytes
encrypted = aes.encrypt(padded_msg)
encrypted_hex = binascii.hexlify(encrypted).decode()

if MODE != "fake":
    resp = requests.post(BACKEND_URL, json={
        "command": "challenge",
        "id": DEVICE_ID,
        "challenge": encrypted_hex,
        "session": session_id
    })
    if resp.status_code != 200:
        print("Challenge failed:", resp.text)
        raise SystemExit
    token_data = resp.json()
    resp.close()
else:
    print("Running in fake mode, skipping challenge")
    token_data = {
        "token": "fake_token"
    }
    print("Challenge response:", json.dumps(token_data))
        
token = token_data.get('token')
if not token:
    print("Auth failed")
    raise SystemExit

print("Got JWT:", token)

# Step 5: Send data
sensor_data = {"temperature": 23.5, "humidity": 40}

if MODE != "fake":
    resp = requests.post(BACKEND_URL, json={
        "command": "data",
        "id": DEVICE_ID,
       "token": token,
        "data": sensor_data
    })
    if resp.status_code != 200:
        print("Data failed:", resp.text)
        raise SystemExit
    data_result = resp.json()
    resp.close()
else:
    print("Running in fake mode, skipping data send")
    data_result = {
        "uuid": "fake-uuid"
    }

print("Data UUID:", data_result.get('uuid', 'N/A'))

