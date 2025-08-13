import requests
import binascii
import json
import time
import network
from cryptolib import aes as AES
import esp32

class PlataneDevice:
    def __init__(self, namespace):
        self.namespace = namespace
        self.nvs = esp32.NVS(namespace)
        self.deviceId = None
        self.deviceKey = None
        self.baseUrl = None
        self.ssid = None
        self.password = None
        self.token = None
        self._load_nvs()

    def _load_nvs(self):
        buf = bytearray(64)
        l = self.nvs.get_blob("deviceId", buf)
        self.deviceId = buf[:l].decode('utf-8') if l > 0 else None
        l = self.nvs.get_blob("deviceKey", buf)
        self.deviceKey = buf[:l].decode('utf-8') if l > 0 else None
        l = self.nvs.get_blob("baseurl", buf)
        self.baseUrl = f"https://{buf[:l].decode('utf-8')}/sensorUpload.php" if l > 0 else None
        l = self.nvs.get_blob("ssid", buf)
        self.ssid = buf[:l].decode('utf-8') if l > 0 else None
        l = self.nvs.get_blob("passwd", buf)
        self.password = buf[:l].decode('utf-8') if l > 0 else ""

    def connect_wifi(self):
        nic = network.WLAN(network.WLAN.IF_STA)
        while not nic.active():
            print("Waiting for network interface to become active...")
            time.sleep(1)
        nic.connect(self.ssid, self.password)
        while not nic.isconnected():
            print("Waiting for network connection...")
            time.sleep(1)
        print("Network connected:", nic.ifconfig())

    def get_token(self):
        # Step 1: Join
        resp = requests.post(self.baseUrl, json={
            "command": "join",
            "id": self.deviceId
        })
        if resp.status_code != 200:
            print("Join failed:", resp.text)
            resp.close()
            self.token = None
            return None
        join_data = resp.json()
        resp.close()
        challenge_hex = join_data.get('challenge')
        iv_hex = join_data.get('iv')
        session_id = join_data.get('session', None)
        if not challenge_hex or not iv_hex:
            print("Missing challenge or iv in join response")
            self.token = None
            return None

        # Step 3: Encrypt challenge
        try:
            key_bin = binascii.unhexlify(self.deviceKey)
            iv_bin = binascii.unhexlify(iv_hex)
            challenge_bin = binascii.unhexlify(challenge_hex)
            aes = AES(key_bin, 2, iv_bin)
            padded_msg = self.pkcs7_pad(challenge_bin)
            encrypted = aes.encrypt(padded_msg)
            encrypted_hex = binascii.hexlify(encrypted).decode()
        except Exception as e:
            print("Encryption failed:", e)
            self.token = None
            return None

        resp = requests.post(self.baseUrl, json={
            "command": "challenge",
            "id": self.deviceId,
            "challenge": encrypted_hex,
            "session": session_id
        })
        if resp.status_code != 200:
            print("Challenge failed:", resp.text)
            resp.close()
            self.token = None
            return None
        token_data = resp.json()
        resp.close()
        self.token = token_data.get('token')
        if not self.token:
            print("Auth failed")
            self.token = None
            return None
        return self.token

    def send_data(self, sensor_data):
        if not self.token:
            print("No token, call get_token() first.")
            return None
        resp = requests.post(self.baseUrl, json={
            "command": "data",
            "id": self.deviceId,
            "token": self.token,
            "data": sensor_data
        })
        if resp.status_code != 200:
            print("Data failed:", resp.text)
            resp.close()
            self.token = None
            return None
        data_result = resp.json()
        resp.close()
        return data_result.get('uuid', None)


    @staticmethod
    def pkcs7_pad(msg_bytes):
        pad_len = 16 - (len(msg_bytes) % 16)
        return msg_bytes + bytes([pad_len] * pad_len)


if __name__ == "__main__":
    import sys
    device = PlataneDevice("platane")
    device.connect_wifi()
    token = device.get_token()
    print("Token received:", token)
    if not token:
        print("Failed to get token, exiting.")
        sys.exit(1) 
    sample_data = {"temperature": 23.5, "humidity": 60}
    uuid = device.send_data(sample_data)
    if uuid is None:
        print("Failed to send data.")
    else:
        print("Data sent, UUID:", uuid)
    