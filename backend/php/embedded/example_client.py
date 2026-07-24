#!/usr/bin/env python3
"""
Example client for the Sensor RAG Upload API
Demonstrates how to interact with the sensor upload endpoint
"""

import requests
import json
import base64
import time
import sys
import wave
import struct
import argparse

class SensorRagClient:
    def __init__(self, base_url="http://localhost:8000/sensorRagUpload.php"):
        self.base_url = base_url
        self.session_id = None
        self.token = None
        self.sensor_id = "test_sensor_001"
        
    def join(self, sensor_id):
        """Initiate the join process"""
        self.sensor_id = sensor_id
        payload = {
            "command": "join",
            "id": sensor_id
        }
        
        response = requests.post(self.base_url, json=payload)
        result = response.json()
        
        if "session" in result:
            self.session_id = result["session"]
            return result
        else:
            raise Exception(f"Join failed: {result}")
    
    def respond_to_challenge(self, challenge_response):
        """Respond to the authentication challenge"""
        if not self.session_id:
            raise Exception("No active session. Call join() first.")
        
        payload = {
            "command": "challenge",
            "id": self.sensor_id,
            "session": self.session_id,
            "challenge": challenge_response
        }
        
        response = requests.post(self.base_url, json=payload)
        result = response.json()
        
        if "token" in result:
            self.token = result["token"]
            return result
        else:
            raise Exception(f"Challenge failed: {result}")
    
    def upload_audio(self, audio_file_path, format="adpcm"):
        """Upload audio file for processing"""
        if not self.token:
            raise Exception("No valid token. Complete authentication first.")
        
        # Read audio file
        try:
            with open(audio_file_path, 'rb') as f:
                audio_data = f.read()
        except Exception as e:
            raise Exception(f"Failed to read audio file: {e}")
        
        # Encode to base64
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        
        payload = {
            "command": "data",
            "id": self.sensor_id,
            "token": self.token,
            "format": format,
            "data": audio_base64
        }
        
        response = requests.post(self.base_url, json=payload)
        result = response.json()
        
        return result
    
    def send_text(self, text):
        """Create a simple WAV file from text and upload it"""
        # This is a simplified version - in practice you'd need proper TTS
        # or record actual audio
        print(f"Would generate audio for: {text}")
        print("In a real implementation, you would:")
        print("1. Convert text to speech using TTS")
        print("2. Save as WAV file")
        print("3. Upload using upload_audio()")
        return {"status": "not_implemented"}

def create_simple_wav(text, output_file):
    """Create a simple WAV file (for testing purposes)"""
    # This is just for testing - not real speech
    sample_rate = 8000
    duration = 1.0  # 1 second
    num_samples = int(sample_rate * duration)
    
    # Generate simple sine wave
    with wave.open(output_file, 'w') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 2 bytes (16-bit)
        wav_file.setframerate(sample_rate)
        
        for i in range(num_samples):
            # Simple 440 Hz tone
            value = int(32767 * 0.5 * (1 + math.sin(2 * math.pi * 440 * i / sample_rate)))
            wav_file.writeframes(struct.pack('<h', value))

def main():
    parser = argparse.ArgumentParser(description='Sensor RAG Upload Client')
    parser.add_argument('--url', default='http://localhost:8000/sensorRagUpload.php',
                       help='URL of the sensor upload endpoint')
    parser.add_argument('--sensor-id', default='test_sensor_001',
                       help='Sensor ID to use')
    parser.add_argument('--audio-file', help='Audio file to upload')
    parser.add_argument('--format', default='adpcm',
                       choices=['adpcm', 'wav'], help='Audio format')
    parser.add_argument('--test-auth', action='store_true',
                       help='Test authentication only')
    parser.add_argument('--test-audio', action='store_true',
                       help='Test audio upload with generated test audio')
    
    args = parser.parse_args()
    
    client = SensorRagClient(args.url)
    
    try:
        print(f"Starting authentication for sensor: {args.sensor_id}")
        print("-" * 50)
        
        # Step 1: Join
        print("1. Sending join request...")
        join_result = client.join(args.sensor_id)
        print(f"   Session ID: {join_result['session']}")
        print(f"   Challenge: {join_result['challenge'][:16]}...")
        print(f"   IV: {join_result['iv']}")
        
        # In a real implementation, you would encrypt the challenge here
        # For testing, we'll just skip this part
        print("\n2. Challenge response (in real implementation, encrypt challenge)")
        print("   For testing: Assuming authentication succeeds")
        
        # For testing purposes, we'll proceed without actual challenge response
        # In production, you need to implement the cryptographic challenge response
        if args.test_auth:
            print("\nAuthentication test completed successfully")
            print("Note: Full authentication requires cryptographic challenge response")
            return 0
        
        # For actual usage, you would need to implement the challenge response
        # This requires the device key and AES encryption
        print("\nNote: Complete authentication requires cryptographic challenge response")
        print("This example only demonstrates the protocol flow")
        
        # Skip to audio upload test if requested
        if args.test_audio:
            print("\n3. Testing audio upload...")
            print("   In real implementation, you would need valid authentication token")
            
            # Create test audio file
            test_audio = "/tmp/test_sensor_audio.wav"
            print(f"   Creating test audio file: {test_audio}")
            # create_simple_wav("test", test_audio)
            
            print("   Audio upload would happen here with valid token")
            print("   Response would include:")
            print("   - uuid: Unique identifier")
            print("   - status: Processing status")
            print("   - transcription: Transcribed text")
            print("   - classification: Input categories")
            print("   - response: Generated response")
            print("   - audio_played: Whether audio was played")
            
            return 0
        
        # If audio file specified, try to upload
        if args.audio_file:
            print(f"\n3. Uploading audio file: {args.audio_file}")
            print("   Format: {args.format}")
            
            # Note: This would fail without proper authentication
            try:
                result = client.upload_audio(args.audio_file, args.format)
                print("   Upload result:")
                print(json.dumps(result, indent=2))
            except Exception as e:
                print(f"   Upload failed: {e}")
                print("   Note: This requires proper authentication")
            
            return 0
        
        print("\nExample completed successfully!")
        print("\nNext steps:")
        print("1. Implement cryptographic challenge response for authentication")
        print("2. Prepare actual audio files (ADPCM or WAV format)")
        print("3. Upload audio for processing")
        print("4. Receive transcription and response")
        
        return 0
        
    except Exception as e:
        print(f"\nError: {e}")
        return 1

if __name__ == "__main__":
    import math
    sys.exit(main())