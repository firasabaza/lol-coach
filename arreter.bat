@echo off
rem Arrete le coach lance par lancer.bat.
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*-m lolcoach*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
