@echo off
setlocal
cd /d "%~dp0"
echo Keep NVIDIA Frame Generation enabled and use your normal graphics settings.
echo First reproduce the cemetery traversal hitch. Short CPU operations and their execution threads are recorded.
echo In the affected scene, press F8 while the assets flash. Close the game a few seconds later.
echo This captures four real backbuffers and the exact depth, motion and camera inputs tagged for NVIDIA.
echo It preserves parallel rendering. GPU timestamp profiling stays off. Readback may affect timing after F8.
echo No files are uploaded.
"%~dp0Bloodborne.exe" --play --nvidia-diagnostic=inputs
echo.
echo Inspect NVIDIA-FG-diagnostic.zip in your saves folder, under diagnostics, in the latest session folder.
pause
