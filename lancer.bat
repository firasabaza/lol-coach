@echo off
rem Lance le coach. Ajoute --simulation pour la partie de demonstration.
cd /d "%~dp0"
python -m lolcoach %*
pause
