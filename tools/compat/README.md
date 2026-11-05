# Shader compiler test bench

Compiles the mod's sun shadow pixel shader (`DeferredShadowPS`) in all 128 permutations it uses, with the game's Microsoft compiler and with each vkd3d-shader version Proton ships. Runs under Wine.

| File | What |
|---|---|
| `fxc_lite.c` | Compiles one HLSL file with a given `d3dcompiler_47.dll` (`D3DCompile`); exit code 0 only on success. |
| `vkd3d_lite.c` | Same job with a given `libvkd3d-shader-1.dll`, the compiler behind Proton's `d3dcompiler_47`. |
| `dxbc_disasm.c` | Prints the disassembly of a compiled DXBC shader, for byte-level comparisons. |
| `compat_harness.py` | Builds engine-style HLSL for one permutation from a dumped engine shader, the stock `ShadowCommon.cfi` and the mod's `ShadowMaskGen.cfx`. |
| `compat_matrix.sh` | Runs all 128 permutations through Microsoft's compiler and vkd3d-shader 1.14, 1.18, 2.0 and 2.1; one line per compile, summary at the end. |

Build the tools (MinGW-w64):

```
x86_64-w64-mingw32-gcc -O1 -o fxc_lite.exe fxc_lite.c
x86_64-w64-mingw32-gcc -O1 -o vkd3d_lite.exe vkd3d_lite.c
x86_64-w64-mingw32-gcc -O1 -o dxbc_disasm.exe dxbc_disasm.c
```

Inputs (none of them are in this repo):

- **Engine dump:** the exact HLSL the game sends to the compiler. On Proton, start the game with `VKD3D_SHADER_DUMP_PATH=/some/folder` (for example from Proton's `user_settings.py`), then take the `*-source.hlsl` file for `DeferredShadowPS`.
- **Bench folder:** subfolders `v1.14`, `v1.18`, `v2.0`, `v2.1`, each holding the 64-bit `libvkd3d-shader-1.dll` from Proton 9.0, 10.0, 11.0 and Experimental (or GE-Proton 11).
- **`SHADOWCOMMON`:** the stock `ShadowCommon.cfi`. `../../build.sh` writes it to `build/stock/`.
- **`D3DCOMPILER`:** the game's `Bin/Win64Shared/d3dcompiler_47.dll`.

```
SHADOWCOMMON=build/stock/ShadowCommon.cfi D3DCOMPILER=/path/to/game/Bin/Win64Shared/d3dcompiler_47.dll \
  tools/compat/compat_matrix.sh build/mod/src/ShadowMaskGen.cfx dump.hlsl /path/to/bench matrix.tsv
```

Release 1.0.1: 640 of 640 compiles pass.
