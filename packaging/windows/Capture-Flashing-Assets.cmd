@echo off
setlocal
cd /d "%~dp0"
echo Load Hunter's Dream and press F8 while the assets are flashing.
echo Close the game after a few seconds. The launcher will package the captured frames.
echo Your graphics settings and saves are retained. This diagnostic run uses the serial renderer.
"%~dp0Bloodborne.exe" --play --geometry-diagnostic=capture
echo.
echo The diagnostic ZIP is in your user folder, under diagnostics, in the latest session folder.
pause
