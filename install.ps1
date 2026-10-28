# Mergen kurulumu (Windows):
#
#   irm https://raw.githubusercontent.com/kyhnlbyrk/mergen/main/install.ps1 | iex
#
# Bu dosya bilerek sadece ASCII: asil kurulum kurulum.ps1'de. Onu bayt olarak indirip UTF-8 diye okur ve calistirir;
# boylece Turkce harfler ve BOM hangi PowerShell surumunde olursa olsun sorun cikarmaz.
# Kurulan surum: GitHub'daki son yayimlanmis surum (Releases); main'e gonderilen yarim bir degisiklik kullanicilara gitmez.
# Surum bulunamazsa main. MERGEN_SURUM ile belirli bir surum ya da dal verilebilir (orn. "main").
# Gelistirirken yerel kopyadan kurmak icin: $env:MERGEN_KAYNAK = "."; .\install.ps1
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
if ($env:MERGEN_KAYNAK) {
    $Bayt = [IO.File]::ReadAllBytes((Join-Path (Resolve-Path $env:MERGEN_KAYNAK).Path "kurulum.ps1"))
} else {
    if (-not $env:MERGEN_SURUM) {
        try {
            $env:MERGEN_SURUM = (Invoke-RestMethod "https://api.github.com/repos/kyhnlbyrk/mergen/releases/latest" -TimeoutSec 15).tag_name
        } catch {}
        if (-not $env:MERGEN_SURUM) { $env:MERGEN_SURUM = "main" }
    }
    $Bayt = (New-Object Net.WebClient).DownloadData("https://raw.githubusercontent.com/kyhnlbyrk/mergen/$($env:MERGEN_SURUM)/kurulum.ps1")
}
$Metin = [Text.Encoding]::UTF8.GetString($Bayt).TrimStart([char]0xFEFF)
& ([scriptblock]::Create($Metin))
