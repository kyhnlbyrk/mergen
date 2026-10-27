"""Mergen'in sesi: XTTS v2 (doğal Türkçe, ekran kartında hızlı) ya da Piper (hafif yedek). Konuşma paragraf paragraf ve
akışla üretilir: ilk ses ~0,4 sn'de gelir, üretim çalmanın önünde gider."""
import os
import queue
import re
import threading
import time

import numpy as np
import sounddevice as sd

from .ayarlar import SETTINGS
from .cihazlar import find_device
from .kayit import log

# Konuşma parçası en fazla bu kadar karakter (XTTS'nin Türkçe sınırı 226). Sıcaklık ve çeşitlilik varsayılana yakın:
# yükseltince (0,8 / 0,9) cümle sonlarında uydurma "uh" sesleri ve uzayan kelimeler çıkıyordu. Doğallığı paragraf hâlinde
# üretim veriyor. Hız normal (1,05'te bazı kelimeler uzuyordu).
CHUNK_LIMIT = 220
XTTS_TEMPERATURE = 0.7
XTTS_TOP_P = 0.85
XTTS_SPEED = 1.0
# Akış: dilim büyüklüğü ve çalmaya başlamadan önce doldurulan tampon (üretim çalmanın gerisinde kalıp takılmasın).
STREAM_CHUNK = 30
PREBUFFER_SECONDS = 0.4
# Parçanın sonundaki uydurma sesi yakalamak için çalınmadan tutulan kuyruk ve sessizlik eşiği (RMS, 0..1).
TAIL_HOLD = 0.6
TAIL_SILENCE_RMS = 0.012
# Ekrandaki topun hareketi: ses yüksekliği bu aralıkla ölçülür; konuşma (RMS ~0,05-0,2) bu kazançla 0..1'e taşınır.
LEVEL_STEP = 1 / 30
LEVEL_GAIN = 5.0
# Piper'ın Türkçe sesi (Hugging Face'ten, diğer modellerle aynı önbelleğe iner; kurulum.py).
PIPER_REPO = "rhasspy/piper-voices"
PIPER_MODEL = "tr/tr_TR/dfki/medium/tr_TR-dfki-medium.onnx"
# XTTS "Mergen"i çoğu kez "Mercan" diye okuyor. Yazımlar söyletilip Whisper'a dinletildi (2026-10-27): düz "Mergen" 8'de
# 1, "Mêrgen" 8'de 5 doğru duyuldu. Sadece seslendirilen metinde değişir, ekranda "Mergen" kalır. Piper doğru okuyor.
SPOKEN_NAME = re.compile(r"\bMergen", re.IGNORECASE)
XTTS_REPO = "tts-hub/XTTS-v2"
DEFAULT_SPEAKER = "Damien Black"  # Kayahan 58 konuşmacıyı dinleyip bunu seçti (2026-10-23)
XTTS_IGNORE = ["samples/*", "dvae.pth"]


class XttsEngine:
    """XTTS v2. Açılışta diskten bir kez yüklenir ve RAM'de bekler; uyanınca ekran kartına taşınır (~0,4 sn), uykuya
    geçince RAM'e döner ve ekran kartı boşalır. Ekran kartı yoksa işlemcide (ya da Apple Silicon'da MPS'de) çalışır."""

    def __init__(self) -> None:
        # Model veri klasörüne iner (yollar.py). Lisans (CPML, ticari olmayan) kurulumda kullanıcıya onaylatılır.
        os.environ.setdefault("COQUI_TOS_AGREED", "1")
        import torch
        import TTS.tts.models.xtts as xtts_module
        from TTS.api import TTS

        # Kayıt dosyasını torchcodec (FFmpeg DLL'leri ister) yerine wave ile okur.
        xtts_module.load_audio = _load_wav_tensor
        self.torch = torch
        if torch.cuda.is_available():
            self.gpu = "cuda"
        elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            self.gpu = "mps"
        else:
            self.gpu = None
        self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cpu")
        self.model = self.tts.synthesizer.tts_model
        self.rate = 24000
        # Sesin özellikleri bir kez çıkarılır (her parçada yeniden hesaplanmaz).
        self.set_speaker(SETTINGS["ses"])
        log(f"ses: XTTS ({self.gpu or 'sadece işlemci'}, {self.speaker})")

    @property
    def speakers(self) -> list[str]:
        """Hazır konuşmacılar (58); varsayılan Damien Black başta, gerisi alfabetik."""
        names = sorted(self.model.speaker_manager.speakers)
        return [DEFAULT_SPEAKER] + [n for n in names if n != DEFAULT_SPEAKER]

    def set_speaker(self, name: str) -> None:
        """Konuşmacıyı değiştirir: sesin özellikleri hazır, model yeniden yüklenmez (anında)."""
        speakers = self.model.speaker_manager.speakers
        self.speaker = name if name in speakers else DEFAULT_SPEAKER
        voice = speakers[self.speaker]
        self.gpt_latent, self.speaker_embedding = voice["gpt_cond_latent"], voice["speaker_embedding"]

    def wake(self) -> None:
        if self.gpu:
            started = time.time()
            try:
                self.tts.to(self.gpu)
            except Exception as error:
                self._fall_back_to_cpu(error)
                return
            log(f"ses modeli ekran kartında ({time.time() - started:.1f} sn)")

    def _fall_back_to_cpu(self, error: Exception) -> None:
        """Ekran kartında (özellikle Mac çipinde, MPS) çalışmadı: bundan sonra işlemcide çalışır."""
        log(f"ses modeli {self.gpu} üzerinde çalışmadı ({error!r}), işlemcide devam ediyor")
        self.gpu = None
        self.tts.to("cpu")

    def sleep(self) -> None:
        if self.gpu:
            self.tts.to("cpu")
            if self.gpu == "cuda":
                self.torch.cuda.empty_cache()
            log("ses modeli RAM'de, ekran kartı boş")

    def stream(self, part: str):
        """Parçayı tek seferde (bağlı tonlamayla) üretir ama sesi hazır oldukça küçük dilimler hâlinde verir. Ekran
        kartında hata çıkarsa (Mac çipinde bazı işlemler desteklenmeyebilir) işlemcide yeniden üretir."""
        part = SPOKEN_NAME.sub("Mêrgen", part)
        produced = False
        try:
            for audio in self._stream(part):
                produced = True
                yield audio
        except Exception as error:
            if not self.gpu or produced:
                raise
            self._fall_back_to_cpu(error)
            yield from self._stream(part)

    def _stream(self, part: str):
        device = self.model.device
        # Son TAIL_HOLD saniye çalınmadan tutulur: parça bitince kuyruğundaki uydurma ses ("uh") kesilir.
        hold = int(TAIL_HOLD * self.rate)
        held = np.zeros(0, np.int16)
        for chunk in self.model.inference_stream(part, "tr", self.gpt_latent.to(device), self.speaker_embedding.to(device),
                                                 stream_chunk_size=STREAM_CHUNK, temperature=XTTS_TEMPERATURE, top_p=XTTS_TOP_P,
                                                 speed=XTTS_SPEED):
            audio = (np.clip(chunk.cpu().numpy().astype(np.float32), -1.0, 1.0) * 32767).astype(np.int16)
            held = np.concatenate([held, audio])
            if held.size > hold:
                yield held[:-hold]
                held = held[-hold:]
        yield trim_tail(held, self.rate)


def _load_wav_tensor(path, sampling_rate):
    """XTTS'nin kayıt okuyucusunun yerine: wav'ı okur, tek kanala indirir, istenen örnekleme hızına çevirir."""
    import wave

    import torch
    import torchaudio

    with wave.open(str(path)) as f:
        rate, channels = f.getframerate(), f.getnchannels()
        samples = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    audio = torch.from_numpy(samples.reshape(-1, channels).mean(axis=1)).unsqueeze(0)
    if rate != sampling_rate:
        audio = torchaudio.functional.resample(audio, rate, sampling_rate)
    return audio.clip_(-1, 1)


class PiperEngine:
    """Piper: internetsiz, hafif, her bilgisayarda hızlı (yedek ses)."""

    def __init__(self) -> None:
        from huggingface_hub import hf_hub_download
        from piper import PiperVoice, SynthesisConfig

        hf_hub_download(PIPER_REPO, PIPER_MODEL + ".json", local_files_only=True)
        self.voice = PiperVoice.load(hf_hub_download(PIPER_REPO, PIPER_MODEL, local_files_only=True))
        self.config = SynthesisConfig(length_scale=0.92, noise_scale=0.8, noise_w_scale=0.9)
        self.rate = self.voice.config.sample_rate
        log("ses: Piper")

    def stream(self, part: str):
        chunks = list(self.voice.synthesize(part, syn_config=self.config))
        yield np.concatenate([c.audio_int16_array for c in chunks]) if chunks else np.zeros(0, np.int16)

    def wake(self) -> None:
        pass

    def sleep(self) -> None:
        pass


class Voice:
    """Paragraf paragraf konuşur, akışla: ses üretildikçe kesintisiz tek bir hoparlör akışına yazılır (üretim ayrı iş
    parçacığında; çalma onu beklemez)."""

    def __init__(self, screen) -> None:
        self.screen = screen
        # Aynı anda tek konuşma ("Sesi dene" ile asıl konuşma çakışmasın).
        self._lock = threading.Lock()
        self._switch_lock = threading.Lock()
        # Kullanıcı araya girdi: konuşma o an kesilir (Ears ayarlar).
        self.interrupted = threading.Event()
        self.barge = None
        self.speaker = find_device(SETTINGS["hoparlor"], output=True)
        self.awake = False
        # Ses Piper'dan XTTS'ye geçti, henüz söylenmedi.
        self.new_voice = False
        # Mergen hafif sesle hemen açılır. Doğal ses (seçildiyse ve kuruluysa) arka planda yüklenir ve hazır olunca
        # sessizce ona geçilir: yüklemesi Windows'ta ekran kartıyla ~40 sn, Mac'te daha uzun sürüyor; açılış onu beklerse
        # pencere dakikalarca "hazırlanıyor" kalıyordu.
        try:
            self.engine = PiperEngine()
        except Exception as error:
            log(f"hafif ses açılamadı ({error!r}), doğal ses bekleniyor")
            self.engine = XttsEngine()
            return
        if SETTINGS["ses_motoru"] == "xtts" and SETTINGS["xtts_kurulu"]:
            threading.Thread(target=self.switch_to_xtts, kwargs={"announce": False}, daemon=True).start()

    def set_speaker(self, name: str) -> None:
        self.speaker = find_device(name, output=True)

    def say(self, text: str) -> bool:
        """Söyler. Kullanıcı araya girip sözü kestiyse True."""
        text = clean_for_speech(text)
        if not text:
            return False
        log(f"söylüyor: {text}")
        with self._lock:
            self.interrupted.clear()
            if self.barge:
                self.barge.begin()
            previous = self.screen.state
            self.screen.set_state("konusuyor")
            self.screen.message("mergen", text)
            self._speak(text)
            self.screen.set_state(previous)
            if self.interrupted.is_set():
                log("sözü kesildi, dinliyor")
                self.screen.interrupt()
                return True
            return False

    def _speak(self, text: str) -> None:
        ready: queue.Queue = queue.Queue()

        def produce() -> None:
            try:
                for part in split_chunks(text):
                    for audio in self.engine.stream(part):
                        if self.interrupted.is_set():
                            return
                        ready.put(audio)
            except Exception as error:
                # Ayrı iş parçacığında: kayda düşmezse Mergen sessizce susar, neden bilinmezdi.
                log(f"ses üretilemedi: {error!r}")
            finally:
                ready.put(None)

        threading.Thread(target=produce, daemon=True).start()
        # Tampon: çalmaya başlamadan önce ~0,4 sn ses birikir; üretim bir an yavaşlarsa çalma takılmaz.
        pending: list[np.ndarray] = []
        buffered = 0
        finished = False
        while buffered < PREBUFFER_SECONDS * self.engine.rate and not self.interrupted.is_set():
            audio = ready.get()
            if audio is None:
                finished = True
                break
            pending.append(audio)
            buffered += audio.size
        clock = 0.0  # bu dilimin hoparlörden çıkacağı an (ekrandaki topun hareketi buna göre zamanlanır)
        with sd.OutputStream(samplerate=self.engine.rate, channels=1, dtype="int16", device=self.speaker) as speaker:
            while (pending or not finished) and not self.interrupted.is_set():
                audio = pending.pop(0) if pending else ready.get()
                if audio is None:
                    finished = True
                    continue
                if not audio.size:
                    continue
                audio = boost(audio)
                now = time.time() + speaker.latency
                clock = max(clock, now)
                self.screen.schedule_levels(clock, envelope(audio, self.engine.rate), LEVEL_STEP)
                clock += audio.size / self.engine.rate
                # Küçük parçalarla yaz: araya girilince en geç ~0,1 sn içinde susar.
                step = int(self.engine.rate * 0.1)
                for start in range(0, audio.size, step):
                    if self.interrupted.is_set():
                        speaker.abort()
                        self.screen.clear_levels()
                        return
                    piece = audio[start:start + step]
                    if self.barge:
                        self.barge.played(rms(piece.tobytes()))
                    speaker.write(piece.reshape(-1, 1))

    def wake(self) -> None:
        self.awake = True
        self.engine.wake()

    def sleep(self) -> None:
        self.awake = False
        self.engine.sleep()

    def switch_to_xtts(self, announce: bool = True) -> None:
        """Piper'dan XTTS'ye geçer. announce: doğal ses yeni indi, bir sonraki uyanışta Mergen bunu söyler (her açılışta
        arka planda yüklenip geçildiğinde söylenmez)."""
        with self._switch_lock:
            if isinstance(self.engine, XttsEngine):
                return
            started = time.time()
            try:
                engine = XttsEngine()
            except Exception as error:
                log(f"XTTS açılamadı ({error!r}), Piper'la devam")
                return
            with self._lock:
                self.engine = engine
                if self.awake:
                    engine.wake()
            log(f"doğal sese geçildi ({time.time() - started:.1f} sn)")
        self.new_voice = announce

    def speakers(self) -> list[str]:
        """Doğal sesin konuşmacıları (hafif seste ya da doğal ses henüz yüklenmediyse boş)."""
        return self.engine.speakers if isinstance(self.engine, XttsEngine) else []

    def set_speaker_voice(self, name: str) -> None:
        """Ayarlardan konuşmacı seçildi. Konuşma sürerken değişmesin diye konuşmanın bitmesi beklenir."""
        with self._lock:
            if isinstance(self.engine, XttsEngine):
                self.engine.set_speaker(name)
                log(f"konuşmacı: {self.engine.speaker}")

    def switch_to_piper(self) -> None:
        """Ayarlardan hafif ses seçildi: Piper'a geçer, XTTS'nin tuttuğu ekran kartı belleği boşalır."""
        with self._switch_lock:
            if isinstance(self.engine, PiperEngine):
                return
            engine = PiperEngine()
            with self._lock:
                old, self.engine = self.engine, engine
            old.sleep()

    def beep(self) -> None:
        t = np.linspace(0, 0.12, int(22050 * 0.12), False)
        tone = (np.sin(2 * np.pi * 880 * t) * 0.25 * 32767).astype(np.int16)
        sd.play(boost(tone), 22050, device=self.speaker)
        sd.wait()


def rms(data: bytes) -> float:
    samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(samples * samples))) if samples.size else 0.0


def boost(audio: np.ndarray, gain: float = None) -> np.ndarray:
    """Sesi gain katı yükseltir. Yumuşak sınırlayıcı: %70'in altı doğrusal, üstü tanh ile tavana yumuşakça yaklaşır
    (düz çarpmada tepeler kırpılıp cızırdardı)."""
    gain = float(SETTINGS["ses_seviyesi"]) if gain is None else gain
    if gain == 1.0 or audio.size == 0:
        return audio
    x = audio.astype(np.float32) / 32768.0 * gain
    knee = 0.7
    over = np.abs(x) > knee
    x[over] = np.sign(x[over]) * (knee + (1.0 - knee) * np.tanh((np.abs(x[over]) - knee) / (1.0 - knee)))
    return (x * 32767).astype(np.int16)


def trim_tail(tail: np.ndarray, rate: int) -> np.ndarray:
    """Parçanın sonundaki uydurma sesi keser: son kelimeden sonra kısa bir sessizlik (>= 0,12 sn) ve ardından kısa bir ses
    patlaması (<= 0,35 sn) varsa ("uh", nefes, mırıltı) sessizlikten itibaren atar. Sonda yumuşak sönme (20 ms)."""
    if tail.size == 0:
        return tail
    frame = int(rate * 0.01)
    samples = tail.astype(np.float32) / 32768.0
    frames = samples[: samples.size // frame * frame].reshape(-1, frame)
    if frames.size:
        loud = np.sqrt((frames * frames).mean(axis=1)) > TAIL_SILENCE_RMS
        voiced = np.flatnonzero(loud)
        if voiced.size:
            # Sondan geriye: son ses patlamasının başı ve ondan önceki sessizlik.
            end = voiced[-1]
            start = end
            while start > 0 and loud[start - 1]:
                start -= 1
            gap = 0
            while start - gap - 1 >= 0 and not loud[start - gap - 1]:
                gap += 1
            burst = (end - start + 1) * 0.01
            if gap * 0.01 >= 0.12 and burst <= 0.35 and start - gap > 0:
                cut = (start - gap // 2) * frame
                log(f"kuyruk kesildi ({burst:.2f} sn uydurma ses)")
                samples = samples[:cut]
            else:
                samples = samples[: (end + 1) * frame + frame * 5]
    fade = min(int(rate * 0.02), samples.size)
    if fade:
        samples[-fade:] *= np.linspace(1.0, 0.0, fade)
    return (samples * 32767).astype(np.int16)


def envelope(audio: np.ndarray, rate: int, gain: float = LEVEL_GAIN) -> list[float]:
    """Sesin yüksekliği, LEVEL_STEP saniyelik dilimlerle (0..1): ekrandaki top bununla hareket eder."""
    size = max(int(rate * LEVEL_STEP), 1)
    samples = audio.astype(np.float32) / 32768.0
    levels = []
    for start in range(0, samples.size, size):
        window = samples[start:start + size]
        levels.append(min(1.0, float(np.sqrt(np.mean(window * window))) * gain))
    return levels


def clean_for_speech(text: str) -> str:
    """Markdown ve okunmayacak parçaları (kod, bağlantı, dosya yolu) temizler."""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_#>|]+", " ", text)
    text = re.sub(r"[A-Za-z]:\\[^\s]+|(?<!\w)/(?:Users|home|Applications)/[^\s]+", " ", text)
    # Paragraflar korunur (konuşma paragraf paragraf üretilir); satır içi boşluklar teke iner.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    return text[:800]


def split_chunks(text: str, limit: int = CHUNK_LIMIT) -> list[str]:
    """Konuşulacak parçalar: paragraf paragraf, her parça limit karakteri geçmeden (XTTS Türkçede 226'dan uzununu bozar).
    Uzun paragraf cümle sınırlarından bölünür. Kısa cevaplar tek parça kalır: tonlama baştan sona bağlı akar (cümle
    cümle üretmek her cümlede tonlamayı sıfırlıyor, konuşma mekanik duyuluyordu)."""
    chunks: list[str] = []
    for paragraph in re.split(r"\n\s*\n|\n", text):
        current = ""
        for sentence in re.split(r"(?<=[.!?…])\s+", paragraph.strip()):
            if not sentence:
                continue
            if current and len(current) + 1 + len(sentence) > limit:
                chunks.append(current)
                current = sentence
            else:
                current = f"{current} {sentence}".strip()
        if current:
            chunks.append(current)
    # Parça noktalamayla bitmezse XTTS sonunu kendisi uydurur ("uh" gibi bir ses): nokta eklenir.
    chunks = [c if c[-1] in ".!?…" else c.rstrip(",;:-–") + "." for c in chunks]
    return chunks or [text]
