"""Noise and binaural beat generator — cached WAV files for playback."""

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


def _crossfade(chunks: list[np.ndarray]) -> np.ndarray:
    """Overlap-add crossfade across chunk boundaries (1 s)."""
    if len(chunks) == 1:
        return chunks[0]
    xfade = SAMPLE_RATE
    fade_out = np.linspace(1, 0, xfade)
    fade_in = np.linspace(0, 1, xfade)
    if chunks[0].ndim == 2:
        fade_out = fade_out[:, np.newaxis]
        fade_in = fade_in[:, np.newaxis]
    parts: list[np.ndarray] = [chunks[0][:-xfade]]
    for i in range(1, len(chunks)):
        blend = chunks[i - 1][-xfade:] * fade_out + chunks[i][:xfade] * fade_in
        parts.append(blend)
        last = i == len(chunks) - 1
        tail = chunks[i][xfade:] if last else chunks[i][xfade:-xfade]
        parts.append(tail)
    return np.concatenate(parts)


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

    final = _crossfade(chunks)[: duration * SAMPLE_RATE]
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


class BrainwaveBand(str, Enum):
    """Target brainwave entrainment bands for binaural beats."""

    THETA = "theta"  # 6 Hz — deep relaxation, meditation
    ALPHA = "alpha"  # 10 Hz — calm focus, light relaxation
    BETA = "beta"  # 18 Hz — active thinking, concentration
    GAMMA = "gamma"  # 40 Hz — high-level cognition

    @property
    def beat_freq(self) -> float:
        return _BAND_FREQS[self]


_BAND_FREQS: dict[BrainwaveBand, float] = {
    BrainwaveBand.THETA: 6.0,
    BrainwaveBand.ALPHA: 10.0,
    BrainwaveBand.BETA: 18.0,
    BrainwaveBand.GAMMA: 40.0,
}

CARRIER_HZ = 200.0  # good perceived beat strength


def binaural_audio_file(
    band: BrainwaveBand,
    noise: NoiseColor = NoiseColor.BROWN,
) -> Path:
    return DATA_DIR / f"binaural_{band.value}_{noise.value}.wav"


def generate_binaural(
    band: BrainwaveBand = BrainwaveBand.ALPHA,
    noise: NoiseColor = NoiseColor.BROWN,
    output_path: Path | None = None,
    duration: int = DURATION,
    beat_volume: float = 0.15,
) -> Path:
    """Generate stereo binaural beats layered under noise.

    Left ear hears carrier_hz, right ear hears carrier_hz + beat_freq.
    The perceptual difference produces the binaural beat. Noise is
    identical in both channels so the beat stands out without the
    raw sine being harsh on its own.

    beat_volume controls the sine amplitude relative to the noise
    (0.15 = subtle undertone, which is the sweet spot for focus).
    """
    if output_path is None:
        output_path = binaural_audio_file(band, noise)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    beat_freq = band.beat_freq
    left_hz = CARRIER_HZ
    right_hz = CARRIER_HZ + beat_freq

    chunk_seconds = 300  # 5-min chunks, same as noise gen
    chunk_samples = SAMPLE_RATE * chunk_seconds
    n_chunks = max(1, math.ceil(duration * SAMPLE_RATE / chunk_samples))

    # Filters for the noise bed (same as generate_noise)
    sub_sos = butter(1, 20, btype="high", fs=SAMPLE_RATE, output="sos")
    if noise == NoiseColor.BROWN:
        hp_sos = butter(2, 1.0, btype="high", fs=SAMPLE_RATE, output="sos")
        lp_sos = butter(2, 500, btype="low", fs=SAMPLE_RATE, output="sos")

    # Each chunk is (n, 2) — left and right channels
    chunks: list[np.ndarray] = []
    sample_offset = 0

    for _ in range(n_chunks):
        # Noise bed (mono, duplicated to both channels)
        bed = _raw_noise(noise, chunk_samples)
        if noise == NoiseColor.BROWN:
            bed = sosfilt(hp_sos, bed)
            bed = sosfilt(lp_sos, bed)
        bed = sosfilt(sub_sos, bed)
        rms = np.sqrt(np.mean(bed**2))
        bed *= 0.3 / rms

        # Binaural tones — continuous phase across chunks
        t = (np.arange(chunk_samples) + sample_offset) / SAMPLE_RATE
        left_tone = np.sin(2 * np.pi * left_hz * t) * beat_volume
        right_tone = np.sin(2 * np.pi * right_hz * t) * beat_volume
        sample_offset += chunk_samples

        stereo = np.column_stack(
            [
                bed + left_tone,
                bed + right_tone,
            ]
        )

        # Per-channel RMS normalize to 0.3
        for ch in range(2):
            ch_rms = np.sqrt(np.mean(stereo[:, ch] ** 2))
            if ch_rms > 0:
                stereo[:, ch] *= 0.3 / ch_rms

        stereo = np.clip(stereo, -1.0, 1.0)
        chunks.append(stereo)

    final = _crossfade(chunks)[: duration * SAMPLE_RATE]
    audio_data = (final * 32_767).astype(np.int16)
    wav_write(str(output_path), SAMPLE_RATE, audio_data)
    return output_path


def ensure_binaural(
    band: BrainwaveBand = BrainwaveBand.ALPHA,
    noise: NoiseColor = NoiseColor.BROWN,
) -> Path:
    """Return path to the binaural audio file, generating if needed."""
    path = binaural_audio_file(band, noise)
    if path.exists():
        return path
    print(
        f"Generating {band.value} binaural beat over {noise.value} noise"
        f" (first run — takes ~5 s) …"
    )
    return generate_binaural(band, noise)
