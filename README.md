# Mergen

Türklerin JARVIS'i: Mergen. Türkçe konuşan, tamamen sesle yönetilen bir yapay zekâ asistanı. "Mergen uyan" demeniz
yeterli: uygulamalarınızı açar, müziğinizi çalar, oyununuzu başlatır, bilgisayarınızı sizin yerinize kullanır.

API anahtarı gerekmez. Mergen, aboneliğinizle giriş yaptığınız resmi yapay zekâ aracını kullanır. Ses tanıma ve
konuşma tamamen sizin bilgisayarınızda çalışır.

> **Durum:** geliştirme aşamasında. Şu an Windows'ta ve Claude ile çalışıyor. ChatGPT (Codex), Gemini, macOS desteği
> ve tek tıkla kurulum yolda.

## Nasıl çalışır?

```
mikrofon → Whisper (yerel ses tanıma) → "Mergen uyan" → yapay zekâ (abonelikle) → XTTS / Piper (yerel ses) → hoparlör
```

Ekranda JARVIS tarzı bir top ve konuşmanın yazılı hâli görünür. Ayarlar panelinden yapay zekâyı, sesi, mikrofonu ve
hoparlörü değiştirebilirsiniz.

| Yapay zekâ | Gereken araç | Durum |
|---|---|---|
| Claude | [Claude Code](https://claude.com/claude-code) (Claude aboneliği) | Çalışıyor |
| ChatGPT | Codex CLI (ChatGPT aboneliği) | Yolda |
| Gemini | Gemini CLI (Google hesabı) | Yolda |

## Sesli komutlar

- **"Mergen uyan"**: uyanır, sonrasında anahtar sözcük olmadan sohbet sürer.
- **"Görüşürüz"**, **"uyu"**: uykuya geçer.
- **"Yeni konuşma"**: önceki konuşmayı unutur.
- **"Kapat kendini"**: tamamen kapanır.

Mergen konuşurken araya girerseniz susar ve sizi dinler.

## Geliştirici kurulumu (şimdilik)

```bash
git clone https://github.com/kyhnlbyrk/mergen.git
cd mergen
python -m venv .venv
.venv\Scripts\pip install -e .
.venv\Scripts\python -m mergen
```

İlk açılışta ekranda bir kurulum sihirbazı çıkar. Bilgisayarınızı (işletim sistemi, ekran kartı, disk) kendisi tanır ve
size sadece tercihlerinizi sorar: yapay zekâ, ses (örnekleri dinleyerek), konuşma tanıma, yetki, mikrofon ve hoparlör.
Gerekenleri kendisi indirir ve ilerlemeyi gösterir. Doğal ses (XTTS) seçerseniz Mergen önce hafif sesle açılır, doğal
ses arka planda iner ve bitince ona geçer.

Seçtiğiniz yapay zekânın aracı kurulu ve giriş yapılmış olmalı. Sihirbaz bunu denetler; değilse hangi komutları
çalıştıracağınızı gösterir.

## Dosyalar nerede?

Ayarlar, kayıtlar, notlar ve indirilen modeller tek bir klasörde durur. Mergen'i kaldırınca bu klasörü silmeniz yeterli:

- Windows: `%LOCALAPPDATA%\Mergen`
- macOS: `~/Library/Application Support/Mergen`

## Güvenlik

Varsayılan olarak **sınırlı moddadır**: yapay zekâ dosya okuyup arayabilir ama komut çalıştıramaz. Bilgisayarı
kullanması için ayarlardan **tam yetki** açılır. Tam yetkide de geri alınamayan işlerden önce (silme, satın alma,
mesaj gönderme, sistem ayarı) sesli "evet" bekler.

## Lisans

Mergen'in kodu [MIT](LICENSE) lisanslıdır.

XTTS v2 ses modeli Mergen'le dağıtılmaz; kurulumda sizin onayınızla indirilir ve kendi lisansına
([Coqui Public Model License](https://tts-hub.github.io/cpml), yalnızca ticari olmayan kullanım) tabidir.
