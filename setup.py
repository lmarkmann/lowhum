"""py2app build configuration for LowHum.app.

Usage:
    uv run python setup.py py2app
"""

from setuptools import setup

# py2app 0.28 rejects install_requires, but setuptools auto-populates
# it from pyproject.toml [project].dependencies. Patch the check out.
import py2app.build_app as _build_app  # noqa: E402

_orig_finalize = _build_app.py2app.finalize_options


def _finalize_no_install_requires(self):
    self.distribution.install_requires = []
    _orig_finalize(self)


_build_app.py2app.finalize_options = _finalize_no_install_requires

APP = ["src/lowhum/cli.py"]

OPTIONS = {
    "argv_emulation": False,
    "plist": {
        "CFBundleName": "LowHum",
        "CFBundleIdentifier": "com.lowhum.app",
        "CFBundleVersion": "1.1.0",
        "CFBundleShortVersionString": "1.1.0",
        "LSUIElement": True,
    },
    "packages": [
        "lowhum",
        "numpy",
        "scipy",
        "sounddevice",
        "rumps",
        "typer",
        "PIL",
    ],
    "includes": ["_sounddevice_data"],
    "iconfile": "LowHum.icns",
}

setup(
    app=APP,
    name="LowHum",
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
