import requests 
import json
import time
import sys
import binascii
if not sys.platform.lower().startswith("linux"):
    import network
    import cryptolib
    embedded = True
else:
    from Crypto.Cipher import AES
    embedded = False


class ProtoEngine:
    """
    Simple helper to encrypt/decrypt with cryptolib.aes and upload payloads to a server.
    Expects `baseUrl`, `cryptolib` and `requests` to be available in the module scope.
    Updated for RAG backend with conversation tracking.
    """
    def __init__(self, ssid, pwd, baseUrl, id, key):
        self.base_url = baseUrl
        self.pwd = pwd
        # current runtime state: one of "offline", "online", "joining", "connected"
        self._valid_states = {"offline", "online", "joining", "connected"}
        self.state = "offline"
        self.ssid = ssid
        self.debug = False
        self.id = id
        self.key = key
        self.session = None
        self.token = None
        self.conversation_id = None  # Track current conversation ID
        self.conversation_reset = False  # Track if conversation was reset

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
            try:
                if self.debug:
                    print(f"Connecting to network SSID: {self.ssid}, Password: {self.pwd}")
                nic.connect(self.ssid, self.pwd)
            except Exception as e:
                if self.debug:
                    print(f"Failed to connect to network: {e}")
                nic.disconnect()
                nic.active(False)
                time.sleep(1)
                nic.active(True)
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
        r = requests.post(self.base_url + "/sensorRagUpload.php", json={"id": self.id, "command": "join"})
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
            if embedded:
                crypt = cryptolib.aes(bytes.fromhex(self.key),2,bytes.fromhex(iv))
                response = crypt.encrypt(bytes.fromhex(challenge))
            else:
                crypt = AES.new(bytes.fromhex(self.key), AES.MODE_CBC, bytes.fromhex(iv))
                response = crypt.encrypt(bytes.fromhex(challenge))
        except:
            raise ValueError("Failed to initialize AES cipher with provided key/iv.")
        payload = {"command": "challenge", "session": self.session, "id": self.id, "challenge": response.hex()}
        if self.debug:
            print("Challenge payload:", payload)
        r2 = requests.post(self.base_url + "/sensorRagUpload.php", json=payload)
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
    

    def upload(self, data, format="adpcm"):
            if self.state != "connected":
                raise ValueError("Not connected. Cannot upload data.")
            payload = {"command": "data", "token": self.token, "session": self.session, "id": self.id, "format": format, "data": binascii.b2a_base64(data).decode('utf-8')}
            resp = requests.post(self.base_url + "/sensorRagUpload.php", json=payload)
            if resp.status_code != 200:
                self._transit(self.state, "online")
                if self.debug:
                    print("Upload response:", resp.status_code, resp.text)
                raise ValueError(f"Upload request failed with status code {resp.status_code}, {resp.text}.")
            result = resp.json()
            
            # Update conversation tracking
            if result.get("status") == "ok":
                new_conversation_id = result.get("conversation_id")
                conversation_reset = result.get("conversation_reset", False)
                
                if self.debug:
                    print(f"Conversation tracking - ID: {new_conversation_id}, Reset: {conversation_reset}")
                
                # Update local conversation state
                if conversation_reset or self.conversation_id != new_conversation_id:
                    if self.debug and conversation_reset:
                        print("Conversation was reset by server (stop command or timeout)")
                    self.conversation_reset = conversation_reset
                else:
                    self.conversation_reset = False
                
                self.conversation_id = new_conversation_id
            
            if self.debug:
                print("Upload response:", result)
            return result

    # send a stop command, no data
    def stop(self):
        """NEW: Stop command"""
        if self.debug:
            print("Sending stop command")
        if self.state != "connected":
            print("Not connected. Cannot send stop command.")
            return {"status": "not_connected"}
        payload = {"command": "stop", "token": self.token, "id": self.id}
        resp = requests.post(self.base_url + "/sensorRagUpload.php", json=payload)
        if resp.status_code != 200:
            if self.debug:
                print("Stop response:", resp.status_code, resp.text)
            raise ValueError(f"Stop request failed with status code {resp.status_code}, {resp.text}.")
        result = resp.json()
        if self.debug:
            print("Stop response:", result)
        return result

        
    # Legacy methods for compatibility with old backend - not used with RAG
    def check(self, name, format="adpcm"):
        """DEPRECATED: Not used with RAG backend"""
        if self.debug:
            print("WARNING: check() is deprecated with RAG backend - handling is done server-side")
        if self.state != "connected":
            raise ValueError("Not connected. Cannot check data.")
        payload = {"command": "check", "token": self.token, "id": self.id, "name": name, "format": format}
        resp = requests.post(self.base_url + "/sensorDownload.php", json=payload)
        if resp.status_code == 408:
            if self.debug:
                print("Check response: file not ready, retry later.")
            return resp.json()
        if resp.status_code != 200:
            self._transit(self.state, "online")
            if self.debug:
                print("Check response:", resp.status_code, resp.text)
            raise ValueError(f"Check request failed with status code {resp.status_code}, {resp.text}.")
        result = resp.json()
        if self.debug:
            print("Check response:", result)
        return result

    def download(self, name, chunk, format="adpcm"):
        """DEPRECATED: Not used with RAG backend"""
        if self.debug:
            print("WARNING: download() is deprecated with RAG backend - handling is done server-side")
        if self.state != "connected":
            raise ValueError("Not connected. Cannot download data.")
        payload = {"command": "down", "token": self.token, "id": self.id, "name": name, "chunk": chunk, "format": format}
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

