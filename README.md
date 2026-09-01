# Claude-Projekte

Sammelrepo für die Projekte, die mit Claude entstanden sind. Jedes Projekt
liegt in einem eigenen Ordner mit seinen eigenen Dateien und seinem eigenen
README — die Ordner sind unabhängig voneinander, es gibt keinen gemeinsamen
Build und keine geteilten Abhängigkeiten.

| Projekt | Was es ist | Start |
|---|---|---|
| [`GalaxyGame`](GalaxyGame/) | Galaxy Attack — Arcade-Weltraumshooter, komplett in einer Python-Datei | `python space_shooter.py` |
| [`shard-calc`](shard-calc/) | Rechner für den Einkauf von Minecraft Spawner Shards | `index.html` im Browser öffnen |

## GalaxyGame — Galaxy Attack

Neon-Vektor-Shooter mit Gefahrenleiter, Hangar, Shop und Bosskämpfen. Rund
6.700 Zeilen Python in einer einzigen Datei; jede Grafik wird zur Laufzeit
mit `pygame.draw` gezeichnet, im Spiel steckt keine einzige Bilddatei.
Braucht nur `pygame` (`pip install -r GalaxyGame/requirements.txt`). Unter
Windows richtet `Galaxy Attack einrichten.bat` alles selbst ein.

Details, Steuerung und Screenshots: [`GalaxyGame/README.md`](GalaxyGame/README.md)

## shard-calc — Spawner-Shard-Rechner

Beantwortet zwei Fragen: Was darf ein Shard höchstens kosten, damit ein
gewünschter Stundenlohn übrig bleibt — und lohnt sich ein konkretes Angebot,
mit oder ohne Boost. Eine statische HTML-Datei ohne Build und ohne
Abhängigkeiten.

Details und Rechenweg: [`shard-calc/README.md`](shard-calc/README.md)

## Herkunft

Beide Projekte lagen vorher in eigenen Repositories; deren Git-Historie bleibt
dort erhalten:

- `GalaxyGame` → https://github.com/Wundulaa/GalaxyGame
- `shard-calc` → https://github.com/Wundulaa/shard-calc (wird als GitHub Page
  unter https://wundulaa.github.io/shard-calc/ ausgeliefert)
