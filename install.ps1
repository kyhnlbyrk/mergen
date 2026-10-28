# Mergen kurulumu (Windows):
#
#   irm https://raw.githubusercontent.com/kyhnlbyrk/mergen/main/install.ps1 | iex
#
# Bu dosya bilerek sadece ASCII: asil kurulum kurulum.ps1'de. Onu bayt olarak indirip UTF-8 diye okur ve calistirir;
# boylece Turkce harfler ve BOM hangi PowerShell surumunde olursa olsun sorun cikarmaz.
# Gelistirirken yerel kopyadan kurmak icin: $env:MERGEN_KAYNAK = "."; .\install.ps1
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
if ($env:MERGEN_KAYNAK) {
    $Bayt = [IO.File]::ReadAllBytes((Join-Path (Resolve-Path $env:MERGEN_KAYNAK).Path "kurulum.ps1"))
} else {
    $Bayt = (New-Object Net.WebClient).DownloadData("https://raw.githubusercontent.com/kyhnlbyrk/mergen/main/kurulum.ps1")
}
$Metin = [Text.Encoding]::UTF8.GetString($Bayt).TrimStart([char]0xFEFF)
& ([scriptblock]::Create($Metin))
