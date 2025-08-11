import numpy as np

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
    import wave

    parser = argparse.ArgumentParser(description="ADPCM Encoder/Decoder")
    parser.add_argument("-i", "--input", required=True, type=str, help="Input RAW file")
    parser.add_argument("-o", "--output", required=True, type=str, help="Output WAV file")
    parser.add_argument("-e", "--encoded", required=True, type=str, help="Output Encoded file")
    parser.add_argument("-s", "--samplingrate", type=int, default=22050, help="Sampling rate for output WAV file")
    parser.add_argument("-m", "--maximise", action="store_true", help="Maximise volume of output WAV file")
    args = parser.parse_args()

    # Load raw PCM samples from Input
    with open(args.input, "rb") as f:
        #raw = np.frombuffer(f.read(), dtype=np.int16)
        raw = np.frombuffer(f.read(), dtype=np.uint8)


    print(f"Loaded {len(raw)} samples from {args.input}")
    # Encode to ADPCM
    decoded = adpcm_decode(raw)
    print(f"Decoded {len(decoded)} samples from ADPCM")


    # Encode to ADPCM
    encoded = adpcm_encode(decoded)
    print(f"Encoded {len(encoded)} samples to ADPCM")


    # Save decoded PCM as WAV
    with wave.open(args.output, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(args.samplingrate)
        if args.maximise:
            decoded = maximise_volume(decoded)
        w.writeframes(decoded.tobytes())
    

    # Save encoded WAV as RAW
    with open(args.encoded, "wb") as f:
        f.write(encoded.tobytes())
    
    print(f"Saved decoded PCM to {args.output} and encoded ADPCM to {args.encoded}")
