from platanAuth import PlatanAuth
import sys
import os
import binascii
import requests

device = PlatanAuth("platane")
id = device.get_id()
baseUrl = device.get_baseUrl()
print("Device ID:", id)
print("Base URL:", baseUrl)

device.connect_wifi()

token = device.get_token()
print("Token received:", token)
if not token:
    print("Failed to get token, exiting.")
    sys.exit(1) 
sample_data = binascii.b2a_base64(bytearray(list(os.urandom(10000)))).decode('utf-8')
resp = requests.post(f"{baseUrl}/sensorUpload.php", json={
    "command": "data",
    "id": id,
    "token": token,
    "data": sample_data
})
if resp.status_code != 200:
    print("Data failed:", resp.text)
    resp.close()
data_result = resp.json()
resp.close()
uuid = data_result.get('uuid', None)
if uuid is None:
    print("Failed to send data.")
    sys.exit(1)
else:
    print("Data sent, UUID:", uuid)

# check files
resp = requests.post(f"{baseUrl}/sensorDownload.php", json={
    "command": "check",
    "id": id,
    "token": token,
    "name": uuid
})
if resp.status_code != 200:
    print("Check failed:", resp.text)
    resp.close()
data_result = resp.json()
resp.close()
chunks = data_result.get("chunks", 0)
print("Number of chunks available:", chunks)
for chunk in range(chunks):
    resp = requests.post(f"{baseUrl}/sensorDownload.php", json={
        "command": "down",
        "id": id,
        "token": token,
        "chunk": chunk,
        "name": uuid
    })
    if resp.status_code != 200:
        print("Down failed:", resp.text)
        resp.close()
    data_result = resp.json()
    resp.close()
    size = data_result.get("length", 0)
    data_b64 = data_result.get("data", "")
    receiver = bytearray(4096)
    decoded = binascii.a2b_base64(data_b64)
    receiver[:len(decoded)] = decoded
    data = receiver
    print(f"Chunk {chunk} size: {size} bytes, data: {data[:50]}... (truncated)")    