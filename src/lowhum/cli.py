"""CLI entry point for LowHum — ``lhm`` and ``lowhum`` resolve here."""

from __future__ import annotations

import signal
import sys

import typer

app = typer.Typer(
    name="lowhum",
    help="LowHum — deep brown noise for focus.",
    invoke_without_command=True,
    no_args_is_help=False,
)


@app.callback(invoke_without_command=True)
def _default(ctx: typer.Context) -> None:
    """Launch the menu-bar app (default when no subcommand given)."""
    if ctx.invoked_subcommand is not None:
        return

    from .app import LowHumApp
    from .generator import ensure_audio

    ensure_audio()
    LowHumApp().run()


@app.command()
def start(
    device: int | None = typer.Option(
        None, "--device", "-d", help="Output device index (see `lhm devices`)."
    ),
) -> None:
    """Play brown noise immediately in the terminal (Ctrl+C to stop)."""
    from .audio import AudioPlayer
    from .generator import AUDIO_FILE, ensure_audio

    ensure_audio()

    player = AudioPlayer()

    def _sigint(_sig: int, _frame: object) -> None:
        player.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _sigint)

    typer.echo("Playing brown noise … (Ctrl+C to stop)")
    player.play_blocking(AUDIO_FILE, device=device, loop=True)


@app.command()
def devices() -> None:
    """List available audio output devices."""
    from .audio import get_default_output_device, list_output_devices

    default_idx = get_default_output_device()
    for idx, name in list_output_devices():
        marker = " (default)" if idx == default_idx else ""
        typer.echo(f"  [{idx}] {name}{marker}")


@app.command()
def generate() -> None:
    """Pre-generate the brown noise audio file."""
    from .generator import AUDIO_FILE, generate_brown_noise

    if AUDIO_FILE.exists():
        typer.echo(f"Audio file already exists at {AUDIO_FILE}")
        if not typer.confirm("Regenerate?"):
            raise typer.Abort()

    generate_brown_noise()
    typer.echo(f"Saved to {AUDIO_FILE}")
