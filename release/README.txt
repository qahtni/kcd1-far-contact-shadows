FAR CONTACT SHADOWS 1.0.2
Expanded Screen Space Shadows
Kingdom Come: Deliverance (1.9.8)
Author: mrtaxerman

The game's sun screen-space shadows (contact shadows) only run in the
nearest sun shadow cascade and fade out after about 3 m. This mod runs them
in every sun shadow cascade, so they reach as far as the sun shadows do
(about 250 m at the highest shadow setting), and lets grass and foliage
receive them. Shadows cast by foliage use separate thickness and strength
on foliage and on other surfaces.

FILES IN THIS ARCHIVE
- mod.manifest, Data\FarContactShadows.pak: the mod (modified ShadowMaskGen
  shader).
- install\shadercache_fcs.pak: the game's 1.9.8 shader cache without the two
  stock sun shadow shaders, so the game builds the modded one instead. The
  installer copies it to Engine\shadercache.pak. The game ignores shader
  cache files inside the Mods folder, which is why this step is needed.
- Install-Windows.bat, Uninstall-Windows.bat
- Install-Linux-SteamDeck.sh, Uninstall-Linux-SteamDeck.sh
  Plain text: open them in a text editor to see exactly what they do.

INSTALL (WINDOWS)
1. Extract the archive anywhere, for example to Downloads.
2. Double-click Install-Windows.bat in the extracted folder.
The installer finds the game in your Steam libraries (and in the GOG Galaxy
and Epic default folders), copies the mod to Mods\FarContactShadows and
installs the shader cache. If it can't find the game, drag the game folder
onto Install-Windows.bat.

INSTALL WITH VORTEX
1. Install and enable the mod in Vortex (Vortex adds it to mod_order.txt).
2. In Vortex, right-click the mod > Open in File Manager, and double-click
   Install-Windows.bat. It leaves the mod files to Vortex and only installs
   the shader cache.

INSTALL ON STEAM DECK / LINUX
1. Switch to Desktop Mode and extract the archive anywhere, for example to
   Downloads.
2. Right-click an empty spot in the extracted folder > Open Terminal Here,
   type
     bash Install-Linux-SteamDeck.sh
   and press Enter.
It finds the game in every Steam library (SD card included, also Flatpak
Steam) and in ~/Games (Heroic, Lutris). For a game somewhere else, add its
folder: bash Install-Linux-SteamDeck.sh "/path/to/KingdomComeDeliverance"
Needs Proton 9.0 or newer (Steam's default Proton is fine). With Proton 8 or
older the game can't build the new shadow shader and shows no sun shadows.
To check: right-click the game > Properties > Compatibility.

UPDATING FROM 1.0 OR 1.0.1
Install 1.0.2 the same way: run the installer again, or let Vortex replace
the mod. Only the mod files change; the shader cache from 1.0 stays. The
first start after updating builds the new shadow shader once.

INSTALL BY HAND (NO SCRIPT)
To open the game folder: in Steam, right-click Kingdom Come: Deliverance >
Manage > Browse local files. It holds Bin, Data, Engine and Mods.
1. In the game folder, create Mods\FarContactShadows (create Mods first if
   it is not there) and copy mod.manifest and the Data folder into it.
2. In Engine, rename shadercache.pak to shadercache.pak.original.
3. Copy install\shadercache_fcs.pak into Engine and rename the copy to
   shadercache.pak.
4. If Mods\mod_order.txt exists, add FarContactShadows on a new line.

The installer checks Engine\shadercache.pak first and changes nothing if it
is not the original 1.9.8 file. It keeps the original as
Engine\shadercache.pak.original and puts an uninstaller in the game folder.
The first start after installing builds the new shadow shader once.

UNINSTALL: DO THIS BEFORE YOU REMOVE OR DISABLE THE MOD
Without the original Engine\shadercache.pak the game has no sun shadows at
all, so disabling the mod in Vortex or in mod_order.txt is not enough.
- With the script: in the game folder, double-click
  FarContactShadows-Uninstall.bat (Windows), or run
    bash FarContactShadows-Uninstall.sh
  (Steam Deck / Linux). Uninstall-Windows.bat / Uninstall-Linux-SteamDeck.sh
  in the extracted archive do the same. It restores the original cache and
  deletes Mods\FarContactShadows. With Vortex, remove the mod in Vortex
  afterwards.
- By hand: in Engine, delete shadercache.pak and rename
  shadercache.pak.original back to shadercache.pak. Then remove the mod in
  Vortex, or delete Mods\FarContactShadows and its line in mod_order.txt.
- No backup, or the mod is already gone: in Steam, right-click the game >
  Properties > Installed Files > Verify integrity of game files. It
  downloads the original shader cache again.

GOOD TO KNOW
- Steam's "Verify integrity" or a game update puts the original shader cache
  back. That turns the mod off (normal shadows); run the installer again.
- Does not work together with other mods that replace the shader cache or
  ShadowMaskGen.cfx, including mods that add their own shader cache paks to
  Engine through Data\pak.cfg.
- The console command r_ShadowsScreenSpace 0 no longer turns these shadows
  off. Uninstall the mod instead.
- At the Low shadow setting the base game turns contact shadows off; with
  this mod they stay on.
- Reach depends on the shadow quality setting.
- The backup keeps the original 226 MB shader cache next to the new one.

CHANGES
1.0.2
- Tents, awnings, laundry and other hanging cloth: no more dark wedges and
  lines on the cloth where the sun shines through it (for example inside a
  tent), and no dark line where a tent wall meets the floor. The sunlit side
  keeps its contact shadows.
1.0.1
- Fixed a dark square around the sun when facing a low sun (sunrise,
  sunset), mostly at low resolutions such as the Steam Deck's, and dark
  bands on flat ground with a low sun from the side.
1.0
- First release.
