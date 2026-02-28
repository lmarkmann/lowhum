"""Audio playback engine — sounddevice streaming with device selection."""

from __future__ import annotations

import contextlib
import struct
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import sounddevice as sd

# WAV header parsing (avoids loading the full file into memory)


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
                _audio_fmt, channels, sample_rate = struct.unpack(
                    "<HHI", fmt[:8]
                )
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


def list_output_devices() -> list[tuple[int, str]]:
    """Return ``[(index, name), ...]`` for every output-capable device."""
    devices = sd.query_devices()
    return [
        (i, d["name"])
        for i, d in enumerate(devices)
        if d["max_output_channels"] > 0
    ]


def get_default_output_device() -> int:
    """Index of the current default output device."""
    return sd.default.device[1]  # type: ignore[index]


class AudioPlayer:
    """Streams a WAV file through sounddevice with device selection."""

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._stream: sd.OutputStream | None = None
        self._playing = False
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._pos = 0
        self._paused_pos: int | None = None
        self._file_path: Path | None = None
        self._device: int | None = None
        self._loop = True
        self._volume: float = 1.0

    @property
    def playing(self) -> bool:
        return self._playing

    @property
    def paused(self) -> bool:
        return not self._playing and self._paused_pos is not None

    @property
    def volume(self) -> float:
        return self._volume

    @volume.setter
    def volume(self, v: float) -> None:
        self._volume = max(0.0, min(1.0, v))

    def play(
        self,
        file_path: Path,
        device: int | None = None,
        loop: bool = True,
    ) -> None:
        """Start streaming file_path from the beginning (non-blocking)."""
        self.stop()
        self._file_path = file_path
        self._device = device
        self._loop = loop
        self._pos = 0
        self._paused_pos = None
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def pause(self) -> None:
        """Freeze playback at the current position."""
        self._stop_event.set()
        with self._lock:
            if self._stream is not None:
                with contextlib.suppress(Exception):
                    self._stream.abort()
                self._stream = None
            self._paused_pos = self._pos
            self._playing = False
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def resume(self) -> None:
        """Continue from the paused position."""
        if self._paused_pos is None or self._file_path is None:
            return
        start = self._paused_pos
        self._paused_pos = None
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, args=(start,), daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop playback and reset to the beginning."""
        self._stop_event.set()
        with self._lock:
            if self._stream is not None:
                with contextlib.suppress(Exception):
                    self._stream.abort()
                self._stream = None
            self._playing = False
        self._paused_pos = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def _run(self, start_pos: int = 0) -> None:
        file_path = self._file_path
        device = self._device
        loop = self._loop

        info = parse_wav_header(file_path)
        n_frames = info.data_size // (info.channels * info.bits_per_sample // 8)

        if info.channels == 1:
            data = np.memmap(
                file_path,
                dtype=np.int16,
                mode="r",
                offset=info.data_offset,
                shape=(n_frames,),
            )
        else:
            data = np.memmap(
                file_path,
                dtype=np.int16,
                mode="r",
                offset=info.data_offset,
                shape=(n_frames, info.channels),
            )

        pos = [start_pos]
        stop_evt = self._stop_event
        mono = info.channels == 1

        def _callback(
            outdata: np.ndarray,
            frames: int,
            _time: object,
            _status: sd.CallbackFlags,
        ) -> None:
            current = pos[0]
            end = current + frames
            should_stop = False

            if mono:
                if end <= n_frames:
                    outdata[:, 0] = data[current:end]
                    pos[0] = end
                elif loop:
                    first = n_frames - current
                    outdata[:first, 0] = data[current:]
                    remaining = frames - first
                    outdata[first:, 0] = data[:remaining]
                    pos[0] = remaining
                else:
                    first = n_frames - current
                    outdata[:first, 0] = data[current:]
                    outdata[first:] = 0
                    should_stop = True
            else:
                if end <= n_frames:
                    outdata[:] = data[current:end]
                    pos[0] = end
                elif loop:
                    first = n_frames - current
                    outdata[:first] = data[current:]
                    remaining = frames - first
                    outdata[first:] = data[:remaining]
                    pos[0] = remaining
                else:
                    first = n_frames - current
                    outdata[:first] = data[current:]
                    outdata[first:] = 0
                    should_stop = True

            vol = self._volume
            if vol != 1.0:
                outdata[:] = (outdata.astype(np.float32) * vol).astype(np.int16)

            self._pos = pos[0]
            if stop_evt.is_set():
                raise sd.CallbackAbort
            if should_stop:
                raise sd.CallbackStop

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
