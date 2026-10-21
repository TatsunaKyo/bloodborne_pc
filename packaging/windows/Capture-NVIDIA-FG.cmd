@echo off
setlocal
cd /d "%~dp0"
echo For traversal alone, use Capture-Traversal.cmd with FG on or off.
echo This run also records CPU operations, independently of FG. A log ZIP is saved even without F8.
echo To capture NVIDIA's tagged images, keep NVIDIA Frame Generation enabled and use normal graphics settings.
echo First reproduce the cemetery traversal hitch.
echo In the affected scene, press F8 while the assets flash. Close the game a few seconds later.
echo This captures four real backbuffers and the exact depth, motion and camera inputs tagged for NVIDIA.
echo It preserves parallel rendering. GPU timestamp profiling stays off. Readback may affect timing after F8.
echo No files are uploaded.
"%~dp0Bloodborne.exe" --play --nvidia-diagnostic=inputs
echo.
echo Inspect NVIDIA-FG-diagnostic.zip in your saves folder, under diagnostics, in the latest session folder.
pause
