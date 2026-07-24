#!/usr/bin/env python3
"""
generate_german_audio.py - Generate German audio samples using Piper TTS
Creates WAV files with German text for testing the sensor upload workflow
"""

import subprocess
import argparse
import json
import os
import sys
import wave
import struct
import tempfile

# German sample sentences for testing
SAMPLE_SENTENCES = [
    "Hallo, wie geht es dir?",
    "Guten Tag, alles gut bei dir?",
    "Wie ist das Wetter heute?",
    "Können Sie mir helfen?",
    "Was ist deine Funktion?",
    "Erzähl mir etwas über dich.",
    "Stop",
    "Kannst du das wiederholen?",
    "Woher kommst du?",
    "Was können wir machen?",
    "Ich verstehe das nicht.",
    "Das ist sehr interesting.",
    "Können wir nochmal anfangen?",
    "Wie lange arbeitest du schon hier?",
    "Was für ein Baum bist du?",
    "Bist du eine echte Platane?",
    "Wann wurdest du gepflanzt?",
    "Wie alt bist du?",
    "Hast du schon Schatten gespendet?",
    "Was machst du im Winter?"
]

def resample_to_8000_mono(input_wav, output_wav):
    """Resample WAV to 8000Hz mono using FFmpeg"""
    
    cmd = [
        'ffmpeg',
        '-y',  # Overwrite output file
        '-i', input_wav,
        '-ar', '8000',  # Sample rate 8000Hz
        '-ac', '1',      # Mono
        '-acodec', 'pcm_s16le',  # 16-bit PCM
        output_wav
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            print(f"FFmpeg error: {result.stderr}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print("FFmpeg timeout")
        return False
    except FileNotFoundError:
        print("FFmpeg not found. Please install FFmpeg.")
        return False

def generate_piper_audio(text, output_wav, voice_model="/opt/pyenvs/pipertts/voices/de_DE-thorsten-low.onnx"):
    """Generate German audio using Piper TTS"""
    
    # Create temporary text file for Piper
    temp_text = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8')
    temp_text.write(text)
    temp_text.close()
    
    # Build Piper command
    cmd = [
        '/opt/pyenvs/pipertts/bin/piper',
        '-m', voice_model,
        '-i', temp_text.name,
        '-f', output_wav,
        '-o', '.'
    ]
    
    try:
        print(f"Generating audio for: {text}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        # Clean up temp file
        os.unlink(temp_text.name)
        
        if result.returncode != 0:
            print(f"Piper error: {result.stderr}")
            return False
        
        # Check if output file was created
        if not os.path.exists(output_wav):
            print(f"Piper failed to create output file: {output_wav}")
            return False
        
        return True
        
    except subprocess.TimeoutExpired:
        print("Piper timeout")
        if os.path.exists(temp_text.name):
            os.unlink(temp_text.name)
        return False
    except FileNotFoundError:
        print("Piper not found at /opt/pyenvs/pipertts/bin/piper")
        if os.path.exists(temp_text.name):
            os.unlink(temp_text.name)
        return False

def list_piper_voices():
    """List available Piper voices"""
    voices_dir = "/opt/pyenvs/pipertts/voices"
    
    if os.path.exists(voices_dir):
        voices = []
        for file in os.listdir(voices_dir):
            if file.endswith('.onnx'):
                voices.append(file)
        
        if voices:
            print("Available Piper voices:")
            for voice in voices:
                print(f"  - {voice}")
            return voices
    
    print(f"No voices found in {voices_dir}")
    return []

def convert_to_raw_pcm(wav_file, output_pcm):
    """Extract raw PCM data from WAV file"""
    try:
        with wave.open(wav_file, 'rb') as wav:
            # Read all audio frames
            frames = wav.readframes(wav.getnframes())
        
        # Write raw PCM data
        with open(output_pcm, 'wb') as f:
            f.write(frames)

        return True
        
    except Exception as e:
        print(f"Error extracting PCM: {e}")
        return False

def generate_sample_sentences(output_dir="german_samples", sentences=None):
    """Generate multiple German sample sentences"""
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    if sentences is None:
        sentences = SAMPLE_SENTENCES
    
    print(f"Generating {len(sentences)} German audio samples...")
    print(f"Output directory: {output_dir}")
    print("-" * 60)
    
    generated_files = []
    
    for i, text in enumerate(sentences, 1):
        # Create filename from text (safe for filesystem)
        safe_text = text.lower().replace(' ', '_').replace(',', '').replace('?', '')[:30]
        wav_filename = f"{i:02d}_{safe_text}.wav"
        pcm_filename = f"{i:02d}_{safe_text}.pcm"
        
        wav_path = os.path.join(output_dir, wav_filename)
        pcm_path = os.path.join(output_dir, pcm_filename)
        
        print(f"\n[{i}/{len(sentences)}] {text}")
        
        # Generate audio with Piper
        temp_wav = tempfile.NamedTemporaryFile(suffix='.wav', delete=False).name
        
        if not generate_piper_audio(text, temp_wav):
            print(f"  ❌ Failed to generate audio")
            continue
        
        # Resample to 8000Hz mono
        if not resample_to_8000_mono(temp_wav, wav_path):
            print(f"  ❌ Failed to resample audio")
            os.unlink(temp_wav)
            continue
        
        # Extract raw PCM
        if not convert_to_raw_pcm(wav_path, pcm_path):
            print(f"  ❌ Failed to extract PCM")
            os.unlink(temp_wav)
            continue
        
        # Clean up temp file
        os.unlink(temp_wav)
        
        print(f"  ✅ Generated: {wav_filename}")
        print(f"  ✅ Extracted: {pcm_filename}")
        
        # Get file info
        wav_size = os.path.getsize(wav_path)
        pcm_size = os.path.getsize(pcm_path)
        print(f"  📊 WAV: {wav_size} bytes, PCM: {pcm_size} bytes")
        
        generated_files.append({
            'text': text,
            'wav': wav_filename,
            'pcm': pcm_filename,
            'index': i
        })
    
    # Generate metadata file
    metadata = {
        'description': 'German audio samples generated with Piper TTS',
        'voice_model': '/opt/pyenvs/piper/voices/de_DE-thorsten-low.onnx',
        'sample_rate': '8000',
        'channels': 'mono',
        'bits_per_sample': '16',
        'count': len(generated_files),
        'files': generated_files
    }
    
    metadata_path = os.path.join(output_dir, 'metadata.json')
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*60}")
    print(f"✅ Generated {len(generated_files)} German audio samples")
    print(f"📁 Output directory: {output_dir}")
    print(f"📄 Metadata: {metadata_path}")
    print(f"{'='*60}")
    
    return generated_files

def generate_single_sample(text, output_wav, output_pcm=None):
    """Generate a single German audio sample"""
    
    print(f"Generating German audio: {text}")
    print("-" * 60)
    
    # Generate audio with Piper
    temp_wav = tempfile.NamedTemporaryFile(suffix='.wav', delete=False).name
    
    if not generate_piper_audio(text, temp_wav):
        return False
    
    # Resample to 8000Hz mono
    if not resample_to_8000_mono(temp_wav, output_wav):
        os.unlink(temp_wav)
        return False
    
    # Extract raw PCM if requested
    if output_pcm:
        if not convert_to_raw_pcm(output_wav, output_pcm):
            os.unlink(temp_wav)
            return False
    
    # Clean up temp file
    os.unlink(temp_wav)
    
    print(f"✅ Generated: {output_wav}")
    if output_pcm:
        print(f"✅ Extracted: {output_pcm}")
    
    return True

def main():
    parser = argparse.ArgumentParser(
        description='Generate German audio samples using Piper TTS',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Generate all sample sentences
  python3 generate_german_audio.py
  
  # Generate in custom directory
  python3 generate_german_audio.py -d my_samples
  
  # Generate single custom sentence
  python3 generate_german_audio.py -t "Wie geht es dir?" -o custom.wav -p custom.pcm
  
  # List available voices
  python3 generate_german_audio.py -l
  
  # Show sample sentences
  python3 generate_german_audio.py -s
        '''
    )
    
    parser.add_argument('-d', '--dir', default='german_samples',
                       help='Output directory for sample files (default: german_samples)')
    parser.add_argument('-t', '--text', 
                       help='Single text to generate (single mode)')
    parser.add_argument('-o', '--output', 
                       help='Output WAV file (single mode)')
    parser.add_argument('-p', '--pcm',
                       help='Output PCM file (single mode)')
    parser.add_argument('-l', '--list', action='store_true',
                       help='List available Piper voices')
    parser.add_argument('-s', '--show-samples', action='store_true',
                       help='Show available sample sentences')
    parser.add_argument('-v', '--voice', 
                       default='/opt/pyenvs/piper/voices/de_DE-thorsten-low.onnx',
                       help='Piper voice model to use')
    
    args = parser.parse_args()
    
    # List voices
    if args.list:
        print("Available Piper voices:")
        list_piper_voices()
        return 0
    
    # Show sample sentences
    if args.show_samples:
        print("Available German sample sentences:")
        print("-" * 60)
        for i, text in enumerate(SAMPLE_SENTENCES, 1):
            print(f"{i:2d}. {text}")
        print(f"\nTotal: {len(SAMPLE_SENTENCES)} sentences")
        return 0
    
    # Single text generation
    if args.text:
        if not args.output:
            print("Error: -o/--output required for single text mode")
            return 1
        
        return 0 if generate_single_sample(args.text, args.output, args.pcm) else 1
    
    # Generate all sample sentences
    return 0 if generate_sample_sentences(args.dir) else 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(130)