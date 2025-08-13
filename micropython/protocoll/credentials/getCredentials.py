import esp32

namespace = "platane"

nvs = esp32.NVS(namespace)
buf = bytearray(64)
l = nvs.get_blob("deviceId", buf)
if l > 0:
    deviceId = buf[:l].decode('utf-8')
    print(f"Found deviceId: {deviceId}")
else:
    print("No deviceId found, setting new credentials.")

l = nvs.get_blob("deviceKey", buf)
if l > 0:
    deviceKey = buf[:l].decode('utf-8')
    print(f"Found deviceKey: {deviceKey}")
else:
    print("No deviceKey found, setting new credentials.")

l = nvs.get_blob("baseurl", buf)
if l > 0:
    baseUrl = f"https://{buf[:l].decode('utf-8')}"
    print(f"Found baseUrl: {baseUrl}")
else:
    print("No baseUrl found, setting new credentials.")

l = nvs.get_blob("ssid", buf)
if l > 0:
    ssid = buf[:l].decode('utf-8')
    print(f"Found ssid: {ssid}")
else:
    print("No ssid found, setting new credentials.")

l = nvs.get_blob("passwd", buf)
if l > 0:
    password = buf[:l].decode('utf-8')
    print(f"Found password: {password}")
else:
    print("No password found, setting new credentials.")
    
    