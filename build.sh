#!/usr/bin/env bash
# Builds Far Contact Shadows from your own copy of Kingdom Come: Deliverance (made for 1.9.8).
# The repo holds no game files: the stock shader and shader cache are read from the game's paks.
# Needs python3 and 7z (p7zip).
# usage: ./build.sh /path/to/KingdomComeDeliverance [BUILD_DIR]   (default BUILD_DIR: ./build)
set -euo pipefail
VERSION=1.0.1
GAME=${1:?usage: ./build.sh /path/to/KingdomComeDeliverance [BUILD_DIR]}
HERE=$(cd "$(dirname "$0")" && pwd)
B=${2:-$HERE/build}
mkdir -p "$B"; B=$(cd "$B" && pwd)

# 1. Stock shader sources from Engine/shaders.pak (ShadowCommon.cfi is only needed by tools/compat).
python3 -I - "$GAME/Engine/shaders.pak" "$B/stock" <<'EOF'
import sys, zipfile, os
pak, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
with zipfile.ZipFile(pak) as z:
    for name in ('Shaders/HWScripts/CryFX/ShadowMaskGen.cfx', 'Shaders/HWScripts/CryFX/ShadowCommon.cfi'):
        open(os.path.join(out, os.path.basename(name)), 'wb').write(z.read(name))
EOF

# 2. The mod shader: far contact shadows (make_sss_mod.py), then the Proton-compatible helpers and the
#    low-sun fix (make_compat.py). These are the 1.0.1 release settings.
python3 -I "$HERE/src/make_sss_mod.py" "$B/stock/ShadowMaskGen.cfx" "$B/base" "" \
    len=0.06 steps=24 thick=0.04 foliage=1 thin=1 folsplit=0.75:0.8,0.5:1 > /dev/null
python3 -I "$HERE/src/make_compat.py" "$B/base/src/ShadowMaskGen.cfx" "$B/mod" version=$VERSION ownsurface=1 > /dev/null

# 3. The game's shader cache without the two stock sun shadow shaders, so the game compiles the mod's.
python3 -I "$HERE/src/filter_pak.py" "$GAME/Engine/shadercache.pak" "$B/shadercache_fcs.pak" \
    Shaders/Cache/D3D11/cgpshaders/shadowmaskgen@deferredshadowps.fxcb \
    Shaders/Cache/D3D11/cgvshaders/shadowmaskgen@deferredshadowvs.fxcb > /dev/null

# 4. The release archive.
"$HERE/release/build_release.sh" "$B" "$VERSION"

# Compare with the published 1.0.1 build (game 1.9.8, Steam build 22623230).
check() {
    local got; got=$(sha256sum "$2" | cut -d' ' -f1)
    if [ "$got" = "$3" ]; then echo "  $1: matches release $VERSION"; else echo "  $1: differs from release $VERSION ($got)"; fi
}
echo "Checks:"
check "stock ShadowMaskGen.cfx" "$B/stock/ShadowMaskGen.cfx" 101111eccec487cc854ccf42b1e03095d6c957f023d7b60d18b7778a7c034c5b
check "Data/FarContactShadows.pak" "$B/mod/FarContactShadows/Data/FarContactShadows.pak" ee6b3e04792ad6000303c6e2319b1bea23be47490ad3eaa09dad34560f9836e0
check "mod.manifest" "$B/mod/FarContactShadows/mod.manifest" f1fd9adc51ba8d9950c290f996690a8bd24c8842cc271572efdb5f82e8b2b353
check "install/shadercache_fcs.pak" "$B/shadercache_fcs.pak" 09c8201b9b204797f93cfd2d3e477df84fa2bea4effe536b0eb405e412747b03
echo "A different stock file means a different game version: check the mod before using it there."
