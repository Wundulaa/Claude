# Spawner-Shard-Rechner

Rechner für den Einkauf von Spawner Shards: Preis eingeben, Stundenlohn sehen —
und nachschlagen, was für jede Shard-Größe noch ein fairer Preis ist.

**Live:** https://wundulaa.github.io/shard-calc/

## Werkzeuge

**Preis-Check.** Shard-Größe wählen, Gesamtpreis oder Preis je Ladung
eintippen — beide Felder sind gekoppelt. Ergebnis: erreichter Stundenlohn ohne
und mit Boost, der bessere Modus ist markiert, dazu Gewinn und Farmzeit je
Shard. Die Zahl färbt sich nach Zielwert: Grün ab Ziel-Stundenlohn, Gelb ab
Mindest-Stundenlohn, Rot darunter.

**Faire Preise je Shard-Größe.** Feste Tabelle für alle Shard-Größen
(30 … 405 Ladungen): Vollwert und der faire Preis-Rahmen — unten der Preis
bei Ziel-Stundenlohn, oben bei Mindest-Stundenlohn, automatisch im besseren
Modus. Zeile anklicken wählt die Größe auch im Preis-Check.

**Einstellungen** (Zahnrad oben rechts). Alle Grundwerte, normalerweise fix:
Münzen je Ladung, Spawn-Takt mit und ohne Boost, Boost-Preis und -Dauer,
Rüstzeit je Shard, anteilige oder blockweise Boost-Abrechnung — sowie
Ziel- und Mindest-Stundenlohn, die die faire Preisspanne festlegen.

## Modell

| | ohne Boost | mit Boost |
|---|---|---|
| Spawn | 5 Ladungen / 10 s | 5 Ladungen / 3 s |
| Ladungen pro Stunde | 1.800 | 6.000 |
| Umsatz pro Stunde | 164.592 | 548.640 |
| Boostkosten | — | 4.000 je 10 min = 24.000/h |
| Netto pro Stunde | 164.592 | 524.640 |

91,44 Münzen je Ladung. Alle Grundwerte sind über das Einstellungsmenü
editierbar (Münzwert, Spawn-Takt, Boost-Preis und -Dauer, Rüstzeit je Shard,
anteilige oder blockweise Boost-Abrechnung, Ziel- und Mindest-Stundenlohn).

Zwei Faustregeln fallen aus dem Modell:

- Der **Boost lohnt nur bis rund 85,7 Münzen je Ladung** Einkaufspreis.
  Darüber verdienst du ohne Boost mehr pro Stunde.
- Ohne Rüstzeit zählt **nur der Preis je Ladung** — ein 30er zu 55/Ladung ist
  exakt so gut wie ein 405er zu 55/Ladung. Sobald in den Einstellungen eine
  Rüstzeit eingetragen ist, werden große Shards planbar besser.

## Rechenweg

```
Farmzeit    = Ladungen ÷ (Ladungen je Spawn ÷ Takt) + Rüstzeit
Stundenlohn = (Ladungen × Münzen je Ladung − Boostkosten − Preis) ÷ Farmzeit
Rahmen      = Preis bei Ziel-Stundenlohn  …  Preis bei Mindest-Stundenlohn
              (jeweils: Ladungen × Münzen je Ladung − Boostkosten − Zielwert × Farmzeit)
```

## Hosting

Eine einzelne statische Datei, keine Abhängigkeiten außer der Schriftart von
Google Fonts. GitHub Pages: Settings → Pages → Source „Deploy from a branch",
Branch `main`, Ordner `/ (root)`.
