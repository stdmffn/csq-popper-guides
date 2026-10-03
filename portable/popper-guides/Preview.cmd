@echo off
setlocal
"%~dp0runtime\python.exe" "%~dp0guides.py" preview %*
if errorlevel 1 echo Setup did not complete. Read the message above.
pause
