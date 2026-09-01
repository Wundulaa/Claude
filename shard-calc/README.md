# Spawner-Shard-Rechner

Rechner für den Einkauf von Spawner Shards: Wie teuer darf ein Shard sein, damit
sich das Abfarmen bei einem gewünschten Stundenlohn noch lohnt — und lohnt sich
ein konkretes Angebot?

**Live:** https://wundulaa.github.io/shard-calc/

## Werkzeuge

**1 — Zielstundenlohn → Maximalpreis.** Ziel-Stundenlohn eingeben, die Tabelle
zeigt für alle Shard-Größen (30 … 405 Ladungen) Farmzeit und Maximalpreis mit
und ohne Boost. Der günstigere Modus ist je Zeile markiert.

**2 — Preis-Check.** Shard-Größe wählen, Gesamtpreis oder Preis je Ladung
eintippen. Ergebnis: Urteil, erreichter Stundenlohn, Gewinn je Shard, Marge,
Rendite auf den Einsatz, Amortisation, Puffer bis zum Ziel — dazu ein Diagramm
Stundenlohn über Einkaufspreis für beide Modi.

## Modell

| | ohne Boost | mit Boost |
|---|---|---|
| Spawn | 5 Ladungen / 10 s | 5 Ladungen / 5 s |
| Ladungen pro Stunde | 1.800 | 3.600 |
| Umsatz pro Stunde | 164.592 | 329.184 |
| Boostkosten | — | 4.000 je 10 min = 24.000/h |
| Netto pro Stunde | 164.592 | 305.184 |

91,44 Münzen je Ladung. Alle Grundwerte sind auf der Seite editierbar
(Münzwert, Spawn-Takt, Boost-Preis und -Dauer, Rüstzeit je Shard, anteilige
oder blockweise Boost-Abrechnung).

Zwei Faustregeln fallen aus dem Modell:

- Der **Boost lohnt nur bis 78,11 Münzen je Ladung** Einkaufspreis. Darüber
  verdienst du ohne Boost mehr pro Stunde.
- Ohne Rüstzeit zählt **nur der Preis je Ladung** — ein 30er zu 55/Ladung ist
  exakt so gut wie ein 405er zu 55/Ladung.

## Rechenweg

```
Farmzeit    = Ladungen ÷ (Ladungen je Spawn ÷ Takt) + Rüstzeit
Gewinn      = Ladungen × Münzen je Ladung − Boostkosten − Kaufpreis
Stundenlohn = Gewinn ÷ Farmzeit
Max-Preis   = Ladungen × Münzen je Ladung − Boostkosten − Ziel-Stundenlohn × Farmzeit
```

## Hosting

Eine einzelne statische Datei, keine Abhängigkeiten außer der Schriftart von
Google Fonts. GitHub Pages: Settings → Pages → Source „Deploy from a branch",
Branch `main`, Ordner `/ (root)`.
