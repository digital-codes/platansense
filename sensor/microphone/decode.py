import struct

def write_adpcm_wav(input_path, output_path, sample_rate=22050, num_channels=1, block_align=256):
    with open(input_path, "rb") as f:
        adpcm_data = f.read()

    # IMA ADPCM mono: samplesPerBlock = ((blockAlign - 4) * 2) + 1
    samples_per_block = ((block_align - 4) * 2) + 1
    byte_rate = (sample_rate * block_align) // samples_per_block

    # Chunks
    fmt_chunk_size = 20  # 18 + 2 (for extra bytes)
    data_chunk_size = len(adpcm_data)
    riff_chunk_size = 4 + (8 + fmt_chunk_size) + (8 + data_chunk_size)

    with open(output_path, "wb") as out:
        # RIFF chunk
        out.write(b'RIFF')
        out.write(struct.pack('<I', riff_chunk_size))
        out.write(b'WAVE')

        # fmt chunk
        out.write(b'fmt ')
        out.write(struct.pack('<I', fmt_chunk_size))      # fmt chunk size
        out.write(struct.pack('<H', 0x11))                # WAVE_FORMAT_ADPCM
        out.write(struct.pack('<H', num_channels))        # mono
        out.write(struct.pack('<I', sample_rate))         # sample rate
        out.write(struct.pack('<I', byte_rate))           # byte rate
        out.write(struct.pack('<H', block_align))         # block align
        out.write(struct.pack('<H', 4))                   # bits per sample (ignored)
        out.write(struct.pack('<H', 2))                   # cbSize (2 bytes follow)
        out.write(struct.pack('<H', samples_per_block))   # samples per block

        # data chunk
        out.write(b'data')
        out.write(struct.pack('<I', data_chunk_size))
        out.write(adpcm_data)

    print(f"✅ Correct IMA ADPCM WAV written: {output_path}")

input = "recorded_audio.adpcm"
output = "decoded_audio.wav"

write_adpcm_wav(input, output)
