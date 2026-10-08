"""Decode a recorded audio file (mp3, wav, flac, ogg) to what the recognizer wants: mono 16 kHz 16-bit PCM bytes.

Uses `miniaudio` (pure wheel, no ffmpeg): pip install miniaudio (in the Lumo venv)
"""
import miniaudio


def load_pcm16k(path):
    d = miniaudio.decode_file(str(path), output_format=miniaudio.SampleFormat.SIGNED16, nchannels=1, sample_rate=16000)
    return d.samples.tobytes()
