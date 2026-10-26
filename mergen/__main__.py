"""Başlatma: python -m mergen (ya da kurulumdan sonra mergen komutu).

Ekran, ağır kütüphaneler (Whisper, ses motoru) yüklenmeden önce kendi penceresinde açılır (pencere.py): macOS ilk açılışta
indirilen her kütüphaneyi güvenlik taramasından geçirdiği için yükleme uzun sürebiliyor; bu sırada kullanıcı boş ekran
yerine "hazırlanıyor" görür."""
import os
import time
import traceback

from .kayit import log, redirect_console


def run() -> None:
    redirect_console()
    from .arayuz import Screen

    # Zaten açıksa ikinci bir Mergen başlamaz (iki tane aynı anda dinleyip cevap verirdi): açık olanın penceresi öne gelir.
    if Screen.already_running():
        Screen.bring_to_front()
        return
    screen = Screen()
    from .pencere import run_in_window

    if not run_in_window(screen, lambda: start(screen)):
        screen.open()
        start(screen)


def start(screen) -> None:
    try:
        started = time.time()
        from .uygulama import main

        log(f"açılış: kütüphaneler yüklendi ({time.time() - started:.1f} sn)")
        main(screen)
    except KeyboardInterrupt:
        pass
    except Exception as error:  # Arka planda çalışırken hata kayda düşsün.
        log(f"HATA: {error!r}")
        traceback.print_exc()
        os._exit(1)
    # "Kapat kendini": pencere de kapanır (Mergen pencereden ayrı iş parçacığında çalışıyor).
    os._exit(0)


if __name__ == "__main__":
    run()
