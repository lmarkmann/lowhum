"""Icon generation — creates a filled template icon for the macOS menu bar."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

_SOURCE_ICON_DARK = Path(__file__).parent / "menubar_dark.png"
_SOURCE_ICON_LIGHT = Path(__file__).parent / "menubar_light.png"
_DATA_DIR = Path.home() / ".lowhum"
_TEMPLATE_ICON = _DATA_DIR / "icon_template.png"

# Menu bar icon: 22 pt = 44 px @2x retina
_ICON_SIZE = 44


def ensure_template_icon() -> Path:
    """Return path to a filled template icon, creating it if needed.

    Loads the bundled buffalo artwork, thresholds every non-transparent
    pixel to solid black, resizes to 44x44, and saves.  macOS renders
    template icons automatically in dark/light mode.
    """
    if _TEMPLATE_ICON.exists():
        return _TEMPLATE_ICON

    _DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Try to load dark mode icon first, fall back to light mode
    if _SOURCE_ICON_DARK.exists():
        img = Image.open(_SOURCE_ICON_DARK).convert("RGBA")
    elif _SOURCE_ICON_LIGHT.exists():
        img = Image.open(_SOURCE_ICON_LIGHT).convert("RGBA")
    else:
        raise FileNotFoundError(f"Neither {_SOURCE_ICON_DARK} nor {_SOURCE_ICON_LIGHT} found")
    img = img.resize((_ICON_SIZE, _ICON_SIZE), Image.LANCZOS)  # type: ignore

    pixels = np.array(img)

    # Threshold: any pixel with alpha > 30 → solid black; else transparent
    mask = pixels[:, :, 3] > 30
    pixels[mask] = [0, 0, 0, 255]
    pixels[~mask] = [0, 0, 0, 0]

    Image.fromarray(pixels).save(_TEMPLATE_ICON)
    return _TEMPLATE_ICON
