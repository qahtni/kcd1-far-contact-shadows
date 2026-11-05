#!/usr/bin/env bash
# Packs BUILD/FarContactShadows-VERSION.7z in the mod-folder layout (Vortex deploys it as-is into
# Mods/<mod>/; manual users extract it into Mods/FarContactShadows/). Called by ../build.sh.
# Inputs: BUILD/mod/FarContactShadows/{mod.manifest,Data/FarContactShadows.pak} (src/make_compat.py),
# BUILD/shadercache_fcs.pak (src/filter_pak.py), release/{README.txt,*.bat,*.sh}.
# .bat/README get CRLF; .sh stay LF and executable.
# usage: release/build_release.sh BUILD_DIR VERSION
set -euo pipefail
B=$(cd "$1" && pwd); V=$2
R=$(cd "$(dirname "$0")" && pwd)
M=$B/mod/FarContactShadows; S=$B/release/FarContactShadows; OUT=$B/FarContactShadows-$V.7z
rm -rf "$B/release"; mkdir -p "$S/Data" "$S/install"
cp -p "$M/Data/FarContactShadows.pak" "$S/Data/"
cp -p "$M/mod.manifest" "$S/"
cp -p "$B/shadercache_fcs.pak" "$S/install/"
for f in Install-Windows.bat Uninstall-Windows.bat README.txt; do sed 's/\r$//; s/$/\r/' "$R/$f" > "$S/$f"; done
for f in Install-Linux-SteamDeck.sh Uninstall-Linux-SteamDeck.sh; do cp "$R/$f" "$S/$f"; chmod 755 "$S/$f"; bash -n "$S/$f"; done
rm -f "$OUT"; (cd "$S" && 7z a -t7z -mx=9 "$OUT" . >/dev/null)
7z t "$OUT" >/dev/null && echo "built $OUT ($(stat -c %s "$OUT") bytes)"
