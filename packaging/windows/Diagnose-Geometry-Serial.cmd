@echo off
cd /d "%~dp0"
echo Starting a one-run geometry reference. This can reduce FPS.
echo Draw preparation, two-stage draws, deferred Vulkan recording and copy workers are off.
echo Your graphics, FG, saves and saved launcher preferences are retained.
"%~dp0Bloodborne.exe" --play --geometry-diagnostic=serial
echo The session log and settings are in your user folder under diagnostics.
pause
