"""Mergen'in ekranı: yerel bir sunucu (sadece bu bilgisayar, 127.0.0.1) arayuz.html'i sunar ve olayları canlı yollar
(Server-Sent Events): durum (uyku / dinliyor / düşünüyor / konuşuyor), ses seviyesi (topun hareketi) ve mesajlar.
Ekran Mergen'in kendi penceresinde gösterilir (pencere.py); o açılamazsa tarayıcıda (Edge ya da Chrome --app, ikisi de
yoksa varsayılan tarayıcı)."""
import json
import queue
import shutil
import socket
import subprocess
import threading
import time
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .yollar import MAC, PACKAGE, WINDOWS

PAGE = PACKAGE / "arayuz.html"
SAMPLES = PACKAGE / "ornekler"
PORT = 8765
URL = f"http://127.0.0.1:{PORT}/"
if WINDOWS:
    APP_BROWSERS = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    ]
elif MAC:
    APP_BROWSERS = [
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
    ]
else:
    APP_BROWSERS = []


class Screen:
    """Olayları bağlı bütün sayfalara yollar. Konuşurken ses seviyeleri çalma saatine göre zamanlanır."""

    def __init__(self) -> None:
        self._clients: list[queue.Queue] = []
        self._lock = threading.Lock()
        self._levels: list[tuple[float, float]] = []  # (çalınacağı an, seviye)
        self._history: list[dict] = []  # sonradan açılan sayfa da konuşmayı görsün
        # Açılışta kütüphaneler yüklenirken "hazırlanıyor"; sonra ana döngü uyku / dinliyor / ... diye değiştirir.
        self.state = "hazirlaniyor"
        # Sayfanın çağırdığı uçlar: {("GET" | "POST", "/yol"): işlev}. İşlev POST'ta gövdeyi (JSON) alır, JSON döndürür.
        # Ayarlar paneli (uygulama.py) ve kurulum sihirbazı (kurulum.py) buraya kaydolur.
        self.routes: dict[tuple[str, str], object] = {}
        # Ekrandaki "Kapat" düğmesine basılınca çağrılır (Mergen'i tamamen kapatır).
        self.on_shutdown = None
        # Mergen ikinci kez açılmak istenince çağrılır: kendi penceresi öne gelir (pencere.py).
        self.on_focus = None
        self.routes[("POST", "/one")] = lambda body: self.on_focus() if self.on_focus else Screen.open()
        screen = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:
                pass

            def do_POST(self) -> None:
                path = self.path.split("?")[0]
                if path == "/kapat" and screen.on_shutdown:
                    self.send_response(204)
                    self.end_headers()
                    threading.Thread(target=screen.on_shutdown, daemon=True).start()
                    return
                route = screen.routes.get(("POST", path))
                if route:
                    length = int(self.headers.get("Content-Length", 0))
                    self._json(route(json.loads(self.rfile.read(length) or b"{}")))
                    return
                self.send_response(404)
                self.end_headers()

            def _json(self, data) -> None:
                self._send(json.dumps(data or {}, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

            def _send(self, body: bytes, content_type: str) -> None:
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:
                path = self.path.split("?")[0]
                if path == "/olaylar":
                    screen._serve_events(self)
                    return
                route = screen.routes.get(("GET", path))
                if route:
                    self._json(route())
                    return
                if path.startswith("/ornek/"):
                    # Kurulumda dinletilen ses örnekleri.
                    sample = SAMPLES / Path(path).name
                    if sample.is_file():
                        self._send(sample.read_bytes(), "audio/mpeg")
                        return
                    self.send_response(404)
                    self.end_headers()
                    return
                self._send(PAGE.read_bytes(), "text/html; charset=utf-8")

        self.server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        threading.Thread(target=self._meter, daemon=True).start()

    # --- Mergen'in çağırdıkları ---------------------------------------------------------------------------------

    @staticmethod
    def already_running() -> bool:
        """Mergen zaten açık mı (ekran sunucusu cevap veriyor mu)."""
        try:
            with socket.create_connection(("127.0.0.1", PORT), timeout=0.5):
                return True
        except OSError:
            return False

    @staticmethod
    def bring_to_front() -> None:
        """Açık Mergen'in penceresini öne getirir (yoksa ekranı tarayıcıda açar)."""
        try:
            request = urllib.request.Request(URL + "one", data=b"{}", method="POST")
            urllib.request.urlopen(request, timeout=3)
        except OSError:
            Screen.open()

    @property
    def url(self) -> str:
        return URL

    @staticmethod
    def open() -> None:
        """Ekranı tarayıcı penceresinde açar (kendi penceresi açılamadığında; pencere.py)."""
        url = URL
        browser = next((p for p in APP_BROWSERS if p.exists()), None) or shutil.which("msedge") \
            or shutil.which("google-chrome") or shutil.which("chromium")
        if browser:
            subprocess.Popen([str(browser), f"--app={url}", "--window-size=1100,720"])
        else:
            webbrowser.open(url)

    def set_state(self, state: str) -> None:
        self.state = state
        self._send({"tip": "durum", "durum": state})

    def message(self, who: str, text: str) -> None:
        event = {"tip": "mesaj", "kim": who, "metin": text, "zaman": time.strftime("%H:%M")}
        self._history = (self._history + [event])[-60:]
        self._send(event)

    def clear_levels(self) -> None:
        """Konuşma kesildi: sırada bekleyen ses seviyeleri atılır (top hemen durulsun)."""
        with self._lock:
            self._levels.clear()

    def interrupt(self) -> None:
        """Sözü kesildi: son Mergen mesajı ekranda işaretlenir."""
        for event in reversed(self._history):
            if event["kim"] == "mergen":
                event["kesildi"] = True
                break
        self._send({"tip": "kesildi"})

    def schedule_levels(self, start: float, levels: list[float], step: float) -> None:
        """Konuşma sesi: her seviye çalındığı anda gönderilir (start + i * step)."""
        with self._lock:
            self._levels.extend((start + i * step, level) for i, level in enumerate(levels))

    # --- İç ---------------------------------------------------------------------------------------------------

    def _meter(self) -> None:
        while True:
            now = time.time()
            due = None
            with self._lock:
                while self._levels and self._levels[0][0] <= now:
                    due = self._levels.pop(0)[1]
            if due is not None:
                self._send({"tip": "seviye", "deger": round(due, 3), "kaynak": "ses"})
            time.sleep(1 / 60)

    def send(self, event: dict) -> None:
        """Olayı bağlı bütün sayfalara yollar (kurulum ilerlemesi, mikrofon seviyesi gibi)."""
        self._send(event)

    def _send(self, event: dict) -> None:
        data = f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8")
        with self._lock:
            for client in self._clients:
                client.put(data)

    def _serve_events(self, handler: BaseHTTPRequestHandler) -> None:
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
        handler.send_header("Cache-Control", "no-cache")
        handler.end_headers()
        inbox: queue.Queue = queue.Queue()
        with self._lock:
            self._clients.append(inbox)
        try:
            inbox.put(f"data: {json.dumps({'tip': 'durum', 'durum': self.state})}\n\n".encode())
            for event in self._history:
                # Geçmiş mesajlar sayfada anında, tam hâliyle görünür (harf harf yazılmaz).
                old = dict(event, gecmis=True)
                inbox.put(f"data: {json.dumps(old, ensure_ascii=False)}\n\n".encode("utf-8"))
            while True:
                try:
                    data = inbox.get(timeout=15)
                except queue.Empty:
                    data = b": canli\n\n"  # bağlantı açık kalsın
                handler.wfile.write(data)
                handler.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass
        finally:
            with self._lock:
                if inbox in self._clients:
                    self._clients.remove(inbox)
