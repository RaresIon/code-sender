"""stylegen: deterministic 2D 'What if' style video engine, driven by episode JSON."""
import os
import pathlib

__version__ = "0.1.0"

_PKG = pathlib.Path(__file__).resolve().parent
FONT_DIR = _PKG / "fonts"
EXAMPLES_DIR = _PKG / "examples"


def _pin_fonts():
    """Point fontconfig at the bundled Inter files ONLY, so renders are identical on
    every machine. Must run before cairo touches fontconfig. Opt out with
    STYLEGEN_SYSTEM_FONTS=1."""
    if os.environ.get("STYLEGEN_SYSTEM_FONTS") == "1":
        return
    cache = pathlib.Path(os.environ.get("XDG_CACHE_HOME", pathlib.Path.home() / ".cache"))
    cache = cache / "stylegen"
    cache.mkdir(parents=True, exist_ok=True)
    conf = cache / "fonts.conf"
    body = (
        '<?xml version="1.0"?>\n<!DOCTYPE fontconfig SYSTEM "fonts.dtd">\n<fontconfig>\n'
        f"  <dir>{FONT_DIR}</dir>\n  <cachedir>{cache / 'fc-cache'}</cachedir>\n</fontconfig>\n"
    )
    if not conf.exists() or conf.read_text() != body:
        conf.write_text(body)
    os.environ["FONTCONFIG_FILE"] = str(conf)


_pin_fonts()
