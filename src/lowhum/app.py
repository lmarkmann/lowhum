"""LowHum — macOS menu-bar application for brown noise playback."""

from __future__ import annotations

import shutil
import sys
import threading
from pathlib import Path

import rumps
import sounddevice as sd
import tomllib

from .audio import AudioPlayer, list_output_devices
from .generator import (
    DATA_DIR,
    NoiseColor,
    audio_file,
    generate_noise,
)
from .icons import ensure_template_icon

_APP_ICON = Path(__file__).parent / "icon.png"
_CONFIG_FILE = DATA_DIR / "config.toml"
_LAUNCH_AGENTS = Path.home() / "Library" / "LaunchAgents"
_PLIST = _LAUNCH_AGENTS / "com.lowhum.app.plist"

_PLIST_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.lowhum.app</string>
  <key>ProgramArguments</key>
  <array>
    <string>{binary}</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
</dict>
</plist>
"""


def _find_binary() -> str:
    for name in ("lhm", "lowhum"):
        found = shutil.which(name)
        if found:
            return found
    return sys.argv[0]


def _load_config() -> dict:
    if not _CONFIG_FILE.exists():
        return {}
    try:
        with open(_CONFIG_FILE, "rb") as f:
            data = tomllib.load(f)
        return data.get("audio", {})
    except Exception:
        return {}


def _save_config(
    device: int | None,
    color: NoiseColor,
    volume: float,
) -> None:
    _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = ["[audio]\n"]
    if device is not None:
        lines.append(f"device = {device}\n")
    lines.append(f'noise_color = "{color.value}"\n')
    lines.append(f"volume = {volume:.2f}\n")
    _CONFIG_FILE.write_text("".join(lines))


def _login_item_active() -> bool:
    return _PLIST.exists()


def _set_login_item(enabled: bool) -> None:
    if enabled:
        _LAUNCH_AGENTS.mkdir(parents=True, exist_ok=True)
        _PLIST.write_text(_PLIST_TEMPLATE.format(binary=_find_binary()))
    else:
        _PLIST.unlink(missing_ok=True)


def _set_dock_icon() -> None:
    if not _APP_ICON.exists():
        return
    try:
        from AppKit import (  # type: ignore[import-untyped]
            NSApplication,
            NSImage,
        )

        ns_image = NSImage.alloc().initByReferencingFile_(str(_APP_ICON))
        NSApplication.sharedApplication().setApplicationIconImage_(ns_image)
    except ImportError:
        pass


class LowHumApp(rumps.App):
    """Menu-bar app: play / pause / stop / noise color / volume / device."""

    def __init__(self) -> None:
        icon_path = str(ensure_template_icon())
        super().__init__(  # type: ignore
            "LowHum", icon=icon_path, template=True, quit_button=None
        )
        _set_dock_icon()

        self._player = AudioPlayer()
        self._known_device_names: set[str] = set()

        # Load persisted config
        cfg = _load_config()
        raw_device = cfg.get("device")
        self._selected_device: int | None = (
            int(raw_device) if raw_device is not None else None
        )
        try:
            self._noise_color = NoiseColor(cfg.get("noise_color", "brown"))
        except ValueError:
            self._noise_color = NoiseColor.BROWN
        self._volume: float = float(cfg.get("volume", 1.0))
        self._player.volume = self._volume

        # Build static menu items
        self._play_pause_item = rumps.MenuItem(
            "Play", callback=self._on_play_pause
        )
        self._stop_item = rumps.MenuItem("Stop", callback=self._on_stop)
        self._volume_menu = rumps.MenuItem(self._volume_label())
        self._color_menu = rumps.MenuItem("Noise Color")
        self._device_menu = rumps.MenuItem("Output Device")
        self._login_item = rumps.MenuItem(
            "Launch at Login", callback=self._on_toggle_login
        )

        self.menu = [
            self._play_pause_item,
            self._stop_item,
            None,
            self._volume_menu,
            None,
            self._color_menu,
            None,
            self._device_menu,
            None,
            self._login_item,
            None,
            rumps.MenuItem("Quit", callback=self._on_quit),
        ]

        self._volume_menu["Louder (+10%)"] = rumps.MenuItem(
            "Louder (+10%)", callback=self._on_volume_up
        )
        self._volume_menu["Quieter (-10%)"] = rumps.MenuItem(
            "Quieter (-10%)", callback=self._on_volume_down
        )

        self._refresh_color_menu()
        self._refresh_devices()
        self._login_item.state = _login_item_active()

        self._device_timer = rumps.Timer(self._check_devices, 2)
        self._device_timer.start()

    # Volume

    def _volume_label(self) -> str:
        return f"Volume ({int(self._volume * 100)}%)"

    def _on_volume_up(self, _: rumps.MenuItem) -> None:
        self._set_volume(self._volume + 0.1)

    def _on_volume_down(self, _: rumps.MenuItem) -> None:
        self._set_volume(self._volume - 0.1)

    def _set_volume(self, v: float) -> None:
        self._volume = max(0.0, min(1.0, round(v, 1)))
        self._player.volume = self._volume
        self._volume_menu.title = self._volume_label()
        self._persist()

    # Noise color

    def _refresh_color_menu(self) -> None:
        for key in list(self._color_menu.keys()):
            del self._color_menu[key]
        for color in NoiseColor:
            item = rumps.MenuItem(
                color.value.capitalize(),
                callback=lambda _, c=color: self._select_color(c),
            )
            item.state = color == self._noise_color
            self._color_menu[color.value] = item

    def _select_color(self, color: NoiseColor) -> None:
        was_playing = self._player.playing
        if was_playing:
            self._player.stop()
            self._play_pause_item.title = "Play"
        self._noise_color = color
        self._refresh_color_menu()
        self._persist()

        path = audio_file(color)
        if not path.exists():
            rumps.notification("LowHum", "", f"Generating {color.value} noise…")
            threading.Thread(
                target=self._generate_and_resume,
                args=(color, was_playing),
                daemon=True,
            ).start()
        elif was_playing:
            self._player.play(path, device=self._selected_device, loop=True)
            self._play_pause_item.title = "Pause"

    def _generate_and_resume(self, color: NoiseColor, resume: bool) -> None:
        generate_noise(color)
        if self._noise_color == color and resume:
            self._player.play(
                audio_file(color), device=self._selected_device, loop=True
            )
            self._play_pause_item.title = "Pause"

    # Device management

    def _refresh_devices(self) -> None:
        devices = list_output_devices()
        self._known_device_names = {name for _, name in devices}

        for key in list(self._device_menu.keys()):
            del self._device_menu[key]

        sys_item = rumps.MenuItem(
            "System Default",
            callback=lambda _: self._select_device(None),
        )
        sys_item.state = self._selected_device is None
        self._device_menu["System Default"] = sys_item

        for idx, name in devices:
            item = rumps.MenuItem(
                name,
                callback=lambda _, d=idx: self._select_device(d),
            )
            item.state = self._selected_device == idx
            self._device_menu[name] = item

    def _select_device(self, device_id: int | None) -> None:
        was_playing = self._player.playing
        self._player.stop()
        self._play_pause_item.title = "Play"

        self._selected_device = device_id
        self._persist()
        self._refresh_devices()

        if was_playing:
            self._player.play(
                audio_file(self._noise_color),
                device=self._selected_device,
                loop=True,
            )
            self._play_pause_item.title = "Pause"

    def _check_devices(self, _: rumps.Timer) -> None:
        try:
            current = {name for _, name in list_output_devices()}
        except sd.PortAudioError:
            return

        if current != self._known_device_names:
            if self._player.playing or self._player.paused:
                self._player.stop()
                self._play_pause_item.title = "Play"
                rumps.notification(
                    "LowHum", "", "Audio stopped — output device changed."
                )
            self._refresh_devices()

    # Login item

    def _on_toggle_login(self, _: rumps.MenuItem) -> None:
        enabled = not _login_item_active()
        _set_login_item(enabled)
        self._login_item.state = enabled

    # Menu callbacks

    def _on_play_pause(self, _: rumps.MenuItem) -> None:
        if self._player.playing:
            self._player.pause()
            self._play_pause_item.title = "Resume"
        elif self._player.paused:
            self._player.resume()
            self._play_pause_item.title = "Pause"
        else:
            path = audio_file(self._noise_color)
            if not path.exists():
                rumps.notification(
                    "LowHum", "", f"Generating {self._noise_color.value} noise…"
                )
                threading.Thread(
                    target=self._generate_and_resume,
                    args=(self._noise_color, True),
                    daemon=True,
                ).start()
            else:
                self._player.play(path, device=self._selected_device, loop=True)
                self._play_pause_item.title = "Pause"

    def _on_stop(self, _: rumps.MenuItem) -> None:
        self._player.stop()
        self._play_pause_item.title = "Play"

    def _on_quit(self, _: rumps.MenuItem) -> None:
        self._player.stop()
        rumps.quit_application()

    def _persist(self) -> None:
        _save_config(self._selected_device, self._noise_color, self._volume)
