# LowHum - Deep Brown Noise for Focus as a MenuBar App & CLI Tool

Generates a 1-hour deep brown noise file on first run (Butterworth-filtered, crossfaded chunks, 1–500 Hz band) and streams it through any output device via PortAudio.

## Install

```bash
uv tool install lowhum          # global CLI (recommended)
# or
pip install lowhum
```

## Usage

### Instant playback

```bash
lowhum start                    # play immediately (Ctrl+C to stop)
lowhum start -d 3               # play on a specific device
lhm start                       # shorthand alias
```

### Menu-bar app

```bash
lowhum                          # launch the macOS menu-bar app
```

Features:
- Play / Stop from the menu bar
- **Output Device** submenu — select any connected audio device
- Auto-stops when headphones connect or disconnect

### Other commands

```bash
lowhum devices                  # list output devices
lowhum generate                 # pre-generate the audio file
lowhum --help                   # full help
```

`lhm` is an alias for `lowhum` — all commands work with either name.

## How it works

1. **Generation** — On first run, a 1-hour WAV is synthesised from cumulative-sum brown noise, bandpass-filtered with Butterworth filters (1–500 Hz + 20 Hz sub-bass HP), RMS-normalised per chunk, and crossfaded at chunk boundaries. Stored at `~/.lowhum/deep_brown_noise_1hr.wav`.
2. **Playback** — The WAV is memory-mapped and streamed through `sounddevice` (PortAudio) in int16 with a callback-driven output stream. No full-file load into RAM.
3. **Device detection** — The menu-bar app polls `sounddevice.query_devices()` every 2 seconds. Any device change instantly stops playback (headphone unplug, Bluetooth disconnect, etc.).
4. **Menu-bar icon** — A template icon; macOS handles dark/light mode rendering automatically.

## Requirements

- macOS (uses `rumps` for the menu bar)
- Python ≥ 3.12
