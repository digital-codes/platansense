import requests
import os 
import binascii
import json
import random
import time
import network
from cryptolib import aes as AES
import esp32

aesMode = 2  # AES.MODE_CBC

def loadNvs():
    # import esp32 for NVS
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
    l = nvs.get_blob("ssid", buf)
    if l == 0:
        print("No ssid found, setting new credentials.")
        ssid = None
    ssid = buf[:l].decode('utf-8')
    l = nvs.get_blob("passwd", buf)
    if l > 0:
        password = buf[:l].decode('utf-8')
    else:
        password = ""
    return deviceId, deviceKey, baseUrl, ssid, password


def pkcs7_pad(msg_bytes):
    pad_len = 16 - (len(msg_bytes) % 16)
    return msg_bytes + bytes([pad_len] * pad_len)


deviceId, deviceKey, baseUrl, ssid, password = loadNvs()

nic = network.WLAN(network.WLAN.IF_STA)

while not nic.active():
    print("Waiting for network interface to become active...")
    time.sleep(1)
nic.connect(ssid, password)
while not nic.isconnected():
    print("Waiting for network connection...")
    time.sleep(1)
    
print("Network connected:", nic.ifconfig()) 


# Step 1: Join
resp = requests.post(f"{baseUrl}/sensorUpload.php", json={
    "command": "join",
    "id": deviceId
})
if resp.status_code != 200:
    print("Join failed:", resp.text)
    raise SystemExit
join_data = resp.json()
resp.close()

print("Join response:", json.dumps(join_data))

challenge_hex = join_data['challenge']
iv_hex = join_data['iv']
session_id = join_data.get('session', None)


# Step 3: Encrypt challenge
key_bin = binascii.unhexlify(deviceKey)
iv_bin = binascii.unhexlify(iv_hex)
challenge_bin = binascii.unhexlify(challenge_hex)

aes = AES(key_bin, aesMode, iv_bin)


padded_msg = pkcs7_pad(challenge_bin)  # pad challenge to 16 bytes
encrypted = aes.encrypt(padded_msg)
encrypted_hex = binascii.hexlify(encrypted).decode()

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
        
token = token_data.get('token')
if not token:
    print("Auth failed")
    raise SystemExit

print("Got JWT:", token)

# Step 5: Send data
sensor_data = {"temperature": 23.5, "humidity": 40}

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

print("Data UUID:", data_result.get('uuid', 'N/A'))

