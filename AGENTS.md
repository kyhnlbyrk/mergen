# AGENTS.md: Mergen için teknik kılavuz

Bu dosya Mergen üzerinde çalışan yapay zekâ ajanları (ve kodu derinlemesine öğrenmek isteyen geliştiriciler) içindir:
projenin ne olduğu, nasıl çalıştığı, nerede ne olduğu ve alınmış kararların gerekçeleri. Katkı süreci için
[CONTRIBUTING.md](CONTRIBUTING.md), kullanıcı belgesi için [README.md](README.md).

Bir kararı değiştirmeden önce buradaki gerekçesini okuyun; çoğu, denenip başarısız olmuş bir yolun sonucu. Yeni bir
teknik karar aldığınızda ya da bir tuzağa düştüğünüzde buraya ekleyin.

## Proje

Mergen, Türkçe konuşan, anahtar sözcükle uyanan, eller serbest bir sesli asistan (Iron Man'deki JARVIS tarzı). Hedef
kitle teknik olmayan son kullanıcı. Sabit ilkeler:

- **Sadece Türkçe.** Adı Mergen; kullanıcıya "beyim" der, "siz" diye konuşur.
- **API anahtarı yok.** Beyin, kullanıcının aboneliğiyle giriş yaptığı resmi komut satırı aracıdır (şimdilik Claude
  Code; Codex ve Gemini "yakında").
- **Ses yerelde.** Konuşma tanıma (Whisper) ve ses (XTTS / Piper) kullanıcının bilgisayarında çalışır; buluta yalnızca
  söylenenin yazılı hâli gider.
- **Windows ve macOS.** Linux "çalışırsa çalışır" düzeyinde (pencere yerine tarayıcı).
- **Kullanıcıya teknik soru sorulmaz.** Platform, ekran kartı, disk kendiliğinden tespit edilir; kullanıcı yalnızca
  tercih yapar.

## Akış

```
mikrofon (sounddevice, 16 kHz, 0,25 sn'lik parçalar)
  → konuşma başı/sonu: ses yüksekliği eşiği (kulak.py, yapay zekâ yok)
  → Whisper (faster-whisper) ile yazıya çevirme
  → uykudaysa "uyan" geçiyor mu? (uyanma her zaman "small" modelle)
  → beyin: kalıcı Claude Code süreci (stream-json)
  → ses: XTTS v2 (akışla, paragraf paragraf) ya da Piper
  → hoparlör; ekranda top ve konuşma akışı (yerel HTTP + SSE)
```

## Dosyalar

| Dosya | Ne |
|---|---|
| `mergen/__main__.py` | Giriş noktası. Ekranı (Screen) ağır kütüphanelerden önce açar; tek kopya denetimi (ikinci açılış ilkini öne getirir); pencereyi ana iş parçacığında çalıştırır, Mergen'i ayrı iş parçacığında. |
| `mergen/pencere.py` | Mergen'in kendi penceresi (pywebview: Windows'ta WebView2, macOS'ta WebKit). macOS'ta Dock'ta ve Cmd+Tab'da "Mergen" görünsün diye uygulama kimliği ayarlanır. |
| `mergen/arayuz.py` | `Screen`: `127.0.0.1:8765`'te yerel HTTP sunucusu. `routes` sözlüğü (`{("GET"/"POST", "/yol"): işlev}`), SSE `/olaylar` (olaylar: `durum`, `mesaj`, `kesildi`, `seviye`, `kurulum`, `mikseviye`), bilinmeyen yollara 404. |
| `mergen/arayuz.html` | Ekranın tamamı (tek dosya): top, konuşma akışı, ayarlar paneli, ilk açılış sihirbazı, köşedeki arka plan indirme göstergesi. JS adları Türkçe. |
| `mergen/uygulama.py` | `main`: açılış sırası, ana döngü (uyku → uyanma → sohbet), sesli komutlar, `connect_settings` (ayarlar panelinin GET/POST `/ayarlar`'ı). |
| `mergen/kurulum.py` | `Setup`: donanım tespiti, sihirbazın uçları (`/kurulum/...`), indirme adımları ve ilerleme, arka plan indirmeleri (doğal ses, sonradan seçilen konuşma tanıma). |
| `mergen/kulak.py` | `Ears`: mikrofon, uyanma, dinleme, Whisper yükleme (CUDA varsa ekran kartında), uydurma altyazı süzgeci; `BargeDetector` (söz kesme). |
| `mergen/ses.py` | `XttsEngine`, `PiperEngine`, `Voice` (akışla konuşma, söz kesilince susma, Piper → XTTS geçişi, konuşmacı seçimi). |
| `mergen/beyin/` | Yapay zekâ bağlantıları: `temel.py` (`Brain` arayüzü, `find_executable`), `claude.py`, `__init__.py` (`BRAINS`, `COMING_SOON`). |
| `mergen/kisilik.py` | Sistem istemi: karakter, platforma göre bilgisayarı kullanma bilgisi, sınırlı mod notu, kullanıcının notları. |
| `mergen/ayarlar.py` | `DEFAULTS` ve `SETTINGS` (veri klasöründeki `ayar.json`, BOM'suz yazılır). Her anahtarın anlamı orada yorumlu. |
| `mergen/cihazlar.py` | Ses aygıtları (Windows'ta MME, macOS'ta Core Audio), ad parçasıyla bulma, aygıt listesini tazeleme. |
| `mergen/yollar.py` | Platform ve klasörler; `HF_HOME` ve `HF_HUB_DISABLE_XET` burada ayarlanır. |
| `mergen/kayit.py` | `log()`: veri klasöründeki `mergen.log`. |
| `mergen/araclar/` | `medya.ps1` (Windows'ta Spotify ve medya tuşları), simgeler. |
| `mergen/ornekler/` | Sihirbazdaki "Dinle" düğmesinin ses örnekleri. |
| `install.ps1` | Windows kurulumunun ASCII yükleyicisi: `kurulum.ps1`'i bayt olarak indirip UTF-8 diye çalıştırır. |
| `kurulum.ps1` | Windows kurulumu (BOM'lu UTF-8). |
| `install.sh` | macOS (ve Linux) kurulumu; `~/Applications/Mergen.app` oluşturur. |

## Veri klasörü

Kullanıcıya ait her şey tek klasörde; Mergen kaldırılınca sistemde iz kalmaz:

- Windows `%LOCALAPPDATA%\Mergen`, macOS `~/Library/Application Support/Mergen`, Linux `~/.local/share/mergen`
- `MERGEN_HOME` ortam değişkeni verilirse o klasör (geliştirme ve deneme için; boş klasör = ilk açılış sihirbazı).
- İçinde: `uygulama/.venv` (kurulum betiğinin Python ortamı), `modeller/` (Hugging Face önbelleği dahil), `ayar.json`,
  `notlar.md` (Mergen'in kalıcı notları; sistem istemine eklenir), `mergen.log`, `konsol.log` (pencere modunda stdout),
  `beyin.log` (Claude sürecinin stderr'i).

## Teknik kararlar ve gerekçeleri

### Kurulum

- **Kurulum son yayımlanmış sürümü indirir, `main`'i değil.** `install.ps1` / `install.sh` GitHub API'sinden
  (`releases/latest`) sürüm etiketini alır; yoksa `main`'e düşer. `MERGEN_SURUM` ile belirli bir sürüm ya da dal
  verilebilir. Böylece `main`'e gönderilen yarım bir değişiklik kullanıcılara gitmez. Sürüm yayımlamak: `pyproject.toml`'daki
  ve `install.sh`'taki (Info.plist) sürüm numarasını artırıp GitHub'da yeni bir Release açın (etiket `vX.Y.Z`).
  Dikkat: `install.ps1` ve `install.sh`'ın kendisi hâlâ `main`'den gelir; bu iki dosyadaki değişiklik anında herkese
  ulaşır.

- **Terminal betiği soru sormaz; tercihleri ilk açılıştaki sihirbaz sorar.** Teknik olmayan kullanıcı için terminalde
  soru-cevap kötü bir deneyim.
- **uv + Python 3.12, ortam veri klasöründe.** Kullanıcının sistem Python'una dokunulmaz; Python kurulu olmasa da olur.
- **`install.ps1` ASCII, asıl betik `kurulum.ps1`.** `irm | iex`, dosyanın başındaki BOM'u metinde bırakıyor; ilk
  satır yorum sayılmıyor ve betik ayrıştırılamıyordu. BOM'suz olunca da PowerShell 5.1 yerel dosyadaki Türkçe
  harfleri bozuyor. Bu yüzden yükleyici ASCII, asıl betik BOM'lu ve yükleyici onu BOM'u atarak çalıştırıyor.
- **Uzun adımlarda canlı satır (dönen işaret, süre, ağdan inen MB), yüzde yok.** uv toplam ilerleme vermiyor; tahmini
  yüzde yanıltıcı. MB ağ sayacından: uv paketleri önce önbelleğe indirip ortama en sonda kopyaladığı için ortamın boyutu
  dakikalarca yerinde sayıyordu.
- **Modeller Hugging Face'ten veri klasörüne iner, Xet kapalı (`HF_HUB_DISABLE_XET=1`).** Xet indiricisi dosyayı ayrı
  bir önbellekte toplayıp en sonda taşıyor; ilerleme ölçülemiyordu. Düz HTTP'de yarım dosya model klasöründe büyür ve
  kesilirse kaldığı yerden sürer.
- **Mergen önce hafif sesle (Piper) açılır, doğal ses (XTTS) arka planda iner ve yüklenir.** Açılış XTTS'yi beklerse
  pencere dakikalarca "hazırlanıyor" kalıyordu. İlk kurulumda kullanıcıya "doğal sesi bekle / hafif sesle başla" sorulur.
- **NVIDIA kartı varsa ama PyTorch kurulmayacaksa** (doğal ses seçilmediyse) Whisper'ın istediği CUDA kitaplıkları
  `nvidia-cublas-cu12` / `nvidia-cudnn-cu12` paketleriyle ayrıca kurulur.
- **XTTS için `torchcodec` kurulur.** PyTorch 2.9'dan beri coqui açılırken kurulu olmasını istiyor (kullanılmıyor;
  kayıtları `_load_wav_tensor` yamasıyla `wave` modülü okuyor). Eksikse Mac'te doğal ses hiç açılmıyordu.
- **XTTS lisansı (CPML, ticari olmayan kullanım) sihirbazda kullanıcıya onaylatılır;** model Mergen'le dağıtılmaz.

### Pencere

- **Mergen'in kendi penceresi (pywebview).** macOS'ta tarayıcı penceresi öne gelmiyor, Dock simgesi zıplıyordu;
  kullanıcı uygulamanın Dock'ta ve Cmd+Tab'da gerçek uygulama gibi görünmesini istedi (Dock'tan gizlemek reddedildi).
  pywebview ana iş parçacığında çalışmak zorunda; Mergen ayrı iş parçacığında. Linux'ta tarayıcıya düşer.
- **Tek kopya:** ikinci açılış `POST /one` ile ilk pencereyi öne getirir ve çıkar.
- **Ekran açılmadan önce sunucu `hazirlaniyor` durumunda;** hazır olmayan uçlar 404 döner, sayfa hata alınca yeniden
  dener (Mac'te sayfa HTML'i JSON sanıp "hazırlanıyor"da takılıyordu).

### Konuşma tanıma (Whisper)

- **Uyanma her zaman "small" ile dinlenir,** sohbet seçilen modelle. Uykudayken duyulan her ses yazıya çevriliyor;
  büyük model bunu yetiştiremeyince "Mergen uyan" geç algılanıyordu.
- **Ekran kartında yalnızca CUDA kitaplıkları varsa** (PyTorch'un CUDA'lısı ya da nvidia pip paketleri). Kitaplıklar
  yokken CUDA'da açılan Whisper takılıyordu. Açılışta bir ısınma çevirisi yapılır; sonuç tembel üretildiği için
  `list(segments)` ile tüketilmeli, yoksa ısınma hiç çalışmıyor.
- **Mac'te Whisper işlemcide.** faster-whisper (CTranslate2) Apple çipinin grafik kısmını kullanamıyor; "En doğru" model
  Mac'te her cümleye birkaç saniye ekliyor. Bu yüzden öneri donanıma göre: NVIDIA'da "En doğru", Mac'te ve kartsız
  bilgisayarda "Hızlı" (`arayuz.html` → `tanimaRehberi`). Düşünülen çözüm: Mac'te MLX tabanlı Whisper.
- **Teknik kelimeler `hotwords` ile** verilir (`BASE_WORDS` + kullanıcının "özel kelimeler"i).
- **Uydurma altyazı süzgeci:** Whisper sessizlikte "İzlediğiniz için teşekkürler" gibi YouTube altyazıları uyduruyor;
  kısa ve bu kalıba uyan metinler atılır (`HALLUCINATION`).
- **Şarkı sözü ve başka dil süzgeci** (`Ears._is_speech_for_us`): müzik çalarken şarkı sözleri kullanıcının konuşması
  sanılıyordu. Harfsiz ya da tek harfli çıktılar ("...", "G- G- G-") atılır. Türkçe harf içermeyen metinlerde sesin dili
  hızlı modelle tespit edilir; başka bir dil %80'in üstünde ve Türkçe %5'in altındaysa atılır. Eşik yüksek, çünkü kısa
  ya da İngilizce kelimeli Türkçe de şaşırtıyor ("Evet." %40 İngilizce çıktı). Türkçe şarkı sözlerini ayıramaz.
- **Konuşma bitti beklemesi** 1,6 sn (panelden 0,6-4). Cümle bağlaç ya da virgülle bitiyorsa 3 sn daha beklenir.

### Ses

- **XTTS v2, hazır konuşmacı "Damien Black"** (58 konuşmacıdan seçildi; panelden değiştirilebilir).
- **Paragraf paragraf (≤220 karakter; Türkçe sınır 226) + akış.** Cümle cümle üretim mekanik konuşuyordu. Parça sonuna
  noktalama zorlanır; `trim_tail` kuyruktaki uydurma "uh" sesini keser; 0,4 sn ön tampon takılmayı önler.
- **temperature 0.7, top_p 0.85, speed 1.0.** Değiştirilince uydurma sesler ve uzayan kelimeler çıktı.
- **"Mergen" seslendirmede "Mêrgen" yazılır.** XTTS düz yazımı çoğunlukla "Mercan" okuyor (Whisper'la dinletilerek
  denendi: 8'de 1'e karşı 8'de 5). Sadece seslendirilen metinde; ekranda "Mergen" kalır.
- **Model uykuda RAM'de, uyanınca ekran kartına** (~0,4 sn). Apple çipinde (MPS) bir işlem desteklenmezse işlemciye
  düşer.
- **Kısa cümlelerde XTTS sona hece uydurabiliyor;** sabit cümleleri (karşılama, veda) çok kısa yazmayın.

### Söz kesme (barge-in)

Mergen konuşurken kullanıcı konuşursa susar. İlk sürümde Mergen'in hoparlörden mikrofona sızan kendi sesi sözünü
kesiyordu. Şimdi her konuşmanın ilk saniyesinde sızıntı oranı ölçülür (o sürede kesilmez); mikrofon beklenen yankının ve
gürültü eşiğinin birkaç katını art arda aşmalı ve Silero VAD konuşma saymalı. Hassasiyet panelde (Kapalı / Düşük / Orta
/ Yüksek).

### Ses aygıtları

- **Aygıt adın bir parçasıyla seçilir;** sistemin varsayılan aygıtlarına dokunulmaz.
- **PortAudio aygıt listesini açılışta bir kez okur.** Sonradan takılan aygıtı görmek için kütüphane yeniden
  başlatılmalı (`cihazlar.refresh`); bu açık akışları geçersiz kıldığı için yalnızca mikrofonu tutan `Ears` yapar.
- **Mikrofon yoksa çökmez:** ekranda "mikrofon bulunamadı" (`mikrofonsuz` durumu) gösterilir, 2 sn'de bir yeniden
  taranır. Kullanırken 3 sn hiç ses parçası gelmezse çıkarılmış sayılır. Hoparlör yoksa cevap ekranda yazılı kalır.

### Beyin (Claude Code)

- **Kalıcı süreç:** `claude -p --input-format stream-json --output-format stream-json --verbose
  --append-system-prompt <kisilik> --effort <efor> [--dangerously-skip-permissions] [--model] [--resume <oturum>]`.
  Her soruda yeniden açılmanın ~4 sn'si kalktı. Model, efor ya da yetki değişince oturum korunarak yeniden başlar.
- **Kişilik `--append-system-prompt` ile verilir;** Claude Code çalışma klasörü dışındaki talimat dosyalarını yüklemiyor.
  Claude, kullanıcının kendi Claude ayarlarını ve belleğini de okur (bu beklenen bir davranış).
- **Her mesaja o anki tarih ve saat eklenir** (`kisilik.with_time`: "[Şu an: 28 Ekim 2026 Çarşamba, 15:02] ...").
  Yapay zekâ zamanı bilmiyor, konuşma geçmişinden tahmin ediyordu; yarım saat önceki konuşmaya "dünkü" dedi.
- **Sınırlı mod varsayılan;** tam yetki `--dangerously-skip-permissions` demek. Tek güvence kişilikteki "geri alınamayan
  işlerden önce sesli evet" kuralı; bu kural zayıflatılmaz.
- **Sihirbaz `claude auth status`** ile kurulu mu, giriş yapılmış mı denetler. `find_executable` PATH'e ek olarak
  bilinen kurulum klasörlerine bakar: kullanıcı Claude'u Mergen açıkken kurduğunda Mergen'in PATH'i eski kalıyor.

### Ekran metinleri

- Kullanıcının gördüğü metinler son kullanıcıya hitap eder: "indirilir", "Mac'inizde gecikebilir"; teknik terim yok
  ("işlemci", "ekran kartında çalışır", model adı).
- Sihirbazda bir şey kurdurulurken bunun Mergen değil, beyin olan yapay zekânın kendi programı olduğu açıkça söylenir.
- Önerilen seçenekler donanıma göre değişir; sabit değildir.

## Teknik tuzaklar

- **PowerShell 5.1:** BOM'suz UTF-8 `.ps1` dosyasında Türkçe karakterler bozulur. `irm | iex` ise BOM'u bozar
  (yukarıda). Kurulum betiklerini `powershell` (5.1) ile deneyin, `pwsh` ile değil.
- **pythonw altında `sys.stdout` yok;** çıktı `konsol.log`'a yönlendirilir.
- **`ayar.json`'a BOM yazmayın;** okurken `utf-8-sig` kullanılır (elle düzenlenip BOM'la kaydedilirse de okunsun).
- **Ekranda geçmiş mesajlar** SSE yeniden bağlanınca `gecmis` bayrağıyla anında gösterilir (yoksa harf harf yeniden
  yazılıyordu).
- **Tarayıcıda (geliştirirken) çok sekme açmayın:** her sekme `/olaylar`'a açık bağlantı tutar; tarayıcının aynı sunucuya
  6 bağlantı sınırı dolunca sayfa takılır.
- **JS'de değişken adı çakışmasın** (`seviye` iki kez tanımlanmıştı → `seviyeKaydirici`).
- **raw.githubusercontent.com 5 dakikaya kadar önbellekler;** gönderdikten hemen sonra kurulum komutu eski betiği
  verebilir.

## Çalıştırma ve deneme

```bash
uv venv --python 3.12 && uv pip install -e ".[piper,xtts]"
MERGEN_HOME=/tmp/mergen-deneme .venv/bin/python -m mergen
```

- Ayarlar: `curl http://127.0.0.1:8765/ayarlar`; kapatmak: `curl -X POST http://127.0.0.1:8765/kapat`.
- Arayüzdeki JS hataları için `http://127.0.0.1:8765`'i bir tarayıcıda açın.
- Konuşmalar, süreler ve hatalar `mergen.log`'da; bir şeyi değiştirdikten sonra oraya bakın.
- Otomatik test yok; değişikliği gerçekten çalıştırarak deneyin (CONTRIBUTING.md → "Denemek").

## Yol haritası (konuşulmuş, yapılmamış)

- ChatGPT (Codex CLI) ve Gemini (Gemini CLI) beyinleri.
- Mac'te konuşma tanımayı Apple çipine taşımak (MLX tabanlı Whisper).
- Mac için medya betiği (Windows'taki `medya.ps1`'in karşılığı, AppleScript ile); şu an Claude Spotify'ı her seferinde
  kendisi çözmeye çalışıyor ve yavaş.
- Her konuşmada süre ölçümleri (tanıma, ilk cevap, ilk ses) kayda.
- Türkçe şarkı sözlerinin kullanıcı sanılmaması (dil süzgeci yalnızca yabancı dili ayırıyor).
- Mikrofon beklenirken ayarlar panelinin de açılabilmesi.

## Güvenlik sınırları

- Varsayılan sınırlı yetki ve sesli "evet" kuralı korunur.
- Otomatik başlatma eklenmez; Windows ya da macOS güvenlik ayarlarına dokunulmaz.
- XTTS modeli ticari amaçla kullanılmaz ya da dağıtılmaz.
