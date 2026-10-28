"""Mergen'in kulağı: mikrofonu sürekli (internetsiz) dinler, konuşma parçalarını Whisper'la (işlemcide) yazıya çevirir.
Mergen konuşurken kullanıcı konuşursa sözünü kesmeye de burası karar verir (BargeDetector)."""
import collections
import ctypes
import importlib
import importlib.util
import os
import queue
import re
import threading
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from faster_whisper.vad import VadOptions, get_speech_timestamps

from .ayarlar import SETTINGS
from .cihazlar import find_device, refresh, refresh_wanted
from .kayit import log
from .ses import LEVEL_STEP, envelope, rms
from .yollar import WINDOWS

RATE = 16000
INF = float("inf")
# Mikrofondan bu kadar süre hiç ses parçası gelmezse çıkarılmış sayılır (açıkken sessizlikte bile parça gelir).
MIC_TIMEOUT = 3.0
# Mikrofon yokken aygıtlar bu aralıkla yeniden taranır.
MIC_RETRY = 2.0
BLOCK = 4000  # 0,25 sn
# Uyanma: "Mergen uyan". Whisper "Mergen"i farklı yazabiliyor; kısa bir konuşma parçasında "uyan" geçmesi yeter.
WAKE = re.compile(r"\buyan(sana|ın)?\b")
# Uyanma için bakılan en uzun konuşma parçası (daha uzunu sohbettir).
WAKE_MAX_SECONDS = 5.0
# Konuşma bitti sayılmadan önce beklenen sessizlik ayarda ("sessizlik_suresi"). Söylenen şey yarım kalmış gibi bitiyorsa
# (bağlaç, dolgu kelimesi, virgül) bu kadar daha beklenir; konuşma sürerse birleşir.
CONTINUE_WAIT = 3.0
CONTINUATION = re.compile(r"(,|\b(ve|ama|fakat|ancak|yani|şey|bir de|çünkü|mesela|hani|ile|veya|ya da|sonra|ayrıca)\s*[.…]*)$")
MAX_UTTERANCE_SECONDS = 25.0
# Whisper sessizlikte ya da gürültüde eğitim verisindeki video altyazılarını uydurur ("Altyazı M.K.", "İzlediğiniz
# için teşekkürler"). Kısa bir parçanın tamamı buysa duyulmamış sayılır.
HALLUCINATION = re.compile(r"altyazı|abone ol|izlediğiniz için|beğenmeyi unutmayın|bir sonraki videoda", re.I)
# Müzik çalarken şarkı sözleri kullanıcının konuşması sanılıyordu ("I'm out again, were you?", "G- G- G-"). Türkçe harf
# içermeyen metinlerde sesin dili hızlı modelle ayrıca tespit edilir; başka bir dil kesinse atılır. Eşikler ölçüldü
# (2026-10-28): İngilizce konuşma ve şarkı sözleri %93-99 İngilizce, Türkçe %0; ama kısa ya da İngilizce kelimeli Türkçe
# de şaşırtıyor ("Evet." %40 İngilizce, "Commit at ve push et." %43 Arnavutça), bu yüzden eşik yüksek.
TURKISH_LETTERS = re.compile(r"[çğıöşüÇĞİÖŞÜ]")
FOREIGN_SURE = 0.8
TURKISH_UNLIKELY = 0.05
# Konuşma eşiği (int16 RMS); ortam gürültüsüne göre başta ayarlanır.
MIN_SPEECH_RMS = 500.0
MIC_GAIN = 4.0
# Whisper'ın tanıması zor kelimeler (yabancı, teknik): duyduğunda bunları tercih eder. Kullanıcı panelden ekler.
BASE_WORDS = ["Mergen", "Claude", "ChatGPT", "Gemini", "Spotify", "Steam", "YouTube", "Discord", "session", "commit", "push",
              "pull", "build", "branch", "merge", "test"]
# Uyanmayı dinleyen model (her zaman bu; seçilen model sadece asıl konuşma için). Kurulumda bu da indirilir.
WAKE_MODEL = "small"
WHISPER_MODELS = {
    # Ayarlar panelindeki adlar. Boyut yazılmaz: inmemişse indirme ekranın köşesinde boyutuyla görünür.
    "small": "Hızlı",
    "medium": "Dengeli",
    "large-v3-turbo": "En doğru",
}

# Mergen konuşurken kullanıcı konuşursa susup dinler. Mergen'in kendi sesi hoparlörden mikrofona sızar: her konuşmanın
# ilk saniyesinde sızıntı ölçülür, mikrofon ancak o yankıdan belirgin yüksekse ve ses gerçekten konuşmaysa (Silero VAD;
# tık, nefes, öksürük sayılmaz) keser. Hassasiyet: (art arda blok sayısı ×0,25 sn, gürültü eşiğinin katı, yankının katı).
BARGE_LEVELS = {
    "kapali": ("Kapalı", None),
    "dusuk": ("Düşük — sadece yüksek sesle, uzun konuşunca", (4, 5.0, 4.0)),
    "orta": ("Orta", (3, 3.5, 3.0)),
    "yuksek": ("Yüksek — kısa bir sözle bile", (2, 2.5, 2.0)),
}
BARGE_LEARN_SECONDS = 1.0  # her konuşmanın başında sızıntı ölçülür (bu sürede söz kesilmez)
BARGE_ECHO_WINDOW = 0.8  # çalınan sesin mikrofona ulaşma gecikmesi payı


def user_words() -> list[str]:
    return [w.strip() for w in SETTINGS["kelimeler"].split(",") if w.strip()]


def _load_whisper(name: str) -> WhisperModel:
    """Whisper modeli: NVIDIA ekran kartı varsa onda (büyük modeller işlemcide bir cümleyi 5-6 sn'de çözüyordu, ekran
    kartında bir saniyenin altında), açılamazsa işlemcide. Model ilk kullanımda veri klasörüne iner (HF_HOME, yollar.py)."""
    if _cuda_available():
        try:
            model = WhisperModel(name, device="cuda", compute_type="int8_float16")
            # CUDA kitaplıkları ancak ilk çözümlemede yüklenir ve ilk çözümleme çekirdekleri hazırladığı için uzun sürer
            # (~20 sn, bir kerelik): açılışta yapılır, ilk "Mergen uyan" beklemesin. Sonuç tembel üretildiği için
            # list() ile çalıştırılır.
            segments, _ = model.transcribe(np.random.default_rng(0).normal(0, 0.01, RATE).astype(np.float32),
                                           language="tr", beam_size=1, vad_filter=False)
            list(segments)
            log(f"Whisper ({name}) ekran kartında")
            return model
        except Exception as error:
            log(f"Whisper ekran kartında açılamadı ({error!r}), işlemcide çalışacak")
    log(f"Whisper ({name}) işlemcide")
    return WhisperModel(name, device="cpu", compute_type="int8")


def _cuda_available() -> bool:
    """NVIDIA ekran kartı var mı (anında bakılır; kartsız bilgisayar ve Mac burada döner) ve Whisper'ın istediği CUDA
    kitaplıkları (cuBLAS, cuDNN) bulunuyor mu. Kitaplıklar olmadan ekran kartında çözümleme hata vermeden takılıyordu."""
    try:
        import ctranslate2

        if ctranslate2.get_cuda_device_count() == 0:
            return False
    except Exception:
        return False
    return load_cuda_libraries()


def load_cuda_libraries() -> bool:
    """CUDA kitaplıklarını Whisper'ın bulacağı yere koyar. Ya PyTorch getirir (doğal ses için kurulur; içe aktarılınca
    kitaplıklarını yükleme yoluna ekler) ya da kurulumun NVIDIA kartı için indirdiği nvidia-cublas / nvidia-cudnn
    paketleri."""
    if importlib.util.find_spec("torch") and importlib.import_module("torch").version.cuda:
        return True  # PyTorch'un işlemci sürümünde CUDA kitaplıkları yok: o zaman aşağıdaki paketlere bakılır
    folders = []
    for package in ("nvidia.cublas", "nvidia.cudnn"):
        try:
            spec = importlib.util.find_spec(package)
        except ModuleNotFoundError:
            spec = None
        if spec is None or not spec.submodule_search_locations:
            return False
        folders.append(Path(spec.submodule_search_locations[0]) / ("bin" if WINDOWS else "lib"))
    for folder in folders:
        if WINDOWS:
            os.add_dll_directory(str(folder))
            os.environ["PATH"] = str(folder) + os.pathsep + os.environ.get("PATH", "")
        else:
            for library in sorted(folder.glob("lib*.so*")):
                ctypes.CDLL(str(library), mode=ctypes.RTLD_GLOBAL)
    return True


class Ears:
    """Mikrofon: konuşma parçalarını kaydeder (sessizlikte durur), Whisper'la yazıya çevirir."""

    def __init__(self, screen) -> None:
        self.screen = screen
        # Konuşurken araya girmeyi dinler (main bağlar): Mergen'in sesi bu olayla kesilir.
        self.barge_event: threading.Event | None = None
        self.barge: BargeDetector | None = None
        # Uyanıkken mikrofonun sesi ekrandaki topa yansır (kullanıcı konuştukça titrer).
        self.show_mic = False
        self.audio: queue.Queue[bytes] = queue.Queue()
        log("Whisper yükleniyor...")
        self.whisper = _load_whisper(SETTINGS["whisper_model"])
        # Uyanma her zaman hızlı modelle dinlenir: uykudayken duyulan her ses yazıya çevrilir, büyük model bunu
        # yetiştiremeyince sesler kuyrukta birikip "Mergen uyan" geç algılanıyordu.
        self.wake_whisper = self.whisper if SETTINGS["whisper_model"] == WAKE_MODEL else _load_whisper(WAKE_MODEL)
        self.stream = None
        self.threshold = MIN_SPEECH_RMS
        self.wait_for_microphone()

    def open_microphone(self, name: str) -> None:
        """Mikrofonu açar; ayarlardan değişince yeniden çağrılır."""
        self.close_microphone()
        self.stream = sd.RawInputStream(samplerate=RATE, blocksize=BLOCK, dtype="int16", channels=1, callback=self._on_audio,
                                         device=find_device(name, output=False))
        self.stream.start()

    def close_microphone(self) -> None:
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except sd.PortAudioError:
                pass  # aygıt çıkarılmışsa kapatırken de hata verebiliyor
            self.stream = None

    def wait_for_microphone(self) -> None:
        """Mikrofonu açar; yoksa (takılı değil ya da çıkarılmış) ekranda söyler ve takılana kadar aygıtları yeniden tarar.
        Mikrofonsuz açılışta Mergen çöküyordu. Hoparlör aygıtları da bu sırada tazelenir."""
        previous = self.screen.state
        waiting = False
        while True:
            try:
                if refresh_wanted():
                    self.close_microphone()
                    refresh()
                self.open_microphone(SETTINGS["mikrofon"])
                break
            except sd.PortAudioError as error:
                self.close_microphone()
                if not waiting:
                    log(f"mikrofon bulunamadı ({error}), takılması bekleniyor")
                    self.screen.set_state("mikrofonsuz")
                    waiting = True
                time.sleep(MIC_RETRY)
                refresh()
        if waiting:
            log("mikrofon bulundu")
            self.screen.set_state(previous)
        self.flush()
        self.calibrate()

    def _next_block(self) -> bytes | None:
        """Mikrofondan sıradaki parça. Mikrofon çıkarıldıysa (parça gelmiyorsa) ya da hoparlör listesinin tazelenmesi
        istendiyse mikrofonu yeniden açar ve None döner: kayıt baştan başlar."""
        if refresh_wanted():
            self.wait_for_microphone()
            return None
        try:
            return self.audio.get(timeout=MIC_TIMEOUT)
        except queue.Empty:
            log("mikrofondan ses gelmiyor (çıkarılmış olabilir)")
            self.wait_for_microphone()
            return None

    def move_to_gpu(self) -> None:
        """Doğal ses için PyTorch arka planda kuruldu: işlemcide açılan Whisper artık ekran kartına geçebilir."""
        if self.whisper.model.device == "cuda" or not _cuda_available():
            return
        whisper = _load_whisper(SETTINGS["whisper_model"])
        self.wake_whisper = whisper if SETTINGS["whisper_model"] == WAKE_MODEL else _load_whisper(WAKE_MODEL)
        self.whisper = whisper

    def load_whisper(self, name: str) -> None:
        """Whisper modelini değiştirir (arka planda yüklenir; ilk seçimde iner). Yüklenene kadar eskisi çalışır."""
        log(f"Whisper modeli yükleniyor: {name}")
        self.whisper = self.wake_whisper if name == WAKE_MODEL else _load_whisper(name)
        log(f"Whisper modeli hazır: {name}")

    def _on_audio(self, data, frames, time_info, status) -> None:
        self.audio.put(bytes(data))
        # Araya girme: Mergen konuşurken kullanıcı konuşursa konuşma kesilir.
        if self.barge and self.barge_event is not None and self.screen.state == "konusuyor" \
                and not self.barge_event.is_set() and self.barge.check(bytes(data), self.threshold):
            self.barge_event.set()
        if self.show_mic and self.screen.state == "dinliyor":
            levels = envelope(np.frombuffer(data, dtype=np.int16), RATE, MIC_GAIN)
            self.screen.schedule_levels(time.time(), levels, LEVEL_STEP)

    def flush(self) -> None:
        """Kendi sesimizi ya da bekleyen eski sesi atar (konuşurken mikrofon kendini duymasın)."""
        while not self.audio.empty():
            self.audio.get_nowait()

    def keep_recent(self, seconds: float = 1.0) -> None:
        """Araya girildi: kuyrukta sadece son birkaç bloğu (kullanıcının konuşmasının başı) tutar, öncesini atar."""
        blocks = []
        while not self.audio.empty():
            blocks.append(self.audio.get_nowait())
        for block in blocks[-max(int(seconds * RATE / BLOCK), 1):]:
            self.audio.put(block)

    def calibrate(self) -> None:
        levels = [rms(self.audio.get(timeout=MIC_TIMEOUT)) for _ in range(8)]
        self.threshold = max(MIN_SPEECH_RMS, float(np.median(levels)) * 3.0)
        log(f"gürültü eşiği {self.threshold:.0f}")

    def wait_for_wake(self) -> str:
        """"Mergen uyan" duyulana kadar bekler. Aynı cümlede söylenen komutu döndürür (yoksa boş)."""
        while True:
            frames = self._record(start_timeout=INF, max_seconds=MAX_UTTERANCE_SECONDS)
            if len(frames) * BLOCK / RATE > WAKE_MAX_SECONDS + 3.0:
                continue  # uzun konuşma: biri başkasıyla konuşuyor, uyanma değil
            text = self._transcribe(frames, self.wake_whisper)
            match = WAKE.search(text.lower()) if text else None
            if match:
                log(f"uyandı: '{text}'")
                return text[match.end():].strip(" ,.!?")

    def listen(self, start_timeout: float) -> str:
        """Konuşma başlayana kadar en fazla start_timeout bekler, sessizlik gelene kadar kaydeder, yazıya çevirir.
        Söylenen yarım kalmış gibi bitiyorsa ("... ve", "... yani", virgül) biraz daha bekler; devam edilirse birleştirir."""
        frames = self._record(start_timeout, MAX_UTTERANCE_SECONDS)
        text = self._transcribe(frames) if frames else ""
        while text and CONTINUATION.search(text.lower().rstrip()):
            log(f"yarım kaldı, bekliyor: {text}")
            more = self._record(CONTINUE_WAIT, MAX_UTTERANCE_SECONDS)
            if not more:
                break
            frames += more
            text = f"{text} {self._transcribe(more)}".strip()
        if text and not self._is_speech_for_us(text, frames):
            return ""
        return text

    def _is_speech_for_us(self, text: str, frames: list[bytes]) -> bool:
        """Söylenen gerçekten kullanıcının Türkçe konuşması mı? Anlamsız parçaları ("...", "G- G- G-") ve başka dildeki
        sesi (çoğunlukla hoparlörden gelen şarkı sözü) ayıklar."""
        if not any(len(word) >= 2 for word in re.findall(r"[^\W\d_]+", text)):
            log(f"anlamsız tanıma atıldı: {text}")
            return False
        if TURKISH_LETTERS.search(text):
            return True
        audio = np.frombuffer(b"".join(frames), dtype=np.int16).astype(np.float32) / 32768.0
        language, probability, probabilities = self.wake_whisper.detect_language(audio)
        if language != "tr" and probability >= FOREIGN_SURE and dict(probabilities).get("tr", 0.0) < TURKISH_UNLIKELY:
            log(f"başka dilde ses atıldı ({language} %{probability * 100:.0f}): {text}")
            return False
        return True

    def _record(self, start_timeout: float, max_seconds: float) -> list[bytes]:
        """Konuşma başlayınca kaydeder, sessizlik gelince durur. Konuşma hiç başlamazsa boş liste."""
        frames: list[bytes] = []
        waited = 0.0
        speaking = False
        silence = 0.0
        spoken = 0.0
        seconds = BLOCK / RATE
        while True:
            data = self._next_block()
            if data is None:
                return []  # mikrofon yeniden açıldı: yarım kalan kayıt atılır
            loud = rms(data) > self.threshold
            if not speaking:
                waited += seconds
                frames = (frames + [data])[-2:]  # konuşmanın başı kesilmesin
                if loud:
                    speaking = True
                elif waited >= start_timeout:
                    return []
                continue
            frames.append(data)
            spoken += seconds
            silence = 0.0 if loud else silence + seconds
            if silence >= float(SETTINGS["sessizlik_suresi"]) or spoken >= max_seconds:
                return frames

    def _transcribe(self, frames: list[bytes], model: WhisperModel = None) -> str:
        audio = np.frombuffer(b"".join(frames), dtype=np.int16).astype(np.float32) / 32768.0
        hotwords = ", ".join(BASE_WORDS + user_words())
        segments, _ = (model or self.whisper).transcribe(audio, language="tr", beam_size=1, vad_filter=True,
                                                         hotwords=hotwords)
        text = " ".join(s.text.strip() for s in segments).strip()
        if text and len(text) < 60 and HALLUCINATION.search(text):
            log(f"uydurma altyazı atıldı: {text}")
            return ""
        return text


class BargeDetector:
    """Söz kesme kararı. Mergen konuşurken kendi sesi hoparlörden mikrofona sızar; bu yüzden her konuşmanın ilk
    saniyesinde sızıntı oranı (mikrofon / çalınan ses) ölçülür. Sonra mikrofon, o an beklenen yankının birkaç katını ve
    gürültü eşiğinin birkaç katını art arda aşarsa ve Silero VAD bunu konuşma sayarsa söz kesilir."""

    def __init__(self) -> None:
        self._played: collections.deque = collections.deque(maxlen=100)  # (yazıldığı an, seviye)
        self._first_played = 0.0
        self.leak = 0.0  # mikrofon seviyesi / çalınan ses seviyesi
        self._loud: list[bytes] = []

    def begin(self) -> None:
        self._played.clear()
        self._first_played = 0.0
        self._loud = []
        self.leak *= 0.5  # önceki konuşmadan kalan ölçüm yavaşça unutulur, yenisi ölçülür

    def played(self, level: float) -> None:
        now = time.time()
        if not self._first_played:
            self._first_played = now
        self._played.append((now, level))

    def _echo(self) -> float:
        now = time.time()
        return max((level for at, level in self._played if now - at <= BARGE_ECHO_WINDOW), default=0.0)

    def check(self, data: bytes, threshold: float) -> bool:
        params = BARGE_LEVELS.get(SETTINGS["araya_girme"], BARGE_LEVELS["orta"])[1]
        if params is None or not self._first_played:
            return False
        blocks, noise_factor, echo_factor = params
        level, echo = rms(data), self._echo()
        if time.time() - self._first_played < BARGE_LEARN_SECONDS:
            if echo > 0:
                self.leak = max(self.leak, level / echo)
            return False
        need = max(threshold * noise_factor, self.leak * echo * echo_factor)
        if level <= need:
            self._loud = []
            return False
        self._loud.append(data)
        if len(self._loud) < blocks:
            return False
        if is_speech(b"".join(self._loud)):
            log(f"söz kesme: mikrofon {level:.0f}, yankı payı {self.leak * echo:.0f}, eşik {need:.0f}")
            return True
        self._loud.pop(0)
        return False


def is_speech(data: bytes) -> bool:
    """Silero VAD (faster-whisper'la gelir): sesin en az yarısı konuşma mı."""
    audio = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
    spans = get_speech_timestamps(audio, VadOptions(min_speech_duration_ms=200, min_silence_duration_ms=100))
    return sum(s["end"] - s["start"] for s in spans) >= audio.size * 0.5
