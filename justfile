version := `python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"`

build:
    uv run python setup.py py2app

archive: build
    cd dist && zip -r "LowHum-{{version}}-macOS-arm64.zip" LowHum.app

clean:
    rm -rf build/ dist/

sha256:
    shasum -a 256 dist/LowHum-{{version}}-macOS-arm64.zip
