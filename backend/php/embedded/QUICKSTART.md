# Quick Start Guide

This guide will help you get the Sensor RAG Upload Backend running quickly.

## Prerequisites

- Linux system with Python 3, PHP 8.0+, and Composer
- Access to install Whisper, Piper TTS, and Ollama
- Bluetooth speaker configured

## Installation Steps

### 1. Install Dependencies

```bash
# Navigate to the project directory
cd /home/agent/projects/orinchat/platansense/backend-php-rag

# Install PHP dependencies
composer install
```

### 2. Install and Configure Whisper

```bash
# Install Whisper CLI (if not already installed)
# Follow instructions at: https://github.com/openai/whisper

# Ensure the model is available at:
# /opt/whisper/models/ggml-base-q8_0.bin

# Test Whisper
whisper-cli --help
```

### 3. Install and Configure Piper TTS

```bash
# Install Piper TTS (if not already installed)
# Follow instructions at: https://github.com/rhasspy/piper

# Ensure German voice is available at:
# /opt/pyenvs/piper/voices/de_DE-thorsten-low.onnx

# Test Piper
/opt/pyenvs/piper/bin/piper --help
```

### 4. Install and Configure Ollama

```bash
# Install Ollama (if not already installed)
# Follow instructions at: https://ollama.com

# Start Ollama service
ollama serve

# Pull the required model
ollama pull granite4.1:3b

# Test Ollama
curl http://localhost:11434/api/tags
```

### 5. Configure Bluetooth Audio

```bash
# Ensure bluetooth speaker is connected
# Adjust device address in configuration if needed
# Device: 20:0E:5A:1E:43:6C

# Test audio playback
aplay -D bluealsa:DEV=20:0E:5A:1E:43:6C,PROFILE=a2dp,SRV=org.bluealsa test.wav
```

### 6. Set Up Configuration Files

```bash
# Create configuration directory
sudo mkdir -p /var/www/files/platane

# Create config.ini
sudo nano /var/www/files/platane/config.ini
```

Add the following content:

```ini
[JWT]
key = your-32-byte-hex-encoded-key-here
relatedTo = platansense-rag-backend
issuedBy = your-organization
```

Create devices.json:

```bash
sudo nano /var/www/files/platane/devices.json
```

Add the following content:

```json
{
  "sensor001": "a1b2c3d4e5f6",
  "sensor002": "f6e5d4c3b2a1"
}
```

### 7. Test the Installation

```bash
# Run the comprehensive test suite
php testRagPipeline.php

# Or test individual pipeline commands
./test_pipeline_commands.sh
```

## Basic Usage

### Start the Backend

You can serve the PHP file using a web server or PHP's built-in server:

```bash
# Using PHP built-in server (for testing)
php -S localhost:8000

# Or configure Apache/Nginx (see CONFIGURATION.md)
```

### Send a Test Request

```bash
# Use the example client
python3 example_client.py --test-auth

# Or test with curl (requires proper authentication)
curl -X POST http://localhost:8000/sensorRagUpload.php \
  -H "Content-Type: application/json" \
  -d '{
    "command": "join",
    "id": "sensor001"
  }'
```

## Pipeline Overview

When you send audio data, the system will:

1. **Authenticate** the sensor using JWT tokens
2. **Decode** audio from ADPCM format
3. **Transcribe** audio to text using Whisper
4. **Check** conversation continuity (timeout or "stop" command)
5. **Classify** the input into categories
6. **Select** appropriate persona and context
7. **Generate** response using Ollama
8. **Synthesize** response to audio using Piper TTS
9. **Play** response via Bluetooth speaker
10. **Return** results including transcription and response

## Troubleshooting

### Common Issues

**Whisper not working:**
```bash
# Check if Whisper is installed
which whisper-cli

# Verify model file
ls -lh /opt/whisper/models/ggml-base-q8_0.bin

# Test with a real audio file
whisper-cli -m /opt/whisper/models/ggml-base-q8_0.bin -otxt -of test -f test.wav -l de
```

**Piper TTS not working:**
```bash
# Check if Piper is installed
ls -lh /opt/pyenvs/piper/bin/piper

# Verify voice model
ls -lh /opt/pyenvs/piper/voices/de_DE-thorsten-low.onnx

# Test TTS
echo "Test" > /tmp/test.txt
/opt/pyenvs/piper/bin/piper -m /opt/pyenvs/piper/voices/de_DE-thorsten-low.onnx -i /tmp/test.txt -f /tmp/test.wav -o .
```

**Ollama not working:**
```bash
# Check if Ollama is running
ps aux | grep ollama

# Start Ollama if not running
ollama serve

# Check available models
ollama list

# Test with a simple query
curl http://localhost:11434/api/chat -d '{
  "model": "granite4.1:3b",
  "messages": [{"role": "user", "content": "Say hello"}],
  "stream": false
}'
```

**Bluetooth audio not working:**
```bash
# Check bluetooth status
bluetoothctl

# List connected devices
bluetoothctl devices

# Test audio playback
aplay -D bluealsa:DEV=20:0E:5A:1E:43:6C,PROFILE=a2dp,SRV=org.bluealsa /usr/share/sounds/alsa/Front_Center.wav
```

**Permission issues:**
```bash
# Fix directory permissions
chmod -R 755 /home/agent/projects/orinchat/platansense/backend-php-rag
chown -R www-data:www-data /home/agent/projects/orinchat/platansense/backend-php-rag
```

## Next Steps

1. **Configure Apache/Nginx** for production use (see CONFIGURATION.md)
2. **Set up monitoring** to track performance and errors
3. **Customize categories and prompts** in the data/ directory
4. **Implement proper authentication** in your sensor devices
5. **Test with real audio** from your sensors

## Getting Help

- Check the main README.md for detailed documentation
- Review CONFIGURATION.md for server setup
- Examine example_client.py for API usage patterns
- Run testRagPipeline.php for system diagnostics

## Performance Tips

- Use SSD storage for audio files if processing many requests
- Monitor Ollama memory usage and memory as needed
- Adjust conversation timeout based on your use case
- Consider caching frequent responses to reduce LLM calls

## Security Notes

- Keep your JWT keys and device keys secret
- Use HTTPS in production environments
- Regularly rotate device keys
- Monitor for unusual authentication patterns
- Limit audio file sizes (already set to 512KB maximum)