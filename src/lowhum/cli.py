"""CLI entry point for LowHum — ``lhm`` and ``lowhum`` resolve here."""

from __future__ import annotations

import importlib.metadata
import os
import subprocess
import sys

import typer

_DETACHED_ENV = "_LHM_DETACHED"

app = typer.Typer(
    name="lowhum",
    help="LowHum — deep brown noise for focus.",
    invoke_without_command=True,
    no_args_is_help=False,
)


_BISON = r"""
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
"""


def _banner() -> None:
    version = importlib.metadata.version("lowhum")
    typer.echo(_BISON)
    typer.echo(f"  ∿  LowHum  {version}  —  deep brown noise for focus\n")


@app.callback(invoke_without_command=True)
def _default(ctx: typer.Context) -> None:
    """Launch the menu-bar app (default when no subcommand given)."""
    if ctx.invoked_subcommand is not None:
        return

    # Already running as the detached background process — just launch the app.
    if os.environ.get(_DETACHED_ENV):
        from .app import LowHumApp
        from .generator import ensure_audio

        ensure_audio()
        LowHumApp().run()
        return

    _banner()
    typer.echo("  Starting in background …\n")

    env = {**os.environ, _DETACHED_ENV: "1"}
    subprocess.Popen(
        [sys.argv[0]],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    raise SystemExit(0)


@app.command()
def devices() -> None:
    """List available audio output devices."""
    from .audio import get_default_output_device, list_output_devices

    _banner()
    default_idx = get_default_output_device()
    for idx, name in list_output_devices():
        marker = "  ← default" if idx == default_idx else ""
        typer.echo(f"  [{idx}]  {name}{marker}")


@app.command()
def generate() -> None:
    """Pre-generate the brown noise audio file."""
    from .generator import AUDIO_FILE, generate_brown_noise

    _banner()
    if AUDIO_FILE.exists():
        typer.echo(f"  Audio file already exists at {AUDIO_FILE}")
        if not typer.confirm("  Regenerate?"):
            raise typer.Abort()

    generate_brown_noise()
    typer.echo(f"  Saved to {AUDIO_FILE}")
