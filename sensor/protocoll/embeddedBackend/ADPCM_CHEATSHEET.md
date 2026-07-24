# ADPCM Workflow Cheat Sheet

## Quick Reference Commands

### Generate Test Files

```bash
# Generate complete ADPCM test suite (RECOMMENDED)
./generate_test_adpcm.sh

# Generate German audio only
python3 generate_german_audio.py -d my_samples

# Convert to ADPCM only
cd backend-php-rag
php convert_to_adpcm.php -d ../sensor/protocoll/german_audio_samples -m metadata.json
```

### Run Tests

```bash
# Complete workflow test (RECOMMENDED)
python3 test_ad_workflow.py

# Conversation tracking test
python3 test_sensor_conversation.py

# Manual upload test
python3 protoEngine.py -i adpcm_test_samples/01_hallo_wie_geht_es_dir.adpcm --format adpcm
```

### Quick Commands

```bash
# List available ADPCM test files
ls -lh adpcm_test_samples/*.adpcm

# Show sample sentences
python3 generate_german_audio.py -s

# List German audio samples
ls -lh german_audio_samples/*.wav

# Check metadata
cat adpcm_test_samples/metadata.json
```

## Sensor API

### Upload ADPCM

```python
from protoEngine import ProtoEngine

# Standard ADPCM upload
pt = ProtoEngine(ssid, url, sensor_id, sensor_key)
pt.connect()
pt.join()

with open("audio.adpcm", "rb") as f:
    audio_data = f.read()

response = pt.upload(audio_data, format="adpcm")

# Check response
if response["status"] == "ok":
    print(f"Conversation ID: {response['conversation_id']}")
    print(f"Reset: {response['conversation_reset']}")
    print(f"Transcription: {response['transcription']}")
    print(f"Response: {response['response']}")
```

## Response Format

```json
{
  "status": "ok",
  "transcription": "Hallo, wie geht es dir?",
  "classification": ["personal"],
  "response": "Mir geht es gut!",
  "conversation_id": "conv_abc123_1234567890",
  "conversation_reset": true,
  "message_count": 1
}
```

## Key Files

| File | Purpose |
|------|---------|
| `protoEngine.py` | Sensor protocol implementation |
| `generate_test_adpcm.sh` | Master generation script |
| `generate_german_audio.py` | German audio generation |
| `backend-php-rag/convert_to_adpcm.php` | ADPCM conversion |
| `test_ad_workflow.py` | Complete workflow tests |
| `adpcm_test_samples/` | Generated ADPCM files |

## Conversation States

| Condition | Behavior |
|-----------|----------|
| First upload | `reset: true`, New conversation ID |
| Subsequent uploads | `reset: false`, Same conversation ID |
| User says "Stop" | `reset: true`, New conversation ID |
| 2-minute timeout | `reset: true`, New conversation ID |

## Typical Workflow

1. **Setup (one time)**
   ```bash
   ./generate_test_adpcm.sh  # Generates test files
   ```

2. **Testing (any time)**
   ```bash
   python3 test_ad_workflow.py  # Run complete tests
   ```

3. **Manual testing (as needed)**
   ```bash
   python3 protoEngine.py -i adpcm_test_samples/01_hallo_wie_geht_es_dir.adpcm --format adpcm
   ```

## Troubleshooting

### Not transcribing
- Check audio quality: `play german_audio_samples/01_*.wav`
- Verify Whisper: `whisper-cli --help`
- Check backend logs for errors

### No conversation tracking
- Verify backend URL: Must use `sensorRagUpload.php`
- Check response format includes conversation fields
- Test with simple file first

### ADPCM conversion fails
- Check PHP: `php --version`
- Verify codec path: `ls -l backend-php-rag/codec.php`
- Test conversion: `php convert_to_adpcm.php -h`

## Performance Benchmarks

| Operation | Time | Size |
|-----------|------|------|
| ADPCM upload | < 0.1s | 2-8KB |
| Whisper transcription | 2-5s | N/A |
| LLM processing | 1-3s | N/A |
| TTS + playback | 2-4s | N/A |
| **Total per request** | **5-12s** | **< 512KB** |

## Environment Requirements

```bash
# Check dependencies
which python3           # Python 3.8+
which php               # PHP 8.0+
which ffmpeg            # For audio resampling
/opt/pyenvs/piper/bin/piper  # Piper TTS
ls /opt/whisper/models/*     # Whisper model
ls /opt/pyenvs/piper/voices/*  # German voice model
```

## Sample Test Cases

The system includes 21 German test sentences:

```bash
# Test different conversation scenarios
01-05: Greetings and basic questions
06-10: Complex and specific questions  
11-15: Conversational follow-ups
16-20: Tree/Platane specific questions
21: Stop command
```

## Quick Tips

✅ **Always use `--format adpcm`** - Sensor default format
✅ **Check `conversation_reset`** - Detect new conversations  
✅ **Track `conversation_id`** - Monitor conversation continuity
✅ **Use provided test files** - They're optimized for the system
✅ **Run `test_ad_workflow.py`** - Verify everything works
✅ **Generate custom audio** - Use generate_german_audio.py for new content

## Common Issues

| Issue | Solution |
|-------|----------|
| No transcription | Check audio quality and Whisper installation |
| No conversation tracking | Ensure using sensorRagUpload.php |
| ADPCM conversion fails | Check PHP and codec.php installation |
| Upload timeout | Check network and backend status |
| Wrong conversation ID | Verify conversation reset logic |

Remember: The sensor ALWAYS sends ADPCM format. The backend handles all processing including transcription, LLM, and audio playback!