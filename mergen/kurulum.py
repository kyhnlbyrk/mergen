"""İlk açılış kurulumu: ekrandaki sihirbazın arka ucu. Platform, ekran kartı ve disk alanı kendiliğinden tespit edilir
(kullanıcıya sorulmaz); kullanıcı sadece tercih yapar (yapay zekâ, ses, konuşma tanıma, yetki, aygıtlar). Seçimlere göre
gereken paketler kurulur ve modeller indirilir; ilerleme ekrana canlı yollanır.

Sıra: önce hafif olanlar (Piper sesi, Whisper) iner ve Mergen hemen açılır. Doğal ses (XTTS: PyTorch + model, birkaç GB)
seçildiyse arka planda iner; bitince Mergen o sese geçer. İndirme kesilirse kaldığı yerden sürer (uygulama kapanıp açılsa
da). Bütün modeller Hugging Face'ten veri klasörüne iner (yollar.py)."""
import fnmatch
import importlib
import importlib.util
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import sounddevice as sd

from .ayarlar import SETTINGS, save_settings
from .beyin import BRAINS, COMING_SOON
from .cihazlar import device_name, find_device, list_devices
from .kayit import log
from .kulak import WAKE_MODEL, WHISPER_MODELS
from .ses import PIPER_MODEL, PIPER_REPO, XTTS_IGNORE, XTTS_REPO, boost
from .yollar import DATA, MAC, WINDOWS

GB = 1e9
# Ekranda gösterilen tahmini indirme boyutları (bayt). Kesin boyut indirme başlarken Hugging Face'ten okunur.
SIZES = {
    "piper": 0.065 * GB,
    "xtts": 1.87 * GB,
    "coqui": 0.3 * GB,
    "torch": {"cuda": 3.2 * GB, "mps": 0.8 * GB, "cpu": 0.8 * GB},
    # NVIDIA kartında Whisper'ın istediği CUDA kitaplıkları (PyTorch kurulmayacaksa; kurulacaksa onunla gelir).
    "cuda": 1.0 * GB,
    "whisper": {"small": 0.47 * GB, "medium": 1.53 * GB, "large-v3-turbo": 1.62 * GB},
}
WHISPER_REPOS = {
    "small": "Systran/faster-whisper-small",
    "medium": "Systran/faster-whisper-medium",
    "large-v3-turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
}
# faster-whisper'ın bir modelden indirdiği dosyalar.
WHISPER_FILES = ["config.json", "preprocessor_config.json", "model.bin", "tokenizer.json", "vocabulary.*"]
# PyTorch: NVIDIA ekran kartında CUDA'lı sürüm (RTX 50 serisi CUDA 12.8 ister), Windows'ta ekran kartı yoksa küçük
# işlemci sürümü; macOS'ta PyPI'deki sürüm (Apple Silicon'da MPS'i kendisi destekler).
TORCH_INDEX = {"cuda": "https://download.pytorch.org/whl/cu128", "cpu": "https://download.pytorch.org/whl/cpu"}
DOWNLOAD_ATTEMPTS = 3


class SetupError(Exception):
    """Yeniden denemenin işe yaramayacağı hata (ör. disk dolu)."""


def _run(command: list[str]) -> str:
    try:
        return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
                              creationflags=subprocess.CREATE_NO_WINDOW if WINDOWS else 0).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def detect_hardware() -> dict:
    """İşletim sistemi, ekran kartı (hızlandırma: cuda / mps / cpu) ve veri klasörünün diskindeki boş alan."""
    acceleration, gpu = "cpu", ""
    if MAC:
        if platform.machine() == "arm64":
            acceleration, gpu = "mps", _run(["sysctl", "-n", "machdep.cpu.brand_string"]) or "Apple Silicon"
    else:
        smi = shutil.which("nvidia-smi")
        name = _run([smi, "--query-gpu=name", "--format=csv,noheader"]) if smi else ""
        if name:
            acceleration, gpu = "cuda", name.splitlines()[0].strip()
    if WINDOWS:
        # platform.release() Windows 11'de de "10" diyebiliyor; 22000 ve sonrası derlemeler Windows 11.
        build = int(platform.version().split(".")[-1] or 0) if platform.version().split(".")[-1].isdigit() else 0
        system = "Windows 11" if build >= 22000 else f"Windows {platform.release()}"
    elif MAC:
        system = f"macOS {platform.mac_ver()[0]}"
    else:
        system = platform.system()
    return {"isletim": system, "ekran_karti": gpu, "hizlandirma": acceleration, "bos_alan": shutil.disk_usage(DATA).free}


def installed(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except ModuleNotFoundError:  # üst paket yok ("nvidia.cudnn" için "nvidia")
        return False


def cuda_libraries_needed(hardware: dict, xtts: bool) -> bool:
    """NVIDIA kartı var ama Whisper'ın istediği CUDA kitaplıklarını getirecek PyTorch kurulmayacak: ayrıca indirilir."""
    return hardware["hizlandirma"] == "cuda" and not xtts and not installed("torch") \
        and not (installed("nvidia.cublas") and installed("nvidia.cudnn"))


def _uv() -> str | None:
    found = shutil.which("uv")
    if found:
        return found
    candidate = Path.home() / ".local" / "bin" / ("uv.exe" if WINDOWS else "uv")
    return str(candidate) if candidate.exists() else None


def pip_install(arguments: list[str], report) -> None:
    """Mergen'in kendi Python ortamına paket kurar (uv varsa onunla, hızlı; yoksa pip). Çıktının son satırı ekranda görünür."""
    uv = _uv()
    command = [uv, "pip", "install", "--python", sys.executable] if uv else \
        [sys.executable, "-m", "pip", "install", "--progress-bar", "off", "--disable-pip-version-check"]
    process = subprocess.Popen(command + arguments, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                               encoding="utf-8", errors="replace",
                               creationflags=subprocess.CREATE_NO_WINDOW if WINDOWS else 0)
    tail: list[str] = []
    for line in process.stdout:
        line = line.strip()
        if line:
            tail = (tail + [line])[-20:]
            detail = _package_line(line)
            if detail:
                report(detail=detail)
    if process.wait() != 0:
        log("paket kurulamadı:\n  " + "\n  ".join(tail))
        raise RuntimeError("paket kurulamadı: " + (tail[-1] if tail else "bilinmeyen hata"))
    importlib.invalidate_caches()


def _package_line(line: str) -> str | None:
    """pip / uv çıktısının ekranda gösterilecek Türkçe hâli ("torch indiriliyor (2,5 GB)"); gösterilmeyecekse None."""
    match = re.match(r"(?:Downloading|Collecting)\s+([A-Za-z0-9_.\-]+?)(?:-\d[^\s]*)?(?:\s+\(([\d.]+)\s*(MiB|GiB|MB|GB|kB)\))?$",
                     line)
    if match:
        name, size, unit = match.groups()
        if size:
            gb = float(size) / (1024 if unit in ("MiB", "MB") else 1 if unit in ("GiB", "GB") else 1024 * 1024)
            return f"{name} indiriliyor ({_gb(gb * GB)})"
        return f"{name} indiriliyor"
    if line.startswith(("Installing", "Prepared", "Building")):
        return "Kuruluyor…"
    if line.startswith(("Installed", "Successfully installed")):
        return "Kuruldu"
    return None


def _wanted(name: str, allow: list[str] | None, ignore: list[str] | None) -> bool:
    if allow and not any(fnmatch.fnmatch(name, pattern) for pattern in allow):
        return False
    return not (ignore and any(fnmatch.fnmatch(name, pattern) for pattern in ignore))


def _folder_size(folder: Path) -> int:
    """Hugging Face önbelleğindeki bir modelin diskteki boyutu (yarım inen dosyalar dahil; bağlar sayılmaz)."""
    total = 0
    for path in folder.rglob("*") if folder.exists() else []:
        try:
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
        except OSError:
            pass
    return total


def hf_download(repo: str, report, files: list[str] | None = None, allow: list[str] | None = None,
                ignore: list[str] | None = None) -> None:
    """Hugging Face'ten indirir (files: belirli dosyalar; yoksa allow / ignore süzgeciyle bütün depo). İlerleme önbellek
    klasörünün büyümesinden ölçülür. Yarım kalan indirme kaldığı yerden sürer; inmiş dosyalar yeniden inmez."""
    from huggingface_hub import HfApi, constants, hf_hub_download, snapshot_download

    def fetch(local: bool = False) -> None:
        if files:
            for name in files:
                hf_hub_download(repo, name, local_files_only=local)
        else:
            snapshot_download(repo, allow_patterns=allow, ignore_patterns=ignore, local_files_only=local)

    api = HfApi()
    try:
        if files:
            total = sum(info.size or 0 for info in api.get_paths_info(repo, files))
        else:
            info = api.model_info(repo, files_metadata=True)
            total = sum(s.size or 0 for s in info.siblings if _wanted(s.rfilename, allow, ignore))
    except Exception:
        # İnternet yok: önceden tamamen inmişse yeter.
        fetch(local=True)
        return
    folder = Path(constants.HF_HUB_CACHE) / f"models--{repo.replace('/', '--')}"
    errors: list[Exception] = []
    finished = threading.Event()

    def run() -> None:
        try:
            fetch()
        except Exception as error:
            errors.append(error)
        finally:
            finished.set()

    threading.Thread(target=run, daemon=True).start()
    samples: list[tuple[float, int]] = []
    while not finished.wait(0.5):
        size = min(_folder_size(folder), total)
        now = time.time()
        samples = [(t, s) for t, s in samples if now - t <= 5] + [(now, size)]
        speed = (samples[-1][1] - samples[0][1]) / (samples[-1][0] - samples[0][0]) if len(samples) > 1 else 0.0
        report(done=size, total=total, speed=speed)
    if errors:
        raise errors[0]
    report(done=total, total=total, speed=0.0)


def _gb(size: float) -> str:
    return f"{size / GB:.2f}".replace(".", ",") + " GB" if size >= 0.1 * GB else f"{size / 1e6:.0f} MB"


def _duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f} sn"
    return f"{seconds / 60:.0f} dk".replace(".", ",")


class Setup:
    """Kurulum sihirbazının arka ucu (ekran uçları /kurulum...). İlerleme "kurulum" olaylarıyla ekrana yollanır."""

    def __init__(self, screen) -> None:
        self.screen = screen
        self.hardware = detect_hardware()
        # Mergen'in açılması için gerekenler (Piper, Whisper) hazır.
        self.core_ready = threading.Event()
        if SETTINGS["kurulum_tamam"]:
            self.core_ready.set()
        # Doğal ses arka planda inip kurulunca çağrılır (uygulama.py: Piper'dan XTTS'ye geçer).
        self.on_xtts_ready = None
        # Doğal ses seçildiyse hafif ses hazır olunca kullanıcıya sorulur: hafif (mekanik) sesle hemen mi başlansın, doğal
        # ses inene kadar mı beklensin. Beklenirse Mergen doğal ses inince açılır ve ilk sözünü onunla söyler.
        self.awaiting_choice = False
        self.waited_for_xtts = False
        self.status = "bekliyor"  # bekliyor / kuruluyor / bitti / hata
        self.error = ""
        self.steps: list[dict] = []
        self._thread: threading.Thread | None = None
        self._microphone = None
        self._last_push = 0.0
        routes = screen.routes
        routes[("GET", "/kurulum")] = self.state
        routes[("POST", "/kurulum/beyin")] = lambda body: BRAINS[body.get("ad", "claude")].check()
        routes[("POST", "/kurulum/mikrofon")] = self.test_microphone
        routes[("POST", "/kurulum/hoparlor")] = self.test_speaker
        routes[("POST", "/kurulum/baslat")] = self.start
        routes[("POST", "/kurulum/piper")] = self.fall_back_to_piper
        routes[("POST", "/kurulum/simdi")] = self.open_now
        routes[("POST", "/kurulum/tekrar")] = self.retry
        # Son işi yeniden başlatan işlev ("Tekrar dene") ve bitince ekranın köşesinde gösterilecek yazı.
        self._retry = None
        self.done_message = ""

    # --- Ekranın sordukları ------------------------------------------------------------------------------------

    def state(self) -> dict:
        return {
            "gerekli": not self.core_ready.is_set(),
            "donanim": self.hardware,
            "beyinler": [{"ad": key, "baslik": cls.TITLE} for key, cls in BRAINS.items()]
            + [{"ad": key, "baslik": title, "yakinda": True} for key, title in COMING_SOON.items()],
            "whisper_modeller": WHISPER_MODELS,
            "boyutlar": self.sizes(),
            "mikrofonlar": list_devices(output=False), "mikrofon": device_name(None, output=False),
            "hoparlorler": list_devices(output=True), "hoparlor": device_name(None, output=True),
            "ilerleme": self.progress(),
        }

    def sizes(self) -> dict:
        """Seçeneklerin indirme boyutları (bayt); kurulu paketler sayılmaz."""
        xtts = SIZES["xtts"]
        if not installed("torch"):
            xtts += SIZES["torch"][self.hardware["hizlandirma"]]
        if not installed("TTS"):
            xtts += SIZES["coqui"]
        # Uyanmayı dinleyen hızlı model (kulak.py) her seçimde indirilir.
        whisper = {name: size + (SIZES["whisper"][WAKE_MODEL] if name != WAKE_MODEL else 0)
                   for name, size in SIZES["whisper"].items()}
        return {"piper": SIZES["piper"], "xtts": xtts, "whisper": whisper,
                "cuda": SIZES["cuda"] if cuda_libraries_needed(self.hardware, xtts=False) else 0}

    def progress(self) -> dict:
        background = self.status in ("kuruluyor", "hata") and self.core_ready.is_set()
        return {"durum": self.status, "adimlar": self.steps, "hata": self.error, "arka_plan": background,
                "secim_bekliyor": self.awaiting_choice, "acildi": self.core_ready.is_set(), "mesaj": self.done_message}

    def retry(self, body: dict) -> dict:
        if self._retry and not (self._thread and self._thread.is_alive()):
            self._retry()
        return self.progress()

    def download_whisper(self, name: str, on_ready) -> str:
        """Ayarlardan konuşma tanıma modeli değişti: model inmemişse indirme ekranın köşesinde ilerlemeyle görünür, inince
        on_ready yükler. Başka bir indirme sürüyorsa beklemesi söylenir (dönen uyarı); sorun yoksa boş."""
        if self._thread and self._thread.is_alive():
            return "Şu an başka bir indirme sürüyor; o bitince yeniden seçin."
        step = self._step("whisper_ek", "Konuşma tanıma indiriliyor", background=True)
        self.steps, self.status, self.error = [step], "kuruluyor", ""
        self.done_message = "Konuşma tanıma hazır ✓"
        self._retry = lambda: self.download_whisper(name, on_ready)
        self._whisper_name = name

        def run() -> None:
            try:
                self._do(step)
                on_ready()
                self.status = "bitti"
            except Exception as error:
                log(f"konuşma tanıma indirilemedi: {error!r}")
                step["durum"] = "hata"
                self.status, self.error = "hata", str(error)
            self._push(force=True)

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()
        self._push(force=True)
        return ""

    def test_microphone(self, body: dict) -> dict:
        """Seçilen mikrofonu açar, seviyesini ekrana yollar ("mikseviye"): kullanıcı konuşunca çubuk oynar."""
        self._stop_microphone()
        if body.get("dur"):
            return {}

        def on_audio(data, frames, time_info, status) -> None:
            level = float(np.sqrt(np.mean(np.square(data.astype(np.float32) / 32768.0))))
            self.screen.send({"tip": "mikseviye", "deger": round(min(1.0, level * 8), 3)})

        try:
            self._microphone = sd.InputStream(samplerate=16000, blocksize=1600, channels=1, dtype="int16",
                                              device=find_device(body.get("ad", ""), output=False), callback=on_audio)
            self._microphone.start()
        except sd.PortAudioError as error:
            return {"hata": f"Mikrofon açılamadı: {error}"}
        return {}

    def _stop_microphone(self) -> None:
        if self._microphone is not None:
            self._microphone.stop()
            self._microphone.close()
            self._microphone = None

    def test_speaker(self, body: dict) -> dict:
        """Seçilen hoparlörden kısa bir çan sesi."""
        rate = 22050
        t = np.linspace(0, 0.18, int(rate * 0.18), False)
        fade = np.minimum(1.0, (0.18 - t) * 20)
        tone = np.concatenate([np.sin(2 * np.pi * f * t) * fade for f in (660, 880)]) * 0.3
        device = find_device(body.get("ad", ""), output=True)
        threading.Thread(target=lambda: sd.play(boost((tone * 32767).astype(np.int16), 1.0), rate, device=device),
                         daemon=True).start()
        return {}

    # --- Kurulum -----------------------------------------------------------------------------------------------

    def start(self, choices: dict) -> dict:
        """Seçimleri kaydeder ve kurulumu arka planda başlatır (yarım kalmışsa kaldığı yerden sürdürür)."""
        if self._thread and self._thread.is_alive():
            return self.progress()
        # Verilmeyen seçim kayıtlı ayardan gelir ("Tekrar dene" ve yarım kalan kurulumu sürdürme boş gönderir).
        choices = {key: choices.get(key, SETTINGS[key]) for key in
                   ("beyin", "ses_motoru", "xtts_lisans", "whisper_model", "tam_yetki", "mikrofon", "hoparlor")}
        xtts = choices["ses_motoru"] == "xtts"
        if xtts and not choices["xtts_lisans"]:
            return {"hata": "Doğal ses için lisansı kabul etmeniz gerekiyor."}
        SETTINGS.update(choices)
        if SETTINGS["whisper_model"] not in WHISPER_REPOS:
            SETTINGS["whisper_model"] = "small"
        save_settings()
        self.steps = [self._step("alan", "Diskte yeterli yer olup olmadığına bakılıyor")]
        if not installed("piper"):
            self.steps.append(self._step("piper_paket", "Hafif ses için gerekli yazılım kuruluyor"))
        self.steps += [self._step("piper", "Hafif ses indiriliyor"),
                       self._step("whisper", "Konuşma tanıma indiriliyor")]
        if cuda_libraries_needed(self.hardware, xtts):
            self.steps.append(self._step("cuda", "Konuşma tanıma ekran kartı için hazırlanıyor"))
        if xtts:
            if not installed("torch"):
                self.steps.append(self._step("torch", "Doğal ses için gerekli yazılım kuruluyor (1/2)", background=True))
            if not installed("TTS") or not installed("torchcodec"):
                self.steps.append(self._step("coqui", "Doğal ses için gerekli yazılım kuruluyor (2/2)", background=True))
            self.steps.append(self._step("xtts", "Doğal ses indiriliyor", background=True))
        self.status, self.error = "kuruluyor", ""
        self.done_message = "Doğal ses hazır ✓" if xtts else ""
        self._retry = lambda: self.start({})
        log(f"kurulum başladı: {SETTINGS['beyin']}, ses {SETTINGS['ses_motoru']}, whisper {SETTINGS['whisper_model']}, "
            f"{'tam yetki' if SETTINGS['tam_yetki'] else 'sınırlı'}, {self.hardware}")
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._push(force=True)
        return self.progress()

    def resume_background(self) -> None:
        """Önceki açılışta doğal ses inerken Mergen kapandıysa kaldığı yerden sürdürür."""
        if self._thread and self._thread.is_alive():
            return  # sihirbazdan başlayan kurulum zaten sürüyor
        if SETTINGS["kurulum_tamam"] and SETTINGS["ses_motoru"] == "xtts" and not SETTINGS["xtts_kurulu"]:
            log("doğal ses kurulumu sürdürülüyor")
            self.start({})

    def fall_back_to_piper(self, body: dict) -> dict:
        """Doğal ses kurulamadı: Piper'la devam (ayarlardan sonra yeniden denenebilir)."""
        SETTINGS["ses_motoru"] = "piper"
        save_settings()
        self.status, self.error = "bitti", ""
        if not self.core_ready.is_set():
            self._open()  # doğal ses beklenirken kurulamadı: Mergen hafif sesle açılır
        self._push(force=True)
        return self.progress()

    def open_now(self, body: dict) -> dict:
        """Kullanıcı doğal sesi beklemek istemedi: Mergen hafif sesle hemen açılır, doğal ses arka planda iner."""
        if not self.core_ready.is_set():
            self._open()
        return self.progress()

    @staticmethod
    def _step(key: str, title: str, background: bool = False) -> dict:
        return {"id": key, "ad": title, "durum": "bekliyor", "yuzde": None, "detay": "", "arka_plan": background}

    def _run(self) -> None:
        current = None
        try:
            for step in self.steps:
                current = step
                if step["arka_plan"] and not self.core_ready.is_set() and not self.awaiting_choice:
                    self._core_done(ask=True)
                self._do(step)
            if not self.core_ready.is_set() and not self.awaiting_choice:
                self._core_done()
            if SETTINGS["ses_motoru"] == "xtts" and not SETTINGS["xtts_kurulu"]:
                SETTINGS["xtts_kurulu"] = True
                save_settings()
                log("kurulum: doğal ses hazır")
                if not self.core_ready.is_set():
                    # Kullanıcı doğal sesi bekledi: Mergen şimdi açılır, ilk sözünü doğal sesle söyler (uygulama.py).
                    self.waited_for_xtts = True
                    self._open()
                elif self.on_xtts_ready:
                    self.on_xtts_ready()
            self.status = "bitti"
        except Exception as error:
            log(f"kurulum hatası ({current['id'] if current else '?'}): {error!r}")
            if current:
                current["durum"] = "hata"
            self.status, self.error = "hata", str(error)
        self._push(force=True)

    def _core_done(self, ask: bool = False) -> None:
        """Mergen'in açılması için gerekenler (Piper, Whisper) hazır. Doğal ses hâlâ iniyorsa (ask) kullanıcıya sorulur:
        hafif sesle hemen mi başlansın (open_now), doğal ses inene kadar mı beklensin. Yoksa Mergen hemen açılır."""
        self._stop_microphone()
        if ask:
            self.awaiting_choice = True
            log("kurulum: hafif ses hazır, doğal sesi bekleyip beklemeyeceği soruluyor")
            self._push(force=True)
        else:
            self._open()

    def _open(self) -> None:
        # Kurulum ancak Mergen açılınca tamam sayılır: seçim beklenirken kapatılırsa sihirbaz bir sonraki açılışta yeniden
        # çıkar (inmiş olanlar yeniden inmez).
        SETTINGS["kurulum_tamam"] = True
        save_settings()
        self.awaiting_choice = False
        log("kurulum: Mergen açılıyor")
        self.core_ready.set()
        self._push(force=True)

    def _do(self, step: dict) -> None:
        step["durum"] = "suruyor"
        # Yüzdesi bilinmeyen adımlarda (paket kurulumu) ekran geçen süreyi gösterir.
        step["basladi"] = time.time()
        self._push(force=True)
        action = getattr(self, f"_install_{step['id']}")
        for attempt in range(DOWNLOAD_ATTEMPTS):
            try:
                action(lambda **values: self._report(step, **values))
                break
            except SetupError:
                raise
            except Exception as error:
                if attempt == DOWNLOAD_ATTEMPTS - 1:
                    raise
                log(f"kurulum ({step['id']}) yeniden deneniyor: {error!r}")
                step["detay"] = "Bağlantı koptu, yeniden deniyorum…"
                self._push(force=True)
                time.sleep(3 * (attempt + 1))
        step["durum"], step["yuzde"], step["detay"] = "bitti", 100, ""
        self._push(force=True)

    def _report(self, step: dict, done: float = None, total: float = None, speed: float = 0.0, detail: str = None) -> None:
        if total:
            step["yuzde"] = round(done / total * 100, 1)
            text = f"{_gb(done)} / {_gb(total)}"
            if speed > 0 and done < total:
                text += f" · {speed / 1e6:.1f} MB/sn · ~{_duration((total - done) / speed)} kaldı".replace(".", ",", 1)
            step["detay"] = text
        if detail is not None:
            step["detay"] = detail
        self._push()

    def _push(self, force: bool = False) -> None:
        now = time.time()
        if force or now - self._last_push >= 0.25:
            self._last_push = now
            self.screen.send({"tip": "kurulum", **self.progress()})

    # --- Adımlar -------------------------------------------------------------------------------------------------

    def _install_alan(self, report) -> None:
        need = self.sizes()["piper"] + self.sizes()["whisper"][SETTINGS["whisper_model"]]
        if cuda_libraries_needed(self.hardware, SETTINGS["ses_motoru"] == "xtts"):
            need += SIZES["cuda"]
        if SETTINGS["ses_motoru"] == "xtts" and not SETTINGS["xtts_kurulu"]:
            need += self.sizes()["xtts"]
        free = shutil.disk_usage(DATA).free
        self.hardware["bos_alan"] = free
        if free < need + 0.5 * GB:
            raise SetupError(f"Diskte yeterli yer yok: {_gb(need)} gerekiyor, {_gb(free)} boş.")
        report(detail=f"{_gb(need)} yer gerekiyor, diskte {_gb(free)} boş")

    def _install_piper_paket(self, report) -> None:
        pip_install(["piper-tts>=1.3"], report)

    def _install_piper(self, report) -> None:
        hf_download(PIPER_REPO, report, files=[PIPER_MODEL, PIPER_MODEL + ".json"])

    def _install_whisper_ek(self, report) -> None:
        hf_download(WHISPER_REPOS[self._whisper_name], report, allow=WHISPER_FILES)

    def _install_whisper(self, report) -> None:
        if SETTINGS["whisper_model"] != WAKE_MODEL:
            hf_download(WHISPER_REPOS[WAKE_MODEL], report, allow=WHISPER_FILES)
        hf_download(WHISPER_REPOS[SETTINGS["whisper_model"]], report, allow=WHISPER_FILES)

    def _install_cuda(self, report) -> None:
        pip_install(["nvidia-cublas-cu12", "nvidia-cudnn-cu12>=9,<10"], report)

    def _install_torch(self, report) -> None:
        index = TORCH_INDEX.get(self.hardware["hizlandirma"]) if not MAC else None
        pip_install(["torch", "torchaudio"] + (["--index-url", index] if index else []), report)

    def _install_coqui(self, report) -> None:
        # PyTorch 2.9'dan beri coqui açılırken torchcodec paketinin kurulu olmasını istiyor (yoksa XTTS açılmıyor, Mac'te
        # 2026-10-27). Kendisi kullanılmaz: ses dosyası okuma ses.py'deki _load_wav_tensor'la yapılır (FFmpeg istemez).
        pip_install(["coqui-tts>=0.27", "torchcodec"], report)

    def _install_xtts(self, report) -> None:
        hf_download(XTTS_REPO, report, ignore=XTTS_IGNORE)
