"""Kayıt: bütün konuşma (duydu / soruyor / söylüyor) ve olaylar veri klasöründeki mergen.log'a yazılır."""
import sys
import time

from .yollar import CONSOLE_LOG, LOG


def redirect_console() -> None:
    """Konsolsuz açıldıysa (Windows'ta pythonw) stdout yoktur: kütüphanelerin uyarıları ve hatalar konsol.log'a yazılsın."""
    if sys.stdout is None:
        sys.stdout = sys.stderr = open(CONSOLE_LOG, "a", encoding="utf-8", buffering=1)


def log(message: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {message}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
