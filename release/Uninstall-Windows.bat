@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem Far Contact Shadows 1.0.1 - uninstaller for Windows.
rem Works from the game folder (the installer leaves a copy there as FarContactShadows-Uninstall.bat),
rem from Mods\FarContactShadows, or from the extracted archive anywhere else (it then finds the game
rem the same way the installer does; or drag the game folder onto this file).
rem What it does:
rem   1. Puts the original Engine\shadercache.pak back from Engine\shadercache.pak.original.
rem   2. Deletes the mod folder and its line in Mods\mod_order.txt
rem      (skipped for a Vortex-installed copy: remove that one in Vortex).
rem   3. Deletes FarContactShadows-Uninstall.bat from the game folder.
rem Files are recognised by their exact size in bytes.
title Far Contact Shadows - uninstall
set "STOCK=226389373"
set "TRIM=226262161"
set "SELF=%~dp0"
set "SELF=%SELF:~0,-1%"
set "ARG=%~1"
set "SELFDEL="
echo Far Contact Shadows 1.0.1 - uninstall
call :findgame
if not defined GAME goto :nogame
echo Game folder: "%GAME%"
set "E=%GAME%\Engine"
set "MODS=%GAME%\Mods"
tasklist /fi "imagename eq KingdomCome.exe" 2>nul | find /i "KingdomCome.exe" >nul && goto :running

echo Checking files...
set "CUR=" & set "ORIG="
if exist "%E%\shadercache.pak" call :size "%E%\shadercache.pak" CUR
if exist "%E%\shadercache.pak.original" call :size "%E%\shadercache.pak.original" ORIG
if "%CUR%"=="%STOCK%" goto :isstock
if not "%ORIG%"=="%STOCK%" goto :nobackup
if not "%CUR%"=="" if not "%CUR%"=="%TRIM%" echo Note: Engine\shadercache.pak was changed by something else; replacing it with the original anyway.
move /y "%E%\shadercache.pak.original" "%E%\shadercache.pak" >nul || (set "ERR=Could not restore Engine\shadercache.pak. Try right-click, Run as administrator." & goto :fail)
echo Shader cache: original restored.
goto :mods
:isstock
echo Shader cache: already the original.
if "%ORIG%"=="%STOCK%" del /q "%E%\shadercache.pak.original" && echo Removed the spare backup Engine\shadercache.pak.original.

:mods
set "VORTEX="
findstr /m /i /l /c:"FarContactShadows.pak" "%MODS%\vortex.deployment*.json" >nul 2>&1 && set "VORTEX=1"
for /d %%D in ("%MODS%\*") do if exist "%%~fD\Data\FarContactShadows.pak" call :removemod "%%~fD"
if /i not "%SELF%"=="%GAME%" del /q "%GAME%\FarContactShadows-Uninstall.bat" 2>nul
echo.
echo Done. The game is back to its original shadows.
echo.
pause
if defined SELFDEL goto :delmodfolder
if /i "%SELF%"=="%GAME%" goto :delself
exit /b 0

:removemod
set "D=%~1"
set "N=%~nx1"
if defined VORTEX (echo "Mods\%N%" was installed by Vortex: remove the mod in Vortex now.& exit /b)
if not exist "%MODS%\mod_order.txt" goto :rmmod
findstr /v /x /i /l /c:"%N%" "%MODS%\mod_order.txt" > "%MODS%\mod_order.txt.fcs-tmp"
move /y "%MODS%\mod_order.txt.fcs-tmp" "%MODS%\mod_order.txt" >nul && echo mod_order.txt: removed "%N%".
:rmmod
if /i "%D%"=="%SELF%" (set "SELFDEL=1" & echo "Mods\%N%" gets deleted after you press a key.& exit /b)
rmdir /s /q "%D%" && echo Deleted "Mods\%N%".
exit /b

:delmodfolder
(goto) 2>nul & cd /d "%GAME%" & rmdir /s /q "%SELF%"
:delself
(goto) 2>nul & del /q "%~f0"

:nobackup
set "ERR=The backup Engine\shadercache.pak.original is missing or changed. Get the original back with Steam: right-click the game, Properties, Installed Files, Verify integrity of game files. Until then the game has no sun shadows."
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
