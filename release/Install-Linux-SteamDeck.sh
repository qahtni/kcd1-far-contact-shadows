#!/usr/bin/env bash
# Far Contact Shadows 1.0.1 - installer for Steam Deck / Linux (Proton).
#   bash Install-Linux-SteamDeck.sh [game folder]
# Run it from the extracted archive, wherever that is (Downloads, Mods/FarContactShadows, ...).
# It finds the game itself: in the folder around it (Mods/<mod>), else in every Steam library
# (native and Flatpak Steam, SD cards and other drives Steam knows about), else in ~/Games
# (Heroic, Lutris). A game folder given as the first argument wins over all of that.
# What it does (nothing else):
#   1. Checks the game is closed and Engine/shadercache.pak is the original KCD 1.9.8 file.
#   2. Copies the mod to Mods/FarContactShadows (unless it is already there, e.g. from Vortex).
#   3. Adds the mod to Mods/mod_order.txt if that file exists and does not list it yet.
#   4. Renames Engine/shadercache.pak to Engine/shadercache.pak.original (your backup)
#      and copies install/shadercache_fcs.pak to Engine/shadercache.pak.
#   5. Copies the uninstaller to the game folder as FarContactShadows-Uninstall.sh.
set -u

# Started by double-click (no terminal): reopen in a terminal so the messages stay readable.
if [ ! -t 1 ] && [ -z "${FCS_TERM:-}" ] && { [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; }; then
  command -v konsole >/dev/null && FCS_TERM=1 exec konsole --hold -e bash "$0" "$@"
  command -v xterm >/dev/null && FCS_TERM=1 exec xterm -hold -e bash "$0" "$@"
fi

STOCK=309c3619a2f7eea7ac31ba6df6301f42bf1d42d44b8c261afc4c6ab1b1ec8f55  # KCD 1.9.8 Engine/shadercache.pak
TRIM=09c8201b9b204797f93cfd2d3e477df84fa2bea4effe536b0eb405e412747b03   # install/shadercache_fcs.pak
die() { echo; echo "ERROR: $*"; echo "Nothing more was changed."; exit 1; }
sha() { sha256sum "$1" | cut -d' ' -f1; }
is_game() { [ -f "$1/Bin/Win64/KingdomCome.exe" ] && [ -d "$1/Engine" ]; }
find_game() {  # candidate game folders, one per line
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
echo "Far Contact Shadows 1.0.1 - install"
if [ $# -ge 1 ]; then
  is_game "$1" || die "No Kingdom Come: Deliverance in $1 (it needs Bin/Win64/KingdomCome.exe)."
  GAME=$(cd "$1" && pwd -P)
else
  mapfile -t found < <(find_game | awk '!seen[$0]++')
  if [ ${#found[@]} -eq 0 ]; then
    die "Kingdom Come: Deliverance not found. Run it with the game folder:
  bash Install-Linux-SteamDeck.sh \"/path/to/KingdomComeDeliverance\""
  elif [ ${#found[@]} -eq 1 ]; then
    GAME=${found[0]}
  else
    echo "Found more than one copy of the game:"; for i in "${!found[@]}"; do echo "  $((i + 1))) ${found[$i]}"; done
    [ -t 0 ] || die "Run it again with the game folder as the first argument."
    read -r -p "Install into which one? Number: " n
    [[ "$n" =~ ^[0-9]+$ ]] && [ "$n" -ge 1 ] && [ "$n" -le ${#found[@]} ] || die "No such number."
    GAME=${found[$((n - 1))]}
  fi
fi
echo "Game folder: $GAME"
[ "$SELF" != "$GAME" ] || die "Extract the archive into a folder of its own (for example Downloads), not into the game folder itself."
E=$GAME/Engine
MODS=$(find "$GAME" -maxdepth 1 -type d -iname mods | head -n 1); [ -n "$MODS" ] || MODS=$GAME/Mods
[ -f "$E/shadercache.pak" ] || die "Engine/shadercache.pak is missing. Verify the game files in Steam first."
pgrep -f 'KingdomCome\.exe' >/dev/null && die "The game is running. Close it first."
[ -f "$SELF/Data/FarContactShadows.pak" ] || die "Data/FarContactShadows.pak is missing from $SELF."
NEW=$SELF/install/shadercache_fcs.pak
[ -f "$NEW" ] || die "install/shadercache_fcs.pak is missing from $SELF."

echo "Checking files..."
[ "$(sha "$NEW")" = "$TRIM" ] || die "install/shadercache_fcs.pak is damaged. Download the mod again."
cur=$(sha "$E/shadercache.pak")
if [ "$cur" = "$STOCK" ] && [ -e "$E/shadercache.pak.original" ] && [ "$(sha "$E/shadercache.pak.original")" != "$STOCK" ]; then
  die "Engine/shadercache.pak.original exists but is not the original file. Move it somewhere else, then run this again."
fi
[ "$cur" = "$STOCK" ] || [ "$cur" = "$TRIM" ] ||
  die "Engine/shadercache.pak is not the original KCD 1.9.8 file (another mod changed it, or a different game version).
Restore it with Steam: right-click the game > Properties > Installed Files > Verify integrity of game files, then run this again."

# 1. Mod files
if [ -d "$MODS" ] && [ "$(cd "$SELF/.." && pwd -P)" = "$(cd "$MODS" && pwd -P)" ]; then
  MODDIR=$SELF; echo "Mod files: already in Mods/$(basename "$MODDIR")."
else
  MODDIR=
  for p in "$MODS"/*/Data/FarContactShadows.pak; do [ -f "$p" ] && { MODDIR=$(dirname "$(dirname "$p")"); break; }; done
  if [ -n "$MODDIR" ] && grep -qsi 'FarContactShadows\.pak' "$MODS"/vortex.deployment*.json; then
    echo "Mod files: Mods/$(basename "$MODDIR") (installed by Vortex)."
  else
    [ -n "$MODDIR" ] || MODDIR=$MODS/FarContactShadows
    mkdir -p "$MODDIR/Data" && cp -f "$SELF/mod.manifest" "$SELF/README.txt" "$MODDIR/" &&
      cp -f "$SELF/Data/FarContactShadows.pak" "$MODDIR/Data/" || die "Could not copy the mod to $MODDIR."
    echo "Mod files: copied to Mods/$(basename "$MODDIR")."
  fi
fi
NAME=$(basename "$MODDIR")

# 2. mod_order.txt (when it exists, the game loads only the mods listed in it)
MO=$(find "$MODS" -maxdepth 1 -iname mod_order.txt 2>/dev/null | head -n 1)
if [ -z "$MO" ]; then
  echo "mod_order.txt: not present, nothing to add."
elif tr -d '\r' < "$MO" | grep -qixF -- "$NAME"; then
  echo "mod_order.txt: already lists $NAME."
else
  if [ -s "$MO" ] && [ "$(tail -c 1 "$MO" | od -An -tx1 | tr -d ' ')" != "0a" ]; then printf '\r\n' >> "$MO"; fi
  printf '%s\r\n' "$NAME" >> "$MO" || die "Could not add $NAME to Mods/mod_order.txt."
  echo "mod_order.txt: added $NAME."
fi

# 3. Shader cache (last, so it never runs without the mod in place)
if [ "$cur" = "$TRIM" ]; then
  echo "Shader cache: already installed."
else
  if [ -e "$E/shadercache.pak.original" ]; then
    echo "Backup: Engine/shadercache.pak.original already there."
  else
    mv "$E/shadercache.pak" "$E/shadercache.pak.original" || die "Could not rename Engine/shadercache.pak."
    echo "Backup: Engine/shadercache.pak -> Engine/shadercache.pak.original"
  fi
  if ! { cp "$NEW" "$E/shadercache.pak.fcs-tmp" && mv -f "$E/shadercache.pak.fcs-tmp" "$E/shadercache.pak"; }; then
    rm -f "$E/shadercache.pak.fcs-tmp"
    [ -e "$E/shadercache.pak" ] || mv "$E/shadercache.pak.original" "$E/shadercache.pak"
    die "Copying the shader cache failed (disk full?). The original file is back in place."
  fi
  [ "$(sha "$E/shadercache.pak")" = "$TRIM" ] || die "The copied Engine/shadercache.pak does not match. Run the uninstaller, then try again."
  echo "Shader cache: installed."
fi

cp -f "$SELF/Uninstall-Linux-SteamDeck.sh" "$GAME/FarContactShadows-Uninstall.sh" &&
  echo "Uninstaller copied to the game folder: FarContactShadows-Uninstall.sh"
echo
echo "Done. Start the game; the first start builds the new shadow shader once."
echo "To remove the mod, run FarContactShadows-Uninstall.sh in the game folder FIRST."
echo "(Without the original shader cache back, the game has no sun shadows.)"
