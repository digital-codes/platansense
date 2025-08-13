import requests
import os 
import binascii
import json
import random
import time

# get platform and intialize base settings
try:
    platform = os.uname().lower() # popen("uname").read().strip().lower()
    if "linux" in platform:
        platform = "linux"
        print("Using Linux")
        # import pycryptodome and pycryptodomex. do not use pycrypto
        from Crypto.Cipher import AES
        aesMode = AES.MODE_CBC 
        import secrets
        import base64
        baseUrl = "http://localhost:9000/sensorUpload.php"
        deviceId = "1"
        deviceKey = "00112233445566778899aabbccddeeff"  # hex
    else:
        raise Exception("No uname")
except (ImportError, Exception) as e:
    platform = "esp32" # assume esp32 if uname fails
    print("Using ESP32 as default")
    from cryptolib import aes as AES
    aesMode = 2  # AES.MODE_CBC
    # try to import esp32 for NVS
    try:
        import esp32
        namespace = "platane"
        nvs = esp32.NVS(namespace)
        buf = bytearray(64)
        l = nvs.get_blob("deviceId", buf)
        if l > 0:
            deviceId = buf[:l].decode('utf-8')
        else:
            deviceId = None
        l = nvs.get_blob("deviceKey", buf)
        if l > 0:
            deviceKey = buf[:l].decode('utf-8')
            print(f"Found deviceKey: {deviceKey}")
        else:
            deviceKey = None
        l = nvs.get_blob("baseurl", buf)
        if l > 0:
            baseUrl = f"https://{buf[:l].decode('utf-8')}/sensorUpload.php"
        else:
            baseUrl = None
    except ImportError:
        print("No esp32 module found, using defaults")
        exit(1)

MODE = "real" # "fake"

if MODE == "real":
    import network
    nic = network.WLAN(network.WLAN.IF_STA)
    l = nvs.get_blob("ssid", buf)
    if l == 0:
        print("No ssid found, setting new credentials.")
        exit(1)
    ssid = buf[:l].decode('utf-8')

    l = nvs.get_blob("passwd", buf)
    if l > 0:
        password = buf[:l].decode('utf-8')
    else:
        password = ""
    
    while not nic.active():
        print("Waiting for network interface to become active...")
        time.sleep(1)
    nic.connect(ssid, password)
    while not nic.isconnected():
        print("Waiting for network connection...")
        time.sleep(1)
        
    print("Network connected:", nic.ifconfig()) 



def pkcs7_pad(msg_bytes):
    pad_len = 16 - (len(msg_bytes) % 16)
    return msg_bytes + bytes([pad_len] * pad_len)

# Step 1: Join
if MODE != "fake":
    resp = requests.post(f"{baseUrl}/sensorUpload.php", json={
        "command": "join",
        "id": deviceId
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
key_bin = binascii.unhexlify(deviceKey)
iv_bin = binascii.unhexlify(iv_hex)
challenge_bin = binascii.unhexlify(challenge_hex)

if platform != "linux":
    aes = AES(key_bin, aesMode, iv_bin)
else:
    aes = AES.new(key_bin, aesMode, iv_bin)


padded_msg = pkcs7_pad(challenge_bin)  # pad challenge to 16 bytes
encrypted = aes.encrypt(padded_msg)
encrypted_hex = binascii.hexlify(encrypted).decode()

if MODE != "fake":
    resp = requests.post(baseUrl, json={
        "command": "challenge",
        "id": deviceId,
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
    resp = requests.post(baseUrl, json={
        "command": "data",
        "id": deviceId,
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


if MODE != "fake":
    while True:
        print("Sending data")
        resp = requests.post(baseUrl, json={
            "command": "data",
            "id": deviceId,
            "token": token,
            "data": sensor_data
        })
        if resp.status_code != 200:
            print("Data failed:", resp.text)
            raise SystemExit
        data_result = resp.json()
        resp.close()
        time.sleep(10)
