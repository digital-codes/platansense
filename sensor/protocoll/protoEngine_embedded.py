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

if __name__ == "__main__":
    if not embedded:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('-u', '--url', default='http://localhost:8000', help='Base URL for the server')
        parser.add_argument('-i', '--input', required=True, help='Audio file to upload (ADPCM format)')
        parser.add_argument('-f', '--format', default='adpcm', choices=['wav', 'adpcm'], help='Audio format (default: adpcm)')
        parser.add_argument('-id', '--sensor-id', type=int, default=1, help='Sensor ID (default: 1)')
        parser.add_argument('-k', '--key', default='00112233445566778899aabbccddeeff', help='Sensor key (hex)')
        args = parser.parse_args()
        baseUrl = args.url
        audio_file = args.input
        format = args.format
        id = args.sensor_id
        key = args.key
    else:
        baseUrl = "https://llama.ok-lab-karlsruhe.de/platane/php"
        audio_file = None
        format = "adpcm"
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
        pt.disconnect()
        sys.exit(1)

    # Load audio file if specified
    if audio_file and not embedded:
        try:
            with open(audio_file, 'rb') as f:
                audioData = f.read()
            print(f"Loaded audio file: {audio_file} ({len(audioData)} bytes)")
            
            # Sensor always sends ADPCM format
            if format == "adpcm":
                # No conversion needed, upload ADPCM data directly
                print("Format: ADPCM (sensor default format)")
            else:
                print(f"Warning: Sensor format is '{format}' but should be 'adpcm'")
                print("ADPCM is the standard sensor format for this application")
                format = "adpcm"
                
        except FileNotFoundError:
            print(f"Audio file not found: {audio_file}")
            pt.disconnect()
            sys.exit(1)
        except Exception as e:
            print(f"Error loading audio file: {e}")
            pt.disconnect()
            sys.exit(1)
    else:
        print("No audio file specified, using dummy data (will not produce transcription)")
        audioData = b'This is a test payload for encryption.'

    # Upload audio data
    print(f"Uploading audio data ({len(audioData)} bytes, format: {format})...")
    resp = pt.upload(audioData, format=format)
    
    # Check response from new RAG backend
    status = resp.get("status", None)
    if not status:
        print(f"Upload failed: Invalid response format")
        print(f"Response: {resp}")
        pt.disconnect()
        sys.exit(1)
    
    print(f"\n{'='*60}")
    print(f"RAG Processing Results")
    print(f"{'='*60}")
    print(f"Status: {status}")
    print(f"UUID: {resp.get('uuid', 'N/A')}")
    
    # Display conversation tracking information
    conversation_id = resp.get("conversation_id")
    conversation_reset = resp.get("conversation_reset", False)
    conversation_timestamp = resp.get("conversation_timestamp")
    message_count = resp.get("message_count", 0)
    
    print(f"\n🔗 Conversation Tracking:")
    print(f"  ID: {conversation_id if conversation_id else 'N/A'}")
    print(f"  Reset: {'Yes (stop/timeout)' if conversation_reset else 'No (continued)'}")
    if conversation_timestamp:
        import datetime
        dt = datetime.datetime.fromtimestamp(conversation_timestamp)
        print(f"  Started: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Messages: {message_count}")
    
    if status == "transcription_failed":
        print(f"\n❌ Error: Audio transcription failed")
        print(f"{'='*60}")
    elif status == "ok":
        # Display transcription
        transcription = resp.get("transcription", "")
        print(f"\n📝 Transcription:")
        if transcription:
            print(f"  {transcription}")
        else:
            print(f"  (empty)")
        
        # Display classification
        classification = resp.get("classification", [])
        print(f"\n🏷️  Classification:")
        if classification:
            for category in classification:
                print(f"  - {category}")
        else:
            print(f"  No categories detected")
        
        # Display response
        response = resp.get("response", "")
        print(f"\n💬 AI Response:")
        if response:
            print(f"  {response}")
        else:
            print(f"  (empty)")
        
        # Display audio playback status
        audio_played = resp.get("audio_played", False)
        print(f"\n🔊 Audio Playback: {'✅ Success' if audio_played else '❌ Failed'}")
        print(f"{'='*60}\n")
        print("✅ Complete - Backend handled transcription, classification, and audio playback")
        
    elif status.startswith("failed"):
        print(f"\n❌ Error: Processing failed")
        error_msg = resp.get("error", "Unknown error")
        print(f"Details: {error_msg}")
        print(f"{'='*60}")
    else:
        print(f"\n⚠️  Unknown status: {status}")
        print(f"{'='*60}")
    
    pt.disconnect()
    if pt.state != "offline":
        print("Disconnect failed")
    else:
        print("Disconnect OK")
            
    
