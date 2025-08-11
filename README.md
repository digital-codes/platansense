
# Build

use proper idf version (e.g. 5.2)

checkout micropython version

build mpy-cross first 

cd ports/esp32
make BOARD=ESP32_GENERIC_S3 BOARD_VARIANT=SPIRAM_OCT submodules
make BOARD=ESP32_GENERIC_S3 BOARD_VARIANT=SPIRAM_OCT



# Flash

esptool --chip esp32s3 -p /dev/ttyACM0 -b 460800 --before default_reset --after hard_reset write_flash --flash_mode dio --flash_size 8MB --flash_freq 80m 0x0 build-ESP32_GENERIC_S3-SPIRAM_OCT/bootloader/bootloader.bin 0x8000 build-ESP32_GENERIC_S3-SPIRAM_OCT/partition_table/partition-table.bin 0x10000 build-ESP32_GENERIC_S3-SPIRAM_OCT/micropython.bin

# Extending

## MpyModule C

See https://docs.micropython.org/en/latest/develop/natmod.html


export PATH=$PATH:/opt/esp32/idf/tools/xtensa-esp-elf/esp-14.2.0_20241119/xtensa-esp-elf/bin

micropython/mpyMods/adpcm$ make ARCH=xtensawin
GEN build/adpcm.config.h
CC adpcm.c
LINK build/adpcm.o
arch:         EM_XTENSA
text size:    800
rodata size:  512
bss size:     0
GOT entries:  10
GEN adpcm.mpy
kugel@tux3:~/temp/micropython/mpyMods/adpcm$ 


### ADPCM


Example:
import adpcm
import random
a = bytearray(1000)
b = bytearray([random.randint(0,256) for i in range(len(a))])
len(b)
c = adpcm.encode(b)
len(c)
d = adpcm.decode(c)
len(d)

or encode_into, decode_into
