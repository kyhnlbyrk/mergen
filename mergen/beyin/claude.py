"""Claude: Claude Code komut satırı (claude), kullanıcının Claude aboneliğiyle. Kalıcı süreç: Mergen açılırken bir kez
başlar, sorular stream-json ile gönderilir (her soruda baştan açılmanın ~4 sn'si kalkar). Aynı oturum sürer (önceki
konuşmayı hatırlar); model, efor ya da yetki değişince, süreç kapanınca ya da hata olunca oturum korunarak yeniden başlar."""
import json
import subprocess
import threading
from pathlib import Path

from ..ayarlar import SETTINGS
from ..kayit import log
from ..kisilik import system_prompt
from ..yollar import BRAIN_LOG, WINDOWS
from .temel import Brain, find_executable


class ClaudeBrain(Brain):
    TITLE = "Claude (Claude Code)"
    MODELS = {
        "": "Varsayılan (hesabın modeli)",
        "haiku": "Haiku — en hızlı",
        "sonnet": "Sonnet — dengeli",
        "opus": "Opus — en güçlü",
    }
    EFFORTS = {"low": "Düşük — en hızlı", "medium": "Orta", "high": "Yüksek", "xhigh": "Çok yüksek",
               "max": "En derin — en yavaş"}

    @classmethod
    def check(cls) -> dict:
        result = {
            "bulundu": False, "giris": False, "hesap": "",
            "kurulum": "irm https://claude.ai/install.ps1 | iex" if WINDOWS else "curl -fsSL https://claude.ai/install.sh | bash",
            "kabuk": "PowerShell" if WINDOWS else "Terminal",
            "giris_komutu": "claude auth login",
        }
        executable = find_executable("claude")
        if executable is None:
            return result
        result["bulundu"] = True
        try:
            status = subprocess.run([str(executable), "auth", "status"], capture_output=True, text=True, encoding="utf-8",
                                    timeout=30, creationflags=subprocess.CREATE_NO_WINDOW if WINDOWS else 0)
            info = json.loads(status.stdout)
            result["giris"] = bool(info.get("loggedIn"))
            result["hesap"] = info.get("email") or ""
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            log(f"claude giriş durumu okunamadı: {error!r}")
        return result

    def __init__(self) -> None:
        self.session = None
        self.process: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._errors = open(BRAIN_LOG, "a", encoding="utf-8", buffering=1)

    def start(self) -> None:
        with self._lock:
            if not self._alive():
                self._start()

    def _alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def _start(self) -> None:
        executable = find_executable("claude")
        if executable is None:
            raise OSError("Claude Code bulunamadı")
        command = [
            str(executable), "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
            # Kişilik süreç başlarken eklenir: Claude Code çalışma klasörü dışındaki talimat dosyalarını yüklemiyor.
            "--append-system-prompt", system_prompt(),
        ]
        for folder in SETTINGS["ek_klasorler"]:
            command += ["--add-dir", folder]
        effort = SETTINGS["efor"] if SETTINGS["efor"] in self.EFFORTS else "low"
        command += ["--effort", effort]
        if SETTINGS["tam_yetki"]:
            command.append("--dangerously-skip-permissions")
        if SETTINGS["model"] in self.MODELS and SETTINGS["model"]:
            command += ["--model", SETTINGS["model"]]
        if self.session:
            command += ["--resume", self.session]
        log(f"claude başlıyor (model {SETTINGS['model'] or 'varsayılan'}, efor {effort}, "
            f"{'tam yetki' if SETTINGS['tam_yetki'] else 'sınırlı'})")
        self.process = subprocess.Popen(command, cwd=SETTINGS["calisma_klasoru"] or Path.home(), stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=self._errors, text=True, encoding="utf-8",
                                        creationflags=subprocess.CREATE_NO_WINDOW if WINDOWS else 0)

    def ask(self, text: str) -> str:
        log(f"soruyor: {text}")
        with self._lock:
            for attempt in range(2):
                try:
                    if not self._alive():
                        self._start()
                    message = {"type": "user", "message": {"role": "user", "content": text}}
                    self.process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
                    self.process.stdin.flush()
                    while True:
                        line = self.process.stdout.readline()
                        if not line:
                            raise OSError("claude süreci kapandı")
                        event = json.loads(line)
                        if event.get("session_id"):
                            self.session = event["session_id"]
                        if event.get("type") == "result":
                            if event.get("is_error"):
                                log(f"claude hatası: {str(event.get('result'))[:300]}")
                            return event.get("result") or "Tamamdır beyim."
                except (OSError, ValueError) as error:
                    log(f"claude bağlantısı koptu ({error}), yeniden başlıyor")
                    self._stop()
            return "Korkarım bir sorun var beyim, Claude'a bağlanamadım."

    def _stop(self) -> None:
        if self.process is not None:
            try:
                self.process.kill()
            except OSError:
                pass
        self.process = None

    def restart(self) -> None:
        with self._lock:
            self._stop()
        threading.Thread(target=self.start, daemon=True).start()

    def reset(self) -> None:
        self.session = None
        self.restart()
