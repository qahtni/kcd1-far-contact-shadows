#!/bin/bash
# Compile DeferredShadowPS from a mod ShadowMaskGen.cfx in every %_RT_ permutation it uses, with the game's
# Microsoft d3dcompiler_47 and each Proton vkd3d-shader in BENCH/v*/ (Proton 9 = 1.14, 10 = 1.18,
# 11.0 = 2.0, Experimental/GE = 2.1). One line per compile in OUT; summary at the end.
# usage: compat_matrix.sh MOD_ShadowMaskGen.cfx ENGINE_DUMP.hlsl BENCH_DIR OUT.tsv
# Environment:
#   SHADOWCOMMON  stock ShadowCommon.cfi (../../build.sh writes it to build/stock/)
#   D3DCOMPILER   the game's Microsoft Bin/Win64Shared/d3dcompiler_47.dll
#   BIN           folder with fxc_lite.exe and vkd3d_lite.exe (default: this folder; see README.md)
#   WINEPREFIX    optional; any 64-bit Wine prefix
set -u
H=$(cd "$(dirname "$0")" && pwd)
MOD=$1 DUMP=$2 BENCH=$3 OUT=$4
CF=${SHADOWCOMMON:?set SHADOWCOMMON to the stock ShadowCommon.cfi}
BIN=${BIN:-$H}
export WINEDEBUG=-all
MSDLL='Z:'$(echo "${D3DCOMPILER:?set D3DCOMPILER to the d3dcompiler_47.dll from the game Bin/Win64Shared folder}" | tr / '\\')
T=$(mktemp -d -p "$BENCH" matrix.XXXX)
: > "$OUT"
for m in $(seq 0 127); do
  f="QUALITY=$((m & 1)) QUALITY1=$((m >> 1 & 1)) SHADOW_JITTERING=$((m >> 2 & 1)) SAMPLE1=$((m >> 3 & 1)) SAMPLE2=$((m >> 4 & 1)) SAMPLE3=$((m >> 5 & 1)) SHADOW_MIXED_MAP_G16R16=$((m >> 6 & 1))"
  python3 -I "$H/compat_harness.py" "$DUMP" "$CF" "$MOD" "$T/p.hlsl" $f > /dev/null || { echo "$m	harness	FAIL" >> "$OUT"; continue; }
  r=$(cd "$T" && timeout 60 wine "$BIN/fxc_lite.exe" "$MSDLL" p.hlsl DeferredShadowPS ps_5_0 1000 2>&1 | grep -o "hr=0x[0-9a-f]*")
  echo "$m	MS	$r	$f" >> "$OUT"
  for d in "$BENCH"/v1.14 "$BENCH"/v1.18 "$BENCH"/v2.0 "$BENCH"/v2.1; do
    o=$(cd "$T" && timeout 60 wine "$BIN/vkd3d_lite.exe" "$d/libvkd3d-shader-1.dll" p.hlsl DeferredShadowPS ps_5_0 8:1 2>&1); rc=$?
    r=$(echo "$o" | grep -o "ret=-*[0-9]*" | head -1); [ $rc = 124 ] && r=HANG; [ -z "$r" ] && r=CRASH
    e=$(echo "$o" | grep -m1 -o "E[0-9]*: .*" | cut -c1-100)
    echo "$m	$(basename "$d")	$r	$f	$e" >> "$OUT"
  done
done
rm -rf "$T"
echo "== summary (compiler, result, count)"
awk -F'\t' '{print $2" "$3}' "$OUT" | sort | uniq -c
