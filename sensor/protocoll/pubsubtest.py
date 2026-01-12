import asyncio
import json
import time
import network
import binascii

topic = "bot/espsense"
bufSize = 2*2000  # 2*4000 seems to work at least once on base atom. 2*8000 fails. 
testBuf_ = bytearray(bufSize) # Simulated audio data
for i in range(bufSize):
    testBuf_[i] = i % 256
testBuf = binascii.b2a_base64(testBuf_).rstrip(b'\n').decode('ascii')

async def messages(client):  # Respond to incoming messages
    # If MQTT V5is used this would read
    # async for topic, msg, retained, properties in client.queue:
    async for topic, msg, retained in client.queue:
        #print(topic.decode(), msg.decode(), retained)
        print(topic.decode(), len(msg.decode()), retained)

async def up(client):  # Respond to connectivity being (re)established
    while True:
        await client.up.wait()  # Wait on an Event
        client.up.clear()
        await client.subscribe(topic, 1)  # renew subscriptions

async def main(client):
    global testBuf
    print('Connecting to broker...')
    await client.connect()
    print('Connected')
    for coroutine in (up, messages):
        asyncio.create_task(coroutine(client))
    n = 0
    while True:
        await asyncio.sleep(5)
        print('publish', n)
        payload = {"sensid":3,"temp":22.1,"hum":45.3,"press":1013.2,"audio":testBuf}
        # If WiFi is down the following will pause for the duration.
        await client.publish(topic, json.dumps(payload), qos = 1)
        n += 1


SSID = 'karlsruhe.freifunk.net'
PWD = ''  # No password
nic = network.WLAN(network.WLAN.IF_STA)
nic.active(False)
time.sleep(1)
if not nic.active():
    nic.active(True)
    time.sleep(1)
while not nic.active():
    print("Waiting for network interface to become active...")
    time.sleep(1)
nic.connect(SSID, PWD)
print("Network config:", nic.ifconfig())
nc = nic.ifconfig()[-1]
while nc == "0.0.0.0":
    print("Waiting for network connection...")
    nic.active(True)
    time.sleep(1)
    nc = nic.ifconfig()[-1]
print("Network connected, IP address:", nc)


# Local configuration
from mqtt_as import MQTTClient, config
config['ssid'] = SSID  # Optional on ESP8266
config['wifi_pw'] = PWD
config['server'] = '5.189.145.125'  # Change to suit e.g. 'iot.eclipse.org'
config['user'] = 'espsense' 
config['password'] = 'Chah]gikaish6iev4cha'
config["queue_len"] = 1  # Use event interface with default queue size
MQTTClient.DEBUG = True  # Optional: print diagnostic messages

client = MQTTClient(config)
try:
    asyncio.run(main(client))
finally:
    client.close()  # Prevent LmacRxBlk:1 errors
