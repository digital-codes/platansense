#!/usr/bin/env python3
"""
Record 5 seconds from microphone, ensure 8 kHz / 16-bit mono,
save as raw + wav, then play from buffer.

Requirements:
    pip install sounddevice numpy
"""

import numpy as np
import sounddevice as sd
import wave

TARGET_SR = 8000       # Hz
DURATION = 5.0         # seconds
CHANNELS = 1
RAW_FILENAME = "recording.raw"
WAV_FILENAME = "recording.wav"


def resample_to_8k(audio: np.ndarray, orig_sr: int) -> np.ndarray:
    """
    Resample mono audio to 8 kHz using numpy only (linear interpolation).
    audio: shape (n_samples,) or (n_samples, 1), float32 in [-1, 1]
    returns: shape (n_new_samples,), float32
    """
    if audio.ndim == 2 and audio.shape[1] == 1:
        audio = audio[:, 0]

    if orig_sr == TARGET_SR:
        return audio

    n_orig = audio.shape[0]
    n_new = int(round(n_orig * TARGET_SR / orig_sr))

    # original and new sample positions
    orig_x = np.linspace(0.0, 1.0, num=n_orig, endpoint=False)
    new_x = np.linspace(0.0, 1.0, num=n_new, endpoint=False)

    audio_8k = np.interp(new_x, orig_x, audio).astype(np.float32)
    return audio_8k


def float_to_int16(audio_f32: np.ndarray) -> np.ndarray:
    """
    Convert float32 [-1, 1] to int16 with clipping.
    """
    audio_f32 = np.clip(audio_f32, -1.0, 1.0)
    audio_i16 = (audio_f32 * 32767.0).astype(np.int16)
    return audio_i16


def record_audio() -> tuple[np.ndarray, int]:
    """
    Try to record directly at 8 kHz; if unsupported, record at default
    input samplerate and return (audio_float32, actual_samplerate).
    """
    try:
        # Check if 8 kHz is supported
        sd.check_input_settings(samplerate=TARGET_SR, channels=CHANNELS)
        samplerate = TARGET_SR
    except Exception:
        # Fallback to default input samplerate
        default_dev = sd.query_devices(kind='input')
        samplerate = int(default_dev['default_samplerate'])

    print(f"Recording at {samplerate} Hz for {DURATION} seconds...")
    n_frames = int(DURATION * samplerate)

    recording = sd.rec(
        frames=n_frames,
        samplerate=samplerate,
        channels=CHANNELS,
        dtype='float32'
    )
    sd.wait()  # block until recording is finished
    return recording, samplerate


def save_raw(audio_i16: np.ndarray, filename: str) -> None:
    """
    Save int16 mono audio as headerless raw (little-endian).
    """
    # Ensure (n_samples,) shape
    if audio_i16.ndim == 2 and audio_i16.shape[1] == 1:
        audio_i16 = audio_i16[:, 0]

    # Ensure little-endian 16-bit
    audio_le = audio_i16.astype('<i2')
    with open(filename, "wb") as f:
        f.write(audio_le.tobytes())


def save_wav(audio_i16: np.ndarray, filename: str) -> None:
    """
    Save int16 mono audio as WAV with header.
    """
    # Ensure (n_samples,) shape
    if audio_i16.ndim == 2 and audio_i16.shape[1] == 1:
        audio_i16 = audio_i16[:, 0]

    with wave.open(filename, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)          # 16-bit = 2 bytes
        wf.setframerate(TARGET_SR)  # 8 kHz
        wf.writeframes(audio_i16.tobytes())


def play_from_buffer(audio_i16: np.ndarray) -> None:
    """
    Play audio from an in-memory buffer (int16) at 8 kHz.
    """
    # sounddevice can play int16 directly
    sd.play(audio_i16, samplerate=TARGET_SR)
    sd.wait()


def main():
    # 1. Record audio
    audio_f32, recorded_sr = record_audio()

    # 2. Resample if needed
    if recorded_sr != TARGET_SR:
        print(f"Resampling from {recorded_sr} Hz to {TARGET_SR} Hz...")
        audio_f32 = resample_to_8k(audio_f32, recorded_sr)

    # 3. Convert to int16
    audio_i16 = float_to_int16(audio_f32)

    # 4. Save as raw and wav
    print(f"Saving raw PCM to {RAW_FILENAME}")
    save_raw(audio_i16, RAW_FILENAME)

    print(f"Saving WAV to {WAV_FILENAME}")
    save_wav(audio_i16, WAV_FILENAME)

    # 5. Play from buffer
    print("Playing from buffer...")
    play_from_buffer(audio_i16)

    print("Done.")


if __name__ == "__main__":
    main()
