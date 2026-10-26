"""Başlatma: python -m mergen (ya da kurulumdan sonra mergen komutu).

Ekran, ağır kütüphaneler (Whisper, ses motoru) yüklenmeden önce açılır: macOS ilk açılışta indirilen her kütüphaneyi
güvenlik taramasından geçirdiği için yükleme dakikalar sürebiliyor; bu sırada kullanıcı boş ekran yerine "hazırlanıyor"
görür."""
import sys
import time

from .kayit import log, redirect_console


def run() -> None:
    redirect_console()
    from .arayuz import Screen

    # Zaten açıksa ikinci bir Mergen başlamaz (iki tane aynı anda dinleyip cevap verirdi): sadece ekran öne gelir.
    if Screen.already_running():
        Screen.open()
        return
    screen = Screen()
    screen.open()
    try:
        started = time.time()
        from .uygulama import main

        log(f"açılış: kütüphaneler yüklendi ({time.time() - started:.1f} sn)")
        main(screen)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as error:  # Arka planda çalışırken hata kayda düşsün.
        log(f"HATA: {error!r}")
        raise


if __name__ == "__main__":
    run()
