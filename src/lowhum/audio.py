"""Audio playback engine — sounddevice streaming with device selection."""

from __future__ import annotations

import contextlib
import struct
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import sounddevice as sd

# ---------------------------------------------------------------------------
# WAV header parsing (avoids loading the full file into memory)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WavInfo:
    sample_rate: int
    channels: int
    bits_per_sample: int
    data_offset: int
    data_size: int


def parse_wav_header(file_path: Path) -> WavInfo:
    """Parse a RIFF/WAV header and return metadata + data offset."""
    with open(file_path, "rb") as f:
        if f.read(4) != b"RIFF":
            raise ValueError("Not a RIFF file")
        f.read(4)  # file size
        if f.read(4) != b"WAVE":
            raise ValueError("Not a WAVE file")

        sample_rate = channels = bits_per_sample = 0
        data_offset = data_size = 0

        while True:
            chunk_id = f.read(4)
            if len(chunk_id) < 4:
                break
            (chunk_size,) = struct.unpack("<I", f.read(4))

            if chunk_id == b"fmt ":
                fmt = f.read(min(chunk_size, 16))
                _audio_fmt, channels, sample_rate = struct.unpack("<HHI", fmt[:8])
                bits_per_sample = struct.unpack("<H", fmt[14:16])[0]
                remaining = chunk_size - 16
                if remaining > 0:
                    f.read(remaining)
            elif chunk_id == b"data":
                data_offset = f.tell()
                data_size = chunk_size
                break
            else:
                f.seek(chunk_size, 1)

    return WavInfo(
        sample_rate=sample_rate,
        channels=channels,
        bits_per_sample=bits_per_sample,
        data_offset=data_offset,
        data_size=data_size,
    )


# ---------------------------------------------------------------------------
# Device helpers
# ---------------------------------------------------------------------------


def list_output_devices() -> list[tuple[int, str]]:
    """Return ``[(index, name), ...]`` for every output-capable device."""
    devices = sd.query_devices()
    return [(i, d["name"]) for i, d in enumerate(devices) if d["max_output_channels"] > 0]


def get_default_output_device() -> int:
    """Index of the current default output device."""
    return sd.default.device[1]  # type: ignore[index]


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------


class AudioPlayer:
    """Streams a WAV file through sounddevice with device selection."""

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._stream: sd.OutputStream | None = None
        self._playing = False
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    @property
    def playing(self) -> bool:
        return self._playing

    # -- public API ---------------------------------------------------------

    def play(
        self,
        file_path: Path,
        device: int | None = None,
        loop: bool = True,
    ) -> None:
        """Start streaming *file_path* (non-blocking)."""
        self.stop()
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(file_path, device, loop),
            daemon=True,
        )
        self._thread.start()

    def play_blocking(
        self,
        file_path: Path,
        device: int | None = None,
        loop: bool = True,
    ) -> None:
        """Play audio, blocking until stopped or file ends."""
        self._stop_event.clear()
        self._run(file_path, device, loop)

    def stop(self) -> None:
        """Stop playback immediately."""
        self._stop_event.set()
        with self._lock:
            if self._stream is not None:
                with contextlib.suppress(Exception):
                    self._stream.abort()
                self._stream = None
            self._playing = False
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    # -- internals ----------------------------------------------------------

    def _run(
        self,
        file_path: Path,
        device: int | None,
        loop: bool,
    ) -> None:
        info = parse_wav_header(file_path)
        n_samples = info.data_size // (info.bits_per_sample // 8)

        data = np.memmap(
            file_path,
            dtype=np.int16,
            mode="r",
            offset=info.data_offset,
            shape=(n_samples,),
        )

        pos = [0]  # mutable for callback closure
        stop_evt = self._stop_event

        def _callback(
            outdata: np.ndarray,
            frames: int,
            _time: object,
            _status: sd.CallbackFlags,
        ) -> None:
            current = pos[0]
            end = current + frames

            if end <= n_samples:
                outdata[:, 0] = data[current:end]
                pos[0] = end
            elif loop:
                first = n_samples - current
                outdata[:first, 0] = data[current:]
                remaining = frames - first
                outdata[first:, 0] = data[:remaining]
                pos[0] = remaining
            else:
                first = n_samples - current
                outdata[:first, 0] = data[current:]
                outdata[first:] = 0
                raise sd.CallbackStop

            if stop_evt.is_set():
                raise sd.CallbackAbort

        try:
            stream = sd.OutputStream(
                samplerate=info.sample_rate,
                channels=info.channels,
                dtype="int16",
                device=device,
                blocksize=2048,
                callback=_callback,
            )
            with self._lock:
                self._stream = stream
                self._playing = True

            stream.start()
            while stream.active and not stop_evt.is_set():
                sd.sleep(100)
        except sd.PortAudioError as exc:
            print(f"Audio error: {exc}")
        finally:
            with self._lock:
                if self._stream is not None:
                    try:
                        self._stream.stop()
                        self._stream.close()
                    except Exception:
                        pass
                    self._stream = None
                self._playing = False
