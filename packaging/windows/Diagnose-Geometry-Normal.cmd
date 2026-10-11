@echo off
cd /d "%~dp0"
echo Starting Revision 17 with your usual renderer settings and diagnostics.
echo Load the Hunter's Dream and compare the same view with the Serial reference.
"%~dp0Bloodborne.exe" --play --geometry-diagnostic=normal
echo The session log and settings are in your user folder under diagnostics.
pause
