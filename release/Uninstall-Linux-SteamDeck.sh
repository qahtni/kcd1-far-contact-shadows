#!/usr/bin/env bash
# Far Contact Shadows 1.0.1 - uninstaller for Steam Deck / Linux (Proton).
#   bash FarContactShadows-Uninstall.sh [game folder]
# Works from the game folder (the installer leaves a copy there as FarContactShadows-Uninstall.sh),
# from Mods/FarContactShadows, or from the extracted archive anywhere else (it then finds the game
# the same way the installer does).
# What it does:
#   1. Puts the original Engine/shadercache.pak back from Engine/shadercache.pak.original.
#   2. Deletes the mod folder and its line in Mods/mod_order.txt
#      (skipped for a Vortex-installed copy: remove that one in Vortex).
#   3. Deletes FarContactShadows-Uninstall.sh from the game folder.
set -u

if [ ! -t 1 ] && [ -z "${FCS_TERM:-}" ] && { [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; }; then
  command -v konsole >/dev/null && FCS_TERM=1 exec konsole --hold -e bash "$0" "$@"
  command -v xterm >/dev/null && FCS_TERM=1 exec xterm -hold -e bash "$0" "$@"
fi

STOCK=309c3619a2f7eea7ac31ba6df6301f42bf1d42d44b8c261afc4c6ab1b1ec8f55
TRIM=09c8201b9b204797f93cfd2d3e477df84fa2bea4effe536b0eb405e412747b03
die() { echo; echo "ERROR: $*"; exit 1; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
is_game() { [ -f "$1/Bin/Win64/KingdomCome.exe" ] && [ -d "$1/Engine" ]; }
find_game() {  # same search as the installer
  local d r lib
  for d in "$SELF/../.." "$SELF"; do is_game "$d" && { (cd "$d" && pwd -P); return; }; done
  for r in "$HOME/.local/share/Steam" "$HOME/.steam/steam" "$HOME/.steam/root" \
           "$HOME/.var/app/com.valvesoftware.Steam/.local/share/Steam" "$HOME/.var/app/com.valvesoftware.Steam/data/Steam"; do
    [ -d "$r/steamapps" ] || continue
    { echo "$r"; sed -n 's/^[[:space:]]*"path"[[:space:]]*"\(.*\)"[[:space:]]*$/\1/p' "$r/steamapps/libraryfolders.vdf" 2>/dev/null; } |
      while IFS= read -r lib; do d=$lib/steamapps/common/KingdomComeDeliverance; is_game "$d" && (cd "$d" && pwd -P); done
  done
  find "$HOME/Games" -maxdepth 6 -type f -path '*/Bin/Win64/KingdomCome.exe' 2>/dev/null | sed 's|/Bin/Win64/KingdomCome.exe$||'
}

SELF=$(cd "$(dirname "$0")" && pwd -P)
echo "Far Contact Shadows 1.0.1 - uninstall"
if [ $# -ge 1 ]; then
  is_game "$1" || die "No Kingdom Come: Deliverance in $1 (it needs Bin/Win64/KingdomCome.exe)."
  GAME=$(cd "$1" && pwd -P)
else
  mapfile -t found < <(find_game | awk '!seen[$0]++')
  if [ ${#found[@]} -eq 0 ]; then
    die "Kingdom Come: Deliverance not found. Run it with the game folder:
  bash FarContactShadows-Uninstall.sh \"/path/to/KingdomComeDeliverance\""
  elif [ ${#found[@]} -eq 1 ]; then
    GAME=${found[0]}
  else
    echo "Found more than one copy of the game:"; for i in "${!found[@]}"; do echo "  $((i + 1))) ${found[$i]}"; done
    [ -t 0 ] || die "Run it again with the game folder as the first argument."
    read -r -p "Uninstall from which one? Number: " n
    [[ "$n" =~ ^[0-9]+$ ]] && [ "$n" -ge 1 ] && [ "$n" -le ${#found[@]} ] || die "No such number."
    GAME=${found[$((n - 1))]}
  fi
fi
echo "Game folder: $GAME"
E=$GAME/Engine
MODS=$(find "$GAME" -maxdepth 1 -type d -iname mods | head -n 1); [ -n "$MODS" ] || MODS=$GAME/Mods
pgrep -f 'KingdomCome\.exe' >/dev/null && die "The game is running. Close it first."

echo "Checking files..."
cur=$( [ -f "$E/shadercache.pak" ] && sha "$E/shadercache.pak" )
if [ "$cur" = "$STOCK" ]; then
  echo "Shader cache: already the original."
  [ -f "$E/shadercache.pak.original" ] && [ "$(sha "$E/shadercache.pak.original")" = "$STOCK" ] &&
    rm -f "$E/shadercache.pak.original" && echo "Removed the spare backup Engine/shadercache.pak.original."
elif [ -f "$E/shadercache.pak.original" ] && [ "$(sha "$E/shadercache.pak.original")" = "$STOCK" ]; then
  [ -z "$cur" ] || [ "$cur" = "$TRIM" ] || echo "Note: Engine/shadercache.pak was changed by something else; replacing it with the original anyway."
  mv -f "$E/shadercache.pak.original" "$E/shadercache.pak" || die "Could not restore Engine/shadercache.pak."
  echo "Shader cache: original restored."
else
  die "The backup Engine/shadercache.pak.original is missing or changed.
Get the original back with Steam: right-click the game > Properties > Installed Files > Verify integrity of game files.
Until then the game has no sun shadows."
fi

MO=$(find "$MODS" -maxdepth 1 -iname mod_order.txt 2>/dev/null | head -n 1)
for pak in "$MODS"/*/Data/FarContactShadows.pak; do
  [ -f "$pak" ] || continue
  D=$(dirname "$(dirname "$pak")"); N=$(basename "$D")
  if grep -qsi 'FarContactShadows\.pak' "$MODS"/vortex.deployment*.json; then
    echo "Mods/$N was installed by Vortex: remove the mod in Vortex now."
    continue
  fi
  if [ -n "$MO" ]; then
    tr -d '\r' < "$MO" | awk -v n="$N" 'tolower($0) != tolower(n) && $0 != "" { printf "%s%s", (c++ ? "\r\n" : ""), $0 }' > "$MO.fcs-tmp" &&
      mv -f "$MO.fcs-tmp" "$MO" && echo "mod_order.txt: removed $N."
  fi
  rm -rf -- "$D" && echo "Deleted Mods/$N."
done

rm -f "$GAME/FarContactShadows-Uninstall.sh"
echo
echo "Done. The game is back to its original shadows."
