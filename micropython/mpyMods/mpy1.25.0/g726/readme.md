FFmpeg can encode raw PCM (or WAV) to G.726 in .g726 format directly.
🛠️ Convert WAV → G.726 (16 kbps):

ffmpeg -i input.wav -ar 8000 -ac 1 -c:a g726 -b:a 16k output.g726

    -ar 8000 sets sample rate

    -ac 1 mono

    -c:a g726 enables the codec

    -b:a 16k selects 16 kbps (2-bit/sample mode)

    🔄 Output is a raw G.726 bitstream (typically no header).


     G.726 → WAV using FFmpeg

ffmpeg -f g726 -ar 8000 -ac 1 -i input.g726 output.wav

Explanation:
Option	Meaning
-f g726	Tell FFmpeg the input is raw G.726 ADPCM
-ar 8000	Sample rate is 8 kHz
-ac 1	Mono
-i input.g726	Input file
output.wav	Output PCM WAV file
🧪 Round-trip test (WAV → G726 → WAV)

# Encode
ffmpeg -i input.wav -ar 8000 -ac 1 -c:a g726 -b:a 16k -f g726 encoded.g726


# Decode back
ffmpeg -f g726 -ar 8000 -ac 1 -i encoded.g726 roundtrip.wav

You can now compare input.wav vs roundtrip.wav in:

    Audacity

    Python (e.g. scipy.io.wavfile.read)

    File size

    Listening

