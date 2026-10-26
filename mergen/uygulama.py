"""Mergen'in ana döngüsü: uyku → "Mergen uyan" → sohbet (her konuşma ona söylenmiş sayılır) → "görüşürüz" ile uyku.
Ekrandaki ayarlar paneli de burada bağlanır."""
import os
import random
import re
import threading

from .arayuz import Screen
from .ayarlar import SETTINGS, save_settings
from .beyin import BRAINS, create_brain
from .cihazlar import device_name, list_devices
from .kayit import log
from .kulak import BARGE_LEVELS, BASE_WORDS, INF, WHISPER_MODELS, BargeDetector, Ears, user_words
from .kurulum import Setup
from .ses import Voice

SLEEP_WORDS = re.compile(r"görüşürüz|görüşmek üzere|tamam teşekkür|teşekkürler bu kadar|uyu(yabilirsin)?\b|sus artık")
# Mergen tamamen kapanır (bellek ve ekran kartı boşalır).
SHUTDOWN_WORDS = re.compile(r"kapat kendini|kendini kapat|programı kapat|mergen'?i kapat")
RESET_WORDS = re.compile(r"yeni konuşma|baştan başla")

GREETINGS = ["Buyurun beyim?", "Dinliyorum beyim.", "Emrinizdeyim beyim.", "Evet beyim?", "Buradayım beyim."]
GOODBYES = ["Her zaman buradayım beyim.", "Görüşmek üzere beyim.", "Bir şey olursa seslenmeniz yeterli beyim.", "Peki beyim."]


def connect_settings(screen: Screen, voice: Voice, ears: Ears, brain_holder: list) -> None:
    """Ekrandaki ayarlar paneli: değişiklik anında uygulanır ve ayar.json'a kaydedilir; "Sesi dene"."""

    def get() -> dict:
        brain = brain_holder[0]
        return {
            "beyin": SETTINGS["beyin"], "beyinler": {key: cls.TITLE for key, cls in BRAINS.items()},
            "model": SETTINGS["model"], "modeller": brain.MODELS, "efor": SETTINGS["efor"], "eforlar": brain.EFFORTS,
            "tam_yetki": SETTINGS["tam_yetki"],
            "ses_seviyesi": SETTINGS["ses_seviyesi"], "sessizlik_suresi": SETTINGS["sessizlik_suresi"],
            "hoparlor": device_name(voice.speaker, output=True), "hoparlorler": list_devices(output=True),
            "mikrofon": SETTINGS["mikrofon"] or device_name(None, output=False), "mikrofonlar": list_devices(output=False),
            "whisper_model": SETTINGS["whisper_model"], "whisper_modeller": WHISPER_MODELS,
            "kelimeler": ", ".join(user_words()), "temel_kelimeler": ", ".join(BASE_WORDS),
            "araya_girme": SETTINGS["araya_girme"], "araya_girme_secenekleri": {k: v[0] for k, v in BARGE_LEVELS.items()},
        }

    def set_(changes: dict) -> dict:
        restart = False
        if changes.get("beyin") in BRAINS and changes["beyin"] != SETTINGS["beyin"]:
            SETTINGS["beyin"], SETTINGS["model"] = changes["beyin"], ""
            brain_holder[0] = create_brain()
            threading.Thread(target=brain_holder[0].start, daemon=True).start()
        brain = brain_holder[0]
        if changes.get("model") in brain.MODELS and changes["model"] != SETTINGS["model"]:
            SETTINGS["model"] = changes["model"]
            restart = True
        if changes.get("efor") in brain.EFFORTS and changes["efor"] != SETTINGS["efor"]:
            SETTINGS["efor"] = changes["efor"]
            restart = True
        if "tam_yetki" in changes and bool(changes["tam_yetki"]) != SETTINGS["tam_yetki"]:
            SETTINGS["tam_yetki"] = bool(changes["tam_yetki"])
            restart = True
        if restart:
            brain.restart()
        if changes.get("whisper_model") in WHISPER_MODELS and changes["whisper_model"] != SETTINGS["whisper_model"]:
            SETTINGS["whisper_model"] = changes["whisper_model"]
            threading.Thread(target=ears.load_whisper, args=(SETTINGS["whisper_model"],), daemon=True).start()
        if "kelimeler" in changes:
            SETTINGS["kelimeler"] = ", ".join(w.strip() for w in str(changes["kelimeler"]).split(",") if w.strip())
        if changes.get("araya_girme") in BARGE_LEVELS:
            SETTINGS["araya_girme"] = changes["araya_girme"]
        if "sessizlik_suresi" in changes:
            SETTINGS["sessizlik_suresi"] = round(min(max(float(changes["sessizlik_suresi"]), 0.6), 4.0), 1)
        if "ses_seviyesi" in changes:
            SETTINGS["ses_seviyesi"] = round(min(max(float(changes["ses_seviyesi"]), 0.3), 3.0), 2)
        if "hoparlor" in changes:
            SETTINGS["hoparlor"] = changes["hoparlor"]
            voice.set_speaker(changes["hoparlor"])
        if "mikrofon" in changes:
            SETTINGS["mikrofon"] = changes["mikrofon"]
            ears.open_microphone(changes["mikrofon"])
        save_settings()
        log(f"ayarlar: {SETTINGS['beyin']} (model {SETTINGS['model'] or 'varsayılan'}, efor {SETTINGS['efor']}, "
            f"{'tam yetki' if SETTINGS['tam_yetki'] else 'sınırlı'}), whisper {SETTINGS['whisper_model']}, "
            f"söz kesme {SETTINGS['araya_girme']}, ses {SETTINGS['ses_seviyesi']:.2f}, "
            f"sessizlik {SETTINGS['sessizlik_suresi']:.1f} sn, hoparlör '{device_name(voice.speaker, output=True)}', "
            f"mikrofon '{SETTINGS['mikrofon'] or 'varsayılan'}'")
        return get()

    def test() -> None:
        asleep = screen.state == "uyku"
        if asleep:
            voice.wake()
        voice.say("Ses böyle geliyor beyim. Yeterince gür mü?")
        if asleep:
            voice.sleep()
        ears.flush()

    screen.routes[("GET", "/ayarlar")] = get
    screen.routes[("POST", "/ayarlar")] = set_
    screen.routes[("POST", "/dene")] = lambda body: threading.Thread(target=test, daemon=True).start()


def main() -> None:
    # Zaten açıksa ikinci bir Mergen başlamaz (iki tane aynı anda dinleyip cevap verirdi): sadece ekran öne gelir.
    if Screen.already_running():
        Screen.open()
        return
    screen = Screen()
    screen.open()

    def shutdown() -> None:
        log("ekrandan kapatıldı")
        os._exit(0)

    screen.on_shutdown = shutdown
    setup = Setup(screen)
    if not SETTINGS["kurulum_tamam"]:
        # İlk açılış: ekrandaki sihirbaz seçimleri alır, gerekenleri indirir; hafif ses ve konuşma tanıma hazır olunca
        # Mergen açılır (doğal ses seçildiyse arka planda inmeye devam eder).
        log("ilk açılış: kurulum sihirbazı bekleniyor")
        setup.core_ready.wait()
    voice = Voice(screen)
    setup.on_xtts_ready = voice.switch_to_xtts
    if SETTINGS["ses_motoru"] == "xtts" and SETTINGS["xtts_kurulu"]:
        # Doğal ses, Voice açılırken inip bitmiş olabilir.
        threading.Thread(target=voice.switch_to_xtts, daemon=True).start()
    setup.resume_background()
    ears = Ears(screen)
    # Panelden yapay zekâ değişince yenisi buraya konur; döngü her soruda buradan okur.
    brains = [create_brain()]
    threading.Thread(target=brains[0].start, daemon=True).start()
    ears.barge_event = voice.interrupted
    voice.barge = ears.barge = BargeDetector()
    connect_settings(screen, voice, ears, brains)
    voice.wake()
    voice.say("Sistemler hazır beyim. Mergen uyan demeniz yeterli.")
    voice.sleep()
    ears.flush()
    while True:
        screen.set_state("uyku")
        ears.show_mic = False
        text = ears.wait_for_wake()
        screen.set_state("dinliyor")
        ears.show_mic = True
        # Ses modeli ekran kartına taşınırken bip çalar.
        loading = threading.Thread(target=voice.wake, daemon=True)
        loading.start()
        voice.beep()
        loading.join()
        if not text:
            if voice.new_voice:
                voice.new_voice = False
                voice.say("Yeni sesim hazır beyim. Nasıl, beğendiniz mi?")
            else:
                voice.say(random.choice(GREETINGS))
            ears.flush()
        # Uyanıkken sessizlikte uyumaz: "görüşürüz" ya da "uyu" diyene kadar her konuşma ona söylenmiş sayılır.
        while True:
            if not text:
                text = ears.listen(INF)
            if not text:
                continue  # Whisper bir şey anlamadı (öksürük, gürültü)
            log(f"duydu: {text}")
            screen.message("sen", text)
            lowered = text.lower()
            if SHUTDOWN_WORDS.search(lowered):
                voice.say("Peki beyim, sistemleri kapatıyorum. İyi günler.")
                screen.set_state("uyku")
                log("kapandı")
                return
            if SLEEP_WORDS.search(lowered):
                voice.say(random.choice(GOODBYES))
                break
            if RESET_WORDS.search(lowered):
                brains[0].reset()
                voice.say("Peki beyim, sayfayı temizledim.")
            else:
                ears.show_mic = False
                screen.set_state("dusunuyor")
                ears.flush()
                # Beklerken bir şey söylenmez: ekrandaki top turuncuya döner ("düşünüyorum").
                reply = brains[0].ask(text)
                screen.set_state("dinliyor")
                interrupted = voice.say(reply)
                ears.show_mic = True
                if interrupted:
                    # Araya girildi: konuşmanın başı kaybolmasın, sadece son bir saniye tutulur; hemen dinler.
                    ears.keep_recent()
                    text = ""
                    continue
            ears.flush()
            text = ""
        voice.sleep()
        ears.flush()
