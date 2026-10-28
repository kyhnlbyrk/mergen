# Mergen kurulumu (Windows). Soru sormaz: Python ortamını kurar, Mergen'i indirir, kısayolları oluşturur ve açar.
# Tercihler (yapay zekâ, ses, konuşma tanıma...) ilk açılışta ekrandaki sihirbazda sorulur.
#
#   irm https://raw.githubusercontent.com/kyhnlbyrk/mergen/main/install.ps1 | iex
#
# install.ps1 bu dosyayı indirip UTF-8 olarak çalıştıran ASCII yükleyicidir: "irm | iex" dosyanın başındaki BOM'u metinde
# bırakıyor, ilk satır yorum sayılmayıp betik ayrıştırılamıyordu. BOM'suz olunca da PowerShell 5.1 yerel dosyadaki Türkçe
# harfleri bozuyor; bu yüzden ikiye bölündü.
#
# Yeniden çalıştırmak Mergen'i günceller; ayarlar, notlar ve indirilen modeller (veri klasörü) korunur.
# Geliştirirken yerel kopyadan kurmak için: $env:MERGEN_KAYNAK = "."; .\install.ps1
# (param bloğu kullanılmadı: "irm | iex" ile çalıştırılınca sorun çıkarabiliyor.)
$Kaynak = $env:MERGEN_KAYNAK
# Denemek için: MERGEN_HOME başka bir veri klasörü verir (Mergen de onu kullanır), MERGEN_KISAYOLSUZ=1 kısayol yazmaz.

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"  # Invoke-WebRequest'in ilerleme çubuğu indirmeyi çok yavaşlatıyor
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Depo = "https://github.com/kyhnlbyrk/mergen"
$Veri = if ($env:MERGEN_HOME) { $env:MERGEN_HOME } else { Join-Path $env:LOCALAPPDATA "Mergen" }
$Uygulama = Join-Path $Veri "uygulama"
$Ortam = Join-Path $Uygulama ".venv"

function Adim($No, $Metin) { Write-Host "  [$No/5] $Metin" -ForegroundColor Cyan }

# Uzun süren komut: çıktısı gizli çalışır, altında dönen işaret, geçen süre ve indirilen MB görünür (kullanıcı takıldı
# sanmasın). MB ağ kartının sayacından: uv paketleri önce kendi önbelleğine indirip ortama en sonda kopyaladığı için ortamın
# boyutu dakikalarca "1 MB"da kalıyordu. Yüzde gösterilmez: uv toplam ilerleme vermiyor, tahmini yüzde %90'da dakikalarca bekleyip yanıltıyordu.
function Calistir($Dosya, [string[]]$Argumanlar, $Hata) {
    $Bilgi = New-Object System.Diagnostics.ProcessStartInfo $Dosya
    $Bilgi.Arguments = ($Argumanlar | ForEach-Object { '"' + $_ + '"' }) -join " "
    $Bilgi.UseShellExecute = $false
    $Bilgi.RedirectStandardOutput = $true
    $Bilgi.RedirectStandardError = $true
    $Bilgi.CreateNoWindow = $true
    $Surec = [System.Diagnostics.Process]::Start($Bilgi)
    $Cikti = $Surec.StandardOutput.ReadToEndAsync()
    $Hatalar = $Surec.StandardError.ReadToEndAsync()
    $Saat = [System.Diagnostics.Stopwatch]::StartNew()
    $Isaret = "|/-\"; $i = 0; $Ilk = Alinan
    while (-not $Surec.WaitForExit(250)) {
        Write-Host -NoNewline ("`r        {0} {1:m\:ss} · {2} MB indirildi   " -f $Isaret[$i % 4], $Saat.Elapsed, [int]((Alinan) - $Ilk))
        $i++
    }
    $Surec.WaitForExit()
    if ($Surec.ExitCode -ne 0) {
        Write-Host ""
        Write-Host ($Hatalar.Result + $Cikti.Result).Trim() -ForegroundColor DarkGray
        throw $Hata
    }
    Write-Host ("`r        ✓ {0:m\:ss} · {1} MB indirildi   " -f $Saat.Elapsed, [int]((Alinan) - $Ilk)) -ForegroundColor Green
}
function Alinan {
    # Bilgisayarın ağdan aldığı toplam (MB); başka indirmeler de sayılır ama hareketi dürüstçe gösterir.
    $Toplam = 0
    foreach ($Kart in [System.Net.NetworkInformation.NetworkInterface]::GetAllNetworkInterfaces()) {
        if ($Kart.NetworkInterfaceType -ne "Loopback") { $Toplam += $Kart.GetIPStatistics().BytesReceived }
    }
    $Toplam / 1MB
}

Write-Host ""
Write-Host "  M E R G E N  kuruluyor" -ForegroundColor Cyan
Write-Host ""

# Zaten açıksa kapatılır (dosyaları kullanıyor olabilir).
try { Invoke-RestMethod -Method Post http://127.0.0.1:8765/kapat -TimeoutSec 2 | Out-Null; Start-Sleep 3 } catch {}

# 1. uv: Python'u ve paketleri kuran araç (Python kurulu olmasa da kendisi indirir).
$Uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
if (-not $Uv) { $Uv = Join-Path $HOME ".local\bin\uv.exe" }
Adim 1 "Kurulum aracı (uv) hazırlanıyor"
if (-not (Test-Path $Uv)) {
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex" | Out-Null
    if (-not (Test-Path $Uv)) { throw "uv kurulamadı. İnternet bağlantınızı denetleyip yeniden deneyin." }
}

# 2. Mergen'in kodu: GitHub'dan en son sürüm (ya da MERGEN_KAYNAK ile verilen yerel klasör).
Adim 2 "Mergen indiriliyor"
$Gecici = Join-Path ([System.IO.Path]::GetTempPath()) ("mergen-" + [guid]::NewGuid())
New-Item -ItemType Directory -Force $Gecici | Out-Null
if ($Kaynak) {
    $KodKlasoru = (Resolve-Path $Kaynak).Path
} else {
    $Zip = Join-Path $Gecici "mergen.zip"
    Invoke-WebRequest "$Depo/archive/refs/heads/main.zip" -OutFile $Zip -UseBasicParsing
    Expand-Archive $Zip -DestinationPath $Gecici
    $KodKlasoru = (Get-ChildItem $Gecici -Directory | Select-Object -First 1).FullName
}

# 3. Python ortamı ve Mergen (Python 3.12; ortam veri klasöründe, sisteme dokunulmaz).
Adim 3 "Python hazırlanıyor"
New-Item -ItemType Directory -Force $Uygulama | Out-Null
if (-not (Test-Path (Join-Path $Ortam "Scripts\python.exe"))) {
    Calistir $Uv @("venv", $Ortam, "--python", "3.12", "--quiet") "Python ortamı oluşturulamadı."
}
$Python = Join-Path $Ortam "Scripts\python.exe"
$Pythonw = Join-Path $Ortam "Scripts\pythonw.exe"
Adim 4 "Mergen ve kütüphaneleri kuruluyor (internet hızınıza göre birkaç dakika ile 15 dakika arası sürebilir)"
Calistir $Uv @("pip", "install", "--python", $Python, "--quiet", "--reinstall-package", "mergen", $KodKlasoru) "Mergen kurulamadı."
Remove-Item -Recurse -Force $Gecici -ErrorAction SilentlyContinue

# 4. Kısayollar: masaüstü ve Başlat menüsü (konsolsuz açılır).
Adim 5 "Kısayollar oluşturuluyor"
$Simge = Join-Path $Ortam "Lib\site-packages\mergen\araclar\mergen.ico"
$Kabuk = New-Object -ComObject WScript.Shell
$Yerler = @([Environment]::GetFolderPath("Desktop"), (Join-Path ([Environment]::GetFolderPath("Programs")) ""))
if ($env:MERGEN_KISAYOLSUZ) { $Yerler = @() }
foreach ($Yer in $Yerler) {
    $Kisayol = $Kabuk.CreateShortcut((Join-Path $Yer "Mergen.lnk"))
    $Kisayol.TargetPath = $Pythonw
    $Kisayol.Arguments = "-m mergen"
    $Kisayol.WorkingDirectory = $Uygulama
    $Kisayol.IconLocation = $Simge
    $Kisayol.Description = "Mergen: Türkçe sesli asistan"
    $Kisayol.Save()
}

Write-Host ""
Write-Host "  Mergen kuruldu. Masaüstündeki Mergen simgesiyle açabilirsiniz." -ForegroundColor Green
Write-Host "  Şimdi açılıyor; ilk açılışta birkaç tercihinizi soracak." -ForegroundColor Green
Write-Host ""
Start-Process $Pythonw -ArgumentList "-m", "mergen" -WorkingDirectory $Uygulama
