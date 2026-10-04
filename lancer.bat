@echo off
rem Lance le coach sans fenetre de terminal : seule la messagerie apparait, en haut a gauche.
rem Pour l'arreter : arreter.bat. Ce qu'il dit est aussi ecrit dans journal.log.
cd /d "%~dp0"
start "" pythonw -m lolcoach %*
