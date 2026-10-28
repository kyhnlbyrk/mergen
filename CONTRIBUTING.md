# Mergen'e katkıda bulunmak

Mergen'e ilgi gösterdiğiniz için teşekkürler. Hata bildirimi, fikir, metin düzeltmesi ya da kod; her katkı değerli.

## Nasıl katkıda bulunurum?

### Hata bildirmek

[Issues](https://github.com/kyhnlbyrk/mergen/issues) sayfasında yeni bir kayıt açın ve şunları yazın:

- Ne yaptınız, ne bekliyordunuz, ne oldu
- İşletim sistemi (Windows 11, macOS 15...) ve bilgisayar (ekran kartı, Apple çipi)
- Ayarlardaki seçimleriniz (ses, konuşma tanıma, yetki)
- Veri klasöründeki kayıtlar: `mergen.log`, `konsol.log`, gerekirse `beyin.log`
  (Windows: `%LOCALAPPDATA%\Mergen`, macOS: `~/Library/Application Support/Mergen`)

Kayıtlarda konuşmalarınız yazılıdır; paylaşmadan önce göz atın.

### Fikir önermek

Büyük bir değişiklik (yeni bir yapay zekâ, yeni bir özellik, mimari değişiklik) düşünüyorsanız önce bir issue açıp
konuşalım. Böylece emeğiniz boşa gitmez.

### Kod göndermek (Pull Request)

1. Depoyu kendi hesabınıza **fork** edin ve yerelinize klonlayın.
2. `main`'den yeni bir dal açın: `git checkout -b ses-seviyesi-duzeltmesi`
3. Değişikliğinizi yapın. Bir PR tek bir işi yapsın; küçük ve odaklı PR'lar çok daha hızlı incelenir.
4. Değişikliği gerçekten çalıştırarak deneyin (aşağıda "Denemek").
5. Commit mesajını Türkçe ve kısa yazın: ne değişti, neden (`Mikrofon yokken çökmez, takılınca devam eder`).
6. Fork'unuza gönderin ve `main`'e bir **Pull Request** açın. Açıklamada şunları yazın:
   - Neyi neden değiştirdiniz
   - Hangi işletim sisteminde, hangi ayarlarla denediniz
   - Ekranda görünen bir değişiklikse ekran görüntüsü

Katkılarınız projenin [MIT lisansıyla](LICENSE) yayımlanır.

## Geliştirme ortamı

Gerekenler: Python 3.12 (ya da 3.10-3.13), [uv](https://docs.astral.sh/uv/) önerilir, Claude Code kurulu ve giriş
yapılmış olmalı.

```bash
git clone https://github.com/<kullanıcı-adınız>/mergen.git
cd mergen
uv venv --python 3.12
uv pip install -e ".[piper,xtts]"
```

Doğal sesle uğraşmayacaksanız `xtts` olmadan kurabilirsiniz (`uv pip install -e ".[piper]"`); PyTorch büyük bir indirme.

Çalıştırmak:

```bash
# Windows: .venv\Scripts\python -m mergen
.venv/bin/python -m mergen
```

Gerçek ayarlarınıza ve modellerinize dokunmadan denemek için ayrı bir veri klasörü verin:

```bash
MERGEN_HOME=/tmp/mergen-deneme .venv/bin/python -m mergen      # macOS
$env:MERGEN_HOME = "$env:TEMP\mergen-deneme"; .venv\Scripts\python -m mergen   # Windows
```

Boş bir veri klasörüyle Mergen ilk açılış sihirbazını baştan gösterir.

### Kurulum betiklerini denemek

Betikleri GitHub yerine yerel kopyanızdan çalıştırmak için `MERGEN_KAYNAK`, kısayol yazmaması için `MERGEN_KISAYOLSUZ`:

```powershell
$env:MERGEN_KAYNAK = "."; $env:MERGEN_HOME = "$env:TEMP\mergen-deneme"; $env:MERGEN_KISAYOLSUZ = "1"; .\install.ps1
```

```bash
MERGEN_KAYNAK=. MERGEN_HOME=/tmp/mergen-deneme bash install.sh
```

Not: Kurulum betikleri açık olan Mergen'i kapatır ve kurulumun sonunda yenisini açar.

## Denemek

Otomatik testler henüz yok; değişikliğinizi elle deneyin. Dokunduğunuz yere göre:

- **Ses, konuşma tanıma, uyanma:** "Mergen uyan" deyip birkaç soru sorun, sözünü kesin, "uyu" deyin.
- **Sihirbaz:** boş bir `MERGEN_HOME` ile baştan geçin.
- **Ayarlar paneli:** ilgili ayarı değiştirin, Mergen'i kapatıp açın, ayarın kaldığını görün.
- **Kurulum betikleri:** PowerShell 5.1'de (`powershell`, `pwsh` değil) ve macOS Terminal'de çalıştırın.
- Mümkünse hem ekran kartlı hem kartsız bir bilgisayarda ya da Mac'te deneyin; davranış donanıma göre değişiyor.

## Kod kuralları

- **Dil:** Kullanıcının gördüğü her şey (ekran, sesli cevaplar, kayıtlar) ve kod yorumları **Türkçe**. Python'da sınıf ve
  işlev adları İngilizce; ekran tarafındaki (HTML/JS) adlar Türkçe. Çevredeki kodun düzenine uyun.
- **Son kullanıcı metinleri:** Teknik terim yok ("işlemcide çalışır" değil, "Mac'inizde gecikebilir"). Mergen kullanıcıya
  "beyim" der ve "siz" diye konuşur.
- **Yorumlar "neden"i anlatır:** Bir şeyi tuhaf bir yoldan yaptıysanız sebebini yorumda yazın; sonraki kişi geri
  almasın.
- **Dosya kodlamaları:** `kurulum.ps1` BOM'lu UTF-8 (PowerShell 5.1 BOM'suz dosyada Türkçeyi bozuyor). `install.ps1`
  bilerek yalnızca ASCII (`irm | iex` BOM'u bozuyor). `install.sh` LF satır sonlu. `ayar.json` BOM'suz yazılır.
- **Güvenlik kuralları değişmez:** Varsayılan sınırlı yetki ve geri alınamayan işlerden önce sesli "evet" kuralı
  zayıflatılmaz. Otomatik başlatma eklenmez.

Projenin mimarisi, dosyaların ne yaptığı ve alınmış teknik kararların gerekçeleri [AGENTS.md](AGENTS.md)'de. Kod
yazmadan önce okumanızı öneririz.

## Yeni bir yapay zekâ eklemek

Mergen API anahtarı kullanmaz; her yapay zekâ, kullanıcının aboneliğiyle giriş yaptığı resmi komut satırı aracıyla
bağlanır. Yeni bir tane eklemek için:

1. `mergen/beyin/` altında `Brain`'den (`beyin/temel.py`) türeyen bir sınıf yazın: `check()` (sihirbaz için kurulu mu,
   giriş yapılmış mı), `ask()`, `start()`, `restart()`, `reset()`. Örnek: `beyin/claude.py`.
2. `beyin/__init__.py`'deki `BRAINS`'e ekleyin (ve `COMING_SOON`'dan çıkarın).
3. Kişilik ve bilgisayarı kullanma bilgisi `kisilik.py`'den gelir; hangi araç olursa olsun aynı sistem istemi verilir.

ChatGPT (Codex CLI) ve Gemini (Gemini CLI) sırada; bunlardan birini üstlenmek isterseniz issue açın.
