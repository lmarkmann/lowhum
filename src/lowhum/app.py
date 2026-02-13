"""LowHum — macOS menu-bar application for brown noise playback."""

from __future__ import annotations

import rumps
import sounddevice as sd

from .audio import AudioPlayer, list_output_devices
from .generator import AUDIO_FILE
from .icons import ensure_template_icon


class LowHumApp(rumps.App):
    """Menu-bar app: play / stop / select output device."""

    def __init__(self) -> None:
        icon_path = str(ensure_template_icon())
        super().__init__("LowHum", icon=icon_path, template=True, quit_button=None)

        self._player = AudioPlayer()
        self._selected_device: int | None = None
        self._known_device_names: set[str] = set()

        # --- static menu items ---
        self._play_item = rumps.MenuItem("Play", callback=self._on_play)
        self._stop_item = rumps.MenuItem("Stop", callback=self._on_stop)
        self._device_menu = rumps.MenuItem("Output Device")

        self.menu = [
            self._play_item,
            self._stop_item,
            None,
            self._device_menu,
            None,
            rumps.MenuItem("Quit", callback=self._on_quit),
        ]

        self._refresh_devices()

        # Poll for audio-device changes every 2 s
        self._device_timer = rumps.Timer(self._check_devices, 2)
        self._device_timer.start()

    # Device management

    def _refresh_devices(self) -> None:
        devices = list_output_devices()
        self._known_device_names = {name for _, name in devices}

        # Clear submenu
        for key in list(self._device_menu.keys()):
            del self._device_menu[key]

        # "System Default" entry
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
        if was_playing:
            self._player.stop()

        self._selected_device = device_id
        self._refresh_devices()

        if was_playing:
            self._player.play(AUDIO_FILE, device=self._selected_device, loop=True)

    def _check_devices(self, _: rumps.Timer) -> None:
        """Detect connects / disconnects and stop playback immediately."""
        try:
            current = {name for _, name in list_output_devices()}
        except sd.PortAudioError:
            return

        if current != self._known_device_names:
            if self._player.playing:
                self._player.stop()
                rumps.notification("LowHum", "", "Audio stopped — output device changed.")
            self._refresh_devices()

    # Menu callbacks

    def _on_play(self, _: rumps.MenuItem) -> None:
        if self._player.playing:
            return
        self._player.play(AUDIO_FILE, device=self._selected_device, loop=True)

    def _on_stop(self, _: rumps.MenuItem) -> None:
        self._player.stop()

    def _on_quit(self, _: rumps.MenuItem) -> None:
        self._player.stop()
        rumps.quit_application()
