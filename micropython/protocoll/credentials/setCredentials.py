import esp32

baseurl = bytes("llama.ok-lab-karlsruhe.de/platane/php", "utf-8")
deviceId = bytes("f09e9e3278c0", "utf-8")
deviceKey = bytes("89fa7c324cdcd7bb962301790d5f8809", "utf-8")
ssid = bytes("karlsruhe.freifunk.net", "utf-8")
passwd = bytes("", "utf-8")

namespace = "platane"

nvs = esp32.NVS(namespace)
nvs.set_blob("deviceId", deviceId)
nvs.set_blob("deviceKey", deviceKey)
nvs.set_blob("baseurl", baseurl)
nvs.set_blob("ssid", ssid)
nvs.set_blob("passwd", passwd)
nvs.commit()

print("Credentials set successfully.")

