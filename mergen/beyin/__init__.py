"""Mergen'in beyni: arkadaki yapay zekâ. Hepsi API anahtarsız, kullanıcının aboneliğiyle giriş yaptığı resmi komut
satırı aracıyla çalışır. Şimdilik Claude; Codex (ChatGPT) ve Gemini sırada."""
from ..ayarlar import SETTINGS
from .claude import ClaudeBrain
from .temel import Brain

BRAINS: dict[str, type[Brain]] = {
    "claude": ClaudeBrain,
}
# Kurulum sihirbazında "yakında" diye görünenler.
COMING_SOON = {"codex": "ChatGPT (Codex)", "gemini": "Gemini"}


def create_brain() -> Brain:
    return BRAINS.get(SETTINGS["beyin"], ClaudeBrain)()
