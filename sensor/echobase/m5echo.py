# M5EchoBase.py
#
# High-level MicroPython helper for the M5Stack Atomic Echo Base.
#
# Requires:
#   - machine.I2C, machine.I2S, machine.Pin (ESP32)
#   - es8311 driver providing an ES8311 class:
#       from es8311 import ES8311
#
# This module mimics the Arduino M5EchoBase API closely:
#   - init(...)
#   - setSpeakerVolume(0..100)
#   - setMicGain(...)
#   - setMicPGAGain(digital_mic, gain)
#   - setMicAdcVolume(0..100)
#   - setMute(bool)
#   - getBufferSize(duration_s, sample_rate=None)
#   - getDuration(size_bytes, sample_rate=None)
#   - record(buffer, size=None)
#   - play(buffer, size=None)
#   - record_to_file(path, size_bytes, chunk_size=1024)
#   - play_from_file(path, chunk_size=1024)
#
# Default pinmap is for ATOMS3/ATOMS3R:
#   I2C SDA = 38, I2C SCL = 39
#   I2S DIN = 7,  I2S WS  = 6
#   I2S DOUT = 5, I2S BCK = 8
#
# For original ATOM (Matrix / Lite), call init(...) with:
#   i2c_sda=25, i2c_scl=21,
#   i2s_di=23, i2s_ws=19, i2s_do=22, i2s_bck=33

from es8311 import ES8311

try:
    from machine import I2C, I2S, Pin
except ImportError:  # type: ignore
    # Allow importing on non-MicroPython systems for static analysis
    I2C = I2S = Pin = None  # type: ignore


# PI4IOE5V6408 I/O expander (speaker/mic routing)
_PI4IOE_ADDR = 0x43
_PI4IOE_REG_CTRL = 0x00
_PI4IOE_REG_IO_PP = 0x07
_PI4IOE_REG_IO_DIR = 0x03
_PI4IOE_REG_IO_OUT = 0x05
_PI4IOE_REG_IO_PULLUP = 0x0D

# ES8311 I2C address
_ES8311_ADDR = 0x18


class M5EchoBase:
    """
    High-level audio helper for Atomic Echo Base.

    Typical usage (ATOMS3/ATOMS3R):

        from M5EchoBase import M5EchoBase

        echobase = M5EchoBase(i2s_id=0)
        echobase.init(
            sample_rate=16000,
            i2c_sda=38, i2c_scl=39,
            i2s_di=7, i2s_ws=6, i2s_do=5, i2s_bck=8,
        )
        echobase.setSpeakerVolume(50)

        duration = 3  # seconds
        buf_size = echobase.getBufferSize(duration)
        buf = bytearray(buf_size)

        echobase.setMute(True)
        echobase.record(buf)
        echobase.setMute(False)
        echobase.play(buf)
    """

    def __init__(self, i2s_id=0):
        self._i2s_id = i2s_id

        self._i2c = None          # type: ignore
        self._i2s_in = None       # type: ignore
        self._i2s_out = None      # type: ignore
        self._es = None           # type: ignore

        self._sample_rate = None  # type: ignore
        self._bits = 16
        self._channels = 2  # stereo
        self._muted = False

    # -------------------------------------------------------------------------
    # Initialization
    # -------------------------------------------------------------------------
    def init(
        self,
        sample_rate=16000,
        i2c_sda=38,
        i2c_scl=39,
        i2s_di=7,
        i2s_ws=6,
        i2s_do=5,
        i2s_bck=8,
        i2c_id=0,
        i2c_freq=100_000,
        ibuf=16_384,
    ):
        """
        Initialize ES8311 codec, I2C expander and I2S (RX+TX).

        Returns True on success (or at least no obvious failure).
        """
        self._sample_rate = int(sample_rate)

        # I2C for ES8311 + PI4IOE5V6408
        self._i2c = I2C(
            i2c_id,
            sda=Pin(i2c_sda),
            scl=Pin(i2c_scl),
            freq=i2c_freq,
        )

        # ES8311 codec instance; exact constructor may depend on your driver
        # Adjust if your ES8311 class uses a different signature.
        self._es = ES8311(self._i2c, addr=_ES8311_ADDR, sample_rate=self._sample_rate, bits=self._bits)  # type: ignore

        # If the ES8311 driver exposes an explicit init/config, call it
        if hasattr(self._es, "init"):
            try:
                # Common pattern: es.init(sample_rate=..., bits=..., channels=...)
                self._es.init(
                    sample_rate=self._sample_rate,
                    bits=self._bits,
                    channels=self._channels,
                )
            except TypeError:
                # Fall back to a simpler call if the signature is different
                self._es.init(self._sample_rate)  # type: ignore

        # Configure PI4IOE5V6408 I/O expander (same logic as Arduino driver)
        self._pi4ioe_init()

        # I2S for playback (TX)
        sck = Pin(i2s_bck)
        ws = Pin(i2s_ws)
        sd_out = Pin(i2s_do)
        sd_in = Pin(i2s_di)

        self._i2s_out = I2S(
            self._i2s_id,
            sck=sck,
            ws=ws,
            sd=sd_out,
            mode=I2S.TX,
            bits=self._bits,
            format=I2S.STEREO,
            rate=self._sample_rate,
            ibuf=ibuf,
        )

        # I2S for recording (RX)
        self._i2s_in = I2S(
            self._i2s_id,
            sck=sck,
            ws=ws,
            sd=sd_in,
            mode=I2S.RX,
            bits=self._bits,
            format=I2S.STEREO,
            rate=self._sample_rate,
            ibuf=ibuf,
        )

        return True

    # -------------------------------------------------------------------------
    # Volume / gain / mute
    # -------------------------------------------------------------------------
    def setSpeakerVolume(self, volume):
        """
        Set speaker volume 0..100 (mapped to ES8311 output volume).

        Returns True on success.
        """
        if volume < 0 or volume > 100:
            return False

        if self._es is None:
            return False

        # Try common ES8311 APIs, but don't crash if they differ
        if hasattr(self._es, "set_voice_volume"):
            self._es.set_voice_volume(volume)  # type: ignore
        elif hasattr(self._es, "voice_volume"):
            self._es.voice_volume(volume)  # type: ignore
        elif hasattr(self._es, "set_volume"):
            self._es.set_volume(volume)  # type: ignore
        else:
            # Can't actually set on the codec, but keep interface compatible
            return False

        return True

    def setMicGain(self, gain):
        """
        Set microphone gain.

        `gain` is expected to be an enum or value understood by the ES8311 driver.
        Returns True on success.
        """
        if self._es is None:
            return False

        if hasattr(self._es, "set_mic_gain"):
            self._es.set_mic_gain(gain)  # type: ignore
            return True

        # Fallback: expose failure if driver doesn't support it
        return False

    def setMicPGAGain(self, digital_mic, pga_gain):
        """
        Set microphone PGA gain.

        digital_mic: True for PDM/digital mic, False for analog.
        pga_gain: codec-specific PGA gain value.
        Returns True on success.
        """
        if self._es is None:
            return False

        if hasattr(self._es, "set_mic_pga_gain"):
            self._es.set_mic_pga_gain(digital_mic, pga_gain)  # type: ignore
            return True

        return False

    def setMicAdcVolume(self, volume):
        """
        Set microphone ADC digital volume, 0..100.

        Returns True on success.
        """
        if volume < 0 or volume > 100:
            return False

        if self._es is None:
            return False

        if hasattr(self._es, "set_mic_adc_volume"):
            self._es.set_mic_adc_volume(volume)  # type: ignore
            return True

        return False

    def setMute(self, mute):
        """
        Mute / unmute via PI4IOE5V6408 IO expander.

        Returns True on success.
        """
        self._muted = bool(mute)
        if self._i2c is None:
            return False

        # Arduino version writes all outputs 0x00 (mute) or 0xFF (unmute)
        try:
            self._i2c.writeto_mem(_PI4IOE_ADDR, _PI4IOE_REG_IO_OUT, bytes([0x00 if mute else 0xFF]))
            return True
        except OSError:
            return False

    # -------------------------------------------------------------------------
    # Buffer size / duration helpers
    # -------------------------------------------------------------------------
    def getBufferSize(self, duration, sample_rate=None):
        """
        Calculate buffer size in bytes to hold the given duration (seconds)
        of 16-bit stereo PCM at the given sample_rate.
        """
        if sample_rate is None:
            sample_rate = self._sample_rate or 16000
        return int(duration * sample_rate * (self._bits // 8) * self._channels)

    def getDuration(self, size, sample_rate=None):
        """
        Calculate duration in seconds for a given raw PCM size in bytes.
        """
        if sample_rate is None:
            sample_rate = self._sample_rate or 16000
        bytes_per_sample_frame = (self._bits // 8) * self._channels
        if bytes_per_sample_frame <= 0 or sample_rate <= 0:
            return 0
        return int(size // (sample_rate * bytes_per_sample_frame))

    # -------------------------------------------------------------------------
    # Recording
    # -------------------------------------------------------------------------
    def record(self, buffer, size=None, timeout_ms=None):
        """
        Record raw PCM audio into the given buffer (bytearray/memoryview).

        buffer: mutable buffer (bytearray, memoryview, etc.)
        size:   number of bytes to fill; defaults to len(buffer)

        Returns True on success.
        """
        if self._i2s_in is None:
            return False

        if size is None:
            size = len(buffer)
        if size <= 0:
            return False

        view = memoryview(buffer)
        total = 0

        # blocking reads until 'size' bytes have been captured
        while total < size:
            # readinto fills the full slice or blocks until it does
            n = self._i2s_in.readinto(view[total:size])
            if n is None or n <= 0:
                # treat as failure / timeout
                return False
            total += n

        return True

    def record_to_file(self, path, size, chunk_size=1024):
        """
        Record raw PCM audio directly into a file.

        path:       filesystem path (string)
        size:       total bytes to record
        chunk_size: I2S chunk size
        """
        if self._i2s_in is None:
            return False

        try:
            f = open(path, "wb")
        except OSError:
            return False

        remaining = size
        buf = bytearray(chunk_size)

        try:
            while remaining > 0:
                n = chunk_size if remaining >= chunk_size else remaining
                mv = memoryview(buf)[:n]
                read = self._i2s_in.readinto(mv)
                if read is None or read <= 0:
                    f.close()
                    return False
                f.write(mv[:read])
                remaining -= read
        finally:
            f.close()

        return True

    # -------------------------------------------------------------------------
    # Playback
    # -------------------------------------------------------------------------
    def play(self, buffer, size=None):
        """
        Play raw PCM audio from the given buffer.

        buffer: bytes / bytearray / memoryview
        size:   number of bytes to send; defaults to len(buffer)

        Returns True on success.
        """
        if self._i2s_out is None:
            return False

        if size is None:
            size = len(buffer)
        if size <= 0:
            return False

        view = memoryview(buffer)
        total = 0

        while total < size:
            n = self._i2s_out.write(view[total:size])
            if n is None or n <= 0:
                return False
            total += n

        return True

    def play_from_file(self, path, chunk_size=1024):
        """
        Play raw PCM audio from a file.

        path:       filesystem path (string)
        chunk_size: number of bytes per I2S write

        Returns True on success.
        """
        if self._i2s_out is None:
            return False

        try:
            f = open(path, "rb")
        except OSError:
            return False

        buf = bytearray(chunk_size)
        try:
            while True:
                n = f.readinto(buf)
                if not n:
                    break
                mv = memoryview(buf)[:n]
                written = self._i2s_out.write(mv)
                if written is None or written <= 0:
                    f.close()
                    return False
        finally:
            f.close()

        return True

    # -------------------------------------------------------------------------
    # PI4IOE5V6408 helpers
    # -------------------------------------------------------------------------
    def _pi4ioe_read_byte(self, reg):
        if self._i2c is None:
            return 0
        try:
            data = self._i2c.readfrom_mem(_PI4IOE_ADDR, reg, 1)
            return data[0]
        except OSError:
            return 0

    def _pi4ioe_write_byte(self, reg, value):
        if self._i2c is None:
            return
        try:
            self._i2c.writeto_mem(_PI4IOE_ADDR, reg, bytes([value & 0xFF]))
        except OSError:
            pass

    def _pi4ioe_init(self):
        """
        Configure PI4IOE5V6408 like the Arduino driver:

          - set all outputs high-impedance
          - enable pull-ups
          - configure IO direction
          - set outputs high
        """
        # Read CTRL (ignored result)
        self._pi4ioe_read_byte(_PI4IOE_REG_CTRL)

        # Set high-impedance
        self._pi4ioe_write_byte(_PI4IOE_REG_IO_PP, 0x00)
        self._pi4ioe_read_byte(_PI4IOE_REG_IO_PP)

        # Enable pull-up and set direction (0=input, 1=output, with P0 as output)
        self._pi4ioe_write_byte(_PI4IOE_REG_IO_PULLUP, 0xFF)
        self._pi4ioe_write_byte(_PI4IOE_REG_IO_DIR, 0x6F)
        self._pi4ioe_read_byte(_PI4IOE_REG_IO_DIR)

        # Set outputs high (unmuted by default)
        self._pi4ioe_write_byte(_PI4IOE_REG_IO_OUT, 0xFF)
        self._pi4ioe_read_byte(_PI4IOE_REG_IO_OUT)

