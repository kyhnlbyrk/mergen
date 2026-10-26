"""Ses aygıtları. Her platformda tek bir ses arayüzü kullanılır (Windows: MME, her örnekleme hızını kabul eder; macOS:
Core Audio); aygıt adın bir parçasıyla bulunur. Sistemin varsayılan aygıtlarına dokunulmaz, sadece Mergen bunları kullanır."""
import sounddevice as sd

from .kayit import log
from .yollar import MAC, WINDOWS

HOST_API = "MME" if WINDOWS else "Core Audio" if MAC else None
# Windows'un sanal "Ses Eşleştiricisi" gerçek bir aygıt değil, listede gösterilmez.
HIDDEN = ("Eşleştiricisi", "Sound Mapper")


def _devices(output: bool) -> list[tuple[int, str]]:
    apis = sd.query_hostapis()
    channels = "max_output_channels" if output else "max_input_channels"
    found = [(i, d["name"]) for i, d in enumerate(sd.query_devices())
             if d[channels] > 0 and (HOST_API is None or apis[d["hostapi"]]["name"] == HOST_API)]
    return [(i, name) for i, name in found if not any(h in name for h in HIDDEN)]


def find_device(name: str, output: bool):
    """Adında name geçen ilk aygıt. Ad boşsa ya da bulunamazsa None (sistemin varsayılanı)."""
    if not name:
        return None
    for index, device in _devices(output):
        if name.lower() in device.lower():
            return index
    log(f"ses aygıtı bulunamadı: '{name}', varsayılan kullanılıyor")
    return None


def list_devices(output: bool) -> list[str]:
    return [name for _, name in _devices(output)]


def device_name(index, output: bool) -> str:
    """Aygıtın adı; index None ise sistemin varsayılanının adı."""
    try:
        return sd.query_devices(index, "output" if output else "input")["name"]
    except (sd.PortAudioError, ValueError):
        return ""
