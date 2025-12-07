# m5echobase.py
#
# MicroPython port of M5EchoBase (half-duplex I2S, shared RX/TX ID)
#
# NOTE:
# - This assumes a MicroPython build with machine.I2S support (ESP32).
# - It also assumes an es8311 driver module is available and provides
#   the codec configuration functions you need. You may need to adapt
#   the es8311_* calls to match your actual driver API.

from machine import Pin, I2C, I2S

# ---- PI4IOE5V6408 I/O expander constants ----
PI4IOE_ADDR          = 0x43
PI4IOE_REG_CTRL      = 0x00
PI4IOE_REG_IO_PP     = 0x07
PI4IOE_REG_IO_DIR    = 0x03
PI4IOE_REG_IO_OUT    = 0x05
PI4IOE_REG_IO_PULLUP = 0x0D

# ES8311 address
ES8311_ADDR = 0x18

CHUNK_SIZE = 4096


try:
    # Adapt these imports to your MicroPython es8311 binding as needed
    import es8311
except ImportError:
    es8311 = None  # You must provide this

class M5EchoBase:
    """
    MicroPython equivalent of the C++ M5EchoBase.

    Public API kept as close as possible:

        bool init(sample_rate=16000, i2c_sda=38, i2c_scl=39,
                  i2s_di=7, i2s_ws=6, i2s_do=5, i2s_bck=8, i2c=None)

        bool setSpeakerVolume(volume)
        bool setMicGain(gain)
        bool setMicPGAGain(digital_mic, pga_gain)
        bool setMicAdcVolume(volume)
        bool setMute(mute)

        int  getBufferSize(duration, sample_rate=0)
        int  getDuration(size, sample_rate=0)

        # Overloads in C++ are merged here; both forms are supported:
        bool record(fs, filename, size)
        bool record(buffer, size)

        bool play(fs, filename)
        bool play(buffer, size)

    Half-duplex I2S: a single I2S instance and ID are used; we reconfigure
    between TX and RX as needed.
    """

    def __init__(self, i2s_id=0):
        # codec handle / object from es8311 driver (implementation-dependent)
        self.es_handle = None

        # I2S / I2C config
        self.i2s_id   = i2s_id
        self.i2s      = None     # machine.I2S instance
        self.i2c      = None     # machine.I2C instance

        # pins
        self._i2c_sda = None
        self._i2c_scl = None
        self._i2s_di  = None
        self._i2s_ws  = None
        self._i2s_do  = None
        self._i2s_bck = None

        # runtime state
        self._sample_rate = None
        self._i2s_mode    = None  # 'tx' or 'rx'

    # ---------- public API ----------

    def init(self,
             sample_rate=16000,
             i2c_sda=38,
             i2c_scl=39,
             i2s_di=7,
             i2s_ws=6,
             i2s_do=5,
             i2s_bck=8,
             i2c=None,
             i2c_id=0):
        """
        Initialize I2C, ES8311, I/O expander, and prepare I2S.

        If `i2c` is provided, it is used directly.
        Otherwise a new I2C instance is created from `i2c_sda`/`i2c_scl`.
        """

        self._i2c_sda = i2c_sda
        self._i2c_scl = i2c_scl
        self._i2s_di  = i2s_di
        self._i2s_ws  = i2s_ws
        self._i2s_do  = i2s_do
        self._i2s_bck = i2s_bck
        self._sample_rate = sample_rate

        if i2c is not None:
            self.i2c = i2c
        else:
            # 100 kHz I2C, same as the C++ code
            self.i2c = I2C(
                i2c_id,
                scl=Pin(self._i2c_scl),
                sda=Pin(self._i2c_sda),
                freq=100_000
            )

        # init codec
        if not self._es8311_codec_init(sample_rate):
            return False

        # init IO expander
        if not self._pi4ioe_init():
            return False

        # In the original, mic gain is set after init()
        self.setMicGain(0)  # ES8311_MIC_GAIN_0DB equivalent; adapt as needed

        return True

    def setSpeakerVolume(self, volume):
        """
        volume: 0–100
        """
        if volume < 0 or volume > 100:
            return False

        if es8311 is None:
            # Placeholder; adapt to your es8311 driver
            return False

        # Adapt this call to your MicroPython es8311 API:
        try:
            # For example, if your driver exposes this:
            # es8311.voice_volume_set(self.es_handle, volume)
            es8311.voice_volume_set(self.es_handle, volume)
        except AttributeError:
            # If your driver instead uses another method name, adjust here
            return False

        return True

    def setMicGain(self, gain):
        """
        gain: driver-specific mic gain value (e.g. ES8311_MIC_GAIN_0DB etc.)
        """
        if es8311 is None:
            return False

        try:
            es8311.microphone_gain_set(self.es_handle, gain)
        except AttributeError:
            return False

        return True

    def setMicPGAGain(self, digital_mic, pga_gain):
        """
        digital_mic: bool
        pga_gain: driver-specific integer gain value
        """
        if es8311 is None:
            return False

        try:
            es8311.microphone_pgagain_config(self.es_handle, digital_mic, pga_gain)
        except AttributeError:
            return False

        return True

    def setMicAdcVolume(self, volume):
        """
        volume: 0–100
        """
        if volume > 100:
            return False
        if es8311 is None:
            return False

        try:
            es8311.set_adc_volume(self.es_handle, volume)
        except AttributeError:
            return False

        return True

    def setMute(self, mute):
        """
        mute: True -> output off, False -> output on.
        Implements PI4IOE write like C++: IO_OUT = 0x00 when mute, 0xFF when not.
        """
        value = 0x00 if mute else 0xFF
        self._wire_write_byte(PI4IOE_ADDR, PI4IOE_REG_IO_OUT, value)
        return True

    def getBufferSize(self, duration, sample_rate=0):
        """
        duration: seconds
        sample_rate: Hz; if 0, use current sample rate.

        returns: number of bytes (stereo, 16-bit).
        """
        if sample_rate == 0:
            sample_rate = self._sample_rate or 16000
        # sample_rate * bytes_per_sample * channels
        return int(duration * sample_rate * 2 * 2)

    def getDuration(self, size, sample_rate=0):
        """
        size: buffer size in bytes
        sample_rate: Hz; if 0, use current sample rate.

        returns: duration in seconds (float).
        """
        if sample_rate == 0:
            sample_rate = self._sample_rate or 16000
        return float(size) / float(sample_rate * 2 * 2)

    # --- record / play overload emulation ---

    def record(self, arg1, arg2, size=None):
        """
        C++ overloads:

            bool record(FS& fs, const char* filename, int size);
            bool record(uint8_t* buffer, int size);

        MicroPython emulation:

            record(buffer, size)
            record(fs_like, filename, size)

        Where:
          - buffer is a bytearray/memoryview
          - fs_like is unused; open() is used on filename.
        """
        # record(buffer, size)
        if isinstance(arg1, (bytearray, memoryview)):
            buffer = arg1
            if size is None:
                size = arg2
            return self._record_to_buffer(buffer, size)

        # record(fs_like, filename, size)
        fs = arg1
        filename = arg2
        if size is None:
            raise ValueError("size required for record(fs, filename, size)")

        # fs is ignored; we use open() directly
        return self._record_to_file(filename, size)

    def play(self, arg1, arg2=None):
        """
        C++ overloads:

            bool play(FS& fs, const char* filename);
            bool play(const uint8_t* buffer, int size);

        MicroPython emulation:

            play(buffer, size)
            play(fs_like, filename)
        """
        # play(buffer, size)
        if isinstance(arg1, (bytearray, memoryview, bytes)):
            buffer = arg1
            size = arg2 if arg2 is not None else len(buffer)
            return self._play_from_buffer(buffer, size)

        # play(fs_like, filename)
        fs = arg1
        filename = arg2
        if filename is None:
            raise ValueError("filename required for play(fs, filename)")

        # fs is ignored; we use open()
        return self._play_from_file(filename)

    # ---------- internal helpers ----------

    def _ensure_i2s(self, mode, sample_rate=None):
        """
        Ensure a single I2S instance is configured for the given mode ('tx' or 'rx')
        and sample rate. Reinitializes the I2S peripheral if needed.

        Half-duplex: only one of TX or RX is active at a time, using the same ID.
        """
        if sample_rate is None:
            sample_rate = self._sample_rate or 16000

        if mode == self._i2s_mode and self.i2s is not None and sample_rate == self._sample_rate:
            return

        # deinit previous instance, if any
        if self.i2s is not None:
            try:
                self.i2s.deinit()
            except Exception:
                pass
            self.i2s = None

        # choose SD pin by direction
        if mode == 'tx':
            sd_pin = self._i2s_do
            i2s_mode = I2S.TX
        else:
            sd_pin = self._i2s_di
            i2s_mode = I2S.RX

        # create new I2S in standard I2S stereo 16-bit mode
        # ibuf is arbitrary buffer size; adjust for your platform.
        self.i2s = I2S(
            self.i2s_id,
            sck=Pin(self._i2s_bck),
            ws=Pin(self._i2s_ws),
            sd=Pin(sd_pin),
            mode=i2s_mode,
            bits=16,
            format=I2S.STEREO,
            rate=sample_rate,
            ibuf=4096,
        )

        self._i2s_mode    = mode
        self._sample_rate = sample_rate

    def _es8311_codec_init(self, sample_rate):
        """
        Adapt this to your es8311 MicroPython driver.

        The C++ code does roughly:

            es8311_set_twowire(_wire);
            es_handle = es8311_create(0, ES8311_ADDR);
            es8311_init(es_handle, &clk_cfg, 32bit, 32bit);
            es8311_voice_volume_set(es_handle, 50);
            es8311_microphone_config(es_handle, false);
        """
        if es8311 is None:
            # No codec driver available
            return False

        try:
            # Example of a high-level MicroPython-style driver API:
            #   self.es_handle = es8311.ES8311(self.i2c, addr=ES8311_ADDR)
            #   self.es_handle.init(sample_rate=sample_rate)
            #   self.es_handle.set_voice_volume(50)
            #   self.es_handle.configure_microphone(digital_mic=False)
            #
            # Replace this with your actual driver calls.

            if hasattr(es8311, "ES8311"):
                # OO style driver
                self.es_handle = es8311.ES8311(self.i2c, addr=ES8311_ADDR)
                self.es_handle.init(sample_rate=sample_rate, bits=16)
            else:
                # C-style binding emulation; adapt names to your driver
                es8311.set_twowire(self.i2c)
                self.es_handle = es8311.create(0, ES8311_ADDR)
                es8311.init(self.es_handle, sample_rate, 16, 16)
                es8311.voice_volume_set(self.es_handle, 50)
                es8311.microphone_config(self.es_handle, False)

        except Exception:
            return False

        return True

    def _pi4ioe_init(self):
        """
        Initialize the PI4IOE5V6408 same way as in C++:

          - read CTRL
          - IO_PP  = 0x00 (high-Z)
          - PULLUP = 0xFF (enable pull-ups)
          - DIR    = 0x6F (inputs 0, outputs 1, P0 as output)
          - OUT    = 0xFF
        """
        # Read CTRL register to get current state
        self._wire_read_byte(PI4IOE_ADDR, PI4IOE_REG_CTRL)

        # Set outputs to high-impedance
        self._wire_write_byte(PI4IOE_ADDR, PI4IOE_REG_IO_PP, 0x00)
        self._wire_read_byte(PI4IOE_ADDR, PI4IOE_REG_IO_PP)

        # Enable pull-ups and configure directions
        self._wire_write_byte(PI4IOE_ADDR, PI4IOE_REG_IO_PULLUP, 0xFF)
        self._wire_write_byte(PI4IOE_ADDR, PI4IOE_REG_IO_DIR, 0x6F)
        self._wire_read_byte(PI4IOE_ADDR, PI4IOE_REG_IO_DIR)

        # Set outputs high
        self._wire_write_byte(PI4IOE_ADDR, PI4IOE_REG_IO_OUT, 0xFF)
        self._wire_read_byte(PI4IOE_ADDR, PI4IOE_REG_IO_OUT)

        return True

    def _wire_read_byte(self, i2c_addr, reg_addr):
        """
        I2C single-byte register read (replacement for wire_read_byte()).
        """
        try:
            data = self.i2c.readfrom_mem(i2c_addr, reg_addr, 1)
            return data[0]
        except Exception:
            return 0xFF

    def _wire_write_byte(self, i2c_addr, reg_addr, value):
        """
        I2C single-byte register write (replacement for wire_write_byte()).
        """
        try:
            self.i2c.writeto_mem(i2c_addr, reg_addr, bytes([value]))
        except Exception:
            pass

    # --- I2S record/play primitives ---

    def _record_to_buffer(self, buffer, size):
        """
        Record `size` bytes into `buffer` via I2S RX.
        """
        self._ensure_i2s('rx')
        mv = memoryview(buffer)[:size]

        try:
            # readinto() usually returns number of bytes
            n = self.i2s.readinto(mv)
            if isinstance(n, tuple):
                n = n[0]
        except Exception:
            return False

        return n == size

    def _record_to_file(self, filename, size):
        """
        Record `size` bytes from I2S RX into a file.
        """
        self._ensure_i2s('rx')

        remaining  = size
        buf        = bytearray(CHUNK_SIZE)

        try:
            with open(filename, "wb") as f:
                while remaining > 0:
                    chunk = CHUNK_SIZE if remaining >= CHUNK_SIZE else remaining
                    mv = memoryview(buf)[:chunk]

                    n = self.i2s.readinto(mv)
                    if isinstance(n, tuple):
                        n = n[0]

                    if n <= 0:
                        return False

                    f.write(mv[:n])
                    remaining -= n
        except Exception:
            return False

        return True

    def _play_from_buffer(self, buffer, size):
        """
        Play `size` bytes from `buffer` via I2S TX.
        """
        self._ensure_i2s('tx')
        mv = memoryview(buffer)[:size]

        try:
            n = self.i2s.write(mv)
            if isinstance(n, tuple):
                n = n[0]
        except Exception:
            return False

        # Some ports require flushing or a small delay; add if needed.
        return n == size

    def _play_from_file(self, filename):
        """
        Play an entire file via I2S TX.
        """
        self._ensure_i2s('tx')
        buf        = bytearray(CHUNK_SIZE)

        try:
            with open(filename, "rb") as f:
                f.read(44)  # Skip WAV header
                while True:
                    n_read = f.readinto(buf)
                    if n_read is None or n_read == 0:
                        break

                    mv = memoryview(buf)[:n_read]
                    n_written = self.i2s.write(mv)
                    if isinstance(n_written, tuple):
                        n_written = n_written[0]
                    if n_written <= 0:
                        return False
        except Exception:
            return False

        return True

