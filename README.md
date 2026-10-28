# Mergen

Türklerin JARVIS'i: Türkçe konuşan, tamamen sesle yönetilen bir yapay zekâ asistanı. "Mergen uyan" demeniz yeterli;
sorularınızı cevaplar, uygulamalarınızı açar, müziğinizi çalar, oyununuzu başlatır, bilgisayarınızı sizin yerinize
kullanır. Size "beyim" diye hitap eder.

- **API anahtarı gerekmez.** Mergen, zaten kullandığınız yapay zekâ aboneliğinizle çalışır.
- **Sesiniz bilgisayarınızda kalır.** Konuşma tanıma ve Mergen'in sesi tamamen sizin bilgisayarınızda çalışır.
- **Kurulumu kolay.** Tek komut; gerisini ilk açılışta ekrandaki sihirbaz sorar.
- **Açık kaynak ve ücretsiz** (MIT).

> **Durum:** Windows ve macOS'ta çalışıyor.

## Desteklenen yapay zekâlar

Mergen'in beyni, seçtiğiniz yapay zekâdır. Mergen onun resmi programını kendi aboneliğinizle kullanır; API anahtarı
gerekmez.

| Yapay zekâ | Gereken abonelik | Durum |
|---|---|---|
| Claude | Claude Pro ya da Max | ✅ Kullanılabilir |
| ChatGPT | ChatGPT Plus ya da Pro | 🔜 Yakında |
| Gemini | Google hesabı | 🔜 Yakında |

## Neler gerekir?

- Windows 10/11 ya da macOS 11 ve sonrası
- Desteklenen bir yapay zekânın aboneliği (şu an **Claude** Pro ya da Max)
- Mikrofon ve hoparlör (ya da kulaklık)
- Diskte 2-6 GB boş alan (seçtiğiniz sese ve konuşma tanımaya göre)

Python ya da başka bir şey kurmanıza gerek yok.

## Kurulum

**Windows:** Başlat menüsüne "PowerShell" yazıp açın, şu komutu yapıştırıp Enter'a basın:

```powershell
irm https://raw.githubusercontent.com/kyhnlbyrk/mergen/main/install.ps1 | iex
```

**macOS:** Cmd + Boşluk ile "Terminal" yazıp açın, şu komutu yapıştırıp Enter'a basın:

```bash
curl -fsSL https://raw.githubusercontent.com/kyhnlbyrk/mergen/main/install.sh | bash
```

Kurulum internet hızınıza göre birkaç dakika ile 15 dakika arası sürer ve adım adım ilerlemesini gösterir. Bitince Mergen kendiliğinden açılır; sonra masaüstündeki
kısayoldan (macOS'ta Launchpad ya da Spotlight'tan "Mergen") açabilirsiniz.

### İlk açılış

Ekranda bir kurulum sihirbazı çıkar. Bilgisayarınızı kendisi tanır, size yalnızca tercihlerinizi sorar:

1. **Yapay zekâ:** Mergen'in beyni olacak yapay zekâyı seçersiniz (şu an Claude; ChatGPT ve Gemini yakında). Onun
   programı bilgisayarınızda kurulu değilse sihirbaz nasıl kuracağınızı adım adım gösterir.
2. **Ses:** Doğal ses (insana çok yakın) ya da hafif ses (her bilgisayarda hızlı). İkisini de dinleyip seçebilirsiniz.
3. **Konuşma tanıma:** Sizi ne kadar iyi anlasın. Sihirbaz bilgisayarınıza en uygun olanı önerir.
4. **Yetki:** Mergen bilgisayarınızda ne kadar serbest olsun (aşağıda "Güvenlik ve gizlilik").
5. **Mikrofon ve hoparlör.**

Gerekenler indirilirken ilerleme ve kalan süre ekranda görünür; doğal ses büyük bir indirme olduğu için yavaş
bağlantılarda uzun sürebilir. Doğal sesi seçtiyseniz isterseniz onu bekleyebilir ya da hafif sesle
hemen başlayabilirsiniz; doğal ses inince Mergen kendiliğinden ona geçer.

### Güncelleme

Kurulum komutunu yeniden çalıştırmanız yeterli. Ayarlarınız ve indirilen modeller korunur.

## Kullanım

- **"Mergen uyan"**: uyanır. Sonrasında anahtar sözcük olmadan sohbet sürer.
- **"Görüşürüz"**, **"uyu"**: uykuya geçer.
- **"Yeni konuşma"**: önceki konuşmayı unutur.
- **"Kapat kendini"**: tamamen kapanır.

Mergen konuşurken araya girerseniz susar ve sizi dinler. Ekranın sol üstündeki **⚙ AYARLAR** panelinden yapay zekâyı,
sesi, konuşmacıyı, konuşma tanımayı, mikrofonu ve hoparlörü değiştirebilirsiniz.

## Güvenlik ve gizlilik

- Varsayılan olarak **sınırlı moddadır**: sohbet eder, dosyalarınızı okuyup arayabilir ama bilgisayarınızda hiçbir şeyi
  değiştirmez, program çalıştırmaz.
- Bilgisayarınızı kullanması için ayarlardan **tam yetki** açılır. Tam yetkide de geri alınamayan işlerden önce (silme,
  satın alma, mesaj gönderme, sistem ayarı) sesli "evet" demenizi bekler.
- Sesiniz bilgisayarınızdan çıkmaz: yazıya bilgisayarınızda çevrilir. Seçtiğiniz yapay zekâya yalnızca söylediklerinizin
  yazılı hâli gider.

## Sorun mu var?

Mergen'in kayıtları veri klasöründe durur:

- Windows: `%LOCALAPPDATA%\Mergen`
- macOS: `~/Library/Application Support/Mergen`

Bir hata bildirmek isterseniz [GitHub'da bir kayıt (issue) açın](https://github.com/kyhnlbyrk/mergen/issues) ve bu
klasördeki `mergen.log` ile `konsol.log` dosyalarını ekleyin.

## Kaldırma

Mergen'in kendisi, ayarlarınız ve indirilen modeller tek bir klasörde durur; sistemde başka iz bırakmaz.

**Windows** (PowerShell):

```powershell
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\Mergen", "$([Environment]::GetFolderPath('Desktop'))\Mergen.lnk", "$([Environment]::GetFolderPath('Programs'))\Mergen.lnk"
```

**macOS** (Terminal):

```bash
rm -rf ~/Applications/Mergen.app "$HOME/Library/Application Support/Mergen"
```

## Katkıda bulunmak

Mergen açık kaynak; her katkıya açığız. Nasıl katkıda bulunacağınızı ve projenin teknik yapısını
[CONTRIBUTING.md](CONTRIBUTING.md) anlatıyor.

## Lisans

Mergen'in kodu [MIT](LICENSE) lisanslıdır.

Doğal ses modeli (XTTS v2) Mergen'le birlikte dağıtılmaz; kurulumda sizin onayınızla indirilir ve kendi lisansına
([Coqui Public Model License](https://tts-hub.github.io/cpml)) tabidir: yalnızca ticari olmayan kullanım.
