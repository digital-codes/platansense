# backlight.py
# MicroPython driver for the LP5562 back‑light controller on M5Stack AtomS3R
# ---------------------------------------------------------------
# Wiring (as per the AtomS3R schematic you supplied)
#   AtomS3R GPIO21  ->  LP5562 SDA
#   AtomS3R GPIO22  ->  LP5562 SCL
#   LP5562 ADDR_SEL0 = GND, ADDR_SEL1 = GND  →  I²C address 0x30 (7‑bit)
#   LP5562 W‑LED output → MOSFET → back‑light LED array
# ---------------------------------------------------------------

from machine import I2C, Pin
import time


class LP5562:
    """Driver for the LP5562 back‑light controller."""
    # --------------------------------------------------------------------
    # LP5562 constants (taken from the datasheet you attached)
    # --------------------------------------------------------------------
    # Static class constants
    # Register map (addresses are 8‑bit)
    REG_ENABLE: int      = 0x00   # LOG_EN | CHIP_EN | ENGx_EXEC
    REG_OP_MODE: int     = 0x01   # Engine operation mode
    REG_W_PWM: int       = 0x0E   # White‑LED PWM (direct‑control register)
    REG_CONFIG: int      = 0x08   # PWM_HF, PS_EN, CLK_DET_EN, INT_CLK_EN
    REG_RESET: int       = 0x0D   # Reset register (write 0xFF to reset everything)

    # Bit masks for the ENABLE register
    BIT_CHIP_EN: int     = 1 << 6   # Master enable
    BIT_LOG_EN: int      = 1 << 7   # Logarithmic PWM (optional – keep linear for now)

    # Bit masks for the CONFIG register
    CFG_PWM_HF: int      = 1 << 6   # 0 = 256 Hz, 1 = 558 Hz
    CFG_PS_EN: int       = 1 << 5   # Power‑save enable
    CFG_CLK_DET_EN: int  = 1 << 0   # Clock‑detect enable (0 = external clock)
    CFG_INT_CLK_EN: int  = 1 << 1   # Internal‑clock enable (0 = external clock)

    LP5562_I2C_ADDR: int = 0x30  # 7‑bit address (WRITE = 0x60, READ = 0x61)

    def __init__(self, i2c_inst=None, sda=None, scl=None, i2c_id=None, freq=None, addr=LP5562_I2C_ADDR):
        # Use provided I2C instance or create one from pins
        if i2c_inst is not None:
            self.i2c = i2c_inst
        else:
            # fall back to module-level SDA/SCL if not provided
            if i2c_id is None:
                i2c_id = 0  # default I2C peripheral
            if freq is None:
                freq = 400_000  # default frequency 400kHz
            if sda is None:
                sda = 45  # default SDA pin for AtomS3R
            if scl is None:
                scl = 0   # default SCL pin for AtomS3R
            sda_pin = sda
            scl_pin = scl
            self.i2c = I2C(i2c_id, scl=Pin(scl_pin), sda=Pin(sda_pin), freq=freq)

        self.addr = addr

    # Low-level helpers
    def write_reg(self, reg, value):
        self.i2c.writeto_mem(self.addr, reg, bytes([value]))

    def read_reg(self, reg):
        return int.from_bytes(self.i2c.readfrom_mem(self.addr, reg, 1), 'little')

    # High-level API
    def init(self):
        """Minimal start‑up sequence from the datasheet."""
        if self.addr not in self.i2c.scan():
            raise RuntimeError("LP5562 not found on the I²C bus (addr 0x{:02X})".format(self.addr))

        # Reset
        self.write_reg(self.REG_RESET, 0xFF)
        time.sleep_ms(2)

        # Enable chip (keep LOG_EN = 0 for linear PWM)
        self.write_reg(self.REG_ENABLE, self.BIT_CHIP_EN)

        # Configure clock/PWM
        cfg_val = 0
        cfg_val &= ~self.CFG_PWM_HF
        cfg_val &= ~self.CFG_CLK_DET_EN
        cfg_val &= ~self.CFG_INT_CLK_EN
        cfg_val |= self.CFG_PS_EN
        self.write_reg(self.REG_CONFIG, cfg_val)

        # Disable engines; use direct W PWM
        self.write_reg(self.REG_OP_MODE, 0x00)

    def set_backlight_brightness(self, level):
        level = max(0, min(255, int(level)))
        self.write_reg(self.REG_W_PWM, level)
        
    def backlight_on(self, brightness=255):
        self.set_backlight_brightness(brightness)

    def backlight_off(self):
        self.set_backlight_brightness(0)

    def fade_to(self, target, step=5, delay_ms=30):
        current = self.read_reg(self.REG_W_PWM)
        target = max(0, min(255, int(target)))
        while current != target:
            if current < target:
                current = min(current + step, target)
            else:
                current = max(current - step, target)
            self.write_reg(self.REG_W_PWM, current)
            time.sleep_ms(delay_ms)

# --------------------------------------------------------------------
# Demo routine (run when the script is executed directly)
# --------------------------------------------------------------------
if __name__ == '__main__':
    try:
        # --------------------------------------------------------------------
        # I²C configuration
        # --------------------------------------------------------------------
        I2C_ID = 0                       # ESP‑S3 I²C peripheral 0
        SDA_PIN = 45                     # AtomS3R SDA
        SCL_PIN = 0                     # AtomS3R SCL
        I2C_FREQ = 400_000               # 400 kHz fast‑mode (well within LP5562 spec)
        LP5562_I2C_ADDR = 0x30            # 7‑bit address (WRITE = 0x60, READ = 0x61)

        i2c = I2C(I2C_ID, scl=Pin(SCL_PIN), sda=Pin(SDA_PIN), freq=I2C_FREQ)
            
        lp5562 = LP5562(i2c_inst=i2c,addr=LP5562_I2C_ADDR)


        print("Initialising LP5562...")
        lp5562.init()
        print("Back‑light demo starting – press Ctrl‑C to stop.")
        while True:
            print("→ Off")
            lp5562.backlight_off()
            time.sleep(2)

            print("→ 30 %")
            lp5562.backlight_on(77)          # ≈30 % of 255
            time.sleep(2)

            print("→ Fade to 100 %")
            lp5562.fade_to(255, step=8, delay_ms=20)
            time.sleep(2)

            print("→ Fade to 0 %")
            lp5562.fade_to(0, step=8, delay_ms=20)
            time.sleep(2)

    except KeyboardInterrupt:
        print("\nDemo stopped – turning back‑light off.")
        lp5562.backlight_off()
    except Exception as e:
        print("Error:", e)
        
        