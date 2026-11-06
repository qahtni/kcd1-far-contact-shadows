@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem Far Contact Shadows 1.0.2 - installer for Windows.
rem Double-click it in the extracted archive, wherever that is (Downloads, Mods\FarContactShadows, ...).
rem It finds the game itself: in the folder around it (Mods\<mod>), else in every Steam library,
rem else in the GOG Galaxy and Epic default folders. To pick a folder yourself, drag the game
rem folder onto this file.
rem What it does (nothing else):
rem   1. Checks the game is closed and Engine\shadercache.pak is the original KCD 1.9.8 file.
rem   2. Copies the mod to Mods\FarContactShadows (unless it is already there, e.g. from Vortex).
rem   3. Adds the mod to Mods\mod_order.txt if that file exists and does not list it yet.
rem   4. Renames Engine\shadercache.pak to Engine\shadercache.pak.original (your backup)
rem      and copies install\shadercache_fcs.pak to Engine\shadercache.pak.
rem   5. Copies the uninstaller to the game folder as FarContactShadows-Uninstall.bat.
rem Files are recognised by their exact size in bytes.
title Far Contact Shadows - install
set "STOCK=226389373"
set "TRIM=226262161"
set "SELF=%~dp0"
set "SELF=%SELF:~0,-1%"
set "ARG=%~1"
set "COPIED="
echo Far Contact Shadows 1.0.2 - install
call :findgame
if not defined GAME goto :nogame
if /i "%SELF%"=="%GAME%" (set "ERR=Extract the archive into a folder of its own, for example Downloads, not into the game folder itself." & goto :fail)
echo Game folder: "%GAME%"
set "E=%GAME%\Engine"
set "MODS=%GAME%\Mods"
set "NEW=%SELF%\install\shadercache_fcs.pak"
if not exist "%E%\shadercache.pak" (set "ERR=Engine\shadercache.pak is missing. Verify the game files in Steam first." & goto :fail)
tasklist /fi "imagename eq KingdomCome.exe" 2>nul | find /i "KingdomCome.exe" >nul && goto :running
if not exist "%SELF%\Data\FarContactShadows.pak" (set "ERR=Data\FarContactShadows.pak is missing from the mod folder." & goto :fail)
if not exist "%NEW%" (set "ERR=install\shadercache_fcs.pak is missing from the mod folder." & goto :fail)

echo Checking files...
call :size "%NEW%" SZ
if not "%SZ%"=="%TRIM%" (set "ERR=install\shadercache_fcs.pak is damaged. Download the mod again." & goto :fail)
call :size "%E%\shadercache.pak" CUR
set "ORIG="
if exist "%E%\shadercache.pak.original" call :size "%E%\shadercache.pak.original" ORIG
if "%CUR%"=="%STOCK%" if defined ORIG if not "%ORIG%"=="%STOCK%" (set "ERR=Engine\shadercache.pak.original exists but is not the original file. Move it somewhere else, then run this again." & goto :fail)
if not "%CUR%"=="%STOCK%" if not "%CUR%"=="%TRIM%" goto :notstock

rem 1. Mod files
set "MODDIR="
for %%I in ("%SELF%\..") do if /i "%%~fI"=="%MODS%" set "MODDIR=%SELF%"
if defined MODDIR goto :modready
for /d %%D in ("%MODS%\*") do if not defined MODDIR if exist "%%~fD\Data\FarContactShadows.pak" set "MODDIR=%%~fD"
if defined MODDIR findstr /m /i /l /c:"FarContactShadows.pak" "%MODS%\vortex.deployment*.json" >nul 2>&1 && goto :modready
if not defined MODDIR set "MODDIR=%MODS%\FarContactShadows"
if not exist "%MODDIR%\Data" mkdir "%MODDIR%\Data" 2>nul
copy /y "%SELF%\mod.manifest" "%MODDIR%\mod.manifest" >nul || goto :modfail
copy /y "%SELF%\Data\FarContactShadows.pak" "%MODDIR%\Data\FarContactShadows.pak" >nul || goto :modfail
copy /y "%SELF%\README.txt" "%MODDIR%\README.txt" >nul
set "COPIED=1"
:modready
for %%I in ("%MODDIR%") do set "NAME=%%~nxI"
if defined COPIED (echo Mod files: copied to "Mods\%NAME%".) else echo Mod files: "Mods\%NAME%" already in place.

rem 2. mod_order.txt (when it exists, the game loads only the mods listed in it)
set "MO=%MODS%\mod_order.txt"
if not exist "%MO%" (echo mod_order.txt: not present, nothing to add.& goto :cache)
findstr /x /i /l /c:"%NAME%" "%MO%" >nul && (echo mod_order.txt: already lists the mod.& goto :cache)
> "%MO%.fcs-tmp" (for /f "usebackq eol=| delims=" %%L in ("%MO%") do echo(%%L)
>> "%MO%.fcs-tmp" echo(%NAME%
move /y "%MO%.fcs-tmp" "%MO%" >nul || (set "ERR=Could not add the mod to Mods\mod_order.txt." & goto :fail)
echo mod_order.txt: added "%NAME%".

rem 3. Shader cache (last, so it never runs without the mod in place)
:cache
if "%CUR%"=="%TRIM%" (echo Shader cache: already installed.& goto :uninstaller)
if defined ORIG (echo Backup: Engine\shadercache.pak.original already there.& goto :copy)
move /y "%E%\shadercache.pak" "%E%\shadercache.pak.original" >nul || (set "ERR=Could not rename Engine\shadercache.pak. Try right-click, Run as administrator." & goto :fail)
echo Backup: Engine\shadercache.pak renamed to shadercache.pak.original
:copy
copy /y /b "%NEW%" "%E%\shadercache.pak.fcs-tmp" >nul || goto :copyfail
move /y "%E%\shadercache.pak.fcs-tmp" "%E%\shadercache.pak" >nul || goto :copyfail
call :size "%E%\shadercache.pak" CUR
if not "%CUR%"=="%TRIM%" (set "ERR=The copied Engine\shadercache.pak does not match. Run the uninstaller, then try again." & goto :fail)
echo Shader cache: installed.

:uninstaller
copy /y "%SELF%\Uninstall-Windows.bat" "%GAME%\FarContactShadows-Uninstall.bat" >nul && echo Uninstaller copied to the game folder: FarContactShadows-Uninstall.bat
echo.
echo Done. Start the game; the first start builds the new shadow shader once.
echo To remove the mod, run FarContactShadows-Uninstall.bat in the game folder FIRST.
echo (Without the original shader cache back, the game has no sun shadows.)
echo.
pause
exit /b 0

:modfail
set "ERR=Could not copy the mod to the Mods folder. Try right-click, Run as administrator."
goto :fail
:copyfail
del /q "%E%\shadercache.pak.fcs-tmp" 2>nul
if not exist "%E%\shadercache.pak" move /y "%E%\shadercache.pak.original" "%E%\shadercache.pak" >nul
set "ERR=Copying the shader cache failed (disk full or no permission). The original file is back in place. Try right-click, Run as administrator."
goto :fail
:notstock
set "ERR=Engine\shadercache.pak is not the original KCD 1.9.8 file (another mod changed it, or a different game version). Restore it with Steam: right-click the game, Properties, Installed Files, Verify integrity of game files. Then run this again."
goto :fail
:nogame
set "ERR=Kingdom Come: Deliverance not found. Drag the game folder (the one with Bin, Data and Engine) onto this file."
goto :fail
:running
set "ERR=The game is running. Close it first."
:fail
echo.
setlocal EnableDelayedExpansion
echo ERROR: !ERR!
endlocal
echo Nothing more was changed.
echo.
pause
exit /b 1

:size
set "%~2=%~z1"
exit /b

rem Game folder search: around this file, the dragged folder, Steam libraries, GOG/Epic defaults.
:findgame
set "GAME="
for %%I in ("%SELF%\..\..") do if exist "%%~fI\Bin\Win64\KingdomCome.exe" set "GAME=%%~fI"
if defined GAME exit /b
if exist "%SELF%\Bin\Win64\KingdomCome.exe" (set "GAME=%SELF%" & exit /b)
if defined ARG call :trydir "%ARG%"
if defined GAME exit /b
set "STEAM="
for /f "tokens=2,*" %%A in ('reg query "HKCU\Software\Valve\Steam" /v SteamPath 2^>nul ^| find /i "SteamPath"') do set "STEAM=%%B"
if not defined STEAM set "STEAM=%ProgramFiles(x86)%\Steam"
set "STEAM=%STEAM:/=\%"
call :trylib "%STEAM%"
if exist "%STEAM%\steamapps\libraryfolders.vdf" for /f usebackq^ tokens^=2^,4^ delims^=^" %%A in ("%STEAM%\steamapps\libraryfolders.vdf") do if /i "%%A"=="path" call :trylib "%%B"
if defined GAME exit /b
call :trydir "%ProgramFiles(x86)%\GOG Galaxy\Games\Kingdom Come Deliverance"
call :trydir "%ProgramFiles%\Epic Games\KingdomComeDeliverance"
exit /b
:trylib
if defined GAME exit /b
set "L=%~1"
set "L=%L:\\=\%"
call :trydir "%L%\steamapps\common\KingdomComeDeliverance"
exit /b
:trydir
if not defined GAME if exist "%~1\Bin\Win64\KingdomCome.exe" set "GAME=%~f1"
exit /b
