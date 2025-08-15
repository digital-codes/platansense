Encode with sox to adpcm

sox output_something  -r 8000  audio_8000.wav gain -n
sox audio_8000.wav -t ima -e ima-adpcm -r 8000 -c 1 test_8000.adpcm

