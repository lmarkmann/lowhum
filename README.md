<div align="center">
<pre>
               _.-````'-,_
     _,.,_ ,-'           `'-.,_
   /)     (\                   '`-.
  ((      ) )                      `\
   \)    (_/                        )\
    |       /)           '    ,'    / \
    `\    ^'            '     (    /  ))
      |      _/\ ,     /    ,,`\   (  "`
       \Y,   |  \  \  | ``````| / \_ \
         `)_/    \  \  )    ( >  ( >
                  \( \(     |/   |/
                 /_(/_(    /_(  /_(
</pre>
</div>

# LowHum

[![PyPI](https://img.shields.io/pypi/v/lowhum)](https://pypi.org/project/lowhum/)
[![Python](https://img.shields.io/pypi/pyversions/lowhum)](https://pypi.org/project/lowhum/)
[![License](https://img.shields.io/github/license/lmarkmann/lowhum)](LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/lowhum)](https://pypi.org/project/lowhum/)

Deep brown noise for focus, right from the macOS menu bar. Requires macOS and Python 3.12+.

[**Listen to a 20s preview**](https://github.com/lmarkmann/lowhum/raw/main/assets/preview.mp3) — this is exactly what LowHum sounds like.

Brown noise is one of the most effective focus aids for people with ADHD and anyone who needs to block out distractions. Most options require keeping a YouTube tab open, paying for a subscription, or relying on your phone. LowHum is a single-purpose menu bar app that generates deep brown noise locally and plays it on loop. Install it, click play, forget about it.

## Install

**pip / uv** (requires Python 3.12+):

```bash
uv tool install -U lowhum
# or
pip install -U lowhum
```

**Standalone .app** — download `LowHum.app` from [the latest release](https://github.com/lmarkmann/lowhum/releases/latest). The app is not notarized, so macOS will block it on first launch. To allow it:

```bash
xattr -cr /Applications/LowHum.app
```

## Usage

```bash
lowhum                          # launch the menu-bar app (runs in background)
lowhum devices                  # list output devices
lowhum generate                 # pre-generate the audio file
```

`lhm` is a shorthand alias for all commands.

### Menu bar controls

- Play / Stop from the menu bar
- Pick any connected audio device from the Output Device submenu
- Binaural beats overlay (Theta, Alpha, Beta, Gamma)
- Noise color selection (brown, pink, white)
- Auto-stops when headphones connect or disconnect

## How it works

On first launch, a 10-minute WAV is synthesized locally for every noise color and binaural combination. Cumulative-sum brown noise through a Butterworth bandpass (1 to 500 Hz, 20 Hz sub-bass highpass), RMS-normalized per chunk, crossfaded at boundaries. Everything is stored in `~/.lowhum/`.

Playback streams through PortAudio via memory-mapped files, so the full WAV never sits in RAM. The app polls audio devices every 2 seconds and stops instantly if headphones disconnect or a Bluetooth device drops.

The menu bar icon is a template image, so macOS handles dark/light mode automatically.

## License

MIT
