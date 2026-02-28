"""Noise generator — brown, pink, and white; generates and caches WAV files."""

import math
from enum import Enum
from pathlib import Path

import numpy as np
from scipy.io.wavfile import write as wav_write
from scipy.signal import butter, sosfilt

SAMPLE_RATE = 44_100
DURATION = 600  # seconds (10 minutes)
DATA_DIR = Path.home() / ".lowhum"


class NoiseColor(str, Enum):
    BROWN = "brown"
    PINK = "pink"
    WHITE = "white"


def audio_file(color: NoiseColor) -> Path:
    return DATA_DIR / f"{color.value}_noise.wav"


def _raw_noise(color: NoiseColor, n: int) -> np.ndarray:
    white = np.random.randn(n)
    if color == NoiseColor.WHITE:
        return white
    elif color == NoiseColor.PINK:
        f = np.fft.rfftfreq(n)
        f[0] = 1.0  # avoid divide-by-zero at DC
        return np.fft.irfft(np.fft.rfft(white) / np.sqrt(f), n=n)
    else:  # BROWN
        return np.cumsum(white)


def generate_noise(
    color: NoiseColor = NoiseColor.BROWN,
    output_path: Path | None = None,
    duration: int = DURATION,
) -> Path:
    """Generate noise of the requested color and write as WAV.

    Brown: cumsum white noise, Butterworth bandpass (1-500 Hz) + HP 20 Hz.
    Pink: 1/f spectral shaping via FFT, HP 20 Hz.
    White: gaussian noise, HP 20 Hz.
    """
    if output_path is None:
        output_path = audio_file(color)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    chunk_samples = SAMPLE_RATE * 300  # process in 5-min chunks
    n_chunks = max(1, math.ceil(duration * SAMPLE_RATE / chunk_samples))

    sub_sos = butter(1, 20, btype="high", fs=SAMPLE_RATE, output="sos")
    if color == NoiseColor.BROWN:
        hp_sos = butter(2, 1.0, btype="high", fs=SAMPLE_RATE, output="sos")
        lp_sos = butter(2, 500, btype="low", fs=SAMPLE_RATE, output="sos")

    chunks: list[np.ndarray] = []
    for _ in range(n_chunks):
        chunk = _raw_noise(color, chunk_samples)
        if color == NoiseColor.BROWN:
            chunk = sosfilt(hp_sos, chunk)
            chunk = sosfilt(lp_sos, chunk)
        chunk = sosfilt(sub_sos, chunk)
        rms = np.sqrt(np.mean(chunk**2))
        chunk = chunk * (0.3 / rms)
        chunk = np.clip(chunk, -1.0, 1.0)
        chunks.append(chunk)

    # Crossfade between chunks (1 s) to eliminate boundary clicks
    xfade = SAMPLE_RATE
    for i in range(1, len(chunks)):
        fade_out = np.linspace(1, 0, xfade)
        fade_in = np.linspace(0, 1, xfade)
        chunks[i - 1][-xfade:] *= fade_out
        chunks[i][:xfade] *= fade_in
        chunks[i][:xfade] += chunks[i - 1][-xfade:]
        chunks[i - 1] = chunks[i - 1][:-xfade]

    final = np.concatenate(chunks)[: duration * SAMPLE_RATE]
    audio_data = (final * 32_767).astype(np.int16)
    wav_write(str(output_path), SAMPLE_RATE, audio_data)
    return output_path


def ensure_audio(color: NoiseColor = NoiseColor.BROWN) -> Path:
    """Return the path to the audio file for *color*, generating if needed."""
    path = audio_file(color)
    if path.exists():
        return path
    print(f"Generating {color.value} noise audio (first run — takes ~5 s) …")
    return generate_noise(color)
