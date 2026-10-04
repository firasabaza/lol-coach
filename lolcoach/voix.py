"""Synthèse vocale française, hors ligne, par les voix installées dans Windows."""

from __future__ import annotations

import base64
import math
import queue
import re
import shutil
import subprocess
import threading
import time

# Un seul PowerShell reste ouvert pendant toute la partie et lit une phrase par ligne.
# Les phrases passent en base64 pour ne pas dépendre de l'encodage de la console.
_SCRIPT = """
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {{ $s.SelectVoice('{nom}') }} catch {{
    $fr = $s.GetInstalledVoices() | Where-Object {{ $_.VoiceInfo.Culture.Name -like 'fr*' }} | Select-Object -First 1
    if ($fr) {{ $s.SelectVoice($fr.VoiceInfo.Name) }}
}}
$s.Rate = {debit}
$s.Volume = {volume}
while ($null -ne ($ligne = [Console]::In.ReadLine())) {{
    $son = New-Object IO.MemoryStream
    $s.SetOutputToWaveStream($son)
    $s.Speak([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($ligne)))
    $s.SetOutputToNull()
    $octets = $son.ToArray()
    # Hauteur : on déclare au lecteur une fréquence d'échantillonnage plus haute que la vraie.
    $taux = [int]([BitConverter]::ToInt32($octets, 24) * {hauteur})
    [BitConverter]::GetBytes($taux).CopyTo($octets, 24)
    [BitConverter]::GetBytes([int]($taux * [BitConverter]::ToInt16($octets, 32))).CopyTo($octets, 28)
    (New-Object System.Media.SoundPlayer (New-Object IO.MemoryStream (, $octets))).PlaySync()
}}
"""

# Un cran de débit de la synthèse Windows accélère d'environ 12 %.
_CRAN_DE_DEBIT = 1.116

class Voix:
    def __init__(self, reglages: dict):
        self._peremption = float(reglages.get("peremption", 8))
        self._debit = int(reglages.get("debit", 2))
        # La voix française lit les mots anglais à la française : config.toml lui souffle les pires.
        self._sons = {mot.lower(): son for mot, son in reglages.get("prononciation", {}).items()}
        mots = sorted(self._sons, key=len, reverse=True)
        self._mots = re.compile(rf"\b({'|'.join(map(re.escape, mots))})\b", re.IGNORECASE) if mots else None
        self._file: queue.Queue[tuple[float, str] | None] = queue.Queue()
        # Les voix françaises récentes (Paul, Julie) ne sont visibles que depuis PowerShell 7.
        programme = shutil.which("pwsh") or shutil.which("powershell")
        if programme is None:
            raise RuntimeError("PowerShell introuvable : la voix a besoin de Windows")
        # Une voix jouée plus aiguë est aussi jouée plus vite : on ralentit la synthèse d'autant.
        hauteur = min(1.5, max(0.7, float(reglages.get("hauteur", 1.0))))
        compensation = round(math.log(hauteur) / math.log(_CRAN_DE_DEBIT))
        script = _SCRIPT.format(
            nom=str(reglages.get("nom", "Microsoft Julie")).replace("'", "''"),
            debit=max(-10, min(10, self._debit - compensation)),
            volume=int(reglages.get("volume", 70)),
            hauteur=hauteur,
        )
        self._processus = subprocess.Popen(
            [programme, "-NoProfile", "-NonInteractive", "-Command", script],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        threading.Thread(target=self._parler, daemon=True).start()

    def dire(self, texte: str) -> None:
        if texte:
            self._file.put((time.monotonic(), texte))

    def fermer(self) -> None:
        self._file.put(None)

    def _parler(self) -> None:
        assert self._processus.stdin is not None
        while (element := self._file.get()) is not None:
            demande, texte = element
            if time.monotonic() - demande > self._peremption:
                continue  # trop tard pour être utile
            if self._mots:
                texte = self._mots.sub(lambda trouve: self._sons[trouve.group(0).lower()], texte)
            try:
                self._processus.stdin.write(base64.b64encode(texte.encode()) + b"\n")
                self._processus.stdin.flush()
            except OSError:
                return
            # On attend la fin estimée de la phrase avant d'envoyer la suivante,
            # pour que la péremption s'applique à ce qui attend.
            time.sleep(len(texte) / (13 + self._debit) + 0.3)
        self._processus.stdin.close()
