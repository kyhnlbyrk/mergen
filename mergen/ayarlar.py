"""Kalıcı ayarlar: veri klasöründeki ayar.json (ekrandaki panelden ve ilk açılış sihirbazından yazılır). Bütün modüller
ayarı kullandığı anda SETTINGS'ten okur; panelden yapılan değişiklik böylece hemen her yere yansır."""
import json

from .yollar import SETTINGS_FILE

DEFAULTS = {
    # İlk açılış sihirbazı bitti mi (kurulum.py); doğal ses (XTTS) indi mi. XTTS arka planda inerken Mergen Piper'la konuşur.
    "kurulum_tamam": False,
    "xtts_kurulu": False,
    # Kullanıcı XTTS modelinin lisansını (CPML, ticari olmayan kullanım) sihirbazda kabul etti mi.
    "xtts_lisans": False,
    # Yapay zekâ: kullanıcının giriş yaptığı komut satırı aracı (beyin/), modeli (boş: hesabın varsayılanı) ve eforu.
    "beyin": "claude",
    "model": "",
    "efor": "low",
    # Tam yetki: yapay zekâ bilgisayarda onay sormadan komut çalıştırır (uygulama açmak, Steam, dosya). Kapalıyken
    # sadece okur ve arar. Geri alınamayan işler için sesli "evet" kuralı her iki durumda da geçerli.
    "tam_yetki": False,
    # Yapay zekânın çalıştığı klasör (boş: ev klasörü) ve erişebileceği ek klasörler (projeler).
    "calisma_klasoru": "",
    "ek_klasorler": [],
    # Ses: "xtts" (doğal, ekran kartında hızlı) ya da "piper" (hafif). XTTS'nin hazır konuşmacısı.
    "ses_motoru": "xtts",
    "ses": "Damien Black",
    "ses_seviyesi": 1.0,
    # Ses aygıtları adın bir parçasıyla seçilir; boşsa sistemin varsayılanı.
    "hoparlor": "",
    "mikrofon": "",
    # Konuşma tanıma (Whisper, işlemcide), konuşma bitti beklemesi (sn), tanıması zor özel kelimeler (virgülle).
    "whisper_model": "small",
    "sessizlik_suresi": 1.6,
    "kelimeler": "",
    # Mergen konuşurken söz kesme hassasiyeti: kapali / dusuk / orta / yuksek.
    "araya_girme": "orta",
}


def _load() -> dict:
    settings = dict(DEFAULTS)
    if SETTINGS_FILE.exists():
        # utf-8-sig: dosya elle düzenlenip BOM'la kaydedildiyse de okunsun.
        settings.update(json.loads(SETTINGS_FILE.read_text(encoding="utf-8-sig")))
    return settings


SETTINGS = _load()


def save_settings() -> None:
    # BOM'suz yazılır.
    SETTINGS_FILE.write_text(json.dumps(SETTINGS, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
