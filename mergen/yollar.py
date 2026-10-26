"""Mergen'in dosyalarının yerleri ve çalıştığı platform. Kullanıcıya hiçbir şey sorulmaz: işletim sistemi ve klasörler
burada tespit edilir.

Kodla gelen dosyalar (ekran, medya betikleri) paketin içindedir. Kullanıcıya ait her şey (ayarlar, kayıtlar, notlar,
indirilen modeller) tek bir veri klasöründedir; Mergen kaldırılınca o klasör silinir, sistemde iz kalmaz:
  Windows: %LOCALAPPDATA%\\Mergen
  macOS:   ~/Library/Application Support/Mergen
  Linux:   ~/.local/share/mergen
MERGEN_HOME ortam değişkeni verilirse veri klasörü odur (geliştirme ve deneme için).
"""
import os
import sys
from pathlib import Path

WINDOWS = sys.platform == "win32"
MAC = sys.platform == "darwin"

PACKAGE = Path(__file__).resolve().parent
TOOLS = PACKAGE / "araclar"


def _data_dir() -> Path:
    if WINDOWS:
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "Mergen"
    if MAC:
        return Path.home() / "Library" / "Application Support" / "Mergen"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "mergen"


DATA = Path(os.environ.get("MERGEN_HOME") or _data_dir())
MODELS = DATA / "modeller"
SETTINGS_FILE = DATA / "ayar.json"
# Kullanıcının Mergen'e bıraktığı (ve Mergen'in öğrendikçe yazdığı) notlar: projeleri, tercihleri. Sistem istemine eklenir.
NOTES_FILE = DATA / "notlar.md"
LOG = DATA / "mergen.log"
CONSOLE_LOG = DATA / "konsol.log"
BRAIN_LOG = DATA / "beyin.log"

MODELS.mkdir(parents=True, exist_ok=True)
# Whisper ve XTTS modellerini Hugging Face'ten indirir: önbellek veri klasörüne yönlendirilir (sadece Mergen'in süreci için;
# kullanıcı HF_HOME'u kendisi verdiyse ona dokunulmaz). Bazı coqui dosyaları TTS_HOME'a iner.
os.environ.setdefault("HF_HOME", str(MODELS / "huggingface"))
# Xet indiricisi dosyayı ayrı bir önbellekte toplayıp en sonda taşıyor: ilerleme ölçülemiyor. Düz HTTP indirmesi model
# klasörüne (yarım dosya .incomplete) yazar; ilerleme oradan ölçülür ve kesilirse kaldığı yerden sürer.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("TTS_HOME", str(MODELS))
