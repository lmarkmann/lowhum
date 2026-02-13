"""Brown noise generator — generates audio on first use, caches to disk."""

from pathlib import Path

import numpy as np
from scipy.io.wavfile import write as wav_write
from scipy.signal import butter, sosfilt

SAMPLE_RATE = 44_100
DURATION = 3600  # seconds (1 hour)
DATA_DIR = Path.home() / ".lowhum"
AUDIO_FILE = DATA_DIR / "deep_brown_noise_1hr.wav"


def generate_brown_noise(output_path: Path | None = None) -> Path:
    """Generate 1 hour of deep brown noise and save as WAV.

    Uses cumulative-sum brown noise with Butterworth bandpass (1–500 Hz)
    and a sub-bass high-pass at 20 Hz. Chunks are crossfaded to avoid clicks.
    """
    if output_path is None:
        output_path = AUDIO_FILE

    output_path.parent.mkdir(parents=True, exist_ok=True)

    chunk_size = SAMPLE_RATE * 300  # 5-minute chunks
    n_chunks = DURATION * SAMPLE_RATE // chunk_size

    # Filter design (done once)
    hp_sos = butter(2, 1.0, btype="high", fs=SAMPLE_RATE, output="sos")
    lp_sos = butter(2, 500, btype="low", fs=SAMPLE_RATE, output="sos")
    sub_sos = butter(1, 20, btype="high", fs=SAMPLE_RATE, output="sos")

    chunks: list[np.ndarray] = []

    for _ in range(n_chunks):
        white = np.random.randn(chunk_size)
        brown = np.cumsum(white)

        brown = sosfilt(hp_sos, brown)
        brown = sosfilt(lp_sos, brown)
        brown = sosfilt(sub_sos, brown)

        # Per-chunk RMS normalisation keeps volume consistent
        rms = np.sqrt(np.mean(brown**2))
        brown = brown * (0.3 / rms)
        brown = np.clip(brown, -1.0, 1.0)

        chunks.append(brown)

    # Crossfade between chunks (1 s) to eliminate boundary clicks
    xfade = SAMPLE_RATE
    for i in range(1, len(chunks)):
        fade_out = np.linspace(1, 0, xfade)
        fade_in = np.linspace(0, 1, xfade)
        chunks[i - 1][-xfade:] *= fade_out
        chunks[i][:xfade] *= fade_in
        chunks[i][:xfade] += chunks[i - 1][-xfade:]
        chunks[i - 1] = chunks[i - 1][:-xfade]

    final = np.concatenate(chunks)
    audio_data = (final * 32_767).astype(np.int16)
    wav_write(str(output_path), SAMPLE_RATE, audio_data)

    return output_path


def ensure_audio() -> Path:
    """Return the path to the audio file, generating it on first call."""
    if AUDIO_FILE.exists():
        return AUDIO_FILE

    print("Generating brown noise audio (first run — takes ~30 s) …")
    return generate_brown_noise()
