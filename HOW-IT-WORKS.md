# How it works

Game build analysed: Kingdom Come: Deliverance 1.9.8 (Steam build 22623230). The sun shadow shader `ShadowMaskGen.cfx` has not changed since game version 1.3 (2018).

## Why the stock contact shadows stop at about 3 m

Four limits stack up. Removing one alone does not give far contact shadows.

| Limit | Where | Effect |
|---|---|---|
| Distance fade | `ShadowCommon.cfi`, `CalculateDetailSSShadow`: `lerp(fInSSS, 1, saturate(depth_m - 2))` | Full contact shadows up to 2 m view depth, none past 3 m. A hard-coded literal, not a cvar. |
| Tiny ray | same function: 16 steps, first step 1.5 mm, x1.05 per step | The last sample is 3.4 cm from the surface: about 21 px at 3 m and 6 px at 10 m at 4K. It only catches contact-scale blockers. |
| First cascade only | renderer (`FX_DeferredShadowPass`) | The screen-space flag is set only for the cascade-0 shadow pass (`nShadowMapLod == 0`), so only pixels covered by the nearest cascade get contact shadows. |
| Cascade edge fade | `ShadowMaskGen.cfx`, `DeferredShadowPS` | The result is multiplied by cascade 0's edge fade and blend, so it dies at that cascade's border. |

The only related cvar is `r_ShadowsScreenSpace` (0 off, 1 sun, 2 all lights). No cvar changes the reach.

## What the mod changes

Everything happens in `ShadowMaskGen.cfx`; the shared `ShadowCommon.cfi` (included by 17 shaders) is not touched.

- **A new local function, `CalculateFarSSShadow`,** modelled on Crysis Remastered's screen-space shadows:
  - ray length = 6 % of view depth, never shorter than the stock 3.4 cm, 24 steps;
  - rays that project long on screen are shortened (the Crysis screen-length scale);
  - depth bias = 0.2 % of depth, at least the stock 1 cm;
  - blocker thickness grows with depth, at least the stock 3 cm;
  - no near fade; the only fade is at 1000-1200 m, past the last sun cascade.
  Near the camera it matches the stock ray.
- **It runs in every sun cascade pass,** not only cascade 0, so the reach is the end of the last cascade. With 5 cascades (`e_GsmRange 3`, step 3) that is about 3, 9, 27, 81 and 243 m. Past the last cascade there is no sun shadow pass to run in.
- **Grass and foliage receive contact shadows.** Stock skips surfaces with the transmittance lighting model (grass, leaves, tents).
- **Foliage blockers are thin.** Treating a grass blade as a blocker as thick as a wall draws dark columns on the ground. Foliage blockers use separate thickness and strength: 3/4 thickness at 80 % strength when the shadow falls on ground, rock or wood, and 1/2 thickness at 100 % when it falls on foliage. No G-buffer value tells grass from tree leaves, so the receiving surface is the switch.

## Why the shader cache has to be replaced

The game compiles shader source at runtime, but only for shaders missing from its caches. `Engine/shadercache.pak` holds precompiled stock versions of the two sun shadow shaders (`shadowmaskgen@deferredshadowps.fxcb` and `@deferredshadowvs.fxcb`), and the game keeps drawing those even when a mod pak supplies new source.

Shader cache data in the Mods folder is ignored: both header-only stub caches and a `lookupdata.bin` without the two entries were tried, and the game still used the stock shaders. What works is a copy of `shadercache.pak` without those two entries (`src/filter_pak.py`): the game finds no precompiled version, compiles the mod's source once, and stores it in the user shader cache.

The catch: with the trimmed cache and the mod **not** loaded, the stock sun shadow pixel shader does not compile at runtime, so there are no sun shadows at all. That is why uninstalling must restore the original cache.

## Proton / Steam Deck

Under Proton the game does not use its own Microsoft `Bin/Win64Shared/d3dcompiler_47.dll`. It loads Proton's builtin `d3dcompiler_47`, which is built on vkd3d-shader. The stock helper functions the shader calls do not compile with several versions:

| Proton | vkd3d-shader | Stock helpers |
|---|---|---|
| 8.0 | 1.8 | fail: default arguments. The mod's own `[loop]` with `break` fails too, so Proton 8 is not supported |
| 9.0 | 1.14 | fail: cast on the left-hand side of an out parameter |
| 10.0 | 1.18 | compiler hangs |
| 11.0 | 2.0 | fail: SM4 half negation, dot and max not implemented |
| Experimental, GE-Proton 11, proton-cachyos | 2.1 | work |

A failed compile means no sun shadows at all, retried every frame, with nothing in `kcd.log`.

`src/make_compat.py` gives the sun shadow pixel shader its own float-only copies of those helpers (`FcsSceneDepth`, `FcsLightingModel`, `FcsSunSelfShadowing`, `FcsCalcShadow` with the filter taps written out per quality level). The maths is the same, and the stock helpers stay in place for every other shader. On Windows, Microsoft's compiler treats `half` as `float` in shader model 5, so the result there does not change.

Test bench (`tools/compat/`): all 128 permutations of the pixel shader compile with Microsoft's compiler and with vkd3d-shader 1.14, 1.18, 2.0 and 2.1, 640 of 640.

## 1.0.1: the dark square around a low sun

Facing a low sun, the screen-space ray points into the screen. Each step moved only 1/400 of the way toward the sun's screen position, so within about 200 px of the sun the first steps stayed in the starting pixel. That pixel is the receiver itself, so the surface shadowed itself: a dark square around the sun. At 1280x800 (Steam Deck) the square was about 400 px wide; at 4K it is a small patch. The same mistake one pixel over darkened flat ground under a low sun from the side.

Fix (`ownsurface=1` in `make_compat.py`): a surface cannot shadow itself. 1/depth of a plane is linear across the screen, so the shader builds the receiving surface's plane from its 4 nearest depths (the flatter side of each pair, so silhouettes don't count) and skips samples that lie on that plane (within 0.5 % of depth plus one pixel's depth change). In a numeric model at 1280x800 the falsely darkened share of sunlit flat ground dropped from 17 % to 0.0 % facing the sun, and from 9.6-20 % to 0.0 % with a low side sun. Cost: 4 depth reads per pixel and 3 lines per step.

Trade-off: at a very low sun, small terrain bumps cast fewer contact shadows into the hollows next to them. Objects that stand above the ground (rocks, posts, grass) are not affected.

## 1.0.2: dark wedges on tent cloth

Tents, awnings, laundry and curtains are drawn with the foliage shader as thin translucent sheets, and the sun shadow maps let the sun through them (the floor inside a tent is sunlit). The contact-shadow ray did not know that. Inside a tent the ray toward the sun passes through the curved wall, so the wall's own folds, its bend toward the floor and its seams read as blockers: dark wedges on the walls and a dark line where the wall meets the floor.

Fix, all in `make_compat.py`:

- **Recognise cloth in the G-buffer** (`nocloth=1`): translucent, no skin profile, and the translucency colour of one of the game's cloth presets (grey, or orange for curtains), which no plant uses. Cloth on a preset that plants share (the Cuman tents and a few others) is told apart by its stored specular value as well (`speckeys=1`). Where a seam decal is blended over that cloth (the floor hem), the shader accepts values on the line between the cloth's and the decal's (`decalkeys=1`). All 363 translucent foliage-shader materials in the game's paks were checked against these rules.
- **No contact shadows where the sun shines through cloth**: the ray toward the sun ends behind the cloth's own plane (the plane test from 1.0.1). The sunlit side keeps its contact shadows.
- **Cloth never blocks a contact-shadow ray** (`clothblock=1`), the same as in the sun shadow maps.

Trade-off: cloth folds cast no contact shadows on either side. Poles, people and props still cast contact shadows on cloth.

## Known side effects

- `r_ShadowsScreenSpace 0` no longer turns sun contact shadows off; the mod's code does not check it.
- At the Low shadow setting the game reuses the Medium shader variants and sets `r_ShadowsScreenSpace 0`, so with the mod contact shadows stay on at Low.
- The grass along the Vranik palisade and a few small forest roots share a Cuman tent's material values, so the mod treats them as cloth: they cast no contact shadows and get none where the sun shines through them.
- If a game update changes `ShadowMaskGen.cfx`, the mod's copy hides the new version. `build.sh` reports when the stock file differs from 1.9.8.
