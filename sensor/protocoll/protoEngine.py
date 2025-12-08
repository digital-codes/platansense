import cryptolib
import requests 
import json
import time
import network
import machine
import random
import binascii


class ProtoEngine:
    """
    Simple helper to encrypt/decrypt with cryptolib.aes and upload payloads to a server.
    Expects `baseUrl`, `cryptolib` and `requests` to be available in the module scope.
    """
    def __init__(self, ssid, baseUrl, id, key):
        self.base_url = baseUrl
        # current runtime state: one of "offline", "online", "joining", "connected"
        self._valid_states = {"offline", "online", "joining", "connected"}
        self.state = "offline"
        self.ssid = ssid
        self.pwd = ""
        self.debug = False
        self.id = id
        self.key = key
        self.session = None
        self.token = None

    def _transit(self, from_state, to_state):
        if from_state not in self._valid_states:
            raise ValueError(f"Invalid from_state: {from_state}")
        if to_state not in self._valid_states:
            raise ValueError(f"Invalid to_state: {to_state}")
        # Define valid transitions
        self.state = to_state

    def _encrypt(self, data):
        if not isinstance(data, (bytes, bytearray)):
            data = str(data).encode()
        return self._aes.encrypt(data)

    def _decrypt(self, data):
        return self._aes.decrypt(data)

    def setDebug(self, enable):
        self.debug = enable
        
    # Connection state management methods
    def connect(self):
        if self.state != "offline":
            return
        nic = network.WLAN(network.WLAN.IF_STA)
        if not nic.active():
            nic.active(True)
        while not nic.active():
            if self.debug:
                print("Waiting for network interface to become active...")
            time.sleep(1)
        nic.connect(self.ssid, self.pwd)
        while not nic.isconnected():
            if self.debug:
                print("Waiting for network connection...")
            time.sleep(1)
            
        if self.debug:
            print("Network connected:", nic.ifconfig()) 

        self._transit(self.state, "online")

    def disconnect(self):
        if self.state == "offline":
            return
        nic = network.WLAN(network.WLAN.IF_STA)
        nic.disconnect()
        self.session = None
        self.token = None   
        self._transit(self.state, "offline")
        if self.debug:
            print("Disconnected from network.")

    def join(self):
        if self.state != "online":
            return
        # part 1 
        r = requests.post(self.base_url + "/sensorUpload.php", json={"id": self.id, "command": "join"})
        if r.status_code != 200:
            raise ValueError(f"Join request failed with status code {r.status_code}.")
        data = r.json()
        challenge = data.get("challenge")
        iv = data.get("iv")
        session = data.get("session")
        if not all([challenge, iv, session]):
            raise ValueError("Invalid join response from server.")
        if self.debug:
            print("Join response:", data)
        self.session = session
        self._transit(self.state, "joining")
        # part 2
        if self.debug:
            print("Preparing challenge response...")
            print(f"Challenge: {challenge}, IV: {iv}, Key: {self.key}")
        try:
            crypt = cryptolib.aes(bytes.fromhex(self.key),2,bytes.fromhex(iv))
            response = crypt.encrypt(bytes.fromhex(challenge))
        except:
            raise ValueError("Failed to initialize AES cipher with provided key/iv.")
        payload = {"command": "challenge", "session": self.session, "id": self.id, "challenge": response.hex()}
        if self.debug:
            print("Challenge payload:", payload)
        r2 = requests.post(self.base_url + "/sensorUpload.php", json=payload)
        if r2.status_code != 200:
            raise ValueError(f"Join request failed with status code {r2.status_code}, {r2.text}")
        data = r2.json()
        if self.debug:
            print("Challenge response:", data)
        self.token = data.get("token", None)
        if not self.token:
            raise ValueError("Invalid challenge response from server.")
        self._transit(self.state, "connected")
        return True
    

    def upload(self, endpoint, data, headers=None, as_hex=False):
        """
        Encrypts `data` and POSTs it to host/endpoint.
        If as_hex is True, sends encrypted payload as hex string; otherwise sends raw bytes.
        Returns the requests.Response object (raises on HTTP errors).
        """
        payload = self.encrypt(data)
        body = payload.hex().encode() if as_hex else payload
        url = self.base_url.rstrip('/') + '/' + endpoint.lstrip('/')
        resp = requests.post(url, data=body, headers=headers or {})
        resp.raise_for_status()
        return resp

    def upload_json(self, endpoint, obj, headers=None, as_hex=False):
        headers = dict(headers or {})
        headers.setdefault("Content-Type", "application/json")
        return self.upload(endpoint, json.dumps(obj).encode(), headers=headers, as_hex=as_hex)

#a = cryptolib.aes("1234567812345678",2,b"1234123412341234")
#x = a.encrypt(b"1234123412341234")
#x.hex()
#'9ae8fd02b340288a0e7bbff0f0ba54d6'

if __name__ == "__main__":
    baseUrl = "http://localhost:9000"
    baseUrl = "https://llama.ok-lab-karlsruhe.de/platane/php"
    id = 1
    key = "00112233445566778899aabbccddeeff"


    pt = ProtoEngine("karlsruhe.freifunk.net", baseUrl, id, key)
    pt.setDebug(True)
    pt.connect()    
    pt.join()
    
    