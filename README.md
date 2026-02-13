# LowHum

**Deep brown noise for focus, right from the macOS menu bar.**

No browser tabs. No subscriptions. No account. Fully offline.

<!-- TODO: Add GIF demo here -->

Brown noise is one of the most effective focus aids for people with ADHD and anyone who needs to block out distractions. Most options require keeping a YouTube tab open, paying for a subscription app, or relying on your phone. LowHum is a single-purpose menu bar app that generates deep brown noise locally and plays it on loop — install it, click play, forget about it.

## Install

```bash
uv tool install lowhum          # recommended
# or
pip install lowhum
```

## Usage

```bash
lowhum                          # launch the menu-bar app
lowhum start                    # play immediately in terminal (Ctrl+C to stop)
lowhum start -d 3               # play on a specific output device
lowhum devices                  # list output devices
lowhum generate                 # pre-generate the audio file
```

`lhm` is a shorthand alias — all commands work with either name.

### Menu-bar app

- Play / Stop from the menu bar
- **Output Device** submenu — pick any connected audio device
- Auto-stops when headphones connect or disconnect

## How it works

1. **Generation** — On first run, a 10-minute WAV is synthesised locally: cumulative-sum brown noise, Butterworth bandpass (1–500 Hz + 20 Hz sub-bass HP), RMS-normalised per chunk, crossfaded at boundaries. Stored at `~/.lowhum/`.
2. **Playback** — Memory-mapped streaming through PortAudio. No full-file RAM load. Loops seamlessly.
3. **Device detection** — Polls audio devices every 2 seconds. Headphone unplug, Bluetooth disconnect — playback stops instantly.
4. **Menu-bar icon** — Template icon; macOS handles dark/light mode automatically.

## Requirements

- macOS
- Python >= 3.12

## License

MIT
