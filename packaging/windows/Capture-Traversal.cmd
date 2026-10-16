@echo off
setlocal
cd /d "%~dp0"
echo Keep your usual settings, including your current FG on/off choice.
echo Reproduce the cemetery traversal hitch, then close the game. No F8 press is needed.
echo This records CPU operations while preserving parallel rendering and keeping GPU profiling off.
echo No gameplay images are read back and nothing is uploaded.
"%~dp0Bloodborne.exe" --play --traversal-diagnostic
echo.
echo Inspect Traversal-diagnostic.zip under user/diagnostics in the latest session folder.
pause
