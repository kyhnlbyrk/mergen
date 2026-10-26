# Spotify ve medya tuşları (Mergen kullanır). "ara" ilk sonucu çalar.
#   medya.ps1 ac | cal | sonraki | onceki | sesac | seskis | sessiz | ara "şarkı ya da sanatçı"
param(
	[Parameter(Mandatory = $true)][string]$Komut,
	[string]$Arama = ""
)

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class Medya {
	[DllImport("user32.dll")] static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
	public static void Bas(byte vk) { keybd_event(vk, 0, 0, UIntPtr.Zero); keybd_event(vk, 0, 2, UIntPtr.Zero); }
}
"@

function Spotify-Ac {
	if (-not (Get-Process Spotify -ErrorAction SilentlyContinue)) {
		Start-Process "spotify:"
		Start-Sleep -Seconds 4
	}
}

switch ($Komut) {
	"ac" { Spotify-Ac }
	"cal" { Spotify-Ac; [Medya]::Bas(0xB3) }
	"sonraki" { [Medya]::Bas(0xB0) }
	"onceki" { [Medya]::Bas(0xB1) }
	"sesac" { 1..5 | ForEach-Object { [Medya]::Bas(0xAF) } }
	"seskis" { 1..5 | ForEach-Object { [Medya]::Bas(0xAE) } }
	"sessiz" { [Medya]::Bas(0xAD) }
	"ara" {
		Spotify-Ac
		# Hızlı arama (Ctrl+K) + Shift+Enter: ilk sonucu doğrudan çalar
		$w = New-Object -ComObject WScript.Shell
		$p = Get-Process Spotify | Where-Object { $_.MainWindowTitle } | Select-Object -First 1
		if ($p) { $w.AppActivate($p.Id) | Out-Null }
		Start-Sleep -Milliseconds 400
		$w.SendKeys("^k"); Start-Sleep -Milliseconds 600
		$w.SendKeys(($Arama -replace '([+^%~(){}\[\]])', '{$1}')); Start-Sleep -Milliseconds 1500
		$w.SendKeys("+{ENTER}")
	}
	default { Write-Output "Bilinmeyen komut: $Komut" ; exit 1 }
}
Write-Output "tamam: $Komut $Arama"
