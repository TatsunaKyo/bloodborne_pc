@echo off
setlocal
cd /d "%~dp0"
echo This comparison asks NVIDIA to show ONLY interpolated frames.
echo Keep NVIDIA FG enabled. This mode is temporary and does not measure normal gameplay FPS.
echo Watch the affected assets. Press F8 if you also want to capture the real source frames and FG inputs.
echo Close the game, then launch normally to return to the usual display mode.
"%~dp0Bloodborne.exe" --play --nvidia-diagnostic=generated-only
echo.
echo Any captured diagnostic is in your saves folder, under diagnostics, in the latest session folder.
echo Nothing has been uploaded and your saved graphics settings are unchanged.
pause
