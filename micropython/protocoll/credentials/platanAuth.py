import requests
import binascii
import json
import time
import network
from cryptolib import aes as AES
import esp32

class PlatanAuth:
    """
    Represents a Platane sensor device for secure communication and data upload using MicroPython.

    This class handles device configuration loading from NVS, WiFi connection, authentication with a remote server,
    and secure data transmission.

    Args:
        namespace (str): The NVS namespace to use for device configuration.

    Attributes:
        namespace (str): The NVS namespace.
        nvs (esp32.NVS): The NVS instance for persistent storage.
        deviceId (str): The unique device identifier.
        deviceKey (str): The device's secret key (hex-encoded).
        baseUrl (str): The base URL for server communication.
        ssid (str): The WiFi SSID.
        password (str): The WiFi password.
        token (str): The authentication token for server communication.

    Methods:
        get_id(): Returns the device ID.
        get_baseUrl(): Returns the base URL for server communication.
        connect_wifi(): Connects the device to the configured WiFi network.
        get_token(): Performs authentication with the server and retrieves an access token.
        pkcs7_pad(msg_bytes): Pads the given bytes using PKCS#7 padding.
    """

    def __init__(self, namespace):
        """
        Initializes the PlatanAuth instance and loads configuration from NVS.

        Args:
            namespace (str): The NVS namespace to use.
        """
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
        """
        Loads configuration values from non-volatile storage (NVS) into instance attributes.

        Retrieves the following blobs from NVS:
            - "deviceId": Sets self.deviceId (str or None)
            - "deviceKey": Sets self.deviceKey (str or None)
            - "baseurl": Sets self.baseUrl (str or None), formatted as an HTTPS URL with "/sensorUpload.php" appended
            - "ssid": Sets self.ssid (str or None)
            - "passwd": Sets self.password (str, empty string if not found)

        Each value is decoded from UTF-8. If a value is not found (length <= 0), the corresponding attribute is set to None or an empty string as appropriate.
        """
        buf = bytearray(64)
        l = self.nvs.get_blob("deviceId", buf)
        self.deviceId = buf[:l].decode('utf-8') if l > 0 else None
        l = self.nvs.get_blob("deviceKey", buf)
        self.deviceKey = buf[:l].decode('utf-8') if l > 0 else None
        l = self.nvs.get_blob("baseurl", buf)
        
        self.baseUrl = f"https://{buf[:l].decode('utf-8')}" if l > 0 else None
        l = self.nvs.get_blob("ssid", buf)
        self.ssid = buf[:l].decode('utf-8') if l > 0 else None
        l = self.nvs.get_blob("passwd", buf)
        self.password = buf[:l].decode('utf-8') if l > 0 else ""

    def connect_wifi(self):
        """
        Connects the device to a Wi-Fi network using the provided SSID and password.

        This method initializes the network interface in station mode, waits for it to become active,
        and then attempts to connect to the specified Wi-Fi network. It blocks execution until the
        network interface is active and the connection is established. Once connected, it prints the
        network configuration.

        Raises:
            Any exceptions raised by the underlying network or time modules.

        Note:
            Assumes that `self.ssid` and `self.password` are set to valid Wi-Fi credentials.
        """
        nic = network.WLAN(network.WLAN.IF_STA)
        while not nic.active():
            print("Waiting for network interface to become active...")
            time.sleep(1)
        nic.connect(self.ssid, self.password)
        while not nic.isconnected():
            print("Waiting for network connection...")
            time.sleep(1)
        print("Network connected:", nic.ifconfig())


    def get_baseUrl(self):
        """
        Returns the base URL for server communication.

        This method retrieves the base URL stored in the instance attribute `self.baseUrl`.

        Returns:
            str or None: The base URL if set, otherwise None.
        """
        return self.baseUrl

    def get_id(self):
        """
        Returns the device ID.

        This method retrieves the device ID stored in the instance attribute `self.deviceId`.

        Returns:
            str or None: The device ID if set, otherwise None.
        """
        return self.deviceId


    def get_token(self):
        """
        Authenticates the device with the server and retrieves an authentication token.

        This method performs a two-step authentication process:
        1. Sends a "join" request to the server to receive a challenge and IV.
        2. Encrypts the challenge using AES-CBC with the device key and IV, then sends the encrypted challenge back to the server.
        If successful, stores and returns the authentication token.

        Returns:
            str or None: The authentication token if successful, otherwise None.

        Side Effects:
            - Updates self.token with the received token or None on failure.
            - Prints error messages on failure.

        Raises:
            None: All exceptions are handled internally.
        """
        # Step 1: Join
        resp = requests.post(f"{self.baseUrl}/sensorUpload.php", json={
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

        # Step 2: Encrypt challenge
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

        resp = requests.post(f"{self.baseUrl}/sensorUpload.php", json={
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


    @staticmethod
    def pkcs7_pad(msg_bytes):
        """
        Applies PKCS#7 padding to the given byte sequence to ensure its length is a multiple of 16 bytes.

        Args:
            msg_bytes (bytes): The input byte sequence to be padded.

        Returns:
            bytes: The padded byte sequence, with PKCS#7 padding added to reach a multiple of 16 bytes.
        """
        pad_len = 16 - (len(msg_bytes) % 16)
        return msg_bytes + bytes([pad_len] * pad_len)


if __name__ == "__main__":
    import sys
    import os
    import binascii
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