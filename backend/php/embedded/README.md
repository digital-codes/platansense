# Sensor RAG Upload Backend

This is an enhanced version of the sensorUpload.php script that includes RAG (Retrieval-Augmented Generation) chat functionality. It processes audio input from sensors, transcribes it using Whisper, classifies the input, generates responses using local Ollama, and plays the response via bluetooth speaker using Piper TTS.

## Features

- JWT-based sensor authentication (preserved from original sensorUpload.php)
- ADPCM codec support (preserved from original sensorUpload.php)
- Real-time audio transcription using Whisper
- Two-pass LLM processing:
  1. Classification pass: Categorizes user input into predefined categories
  2. Response pass: Generates contextual response based on classification and conversation history
- Conversation state management with automatic timeout
- Text-to-speech synthesis using Piper
- Bluetooth speaker audio output
- Local Ollama integration (no API keys required)

## Directory Structure

```
backend-php-rag/
├── audio/              # Temporary audio storage
├── data/               # RAG configuration data
│   ├── classifier_prompt.json  # Classification prompt
│   ├── classes.json            # Category definitions
│   ├── prompts.json            # Persona-based prompts
│   └── context.json            # Context information per category
├── composer.json       # PHP dependencies
├── codec.php           # ADPCM codec functionality
├── buildToken.php      # JWT token creation
├── checkToken.php      # JWT token validation
└── sensorRagUpload.php # Main application script
```

## Requirements

- PHP 8.0 or higher
- Composer
- Whisper CLI: `/opt/whisper/models/ggml-base-q8_0.bin`
- Piper TTS: `/opt/pyenvs/piper/bin/piper` with German voice
- Ollama running locally on port 11434
- Model: `granite4.1:3b`
- Bluetooth speaker device configured for aplay

## Installation

1. Install PHP dependencies:
```bash
cd /home/agent/projects/orinchat/platansense/backend-php-rag
composer install
```

2. Ensure Whisper is installed and configured:
```bash
# Whisper should be available at
# whisper-cli -m /opt/whisper/models/ggml-base-q8_0.bin -otxt -of sampledecoded_w -f sampleaudio_w.wav -l de
```

3. Ensure Piper TTS is installed:
```bash
# Piper should be available at
# /opt/pyenvs/piper/bin/piper -m /opt/pyenvs/piper/voices/de_DE-thorsten-low.onnx -i sampletext.txt -f sampleaudio.wav -o .
```

4. Ensure Ollama is running:
```bash
# Start Ollama service
ollama serve

# Pull the required model
ollama pull granite4.1:3b
```

5. Ensure bluetooth speaker is configured:
```bash
# Test audio output
aplay -D bluealsa:DEV=20:0E:5A:1E:43:6C,PROFILE=a2dp,SRV=org.bluealsa test.wav
```

## Configuration

### Conversation Timeout

Default timeout is 2 minutes. To modify, edit the following line in `sensorRagUpload.php`:

```php
$conversationTimeoutMinutes = 2; // Change this value
```

### Ollama Configuration

Default settings:
- URL: `http://localhost:11434/api/chat`
- Model: `granite4.1:3b`

To modify, edit these lines in `sensorRagUpload.php`:

```php
$ollamaUrl = 'http://localhost:11434/api/chat';
$ollamaModel = 'granite4.1:3b';
```

### RAG Categories

The system includes these predefined categories:
- `city`: City planning, infrastructure, construction
- `technology`: AI, technology, smart city solutions
- `protection`: Climate change, sustainability, environmental protection
- `actionism`: Protest, political action, social engagement
- `nature`: Biology, ecology, trees, plants
- `personal`: Direct user interactions with the tree
- `unrelated`: Topics unrelated to trees, nature, or city

### Personas

Available response personas (in `data/prompts.json`):
- `Aktivist`: Environmentally active tree
- `Alchimist`: Technology-interested tree  
- `Antagonist`: Optimistic about development
- `Absolutist`: Pragmatic, development-focused

## Usage

### API Endpoints

The script supports the same commands as the original sensorUpload.php:

#### 1. Join Request
```bash
curl -X POST http://your-server/sensorRagUpload.php \
  -H "Content-Type: application/json" \
  -d '{
    "command": "join",
    "id": "sensor123"
  }'
```

Response:
```json
{
  "session": "abc123...",
  "challenge": "def456...",
  "iv": "789xyz..."
}
```

#### 2. Challenge Response  
```bash
curl -X POST http://your-server/sensorRagUpload.php \
  -H "Content-Type: application/json" \
  -d '{
    "command": "challenge",
    "id": "sensor123",
    "session": "abc123...",
    "challenge": "encrypted_response..."
  }'
```

Response:
```json
{
  "token": "jwt_token_here"
}
```

#### 3. Data Upload (Audio with RAG Processing)
```bash
curl -X POST http://your-server/sensorRagUpload.php \
  -H "Content-Type: application/json" \
  -d '{
    "command": "data",
    "id": "sensor123",
    "token": "jwt_token_here",
    "format": "adpcm",
    "data": "base64_encoded_audio_data"
  }'
```

Response:
```json
{
  "uuid": "Sensor123_abc123...",
  "status": "ok",
  "transcription": "Transcribed text from audio",
  "classification": ["city", "technology"],
  "response": "Generated response text",
  "audio_played": true
}
```

## Conversation Management

### Starting a New Conversation

The conversation automatically resets when:
1. User says "stop" (case-insensitive)
2. No interaction for 2 minutes (configurable)

To manually reset:
```bash
rm /home/agent/projects/orinchat/platansense/backend-php-rag/data/*_conversation.json
```

### Conversation Storage

Conversation history is stored per sensor in:
```
data/{sensor_id}_conversation.json
```

Each conversation stores up to 10 message pairs.

## Pipeline Flow

1. **Authentication**: JWT token validation
2. **Audio Processing**: ADPCM decoding and WAV conversion
3. **Transcription**: Whisper converts audio to text
4. **Conversation Check**: Validates conversation continuity
5. **Classification**: Categorizes user input using LLM
6. **Context Assembly**: Builds context from classifications
7. **Response Generation**: LLM generates contextual response
8. **Conversation Update**: Updates message history
9. **Audio Synthesis**: Piper converts response to audio
10. **Audio Playback**: Plays response via bluetooth speaker

## Troubleshooting

### Whisper fails to transcribe
- Check Whisper model path: `/opt/whisper/models/ggml-base-q8_0.bin`
- Verify audio file format
- Check language parameter matches input

### Piper synthesis fails
- Verify Piper installation: `/opt/pyenvs/piper/bin/piper`
- Check voice model: `/opt/pyenvs/piper/voices/de_DE-thorsten-low.onnx`
- Ensure output directory is writable

### Ollama connection fails
- Verify Ollama is running: `ollama serve`
- Check model is available: `ollama list`
- Verify URL and port configuration

### Bluetooth audio fails
- Check bluetooth device is connected
- Verify device address: `20:0E:5A:1E:43:6C`
- Test with aplay directly

### Permission issues
- Ensure audio and data directories are writable
- Check file permissions for temporary files
- Verify JWT configuration file access

## Security Considerations

- All sensor requests require valid JWT authentication
- Audio data size limited to 512KB
- Conversation state isolated per sensor
- No external API calls (all local processing)
- Temporary files cleaned up after processing

## Performance Notes

- Processing is synchronous (no parallel requests)
- Typical processing time per audio input:
  - Transcription: 2-5 seconds
  - Classification: 1-2 seconds  
  - Response generation: 2-5 seconds
  - Synthesis: 1-3 seconds
  - Total: ~6-15 seconds per interaction

## Maintenance

### Regular Cleanup
```bash
# Clean old audio files (older than 1 day)
find /home/agent/projects/orinchat/platansense/backend-php-rag/audio -type f -mtime +1 -delete

# Clean stale conversation files (older than 1 week)
find /home/agent/projects/orinchat/platansense/backend-php-rag/data -name "*_conversation.json" -mtime +7 -delete
```

### Monitoring
Monitor log files and error responses for:
- Transcription failures
- Ollama connection issues
- TTS synthesis problems
- Authentication failures

## Extending the System

### Adding New Categories
Edit `data/classes.json`:
```json
{
  "new_category": "Description of the new category"
}
```

Add context in `data/context.json`:
```json
[
  {
    "new_category": "Context information for the new category"
  }
]
```

### Adding New Personas
Edit `data/prompts.json`:
```json
{
  "NewPersona": "Persona description and behavior guidelines"
}
```

### Modifying Classification
Edit `data/classifier_prompt.json` to adjust classification behavior.

## References

- Original sensorUpload.php: Authentication and codec functionality
- Original sensorChat.php: Audio processing patterns
- Original sensorChatLlm.php: LLM integration examples
- platanapp/php/plataChat.php: Chat workflow and session management
- rag_demo: RAG classification and context structure
- pipeline-commands.txt: Command examples for Whisper, Piper, and audio playback