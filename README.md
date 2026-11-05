# Far Contact Shadows - Expanded Screen Space Shadows

A mod for **Kingdom Come: Deliverance** (1.9.8), by mrtaxerman.

The game's sun screen-space shadows (contact shadows) only run in the nearest sun shadow cascade and fade out after about 3 m. This mod runs them in every sun shadow cascade, so they reach as far as the sun shadows do (about 250 m at the highest shadow setting), and lets grass and foliage receive them.

## Changes

- Screen-space sun shadows run in all sun shadow cascades instead of the first one only.
- Ray length, depth bias and thickness scale with view distance.
- The 3 m fade-out is removed.
- Grass and foliage receive screen-space shadows. Shadows cast by foliage use separate thickness and strength on foliage and on other surfaces.
- Only the sun shadow shader (`ShadowMaskGen.cfx`) is changed.

How it works, and why it needs a shader cache swap: [HOW-IT-WORKS.md](HOW-IT-WORKS.md).

## Download

Get `FarContactShadows-1.0.1.7z` from [Releases](../../releases) or [Nexus Mods](https://www.nexusmods.com/kingdomcomedeliverance/mods/2455). It holds the mod, the shader cache and the installers.

## Install

**Windows**
1. Extract the archive anywhere, for example to Downloads.
2. Double-click `Install-Windows.bat` in the extracted folder.

The installer finds the game in your Steam libraries (and in the GOG Galaxy and Epic default folders), copies the mod to `Mods\FarContactShadows` and installs the shader cache. If it can't find the game, drag the game folder onto `Install-Windows.bat`.

**Vortex**
1. Install and enable the mod in Vortex (Vortex adds it to `mod_order.txt`).
2. In Vortex, right-click the mod > Open in File Manager, and double-click `Install-Windows.bat`. It leaves the mod files to Vortex and only installs the shader cache.

**Steam Deck / Linux**

Needs Proton 9.0 or newer (Steam's default Proton is fine). With Proton 8 or older the game can't build the new shadow shader and shows no sun shadows.
1. Switch to Desktop Mode and extract the archive anywhere, for example to Downloads.
2. Right-click an empty spot in the extracted folder > Open Terminal Here, type `bash Install-Linux-SteamDeck.sh` and press Enter.

It finds the game in every Steam library (SD card included, also Flatpak Steam) and in `~/Games` (Heroic, Lutris). For a game somewhere else, add its folder: `bash Install-Linux-SteamDeck.sh "/path/to/KingdomComeDeliverance"`

**By hand (no script)**

In the game folder (Steam: right-click the game > Manage > Browse local files; it holds Bin, Data, Engine and Mods):
1. Create `Mods\FarContactShadows` and copy `mod.manifest` and the `Data` folder into it.
2. In `Engine`, rename `shadercache.pak` to `shadercache.pak.original`.
3. Copy `install\shadercache_fcs.pak` into `Engine` and rename the copy to `shadercache.pak`.
4. If `Mods\mod_order.txt` exists, add `FarContactShadows` on a new line.

The installers check `Engine\shadercache.pak` first and change nothing if it is not the original 1.9.8 file. They keep the original as `Engine\shadercache.pak.original` and put an uninstaller in the game folder. The first start after installing builds the new shadow shader once.

**Updating from 1.0:** install 1.0.1 the same way (run the installer again, or let Vortex replace the mod). Only the mod files change; the shader cache from 1.0 stays.

## Uninstall: do this before you remove or disable the mod

Without the original `Engine\shadercache.pak` the game has no sun shadows at all, so disabling the mod in Vortex or in `mod_order.txt` is not enough.

- **With the script:** in the game folder, double-click `FarContactShadows-Uninstall.bat` (Windows), or run `bash FarContactShadows-Uninstall.sh` (Steam Deck / Linux). It restores the original cache and deletes `Mods\FarContactShadows`. With Vortex, remove the mod in Vortex afterwards.
- **By hand:** in `Engine`, delete `shadercache.pak` and rename `shadercache.pak.original` back to `shadercache.pak`. Then remove the mod in Vortex, or delete `Mods\FarContactShadows` and its line in `mod_order.txt`.
- **No backup, or the mod is already gone:** in Steam, right-click the game > Properties > Installed Files > Verify integrity of game files.

## Notes

- Made for game version 1.9.8. Steam's "Verify integrity" or a game update puts the original shader cache back; that turns the mod off (normal shadows). Run the installer again.
- Not compatible with other mods that replace the shader cache or `ShadowMaskGen.cfx`, including mods that add their own shader cache paks through `Data\pak.cfg`.
- The console command `r_ShadowsScreenSpace 0` no longer turns these shadows off. Uninstall the mod instead.
- At the Low shadow setting the base game turns contact shadows off; with this mod they stay on.
- Reach depends on the shadow quality setting (number of sun shadow cascades).

## Building from source

The repo holds no game files. `build.sh` reads the stock shader and shader cache from your own copy of the game and builds the same release archive:

```
./build.sh "/path/to/KingdomComeDeliverance"      # writes ./build/FarContactShadows-1.0.1.7z
```

Needs Python 3 and 7-Zip (`7z`). With game 1.9.8 every file in the archive is byte-identical to the published 1.0.1 release, and the script prints that check.

| Path | What |
|---|---|
| `src/make_sss_mod.py` | Patches the stock `ShadowMaskGen.cfx`: far-reaching contact shadow function, all cascades, foliage settings. Every replacement must match the stock text exactly once. |
| `src/make_compat.py` | Float-only copies of the stock helpers so Proton's shader compiler can build the shader, plus the 1.0.1 low-sun fix (`ownsurface=1`). Writes the mod pak. |
| `src/filter_pak.py` | Copies the game's `shadercache.pak` without the two stock sun shadow shaders. |
| `release/` | Installers, uninstallers, the archive README and `build_release.sh`. |
| `tools/compat/` | Compiler test bench: builds every shader permutation with Microsoft's compiler and each Proton vkd3d-shader version ([README](tools/compat/README.md)). |
| `tools/media/` | Scripts for the Nexus banner, thumbnail and comparison GIFs. They draw text in the game's menu font, read from your own `Data/GameData.pak` (`Libs/UI/gfxfontlib_glyphs.gfx`); the font is not in this repo. |

## License

The code in this repository is released into the public domain under [The Unlicense](LICENSE): do whatever you want with it.

The mod changes Warhorse Studios' `ShadowMaskGen.cfx` (CRYENGINE), and the release archive carries the game's own shader cache. Those game files stay the property of their owners and are not covered by the Unlicense.
