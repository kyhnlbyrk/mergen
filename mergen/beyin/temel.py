"""Bütün beyinlerin ortak arayüzü. Her beyin, kullanıcının aboneliğiyle giriş yaptığı resmi bir komut satırı aracıyla
konuşur (API anahtarı yok); bilgisayarı kullanma (komut çalıştırma, dosya) o aracın kendi yeteneğidir."""
import shutil
from pathlib import Path

from ..yollar import WINDOWS


class Brain:
    # Ayarlar panelinde görünen ad; seçilebilir modeller ({değer: görünen ad}, "" hesabın varsayılanı) ve eforlar.
    TITLE = ""
    MODELS: dict[str, str] = {"": "Varsayılan (hesabın modeli)"}
    EFFORTS: dict[str, str] = {}

    @classmethod
    def check(cls) -> dict:
        """Kurulum sihirbazı için: araç kurulu mu ("bulundu"), giriş yapılmış mı ("giris"), hesap ("hesap"); kurulu
        değilse kurulum ve giriş komutları ("kurulum", "giris_komutu")."""
        raise NotImplementedError

    def start(self) -> None:
        """Hazırlık (açılışta arka planda çağrılır: ilk soru beklemesin)."""

    def ask(self, text: str) -> str:
        raise NotImplementedError

    def restart(self) -> None:
        """Model, efor ya da yetki değişti: aynı konuşma sürerek yeniden başlar."""

    def reset(self) -> None:
        """Yeni konuşma: önceki konuşma unutulur."""


def find_executable(name: str) -> Path | None:
    """Komut satırı aracının yeri: PATH'te ya da kurulum betiklerinin bilinen klasörlerinde."""
    found = shutil.which(name)
    if found:
        return Path(found)
    suffix = ".exe" if WINDOWS else ""
    for folder in (Path.home() / ".local" / "bin", Path.home() / ".npm-global" / "bin", Path("/opt/homebrew/bin"),
                   Path("/usr/local/bin")):
        candidate = folder / (name + suffix)
        if candidate.exists():
            return candidate
    return None
