@echo off
REM Create submission zip without secrets / venv
cd /d "%~dp0"
set OUT=app-review-insights-submit.zip
if exist "%OUT%" del "%OUT%"

powershell -NoProfile -Command ^
  "$root = Get-Location; $out = Join-Path $root 'app-review-insights-submit.zip'; if (Test-Path $out) { Remove-Item $out -Force }; $items = Get-ChildItem -Force | Where-Object { $_.Name -notin @('.venv','venv','.env','.idea','.git','app-review-insights-submit.zip','pack.bat','scripts') }; Compress-Archive -Path ($items.FullName) -DestinationPath $out -Force; Write-Host ('Created: ' + $out)"

echo Done.
pause
