try:
    from micropython import const
except ImportError:
    def const(x): return x

import time

# 7-bit I2C address (0x30 >> 1 from your C driver)
ES8311_I2C_ADDR = const(0x18)

# --- Register map (from es8311.h) ---

ES8311_RESET_REG00      = const(0x00)

ES8311_CLK_MANAGER_REG01 = const(0x01)
ES8311_CLK_MANAGER_REG02 = const(0x02)
ES8311_CLK_MANAGER_REG03 = const(0x03)
ES8311_CLK_MANAGER_REG04 = const(0x04)
ES8311_CLK_MANAGER_REG05 = const(0x05)
ES8311_CLK_MANAGER_REG06 = const(0x06)
ES8311_CLK_MANAGER_REG07 = const(0x07)
ES8311_CLK_MANAGER_REG08 = const(0x08)

ES8311_SDPIN_REG09      = const(0x09)
ES8311_SDPOUT_REG0A     = const(0x0A)

ES8311_SYSTEM_REG0B     = const(0x0B)
ES8311_SYSTEM_REG0C     = const(0x0C)
ES8311_SYSTEM_REG0D     = const(0x0D)
ES8311_SYSTEM_REG0E     = const(0x0E)
ES8311_SYSTEM_REG0F     = const(0x0F)
ES8311_SYSTEM_REG10     = const(0x10)
ES8311_SYSTEM_REG11     = const(0x11)
ES8311_SYSTEM_REG12     = const(0x12)
ES8311_SYSTEM_REG13     = const(0x13)
ES8311_SYSTEM_REG14     = const(0x14)

# ADC
ES8311_ADC_REG15        = const(0x15)
ES8311_ADC_REG16        = const(0x16)
ES8311_ADC_REG17        = const(0x17)
ES8311_ADC_REG18        = const(0x18)
ES8311_ADC_REG19        = const(0x19)
ES8311_ADC_REG1A        = const(0x1A)
ES8311_ADC_REG1B        = const(0x1B)
ES8311_ADC_REG1C        = const(0x1C)

# DAC
ES8311_DAC_REG31        = const(0x31)
ES8311_DAC_REG32        = const(0x32)  # DAC volume
ES8311_DAC_REG33        = const(0x33)
ES8311_DAC_REG37         = const(0x37)

ES8311_GPIO_REG44        = const(0x44)
ES8311_GP_REG45          = const(0x45)



# internal clock uses fs * 256 in your C driver
#_MCLK_DIV_FRE = const(256)

# pre-computed subset of coeff_div[] from your C code
# (rows with mclk = fs * 256)
#
# fields: pre_div, pre_multi, adc_div, dac_div, fs_mode, lrck_h, lrck_l,
#         bclk_div, adc_osr, dac_osr
#
# You mainly care about: 11025, 16000, 22050, 44100
_COEFFS = {
    11025: dict(pre_div=1, pre_multi=1, adc_div=1, dac_div=1,
                fs_mode=0, lrck_h=0x00, lrck_l=0xFF,
                bclk_div=4, adc_osr=0x10, dac_osr=0x20),

    16000: dict(pre_div=1, pre_multi=1, adc_div=1, dac_div=1,
                fs_mode=0, lrck_h=0x00, lrck_l=0xFF,
                bclk_div=4, adc_osr=0x10, dac_osr=0x20),

    22050: dict(pre_div=1, pre_multi=1, adc_div=1, dac_div=1,
                fs_mode=0, lrck_h=0x00, lrck_l=0xFF,
                bclk_div=4, adc_osr=0x10, dac_osr=0x10),

    44100: dict(pre_div=1, pre_multi=1, adc_div=1, dac_div=1,
                fs_mode=0, lrck_h=0x00, lrck_l=0xFF,
                bclk_div=4, adc_osr=0x10, dac_osr=0x10),

}


class ES8311:
    """
    ES8311 MicroPython driver (I2C control only).

    - Codec in I2S **slave** mode.
    - ESP32(/C3/S3) is I2S **master** (BCLK/LRCK).
    - ES8311 internal MCLK derived from SCLK/BCLK (no external MCLK pin).
    """

    def __init__(self, i2c, addr=ES8311_I2C_ADDR, mclk_from_sclk=True):
        self.i2c = i2c
        self.addr = addr
        self._mclk_from_sclk = mclk_from_sclk
        self.debug = False

    # ---------- low-level I2C ----------

    def write_reg(self, reg, val):
        if self.debug:
            print("ES8311: write reg 0x%02X = 0x%02X" % (reg, val))
        self.i2c.writeto_mem(self.addr, reg, bytes([val & 0xFF]))

    def read_reg(self, reg):
        val = self.i2c.readfrom_mem(self.addr, reg, 1)[0]
        if self.debug:
            print("ES8311: read reg 0x%02X = 0x%02X" % (reg, val))
        return val

    def update_reg(self, reg, mask, value):
        cur = self.read_reg(reg)
        cur = (cur & ~mask) | (value & mask)
        self.write_reg(reg, cur)

    # ---------- basic control ----------

    def reset(self):
        self.write_reg(ES8311_RESET_REG00, 0x80)
        time.sleep_ms(50)

    def mute(self, enable=True):
        regv = self.read_reg(ES8311_DAC_REG31) & 0x9F
        if enable:
            regv |= 0x60  # set bits 5 & 6
        self.write_reg(ES8311_DAC_REG31, regv)

    def set_volume(self, vol):
        """Volume 0..100%, mapped to [0x00..0xBF]."""
        if vol < 0:
            vol = 0
        if vol > 100:
            vol = 100
        reg = int(0xBF * vol / 100)
        self.write_reg(ES8311_DAC_REG32, reg)

    # ---------- I2S interface ----------

    def set_bits_per_sample(self, bits=16):
        """
        16 or 32-bit samples; matches es8311_set_bits_per_sample() logic.
        """
        adc_iface = self.read_reg(ES8311_SDPOUT_REG0A)
        dac_iface = self.read_reg(ES8311_SDPIN_REG09)

        # clear width bits first
        adc_iface &= ~(0x1C)
        dac_iface &= ~(0x1C)

        if bits == 16:
            adc_iface |= 0x0C
            dac_iface |= 0x0C
        elif bits == 32:
            adc_iface |= 0x10
            dac_iface |= 0x10
        else:
            # default to 16-bit
            adc_iface |= 0x0C
            dac_iface |= 0x0C

        self.write_reg(ES8311_SDPOUT_REG0A, adc_iface)
        self.write_reg(ES8311_SDPIN_REG09, dac_iface)

    def set_format(self, fmt="i2s"):
        """
        fmt: "i2s", "lj" (left-justified), "dsp" (DSP mode A).
        """
        adc_iface = self.read_reg(ES8311_SDPOUT_REG0A)
        dac_iface = self.read_reg(ES8311_SDPIN_REG09)

        fmt = fmt.lower()
        if fmt == "i2s":
            adc_iface &= 0xFC
            dac_iface &= 0xFC
        elif fmt == "lj":
            adc_iface &= 0xFC
            dac_iface &= 0xFC
            adc_iface |= 0x01
            dac_iface |= 0x01
        elif fmt == "dsp":
            adc_iface &= 0xDC
            dac_iface &= 0xDC
            adc_iface |= 0x03
            dac_iface |= 0x03
        else:
            adc_iface &= 0xFC
            dac_iface &= 0xFC

        self.write_reg(ES8311_SDPOUT_REG0A, adc_iface)
        self.write_reg(ES8311_SDPIN_REG09, dac_iface)

    # ---------- clock / sample rate ----------

    def _set_mclk_source(self):
        """
        Select internal MCLK source:

        - from SCLK/BCLK (internal synthesis) if self._mclk_from_sclk=True
        - from MCLK pin otherwise
        """
        regv = self.read_reg(ES8311_CLK_MANAGER_REG01)
        if self._mclk_from_sclk:
            regv |= 0x80   # bit7 = 1 -> FROM_SCLK_PIN (your C driver)
        else:
            regv &= 0x7F   # bit7 = 0 -> FROM_MCLK_PIN
        self.write_reg(ES8311_CLK_MANAGER_REG01, regv)

    def set_sample_rate(self, sample_rate):
        """
        Configure ES8311 clocks for given sample_rate (Hz).

        Uses same coeff table and formulas as es8311_config_sample().
        For your use-case: 11025, 16000, 22050, 44100 are fully supported.
        """
        if sample_rate not in _COEFFS:
            raise ValueError("Unsupported sample rate: %d" % sample_rate)

        cfg = _COEFFS[sample_rate]

        # --- CLK_MANAGER_REG02: pre_div and pre_multi / DIG_MCLK source ---
        regv = self.read_reg(ES8311_CLK_MANAGER_REG02) & 0x07

        # bits7..5: (pre_div-1)
        regv |= (cfg["pre_div"] - 1) << 5

        # bits4..3: multiplier / SCLK-based DIG_MCLK
        if self._mclk_from_sclk:
            print("ES8311: using SCLK-based MCLK synthesis")
            # from your C code:
            # datmp = 3 -> DIG_MCLK = LRCK * 256 = BCLK * 8 (16-bit slots)
            # 8k special case (BCLK >= 512k, 32-bit slots) -> DIG_MCLK = BCLK * 4
            datmp = 3
        else:
            pre_multi = cfg["pre_multi"]
            if pre_multi == 1:
                datmp = 0
            elif pre_multi == 2:
                datmp = 1
            elif pre_multi == 4:
                datmp = 2
            elif pre_multi == 8:
                datmp = 3
            else:
                datmp = 0

        regv |= (datmp & 0x03) << 3
        self.write_reg(ES8311_CLK_MANAGER_REG02, regv)

        # --- CLK_MANAGER_REG05: adc_div & dac_div ---
        regv = self.read_reg(ES8311_CLK_MANAGER_REG05) & 0x00
        regv |= (cfg["adc_div"] - 1) << 4
        regv |= (cfg["dac_div"] - 1) << 0
        self.write_reg(ES8311_CLK_MANAGER_REG05, regv)

        # --- CLK_MANAGER_REG03/04: fs_mode, adc_osr, dac_osr ---
        regv = self.read_reg(ES8311_CLK_MANAGER_REG03) & 0x80
        regv |= (cfg["fs_mode"] & 0x03) << 6
        regv |= cfg["adc_osr"] & 0x3F
        self.write_reg(ES8311_CLK_MANAGER_REG03, regv)

        regv = self.read_reg(ES8311_CLK_MANAGER_REG04) & 0x80
        regv |= cfg["dac_osr"] & 0x3F
        self.write_reg(ES8311_CLK_MANAGER_REG04, regv)

        # --- CLK_MANAGER_REG07/08: LRCK divider ---
        regv = self.read_reg(ES8311_CLK_MANAGER_REG07) & 0xC0
        regv |= cfg["lrck_h"] & 0x3F
        self.write_reg(ES8311_CLK_MANAGER_REG07, regv)

        regv = self.read_reg(ES8311_CLK_MANAGER_REG08) & 0x00
        regv |= cfg["lrck_l"] & 0xFF
        self.write_reg(ES8311_CLK_MANAGER_REG08, regv)

        # --- CLK_MANAGER_REG06: BCLK divider & SCLK invert ---
        regv = self.read_reg(ES8311_CLK_MANAGER_REG06) & 0xE0
        bclk_div = cfg["bclk_div"]
        if bclk_div < 19:
            regv |= (bclk_div - 1) & 0x1F
        else:
            regv |= bclk_div & 0x1F

        # no SCLK invert (INVERT_SCLK = 0 in your C code)
        regv &= ~(0x20)
        self.write_reg(ES8311_CLK_MANAGER_REG06, regv)

    # ---------- init / start / stop ----------

    def init_default(self, sample_rate=44100, bits=16, fmt="i2s", slave=True):
        """
        Rough equivalent of es8311_codec_init() + es8311_config_sample().

        - sets basic system regs
        - selects MCLK source (from SCLK/BCLK by default)
        - sets I2S format & bits
        - configures sample rate via coeff table
        """
        # improve I2C noise immunity (same double-write as C)
        self.write_reg(ES8311_GPIO_REG44, 0x08)
        self.write_reg(ES8311_GPIO_REG44, 0x08)

        self.write_reg(ES8311_CLK_MANAGER_REG01, 0x30)
        self.write_reg(ES8311_CLK_MANAGER_REG02, 0x00)
        self.write_reg(ES8311_CLK_MANAGER_REG03, 0x10)
        self.write_reg(ES8311_ADC_REG16, 0x24)
        self.write_reg(ES8311_CLK_MANAGER_REG04, 0x10)
        self.write_reg(ES8311_CLK_MANAGER_REG05, 0x00)

        self.write_reg(ES8311_SYSTEM_REG0B, 0x00)
        self.write_reg(ES8311_SYSTEM_REG0C, 0x00)
        self.write_reg(ES8311_SYSTEM_REG10, 0x1F)
        self.write_reg(ES8311_SYSTEM_REG11, 0x7F)

        # soft reset
        self.write_reg(ES8311_RESET_REG00, 0x80)
        time.sleep_ms(10)

        # master/slave
        regv = self.read_reg(ES8311_RESET_REG00)
        if slave:
            regv &= 0xBF
        else:
            regv |= 0x40
        self.write_reg(ES8311_RESET_REG00, regv)

        # enable clocks
        self.write_reg(ES8311_CLK_MANAGER_REG01, 0x3F)

        # MCLK source: from SCLK/BCLK or from dedicated MCLK pin
        self._set_mclk_source()

        # mclk/sclk invert flags as in C (no invert)
        regv = self.read_reg(ES8311_CLK_MANAGER_REG01)
        regv &= ~(0x40)
        self.write_reg(ES8311_CLK_MANAGER_REG01, regv)

        regv = self.read_reg(ES8311_CLK_MANAGER_REG06)
        regv &= ~(0x20)
        self.write_reg(ES8311_CLK_MANAGER_REG06, regv)

        # some extra tuning
        self.write_reg(ES8311_SYSTEM_REG13, 0x10)
        self.write_reg(ES8311_ADC_REG1B, 0x0A)
        self.write_reg(ES8311_ADC_REG1C, 0x6A)

        # I2S iface
        self.set_bits_per_sample(bits)
        self.set_format(fmt)

        # clocking / sample rate
        self.set_sample_rate(sample_rate)

    def start(self, adc=False, dac=True):
        """
        Enable paths (like es8311_start()).
        """
        # gate / ungate I2S
        dac_iface = self.read_reg(ES8311_SDPIN_REG09) & 0xBF
        adc_iface = self.read_reg(ES8311_SDPOUT_REG0A) & 0xBF

        # start with both gated (bit6)
        adc_iface |= (1 << 6)
        dac_iface |= (1 << 6)

        if adc:
            adc_iface &= ~(1 << 6)
        if dac:
            dac_iface &= ~(1 << 6)

        self.write_reg(ES8311_SDPIN_REG09, dac_iface)
        self.write_reg(ES8311_SDPOUT_REG0A, adc_iface)

        # power-up sequence
        self.write_reg(ES8311_ADC_REG17, 0xBF)
        self.write_reg(ES8311_SYSTEM_REG0E, 0x02)
        self.write_reg(ES8311_SYSTEM_REG12, 0x00)
        self.write_reg(ES8311_SYSTEM_REG14, 0x1A)

        self.write_reg(ES8311_SYSTEM_REG0D, 0x01)
        self.write_reg(ES8311_ADC_REG15, 0x40)
        self.write_reg(ES8311_DAC_REG37, 0x08)
        self.write_reg(ES8311_GP_REG45, 0x00)
        self.write_reg(ES8311_GPIO_REG44, 0x58)

        self.set_volume(80)
        self.mute(False)

    def stop(self):
        """
        Simple suspend / stop.
        """
        self.write_reg(ES8311_DAC_REG32, 0x00)
        self.write_reg(ES8311_ADC_REG17, 0x00)
        self.write_reg(ES8311_SYSTEM_REG0E, 0xFF)
        self.write_reg(ES8311_SYSTEM_REG12, 0x02)
        self.write_reg(ES8311_SYSTEM_REG14, 0x00)
        self.write_reg(ES8311_SYSTEM_REG0D, 0xFA)
        self.mute(True)
        

if __name__ == "__main__":
    from machine import I2C, Pin
    #from es8311 import ES8311

    # adapt pins & I2C bus to your board
    i2c = I2C(0, scl=Pin(39), sda=Pin(38), freq=400000)

    codec = ES8311(i2c)
    codec.debug = True

    codec.reset()
    codec.init_default(bits=16, fmt="i2s", slave=True)
    codec.start(adc=False, dac=True)   # playback only

    codec.set_volume(60)
    codec.mute(False)

    # ... now drive I2S peripheral of the MCU for audio playback
    time.sleep(1)

    codec.stop()
    print("Done.")
    