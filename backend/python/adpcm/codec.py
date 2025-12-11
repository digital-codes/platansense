import numpy as np
import wave

# IMA ADPCM step and index tables
step_table = np.array([
    7, 8, 9, 10, 11, 12, 13, 14, 16, 17,
    19, 21, 23, 25, 28, 31, 34, 37, 41, 45,
    50, 55, 60, 66, 73, 80, 88, 97, 107, 118,
    130, 143, 157, 173, 190, 209, 230, 253, 279, 307,
    337, 371, 408, 449, 494, 544, 598, 658, 724, 796,
    876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066,
    2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871, 5358,
    5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899,
    15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767
], dtype=np.int32)

index_table = np.array([
    -1, -1, -1, -1, 2, 4, 6, 8,
    -1, -1, -1, -1, 2, 4, 6, 8
], dtype=np.int8)

def adpcm_encode(pcm_data: np.ndarray) -> np.ndarray:
    assert pcm_data.dtype == np.int16
    nsamples = len(pcm_data)
    out = np.zeros((nsamples + 1) // 2, dtype=np.uint8)

    index = 0
    valprev = 0
    step = step_table[index]
    buffer = 0
    toggle = False

    for i, sample in enumerate(pcm_data):
        diff = sample - valprev
        sign = 8 if diff < 0 else 0
        if sign:
            diff = -diff

        delta = 0
        tempstep = step
        if diff >= tempstep:
            delta |= 4
            diff -= tempstep
        tempstep >>= 1
        if diff >= tempstep:
            delta |= 2
            diff -= tempstep
        tempstep >>= 1
        if diff >= tempstep:
            delta |= 1

        delta |= sign

        vpdiff = step >> 3
        if delta & 4: vpdiff += step
        if delta & 2: vpdiff += step >> 1
        if delta & 1: vpdiff += step >> 2

        valprev += -vpdiff if sign else vpdiff
        valprev = np.clip(valprev, -32768, 32767)

        index += index_table[delta & 0x0F]
        index = np.clip(index, 0, 88)
        step = step_table[index]

        if toggle:
            out[i >> 1] |= delta & 0x0F
        else:
            out[i >> 1] = (delta << 4) & 0xF0
        toggle = not toggle

    return out

def adpcm_decode(adpcm_data: np.ndarray) -> np.ndarray:
    assert adpcm_data.dtype == np.uint8
    nsamples = len(adpcm_data) * 2
    pcm = np.zeros(nsamples, dtype=np.int16)

    index = 0
    valprev = 0
    step = step_table[index]

    for i in range(nsamples):
        delta = adpcm_data[i >> 1]
        delta = delta & 0x0F if i & 1 else delta >> 4

        sign = delta & 8
        delta &= 7

        vpdiff = step >> 3
        if delta & 4: vpdiff += step
        if delta & 2: vpdiff += step >> 1
        if delta & 1: vpdiff += step >> 2

        valprev += -vpdiff if sign else vpdiff
        valprev = np.clip(valprev, -32768, 32767)
        pcm[i] = valprev

        index += index_table[delta | sign]
        index = np.clip(index, 0, 88)
        step = step_table[index]

    return pcm


# ---------------------------------------------------------------------
# 🎵  WAV converter
# ---------------------------------------------------------------------
def convertFromWav(wav_bytes: bytes, target_rate: int = 22050) -> np.ndarray:
    """
    Convert WAV byte data to PCM int16 samples.

    Parameters
    ----------
    wav_bytes : bytes
        Byte data of a WAV file.

    Returns
    -------
    np.ndarray[int16]
        PCM samples as int16 numpy array.
    """
    import io

    with wave.open(io.BytesIO(wav_bytes), 'rb') as wav_file:
        n_channels = wav_file.getnchannels()
        sampwidth = wav_file.getsampwidth()
        n_frames = wav_file.getnframes()
        framerate = wav_file.getframerate()

        frames = wav_file.readframes(n_frames)

        # Convert raw bytes to PCM int16, handling various sample widths
        if sampwidth == 1:
            # 8-bit WAV: unsigned
            raw = np.frombuffer(frames, dtype=np.uint8).astype(np.int16)
            raw = (raw - 128) << 8
        elif sampwidth == 2:
            # 16-bit WAV: signed little-endian
            raw = np.frombuffer(frames, dtype='<i2').astype(np.int32)
        elif sampwidth == 3:
            # 24-bit WAV: convert manually to int32 then to int16
            b = np.frombuffer(frames, dtype=np.uint8)
            # Ensure length is multiple of 3
            if b.size % 3 != 0:
                b = b[:-(b.size % 3)]
            b = b.reshape(-1, 3)
            # Little-endian: b0 + b1<<8 + b2<<16, sign extend if b2 & 0x80
            raw32 = (b[:, 0].astype(np.int32) |
                 (b[:, 1].astype(np.int32) << 8) |
                 (b[:, 2].astype(np.int32) << 16))
            sign_mask = (raw32 & 0x800000) != 0
            raw32[sign_mask] |= ~0xFFFFFF  # sign extend
            # Reduce 24->16 by shifting
            raw = (raw32 >> 8).astype(np.int32)
        elif sampwidth == 4:
            # 32-bit WAV: signed little-endian -> convert to int16 by shifting
            raw32 = np.frombuffer(frames, dtype='<i4').astype(np.int32)
            raw = (raw32 >> 16).astype(np.int32)
        else:
            # Unknown sample width: treat bytes as silence
            raw = np.zeros(n_frames * n_channels, dtype=np.int32)

        # Convert to shape (n_frames, n_channels)
        try:
            raw = raw.reshape(-1, n_channels)
        except Exception:
            # If reshape fails, try to infer channels by truncation/padding
            total_samples = raw.size
            expected = n_frames * n_channels
            if total_samples > expected:
                raw = raw[:expected].reshape(-1, n_channels)
            else:
                # pad with zeros
                pad = expected - total_samples
                raw = np.concatenate([raw, np.zeros(pad, dtype=raw.dtype)])
                raw = raw.reshape(-1, n_channels)

        # Convert to mono by averaging channels (preserve as float for resampling precision)
        if n_channels == 1:
            pcm = raw[:, 0].astype(np.float32)
        else:
            pcm = raw.mean(axis=1).astype(np.float32)

        # Clip to int16 range just in case, then resample if target_rate differs
        pcm = np.clip(pcm, -32768, 32767)

        if target_rate != framerate and pcm.size > 1:
            # Simple linear resampling (no external deps)
            src_len = pcm.size
            dst_len = int(round(src_len * float(target_rate) / float(framerate)))
            if dst_len <= 0:
                dst_len = 1
            xp = np.linspace(0, src_len - 1, num=src_len)
            xnew = np.linspace(0, src_len - 1, num=dst_len)
            pcm_resampled = np.interp(xnew, xp, pcm).astype(np.float32)
            pcm_data = np.round(pcm_resampled).astype(np.int16)
        else:
            pcm_data = np.round(pcm).astype(np.int16)

    return pcm_data

# ------------------------------------------------------
#  wav format converter
# ------------------------------------------------------
import wave

# … your existing tables + adpcm_encode/adpcm_decode/maximise_volume …

def load_wav_as_mono_pcm(path: str, target_rate: int) -> np.ndarray:
    """
    Load a WAV file, convert to mono and resample to target_rate.
    Returns int16 numpy array.
    """
    with wave.open(path, "rb") as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        n_frames = wf.getnframes()
        frames = wf.readframes(n_frames)

    if sampwidth != 2:
        raise RuntimeError(f"Only 16-bit WAV supported, got {8 * sampwidth}-bit")

    pcm = np.frombuffer(frames, dtype=np.int16)

    # Mix down to mono if needed
    if n_channels > 1:
        pcm = pcm.reshape(-1, n_channels)
        pcm = pcm.mean(axis=1).astype(np.int16)

    if framerate == target_rate:
        return pcm

    # Simple linear resample using numpy
    duration = pcm.shape[0] / framerate
    old_t = np.linspace(0.0, duration, num=pcm.shape[0], endpoint=False)
    new_n = int(round(duration * target_rate))
    new_t = np.linspace(0.0, duration, num=new_n, endpoint=False)
    resampled = np.interp(new_t, old_t, pcm).astype(np.int16)

    return resampled



# ---------------------------------------------------------------------
# 🏋️‍♂️  Volume maximiser
# ---------------------------------------------------------------------
def maximise_volume(pcm_i16: np.ndarray, headroom: float = 0.002) -> np.ndarray:
    """
    Scale 16-bit PCM to the loudest level possible without clipping.

    Parameters
    ----------
    pcm_i16 : np.ndarray[int16]
        Audio samples.
    headroom : float
        Fractional margin below full-scale to leave (default 0.2 %).
        Set to 0.0 for true full-scale, but 0.002 avoids DAC clipping.
        Check for initial clicks.
    Returns
    -------
    np.ndarray[int16]
        Scaled samples (same length).
    """
    
    clickSize = 512 * 2  # 256 samples, 2 bytes per sample
    if pcm_i16.size == 0 or pcm_i16.size < clickSize:
        return pcm_i16

    max_abs = np.abs(pcm_i16).max()
    if max_abs == 0:
        return pcm_i16

    mean_abs = np.mean(np.abs(pcm_i16[clickSize:]))
    mean_abs_start = np.mean(np.abs(pcm_i16[:clickSize]))

    print(f"Max absolute value: {max_abs}, Mean absolute value: {mean_abs}")
    print(f"Mean absolute value of first 256 samples: {mean_abs_start}")

    if mean_abs_start > 10 * mean_abs:
        print(f"Warning: First {clickSize/2} samples have significantly higher mean absolute value than the rest of the audio.")
        pcm_i16 = pcm_i16[clickSize:]  # Remove the first 256 samples
        max_abs = np.abs(pcm_i16).max() # recalculate max_abs after removing samples

    target = int((1.0 - headroom) * 32767)
    gain   = target / max_abs
    # Multiply in float32 to avoid overflow/rounding artefacts
    scaled = (pcm_i16.astype(np.float32) * gain).round()
    return scaled.astype(np.int16)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ADPCM Encoder/Decoder")
    parser.add_argument("-i", "--input", required=True, type=str, help="Input RAW file")
    parser.add_argument("-o", "--output", default=None, type=str, help="Output WAV file")
    parser.add_argument("-e", "--encoded", default=None, type=str, help="Output Encoded file")
    parser.add_argument("-s", "--samplingrate", type=int, default=22050, help="Sampling rate for output WAV file")
    parser.add_argument("-m", "--maximise", action="store_true", help="Maximise volume of output WAV file")
    parser.add_argument("-r", "--raw", action="store_true", help="Input is raw audio, not encoded")
    parser.add_argument("-w", "--wav", action="store_true", help="Input is wav audio")
    args = parser.parse_args()

    # Load samples from Input
    with open(args.input, "rb") as f:
        raw = np.frombuffer(f.read(), dtype=np.uint8)

    if args.output is None and args.encoded is None:
        raise RuntimeError("At least one of --output or --encoded must be specified")
    
    if args.raw and args.wav:
        raise RuntimeError("Only one of --raw or --wav can be specified")

    print(f"Loaded {len(raw)} samples from {args.input}")
    if args.raw:
        decoded = raw.view(np.int16)
        print(f"Using {len(decoded)} raw PCM samples")
    elif args.wav:
        # Convert from WAV
        decoded = convertFromWav(raw,args.samplingrate)
        print(f"Using {len(decoded)} WAV PCM samples")
    else:
        # Decode from ADPCM
        decoded = adpcm_decode(raw)
        print(f"Decoded {len(decoded)} samples from ADPCM")

    # maximize option
    if args.maximise:
        decoded = maximise_volume(decoded)

    # Encode to ADPCM
    encoded = adpcm_encode(decoded)
    print(f"Encoded {len(encoded)} samples to ADPCM")


    # Save decoded PCM as WAV
    if args.output is not None:
        with wave.open(args.output, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(args.samplingrate)
            w.writeframes(decoded.tobytes())
        print(f"Saved WAV to {args.output}")
    

    # Save encoded WAV as RAW
    if args.encoded is not None:
        with open(args.encoded, "wb") as f:
            f.write(encoded.tobytes())
        print(f"Encoded ADPCM to {args.encoded}")
    
