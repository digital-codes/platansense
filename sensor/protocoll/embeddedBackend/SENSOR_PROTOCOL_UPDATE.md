# Sensor Protocol Update - Conversation Tracking

## Overview

The sensor protocol has been updated to work with the new RAG backend. The sensor now only needs to upload audio data and receive immediate responses. Download functionality is no longer required as it's handled by the backend.

## Key Changes

### 1. Simplified Workflow

**Previous (Old Protocol):**
1. Upload audio → `sensorUpload.php`
2. Check if ready → `sensorDownload.php` (polling)
3. Download response chunks → `sensorDownload.php`
4. Play audio locally

**New (RAG Protocol):**
1. Upload audio → `sensorRagUpload.php`
2. Receive immediate response (transcription, classification, response text)
3. Backend handles transcription, LLM processing, and audio playback

### 2. Conversation Tracking

The backend now tracks conversations and provides conversation state information to the sensor:

#### Response Format

```json
{
  "uuid": "Sensor_1_abc123def456",
  "status": "ok",
  "transcription": "Guten Tag, wie geht es Ihnen?",
  "classification": ["personal", "nature"],
  "response": "Mir geht es gut! Ich bin eine Platane in Karlsruhe.",
  "audio_played": true,
  "conversation_id": "conv_a1b2c3d4e5f6_1234567890",
  "conversation_reset": true,
  "conversation_timestamp": 1234567890,
  "message_count": 1
}
```

#### Conversation Tracking Fields

- **`conversation_id`**: Unique identifier for current conversation
- **`conversation_reset`**: Boolean - `true` if conversation was just reset
- **`conversation_timestamp`**: Unix timestamp when conversation started
- **`message_count`**: Number of message exchange pairs in current conversation

### 3. Conversation State Management

The backend automatically manages conversation state:

#### When Conversations Reset

1. **Stop Command**: User says "stop" (case-insensitive)
2. **Timeout**: No interaction for configured timeout (default: 2 minutes)

#### Conversation Lifecycle

```
New Conversation (id: conv_abc123, reset: true, count: 0)
  ↓
Upload 1 → (id: conv_abc123, reset: true, count: 1)
  ↓
Upload 2 → (id: conv_abc123, reset: false, count: 2)
  ↓
Upload 3 → (id: conv_abc123, reset: false, count: 3)
  ↓
Stop/Timeout → New Conversation (id: conv_def456, reset: true, count: 0)
```

## Updated ProtoEngine API

### New Capabilities

#### Conversation Tracking Properties

```python
pt = ProtoEngine(ssid, baseUrl, id, key)
pt.conversation_id      # Current conversation ID (read-only)
pt.conversation_reset   # Was last upload a conversation reset (read-only)
```

#### Enhanced Upload Response

The `upload()` method now automatically updates conversation tracking:

```python
resp = pt.upload(audio_data, format="adpcm")

# Access conversation tracking information
if resp.get("status") == "ok":
    conv_id = resp.get("conversation_id")
    conv_reset = resp.get("conversation_reset")
    msg_count = resp.get("message_count")
```

### Deprecated Methods

The following methods are deprecated with the RAG backend:

- `check()` - File checking is handled server-side
- `download()` - Response processing is handled server-side

These methods are kept for compatibility but emit warnings when used.

## Usage Examples

### Basic Upload with Conversation Tracking

```python
from protoEngine import ProtoEngine

# Initialize sensor
pt = ProtoEngine("network.ssid", "http://localhost:8000", 1, "sensor_key")
pt.setDebug(True)

# Connect and authenticate
pt.connect()
pt.join()

# Read audio file (WAV format)
with open("audio.wav", "rb") as f:
    audio_data = f.read()

# Strip WAV header to get raw PCM
audio_data = audio_data[44:]  # Remove 44-byte header

# Upload and receive immediate response
resp = pt.upload(audio_data, format="adpcm")

# Check the response
if resp.get("status") == "ok":
    print(f"Transcription: {resp.get('transcription')}")
    print(f"Classification: {resp.get('classification')}")
    print(f"Response: {resp.get('response')}")
    print(f"Conversation ID: {resp.get('conversation_id')}")
    print(f"Conversation Reset: {resp.get('conversation_reset')}")
    print(f"Message Count: {resp.get('message_count')}")
    
    # Check if this was a conversation reset
    if resp.get("conversation_reset"):
        print("🔄 New conversation started")
    else:
        print("➡️  Conversation continued")

# Disconnect
pt.disconnect()
```

### Monitoring Conversation Resets

```python
# Track conversation changes across uploads
previous_conv_id = None

for i in range(5):
    # Read and upload audio
    with open(f"audio_{i}.wav", "rb") as f:
        audio_data = f.read()[44:]
    
    resp = pt.upload(audio_data, format="adpcm")
    
    # Check conversation state
    current_conv_id = resp.get("conversation_id")
    conv_reset = resp.get("conversation_reset")
    msg_count = resp.get("message_count")
    
    # Detect conversation changes
    if current_conv_id != previous_conv_id:
        print(f"🆕 New conversation started: {current_conv_id}")
        previous_conv_id = current_conv_id
    
    if conv_reset:
        print(f"🔄 Conversation was reset (stop/timeout)")
    
    print(f"💬 Message {msg_count} in conversation: {current_conv_id}")
```

### Using Command-Line Interface

```bash
# Basic usage with test audio file
python3 protoEngine.py \
  --url http://localhost:8000 \
  --input test_speech.wav \
  --format wav

# With custom sensor configuration
python3 protoEngine.py \
  --url http://localhost:8000 \
  --input audio.wav \
  --format wav \
  --sensor-id 2 \
  --key "aabbccddeeff1122"
```

## Response Status Codes

The RAG backend returns these status codes:

### Success Statuses

- **`"ok"`**: Processing completed successfully
  - All fields available (transcription, classification, response, etc.)
  - Conversation tracking information included

### Error Statuses

- **`"transcription_failed"`**: Whisper transcribe failed
  - No transcription, classification, or response available
  
- **`"llm_failed"`**: LLM processing failed
  - Transcription成功但AI响应失败

- **`"tts_failed"`**: Piper TTS synthesis failed
  - Text response available but audio generation failed

- **`"not_authorizedX"`**: Authentication failed (various codes)
  - JWT token invalid

## Best Practices

### 1. Conversation State Handling

```python
# Always check conversation_reset flag
if resp.get("conversation_reset"):
    # This is a new conversation
    # Clear any local state if needed
    pass
```

### 2. Error Handling

```python
status = resp.get("status")
if status == "ok":
    # Success case
    pass
elif status == "transcription_failed":
    # Audio quality issue
    print("⚠️  Could not understand audio"
elif status == "llm_failed":
    # Backend processing issue
    print("⚠️  AI processing failed")
else:
    # Other errors
    print(f"❌ Error: {status}")
```

### 3. Audio Quality

The conversation tracking works best with clear audio:

```python
# Ensure good audio quality before upload
if len(audio_data) < 1000:
    print("⚠️  Audio too short, may not transcribe well")

if len(audio_data) > 512 * 1024:  # 512KB limit
    print("❌ Audio too large")

# Use appropriate format
format = "adpcm"  # For compressed audio
format = "wav"    # For raw PCM (auto-strips header)
```

## Testing

### Run Conversation Tracking Tests

```bash
# Generate test audio
python3 generate_test_audio.py -f test_speech.wav -t speech

# Run conversation tests
python3 test_sensor_conversation.py

# Or test manually
python3 protoEngine.py --url http://localhost:8000 --input test_speech.wav
```

### Expected Test Results

```
============================================================
RAG Processing Results
============================================================
Status: ok
UUID: Sensor_1_abc123def456

🔗 Conversation Tracking:
  ID: conv_a1b2c3d4e5f6_1234567890
  Reset: Yes (stop/timeout)
  Started: 2024-07-23 15:30:45
  Messages: 1

📝 Transcription:
  Guten Tag, wie geht es Ihnen?

🏷️  Classification:
  - personal
  - nature

💬 AI Response:
  Mir geht es gut! Ich bin eine Platane in Karlsruhe.

🔊 Audio Playback: ✅ Success

============================================================
✅ Complete - Backend handled transcription, classification, and audio playback
```

## Migration Guide

### From Old Protocol to New Protocol

#### Old Code Pattern
```python
# Old: Upload, poll for readiness, download
resp = pt.upload(audio_data)
name = resp.get("uuid")

# Poll for readiness
while True:
    resp = pt.check(name)
    if resp.get("status") == "ready":
        break
    time.sleep(1)

# Download and process
chunks = resp.get("chunks")
for i in range(chunks):
    resp = pt.download(name, i)
    # Process audio chunk locally
```

#### New Code Pattern
```python
# New: Upload and receive immediate response
resp = pt.upload(audio_data)

# Process response immediately
if resp.get("status") == "ok":
    transcription = resp.get("transcription")
    classification = resp.get("classification")
    response = resp.get("response")
    conv_id = resp.get("conversation_id")
    
    # All processing handled by backend
```

## Troubleshooting

### Conversation ID Issues

**Problem**: Conversation ID is None
```python
# Solution: Check backend response format
if resp.get("conversation_id") is None:
    print("⚠️  No conversation ID - may be using old backend")
```

**Problem**: Conversation ID changes unexpectedly
```python
# Solution: Check for reset conditions
if resp.get("conversation_reset"):
    print("🔄 Expected conversation reset (stop/timeout)")
elif pt.conversation_id != resp.get("conversation_id"):
    print("⚠️  Unexpected conversation ID change")
```

### Debug Mode

Enable debug mode for detailed logging:

```python
pt.setDebug(True)
```

This will show:
- Network connection details
- Authentication steps
- Upload progress
- Conversation tracking updates
- Response details

## Security Considerations

1. **Conversation Privacy**: All conversation state is stored server-side in JSON files
2. **ID Security**: Conversation IDs are randomly generated and not predictable
3. **Timeout Protection Automatic timeout prevents conversation hijacking**
4. **Reset Protection**: Only stop command or timeout can reset conversations

## Conclusion

The updated sensor protocol simplifies the workflow significantly:

- ✅ No more polling and waiting
- ✅ Immediate responses with full context
- ✅ Built-in conversation tracking
- ✅ Automatic conversation management
- ✅ Server-side audio processing

The sensor now focuses solely on audio capture and upload, while the backend handles all the intelligence.