"""Mergen'in kendi penceresi (pywebview): Windows'ta görev çubuğunda, macOS'ta Dock'ta ve Cmd+Tab'da kendi simgesiyle duran
gerçek bir uygulama penceresi; içinde ekran (arayuz.html). Tarayıcı penceresi Mac'te ya öne gelmiyor ya da Dock simgesi
zıplayıp duruyordu (arkadaki Python kendini uygulama olarak tanıtmıyordu).

pywebview pencereyi ana iş parçacığında ister: Mergen'in kendisi ayrı iş parçacığında çalışır. Pencere kapanınca Mergen
kapanır. pywebview yoksa ya da açılamazsa (Linux'ta GTK / Qt yoksa) tarayıcı penceresine düşülür."""
import os

from .kayit import log
from .yollar import MAC, TOOLS, WINDOWS


def run_in_window(screen, start_app) -> bool:
    """Pencereyi açar, Mergen'i (start_app) pencere açılınca arka planda başlatır ve pencere kapanana kadar bekler.
    Pencere açılamazsa False döner (Mergen başlatılmamıştır)."""
    if not (WINDOWS or MAC):
        return False
    _set_identity()
    try:
        import webview
    except ImportError:
        return False
    window = webview.create_window("Mergen", screen.url, width=1100, height=720, min_size=(760, 520),
                                   background_color="#05080D")

    def focus() -> None:
        # İkinci kez açılmak istendi (kısayola yeniden tıklandı): pencere öne gelir.
        window.restore()
        window.show()
        window.on_top = True
        window.on_top = False

    screen.on_focus = focus
    icon = TOOLS / ("mergen.icns" if MAC else "mergen.ico")
    try:
        webview.start(start_app, icon=str(icon))
    except Exception as error:
        log(f"pencere açılamadı ({error!r}), tarayıcıda açılıyor")
        return False
    log("pencere kapatıldı")
    os._exit(0)


def _set_identity() -> None:
    """Uygulamanın adı ve görev çubuğu kimliği. Mergen'i çalıştıran Python'dur: yoksa macOS menü çubuğunda "Python"
    yazar, Windows görev çubuğunda pencere Python'un altında gruplanır."""
    try:
        if MAC:
            from Foundation import NSBundle  # pywebview'la gelir (pyobjc)

            bundle = NSBundle.mainBundle()
            info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
            info["CFBundleName"] = "Mergen"
        elif WINDOWS:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Mergen.Asistan")
    except Exception as error:
        log(f"uygulama kimliği ayarlanamadı ({error!r})")
