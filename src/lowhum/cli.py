"""CLI entry point for LowHum — ``lhm`` and ``lowhum`` resolve here."""

from __future__ import annotations

import importlib.metadata
import os
import subprocess
import sys

import typer

_DETACHED_ENV = "_LHM_DETACHED"


def _inside_app_bundle() -> bool:
    return ".app/Contents" in (sys.executable or "")


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

    # Inside .app bundle or already detached — launch directly.
    if _inside_app_bundle() or os.environ.get(_DETACHED_ENV):
        from .app import LowHumApp
        from .generator import ensure_all_audio

        ensure_all_audio()
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
def generate(
    color: str = typer.Option(
        "brown", "--color", "-c", help="brown, pink, or white"
    ),
    duration: int = typer.Option(
        600, "--duration", "-d", help="Duration in seconds"
    ),
) -> None:
    """Pre-generate a noise audio file."""
    from .generator import NoiseColor, audio_file, generate_noise

    try:
        noise_color = NoiseColor(color)
    except ValueError:
        typer.echo(f"  Unknown color '{color}'. Choose: brown, pink, white.")
        raise typer.Exit(1) from None

    _banner()
    path = audio_file(noise_color)
    if path.exists():
        typer.echo(f"  Audio file already exists at {path}")
        if not typer.confirm("  Regenerate?"):
            raise typer.Abort()

    generate_noise(noise_color, duration=duration)
    typer.echo(f"  Saved to {path}")


if __name__ == "__main__":
    app()
