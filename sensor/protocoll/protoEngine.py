import cryptolib
import requests 
import json
import time
import sys
import binascii
if not sys.platform.lower().startswith("linux"):
    import network
    embedded = True
else:
    embedded = False


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

    def setDebug(self, enable):
        self.debug = enable
        
    # Connection state management methods
    def connect(self):
        if self.state != "offline":
            return
        if embedded:
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
                print("Network config:", nic.ifconfig()) 

                
        if self.debug:
            print("Network connected") 

        self._transit(self.state, "online")

    def disconnect(self):
        if self.state == "offline":
            return
        if embedded:
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
            if r2.status_code == 401:
                print(json.dumps(r2))
            raise ValueError(f"Join request failed with status code {r2.status_code}, {r2.text}.")
        data = r2.json()
        if self.debug:
            print("Challenge response:", data)
        self.token = data.get("token", None)
        if not self.token:
            raise ValueError("Invalid challenge response from server.")
        self._transit(self.state, "connected")
        return True
    

    def upload(self, data):
        if self.state != "connected":
            raise ValueError("Not connected. Cannot upload data.")
        payload = {"command": "data", "token": self.token, "session": self.session, "id": self.id, "data": binascii.b2a_base64(data).decode('utf-8')}
        resp = requests.post(self.base_url + "/sensorUpload.php", json=payload)
        if resp.status_code != 200:
            self._transit(self.state, "online")
            if self.debug:
                print("Upload response:", resp.status_code, resp.text)
            raise ValueError(f"Upload request failed with status code {resp.status_code}, {resp.text}.")
        result = resp.json()
        if self.debug:
            print("Upload response:", result)
        return result

    def check(self,name):
        if self.state != "connected":
            raise ValueError("Not connected. Cannot upload data.")
        payload = {"command": "check", "token": self.token, "id": self.id, "name": name}
        resp = requests.post(self.base_url + "/sensorDownload.php", json=payload)
        if resp.status_code != 200:
            self._transit(self.state, "online")
            if self.debug:
                print("Upload response:", resp.status_code, resp.text)
            raise ValueError(f"Upload request failed with status code {resp.status_code}, {resp.text}.")
        result = resp.json()
        if self.debug:
            print("Upload response:", result)
        return result
    
    def download(self,name,chunk):
        if self.state != "connected":
            raise ValueError("Not connected. Cannot upload data.")
        payload = {"command": "down", "token": self.token, "id": self.id, "name": name, "chunk": chunk}
        resp = requests.post(self.base_url + "/sensorDownload.php", json=payload)
        if resp.status_code != 200:
            self._transit(self.state, "online")
            if self.debug:
                print("Download response:", resp.status_code, resp.text)
            raise ValueError(f"Download request failed with status code {resp.status_code}, {resp.text}.")
        result = resp.json()
        if self.debug:
            print("Download response:", result)
        return result

#a = cryptolib.aes("1234567812345678",2,b"1234123412341234")
#x = a.encrypt(b"1234123412341234")
#x.hex()
#'9ae8fd02b340288a0e7bbff0f0ba54d6'

if __name__ == "__main__":
    if not embedded:
        baseUrl = "http://localhost:9000"
    else:
        baseUrl = "https://llama.ok-lab-karlsruhe.de/platane/php"
    id = 1
    key = "00112233445566778899aabbccddeeff"


    pt = ProtoEngine("karlsruhe.freifunk.net", baseUrl, id, key)
    pt.setDebug(True)
    pt.connect()    
    pt.join()
    if pt.state == "connected":
        print("Join OK")
    else:
        print("Join failed")

    dummyData = b'This is a test payload for encryption.'
    resp = pt.upload(dummyData)
    
    name = resp.get("uuid", None)
    if not name:
        print("Upload failed")
    else:
        print("Upload OK, name:", name)
        resp = pt.check(name)
        print("Check OK, size:", resp.get("size",0))
        chunks = resp.get("chunks", 0)
        chunkSize = resp.get("chunksize", 0)
        print(f"Chunks: {chunks}, Chunk Size: {chunkSize}")
        
        while pt.state == "connected":
            time.sleep(10)
            for c in range(chunks):
                print(f"Downloading chunk {c+1}/{chunks}...")
                resp = pt.download(name, c)
                print("Downloaded chunk data:", resp)
                dt = binascii.a2b_base64(resp.get("data", ""))
                print("Decoded chunk data:", dt.decode('utf-8'))
                # Implement download logic here
                # resp = pt.download(name, c)
                # print("Downloaded chunk data:", resp)
        
    pt.disconnect()
    if pt.state != "offline":
        print("Disconnect failed")
    else:
        print("Disconnect OK")
            
    