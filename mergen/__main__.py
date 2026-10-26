"""Başlatma: python -m mergen (ya da kurulumdan sonra mergen komutu)."""
import sys

from .kayit import log, redirect_console


def run() -> None:
    redirect_console()
    from .uygulama import main

    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as error:  # Arka planda çalışırken hata kayda düşsün.
        log(f"HATA: {error!r}")
        raise


if __name__ == "__main__":
    run()
