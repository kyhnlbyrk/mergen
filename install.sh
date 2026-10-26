#!/usr/bin/env bash
# Mergen kurulumu (macOS ve Linux). Soru sormaz: Python ortamını kurar, Mergen'i indirir, uygulama simgesini oluşturur ve
# açar. Tercihler (yapay zekâ, ses, konuşma tanıma...) ilk açılışta ekrandaki sihirbazda sorulur.
#
#   curl -fsSL https://raw.githubusercontent.com/kyhnlbyrk/mergen/main/install.sh | bash
#
# Yeniden çalıştırmak Mergen'i günceller; ayarlar, notlar ve indirilen modeller (veri klasörü) korunur.
# Geliştirirken yerel kopyadan kurmak için: MERGEN_KAYNAK=. ./install.sh
set -euo pipefail

DEPO="https://github.com/kyhnlbyrk/mergen"
if [[ "$(uname)" == "Darwin" ]]; then
  VERI="$HOME/Library/Application Support/Mergen"
else
  VERI="${XDG_DATA_HOME:-$HOME/.local/share}/mergen"
fi
UYGULAMA="$VERI/uygulama"
ORTAM="$UYGULAMA/.venv"

adim() { printf '  \033[36m> %s\033[0m\n' "$1"; }
hata() { printf '  \033[31m%s\033[0m\n' "$1" >&2; exit 1; }

printf '\n  \033[36mM E R G E N  kuruluyor\033[0m\n\n'

# Zaten açıksa kapatılır (dosyaları kullanıyor olabilir).
curl -s -m 2 -X POST http://127.0.0.1:8765/kapat >/dev/null 2>&1 && sleep 3 || true

# 1. uv: Python'u ve paketleri kuran araç (Python kurulu olmasa da kendisi indirir).
UV="$(command -v uv || true)"
[[ -z "$UV" ]] && UV="$HOME/.local/bin/uv"
if [[ ! -x "$UV" ]]; then
  adim "Kurulum aracı (uv) indiriliyor"
  curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1 || true
  [[ -x "$UV" ]] || hata "uv kurulamadı. İnternet bağlantınızı denetleyip yeniden deneyin."
fi

# 2. Mergen'in kodu: GitHub'dan en son sürüm (ya da MERGEN_KAYNAK ile verilen yerel klasör).
GECICI="$(mktemp -d)"
trap 'rm -rf "$GECICI"' EXIT
if [[ -n "${MERGEN_KAYNAK:-}" ]]; then
  KOD="$(cd "$MERGEN_KAYNAK" && pwd)"
else
  adim "Mergen indiriliyor"
  curl -fsSL "$DEPO/archive/refs/heads/main.tar.gz" | tar -xz -C "$GECICI"
  KOD="$(find "$GECICI" -mindepth 1 -maxdepth 1 -type d | head -1)"
fi

# 3. Python ortamı ve Mergen (Python 3.12; ortam veri klasöründe, sisteme dokunulmaz).
adim "Python ortamı hazırlanıyor"
mkdir -p "$UYGULAMA"
[[ -x "$ORTAM/bin/python" ]] || "$UV" venv "$ORTAM" --python 3.12 --quiet || hata "Python ortamı oluşturulamadı."
adim "Mergen kuruluyor"
"$UV" pip install --python "$ORTAM/bin/python" --quiet --reinstall-package mergen "$KOD" || hata "Mergen kurulamadı."
SIMGE_KLASORU="$("$ORTAM/bin/python" -c 'import mergen, pathlib; print(pathlib.Path(mergen.__file__).parent / "araclar")')"

# 4. Uygulama simgesi.
adim "Uygulama simgesi oluşturuluyor"
if [[ "$(uname)" == "Darwin" ]]; then
  # ~/Applications/Mergen.app: Launchpad'de ve Spotlight'ta görünür, açılınca kendi penceresiyle Dock'ta ve Cmd+Tab'da
  # durur (pencere.py). Mikrofon izni ilk açılışta "Mergen" adıyla sorulur.
  APP="$HOME/Applications/Mergen.app"
  rm -rf "$APP"
  mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
  cp "$SIMGE_KLASORU/mergen.icns" "$APP/Contents/Resources/mergen.icns"
  cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Mergen</string>
  <key>CFBundleDisplayName</key><string>Mergen</string>
  <key>CFBundleIdentifier</key><string>com.github.kyhnlbyrk.mergen</string>
  <key>CFBundleExecutable</key><string>Mergen</string>
  <key>CFBundleIconFile</key><string>mergen</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>0.1.0</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>NSMicrophoneUsageDescription</key><string>Mergen sizi duyabilmek için mikrofonu kullanır; ses bilgisayarınızın dışına gönderilmez.</string>
</dict>
</plist>
PLIST
  cat > "$APP/Contents/MacOS/Mergen" <<LAUNCHER
#!/bin/bash
cd "$UYGULAMA"
# Finder'dan açılınca çıktılar hiçbir yere gitmiyor: hatalar konsol.log'a yazılsın.
exec "$ORTAM/bin/python" -m mergen >> "$VERI/konsol.log" 2>&1
LAUNCHER
  chmod +x "$APP/Contents/MacOS/Mergen"
  printf '\n  \033[32mMergen kuruldu. Launchpad ya da Spotlight ile "Mergen" diye açabilirsiniz.\033[0m\n'
  printf '  \033[32mŞimdi açılıyor; ilk açılışta mikrofon izni ve birkaç tercihinizi soracak.\033[0m\n\n'
  open "$APP"
else
  MASAUSTU="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
  mkdir -p "$MASAUSTU"
  cat > "$MASAUSTU/mergen.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Mergen
Comment=Türkçe sesli asistan
Exec="$ORTAM/bin/python" -m mergen
Path=$UYGULAMA
Icon=$SIMGE_KLASORU/mergen.png
Terminal=false
Categories=Utility;
DESKTOP
  printf '\n  \033[32mMergen kuruldu. Uygulamalar menüsünden açabilirsiniz. Şimdi açılıyor.\033[0m\n\n'
  (cd "$UYGULAMA" && nohup "$ORTAM/bin/python" -m mergen >/dev/null 2>&1 &)
fi
