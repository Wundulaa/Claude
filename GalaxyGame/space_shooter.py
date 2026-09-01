"""
================================================================================
  G A L A X Y   A T T A C K   ::   N E O N   V E C T O R   E D I T I O N
================================================================================
  Ein vollstaendiger Arcade Space-Shooter in einer einzigen Datei.

  Steuerung
  ---------
    Pfeiltasten .... Schiff bewegen (fluessige 8-Wege-Bewegung)
    Leertaste ...... Dauerfeuer
    ESC ............ Pause / zurueck
    ENTER .......... Auswahl bestaetigen
    F11 ............ Vollbild umschalten

  Benoetigt ausschliesslich `pygame` - alle Grafiken werden zur Laufzeit
  per pygame.draw als Neon-Vektorgrafik gezeichnet, keine externen Assets.

    pip install pygame
    python space_shooter.py
================================================================================
"""

import datetime
import json
import math
import os
import random
import sys

import pygame
from pygame import Vector2

# ==============================================================================
#  KONFIGURATION
# ==============================================================================

WIDTH, HEIGHT = 1080, 720
FPS = 60
VERSION = "3.0"               # steht im Hauptmenue - so ist sofort sichtbar,
                              # ob wirklich die neueste Datei laeuft
TITLE = "Galaxy Attack %s :: Neon Vector Edition" % VERSION
CAMPAIGN_LEVELS = 10          # Ende der Kampagne, danach Endlosmodus
BOSS_EVERY = 5                # ab Welle 5 alle 5 Wellen ein Boss

PLAY_BOTTOM = HEIGHT - 8   # untere Spielfeldgrenze fuer den Spieler
HUD_HEIGHT = 74


def is_boss_level(level):
    """Boss in Welle 5, 10, 15, 20 ... - auch im Endlosmodus."""
    return level % BOSS_EVERY == 0


def boss_variant(level):
    """1 = Omega Warden, 2 = Nova Tyrant, ab Welle 15 abwechselnd verstaerkt."""
    return 1 if (level // BOSS_EVERY) % 2 == 1 else 2


def boss_tier(level):
    """Wie oft der Bosstyp schon aufgetreten ist - 0 beim ersten Mal."""
    return max(0, (level - BOSS_EVERY) // (BOSS_EVERY * 2))

# ------------------------------------------------------------------ Farbpalette
SPACE = (6, 7, 18)
WHITE = (255, 255, 255)
GREY = (150, 158, 180)
DARKGREY = (58, 64, 86)

CYAN = (0, 232, 255)
BLUE = (70, 130, 255)
DEEPBLUE = (32, 60, 160)
GREEN = (60, 255, 140)
LIME = (170, 255, 60)
YELLOW = (255, 216, 70)
GOLD = (255, 190, 40)
ORANGE = (255, 140, 40)
RED = (255, 70, 80)
MAGENTA = (255, 60, 200)
PURPLE = (170, 90, 255)
CRYSTAL = (90, 190, 255)

# ------------------------------------------------------------ Upgrade-Balancing
# Kosten wachsen geometrisch, Wirkung waechst linear -> klassische
# "diminishing returns"-Kurve, die ueber mehrere Runs hinweg traegt.
UPGRADE_ORDER = ["damage", "firerate", "maxhp", "shieldmatrix", "multishot"]

UPGRADES = {
    "damage": {
        "name": "Waffenschaden",
        "desc": "Schaden pro Laserprojektil",
        "max": 20, "base_cost": 30, "growth": 1.18, "currency": "coins",
    },
    "firerate": {
        "name": "Feuerrate",
        "desc": "Kuerzere Abklingzeit zwischen Schuessen",
        "max": 20, "base_cost": 35, "growth": 1.19, "currency": "coins",
    },
    "maxhp": {
        "name": "Max. Huelle",
        "desc": "Mehr Strukturpunkte + volle Reparatur",
        "max": 15, "base_cost": 45, "growth": 1.20, "currency": "coins",
    },
    "shieldmatrix": {
        "name": "Schildmatrix",
        "desc": "Mehr Schildkapazitaet und schnellere Regeneration",
        "max": 12, "base_cost": 70, "growth": 1.24, "currency": "coins",
    },
    "multishot": {
        "name": "Multi-Shot",
        "desc": "Single > Double > Triple > V-Spread",
        "max": 4, "base_cost": 3, "growth": 2.60, "currency": "crystals",
    },
}

# --------------------------------------------------- Verbrauchsgueter (Shop)
# Einmalkaeufe fuer uebriges Gold zwischen den Wellen. Preise steigen mit der
# Wellennummer, damit spaetes Gold nicht beliebig viel Sicherheit kauft.
CONSUMABLES = {
    "repair": {
        "name": "Reparatur-Kit",
        "desc": "Stellt sofort 55 % der Huelle wieder her",
        "base_cost": 90, "growth": 1.16, "currency": "coins", "stock": 0,
    },
    "shieldcell": {
        "name": "Schild-Zelle",
        "desc": "Schild sofort voll, +40 % Schildkapazitaet fuer diesen Run",
        "base_cost": 140, "growth": 1.22, "currency": "coins", "stock": 3,
    },
    "overdrive": {
        "name": "Overdrive",
        "desc": "+30 % Schaden fuer die naechste Welle",
        "base_cost": 180, "growth": 1.20, "currency": "coins", "stock": 0,
    },
    "revive": {
        "name": "Notfall-Rettung",
        "desc": "Einmal pro Run: Wiederbelebung mit halber Huelle",
        "base_cost": 650, "growth": 1.9, "currency": "coins", "stock": 2,
    },
}
CONSUMABLE_ORDER = ["repair", "shieldcell", "overdrive", "revive"]


def consumable_cost(key, level, bought=0):
    """Preis eines Verbrauchsguts in Welle `level`, teurer je Wiederkauf."""
    cfg = CONSUMABLES[key]
    price = cfg["base_cost"] * (1.0 + 0.10 * (level - 1)) * (cfg["growth"] ** bought)
    return int(round(price / 5.0) * 5)


# --------------------------------------------------------- Adaptive Schwierigkeit
# Der Machtindex misst, wie weit der Spieler ueber der Startausruestung liegt.
# Gegner wachsen bewusst UNTERproportional mit (Exponenten < 1), damit sich
# jedes Upgrade weiterhin spuerbar auszahlt.
BASE_DPS = 10.0 / 0.30              # Schaden pro Sekunde mit Startausruestung
BASE_EHP = 110.0 + 30.0             # Huelle + Schild der Phoenix zu Beginn

THREAT_HP_EXP = 0.26                # Trefferpunkte normaler Gegner
THREAT_COUNT_EXP = 0.22             # Anzahl der Gegner pro Welle
THREAT_AGGRO_EXP = 0.18             # Feuerrate der Gegner (NICHT die Geschosse)
AGGRO_COOLDOWN_EXP = 0.5            # daempft die Feuerrate zusaetzlich
HOVER_COUNT_SHARE = 0.40            # stehende Gegner wachsen nur gedaempft mit
THREAT_BOSS_PIVOT = 6.0             # Machtindex, auf den die Boss-HP geeicht sind
THREAT_BOSS_EXP = 0.68              # unterproportional: Vollausbau toetet schneller
THREAT_BOSS_MIN = 0.30              # Untergrenze fuer schwach ausgeruestete Piloten
THREAT_BOSS_MAX = 5.0               # Obergrenze gegen Endlos-Ausreisser
THREAT_MUTATION = 0.09              # Zusatzchance auf Gegner-Mutationen
THREAT_CAP = 48.0                   # Deckel gegen Ausreisser
MAX_WAVE_ENEMIES = 46               # Obergrenze an Gegnern pro Welle

# ------------------------------------------------------ Kampfmodifikationen
# Nach jeder Welle werden drei Karten gezogen, eine wird gewaehlt. Sie gelten
# nur fuer den laufenden Versuch. Werte stehen in `mult`, Verhalten in `flag`.
MODS = [
    {"key": "damage_up", "name": "Brandmunition", "rare": 0,
     "desc": "+22 % Waffenschaden", "mult": {"dmg": 1.22}},
    {"key": "rate_up", "name": "Kuehlrippen", "rare": 0,
     "desc": "+18 % Feuerrate", "mult": {"fire": 1.18}},
    {"key": "hull_up", "name": "Zusatzplatten", "rare": 0,
     "desc": "+25 % Huelle, sofort aufgefuellt", "mult": {"hp": 1.25}},
    {"key": "speed_up", "name": "Manoevrierduesen", "rare": 0,
     "desc": "+20 % Tempo", "mult": {"speed": 1.20}},
    {"key": "shield_up", "name": "Feldverstaerker", "rare": 0,
     "desc": "+60 % Schildkapazitaet", "mult": {"shield": 1.60}},
    {"key": "pierce", "name": "Durchschuss", "rare": 1,
     "desc": "Laser durchdringen einen Gegner zusaetzlich", "flag": "pierce"},
    {"key": "ricochet", "name": "Querschlaeger", "rare": 1,
     "desc": "Geschosse prallen einmal vom Rand ab", "flag": "ricochet"},
    {"key": "explode", "name": "Zeitbombe", "rare": 1,
     "desc": "Zerstoerte Gegner explodieren", "flag": "explode"},
    {"key": "lifesteal", "name": "Vampirkern", "rare": 1,
     "desc": "Jeder zwoelfte Abschuss heilt 4 % Huelle", "flag": "lifesteal"},
    {"key": "crit", "name": "Schwachstellenscanner", "rare": 1,
     "desc": "12 % Chance auf dreifachen Schaden", "flag": "crit"},
    {"key": "thorns", "name": "Dornenfeld", "rare": 1,
     "desc": "Treffer schaedigen alle Gegner in der Naehe", "flag": "thorns"},
    {"key": "magnet", "name": "Schwarzes Loch", "rare": 1,
     "desc": "Beute fliegt vom ganzen Feld zu", "flag": "magnet"},
    {"key": "greed", "name": "Wucherzins", "rare": 1,
     "desc": "+55 % Muenzen, Gegner +12 % Huelle",
     "mult": {"loot": 1.55, "enemy_hp": 1.12}},
    {"key": "glass", "name": "Aderlass", "rare": 1,
     "desc": "+40 % Schaden, aber -25 % Huelle",
     "mult": {"dmg": 1.40, "hp": 0.75}},
    {"key": "sniper", "name": "Praezisionslauf", "rare": 1,
     "desc": "+85 % Schaden, aber nur eine Bahn",
     "mult": {"dmg": 1.85}, "flag": "single"},
    {"key": "shotgun", "name": "Streuschuss", "rare": 1,
     "desc": "Zwei zusaetzliche Bahnen, -30 % Schaden",
     "mult": {"dmg": 0.70}, "flag": "spread"},
    {"key": "guard", "name": "Notaggregat", "rare": 1,
     "desc": "Schild fuellt sich zu jedem Wellenstart komplett", "flag": "guard"},
    {"key": "regen", "name": "Nanokur", "rare": 1,
     "desc": "Langsame, dauerhafte Huellenregeneration", "flag": "regen"},
    {"key": "haste", "name": "Adrenalin", "rare": 1,
     "desc": "+30 % Feuerrate unter 40 % Huelle", "flag": "haste"},
    {"key": "bulwark", "name": "Traegheitsdaempfer", "rare": 1,
     "desc": "-25 % erlittener Schaden, -10 % Tempo",
     "mult": {"taken": 0.75, "speed": 0.90}},
    {"key": "coins2", "name": "Bergungsrecht", "rare": 1,
     "desc": "+35 % Muenzen und Kristalle", "mult": {"loot": 1.35}},
    {"key": "hearts", "name": "Sanitaetsdrohne", "rare": 1,
     "desc": "Herzen fallen dreimal so haeufig", "flag": "hearts"},
    {"key": "revive", "name": "Reservekern", "rare": 2,
     "desc": "Eine zusaetzliche Notfall-Rettung", "flag": "revive"},
    {"key": "double_dmg", "name": "Ueberladung", "rare": 2,
     "desc": "+45 % Waffenschaden", "mult": {"dmg": 1.45}},
    {"key": "execute", "name": "Gnadenstoss", "rare": 2,
     "desc": "Gegner unter 12 % Huelle sterben sofort", "flag": "execute"},
    {"key": "chain_mod", "name": "Kettenblitz", "rare": 2,
     "desc": "Treffer springen auf einen nahen Gegner ueber", "flag": "chain"},
    {"key": "slowmo", "name": "Zeitdehnung", "rare": 2,
     "desc": "Nach einem Treffer kurz Zeitlupe", "flag": "slowmo"},
    {"key": "fortress_mod", "name": "Ankerfeld", "rare": 2,
     "desc": "Stillstehen halbiert den erlittenen Schaden", "flag": "anchor"},
    {"key": "swarm", "name": "Leichtbau", "rare": 2,
     "desc": "+30 % Feuerrate und +15 % Tempo",
     "mult": {"fire": 1.30, "speed": 1.15}},
    {"key": "titan", "name": "Titanhuelle", "rare": 2,
     "desc": "+60 % Huelle, -12 % Feuerrate",
     "mult": {"hp": 1.60, "fire": 0.88}},
]
MOD_BY_KEY = {m["key"]: m for m in MODS}
MOD_RARITY_COLOR = {0: (150, 158, 180), 1: (90, 190, 255), 2: (255, 190, 40)}
MOD_RARITY_NAME = {0: "einfach", 1: "selten", 2: "episch"}


# ------------------------------------------------------------------ Anbauten
# Anbauten kommen ausschliesslich aus Frachtkisten. Man WAEHLT sie nicht -
# jede Kiste wuerfelt, gewichtet nach `weight`. Deshalb sind die auffaelligen
# Anbauten selten und die kleinen Zugaben haeufig.
#
# `stack` begrenzt, wie oft ein Anbau anfallen kann. Ist alles am Anschlag,
# zahlt die Kiste stattdessen Muenzen aus - eine Niete gibt es also nicht,
# aber eben auch keine Garantie auf das, was man haben will.
ADDONS = [
    {"key": "plating", "name": "Panzerplatten", "weight": 20, "stack": 4,
     "desc": "+10 % Huelle", "color": (170, 180, 210)},
    {"key": "coolant", "name": "Kuehlmittel", "weight": 20, "stack": 4,
     "desc": "+8 % Feuerrate", "color": CYAN},
    {"key": "spotter", "name": "Zielrechner", "weight": 20, "stack": 4,
     "desc": "+8 % Waffenschaden", "color": ORANGE},
    {"key": "salvage", "name": "Bergungsarm", "weight": 16, "stack": 3,
     "desc": "+12 % Muenzfund", "color": GOLD},
    {"key": "lance", "name": "Zusatzlaser", "weight": 13, "stack": 3,
     "desc": "Eine zusaetzliche Laserbahn", "color": (120, 255, 200)},
    {"key": "aegis", "name": "Aegis-Ring", "weight": 11, "stack": 3,
     "desc": "Schildring zu jedem Wellenstart", "color": CRYSTAL},
    {"key": "escort", "name": "Begleitdrohne", "weight": 9, "stack": 3,
     "desc": "Eine mitfliegende Drohne schiesst mit", "color": LIME},
    {"key": "flak", "name": "Flakwerfer", "weight": 7, "stack": 2,
     "desc": "Raeumt regelmaessig Geschosse in der Naehe weg",
     "color": (255, 150, 90)},
]
ADDON_BY_KEY = {a["key"]: a for a in ADDONS}
ADDON_MAX_TOTAL = 12          # Obergrenze, damit ein langer Lauf nicht kippt
CRATE_DROP_CHANCE = 0.016     # je Abschuss - grob eine Kiste alle drei Wellen
CRATE_COIN_FALLBACK = 320     # Muenzen, wenn nichts mehr anzubauen ist

AEGIS_PER_STACK = 34.0        # Schild, den ein Aegis-Ring zum Wellenstart gibt
ESCORT_FIRE_RATE = 1.15       # Sekunden zwischen zwei Schuessen einer Drohne
FLAK_INTERVAL = 4.5           # Sekunden zwischen zwei Flakstoessen
FLAK_RADIUS = 130.0


def roll_addon(counts, rng=random):
    """Wuerfelt einen Anbau aus. None, wenn nichts mehr frei ist."""
    if sum(counts.values()) >= ADDON_MAX_TOTAL:
        return None
    pool = [a for a in ADDONS if counts.get(a["key"], 0) < a["stack"]]
    if not pool:
        return None
    total = sum(a["weight"] for a in pool)
    pick = rng.uniform(0, total)
    for addon in pool:
        pick -= addon["weight"]
        if pick <= 0:
            return addon["key"]
    return pool[-1]["key"]


def draw_mod_icon(surface, mod, cx, cy, t, scale=1.0):
    """Kleines Symbol je Modifikation - aus Grundformen zusammengesetzt."""
    col = MOD_RARITY_COLOR[mod["rare"]]
    key = mod["key"]
    blit_glow(surface, col, (cx, cy), int(24 * scale))
    if "mult" in mod and "dmg" in mod["mult"]:
        pts = rot_points([(0, -16), (6, -4), (2, -4), (8, 14), (-8, 2), (-2, 2)],
                         0, cx, cy, scale)
        pygame.draw.polygon(surface, scale_color(col, 0.35), pts)
        neon_poly(surface, col, pts, 2, halo=0.0)
    elif key in ("hull_up", "titan", "bulwark", "fortress_mod"):
        pts = rot_points([(0, -16), (13, -8), (13, 6), (0, 17), (-13, 6), (-13, -8)],
                         0, cx, cy, scale)
        pygame.draw.polygon(surface, scale_color(col, 0.35), pts)
        neon_poly(surface, col, pts, 2, halo=0.0)
    elif key in ("rate_up", "swarm", "haste", "speed_up"):
        for i in range(3):
            off = (i - 1) * 8 * scale
            pygame.draw.line(surface, col, (cx + off, cy - 14 * scale),
                             (cx + off, cy + 12 * scale), 3)
    elif key in ("shield_up", "guard"):
        pygame.draw.circle(surface, col, (cx, cy), int(15 * scale), 3)
        pygame.draw.arc(surface, WHITE, pygame.Rect(cx - 15 * scale, cy - 15 * scale,
                                                    30 * scale, 30 * scale),
                        t * 2, t * 2 + 1.2, 2)
    elif key in ("coins2", "greed", "magnet"):
        pygame.draw.circle(surface, col, (cx, cy), int(13 * scale))
        pygame.draw.circle(surface, WHITE, (cx, cy), int(13 * scale), 2)
    else:
        pts = rot_points([(0, -15), (11, 0), (0, 15), (-11, 0)],
                         t * 1.2, cx, cy, scale)
        pygame.draw.polygon(surface, scale_color(col, 0.35), pts)
        neon_poly(surface, col, pts, 2, halo=0.0)


# ---------------------------------------------------------------- Refit
# Sind alle Kernaufwertungen auf Maximum, laesst sich das Schiff refitten:
# Die Upgrades fallen auf Stufe 1 zurueck, dafuer gibt es dauerhafte Boni.
# Das ist die einzige Senke ohne Obergrenze - und weil die Boni in den
# Machtindex einfliessen, zieht die Schwierigkeit sauber mit.
REFIT_DAMAGE_PER = 0.06             # +6 % Schaden je Stufe
REFIT_COINS_PER = 0.05              # +5 % Muenzfund je Stufe
REFIT_LIVES_EVERY = 3               # je 3 Stufen eine Notfall-Rettung gratis
REFIT_CRYSTAL_AT = 10               # ab Stufe 10 doppelte Kristallfundrate


def refit_damage_mult(level):
    return 1.0 + REFIT_DAMAGE_PER * max(0, level)


def refit_coin_mult(level):
    return 1.0 + REFIT_COINS_PER * max(0, level)


def refit_free_lives(level):
    return max(0, level) // REFIT_LIVES_EVERY


# ------------------------------------------------------------ Schiffsraenge
# Zehn Raenge je Schiff. Sieben geben Werte, drei schalten ein System frei -
# eine echte Faehigkeit statt eines Prozentwertes.
RANK_MAX = 10
RANK_BASE_COST = 350
RANK_GROWTH = 1.30
RANK_CRYSTAL_AT = {4: 15, 8: 25}     # diese Raenge kosten zusaetzlich Kristalle

RANK_STEPS = [
    {},                                          # Rang 0 (Start)
    {"dmg": 0.04},
    {"hp": 0.04},
    {"system": 0},
    {"fire": 0.06},
    {"shield": 0.08},
    {"system": 1},
    {"dmg": 0.08},
    {"speed": 0.06},
    {"system": 2},
    {"hp": 0.10, "dmg": 0.04},
]

# Je Schiff drei Systeme. Die Namen erscheinen im Spiel, die Schluessel
# steuern die Logik in Player und Game.
SHIP_SYSTEMS = {
    "phoenix": [
        {"key": "twin", "name": "Zwillingskern",
         "desc": "Jede vierte Salve feuert doppelt"},
        {"key": "repair", "name": "Reparaturprotokoll",
         "desc": "Nach jeder Welle 15 % Huelle zurueck"},
        {"key": "heat_dmg", "name": "Gluthitze",
         "desc": "Dauerfeuer steigert den Schaden auf bis zu +40 %"},
    ],
    "vanguard": [
        {"key": "heat_rate", "name": "Ueberhitzung",
         "desc": "Dauerfeuer steigert die Kadenz auf bis zu +25 %"},
        {"key": "afterburner", "name": "Nachbrenner",
         "desc": "+30 % Tempo, solange nicht gefeuert wird"},
        {"key": "chain", "name": "Kettenreaktion",
         "desc": "Zerstoerte Gegner explodieren und schaedigen die Umgebung"},
    ],
    "dreadnought": [
        {"key": "reactive", "name": "Reaktivpanzerung",
         "desc": "Nach einem Treffer 1,5 s lang halber Schaden"},
        {"key": "ram", "name": "Rammsporn",
         "desc": "Rammen zerstoert Gegner und kostet nur ein Drittel Schaden"},
        {"key": "fortress", "name": "Festungsmodus",
         "desc": "Stillstehen gibt nach 1 s +50 % Schaden"},
    ],
    "wraith": [
        {"key": "phase_trail", "name": "Phasenriss",
         "desc": "Der Blink hinterlaesst eine schaedigende Spur"},
        {"key": "cold_start", "name": "Kaltstart",
         "desc": "Blink laedt 45 % schneller nach"},
        {"key": "double_jump", "name": "Doppelsprung",
         "desc": "Eine zusaetzliche Blink-Ladung"},
    ],
    "bastion": [
        {"key": "third_orb", "name": "Dritte Kugel",
         "desc": "Eine zusaetzliche Orbitalkugel"},
        {"key": "fast_charge", "name": "Schnellladung",
         "desc": "Kugeln laden nach dem Abfangen doppelt so schnell nach"},
        {"key": "riposte", "name": "Abwehrschlag",
         "desc": "Jedes abgefangene Geschoss loest einen Gegenschuss aus"},
    ],
    "hydra": [
        {"key": "side_load", "name": "Seitenlast",
         "desc": "Die Seitenlaeufe feuern doppelt"},
        {"key": "rear_hunter", "name": "Heckjaeger",
         "desc": "Der Heckschuss wird zur Zielsuchrakete"},
        {"key": "full_circle", "name": "Vollkreis",
         "desc": "Vier zusaetzliche Diagonalschuesse je Salve"},
    ],
    "helios": [
        {"key": "focus", "name": "Brennglas",
         "desc": "Der Strahl laedt 35 % schneller"},
        {"key": "penetrator", "name": "Durchschlag",
         "desc": "Der Strahl durchdringt beliebig viele Gegner"},
        {"key": "solar_storm", "name": "Sonnensturm",
         "desc": "Ein voll geladener Schuss loest eine Druckwelle aus"},
    ],
    "locust": [
        {"key": "fourth_drone", "name": "Vierter Schwarm",
         "desc": "Eine zusaetzliche Drohne"},
        {"key": "warheads", "name": "Sprengkoepfe",
         "desc": "Raketen richten Flaechenschaden an"},
        {"key": "swarm_lead", "name": "Schwarmfuehrung",
         "desc": "Drohnen feuern doppelt so schnell"},
    ],
}


def rank_cost(rank):
    """Kosten fuer den Sprung von `rank` auf `rank + 1`."""
    if rank >= RANK_MAX:
        return None, 0
    coins = int(round(RANK_BASE_COST * (RANK_GROWTH ** rank)))
    return coins, RANK_CRYSTAL_AT.get(rank + 1, 0)


def rank_bonus(rank):
    """Summierte Werteboni bis zum angegebenen Rang."""
    out = {"dmg": 0.0, "hp": 0.0, "fire": 0.0, "speed": 0.0, "shield": 0.0}
    for step in RANK_STEPS[:max(0, min(rank, RANK_MAX)) + 1]:
        for key, value in step.items():
            if key in out:
                out[key] += value
    return out


def rank_systems(ship_key, rank):
    """Freigeschaltete Systeme eines Schiffes als Schluesselmenge."""
    unlocked = set()
    for idx, step in enumerate(RANK_STEPS[:max(0, min(rank, RANK_MAX)) + 1]):
        if "system" in step:
            unlocked.add(SHIP_SYSTEMS[ship_key][step["system"]]["key"])
    return unlocked


def system_rank(index):
    """Bei welchem Rang das System mit der Nummer `index` freigeschaltet wird."""
    for rank, step in enumerate(RANK_STEPS):
        if step.get("system") == index:
            return rank
    return RANK_MAX


# ----------------------------------------------------------- Gefahrenstufen
# EINE Leiter statt frueher zwei (Schwierigkeitsregler + Nova-Grad).
# Jede Stufe legt drei Dinge fest:
#   threat   - wie stark der ADAPTIVE Zuschlag durch den Machtindex wirkt
#   dmg      - Schadensfaktor der Gegner
#   reward   - Beutefaktor auf Muenzen und Kristalle
#   hardship - zusaetzliche Sonderregeln, die sich nach oben stapeln
#
# Die Stufen 0 bis 2 sind immer waehlbar. Ab Stufe 3 muss die jeweils
# vorherige Stufe einmal durchgespielt worden sein.
HARDSHIPS = {
    "armor":     "Alle Gegner haben 20 % mehr Trefferpunkte",
    "nohearts":  "Keine Herzen mehr im Feld",
    "bulwark":   "Bosse fahren ein zusaetzliches Bollwerk hoch",
    "debris":    "Zerstoerte Gegner hinterlassen kurz gefaehrliche Truemmer",
    "noregen":   "Der Schild regeneriert nicht mehr von selbst",
}

TIERS = [
    {"name": "Kadett", "threat": 0.45, "dmg": 0.72, "reward": 0.85,
     "hardships": (), "color": GREEN,
     "desc": "Gegner ziehen kaum mit, weniger Schaden - dafuer weniger Beute"},
    {"name": "Pilot", "threat": 1.00, "dmg": 1.00, "reward": 1.00,
     "hardships": (), "color": CYAN,
     "desc": "Ausgewogen - empfohlen fuer den ersten Durchgang"},
    {"name": "Veteran", "threat": 1.45, "dmg": 1.12, "reward": 1.25,
     "hardships": (), "color": YELLOW,
     "desc": "Volle Anpassung, harte Treffer, ein Viertel mehr Beute"},
    # Im Nova-Band traegt die jeweils NEUE Erschwernis den Sprung, nicht eine
    # weiter hochgedrehte Zahl. Deshalb steigen threat und dmg hier nur noch
    # flach - sonst waere allein der Einstieg in Nova I eine Wand.
    {"name": "Nova I", "threat": 1.45, "dmg": 1.16, "reward": 1.45,
     "hardships": ("armor",), "color": GOLD,
     "desc": HARDSHIPS["armor"]},
    {"name": "Nova II", "threat": 1.54, "dmg": 1.20, "reward": 1.70,
     "hardships": ("armor", "nohearts"), "color": ORANGE,
     "desc": HARDSHIPS["nohearts"]},
    {"name": "Nova III", "threat": 1.63, "dmg": 1.24, "reward": 2.00,
     "hardships": ("armor", "nohearts", "bulwark"), "color": RED,
     "desc": HARDSHIPS["bulwark"]},
    {"name": "Nova IV", "threat": 1.72, "dmg": 1.28, "reward": 2.35,
     "hardships": ("armor", "nohearts", "bulwark", "debris"), "color": MAGENTA,
     "desc": HARDSHIPS["debris"]},
    {"name": "Nova V", "threat": 1.80, "dmg": 1.32, "reward": 2.75,
     "hardships": ("armor", "nohearts", "bulwark", "debris", "noregen"),
     "color": PURPLE, "desc": HARDSHIPS["noregen"]},
]
TIER_MAX = len(TIERS) - 1
TIER_FREE = 2          # bis hierher ohne Freischaltung waehlbar
DEFAULT_TIER = 1


def tier_cfg(index):
    return TIERS[int(clamp(index, 0, TIER_MAX))]


def tier_top(save):
    """Hoechste aktuell waehlbare Stufe: eine ueber der bereits geschafften."""
    cleared = int(clamp(save.get("tier_cleared", TIER_FREE), 0, TIER_MAX))
    return int(clamp(max(TIER_FREE, cleared + 1), 0, TIER_MAX))


# ------------------------------------------------------------ Gegner-Mutationen
# Einzelne Gegner koennen "aufgeruestet" spawnen. Jede Mutation hat sichtbare
# Folgen im Bild und erhoeht die Beute, damit sie sich zu toeten lohnt.
MUTATIONS = {
    "shield": {"name": "Schild", "color": (90, 190, 255), "loot": 1.6, "weight": 26},
    "rapid": {"name": "Schnellfeuer", "color": (255, 216, 70), "loot": 1.4, "weight": 20},
    "armored": {"name": "Panzerung", "color": (170, 180, 210), "loot": 1.5, "weight": 20},
    "swift": {"name": "Sprint", "color": (60, 255, 140), "loot": 1.3, "weight": 18},
    "elite": {"name": "Elite", "color": (255, 190, 40), "loot": 3.0, "weight": 12},
}
MUTATION_KEYS = list(MUTATIONS.keys())

# --------------------------------------------------------------------- Biome
# Alle vier Wellen wechselt die Kulisse. Rein visuell, aber der Wechsel macht
# den Fortschritt im Endlosmodus sichtbar.
BIOMES = [
    {"name": "Tiefer Raum", "space": (6, 7, 18),
     "stars": [(120, 130, 170), (185, 200, 240), (255, 255, 255)],
     "nebula": [(40, 20, 90), (14, 45, 90), (16, 60, 70)], "effect": None},
    {"name": "Kristallnebel", "space": (7, 12, 30),
     "stars": [(120, 170, 200), (170, 220, 255), (235, 250, 255)],
     "nebula": [(18, 70, 120), (30, 90, 130), (12, 50, 96)], "effect": "shards"},
    {"name": "Ionensturm", "space": (6, 16, 16),
     "stars": [(110, 170, 140), (170, 240, 200), (230, 255, 240)],
     "nebula": [(14, 80, 66), (10, 60, 80), (26, 90, 60)], "effect": "lightning"},
    {"name": "Asteroidenfeld", "space": (14, 11, 12),
     "stars": [(150, 140, 130), (210, 200, 190), (255, 250, 245)],
     "nebula": [(60, 40, 30), (40, 30, 40), (70, 50, 30)], "effect": "rocks"},
    {"name": "Kernbrand", "space": (20, 7, 10),
     "stars": [(190, 130, 120), (255, 180, 150), (255, 235, 220)],
     "nebula": [(90, 20, 20), (70, 26, 50), (100, 40, 10)], "effect": "embers"},
    {"name": "Leere", "space": (10, 6, 20),
     "stars": [(140, 120, 180), (200, 180, 245), (250, 240, 255)],
     "nebula": [(50, 16, 90), (30, 10, 70), (66, 20, 96)], "effect": "voidrift"},
]


def biome_for(level):
    return BIOMES[((level - 1) // 4) % len(BIOMES)]


MULTISHOT_NAMES = {1: "Single", 2: "Double", 3: "Triple", 4: "V-Spread"}
# Gesamtschaden pro Salve: 1.00 / 1.44 / 1.80 / 2.40
MULTISHOT_FALLOFF = {1: 1.00, 2: 0.72, 3: 0.60, 4: 0.48}


def progression_mult(save, ship_key):
    """Dauerhafte Multiplikatoren aus Refit und Schiffsrang.

    Diese Werte fliessen auch in den Machtindex ein - sonst wuerde der
    Fortschritt die adaptive Schwierigkeit aushebeln."""
    ranks = save.get("ranks") or {}
    rank = int(clamp(int(ranks.get(ship_key, 0) or 0), 0, RANK_MAX))
    bonus = rank_bonus(rank)
    refit = max(0, int(save.get("refit", 0) or 0))
    return {
        "dmg": (1.0 + bonus["dmg"]) * refit_damage_mult(refit),
        "hp": 1.0 + bonus["hp"],
        "fire": 1.0 + bonus["fire"],
        "speed": 1.0 + bonus["speed"],
        "shield": 1.0 + bonus["shield"],
        "coins": refit_coin_mult(refit),
        "rank": rank,
        "refit": refit,
        "systems": rank_systems(ship_key, rank),
    }


NO_PROG = {"dmg": 1.0, "hp": 1.0, "fire": 1.0, "speed": 1.0, "shield": 1.0,
           "coins": 1.0, "rank": 0, "refit": 0, "systems": frozenset()}


def stat_damage(level, ship, prog=None):
    """Schaden pro Projektil vor dem Multi-Shot-Abschlag."""
    prog = prog or NO_PROG
    return (10.0 + 3.2 * (level - 1)) * ship["dmg_mult"] * prog["dmg"]


def stat_cooldown(level, ship, prog=None):
    """Sekunden zwischen zwei Salven."""
    prog = prog or NO_PROG
    return 0.30 * (0.958 ** (level - 1)) / (ship["fire_mult"] * prog["fire"])


def stat_maxhp(level, ship, prog=None):
    prog = prog or NO_PROG
    return int((110 + 20 * (level - 1)) * ship["hp_mult"] * prog["hp"])


def stat_magnet(refit):
    """Der Magnet ist kein Upgrade mehr, sondern Grundausstattung. Er waechst
    nur noch leicht mit der Refit-Stufe, damit spaete Runs bequemer werden."""
    return 190 + 8 * max(0, refit)


def stat_shield(level, ship, prog=None):
    """Schildkapazitaet aus Schiff, Schildmatrix und Rang."""
    prog = prog or NO_PROG
    return ship["shield"] * prog["shield"] * (1.0 + 0.16 * (level - 1))


def stat_shield_regen(level):
    """Schildregeneration in Punkten pro Sekunde."""
    return 7.0 + 1.6 * (level - 1)


def upgrade_cost(key, level):
    """Kosten fuer den Sprung von `level` auf `level + 1`."""
    cfg = UPGRADES[key]
    if level >= cfg["max"]:
        return None
    return int(round(cfg["base_cost"] * (cfg["growth"] ** (level - 1))))


# ==============================================================================
#  MATHE- UND ZEICHEN-HILFSFUNKTIONEN
# ==============================================================================

def clamp(value, low, high):
    return low if value < low else high if value > high else value


def lerp(a, b, t):
    return a + (b - a) * t


def scale_color(color, factor):
    return (clamp(int(color[0] * factor), 0, 255),
            clamp(int(color[1] * factor), 0, 255),
            clamp(int(color[2] * factor), 0, 255))


def mix_color(a, b, t):
    return (int(lerp(a[0], b[0], t)), int(lerp(a[1], b[1], t)), int(lerp(a[2], b[2], t)))


def safe_dir(from_vec, to_vec):
    """Normierter Richtungsvektor, der bei identischen Punkten nicht crasht."""
    d = to_vec - from_vec
    length = d.length()
    if length < 1e-6:
        return Vector2(0, 1)
    return d / length


def rot_points(points, angle, cx, cy, scale=1.0):
    """Lokale Punktliste rotieren, skalieren und an (cx, cy) verschieben."""
    ca, sa = math.cos(angle), math.sin(angle)
    return [(cx + (px * ca - py * sa) * scale,
             cy + (px * sa + py * ca) * scale) for px, py in points]


_glow_cache = {}


def glow_surface(color, radius):
    """Vorgerenderte, additiv blitbare Leuchtscheibe (gecacht)."""
    radius = max(2, int(radius))
    key = (color, radius)
    surf = _glow_cache.get(key)
    if surf is None:
        surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        steps = min(radius, 24)
        # Wichtig: additives Blitten (BLEND_ADD) ignoriert den Alphakanal.
        # Der Verlauf muss deshalb ueber die HELLIGKEIT der Ringe entstehen,
        # sonst wird aus dem weichen Schein eine harte Scheibe.
        for i in range(steps, 0, -1):
            t = i / steps
            r = max(1, int(radius * t))
            col = scale_color(color, (1.0 - t) ** 2 * 0.95)
            pygame.draw.circle(surf, (col[0], col[1], col[2], 255),
                               (radius, radius), r)
        _glow_cache[key] = surf
    return surf


def blit_glow(surface, color, pos, radius):
    g = glow_surface(color, radius)
    surface.blit(g, (pos[0] - g.get_width() // 2, pos[1] - g.get_height() // 2),
                 special_flags=pygame.BLEND_ADD)


def neon_poly(surface, color, points, width=2, closed=True, halo=0.32):
    """Polygonzug mit dunklem, breitem Halo + heller Kernlinie = Neon-Look."""
    if len(points) < 2:
        return
    if halo > 0:
        pygame.draw.lines(surface, scale_color(color, halo), closed, points, width + 4)
    pygame.draw.lines(surface, color, closed, points, width)


# ------------------------------------------------------------------- Schriften
_font_cache = {}


def font(size, bold=False):
    key = (size, bold)
    f = _font_cache.get(key)
    if f is None:
        f = pygame.font.Font(None, size)
        f.set_bold(bold)
        _font_cache[key] = f
    return f


def draw_text(surface, text, size, x, y, color=WHITE, anchor="topleft",
              glow=None, bold=False, alpha=255):
    f = font(size, bold)
    img = f.render(str(text), True, color)
    if alpha < 255:
        img = img.copy()
        img.set_alpha(alpha)
    rect = img.get_rect()
    setattr(rect, anchor, (x, y))
    if glow is not None:
        ghost = f.render(str(text), True, scale_color(glow, 0.55))
        if alpha < 255:
            ghost = ghost.copy()
            ghost.set_alpha(alpha)
        for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, 1)):
            surface.blit(ghost, (rect.x + ox, rect.y + oy))
    surface.blit(img, rect)
    return rect


def draw_bar(surface, x, y, w, h, ratio, color, back=(24, 26, 42),
             border=(90, 100, 130), segments=0):
    ratio = clamp(ratio, 0.0, 1.0)
    pygame.draw.rect(surface, back, (x, y, w, h), border_radius=3)
    if ratio > 0:
        inner = max(2, int((w - 4) * ratio))
        pygame.draw.rect(surface, scale_color(color, 0.45), (x + 2, y + 2, inner, h - 4),
                         border_radius=2)
        pygame.draw.rect(surface, color, (x + 2, y + 2, inner, max(2, (h - 4) // 2)),
                         border_radius=2)
    pygame.draw.rect(surface, border, (x, y, w, h), 1, border_radius=3)
    if segments > 1:
        for i in range(1, segments):
            sx = x + int(w * i / segments)
            pygame.draw.line(surface, back, (sx, y + 1), (sx, y + h - 2), 1)


def draw_level_pips(surface, x, y, level, max_level, color, size=9, gap=4):
    """Kompakte Level-Anzeige als Kette kleiner Rauten."""
    for i in range(max_level):
        cx = x + i * (size + gap)
        pts = [(cx + size / 2, y), (cx + size, y + size / 2),
               (cx + size / 2, y + size), (cx, y + size / 2)]
        if i < level:
            pygame.draw.polygon(surface, color, pts)
        else:
            pygame.draw.polygon(surface, (48, 52, 72), pts)
            pygame.draw.polygon(surface, (72, 78, 104), pts, 1)
    return x + max_level * (size + gap)


# ==============================================================================
#  SPEICHERSTAND
# ==============================================================================

try:
    SAVE_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:                                    # pragma: no cover
    SAVE_DIR = os.getcwd()
SAVE_PATH = os.path.join(SAVE_DIR, "galaxy_attack_save.json")

DEFAULT_SAVE = {
    "coins": 0,
    "crystals": 0,
    "highscore": 0,
    "best_level": 0,
    "total_kills": 0,
    "waves_total": 0,
    "upgrades": {"damage": 1, "firerate": 1, "maxhp": 1, "shieldmatrix": 1,
                 "multishot": 1},
    "unlocked": ["phoenix"],
    "ship": "phoenix",
    "tier": DEFAULT_TIER,
    "tier_cleared": TIER_FREE,
    "refit": 0,
    "ranks": {},
}


def _as_int(value, fallback):
    """Ganzzahl aus einem beliebigen Speicherwert - nie mit Fehler."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def load_save():
    data = json.loads(json.dumps(DEFAULT_SAVE))       # tiefe Kopie
    try:
        with open(SAVE_PATH, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        if isinstance(raw, dict):
            for key, default in DEFAULT_SAVE.items():
                if key in raw and isinstance(raw[key], type(default)):
                    data[key] = raw[key]
            # Upgrades einzeln validieren, damit ein kaputter Save nichts sprengt
            ups = dict(DEFAULT_SAVE["upgrades"])
            raw_ups = data["upgrades"] if isinstance(data.get("upgrades"), dict) else {}
            # Der frueher vorhandene Magnet-Rang wandert in die Schildmatrix,
            # damit alte Speicherstaende nichts verlieren.
            if "shieldmatrix" not in raw_ups and "magnet" in raw_ups:
                raw_ups = dict(raw_ups)
                raw_ups["shieldmatrix"] = raw_ups.get("magnet", 1)
            for key, cfg in UPGRADES.items():
                val = raw_ups.get(key, 1)
                ups[key] = int(clamp(int(val) if isinstance(val, (int, float)) else 1,
                                     1, cfg["max"]))
            data["upgrades"] = ups
            data["coins"] = max(0, int(data["coins"]))
            data["crystals"] = max(0, int(data["crystals"]))
            # Alte Speicherstaende kannten zwei getrennte Regler. Sie werden
            # auf die eine Gefahrenleiter abgebildet: Nova-Grad n liegt auf
            # Stufe TIER_FREE + n, ohne Nova zaehlt der alte Schwierigkeitsgrad.
            if "tier" not in raw and ("nova_grade" in raw or "difficulty" in raw):
                old_nova = int(_as_int(raw.get("nova_grade"), 0))
                old_diff = int(_as_int(raw.get("difficulty"), DEFAULT_TIER))
                data["tier"] = (TIER_FREE + old_nova if old_nova > 0
                                else int(clamp(old_diff, 0, TIER_FREE)))
            if "tier_cleared" not in raw and "nova_cleared" in raw:
                data["tier_cleared"] = TIER_FREE + int(
                    _as_int(raw.get("nova_cleared"), 0))
            data["tier_cleared"] = int(clamp(_as_int(data.get("tier_cleared"),
                                                     TIER_FREE),
                                             TIER_FREE, TIER_MAX))
            data["tier"] = int(clamp(_as_int(data.get("tier"), DEFAULT_TIER),
                                     0, tier_top(data)))
            data["refit"] = max(0, int(data.get("refit", 0)))
            ranks = {}
            raw_ranks = data.get("ranks", {})
            for key in SHIP_ORDER:
                value = raw_ranks.get(key, 0) if isinstance(raw_ranks, dict) else 0
                try:
                    ranks[key] = int(clamp(int(value), 0, RANK_MAX))
                except (TypeError, ValueError):
                    ranks[key] = 0
            data["ranks"] = ranks
            if "phoenix" not in data["unlocked"]:
                data["unlocked"].append("phoenix")
    except (OSError, ValueError, TypeError, KeyError):
        pass
    return data


def write_save(data):
    try:
        with open(SAVE_PATH, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
    except OSError:
        pass


# ==============================================================================
#  STATISTIK-DATENBANK
# ==============================================================================
# Jede Partie wird in einer SQLite-Datei neben dem Skript protokolliert. Damit
# laesst sich hinterher pruefen, welche Welle zu hart ist, woran Piloten
# sterben und ob ein Upgrade zu stark geraten ist:
#
#     python space_shooter.py --stats
#
# sqlite3 gehoert zur Standardbibliothek - es kommt keine Abhaengigkeit dazu.

DB_PATH = os.path.join(SAVE_DIR, "galaxy_attack_stats.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT,    ended_at TEXT,  outcome  TEXT,
    ship        TEXT,    score    INTEGER,
    max_wave    INTEGER, endless  INTEGER,
    kills       INTEGER, shots    INTEGER, hits    INTEGER, accuracy REAL,
    coins       INTEGER, crystals INTEGER, duration REAL,
    power       REAL,    dps      REAL,
    lvl_damage  INTEGER, lvl_firerate INTEGER, lvl_maxhp INTEGER,
    lvl_shield  INTEGER, lvl_multishot INTEGER
);
CREATE TABLE IF NOT EXISTS waves (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id   INTEGER, wave INTEGER, cleared INTEGER,
    duration REAL,    kills INTEGER, shots INTEGER, hits INTEGER,
    damage_taken REAL, hp_left REAL, coins INTEGER, crystals INTEGER,
    power    REAL,    threat_hp REAL, enemies INTEGER,
    boss     INTEGER, boss_hp REAL, boss_ttk REAL, mutations INTEGER
);
CREATE TABLE IF NOT EXISTS deaths (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id   INTEGER, wave INTEGER, killer TEXT, killer_mutations TEXT,
    power    REAL,    run_time REAL
);
CREATE TABLE IF NOT EXISTS purchases (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id   INTEGER, wave INTEGER, item TEXT, kind TEXT,
    cost     INTEGER, currency TEXT, new_level INTEGER
);
"""


class StatsDB:
    """Duenner Wrapper um sqlite3. Eine kaputte Datenbank darf nie das Spiel
    stoppen - deshalb wird jeder Fehler abgefangen.

    Wichtig: eine einzelne fehlerhafte Zeile schaltet die Statistik NICHT ab.
    Frueher tat sie das, und danach fehlten stillschweigend alle weiteren
    Zeilen - genau die Daten, mit denen die Balance geprueft wird. Nur ein
    Fehler an der Verbindung selbst schaltet ab; alles andere wird gezaehlt
    und im Report ausgewiesen."""

    def __init__(self, path=None):
        self.path = path or DB_PATH
        self.conn = None
        self.run_id = None
        self.enabled = False
        self.errors = 0                  # verworfene Zeilen
        self.last_error = ""
        try:
            import sqlite3
            self.sqlite3 = sqlite3
            self.conn = sqlite3.connect(self.path)
            self.conn.executescript(SCHEMA)
            self.conn.commit()
            self.enabled = True
        except Exception as exc:
            self.conn = None
            self.enabled = False
            self.last_error = str(exc)

    def _exec(self, sql, params=()):
        if not self.enabled:
            return None
        try:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur
        except Exception as exc:
            self.errors += 1
            self.last_error = "%s: %s" % (type(exc).__name__, exc)
            try:
                self.conn.rollback()      # nur diese eine Zeile ist verloren
            except Exception:
                self.enabled = False      # die Verbindung selbst ist hin
            return None

    # ------------------------------------------------------------- Schreiben
    def start_run(self, ship, upgrades, power, dps):
        cur = self._exec(
            "INSERT INTO runs (started_at, outcome, ship, score, max_wave, endless,"
            " kills, shots, hits, accuracy, coins, crystals, duration, power, dps,"
            " lvl_damage, lvl_firerate, lvl_maxhp, lvl_shield, lvl_multishot)"
            " VALUES (?,?,?,0,0,0,0,0,0,0,0,0,0,?,?,?,?,?,?,?)",
            (datetime.datetime.now().isoformat(timespec="seconds"), "laufend", ship,
             power, dps, upgrades["damage"], upgrades["firerate"], upgrades["maxhp"],
             upgrades["shieldmatrix"], upgrades["multishot"]))
        self.run_id = cur.lastrowid if cur is not None else None
        return self.run_id

    def finish_run(self, outcome, stats, score, max_wave, endless, power, dps,
                   upgrades):
        if self.run_id is None:
            return
        accuracy = (stats["hits"] / stats["shots"]) if stats["shots"] else 0.0
        self._exec(
            "UPDATE runs SET ended_at=?, outcome=?, score=?, max_wave=?, endless=?,"
            " kills=?, shots=?, hits=?, accuracy=?, coins=?, crystals=?, duration=?,"
            " power=?, dps=?, lvl_damage=?, lvl_firerate=?, lvl_maxhp=?,"
            " lvl_shield=?, lvl_multishot=? WHERE id=?",
            (datetime.datetime.now().isoformat(timespec="seconds"), outcome, int(score),
             int(max_wave), int(bool(endless)), stats["kills"], stats["shots"],
             stats["hits"], accuracy, stats["coins"], stats["crystals"],
             stats["time"], power, dps, upgrades["damage"], upgrades["firerate"],
             upgrades["maxhp"], upgrades["shieldmatrix"], upgrades["multishot"],
             self.run_id))

    def log_wave(self, row):
        if self.run_id is None:
            return
        self._exec(
            "INSERT INTO waves (run_id, wave, cleared, duration, kills, shots, hits,"
            " damage_taken, hp_left, coins, crystals, power, threat_hp, enemies,"
            " boss, boss_hp, boss_ttk, mutations)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (self.run_id, row["wave"], int(row["cleared"]), row["duration"],
             row["kills"], row["shots"], row["hits"], row["damage_taken"],
             row["hp_left"], row["coins"], row["crystals"], row["power"],
             row["threat_hp"], row["enemies"], int(row["boss"]), row["boss_hp"],
             row["boss_ttk"], row["mutations"]))

    def log_death(self, wave, killer, mutations, power, run_time):
        if self.run_id is None:
            return
        self._exec(
            "INSERT INTO deaths (run_id, wave, killer, killer_mutations, power,"
            " run_time) VALUES (?,?,?,?,?,?)",
            (self.run_id, wave, killer, ",".join(sorted(mutations)) or "-",
             power, run_time))

    def log_purchase(self, wave, item, kind, cost, currency, new_level):
        if self.run_id is None:
            return
        self._exec(
            "INSERT INTO purchases (run_id, wave, item, kind, cost, currency,"
            " new_level) VALUES (?,?,?,?,?,?,?)",
            (self.run_id, wave, item, kind, cost, currency, new_level))

    def close(self):
        if self.conn is not None:
            try:
                self.conn.commit()
                self.conn.close()
            except Exception:
                pass
            self.conn = None
            self.enabled = False


# ==============================================================================
#  HINTERGRUND :: PARALLAX-STERNENFELD
# ==============================================================================

class Starfield:
    """Drei Sternenebenen mit unterschiedlicher Scrollgeschwindigkeit plus
    langsam driftende Nebelfelder - erzeugt echte Tiefenwirkung."""

    LAYERS = (
        # (anzahl, speed, radius, farbe, twinkle)
        (110, 22, 1, (120, 130, 170), False),
        (70, 62, 2, (185, 200, 240), True),
        (34, 135, 3, (255, 255, 255), True),
    )

    def __init__(self):
        self.stars = []
        for idx, (count, speed, radius, color, twinkle) in enumerate(self.LAYERS):
            for _ in range(count):
                self.stars.append({
                    "layer": idx,
                    "x": random.uniform(0, WIDTH),
                    "y": random.uniform(0, HEIGHT),
                    "speed": speed * random.uniform(0.8, 1.2),
                    "r": radius,
                    "color": color,
                    "twinkle": twinkle,
                    "phase": random.uniform(0, math.tau),
                })
        self.nebulae = []
        for _ in range(6):
            self.nebulae.append({
                "x": random.uniform(0, WIDTH),
                "y": random.uniform(0, HEIGHT),
                "r": random.uniform(90, 210),
                "speed": random.uniform(4, 12),
                "color": random.choice([(40, 20, 90), (14, 45, 90), (70, 16, 66),
                                        (16, 60, 70)]),
            })
        self.time = 0.0
        self.boost = 1.0
        self.space = SPACE
        self.effect = None
        self.ambient = []
        self.flash = 0.0
        self.flash_timer = random.uniform(3, 8)
        self.set_biome(BIOMES[0])

    # ---------------------------------------------------------------- Biome
    def set_biome(self, biome):
        """Faerbt Sterne und Nebel um und legt die Kulissen-Objekte neu an."""
        self.space = biome["space"]
        self.effect = biome["effect"]
        for star in self.stars:
            star["color"] = biome["stars"][star["layer"]]
        for neb in self.nebulae:
            neb["color"] = random.choice(biome["nebula"])
        self.ambient = []
        if self.effect == "rocks":
            for _ in range(14):
                self.ambient.append({
                    "x": random.uniform(0, WIDTH), "y": random.uniform(-HEIGHT, HEIGHT),
                    "r": random.uniform(9, 34), "spin": random.uniform(0, math.tau),
                    "spd": random.uniform(18, 48), "rot": random.uniform(-0.6, 0.6),
                    "shape": [random.uniform(0.68, 1.25) for _ in range(7)]})
        elif self.effect == "shards":
            for _ in range(26):
                self.ambient.append({
                    "x": random.uniform(0, WIDTH), "y": random.uniform(-HEIGHT, HEIGHT),
                    "r": random.uniform(4, 13), "spin": random.uniform(0, math.tau),
                    "spd": random.uniform(28, 70), "rot": random.uniform(-1.4, 1.4),
                    "shape": None})
        elif self.effect == "embers":
            for _ in range(40):
                self.ambient.append({
                    "x": random.uniform(0, WIDTH), "y": random.uniform(0, HEIGHT),
                    "r": random.uniform(1.5, 4), "spin": 0.0,
                    "spd": -random.uniform(20, 70), "rot": 0.0, "shape": None})
        elif self.effect == "voidrift":
            for _ in range(9):
                self.ambient.append({
                    "x": random.uniform(0, WIDTH), "y": random.uniform(0, HEIGHT),
                    "r": random.uniform(40, 120), "spin": random.uniform(0, math.tau),
                    "spd": random.uniform(8, 22), "rot": random.uniform(-0.2, 0.2),
                    "shape": None})

    def update(self, dt):
        self.time += dt
        # Kulissen-Objekte des aktuellen Biomes
        for obj in self.ambient:
            obj["y"] += obj["spd"] * dt * self.boost
            obj["spin"] += obj["rot"] * dt
            if obj["spd"] > 0 and obj["y"] - obj["r"] > HEIGHT:
                obj["y"] = -obj["r"]
                obj["x"] = random.uniform(0, WIDTH)
            elif obj["spd"] < 0 and obj["y"] + obj["r"] < 0:
                obj["y"] = HEIGHT + obj["r"]
                obj["x"] = random.uniform(0, WIDTH)
        if self.effect == "lightning":
            self.flash = max(0.0, self.flash - dt * 4.5)
            self.flash_timer -= dt
            if self.flash_timer <= 0:
                self.flash_timer = random.uniform(2.5, 7.0)
                self.flash = 1.0
        for neb in self.nebulae:
            neb["y"] += neb["speed"] * dt * self.boost
            if neb["y"] - neb["r"] > HEIGHT:
                neb["y"] = -neb["r"]
                neb["x"] = random.uniform(0, WIDTH)
        for star in self.stars:
            star["y"] += star["speed"] * dt * self.boost
            if star["y"] > HEIGHT:
                star["y"] -= HEIGHT + random.uniform(0, 40)
                star["x"] = random.uniform(0, WIDTH)

    def draw(self, surface):
        ground = self.space
        if self.effect == "lightning" and self.flash > 0.01:
            ground = mix_color(ground, (120, 255, 210), 0.30 * self.flash)
        surface.fill(ground)
        for neb in self.nebulae:
            blit_glow(surface, neb["color"], (int(neb["x"]), int(neb["y"])), int(neb["r"]))
        self.draw_ambient(surface)
        for star in self.stars:
            color = star["color"]
            if star["twinkle"]:
                pulse = 0.65 + 0.35 * math.sin(self.time * 3.0 + star["phase"])
                color = scale_color(color, pulse)
            x, y, r = int(star["x"]), int(star["y"]), star["r"]
            if star["layer"] == 2:
                # Schnellste Ebene bekommt einen kurzen Bewegungs-Streak
                pygame.draw.line(surface, scale_color(color, 0.55), (x, y - 7), (x, y), 2)
            if r <= 1:
                surface.set_at((clamp(x, 0, WIDTH - 1), clamp(y, 0, HEIGHT - 1)), color)
            else:
                pygame.draw.circle(surface, color, (x, y), r)

    def draw_ambient(self, surface):
        """Kulisse des Biomes: Asteroiden, Kristalle, Glut oder Risse."""
        if self.effect == "rocks":
            for obj in self.ambient:
                pts = []
                for i, f in enumerate(obj["shape"]):
                    a = obj["spin"] + math.tau * i / len(obj["shape"])
                    pts.append((obj["x"] + math.cos(a) * obj["r"] * f,
                                obj["y"] + math.sin(a) * obj["r"] * f))
                pygame.draw.polygon(surface, (34, 28, 26), pts)
                pygame.draw.lines(surface, (74, 62, 54), True, pts, 1)
        elif self.effect == "shards":
            for obj in self.ambient:
                pts = rot_points([(0, -obj["r"]), (obj["r"] * 0.5, 0),
                                  (0, obj["r"]), (-obj["r"] * 0.5, 0)],
                                 obj["spin"], obj["x"], obj["y"])
                pygame.draw.polygon(surface, (18, 48, 82), pts)
                pygame.draw.lines(surface, (70, 150, 210), True, pts, 1)
        elif self.effect == "embers":
            for obj in self.ambient:
                glow = 0.55 + 0.45 * math.sin(self.time * 4 + obj["x"])
                pygame.draw.circle(surface, scale_color((255, 130, 50), glow),
                                   (int(obj["x"]), int(obj["y"])), max(1, int(obj["r"])))
        elif self.effect == "voidrift":
            for obj in self.ambient:
                a = obj["spin"]
                dx, dy = math.cos(a) * obj["r"], math.sin(a) * obj["r"]
                pygame.draw.line(surface, (46, 20, 78),
                                 (obj["x"] - dx, obj["y"] - dy),
                                 (obj["x"] + dx, obj["y"] + dy), 3)
                pygame.draw.line(surface, (96, 50, 150),
                                 (obj["x"] - dx * 0.5, obj["y"] - dy * 0.5),
                                 (obj["x"] + dx * 0.5, obj["y"] + dy * 0.5), 1)
        elif self.effect == "lightning" and self.flash > 0.05:
            random.seed(int(self.time * 3))
            x = random.uniform(0, WIDTH)
            pts = [(x, 0)]
            y = 0
            while y < HEIGHT:
                y += random.uniform(40, 90)
                x += random.uniform(-60, 60)
                pts.append((clamp(x, 0, WIDTH), y))
            col = scale_color((150, 255, 220), self.flash)
            pygame.draw.lines(surface, col, False, pts, max(1, int(3 * self.flash)))
            random.seed()


# ==============================================================================
#  PARTIKEL- UND EFFEKTSYSTEM
# ==============================================================================

class Particle:
    __slots__ = ("pos", "vel", "life", "max_life", "color", "size", "drag", "gravity")

    def __init__(self, pos, vel, life, color, size, drag=0.94, gravity=0.0):
        self.pos = Vector2(pos)
        self.vel = Vector2(vel)
        self.life = life
        self.max_life = life
        self.color = color
        self.size = size
        self.drag = drag
        self.gravity = gravity

    def update(self, dt):
        self.pos += self.vel * dt
        self.vel *= self.drag ** (dt * 60)
        self.vel.y += self.gravity * dt
        self.life -= dt
        return self.life > 0

    def draw(self, surface):
        t = clamp(self.life / self.max_life, 0.0, 1.0)
        radius = max(1, int(self.size * (0.35 + 0.65 * t)))
        color = scale_color(self.color, 0.25 + 0.75 * t)
        pygame.draw.circle(surface, color, (int(self.pos.x), int(self.pos.y)), radius)


class Shockwave:
    __slots__ = ("pos", "radius", "max_radius", "life", "max_life", "color", "width")

    def __init__(self, pos, max_radius, life, color, width=3):
        self.pos = Vector2(pos)
        self.radius = 4.0
        self.max_radius = max_radius
        self.life = life
        self.max_life = life
        self.color = color
        self.width = width

    def update(self, dt):
        self.life -= dt
        t = 1.0 - clamp(self.life / self.max_life, 0.0, 1.0)
        self.radius = 4 + (self.max_radius - 4) * (1 - (1 - t) ** 2)
        return self.life > 0

    def draw(self, surface):
        t = clamp(self.life / self.max_life, 0.0, 1.0)
        width = max(1, int(self.width * t))
        color = scale_color(self.color, 0.2 + 0.8 * t)
        pygame.draw.circle(surface, color, (int(self.pos.x), int(self.pos.y)),
                           int(self.radius), width)


class FloatingText:
    __slots__ = ("pos", "text", "color", "life", "max_life", "size")

    def __init__(self, pos, text, color, life=0.9, size=22):
        self.pos = Vector2(pos)
        self.text = text
        self.color = color
        self.life = life
        self.max_life = life
        self.size = size

    def update(self, dt):
        self.pos.y -= 34 * dt
        self.life -= dt
        return self.life > 0

    def draw(self, surface):
        t = clamp(self.life / self.max_life, 0.0, 1.0)
        draw_text(surface, self.text, self.size, int(self.pos.x), int(self.pos.y),
                  self.color, anchor="center", alpha=int(255 * t))


class Beam:
    """Kurzlebige Linie - fuer Kettenblitze und aehnliche Treffereffekte."""

    __slots__ = ("a", "b", "life", "max_life", "color", "width")

    def __init__(self, a, b, color, life=0.18, width=3):
        self.a = Vector2(a)
        self.b = Vector2(b)
        self.life = life
        self.max_life = life
        self.color = color
        self.width = width

    def update(self, dt):
        self.life -= dt
        return self.life > 0

    def draw(self, surface):
        t = clamp(self.life / self.max_life, 0.0, 1.0)
        col = scale_color(self.color, 0.3 + 0.7 * t)
        width = max(1, int(self.width * t))
        pygame.draw.line(surface, col, self.a, self.b, width)
        pygame.draw.line(surface, mix_color(col, WHITE, 0.6), self.a, self.b,
                         max(1, width // 2))


class EffectSystem:
    """Sammelt Partikel, Schockwellen und Schadenszahlen; deckelt die Menge,
    damit die Framerate auch bei Massenexplosionen stabil bleibt."""

    MAX_PARTICLES = 900

    def __init__(self):
        self.particles = []
        self.waves = []
        self.texts = []
        self.beams = []

    def clear(self):
        self.particles.clear()
        self.waves.clear()
        self.texts.clear()
        self.beams.clear()

    def beam(self, a, b, color, life=0.18, width=3):
        if len(self.beams) < 40:
            self.beams.append(Beam(a, b, color, life, width))

    def add_particle(self, *args, **kwargs):
        if len(self.particles) < self.MAX_PARTICLES:
            self.particles.append(Particle(*args, **kwargs))

    def spark(self, pos, color, count=6, speed=140, life=0.35, size=3):
        for _ in range(count):
            angle = random.uniform(0, math.tau)
            spd = speed * random.uniform(0.25, 1.0)
            self.add_particle(pos, (math.cos(angle) * spd, math.sin(angle) * spd),
                              life * random.uniform(0.6, 1.3), color,
                              size * random.uniform(0.6, 1.2))

    def explosion(self, pos, color, size=1.0, count=26, ring=True):
        for _ in range(int(count)):
            angle = random.uniform(0, math.tau)
            spd = random.uniform(40, 320) * size
            col = color if random.random() < 0.7 else mix_color(color, WHITE, 0.6)
            self.add_particle(pos, (math.cos(angle) * spd, math.sin(angle) * spd),
                              random.uniform(0.25, 0.75) * size, col,
                              random.uniform(2, 5) * size, drag=0.93)
        if ring:
            self.waves.append(Shockwave(pos, 40 * size + 22, 0.42 * size + 0.15,
                                        mix_color(color, WHITE, 0.4),
                                        width=int(2 + 2 * size)))

    def ring(self, pos, color, radius, life=0.35, width=3):
        """Einzelne Schockwelle mit vorgegebenem Endradius."""
        if len(self.waves) < 60:
            self.waves.append(Shockwave(pos, radius, life, color, width=width))

    def text(self, pos, text, color, size=22):
        if len(self.texts) < 40:
            self.texts.append(FloatingText(pos, text, color, size=size))

    def update(self, dt):
        self.particles = [p for p in self.particles if p.update(dt)]
        self.waves = [w for w in self.waves if w.update(dt)]
        self.texts = [t for t in self.texts if t.update(dt)]
        self.beams = [b for b in self.beams if b.update(dt)]

    def draw(self, surface):
        for p in self.particles:
            p.draw(surface)
        for w in self.waves:
            w.draw(surface)
        for b in self.beams:
            b.draw(surface)

    def draw_texts(self, surface):
        for t in self.texts:
            t.draw(surface)

# ==============================================================================
#  SKIN-GARAGE :: SCHIFFSDESIGNS UND WERTE
# ==============================================================================

def draw_phoenix(surface, x, y, scale, t, thrust=1.0):
    """Classic Phoenix - schlanker Pfeil mit geschwungenen Fluegeln, Cyan/Blau."""
    hull = [(0, -26), (7, -10), (10, 8), (5, 18), (-5, 18), (-10, 8), (-7, -10)]
    wing_r = [(7, -6), (26, 6), (30, 16), (12, 14), (6, 16)]
    wing_l = [(-p[0], p[1]) for p in wing_r]
    tail = [(0, 18), (9, 26), (0, 22), (-9, 26)]

    pygame.draw.polygon(surface, (10, 30, 62), rot_points(wing_r, 0, x, y, scale))
    pygame.draw.polygon(surface, (10, 30, 62), rot_points(wing_l, 0, x, y, scale))
    neon_poly(surface, BLUE, rot_points(wing_r, 0, x, y, scale), 2)
    neon_poly(surface, BLUE, rot_points(wing_l, 0, x, y, scale), 2)
    pygame.draw.polygon(surface, (12, 40, 78), rot_points(hull, 0, x, y, scale))
    neon_poly(surface, CYAN, rot_points(hull, 0, x, y, scale), 2)
    neon_poly(surface, scale_color(CYAN, 0.8), rot_points(tail, 0, x, y, scale), 1)
    # Cockpit
    pulse = 0.7 + 0.3 * math.sin(t * 5)
    blit_glow(surface, CYAN, (x, y - 4 * scale), 11 * scale)
    pygame.draw.circle(surface, scale_color(WHITE, pulse),
                       (int(x), int(y - 5 * scale)), max(1, int(3.2 * scale)))
    if thrust > 0.05:
        flame = 12 * scale * thrust * (0.75 + 0.25 * math.sin(t * 28))
        blit_glow(surface, BLUE, (x, y + 22 * scale), flame)


def draw_vanguard(surface, x, y, scale, t, thrust=1.0):
    """Plasma Vanguard - aggressiver Dart mit Doppelklingen, Neon-Gruen."""
    hull = [(0, -30), (6, -12), (8, 10), (0, 20), (-8, 10), (-6, -12)]
    blade_r = [(6, -14), (14, -20), (22, 4), (18, 18), (9, 8)]
    blade_l = [(-p[0], p[1]) for p in blade_r]
    fin = [(0, -30), (0, -8), (3, 2), (-3, 2)]

    pygame.draw.polygon(surface, (8, 46, 26), rot_points(blade_r, 0, x, y, scale))
    pygame.draw.polygon(surface, (8, 46, 26), rot_points(blade_l, 0, x, y, scale))
    neon_poly(surface, GREEN, rot_points(blade_r, 0, x, y, scale), 2)
    neon_poly(surface, GREEN, rot_points(blade_l, 0, x, y, scale), 2)
    pygame.draw.polygon(surface, (10, 56, 34), rot_points(hull, 0, x, y, scale))
    neon_poly(surface, LIME, rot_points(hull, 0, x, y, scale), 2)
    neon_poly(surface, scale_color(LIME, 0.9), rot_points(fin, 0, x, y, scale), 1)
    blit_glow(surface, GREEN, (x, y - 2 * scale), 12 * scale)
    pygame.draw.circle(surface, WHITE, (int(x), int(y - 4 * scale)),
                       max(1, int(2.6 * scale)))
    for side in (-1, 1):
        pygame.draw.circle(surface, LIME,
                           (int(x + side * 17 * scale), int(y + 6 * scale)),
                           max(1, int(2 * scale)))
    if thrust > 0.05:
        flame = 14 * scale * thrust * (0.7 + 0.3 * math.sin(t * 34))
        for side in (-1, 1):
            blit_glow(surface, GREEN, (x + side * 5 * scale, y + 20 * scale), flame)


def draw_dreadnought(surface, x, y, scale, t, thrust=1.0):
    """Dreadnought - massiver Panzerkreuzer mit Schildringen, Rot/Orange."""
    hull = [(0, -24), (12, -12), (15, 8), (9, 22), (-9, 22), (-15, 8), (-12, -12)]
    armor_r = [(12, -10), (30, -2), (34, 12), (24, 20), (12, 16)]
    armor_l = [(-p[0], p[1]) for p in armor_r]
    plate = [(0, -14), (8, -4), (0, 8), (-8, -4)]

    pygame.draw.polygon(surface, (58, 12, 18), rot_points(armor_r, 0, x, y, scale))
    pygame.draw.polygon(surface, (58, 12, 18), rot_points(armor_l, 0, x, y, scale))
    neon_poly(surface, RED, rot_points(armor_r, 0, x, y, scale), 2)
    neon_poly(surface, RED, rot_points(armor_l, 0, x, y, scale), 2)
    pygame.draw.polygon(surface, (72, 16, 22), rot_points(hull, 0, x, y, scale))
    neon_poly(surface, ORANGE, rot_points(hull, 0, x, y, scale), 3)
    neon_poly(surface, YELLOW, rot_points(plate, 0, x, y, scale), 1)
    blit_glow(surface, RED, (x, y - 2 * scale), 14 * scale)
    pygame.draw.circle(surface, mix_color(YELLOW, WHITE, 0.5),
                       (int(x), int(y - 4 * scale)), max(1, int(3.4 * scale)))
    for side in (-1, 1):
        pygame.draw.circle(surface, ORANGE,
                           (int(x + side * 26 * scale), int(y + 8 * scale)),
                           max(1, int(2.5 * scale)), 1)
    if thrust > 0.05:
        flame = 13 * scale * thrust * (0.75 + 0.25 * math.sin(t * 22))
        for side in (-1, 1):
            blit_glow(surface, ORANGE, (x + side * 7 * scale, y + 24 * scale), flame)


def draw_wraith(surface, x, y, scale, t, thrust=1.0):
    """Wraith - Phasenjaeger, schmal und kantig, violettes Nachbild."""
    hull = [(0, -30), (7, -10), (5, 12), (0, 22), (-5, 12), (-7, -10)]
    blade_r = [(6, -6), (20, 4), (17, 16), (5, 10)]
    blade_l = [(-p[0], p[1]) for p in blade_r]
    ghost = 0.5 + 0.5 * math.sin(t * 2.2)

    for offset in (-11 * ghost, 0):
        alpha = 0.35 if offset else 1.0
        col = scale_color(PURPLE, alpha)
        pygame.draw.polygon(surface, scale_color((40, 16, 66), alpha),
                            rot_points(hull, 0, x + offset * scale, y, scale))
        neon_poly(surface, col, rot_points(hull, 0, x + offset * scale, y, scale), 2,
                  halo=0.2 * alpha)
    pygame.draw.polygon(surface, (34, 14, 58), rot_points(blade_r, 0, x, y, scale))
    pygame.draw.polygon(surface, (34, 14, 58), rot_points(blade_l, 0, x, y, scale))
    neon_poly(surface, (200, 150, 255), rot_points(blade_r, 0, x, y, scale), 2)
    neon_poly(surface, (200, 150, 255), rot_points(blade_l, 0, x, y, scale), 2)
    blit_glow(surface, PURPLE, (x, y - 4 * scale), 12 * scale)
    pygame.draw.circle(surface, WHITE, (int(x), int(y - 6 * scale)),
                       max(1, int(2.6 * scale)))
    if thrust > 0.05:
        blit_glow(surface, PURPLE, (x, y + 22 * scale),
                  11 * scale * thrust * (0.7 + 0.3 * math.sin(t * 30)))


def draw_bastion(surface, x, y, scale, t, thrust=1.0):
    """Bastion - gedrungener Schildtraeger mit schwerem Bug."""
    hull = [(0, -22), (14, -8), (17, 10), (9, 22), (-9, 22), (-17, 10), (-14, -8)]
    plate = [(0, -12), (10, -2), (0, 12), (-10, -2)]
    pygame.draw.polygon(surface, (10, 34, 58), rot_points(hull, 0, x, y, scale))
    neon_poly(surface, CRYSTAL, rot_points(hull, 0, x, y, scale), 3)
    neon_poly(surface, (170, 225, 255), rot_points(plate, 0, x, y, scale), 2)
    for side in (-1, 1):
        pygame.draw.circle(surface, (150, 210, 255),
                           (int(x + side * 13 * scale), int(y + 12 * scale)),
                           max(1, int(3 * scale)))
    blit_glow(surface, CRYSTAL, (x, y), 15 * scale)
    pygame.draw.circle(surface, WHITE, (int(x), int(y - 2 * scale)),
                       max(1, int(3.2 * scale)))
    if thrust > 0.05:
        blit_glow(surface, CRYSTAL, (x, y + 24 * scale),
                  12 * scale * thrust * (0.75 + 0.25 * math.sin(t * 20)))


def draw_hydra(surface, x, y, scale, t, thrust=1.0):
    """Hydra - Rundumfeuer, breite Kanzel mit vier Laeufen."""
    hull = [(0, -24), (10, -6), (12, 10), (0, 20), (-12, 10), (-10, -6)]
    arm_r = [(11, -2), (28, 4), (25, 14), (10, 10)]
    arm_l = [(-p[0], p[1]) for p in arm_r]
    pygame.draw.polygon(surface, (10, 44, 36), rot_points(arm_r, 0, x, y, scale))
    pygame.draw.polygon(surface, (10, 44, 36), rot_points(arm_l, 0, x, y, scale))
    neon_poly(surface, (120, 255, 220), rot_points(arm_r, 0, x, y, scale), 2)
    neon_poly(surface, (120, 255, 220), rot_points(arm_l, 0, x, y, scale), 2)
    pygame.draw.polygon(surface, (10, 52, 42), rot_points(hull, 0, x, y, scale))
    neon_poly(surface, (140, 255, 230), rot_points(hull, 0, x, y, scale), 2)
    for dx, dy in ((0, -26), (0, 22), (26, 8), (-26, 8)):
        pygame.draw.circle(surface, (170, 255, 240),
                           (int(x + dx * scale), int(y + dy * scale)),
                           max(1, int(2.4 * scale)))
    blit_glow(surface, (120, 255, 220), (x, y), 13 * scale)
    pygame.draw.circle(surface, WHITE, (int(x), int(y - 3 * scale)),
                       max(1, int(2.8 * scale)))


def draw_helios(surface, x, y, scale, t, thrust=1.0):
    """Helios - Ladeschuss-Schiff mit Fokuslinse im Bug."""
    hull = [(0, -28), (10, -8), (8, 12), (0, 22), (-8, 12), (-10, -8)]
    wing_r = [(8, -4), (24, 2), (20, 16), (7, 12)]
    wing_l = [(-p[0], p[1]) for p in wing_r]
    pulse = 0.5 + 0.5 * math.sin(t * 3)
    pygame.draw.polygon(surface, (56, 40, 8), rot_points(wing_r, 0, x, y, scale))
    pygame.draw.polygon(surface, (56, 40, 8), rot_points(wing_l, 0, x, y, scale))
    neon_poly(surface, ORANGE, rot_points(wing_r, 0, x, y, scale), 2)
    neon_poly(surface, ORANGE, rot_points(wing_l, 0, x, y, scale), 2)
    pygame.draw.polygon(surface, (66, 48, 10), rot_points(hull, 0, x, y, scale))
    neon_poly(surface, GOLD, rot_points(hull, 0, x, y, scale), 2)
    blit_glow(surface, GOLD, (x, y - 14 * scale), (7 + 4 * pulse) * scale)
    pygame.draw.circle(surface, mix_color(GOLD, WHITE, pulse),
                       (int(x), int(y - 14 * scale)), max(1, int(3.4 * scale)))
    pygame.draw.circle(surface, WHITE, (int(x), int(y + 2 * scale)),
                       max(1, int(2.4 * scale)))
    if thrust > 0.05:
        blit_glow(surface, ORANGE, (x, y + 22 * scale),
                  11 * scale * thrust * (0.75 + 0.25 * math.sin(t * 24)))


def draw_locust(surface, x, y, scale, t, thrust=1.0):
    """Locust - Traegerschiff, schmaler Rumpf mit Andockbuchten."""
    hull = [(0, -24), (8, -6), (10, 10), (0, 20), (-10, 10), (-8, -6)]
    bay_r = [(9, -2), (21, 2), (19, 12), (8, 9)]
    bay_l = [(-p[0], p[1]) for p in bay_r]
    pygame.draw.polygon(surface, (48, 38, 8), rot_points(bay_r, 0, x, y, scale))
    pygame.draw.polygon(surface, (48, 38, 8), rot_points(bay_l, 0, x, y, scale))
    neon_poly(surface, YELLOW, rot_points(bay_r, 0, x, y, scale), 2)
    neon_poly(surface, YELLOW, rot_points(bay_l, 0, x, y, scale), 2)
    pygame.draw.polygon(surface, (54, 42, 10), rot_points(hull, 0, x, y, scale))
    neon_poly(surface, (255, 226, 120), rot_points(hull, 0, x, y, scale), 2)
    blit_glow(surface, YELLOW, (x, y - 2 * scale), 12 * scale)
    pygame.draw.circle(surface, WHITE, (int(x), int(y - 4 * scale)),
                       max(1, int(2.6 * scale)))
    if thrust > 0.05:
        blit_glow(surface, YELLOW, (x, y + 21 * scale),
                  10 * scale * thrust * (0.75 + 0.25 * math.sin(t * 26)))


SHIPS = {
    "phoenix": {
        "name": "Classic Phoenix",
        "tag": "Ausgeglichener Allrounder",
        "draw": draw_phoenix,
        "price": 0,
        "hp_mult": 1.00, "speed_mult": 1.00, "fire_mult": 1.00, "dmg_mult": 1.00,
        "shield": 30, "radius": 17,
        "laser": CYAN, "laser2": BLUE, "accent": CYAN,
        "bullet_w": 3, "bullet_h": 14, "bullet_speed": 780,
        "notes": "Blaue Praezisionslaser, keine Schwaechen.",
    },
    "vanguard": {
        "name": "Plasma Vanguard",
        "tag": "Glaskanone mit Highspeed-Feuer",
        "draw": draw_vanguard,
        "price": 12,
        "hp_mult": 0.78, "speed_mult": 1.16, "fire_mult": 1.38, "dmg_mult": 0.86,
        "shield": 15, "radius": 16,
        "laser": GREEN, "laser2": LIME, "accent": GREEN,
        "bullet_w": 2, "bullet_h": 17, "bullet_speed": 900,
        "power_mult": 0.90,   # hohe Kadenz taeuscht mehr Kampfkraft vor
        "notes": "Feuert 38% schneller, haelt aber deutlich weniger aus.",
    },
    "dreadnought": {
        "name": "Dreadnought",
        "tag": "Schwerer Panzerkreuzer",
        "draw": draw_dreadnought,
        "price": 25,
        "hp_mult": 1.28, "speed_mult": 0.86, "fire_mult": 0.84, "dmg_mult": 1.22,
        "shield": 90, "radius": 21,
        "laser": RED, "laser2": ORANGE, "accent": ORANGE,
        "bullet_w": 6, "bullet_h": 16, "bullet_speed": 700,
        "notes": "Massiver Schild, dicke rote Laser, traegere Steuerung.",
    },
}

SHIPS.update({
    "wraith": {
        "name": "Wraith",
        "tag": "Phasenjaeger mit Blink",
        "draw": draw_wraith,
        "price": 40,
        "hp_mult": 0.62, "speed_mult": 1.30, "fire_mult": 1.15, "dmg_mult": 0.90,
        "shield": 10, "radius": 15,
        "laser": PURPLE, "laser2": (210, 160, 255), "accent": PURPLE,
        "bullet_w": 2, "bullet_h": 16, "bullet_speed": 880,
        "mechanic": "blink",
        "power_mult": 1.05,   # Blink rettet Leben, zaehlt aber nicht als Schaden
        "notes": "SHIFT setzt einen Kurzsprung mit Unverwundbarkeit.",
    },
    "bastion": {
        "name": "Bastion",
        "tag": "Schildtraeger mit Orbitalkugeln",
        "draw": draw_bastion,
        "price": 70,
        "hp_mult": 1.15, "speed_mult": 0.80, "fire_mult": 0.85, "dmg_mult": 1.05,
        "shield": 60, "radius": 19,
        "laser": CRYSTAL, "laser2": (180, 230, 255), "accent": CRYSTAL,
        "bullet_w": 4, "bullet_h": 15, "bullet_speed": 720,
        "mechanic": "orbs",
        "power_mult": 1.05,   # Kugeln helfen beim Ueberleben, nicht beim Raeumen
        "notes": "Kreisende Kugeln fangen gegnerische Geschosse ab.",
    },
    "hydra": {
        "name": "Hydra",
        "tag": "Rundumfeuer statt Frontlast",
        "draw": draw_hydra,
        "price": 100,
        "hp_mult": 1.00, "speed_mult": 1.00, "fire_mult": 0.95, "dmg_mult": 0.72,
        "shield": 25, "radius": 17,
        "laser": (120, 255, 220), "laser2": (200, 255, 240), "accent": (120, 255, 220),
        "bullet_w": 3, "bullet_h": 13, "bullet_speed": 760,
        "mechanic": "omni",
        "power_mult": 1.45,   # Seitenlaeufe verdoppeln den Ausstoss
        "notes": "Feuert zusaetzlich nach hinten und zu beiden Seiten.",
    },
    "helios": {
        "name": "Helios",
        "tag": "Ladeschuss statt Dauerfeuer",
        "draw": draw_helios,
        "price": 140,
        "hp_mult": 0.95, "speed_mult": 0.92, "fire_mult": 0.60, "dmg_mult": 1.00,
        "shield": 30, "radius": 17,
        "laser": GOLD, "laser2": (255, 235, 160), "accent": GOLD,
        "bullet_w": 5, "bullet_h": 22, "bullet_speed": 900,
        "mechanic": "charge",
        # Der Ladeschuss feuert seltener, als die Werte suggerieren - aber
        # nach dem Buff nicht mehr halb so stark. Gemessen: 64 % der Phoenix.
        "power_mult": 0.95,
        "notes": "Feuertaste halten laedt einen durchschlagenden Strahl.",
    },
    "locust": {
        "name": "Locust",
        "tag": "Traegerschiff mit Drohnenschwarm",
        "draw": draw_locust,
        "price": 180,
        "hp_mult": 0.90, "speed_mult": 1.05, "fire_mult": 0.80, "dmg_mult": 0.68,
        "shield": 20, "radius": 16,
        "laser": YELLOW, "laser2": (255, 240, 170), "accent": YELLOW,
        "bullet_w": 2, "bullet_h": 12, "bullet_speed": 700,
        "mechanic": "drones",
        # Gemessen lag die Locust bei 56 % der Phoenix, der Index bei 80 % -
        # sie bekam also zu harte Gegner fuer ihre Feuerkraft. Korrigiert.
        "power_mult": 1.40,
        "notes": "Drei Drohnen feuern selbstaendig Zielsuchraketen.",
    },
})

SHIP_ORDER = ["phoenix", "vanguard", "dreadnought",
              "wraith", "bastion", "hydra", "helios", "locust"]

DEFAULT_SAVE["ranks"] = {key: 0 for key in SHIP_ORDER}


# ==============================================================================
#  PROJEKTILE
# ==============================================================================

class Bullet:
    """Spielerprojektil.

    `pierce` erlaubt Durchschuss durch mehrere Gegner, `homing` macht das
    Geschoss zur Zielsuchrakete, `splash` gibt Flaechenschaden beim Treffer."""

    __slots__ = ("pos", "vel", "damage", "color", "color2", "w", "h", "radius",
                 "alive", "pierce", "hits", "homing", "splash", "angle", "spin",
                 "bounced")

    def __init__(self, pos, vel, damage, color, color2, w, h,
                 pierce=0, homing=0.0, splash=0.0):
        self.pos = Vector2(pos)
        self.vel = Vector2(vel)
        self.damage = damage
        self.color = color
        self.color2 = color2
        self.w = w
        self.h = h
        self.radius = max(w, 4)
        self.alive = True
        self.pierce = pierce
        self.hits = set()
        self.homing = homing              # Drehrate in rad/s
        self.splash = splash              # Radius des Flaechenschadens
        self.angle = math.atan2(vel.y, vel.x) if vel.length_squared() else -math.pi / 2
        self.spin = 0.0
        self.bounced = False

    def update(self, dt, enemies=None):
        if self.homing > 0 and enemies:
            target = None
            best = 1e18
            for enemy in enemies:
                if not enemy.alive:
                    continue
                d = (enemy.pos - self.pos).length_squared()
                if d < best:
                    best, target = d, enemy
            if target is not None:
                want = math.atan2(target.pos.y - self.pos.y,
                                  target.pos.x - self.pos.x)
                diff = (want - self.angle + math.pi) % math.tau - math.pi
                self.angle += clamp(diff, -self.homing * dt, self.homing * dt)
                speed = self.vel.length()
                self.vel = Vector2(math.cos(self.angle),
                                   math.sin(self.angle)) * speed
        self.pos += self.vel * dt
        self.spin += dt * 12
        if (self.pos.y < -40 or self.pos.y > HEIGHT + 40
                or self.pos.x < -40 or self.pos.x > WIDTH + 40):
            self.alive = False

    def on_hit(self, enemy, game):
        """Nach einem Treffer: Flaechenschaden und Durchschuss abwickeln."""
        if self.splash > 0:
            game.effects.explosion(self.pos, self.color, size=self.splash / 55.0,
                                   count=14)
            game.effects.waves.append(Shockwave(self.pos, self.splash, 0.3,
                                                self.color, 2))
            for other in game.enemies:
                if other is enemy or not other.alive:
                    continue
                if (other.pos - self.pos).length_squared() <= self.splash ** 2:
                    other.damage(self.damage * 0.6, game)
        if self.pierce > 0:
            self.pierce -= 1
            self.hits.add(id(enemy))
            return True                   # Geschoss fliegt weiter
        return False

    def draw(self, surface):
        x, y = self.pos.x, self.pos.y
        blit_glow(surface, self.color, (int(x), int(y)), int(self.h * 0.85))
        if self.homing > 0:
            pts = rot_points([(self.h * 0.5, 0), (-self.h * 0.3, self.w),
                              (-self.h * 0.15, 0), (-self.h * 0.3, -self.w)],
                             self.angle, x, y)
            pygame.draw.polygon(surface, self.color2, pts)
            pygame.draw.polygon(surface, WHITE, pts, 1)
            return
        rect = pygame.Rect(0, 0, self.w * 2, self.h)
        rect.center = (int(x), int(y))
        pygame.draw.rect(surface, self.color2, rect, border_radius=self.w)
        inner = rect.inflate(-max(2, self.w), -4)
        pygame.draw.rect(surface, mix_color(self.color, WHITE, 0.75), inner,
                         border_radius=max(1, self.w // 2))


class EnemyBullet:
    """Gegnerprojektil. `kind` steuert Optik und Verhalten:
    orb (gerade), laser (schnelle Nadel), homing (Zielsuch-Laser),
    bomb (langsam, gross, hoher Schaden - dafuer abschiessbar)."""

    __slots__ = ("pos", "vel", "damage", "color", "radius", "alive", "kind",
                 "angle", "turn", "life", "spin", "source", "source_mut",
                 "hp", "blast", "fuse")

    def __init__(self, pos, vel, damage, color, radius=6, kind="orb",
                 turn=0.0, life=9.0, source="?", source_mut=(), hp=0.0,
                 blast=0.0):
        self.pos = Vector2(pos)
        self.vel = Vector2(vel)
        self.damage = damage
        self.color = color
        self.radius = radius
        self.kind = kind
        self.turn = turn                    # rad/s fuer Zielsuche
        self.life = life
        self.alive = True
        self.angle = math.atan2(vel.y, vel.x) if vel.length_squared() > 0 else math.pi / 2
        self.spin = random.uniform(0, math.tau)
        self.source = source                 # fuer die Todesursachen-Statistik
        self.source_mut = tuple(source_mut)
        # Bomben lassen sich abschiessen. Das ist die Gegenwehr gegen ein
        # langsames Geschoss mit sehr hohem Schaden: wer reagiert, kommt durch.
        self.hp = hp
        self.blast = blast
        self.fuse = 0.0

    def update(self, dt, player_pos=None):
        if self.kind == "homing" and player_pos is not None and self.turn > 0:
            target = math.atan2(player_pos.y - self.pos.y, player_pos.x - self.pos.x)
            diff = (target - self.angle + math.pi) % math.tau - math.pi
            self.angle += clamp(diff, -self.turn * dt, self.turn * dt)
            speed = self.vel.length()
            self.vel = Vector2(math.cos(self.angle), math.sin(self.angle)) * speed
        self.pos += self.vel * dt
        self.spin += dt * 6
        self.life -= dt
        if self.blast > 0:
            self.fuse += dt
        if (self.life <= 0 or self.pos.y < -60 or self.pos.y > HEIGHT + 60
                or self.pos.x < -60 or self.pos.x > WIDTH + 60):
            self.alive = False

    def draw(self, surface):
        x, y = int(self.pos.x), int(self.pos.y)
        blit_glow(surface, self.color, (x, y), int(self.radius * 3.2))
        if self.kind == "laser":
            tip = self.pos + Vector2(math.cos(self.angle), math.sin(self.angle)) * self.radius * 2.6
            tail = self.pos - Vector2(math.cos(self.angle), math.sin(self.angle)) * self.radius * 2.6
            pygame.draw.line(surface, self.color, tip, tail, max(2, int(self.radius)))
            pygame.draw.line(surface, WHITE, tip, tail, max(1, int(self.radius // 2)))
        elif self.kind == "homing":
            pts = rot_points([(9, 0), (-4, 5), (-2, 0), (-4, -5)], self.angle, x, y,
                             self.radius / 3.4)
            pygame.draw.polygon(surface, self.color, pts)
            pygame.draw.polygon(surface, WHITE, pts, 1)
        elif self.kind == "bomb":
            # Grosse taumelnde Mine mit blinkendem Zuender und Warnkreis:
            # sie MUSS auf den ersten Blick als Gefahr lesbar sein.
            pulse = 0.5 + 0.5 * math.sin(self.fuse * 9.0)
            r = int(self.radius)
            pygame.draw.circle(surface, (255, 190, 60), (x, y), int(self.blast), 1)
            pygame.draw.circle(surface, scale_color(self.color, 0.45), (x, y), r)
            neon_poly(surface, self.color,
                      rot_points([(0, -r), (r, 0), (0, r), (-r, 0)],
                                 self.spin * 0.35, x, y), 2, halo=0.4)
            for i in range(6):
                ang = self.spin * 0.35 + math.tau * i / 6
                pygame.draw.line(surface, self.color, (x, y),
                                 (x + math.cos(ang) * (r + 6),
                                  y + math.sin(ang) * (r + 6)), 2)
            pygame.draw.circle(surface, mix_color(self.color, WHITE, pulse),
                               (x, y), max(2, int(r * 0.42)))
        else:
            pygame.draw.circle(surface, scale_color(self.color, 0.6), (x, y),
                               int(self.radius))
            pygame.draw.circle(surface, self.color, (x, y), max(1, int(self.radius * 0.7)))
            pygame.draw.circle(surface, WHITE, (x, y), max(1, int(self.radius * 0.3)))


# ==============================================================================
#  SAMMELBARES :: MUENZEN, KRISTALLE, REPARATURZELLEN
# ==============================================================================

class Pickup:
    KIND_COIN = "coin"
    KIND_CRYSTAL = "crystal"
    KIND_HEART = "heart"
    KIND_CRATE = "crate"

    def __init__(self, pos, kind, value=1):
        self.pos = Vector2(pos)
        angle = random.uniform(0, math.tau)
        self.vel = Vector2(math.cos(angle), math.sin(angle)) * random.uniform(40, 130)
        self.kind = kind
        self.value = value
        # Frachtkisten sind zu wertvoll, um sie zu verpassen - sie liegen
        # deutlich laenger und sind groesser als alles andere.
        self.life = 22.0 if kind == Pickup.KIND_CRATE else 13.0
        self.spin = random.uniform(0, math.tau)
        self.radius = {Pickup.KIND_COIN: 9, Pickup.KIND_CRATE: 16}.get(kind, 12)
        self.alive = True
        self.magnetized = False

    def update(self, dt, player, magnet_radius):
        self.life -= dt
        if self.life <= 0:
            self.alive = False
            return
        self.spin += dt * 3.4
        if player is not None and player.alive:
            to_player = player.pos - self.pos
            dist = to_player.length()
            if dist < magnet_radius:
                self.magnetized = True
                pull = lerp(1400, 380, clamp(dist / max(1.0, magnet_radius), 0, 1))
                self.vel += (to_player / max(dist, 1e-6)) * pull * dt
            else:
                self.magnetized = False
        self.vel *= 0.955 ** (dt * 60)
        self.vel.y += 28 * dt                       # leichter Drift nach unten
        self.pos += self.vel * dt
        self.pos.x = clamp(self.pos.x, 12, WIDTH - 12)
        if self.pos.y > HEIGHT + 30:
            self.alive = False

    def draw(self, surface):
        x, y = int(self.pos.x), int(self.pos.y)
        blink = self.life > 3.0 or int(self.life * 8) % 2 == 0
        if not blink:
            return
        if self.kind == Pickup.KIND_COIN:
            wobble = abs(math.cos(self.spin))
            w = max(2, int(self.radius * wobble))
            blit_glow(surface, GOLD, (x, y), 15)
            pygame.draw.ellipse(surface, GOLD, (x - w, y - self.radius, w * 2, self.radius * 2))
            pygame.draw.ellipse(surface, mix_color(GOLD, WHITE, 0.6),
                                (x - w, y - self.radius, w * 2, self.radius * 2), 2)
            if w > 4:
                draw_text(surface, "$", 16, x, y, (110, 70, 10), anchor="center", bold=True)
        elif self.kind == Pickup.KIND_CRYSTAL:
            blit_glow(surface, CRYSTAL, (x, y), 22)
            pts = rot_points([(0, -11), (7, 0), (0, 11), (-7, 0)], self.spin * 0.5, x, y)
            pygame.draw.polygon(surface, (20, 70, 130), pts)
            pygame.draw.polygon(surface, CRYSTAL, pts, 2)
            pygame.draw.line(surface, WHITE, (x, y - 8), (x, y + 8), 1)
        elif self.kind == Pickup.KIND_CRATE:
            # Frachtkiste: taumelnder Wuerfel mit pulsierendem Schloss
            pulse = 0.55 + 0.45 * math.sin(self.spin * 2.6)
            col = mix_color(GOLD, MAGENTA, pulse)
            blit_glow(surface, col, (x, y), 34)
            tilt = math.sin(self.spin * 0.8) * 0.22
            body = rot_points([(-13, -11), (13, -11), (13, 11), (-13, 11)],
                              tilt, x, y)
            pygame.draw.polygon(surface, (26, 20, 44), body)
            neon_poly(surface, col, body, 2, halo=0.5)
            band_a = rot_points([(-13, -2), (13, -2)], tilt, x, y)
            band_b = rot_points([(-2, -11), (-2, 11)], tilt, x, y)
            pygame.draw.line(surface, scale_color(col, 0.75), band_a[0], band_a[1], 2)
            pygame.draw.line(surface, scale_color(col, 0.75), band_b[0], band_b[1], 2)
            pygame.draw.circle(surface, mix_color(col, WHITE, pulse),
                               (x, y), max(2, int(4 * pulse) + 2))
        else:
            # Herz: zwei Kreise plus Spitze, pulsierend wie ein Herzschlag
            beat = 1.0 + 0.14 * math.sin(self.spin * 3.2)
            r = 6 * beat
            blit_glow(surface, RED, (x, y), int(20 * beat))
            pygame.draw.circle(surface, RED, (int(x - r * 0.62), int(y - r * 0.42)),
                               max(2, int(r)))
            pygame.draw.circle(surface, RED, (int(x + r * 0.62), int(y - r * 0.42)),
                               max(2, int(r)))
            tip = [(x - r * 1.42, y - r * 0.10), (x + r * 1.42, y - r * 0.10),
                   (x, y + r * 1.62)]
            pygame.draw.polygon(surface, RED, tip)
            pygame.draw.circle(surface, mix_color(RED, WHITE, 0.7),
                               (int(x - r * 0.72), int(y - r * 0.62)),
                               max(1, int(r * 0.34)))


# ==============================================================================
#  SPIELER
# ==============================================================================

class Player:
    """Traegheitsbasierte 8-Wege-Steuerung: Beschleunigung + Reibung ergeben
    ein weiches, aber praezises Flugverhalten."""

    ACCEL = 3400.0
    FRICTION = 0.86
    MAX_SPEED = 470.0

    def __init__(self, ship_key, save):
        self.ship_key = ship_key
        self.ship = SHIPS[ship_key]
        self.save = save
        self.upgrades = save["upgrades"]
        self.prog = progression_mult(save, ship_key)
        self.systems = self.prog["systems"]

        self.damage_mult = 1.0               # Overdrive aus dem Shop
        self.shield_bonus = 1.0              # Schild-Zellen aus dem Shop
        self.mod_mult = {"dmg": 1.0, "fire": 1.0, "hp": 1.0, "speed": 1.0,
                         "shield": 1.0, "taken": 1.0}
        self.mod_flags = set()

        # ------------------------------------------------ Anbauten (Kisten)
        self.addons = {a["key"]: 0 for a in ADDONS}
        self.escorts = []                    # mitfliegende Begleitdrohnen
        self.aegis = 0.0                     # zusaetzlicher Ringschild
        self.aegis_max = 0.0
        self.flak_timer = FLAK_INTERVAL

        self.max_hp = self.compute_max_hp()
        self.hp = self.max_hp
        self.max_shield = stat_shield(self.upgrades["shieldmatrix"], self.ship,
                                      self.prog)
        self.shield = self.max_shield
        self.shield_delay = 0.0

        # ------------------------------------------- Schiffseigene Mechanik
        self.mechanic = self.ship.get("mechanic")
        self.orbs = []                       # Bastion
        self.drones = []                     # Locust
        self.charge = 0.0                    # Helios
        self.blink_cd = 0.0                  # Wraith
        self.blink_charges = 0
        self.blink_held = False
        self.setup_mechanic()

        # ------------------------------------------------ Schiffssysteme
        self.heat = 0.0                      # Gluthitze / Ueberhitzung
        self.salvo_index = 0                 # Zwillingskern
        self.idle_fire = 0.0                 # Nachbrenner
        self.still_time = 0.0                # Festungsmodus
        self.reactive = 0.0                  # Reaktivpanzerung

        self.pos = Vector2(WIDTH / 2, HEIGHT - 110)
        self.vel = Vector2(0, 0)
        self.radius = self.ship["radius"]
        self.alive = True

        self.fire_timer = 0.0
        self.invuln = 1.2
        self.time = 0.0
        self.thrust = 0.0
        self.hit_flash = 0.0
        self.tilt = 0.0

    # ---------------------------------------------------------------- Werte
    def setup_mechanic(self):
        """Legt Kugeln, Drohnen und Blink-Ladungen passend zum Rang an."""
        if self.mechanic == "orbs":
            count = 2 + (1 if "third_orb" in self.systems else 0)
            self.orbs = [{"angle": math.tau * i / count, "ready": 0.0}
                         for i in range(count)]
        elif self.mechanic == "drones":
            count = 3 + (1 if "fourth_drone" in self.systems else 0)
            self.drones = [{"angle": math.tau * i / count, "timer": 0.4 * i}
                           for i in range(count)]
        elif self.mechanic == "blink":
            self.blink_max = 1 + (1 if "double_jump" in self.systems else 0)
            self.blink_charges = self.blink_max

    @property
    def blink_recharge(self):
        return 1.8 * (0.55 if "cold_start" in self.systems else 1.0)

    @property
    def charge_time(self):
        return 1.25 * (0.65 if "focus" in self.systems else 1.0)

    def compute_max_hp(self):
        return int(stat_maxhp(self.upgrades["maxhp"], self.ship, self.prog)
                   * self.mod_mult.get("hp", 1.0)
                   * (1.0 + 0.10 * self.addons["plating"]))

    @property
    def damage(self):
        value = stat_damage(self.upgrades["damage"], self.ship, self.prog)
        value *= self.damage_mult * self.mod_mult.get("dmg", 1.0)
        value *= 1.0 + 0.08 * self.addons["spotter"]
        if "heat_dmg" in self.systems:               # Gluthitze
            value *= 1.0 + 0.40 * self.heat
        if "fortress" in self.systems and self.still_time >= 1.0:
            value *= 1.50                            # Festungsmodus
        return value

    def apply_shield_bonus(self, refill=False):
        """Schildkapazitaet neu berechnen. `refill` fuellt sofort auf."""
        self.max_shield = (stat_shield(self.upgrades["shieldmatrix"], self.ship,
                                       self.prog) * self.shield_bonus
                           * self.mod_mult.get("shield", 1.0))
        if refill:
            self.shield = self.max_shield
        else:
            self.shield = min(self.shield, self.max_shield)

    @property
    def fire_cooldown(self):
        value = stat_cooldown(self.upgrades["firerate"], self.ship, self.prog)
        value /= self.mod_mult.get("fire", 1.0)
        value /= 1.0 + 0.08 * self.addons["coolant"]
        if "heat_rate" in self.systems:              # Ueberhitzung
            value /= 1.0 + 0.25 * self.heat
        if "haste" in self.mod_flags and self.hp < self.max_hp * 0.40:
            value /= 1.30                            # Adrenalin
        return value

    @property
    def magnet_radius(self):
        base = stat_magnet(self.prog["refit"])
        return 2000.0 if "magnet" in self.mod_flags else base

    @property
    def speed_cap(self):
        value = (self.MAX_SPEED * self.ship["speed_mult"] * self.prog["speed"]
                 * self.mod_mult.get("speed", 1.0))
        if "afterburner" in self.systems and self.idle_fire > 0.5:
            value *= 1.30                            # Nachbrenner
        return value

    # ------------------------------------------------------------- Anbauten
    def add_addon(self, key):
        """Einen Anbau montieren und sofort wirksam machen."""
        self.addons[key] = self.addons.get(key, 0) + 1
        if key == "plating":
            before = self.max_hp
            self.max_hp = self.compute_max_hp()
            self.hp += max(0, self.max_hp - before)   # Zuwachs sofort gutschreiben
        elif key == "escort":
            count = len(self.escorts)
            self.escorts.append({"angle": math.tau * count / 3 + 0.6,
                                 "timer": 0.3 * count})
        elif key == "aegis":
            self.refresh_aegis(refill=True)

    def refresh_aegis(self, refill=False):
        """Der Aegis-Ring haelt eine feste Menge Schaden und wird zu jedem
        Wellenstart neu aufgezogen."""
        self.aegis_max = AEGIS_PER_STACK * self.addons["aegis"]
        if refill:
            self.aegis = self.aegis_max
        else:
            self.aegis = min(self.aegis, self.aegis_max)

    def update_addons(self, dt, game):
        """Begleitdrohnen und Flakwerfer - unabhaengig von der Schiffsmechanik."""
        for escort in self.escorts:
            escort["angle"] += 2.1 * dt
            escort["timer"] -= dt
            if escort["timer"] > 0:
                continue
            target = self.nearest_target(game)
            if target is None:
                continue
            escort["timer"] = ESCORT_FIRE_RATE
            pos = self.escort_pos(escort)
            direction = safe_dir(pos, target)
            game.bullets.append(Bullet(
                pos, direction * 470, self.damage * 0.45,
                LIME, mix_color(LIME, WHITE, 0.5), 3, 10, homing=2.2))
            game.stats["shots"] += 1

        if self.addons["flak"] > 0:
            self.flak_timer -= dt
            if self.flak_timer <= 0:
                self.flak_timer = FLAK_INTERVAL / self.addons["flak"]
                self.fire_flak(game)

    def escort_pos(self, escort):
        r = self.radius + 46
        return self.pos + Vector2(math.cos(escort["angle"]),
                                  math.sin(escort["angle"]) * 0.5) * r

    def fire_flak(self, game):
        """Loescht alle gegnerischen Geschosse im Umkreis."""
        hits = 0
        for bullet in game.enemy_bullets:
            if not bullet.alive:
                continue
            if (bullet.pos - self.pos).length_squared() <= FLAK_RADIUS ** 2:
                hits += 1
                if bullet.blast > 0:
                    game.detonate_bomb(bullet, harmless=True)
                else:
                    bullet.alive = False
                    game.effects.spark(bullet.pos, (255, 150, 90), 4, 140, 0.22, 2)
        game.effects.ring(self.pos, (255, 150, 90), FLAK_RADIUS, 0.35)
        if hits:
            game.effects.spark(self.pos, (255, 190, 40), 8, 200, 0.3, 3)

    # --------------------------------------------------------------- Update
    def update(self, dt, keys, game):
        self.time += dt
        self.invuln = max(0.0, self.invuln - dt)
        self.hit_flash = max(0.0, self.hit_flash - dt)
        self.fire_timer = max(0.0, self.fire_timer - dt)
        self.reactive = max(0.0, self.reactive - dt)

        firing = keys[pygame.K_SPACE]
        if firing:
            self.heat = min(1.0, self.heat + dt / 2.2)   # volle Hitze nach 2,2 s
            self.idle_fire = 0.0
        else:
            self.heat = max(0.0, self.heat - dt / 1.1)
            self.idle_fire += dt
        if self.vel.length_squared() < 900:
            self.still_time += dt
        else:
            self.still_time = 0.0
        if "regen" in self.mod_flags and self.hp < self.max_hp:
            self.hp = min(self.max_hp, self.hp + self.max_hp * 0.012 * dt)

        move = Vector2(0, 0)
        if keys[pygame.K_LEFT]:
            move.x -= 1
        if keys[pygame.K_RIGHT]:
            move.x += 1
        if keys[pygame.K_UP]:
            move.y -= 1
        if keys[pygame.K_DOWN]:
            move.y += 1
        if move.length_squared() > 0:
            move = move.normalize()
            self.vel += move * self.ACCEL * self.ship["speed_mult"] * dt
            self.thrust = min(1.0, self.thrust + dt * 5)
        else:
            self.thrust = max(0.0, self.thrust - dt * 3)

        self.vel *= self.FRICTION ** (dt * 60)
        if self.vel.length() > self.speed_cap:
            self.vel.scale_to_length(self.speed_cap)
        self.pos += self.vel * dt

        # Spielfeldgrenzen mit weichem Abprall
        margin = self.radius + 6
        if self.pos.x < margin:
            self.pos.x, self.vel.x = margin, abs(self.vel.x) * 0.3
        elif self.pos.x > WIDTH - margin:
            self.pos.x, self.vel.x = WIDTH - margin, -abs(self.vel.x) * 0.3
        if self.pos.y < HUD_HEIGHT + margin:
            self.pos.y, self.vel.y = HUD_HEIGHT + margin, abs(self.vel.y) * 0.3
        elif self.pos.y > PLAY_BOTTOM - margin:
            self.pos.y, self.vel.y = PLAY_BOTTOM - margin, -abs(self.vel.y) * 0.3

        self.tilt = lerp(self.tilt, clamp(self.vel.x / max(self.speed_cap, 1), -1, 1), dt * 8)

        # Schildregeneration nach 3.5 s ohne Treffer
        if self.max_shield > 0 and not game.hardship("noregen"):
            self.shield_delay = max(0.0, self.shield_delay - dt)
            if self.shield_delay <= 0 and self.shield < self.max_shield:
                regen = stat_shield_regen(self.upgrades["shieldmatrix"])
                self.shield = min(self.max_shield, self.shield + regen * dt)

        # Triebwerkspartikel
        if self.thrust > 0.1 and random.random() < 0.85:
            col = self.ship["accent"]
            game.effects.add_particle(
                (self.pos.x + random.uniform(-5, 5), self.pos.y + 20),
                (self.vel.x * 0.15 + random.uniform(-25, 25), random.uniform(120, 240)),
                random.uniform(0.16, 0.34), col, random.uniform(2, 4), drag=0.9)

        self.update_mechanic(dt, keys, game)
        self.update_addons(dt, game)

        if self.mechanic == "charge":
            # Helios feuert nicht dauernd, sondern laedt und entlaedt
            if firing:
                self.charge = min(1.0, self.charge + dt / self.charge_time)
                if self.charge >= 1.0:
                    # Bei voller Ladung wird von selbst ausgeloest - sonst
                    # wuerde Dauerfeuer nie einen Schuss abgeben.
                    self.release_charge(game)
                    self.charge = 0.0
            elif self.charge > 0.08:
                self.release_charge(game)
                self.charge = 0.0
            else:
                self.charge = 0.0
        elif firing:
            self.shoot(game)

    # ------------------------------------------------------------- Mechanik
    def update_mechanic(self, dt, keys, game):
        if self.mechanic == "blink":
            self.blink_cd = max(0.0, self.blink_cd - dt)
            if self.blink_charges < self.blink_max and self.blink_cd <= 0:
                self.blink_charges += 1
                if self.blink_charges < self.blink_max:
                    self.blink_cd = self.blink_recharge
            pressed = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
            if pressed and not self.blink_held and self.blink_charges > 0:
                self.do_blink(game, keys)
            self.blink_held = pressed

        elif self.mechanic == "orbs":
            speed = 2.4
            for orb in self.orbs:
                orb["angle"] += speed * dt
                orb["ready"] = max(0.0, orb["ready"] - dt)
                if orb["ready"] > 0:
                    continue
                pos = self.orb_pos(orb)
                for bullet in game.enemy_bullets:
                    if not bullet.alive:
                        continue
                    if (bullet.pos - pos).length_squared() <= (bullet.radius + 13) ** 2:
                        if bullet.blast > 0:
                            game.detonate_bomb(bullet, harmless=True)
                        else:
                            bullet.alive = False
                        orb["ready"] = 2.4 * (0.5 if "fast_charge" in self.systems else 1.0)
                        game.effects.spark(pos, CRYSTAL, 10, 200, 0.3, 3)
                        if "riposte" in self.systems:
                            game.bullets.append(Bullet(
                                pos, Vector2(0, -680), self.damage * 0.6,
                                self.ship["laser"], self.ship["laser2"], 3, 12))
                        break

        elif self.mechanic == "drones":
            rate = 1.15 * (0.5 if "swarm_lead" in self.systems else 1.0)
            for drone in self.drones:
                drone["angle"] += 1.7 * dt
                drone["timer"] -= dt
                if drone["timer"] > 0:
                    continue
                target = self.nearest_target(game)
                if target is None:
                    continue
                drone["timer"] = rate
                pos = self.drone_pos(drone)
                direction = safe_dir(pos, target)
                game.bullets.append(Bullet(
                    pos, direction * 430, self.damage,
                    self.ship["laser"], self.ship["laser2"], 3, 12,
                    homing=3.4, splash=48.0 if "warheads" in self.systems else 0.0))
                game.stats["shots"] += 1

    def orb_pos(self, orb):
        r = self.radius + 34
        return self.pos + Vector2(math.cos(orb["angle"]), math.sin(orb["angle"])) * r

    def drone_pos(self, drone):
        r = self.radius + 30
        return self.pos + Vector2(math.cos(drone["angle"]),
                                  math.sin(drone["angle"]) * 0.55) * r

    def nearest_target(self, game):
        best, dist = None, 1e18
        for enemy in game.enemies:
            if not enemy.alive:
                continue
            d = (enemy.pos - self.pos).length_squared()
            if d < dist:
                best, dist = enemy.pos, d
        if game.boss is not None and not game.boss.dying:
            d = (game.boss.pos - self.pos).length_squared()
            if d < dist:
                best = game.boss.pos
        return best

    def do_blink(self, game, keys):
        """Kurzsprung mit Unverwundbarkeit - das Markenzeichen der Wraith."""
        direction = Vector2(0, 0)
        if keys[pygame.K_LEFT]:
            direction.x -= 1
        if keys[pygame.K_RIGHT]:
            direction.x += 1
        if keys[pygame.K_UP]:
            direction.y -= 1
        if keys[pygame.K_DOWN]:
            direction.y += 1
        if direction.length_squared() == 0:
            direction = Vector2(0, -1)
        direction = direction.normalize()

        start = Vector2(self.pos)
        self.pos += direction * 165
        self.pos.x = clamp(self.pos.x, self.radius + 6, WIDTH - self.radius - 6)
        self.pos.y = clamp(self.pos.y, HUD_HEIGHT + self.radius + 6,
                           PLAY_BOTTOM - self.radius - 6)
        self.blink_charges -= 1
        if self.blink_cd <= 0:
            self.blink_cd = self.blink_recharge
        self.invuln = max(self.invuln, 0.35)
        game.effects.waves.append(Shockwave(start, 60, 0.35, PURPLE, 2))
        game.effects.waves.append(Shockwave(self.pos, 60, 0.35, PURPLE, 2))

        if "phase_trail" in self.systems:
            steps = 9
            for i in range(1, steps):
                point = start + (self.pos - start) * (i / float(steps))
                game.effects.spark(point, PURPLE, 4, 90, 0.35, 3)
                for enemy in game.enemies:
                    if enemy.alive and (enemy.pos - point).length_squared() <= 34 ** 2:
                        enemy.damage(self.damage * 1.4, game)

    def release_charge(self, game):
        """Helios: aufgeladenen Strahl abfeuern."""
        ship = self.ship
        # Der Helios lag gemessen bei nur 51 % der Ausgangsleistung einer
        # Phoenix - fuer ein Schiff zu 140 Kristallen zu wenig. Der volle
        # Ladeschuss macht deshalb 7,5 statt 6,0 Salven auf einmal.
        power = 0.25 + 7.25 * self.charge
        dmg = self.damage * power
        pierce = 99 if "penetrator" in self.systems else 3
        width = int(ship["bullet_w"] * (1 + 1.6 * self.charge))
        height = int(ship["bullet_h"] * (1 + 1.4 * self.charge))
        game.bullets.append(Bullet(
            Vector2(self.pos.x, self.pos.y - 18), Vector2(0, -ship["bullet_speed"]),
            dmg, ship["laser"], ship["laser2"], width, height, pierce=pierce))
        game.stats["shots"] += 1
        game.shake(3 + 9 * self.charge)
        game.effects.spark(self.pos, ship["laser"], int(6 + 18 * self.charge),
                           220, 0.35, 4)
        if "solar_storm" in self.systems and self.charge > 0.95:
            game.effects.waves.append(Shockwave(self.pos, 260, 0.7, GOLD, 4))
            for enemy in list(game.enemies):
                if enemy.alive and (enemy.pos - self.pos).length_squared() <= 260 ** 2:
                    enemy.damage(dmg * 0.35, game)

    # ---------------------------------------------------------------- Waffen
    def shoot(self, game):
        if self.fire_timer > 0 or not self.alive:
            return
        self.fire_timer = self.fire_cooldown
        ship = self.ship
        level = self.upgrades["multishot"]
        dmg = self.damage * MULTISHOT_FALLOFF[level]
        speed = ship["bullet_speed"]

        # Offsets (x-Versatz, Winkel in Grad) je Multi-Shot-Stufe
        if level == 1:
            pattern = [(0, 0)]
        elif level == 2:
            pattern = [(-11, 0), (11, 0)]
        elif level == 3:
            pattern = [(-16, 0), (0, 0), (16, 0)]
        else:
            pattern = [(-20, -18), (-11, -8), (0, 0), (11, 8), (20, 18)]
        if "single" in self.mod_flags:                 # Praezisionslauf
            pattern = [(0, 0)]
            dmg = self.damage
        if "spread" in self.mod_flags:                 # Streuschuss
            pattern = pattern + [(-26, -24), (26, 24)]
        # Zusatzlaser: je Stufe eine weitere Bahn, abwechselnd aussen
        for i in range(self.addons["lance"]):
            side = -1 if i % 2 == 0 else 1
            pattern = pattern + [(side * (30 + 8 * (i // 2)), side * 4)]
        pierce = 1 if "pierce" in self.mod_flags else 0
        if "crit" in self.mod_flags and random.random() < 0.12:
            dmg *= 3.0

        # Zwillingskern: jede vierte Salve wird gespiegelt nachgefeuert
        self.salvo_index += 1
        volleys = [0.0]
        if "twin" in self.systems and self.salvo_index % 4 == 0:
            volleys = [-7.0, 7.0]
            game.effects.spark(self.pos, ship["laser"], 8, 160, 0.25, 3)

        for shift in volleys:
            for offset_x, angle_deg in pattern:
                angle = math.radians(angle_deg - 90)
                vel = Vector2(math.cos(angle), math.sin(angle)) * speed
                start = Vector2(self.pos.x + offset_x + shift, self.pos.y - 16)
                game.bullets.append(Bullet(start, vel, dmg, ship["laser"],
                                           ship["laser2"], ship["bullet_w"],
                                           ship["bullet_h"], pierce=pierce))
                game.effects.add_particle(start, (vel.x * 0.05, vel.y * 0.05), 0.12,
                                          ship["laser"], 3)
        game.stats["shots"] += len(pattern) * len(volleys)

        # Hydra: zusaetzliche Laeufe nach hinten und zur Seite
        if self.mechanic == "omni":
            extra = [(0, 90), (0, 180), (0, 0)]          # hinten, links, rechts
            if "side_load" in self.systems:
                extra += [(0, 172), (0, 8)]
            if "full_circle" in self.systems:
                extra += [(0, 45), (0, 135), (0, 225), (0, 315)]
            side_dmg = dmg * 0.75
            for _, deg in extra:
                ang = math.radians(deg)
                vel = Vector2(math.cos(ang), math.sin(ang)) * (speed * 0.85)
                homing = 2.6 if (deg == 90 and "rear_hunter" in self.systems) else 0.0
                game.bullets.append(Bullet(
                    Vector2(self.pos), vel, side_dmg, ship["laser"], ship["laser2"],
                    max(2, ship["bullet_w"] - 1), ship["bullet_h"] - 2,
                    homing=homing))
            game.stats["shots"] += len(extra)

        game.shake(1.6 + 0.4 * len(pattern))

    # --------------------------------------------------------------- Schaden
    def take_damage(self, amount, game, source=None, mutations=()):
        if self.invuln > 0 or not self.alive:
            return False
        if source is not None:
            game.last_killer = (source, tuple(mutations))
        if hasattr(game, "wave_stats"):
            game.wave_stats["damage_taken"] += amount
        amount *= self.mod_mult.get("taken", 1.0)
        if "anchor" in self.mod_flags and self.still_time >= 1.0:
            amount *= 0.5                            # Ankerfeld
        if "slowmo" in self.mod_flags:
            game.slowmo = max(game.slowmo, 1.1)
        self.shield_delay = 3.5
        self.hit_flash = 0.18
        if "reactive" in self.systems:
            if self.reactive > 0:
                amount *= 0.5                        # Reaktivpanzerung greift
            self.reactive = 1.5
        remaining = amount
        # Der Aegis-Ring liegt vor dem Schild und faengt zuerst
        if self.aegis > 0:
            absorbed = min(self.aegis, remaining)
            self.aegis -= absorbed
            remaining -= absorbed
            game.effects.spark(self.pos, CRYSTAL, 12, 230, 0.32, 3)
            game.effects.ring(self.pos, CRYSTAL, self.radius * 4, 0.3, 2)
            if self.aegis <= 0:
                game.effects.text(self.pos, "AEGIS ZERBROCHEN", CRYSTAL, 20)
        if self.shield > 0 and remaining > 0:
            absorbed = min(self.shield, remaining)
            self.shield -= absorbed
            remaining -= absorbed
            game.effects.spark(self.pos, CYAN, 10, 200, 0.3, 3)
            game.effects.waves.append(Shockwave(self.pos, self.radius * 3, 0.3, CYAN, 2))
        if remaining > 0:
            self.hp -= remaining
            game.effects.spark(self.pos, RED, 14, 240, 0.4, 3)
        self.invuln = 0.65
        game.shake(9)
        if self.hp <= 0:
            self.hp = 0
            self.alive = False
            game.effects.explosion(self.pos, ORANGE, size=2.4, count=70)
            game.effects.explosion(self.pos, self.ship["accent"], size=1.8, count=40)
            game.shake(26)
            return True
        return False

    def heal(self, amount):
        self.hp = min(self.max_hp, self.hp + amount)

    # ----------------------------------------------------------------- Draw
    def draw(self, surface):
        if not self.alive:
            return
        if self.invuln > 0 and int(self.invuln * 22) % 2 == 0:
            return
        x, y = self.pos.x, self.pos.y
        # Aegis-Ring - liegt als eigener Kreis AUSSERHALB der Schildkuppel
        if self.aegis > 0.5:
            ratio = self.aegis / max(1.0, self.aegis_max)
            r = int(self.radius * 2.0 + 20)
            col = mix_color((40, 90, 150), CRYSTAL, ratio)
            blit_glow(surface, col, (int(x), int(y)), int(r * 0.75))
            pygame.draw.circle(surface, col, (int(x), int(y)), r, 2)
            # Segmente zeigen die verbleibende Ladung an
            segments = max(1, int(round(self.aegis_max / AEGIS_PER_STACK)) * 6)
            filled = int(math.ceil(segments * ratio))
            for i in range(filled):
                ang = self.time * 1.3 + math.tau * i / segments
                px = int(x + math.cos(ang) * r)
                py = int(y + math.sin(ang) * r)
                pygame.draw.circle(surface, mix_color(col, WHITE, 0.6), (px, py), 3)

        # Schildkuppel
        if self.shield > 0.5:
            ratio = self.shield / max(1, self.max_shield)
            r = int(self.radius * 2.0 + 6)
            col = mix_color(DEEPBLUE, CYAN, ratio)
            blit_glow(surface, col, (int(x), int(y)), int(r * 0.9))
            pygame.draw.circle(surface, col, (int(x), int(y)), r, 2)
            arc_rect = pygame.Rect(x - r, y - r, r * 2, r * 2)
            pygame.draw.arc(surface, WHITE, arc_rect,
                            self.time * 2.0, self.time * 2.0 + 1.1, 2)
        self.ship["draw"](surface, x, y, 1.0, self.time, self.thrust)

        # ------------------------------------------- Mechanik sichtbar machen
        if self.mechanic == "orbs":
            for orb in self.orbs:
                pos = self.orb_pos(orb)
                charged = orb["ready"] <= 0
                col = CRYSTAL if charged else (70, 90, 120)
                blit_glow(surface, col, (int(pos.x), int(pos.y)), 14 if charged else 8)
                pygame.draw.circle(surface, col, (int(pos.x), int(pos.y)), 7)
                pygame.draw.circle(surface, WHITE if charged else (110, 130, 160),
                                   (int(pos.x), int(pos.y)), 7, 1)
        elif self.mechanic == "drones":
            for drone in self.drones:
                pos = self.drone_pos(drone)
                blit_glow(surface, YELLOW, (int(pos.x), int(pos.y)), 11)
                pts = rot_points([(0, -6), (5, 4), (-5, 4)],
                                 drone["angle"] * 2.0, pos.x, pos.y)
                pygame.draw.polygon(surface, (90, 72, 20), pts)
                neon_poly(surface, YELLOW, pts, 1, halo=0.0)
        elif self.mechanic == "charge" and self.charge > 0.02:
            r = int(10 + 26 * self.charge)
            col = mix_color(GOLD, WHITE, self.charge)
            blit_glow(surface, col, (int(x), int(y - 20)), r)
            pygame.draw.circle(surface, col, (int(x), int(y - 20)),
                               max(2, int(4 + 7 * self.charge)))
            if self.charge >= 1.0:
                pygame.draw.circle(surface, WHITE, (int(x), int(y - 20)),
                                   int(14 + 3 * math.sin(self.time * 22)), 2)
        elif self.mechanic == "blink":
            for i in range(self.blink_charges):
                px = int(x - 14 + i * 14)
                pygame.draw.circle(surface, PURPLE, (px, int(y + 30)), 4)
                pygame.draw.circle(surface, WHITE, (px, int(y + 30)), 4, 1)

        # ------------------------------------------------- Anbauten zeichnen
        for escort in self.escorts:
            pos = self.escort_pos(escort)
            ready = escort["timer"] <= 0.25
            col = LIME if ready else (70, 110, 70)
            blit_glow(surface, col, (int(pos.x), int(pos.y)), 12 if ready else 8)
            pts = rot_points([(0, -7), (6, 3), (0, 1), (-6, 3)],
                             escort["angle"] * 1.6, pos.x, pos.y)
            pygame.draw.polygon(surface, (24, 54, 28), pts)
            neon_poly(surface, col, pts, 1, halo=0.0)

        if self.addons["flak"] > 0:
            # Kurz vor dem Stoss zieht sich ein Ring zusammen
            due = clamp(1.0 - self.flak_timer / max(0.1, FLAK_INTERVAL), 0, 1)
            if due > 0.82:
                r = int(FLAK_RADIUS * (1.0 - (due - 0.82) / 0.18))
                pygame.draw.circle(surface, (255, 150, 90), (int(x), int(y)),
                                   max(6, r), 1)

        if self.hit_flash > 0:
            blit_glow(surface, RED, (int(x), int(y)), int(30 * (self.hit_flash / 0.18)))

# ==============================================================================
#  SKALIERUNG DER SCHWIERIGKEIT
# ==============================================================================
# Die Kurven sind bewusst so gewaehlt, dass Welle 1-4 als Aufwaermphase dient,
# Welle 5 (Boss) den ersten echten Check darstellt und Welle 6-10 quadratisch
# anzieht - parallel dazu waechst der Spielerschaden durch Upgrades linear.

def hp_scale(level):
    """Kampagne: quadratischer Anstieg bis Welle 10. Endlos: exponentiell
    weiter, damit es irgendwann wirklich eine Wand gibt."""
    w = min(level, CAMPAIGN_LEVELS)
    base = 1.0 + 0.30 * (w - 1) + 0.020 * (w - 1) ** 2
    if level > CAMPAIGN_LEVELS:
        base *= 1.13 ** (level - CAMPAIGN_LEVELS)
    return base


def speed_scale(level):
    # Tempo laeuft in eine Saettigung: unspielbar schnelle Gegner helfen niemandem.
    return 1.0 + 0.80 * (1.0 - math.exp(-0.075 * (level - 1)))


def shot_scale(level):
    return 1.0 + 0.70 * (1.0 - math.exp(-0.065 * (level - 1)))


def dmg_scale(level):
    return min(3.2, 1.0 + 0.060 * (level - 1))


def reward_scale(level):
    return 1.0 + 0.10 * (level - 1)


# ----------------------------------------------------- Machtindex des Spielers
def multishot_shots(level):
    """Anzahl Projektile pro Salve - deckungsgleich mit Player.shoot()."""
    return {1: 1, 2: 2, 3: 3, 4: 5}[level]


def player_dps(upgrades, ship, prog=None):
    lvl = upgrades["multishot"]
    per_salvo = (stat_damage(upgrades["damage"], ship, prog)
                 * MULTISHOT_FALLOFF[lvl] * multishot_shots(lvl))
    return per_salvo / stat_cooldown(upgrades["firerate"], ship, prog)


def player_ehp(upgrades, ship, prog=None):
    prog = prog or NO_PROG
    return (stat_maxhp(upgrades["maxhp"], ship, prog)
            + stat_shield(upgrades["shieldmatrix"], ship, prog))


def power_index(save, ship_key):
    """1.0 = Startausruestung der Phoenix. Beruecksichtigt Upgrades, Rang
    und Refit, damit die Gegner mit dem gesamten Fortschritt mitziehen.

    `power_mult` korrigiert, was die reinen Werte nicht abbilden: Drohnen,
    Seitenlaeufe oder ein Ladeschuss veraendern die tatsaechliche Kampfkraft
    erheblich. Ohne diese Korrektur bekaemen Traegerschiffe zu leichte
    Gegner und Ladeschiffe zu schwere."""
    ship = SHIPS[ship_key]
    prog = progression_mult(save, ship_key)
    upgrades = save["upgrades"]
    dps_ratio = (player_dps(upgrades, ship, prog) / BASE_DPS
                 * ship.get("power_mult", 1.0))
    ehp_ratio = player_ehp(upgrades, ship, prog) / BASE_EHP
    return clamp(0.74 * dps_ratio + 0.26 * ehp_ratio, 1.0, THREAT_CAP)


def threat_hp(power):
    return power ** THREAT_HP_EXP


def threat_count(power):
    return power ** THREAT_COUNT_EXP


def threat_aggro(power):
    return power ** THREAT_AGGRO_EXP


def threat_boss(power, level=1):
    """Boss-Trefferpunkte folgen der Spielerstaerke fast linear, damit der
    Kampf nie unter eine sinnvolle Dauer faellt - aber mit Ober- und
    Untergrenze, damit weder Anfaenger noch Vollausbau ins Absurde laufen."""
    factor = (power / THREAT_BOSS_PIVOT) ** THREAT_BOSS_EXP
    factor = clamp(factor, THREAT_BOSS_MIN, THREAT_BOSS_MAX)
    if level > CAMPAIGN_LEVELS:
        factor *= 1.045 ** (level - CAMPAIGN_LEVELS)
    return factor


def threat_ramp(level):
    """Die adaptive Skalierung faehrt erst ab der Wellenmitte hoch.

    Sonst wuerde ein gut ausgeruesteter Pilot schon in Welle 2 bestraft -
    gemeint ist aber, dass es SPAET anzieht, nicht frueh."""
    return clamp((level - 2) / 6.0, 0.0, 1.0)


def mutation_chance(level, power):
    """Wahrscheinlichkeit, dass ein Gegner mit Zusatzmodul spawnt."""
    from_wave = 0.022 * max(0, level - 3)
    from_power = THREAT_MUTATION * (power ** 0.42 - 1.0)
    return clamp(from_wave + from_power, 0.0, 0.42)


# ==============================================================================
#  GEGNER
# ==============================================================================

class Enemy:
    """Basisklasse aller regulaeren Gegner."""

    kind = "enemy"
    base_hp = 30
    base_speed = 110
    radius = 16
    score = 100
    coin_value = 3
    crystal_chance = 0.03
    contact_damage = 14
    armor = 0.0
    color = MAGENTA
    accent = WHITE

    def __init__(self, x, y, level, threat=1.0, mutations=()):
        self.level = level
        self.threat = threat                 # Zaehigkeitsfaktor aus dem Machtindex
        self.mutations = set(mutations)
        self.pos = Vector2(x, y)
        self.alive = True
        self.time = random.uniform(0, 10)
        self.phase = random.uniform(0, math.tau)
        self.hit_flash = 0.0
        self.shoot_timer = random.uniform(1.2, 3.0)
        self.spin = random.uniform(0, math.tau)
        self.explodes_on_contact = False

        # ----------------------------------------------- Werte aus Mutationen
        self.size_mult = 1.0
        self.loot_mult = 1.0
        self.fire_mult = 1.0
        self.speed_mult = 1.0
        self.bonus_armor = 0.0
        hp_mult = 1.0
        for key in self.mutations:
            cfg = MUTATIONS.get(key)
            if cfg:
                self.loot_mult *= cfg["loot"]
        if "elite" in self.mutations:
            hp_mult *= 2.2
            self.size_mult *= 1.28
            self.fire_mult *= 1.25
        if "armored" in self.mutations:
            self.bonus_armor += 0.25
            hp_mult *= 1.15
        if "rapid" in self.mutations:
            self.fire_mult *= 1.45
        if "swift" in self.mutations:
            self.speed_mult *= 1.38

        self.radius = self.radius * self.size_mult
        self.max_hp = self.base_hp * hp_scale(level) * threat * hp_mult
        self.hp = self.max_hp
        self.vel = Vector2(0, self.base_speed * speed_scale(level) * self.speed_mult)

        # Schild-Mutation: eigener Pool, der zuerst gebrochen werden muss
        self.max_shield = self.max_hp * 0.65 if "shield" in self.mutations else 0.0
        self.shield = self.max_shield
        self.shield_delay = 0.0
        self.link_shield = 0.0               # vom Schildgeber projiziert

    @property
    def total_armor(self):
        return clamp(self.armor + self.bonus_armor, 0.0, 0.8)

    # ---------------------------------------------------------------- Logik
    def update(self, dt, game):
        self.time += dt
        self.hit_flash = max(0.0, self.hit_flash - dt)
        self.spin += dt * 2.0
        self.link_shield = max(0.0, self.link_shield - dt)
        if self.max_shield > 0:
            self.shield_delay = max(0.0, self.shield_delay - dt)
            if self.shield_delay <= 0 and self.shield < self.max_shield:
                self.shield = min(self.max_shield, self.shield + self.max_shield * 0.12 * dt)
        self.move(dt, game)
        self.pos += self.vel * dt
        self.shoot_timer -= dt
        if self.shoot_timer <= 0:
            self.fire(game)
        if self.pos.y > HEIGHT + 80 or self.pos.x < -140 or self.pos.x > WIDTH + 140:
            self.alive = False

    def move(self, dt, game):
        pass

    def fire(self, game):
        self.shoot_timer = 999.0

    def enemy_shot(self, game, direction, speed, damage_mult=1.0, color=None,
                   radius=6, kind="orb", turn=0.0):
        # Bewusst OHNE game.aggro: schnellere Geschosse nehmen dem Spieler die
        # Reaktionszeit und machen eine Welle unfair statt schwer.
        speed *= shot_scale(self.level)
        dmg = 9.0 * dmg_scale(self.level) * damage_mult * game.enemy_dmg
        if "rapid" in self.mutations:
            radius = max(3, radius - 1)      # schneller, aber duennere Geschosse
        game.enemy_bullets.append(EnemyBullet(
            self.pos + direction * (self.radius * 0.8), direction * speed, dmg,
            color or self.accent, radius, kind, turn,
            source=self.kind, source_mut=tuple(self.mutations)))

    def set_cooldown(self, game, seconds):
        """Schusspause inklusive Schnellfeuer-Mutation und Wellen-Aggression."""
        self.shoot_timer = seconds / (self.fire_mult
                                      * game.aggro ** AGGRO_COOLDOWN_EXP)

    # -------------------------------------------------------------- Schaden
    def damage(self, amount, game):
        effective = amount * (1.0 - self.total_armor)
        if self.link_shield > 0:
            effective *= 0.45                # Schildgeber daempft eingehenden Schaden
        self.hit_flash = 0.09
        if self.shield > 0:
            absorbed = min(self.shield, effective)
            self.shield -= absorbed
            effective -= absorbed
            self.shield_delay = 3.0
            game.effects.spark(self.pos, MUTATIONS["shield"]["color"], 4, 130, 0.2, 2)
            if self.shield <= 0:
                game.effects.waves.append(Shockwave(
                    self.pos, self.radius * 2.4, 0.3, MUTATIONS["shield"]["color"], 2))
        if effective <= 0:
            return False
        self.hp -= effective
        if self.hp <= 0:
            self.alive = False
            self.on_death(game)
            return True
        return False

    def on_death(self, game):
        game.effects.explosion(self.pos, self.color, size=self.radius / 15.0,
                               count=int(14 + self.radius))
        game.shake(3 + self.radius * 0.18)
        game.on_enemy_killed(self)

    # ----------------------------------------------------------------- Draw
    def body_color(self):
        if self.hit_flash > 0:
            return mix_color(self.color, WHITE, 0.85)
        ratio = clamp(self.hp / max(1.0, self.max_hp), 0.0, 1.0)
        return mix_color(scale_color(self.color, 0.55), self.color, ratio)

    def draw(self, surface):
        pygame.draw.circle(surface, self.body_color(),
                           (int(self.pos.x), int(self.pos.y)), self.radius)

    def draw_mutations(self, surface):
        """Zeichnet die sichtbaren Folgen der Mutationen um den Gegner herum."""
        if not self.mutations and self.link_shield <= 0:
            return
        x, y = int(self.pos.x), int(self.pos.y)
        r = int(self.radius)
        if "elite" in self.mutations:
            col = MUTATIONS["elite"]["color"]
            blit_glow(surface, col, (x, y), int(r * 1.9))
            pts = rot_points([(math.cos(a) * (r + 9), math.sin(a) * (r + 9))
                              for a in [math.tau * i / 3 for i in range(3)]],
                             self.time * 1.6, x, y)
            for px, py in pts:
                pygame.draw.circle(surface, col, (int(px), int(py)), 3)
        if "armored" in self.mutations:
            col = MUTATIONS["armored"]["color"]
            for i in range(4):
                a = self.time * 0.6 + math.tau * i / 4
                rect = pygame.Rect(0, 0, 9, 5)
                rect.center = (x + math.cos(a) * (r + 5), y + math.sin(a) * (r + 5))
                pygame.draw.rect(surface, col, rect, 1)
        if "swift" in self.mutations:
            col = MUTATIONS["swift"]["color"]
            for i in (-1, 1):
                pygame.draw.line(surface, col,
                                 (x + i * r * 0.7, y - r - 4),
                                 (x + i * r * 0.7, y - r - 12), 2)
        if "rapid" in self.mutations:
            col = MUTATIONS["rapid"]["color"]
            pulse = 0.5 + 0.5 * math.sin(self.time * 12)
            pygame.draw.circle(surface, col, (x, int(y + r * 0.7)),
                               max(2, int(3 * pulse + 1)))
        if self.shield > 0:
            col = MUTATIONS["shield"]["color"]
            ratio = self.shield / max(1.0, self.max_shield)
            rr = int(r + 7)
            pygame.draw.circle(surface, scale_color(col, 0.35 + 0.5 * ratio),
                               (x, y), rr, 2)
            arc = pygame.Rect(x - rr, y - rr, rr * 2, rr * 2)
            pygame.draw.arc(surface, WHITE, arc, self.time * 2.4,
                            self.time * 2.4 + 1.0 + ratio, 2)
        if self.link_shield > 0:
            col = MUTATIONS["shield"]["color"]
            pygame.draw.circle(surface, scale_color(col, 0.5), (x, y), int(r + 4), 1)

    def draw_hp(self, surface):
        """Kleiner HP-Streifen, sobald der Gegner angeschlagen ist."""
        if self.max_shield > 0 and self.shield > 0:
            w = self.radius * 2
            x = int(self.pos.x - w / 2)
            y = int(self.pos.y - self.radius - 14)
            pygame.draw.rect(surface, (18, 30, 48), (x, y, w, 3))
            pygame.draw.rect(surface, MUTATIONS["shield"]["color"],
                             (x, y, int(w * self.shield / self.max_shield), 3))
        if self.hp >= self.max_hp - 0.01:
            return
        w = self.radius * 2
        x = int(self.pos.x - w / 2)
        y = int(self.pos.y - self.radius - 9)
        pygame.draw.rect(surface, (30, 30, 46), (x, y, w, 4))
        ratio = clamp(self.hp / max(1.0, self.max_hp), 0.0, 1.0)
        col = GREEN if ratio > 0.5 else (YELLOW if ratio > 0.25 else RED)
        pygame.draw.rect(surface, col, (x, y, int(w * ratio), 4))


class Interceptor(Enemy):
    """Schneller Abfangjaeger: Zickzack-Anflug, gelegentlich ein Schnellschuss."""

    kind = "interceptor"
    base_hp = 26
    base_speed = 132
    radius = 15
    score = 100
    coin_value = 3
    crystal_chance = 0.025
    contact_damage = 14
    color = MAGENTA
    accent = (255, 120, 220)

    def __init__(self, x, y, level, threat=1.0, mutations=()):
        super().__init__(x, y, level, threat, mutations)
        self.amplitude = random.uniform(90, 190)
        self.frequency = random.uniform(1.4, 2.4)
        self.shoot_timer = random.uniform(1.4, 3.4)

    def move(self, dt, game):
        self.vel.x = math.sin(self.time * self.frequency + self.phase) * self.amplitude
        if self.pos.x < 40:
            self.vel.x = abs(self.vel.x)
        elif self.pos.x > WIDTH - 40:
            self.vel.x = -abs(self.vel.x)

    def fire(self, game):
        self.set_cooldown(game, random.uniform(2.0, 3.6))
        if self.level < 2 or game.player is None or not game.player.alive:
            return
        if self.pos.y > HEIGHT - 120:
            return
        direction = safe_dir(self.pos, game.player.pos)
        self.enemy_shot(game, direction, 340, 0.85, self.accent, 5, "laser")
        if "rapid" in self.mutations:
            angle = math.atan2(direction.y, direction.x) + 0.13
            self.enemy_shot(game, Vector2(math.cos(angle), math.sin(angle)),
                            340, 0.85, self.accent, 5, "laser")

    def draw(self, surface):
        x, y = self.pos.x, self.pos.y
        col = self.body_color()
        tilt = clamp(self.vel.x / 220.0, -0.5, 0.5)
        hull = [(0, 17), (12, -6), (7, -14), (0, -8), (-7, -14), (-12, -6)]
        pts = rot_points(hull, tilt, x, y)
        blit_glow(surface, self.color, (int(x), int(y)), 20)
        pygame.draw.polygon(surface, scale_color(col, 0.35), pts)
        neon_poly(surface, col, pts, 2)
        pygame.draw.circle(surface, mix_color(col, WHITE, 0.7), (int(x), int(y - 2)), 3)
        blit_glow(surface, self.accent, (int(x), int(y - 13)), 8)


class Bomber(Enemy):
    """Gepanzerter Bomber: schwerfaellig, 28% Schadensreduktion, 3er-Salven."""

    kind = "bomber"
    base_hp = 95
    base_speed = 52
    radius = 26
    score = 260
    coin_value = 8
    crystal_chance = 0.09
    contact_damage = 22
    armor = 0.28
    color = ORANGE
    accent = YELLOW

    def __init__(self, x, y, level, threat=1.0, mutations=()):
        super().__init__(x, y, level, threat, mutations)
        self.hover_y = random.uniform(130, 260)
        self.drift = random.choice((-1, 1)) * random.uniform(35, 70)
        self.shoot_timer = random.uniform(1.6, 2.8)

    def move(self, dt, game):
        if self.pos.y < self.hover_y:
            self.vel.y = self.base_speed * speed_scale(self.level)
            self.vel.x = 0
        else:
            self.vel.y = 14 * math.sin(self.time * 1.2)
            self.vel.x = self.drift
            if self.pos.x < 60:
                self.drift = abs(self.drift)
            elif self.pos.x > WIDTH - 60:
                self.drift = -abs(self.drift)

    def fire(self, game):
        self.set_cooldown(game, max(1.1, 2.6 - 0.08 * self.level))
        if game.player is None or not game.player.alive or self.pos.y < 40:
            return
        base = safe_dir(self.pos, game.player.pos)
        base_angle = math.atan2(base.y, base.x)
        for offset in (-0.30, 0.0, 0.30):
            ang = base_angle + offset
            self.enemy_shot(game, Vector2(math.cos(ang), math.sin(ang)),
                            190, 1.15, ORANGE, 8, "orb")
        game.effects.spark(self.pos, ORANGE, 8, 120, 0.3, 3)

    def draw(self, surface):
        x, y = int(self.pos.x), int(self.pos.y)
        col = self.body_color()
        hull = [(0, 24), (20, 12), (26, -6), (14, -18), (-14, -18), (-26, -6), (-20, 12)]
        pts = rot_points(hull, 0, x, y)
        blit_glow(surface, self.color, (x, y), 30)
        pygame.draw.polygon(surface, scale_color(col, 0.32), pts)
        neon_poly(surface, col, pts, 3)
        # Panzerplatten
        for i in (-1, 1):
            plate = rot_points([(6 * i, -12), (18 * i, -4), (14 * i, 8), (5 * i, 4)], 0, x, y)
            pygame.draw.polygon(surface, scale_color(self.accent, 0.30), plate)
            pygame.draw.polygon(surface, self.accent, plate, 1)
        core_pulse = 0.6 + 0.4 * math.sin(self.time * 4)
        blit_glow(surface, YELLOW, (x, y + 2), int(16 * core_pulse))
        pygame.draw.circle(surface, mix_color(YELLOW, WHITE, core_pulse), (x, y + 2), 6)
        pygame.draw.circle(surface, WHITE, (x, y + 2), 6, 1)


class Drone(Enemy):
    """Kamikaze-Drohne: steuert den Spieler an und detoniert beim Aufprall."""

    kind = "drone"
    base_hp = 20
    base_speed = 92
    radius = 14
    score = 130
    coin_value = 4
    crystal_chance = 0.03
    contact_damage = 26
    color = (255, 90, 60)
    accent = YELLOW

    def __init__(self, x, y, level, threat=1.0, mutations=()):
        super().__init__(x, y, level, threat, mutations)
        self.explodes_on_contact = True
        self.lock_delay = random.uniform(0.3, 1.0)
        self.max_chase = (250 + 14 * level) * self.speed_mult
        self.armed = 0.0

    def move(self, dt, game):
        self.lock_delay -= dt
        if self.lock_delay > 0 or game.player is None or not game.player.alive:
            self.vel = Vector2(self.vel.x, max(self.vel.y, 90))
            return
        self.armed = min(1.0, self.armed + dt * 0.8)
        target = safe_dir(self.pos, game.player.pos)
        desired = target * self.max_chase
        self.vel += (desired - self.vel) * clamp(2.2 * dt, 0, 1)
        if self.vel.length() > self.max_chase:
            self.vel.scale_to_length(self.max_chase)
        if random.random() < 0.4:
            game.effects.add_particle(self.pos, -self.vel * 0.12, 0.25,
                                      self.color, 3, drag=0.9)

    def on_death(self, game):
        game.effects.explosion(self.pos, self.color, size=1.4, count=32)
        game.effects.explosion(self.pos, YELLOW, size=0.8, count=14, ring=False)
        game.shake(7)
        game.on_enemy_killed(self)

    def draw(self, surface):
        x, y = int(self.pos.x), int(self.pos.y)
        pulse = 0.55 + 0.45 * math.sin(self.time * (8 + 8 * self.armed))
        col = self.body_color() if self.hit_flash <= 0 else WHITE
        col = mix_color(col, WHITE, 0.35 * pulse)
        blit_glow(surface, self.color, (x, y), int(20 + 12 * pulse))
        body = rot_points([(0, -14), (10, 0), (0, 14), (-10, 0)], self.spin * 0.8, x, y)
        pygame.draw.polygon(surface, scale_color(col, 0.4), body)
        neon_poly(surface, col, body, 2)
        spikes = rot_points([(0, -19), (0, 19)], self.spin * 0.8, x, y)
        pygame.draw.line(surface, self.accent, spikes[0], spikes[1], 2)
        spikes2 = rot_points([(-19, 0), (19, 0)], self.spin * 0.8, x, y)
        pygame.draw.line(surface, self.accent, spikes2[0], spikes2[1], 2)
        pygame.draw.circle(surface, mix_color(YELLOW, RED, pulse), (x, y), 4)


class Sentinel(Enemy):
    """Schwebende Geschuetzplattform: haelt Distanz und feuert Kreis-Salven."""

    kind = "sentinel"
    base_hp = 62
    base_speed = 72
    radius = 20
    score = 190
    coin_value = 6
    crystal_chance = 0.07
    contact_damage = 18
    armor = 0.10
    color = PURPLE
    accent = (220, 170, 255)

    def __init__(self, x, y, level, threat=1.0, mutations=()):
        super().__init__(x, y, level, threat, mutations)
        self.hover_y = random.uniform(110, 230)
        self.orbit_r = random.uniform(60, 130)
        self.center_x = clamp(x, 120, WIDTH - 120)
        self.shoot_timer = random.uniform(1.8, 3.2)
        self.burst = 0
        self.burst_timer = 0.0

    def move(self, dt, game):
        if self.pos.y < self.hover_y:
            self.vel = Vector2(0, self.base_speed * speed_scale(self.level))
        else:
            self.vel = Vector2(math.cos(self.time * 0.9) * 60,
                               math.sin(self.time * 1.4) * 26)

    def update(self, dt, game):
        super().update(dt, game)
        if self.burst > 0:
            self.burst_timer -= dt
            if self.burst_timer <= 0:
                self.burst -= 1
                self.burst_timer = 0.16
                if game.player is not None and game.player.alive:
                    direction = safe_dir(self.pos, game.player.pos)
                    self.enemy_shot(game, direction, 280, 0.9, self.accent, 6, "orb")

    def fire(self, game):
        self.set_cooldown(game, max(1.7, 3.4 - 0.1 * self.level))
        if self.pos.y < 40:
            return
        if random.random() < 0.45 or self.level >= 7:
            count = 8 if self.level < 7 else 12
            for i in range(count):
                ang = math.tau * i / count + self.spin
                self.enemy_shot(game, Vector2(math.cos(ang), math.sin(ang)),
                                150, 0.8, PURPLE, 6, "orb")
            game.effects.waves.append(Shockwave(self.pos, 46, 0.35, PURPLE, 2))
        else:
            self.burst = 3
            self.burst_timer = 0.0

    def draw(self, surface):
        x, y = int(self.pos.x), int(self.pos.y)
        col = self.body_color()
        blit_glow(surface, self.color, (x, y), 28)
        ring = rot_points([(math.cos(a) * 20, math.sin(a) * 20)
                           for a in [math.tau * i / 6 for i in range(6)]],
                          self.spin, x, y)
        pygame.draw.polygon(surface, scale_color(col, 0.3), ring)
        neon_poly(surface, col, ring, 2)
        for i in range(3):
            ang = self.spin * -1.4 + math.tau * i / 3
            px = x + math.cos(ang) * 26
            py = y + math.sin(ang) * 26
            pygame.draw.circle(surface, self.accent, (int(px), int(py)), 4)
            pygame.draw.circle(surface, WHITE, (int(px), int(py)), 4, 1)
        pygame.draw.circle(surface, mix_color(col, WHITE, 0.5), (x, y), 8)
        pygame.draw.circle(surface, WHITE, (x, y), 8, 1)


class Sniper(Enemy):
    """Scharfschuetze: haelt Abstand, zielt sichtbar vor und feuert dann einen
    harten Praezisionsschuss. Die Ziellinie ist die Warnung - wer sie sieht,
    kann ausweichen."""

    kind = "sniper"
    base_hp = 48
    base_speed = 58
    radius = 17
    score = 240
    coin_value = 7
    crystal_chance = 0.08
    contact_damage = 16
    color = (120, 255, 220)
    accent = (200, 255, 245)

    CHARGE_TIME = 1.15

    def __init__(self, x, y, level, threat=1.0, mutations=()):
        super().__init__(x, y, level, threat, mutations)
        self.hover_y = random.uniform(90, 200)
        self.charge = 0.0
        self.aim = Vector2(0, 1)
        self.shoot_timer = random.uniform(1.5, 2.8)

    def move(self, dt, game):
        if self.pos.y < self.hover_y:
            self.vel = Vector2(0, self.base_speed * speed_scale(self.level))
        else:
            self.vel = Vector2(math.sin(self.time * 0.7 + self.phase) * 52, 0)

    def update(self, dt, game):
        super().update(dt, game)
        if self.charge > 0:
            self.charge -= dt
            player = game.player
            if player is not None and player.alive and self.charge > 0.35:
                # Bis kurz vor dem Schuss wird nachgefuehrt, danach ist das Ziel fix
                self.aim = safe_dir(self.pos, player.pos)
            if self.charge <= 0:
                self.enemy_shot(game, self.aim, 620, 1.8, self.color, 6, "laser")
                game.effects.spark(self.pos, self.color, 10, 220, 0.3, 3)
                game.shake(2)

    def fire(self, game):
        self.set_cooldown(game, max(1.9, 3.6 - 0.06 * self.level))
        if self.pos.y < self.hover_y - 10 or game.player is None:
            return
        if not game.player.alive:
            return
        self.charge = self.CHARGE_TIME
        self.aim = safe_dir(self.pos, game.player.pos)

    def draw(self, surface):
        x, y = int(self.pos.x), int(self.pos.y)
        col = self.body_color()
        if self.charge > 0:
            # Ziellinie als Vorwarnung, kurz vor dem Schuss hell und dick
            t = 1.0 - self.charge / self.CHARGE_TIME
            end = self.pos + self.aim * 900
            width = 1 if t < 0.75 else 2
            pygame.draw.line(surface, scale_color(self.color, 0.30 + 0.55 * t),
                             self.pos, end, width)
            blit_glow(surface, self.color, (x, y), int(10 + 16 * t))
        blit_glow(surface, self.color, (x, y), int(self.radius * 1.4))
        body = rot_points([(0, -self.radius), (self.radius * 0.85, 0),
                           (0, self.radius), (-self.radius * 0.85, 0)], 0, x, y)
        pygame.draw.polygon(surface, scale_color(col, 0.3), body)
        neon_poly(surface, col, body, 2)
        barrel_end = self.pos + self.aim * (self.radius + 8)
        pygame.draw.line(surface, self.accent, self.pos, barrel_end, 3)
        pygame.draw.circle(surface, WHITE, (x, y), max(2, int(self.radius * 0.28)))


class Shard(Enemy):
    """Bruchstueck eines Teilers - klein, schnell, nervig."""

    kind = "shard"
    base_hp = 12
    base_speed = 175
    radius = 9
    score = 45
    coin_value = 1
    crystal_chance = 0.01
    contact_damage = 12
    color = (255, 170, 90)
    accent = YELLOW

    def __init__(self, x, y, level, threat=1.0, mutations=()):
        super().__init__(x, y, level, threat, mutations)
        self.drift = random.uniform(-150, 150)
        self.shoot_timer = 999.0

    def move(self, dt, game):
        self.vel.x = self.drift + math.sin(self.time * 4 + self.phase) * 60
        self.vel.y = self.base_speed * speed_scale(self.level) * self.speed_mult

    def draw(self, surface):
        x, y = int(self.pos.x), int(self.pos.y)
        col = self.body_color()
        blit_glow(surface, self.color, (x, y), 12)
        pts = rot_points([(0, -9), (7, 4), (-7, 4)], self.spin * 1.6, x, y)
        pygame.draw.polygon(surface, scale_color(col, 0.4), pts)
        neon_poly(surface, col, pts, 2, halo=0.0)


class Splitter(Enemy):
    """Teiler: zerfaellt beim Tod in mehrere Bruchstuecke. Wer ihn spaet
    toetet, bekommt die Splitter direkt vor die Nase."""

    kind = "splitter"
    base_hp = 78
    base_speed = 64
    radius = 22
    score = 220
    coin_value = 6
    crystal_chance = 0.06
    contact_damage = 20
    armor = 0.08
    color = (255, 140, 60)
    accent = (255, 210, 120)

    def __init__(self, x, y, level, threat=1.0, mutations=()):
        super().__init__(x, y, level, threat, mutations)
        self.shard_count = 3 if "elite" in self.mutations else 2
        self.shoot_timer = random.uniform(2.4, 4.0)

    def move(self, dt, game):
        self.vel.x = math.sin(self.time * 0.9 + self.phase) * 70
        self.vel.y = self.base_speed * speed_scale(self.level) * self.speed_mult

    def fire(self, game):
        self.set_cooldown(game, max(1.8, 3.4 - 0.07 * self.level))
        if game.player is None or not game.player.alive or self.pos.y < 30:
            return
        direction = safe_dir(self.pos, game.player.pos)
        self.enemy_shot(game, direction, 210, 1.0, self.accent, 7, "orb")

    def on_death(self, game):
        for i in range(self.shard_count):
            angle = math.tau * i / self.shard_count + random.uniform(-0.3, 0.3)
            offset = Vector2(math.cos(angle), math.sin(angle)) * (self.radius * 0.6)
            shard = Shard(self.pos.x + offset.x, self.pos.y + offset.y,
                          self.level, self.threat)
            shard.drift = math.cos(angle) * 180
            game.enemies.append(shard)
        game.effects.explosion(self.pos, self.color, size=1.5, count=30)
        game.shake(6)
        game.on_enemy_killed(self)

    def draw(self, surface):
        x, y = int(self.pos.x), int(self.pos.y)
        col = self.body_color()
        r = self.radius
        blit_glow(surface, self.color, (x, y), int(r * 1.5))
        outer = rot_points([(math.cos(a) * r, math.sin(a) * r)
                            for a in [math.tau * i / 5 for i in range(5)]],
                           self.spin * 0.5, x, y)
        pygame.draw.polygon(surface, scale_color(col, 0.3), outer)
        neon_poly(surface, col, outer, 3)
        # Sollbruchstellen andeuten
        for i in range(self.shard_count):
            a = self.spin * 0.5 + math.tau * i / self.shard_count
            pygame.draw.line(surface, self.accent, (x, y),
                             (x + math.cos(a) * r, y + math.sin(a) * r), 2)
        pygame.draw.circle(surface, mix_color(col, WHITE, 0.6), (x, y),
                           max(3, int(r * 0.3)))



class Guardian(Enemy):
    """Schildgeber: schiesst kaum, projiziert aber einen Schutzschirm auf alle
    Gegner in der Naehe. Solange er lebt, halten die anderen deutlich mehr aus."""

    kind = "guardian"
    base_hp = 130
    base_speed = 46
    radius = 24
    score = 380
    coin_value = 11
    crystal_chance = 0.14
    contact_damage = 18
    armor = 0.12
    color = (90, 190, 255)
    accent = (200, 240, 255)

    LINK_RANGE = 210

    def __init__(self, x, y, level, threat=1.0, mutations=()):
        super().__init__(x, y, level, threat, mutations)
        self.hover_y = random.uniform(110, 210)
        self.links = []
        self.shoot_timer = random.uniform(2.5, 4.0)

    def move(self, dt, game):
        if self.pos.y < self.hover_y:
            self.vel = Vector2(0, self.base_speed * speed_scale(self.level))
        else:
            self.vel = Vector2(math.cos(self.time * 0.6 + self.phase) * 48,
                               math.sin(self.time * 0.9) * 18)

    def update(self, dt, game):
        super().update(dt, game)
        self.links = []
        rng_sq = self.LINK_RANGE ** 2
        for other in game.enemies:
            if other is self or not other.alive:
                continue
            if (other.pos - self.pos).length_squared() <= rng_sq:
                other.link_shield = 0.25
                self.links.append(other)
                if len(self.links) >= 6:
                    break

    def fire(self, game):
        self.set_cooldown(game, max(2.2, 4.2 - 0.08 * self.level))
        if game.player is None or not game.player.alive or self.pos.y < 30:
            return
        for i in range(6):
            ang = math.tau * i / 6 + self.spin
            self.enemy_shot(game, Vector2(math.cos(ang), math.sin(ang)),
                            140, 0.7, self.color, 6, "orb")

    def on_death(self, game):
        for other in self.links:
            other.link_shield = 0.0
        game.effects.explosion(self.pos, self.color, size=2.0, count=40)
        game.effects.waves.append(Shockwave(self.pos, self.LINK_RANGE, 0.6,
                                            self.color, 3))
        game.shake(9)
        game.on_enemy_killed(self)

    def draw(self, surface):
        x, y = int(self.pos.x), int(self.pos.y)
        col = self.body_color()
        r = self.radius
        # Energiestraenge zu den geschuetzten Gegnern
        for other in self.links:
            pulse = 0.4 + 0.3 * math.sin(self.time * 6 + other.phase)
            pygame.draw.line(surface, scale_color(self.color, pulse),
                             self.pos, other.pos, 2)
        blit_glow(surface, self.color, (x, y), int(r * 1.8))
        ring = rot_points([(math.cos(a) * r, math.sin(a) * r)
                           for a in [math.tau * i / 8 for i in range(8)]],
                          self.spin * 0.4, x, y)
        pygame.draw.polygon(surface, scale_color(col, 0.28), ring)
        neon_poly(surface, col, ring, 3)
        inner = rot_points([(math.cos(a) * r * 0.5, math.sin(a) * r * 0.5)
                            for a in [math.tau * i / 3 for i in range(3)]],
                           -self.spin * 1.1, x, y)
        neon_poly(surface, self.accent, inner, 2)
        pygame.draw.circle(surface, WHITE, (x, y), max(3, int(r * 0.22)))
        # Reichweitenring, damit die Schutzzone lesbar ist
        pygame.draw.circle(surface, scale_color(self.color, 0.22), (x, y),
                           int(self.LINK_RANGE), 1)


class Mortar(Enemy):
    """Moerserschiff: wirft langsame, grosse Minen mit sehr hohem Schaden.

    Der Ausgleich fuer den Schaden ist Zeit und Gegenwehr - die Mine fliegt
    langsam, wird lange vorher angekuendigt und laesst sich abschiessen.
    Wer die Mine ignoriert, verliert die halbe Huelle; wer reagiert, nichts.
    """

    kind = "mortar"
    base_hp = 130
    base_speed = 40
    radius = 30
    score = 420
    coin_value = 13
    crystal_chance = 0.13
    contact_damage = 24
    armor = 0.18
    color = (255, 130, 60)
    accent = (255, 220, 120)

    BOMB_SPEED = 108.0
    BOMB_DAMAGE = 3.1         # Vielfaches des normalen Geschossschadens
    BOMB_BLAST = 96.0         # Sprengradius beim Zuenden
    AIM_TIME = 1.30           # sichtbares Zielen, bevor die Mine faellt

    def __init__(self, x, y, level, threat=1.0, mutations=()):
        super().__init__(x, y, level, threat, mutations)
        self.hover_y = random.uniform(96, 190)
        self.drift = random.choice((-1, 1)) * random.uniform(26, 46)
        self.shoot_timer = random.uniform(2.2, 3.6)
        self.aiming = 0.0
        self.aim_at = Vector2(WIDTH / 2, HEIGHT - 120)

    def move(self, dt, game):
        if self.pos.y < self.hover_y:
            self.vel = Vector2(0, self.base_speed * speed_scale(self.level))
            return
        self.vel = Vector2(self.drift, 10 * math.sin(self.time * 0.9))
        if self.pos.x < 70:
            self.drift = abs(self.drift)
        elif self.pos.x > WIDTH - 70:
            self.drift = -abs(self.drift)

    def update(self, dt, game):
        super().update(dt, game)
        if self.aiming > 0:
            self.aiming = max(0.0, self.aiming - dt)
            if game.player is not None and game.player.alive:
                # Das Ziel wandert dem Spieler langsam nach - ausweichen wirkt
                self.aim_at += (game.player.pos - self.aim_at) * clamp(1.6 * dt, 0, 1)
            if self.aiming <= 0:
                self.launch_bomb(game)

    def fire(self, game):
        self.set_cooldown(game, max(2.6, 5.4 - 0.10 * self.level))
        if game.player is None or not game.player.alive or self.pos.y < 40:
            return
        self.aiming = self.AIM_TIME
        self.aim_at = Vector2(game.player.pos)

    def launch_bomb(self, game):
        direction = safe_dir(self.pos, self.aim_at)
        dmg = (9.0 * dmg_scale(self.level) * self.BOMB_DAMAGE * game.enemy_dmg)
        bomb = EnemyBullet(
            self.pos + direction * (self.radius * 0.8),
            direction * self.BOMB_SPEED * shot_scale(self.level),
            dmg, self.color, 16, "bomb", life=11.0,
            source=self.kind, source_mut=tuple(self.mutations),
            hp=18.0 * hp_scale(self.level) ** 0.5, blast=self.BOMB_BLAST)
        game.enemy_bullets.append(bomb)
        game.effects.spark(self.pos, self.accent, 12, 150, 0.35, 3)
        game.effects.ring(self.pos, self.color, 46, 0.3, 2)

    def draw(self, surface):
        x, y = int(self.pos.x), int(self.pos.y)
        col = self.body_color()
        blit_glow(surface, self.color, (x, y), 36)
        hull = [(0, 26), (24, 14), (30, -8), (16, -22), (-16, -22), (-30, -8), (-24, 14)]
        pts = rot_points(hull, 0, x, y)
        pygame.draw.polygon(surface, scale_color(col, 0.30), pts)
        neon_poly(surface, col, pts, 3)
        # Wurfrohr: richtet sich beim Zielen auf den Spieler aus
        aim = safe_dir(self.pos, self.aim_at)
        muzzle = (x + aim.x * 34, y + aim.y * 34)
        pygame.draw.line(surface, self.accent, (x, y), muzzle, 6)
        pygame.draw.line(surface, WHITE, (x, y), muzzle, 2)
        if self.aiming > 0:
            # Zielmarke - der Spieler soll sehen, wohin die Mine faellt
            t = 1.0 - self.aiming / self.AIM_TIME
            tx, ty = int(self.aim_at.x), int(self.aim_at.y)
            r = int(lerp(self.BOMB_BLAST, 26, t))
            pygame.draw.circle(surface, self.color, (tx, ty), max(6, r), 2)
            pygame.draw.line(surface, self.accent, (tx - 14, ty), (tx + 14, ty), 1)
            pygame.draw.line(surface, self.accent, (tx, ty - 14), (tx, ty + 14), 1)
            pygame.draw.line(surface, scale_color(self.color, 0.5),
                             (x, y), (tx, ty), 1)
        core = 0.55 + 0.45 * math.sin(self.time * 3.4)
        pygame.draw.circle(surface, mix_color(self.accent, WHITE, core), (x, y - 4), 7)
        pygame.draw.circle(surface, WHITE, (x, y - 4), 7, 1)


ENEMY_CLASSES = {
    "interceptor": Interceptor,
    "bomber": Bomber,
    "drone": Drone,
    "sentinel": Sentinel,
    "sniper": Sniper,
    "splitter": Splitter,
    "guardian": Guardian,
    "shard": Shard,
    "mortar": Mortar,
}


# ==============================================================================
#  BOSSE
# ==============================================================================

class GeneratorNode(Enemy):
    """Schildgenerator des Bosses. Solange einer lebt, ist der Boss immun -
    der Bollwerk-Modus wird dadurch zur Aufgabe statt zur Wartezeit."""

    kind = "generator"
    base_hp = 1.0                       # wird vom Boss gesetzt
    base_speed = 0.0
    radius = 19
    score = 400
    coin_value = 9
    crystal_chance = 0.10
    contact_damage = 16
    color = (120, 220, 255)
    accent = WHITE

    def __init__(self, boss, angle, hp, level, threat=1.0):
        super().__init__(boss.pos.x, boss.pos.y, level, threat)
        self.boss = boss
        self.angle = angle
        self.orbit = boss.radius + 82
        self.max_hp = hp
        self.hp = hp
        self.max_shield = 0.0
        self.shield = 0.0
        self.spin_speed = 0.85
        self.shoot_timer = random.uniform(1.4, 2.6)

    def update(self, dt, game):
        self.time += dt
        self.hit_flash = max(0.0, self.hit_flash - dt)
        self.spin += dt * 3.0
        self.angle += self.spin_speed * dt
        if self.boss is None or not self.boss.alive:
            self.alive = False
            return
        target = self.boss.pos + Vector2(math.cos(self.angle),
                                         math.sin(self.angle)) * self.orbit
        self.pos += (target - self.pos) * clamp(9.0 * dt, 0, 1)
        self.shoot_timer -= dt
        if self.shoot_timer <= 0:
            self.fire(game)

    def fire(self, game):
        self.set_cooldown(game, random.uniform(1.8, 3.0))
        if game.player is None or not game.player.alive:
            return
        direction = safe_dir(self.pos, game.player.pos)
        self.enemy_shot(game, direction, 260, 0.8, self.color, 6, "orb")

    def on_death(self, game):
        game.effects.explosion(self.pos, self.color, size=1.6, count=34)
        game.effects.waves.append(Shockwave(self.pos, 70, 0.45, self.color, 3))
        game.shake(9)
        if self.boss is not None:
            self.boss.generator_destroyed(game)
        game.on_enemy_killed(self)

    def draw(self, surface):
        x, y = int(self.pos.x), int(self.pos.y)
        col = self.body_color()
        blit_glow(surface, self.color, (x, y), int(self.radius * 2.0))
        ring = rot_points([(math.cos(a) * self.radius, math.sin(a) * self.radius)
                           for a in [math.tau * i / 3 for i in range(3)]],
                          self.spin, x, y)
        pygame.draw.polygon(surface, scale_color(col, 0.35), ring)
        neon_poly(surface, col, ring, 3)
        pygame.draw.circle(surface, WHITE, (x, y), 5)
        pygame.draw.circle(surface, col, (x, y), int(self.radius * 0.72), 1)


class Boss:
    """Riesiger Endgegner mit Phasen, eigener Lebensleiste und mehreren
    Schussmustern (Kreis-Salven, Zielsuch-Laser, Spiralen, Sweep-Beam).

    Ab bestimmten Lebensanteilen faehrt er den Bollwerk-Modus hoch: er wird
    immun, ruft Schildgeneratoren und eine Begleitwelle. Erst wenn alle
    Generatoren zerstoert sind, ist er wieder verwundbar - und danach jedes
    Mal aggressiver."""

    #: Bei diesen Lebensanteilen faehrt der Boss den Bollwerk-Modus hoch.
    BULWARK_AT = {1: (0.75, 0.40), 2: (0.75, 0.50, 0.25)}
    BULWARK_TIMEOUT = 10.5

    def __init__(self, level, variant, power=1.0, tier=0, extra_bulwark=0):
        self.level = level
        self.variant = variant
        self.tier = tier                     # 0 = erster Auftritt, dann staerker
        self.power = power
        self.kind = "boss"
        self.alive = True

        if variant == 1:
            self.name = "OMEGA WARDEN"
            base_hp = 3400.0
            self.radius = 76
            self.color = MAGENTA
            self.accent = PURPLE
            self.phases = [
                ["ring", "aimed", "homing"],
                ["spiral", "ring", "aimed", "homing"],
                ["spiral", "ring", "homing", "minions", "aimed"],
            ]
            self.phase_hp = [0.66, 0.33, 0.0]
            self.contact_damage = 34
            self.score = 6000
            self.coin_value = 160
            self.crystals = 5
        else:
            self.name = "NOVA TYRANT"
            base_hp = 5200.0
            self.radius = 92
            self.color = RED
            self.accent = ORANGE
            self.phases = [
                ["ring", "aimed", "homing", "minions"],
                ["spiral", "beam", "ring", "homing"],
                ["beam", "spiral", "ring", "aimed", "homing", "minions"],
            ]
            self.phase_hp = [0.66, 0.33, 0.0]
            self.contact_damage = 45
            self.score = 15000
            self.coin_value = 320
            self.crystals = 9

        if tier > 0:
            self.name = "%s MK %d" % (self.name, tier + 1)
            self.score = int(self.score * (1 + 0.5 * tier))
            self.coin_value = int(self.coin_value * (1 + 0.35 * tier))
            self.crystals += tier

        # Trefferpunkte richten sich nach der Staerke des Spielers, damit der
        # Kampf weder eine Formsache noch eine Ewigkeit wird.
        self.max_hp = base_hp * threat_boss(power, level)
        self.hp = self.max_hp

        # ------------------------------------------------------ Bollwerk-Modus
        self.bulwark_left = list(self.BULWARK_AT[variant])
        for _ in range(max(0, extra_bulwark)):
            self.bulwark_left.append(0.15)       # Nova-Grad 3: Bollwerk kurz vor Schluss
        self.bulwark_left.sort(reverse=True)
        self.invulnerable = False
        self.bulwark_timer = 0.0
        self.generators = []
        self.rage = 0.0                      # steigt mit jedem Bollwerk
        self.pos = Vector2(WIDTH / 2, -self.radius - 60)
        self.target_y = 150.0
        self.entering = True
        self.time = 0.0
        self.hit_flash = 0.0
        self.phase = 0
        self.pattern_i = 0
        self.attack_t = 2.2
        self.burst_left = 0
        self.burst_timer = 0.0
        self.burst_interval = 0.3
        self.speed_boost = 1.0
        self.burst_kind = None
        self.burst_angle = 0.0
        self.drift_dir = 1
        self.beam_charge = 0.0
        self.beam_time = 0.0
        self.beam_angle = 0.0
        self.beam_damage_t = 0.0
        self.death_timer = 0.0
        self.dying = False

    # ---------------------------------------------------------------- Phasen
    def current_phase(self):
        ratio = self.hp / self.max_hp
        idx = 0
        for i, threshold in enumerate(self.phase_hp):
            if ratio > threshold:
                idx = i
                break
            idx = i
        return idx

    def update(self, dt, game):
        self.time += dt
        self.hit_flash = max(0.0, self.hit_flash - dt)

        if self.dying:
            self.death_timer -= dt
            if random.random() < 0.6:
                offset = Vector2(random.uniform(-1, 1), random.uniform(-1, 1)) * self.radius
                game.effects.explosion(self.pos + offset,
                                       random.choice([self.color, ORANGE, YELLOW]),
                                       size=1.1, count=16)
                game.shake(6)
            if self.death_timer <= 0:
                self.alive = False
                self.finish_death(game)
            return

        # ------------------------------------------------------------ Anflug
        if self.entering:
            self.pos.y += 90 * dt
            if self.pos.y >= self.target_y:
                self.pos.y = self.target_y
                self.entering = False
            return

        # ------------------------------------------------------ Bollwerk-Modus
        ratio = self.hp / self.max_hp
        if (not self.invulnerable and self.bulwark_left
                and ratio <= self.bulwark_left[0]):
            self.start_bulwark(game)
        if self.invulnerable:
            self.bulwark_timer -= dt
            self.generators = [g for g in self.generators if g.alive]
            if not self.generators or self.bulwark_timer <= 0:
                self.end_bulwark(game)

        new_phase = self.current_phase()
        if new_phase != self.phase:
            self.phase = new_phase
            self.pattern_i = 0
            self.attack_t = 1.1
            self.burst_left = 0
            self.beam_charge = 0.0
            self.beam_time = 0.0
            game.effects.explosion(self.pos, WHITE, size=2.2, count=40)
            game.effects.text(self.pos + Vector2(0, -self.radius - 30),
                              "PHASE %d" % (self.phase + 1), WHITE, 34)
            game.shake(16)

        # ---------------------------------------------------------- Bewegung
        speed = 62 + 26 * self.phase
        self.pos.x += self.drift_dir * speed * dt
        if self.pos.x < self.radius + 30:
            self.pos.x = self.radius + 30
            self.drift_dir = 1
        elif self.pos.x > WIDTH - self.radius - 30:
            self.pos.x = WIDTH - self.radius - 30
            self.drift_dir = -1
        self.pos.y = self.target_y + math.sin(self.time * 0.9) * 22

        # -------------------------------------------------------- Sweep-Beam
        if self.beam_charge > 0:
            self.beam_charge -= dt
            if self.beam_charge <= 0:
                self.beam_time = 2.6
                self.beam_angle = math.radians(48)
            game.effects.spark(self.pos + Vector2(0, self.radius * 0.5), RED, 3, 200, 0.25, 3)
        elif self.beam_time > 0:
            self.beam_time -= dt
            self.beam_angle -= math.radians(96) * dt / 1.0 * 0.36
            self.beam_damage_t -= dt
            self.apply_beam(game, dt)
            if self.beam_time <= 0:
                self.beam_time = 0.0

        # -------------------------------------------------------- Angriffe
        if self.burst_left > 0:
            self.burst_timer -= dt
            if self.burst_timer <= 0:
                self.fire_salvo(game)
                self.burst_left -= 1
                self.burst_timer = self.burst_interval
        elif self.beam_time <= 0 and self.beam_charge <= 0:
            self.attack_t -= dt
            if self.attack_t <= 0:
                self.start_pattern(game)

    # ------------------------------------------------------------- Bollwerk
    def start_bulwark(self, game):
        """Boss wird immun und ruft Schildgeneratoren plus Begleitschutz."""
        self.bulwark_left.pop(0)
        self.invulnerable = True
        self.bulwark_timer = self.BULWARK_TIMEOUT
        self.burst_left = 0
        self.beam_charge = 0.0
        self.beam_time = 0.0
        self.attack_t = 1.0

        count = 3 + self.tier + (1 if self.variant == 2 else 0)
        gen_hp = self.max_hp * 0.018
        self.generators = []
        for i in range(count):
            angle = math.tau * i / count
            node = GeneratorNode(self, angle, gen_hp, self.level, 1.0)
            self.generators.append(node)
            game.enemies.append(node)
            game.effects.explosion(node.pos, node.color, size=0.9, count=14)

        # Begleitwelle: gibt dem Spieler zusaetzlich etwas zu tun
        escorts = 2 + self.tier + self.rage
        for i in range(int(escorts)):
            x = clamp(self.pos.x + (i - escorts / 2) * 110, 60, WIDTH - 60)
            kind = Drone if i % 2 == 0 else Interceptor
            game.enemies.append(kind(x, -40, self.level, game.threat))

        game.effects.text(self.pos + Vector2(0, -self.radius - 40),
                          "BOLLWERK AKTIV", self.color, 40)
        game.effects.waves.append(Shockwave(self.pos, self.radius * 4, 0.8,
                                            self.color, 4))
        game.shake(18)
        game.banner("BOLLWERK", "Zerstoere die %d Schildgeneratoren" % count)

    def end_bulwark(self, game):
        """Immunitaet faellt, der Boss wird dauerhaft aggressiver."""
        self.invulnerable = False
        self.rage += 1
        for node in self.generators:
            if node.alive:
                node.alive = False
                node.boss = None
                game.effects.explosion(node.pos, node.color, size=1.2, count=20)
        self.generators = []
        game.effects.explosion(self.pos, WHITE, size=2.6, count=50)
        game.effects.text(self.pos + Vector2(0, -self.radius - 40),
                          "SCHILD GEBROCHEN", YELLOW, 40)
        game.shake(20)
        game.banner("SCHILD GEBROCHEN", "Der Boss ist wuetend - Stufe %d" % self.rage)

    def generator_destroyed(self, game):
        remaining = len([g for g in self.generators if g.alive]) - 1
        if remaining > 0:
            game.effects.text(self.pos + Vector2(0, -self.radius - 20),
                              "NOCH %d" % remaining, self.color, 30)

    # --------------------------------------------------------- Schussmuster
    def start_pattern(self, game):
        patterns = self.phases[self.phase]
        name = patterns[self.pattern_i % len(patterns)]
        self.pattern_i += 1
        speed_boost = 1.0 + 0.10 * self.phase + 0.09 * self.rage
        rush = 1.0 / (1.0 + 0.16 * self.rage + 0.10 * self.tier)
        self.burst_kind = name
        self.burst_angle = random.uniform(0, math.tau)

        if name == "ring":
            self.burst_left = 3 + self.phase
            self.burst_interval = 0.42
            self.attack_t = 1.5 * rush
        elif name == "aimed":
            self.burst_left = 4 + self.phase
            self.burst_interval = 0.20
            self.attack_t = 1.4 * rush
        elif name == "homing":
            self.burst_left = 2 + self.phase
            self.burst_interval = 0.55
            self.attack_t = 1.9 * rush
        elif name == "spiral":
            self.burst_left = 26 + 10 * self.phase
            self.burst_interval = 0.06
            self.attack_t = 1.6 * rush
        elif name == "minions":
            self.burst_left = 1
            self.burst_interval = 0.3
            self.attack_t = 2.6 * rush
        elif name == "beam":
            self.burst_left = 0
            self.beam_charge = 1.25
            self.attack_t = 2.0 * rush
            game.effects.text(self.pos + Vector2(0, -self.radius - 34),
                              "!! STRAHL !!", RED, 30)
        self.speed_boost = speed_boost

    def boss_shot(self, game, direction, speed, damage, color, radius=8,
                  kind="orb", turn=0.0):
        origin = self.pos + direction * (self.radius * 0.55)
        game.enemy_bullets.append(EnemyBullet(origin, direction * speed, damage,
                                              color, radius, kind, turn,
                                              source="boss"))

    def fire_salvo(self, game):
        name = self.burst_kind
        boost = getattr(self, "speed_boost", 1.0)
        dmg_base = 11.0 * dmg_scale(self.level) * game.enemy_dmg
        player = game.player

        if name == "ring":
            count = 16 + 4 * self.phase + (4 if self.variant == 2 else 0)
            offset = self.burst_angle + self.burst_left * 0.16
            for i in range(count):
                ang = math.tau * i / count + offset
                self.boss_shot(game, Vector2(math.cos(ang), math.sin(ang)),
                               168 * boost, dmg_base, self.color, 8)
            game.effects.waves.append(Shockwave(self.pos, self.radius + 40, 0.4,
                                                self.color, 3))
            game.shake(4)
        elif name == "aimed":
            if player is None or not player.alive:
                return
            base = safe_dir(self.pos, player.pos)
            base_ang = math.atan2(base.y, base.x)
            spread = 5 if self.variant == 2 else 3
            for i in range(spread):
                ang = base_ang + (i - (spread - 1) / 2) * 0.17
                self.boss_shot(game, Vector2(math.cos(ang), math.sin(ang)),
                               400 * boost, dmg_base * 0.9, self.accent, 6, "laser")
        elif name == "homing":
            if player is None or not player.alive:
                return
            count = 3 + self.phase
            for i in range(count):
                ang = math.pi / 2 + (i - (count - 1) / 2) * 0.5
                self.boss_shot(game, Vector2(math.cos(ang), math.sin(ang)),
                               210 * boost, dmg_base * 1.15, CYAN, 8, "homing",
                               turn=1.5 + 0.25 * self.phase)
            game.effects.text(self.pos + Vector2(0, self.radius * 0.6),
                              "ZIELSUCHE", CYAN, 22)
        elif name == "spiral":
            arms = 2 if self.variant == 1 else 3
            base = self.burst_angle + self.time * 3.4
            for a in range(arms):
                ang = base + math.tau * a / arms
                self.boss_shot(game, Vector2(math.cos(ang), math.sin(ang)),
                               230 * boost, dmg_base * 0.8, self.accent, 6)
            self.burst_angle += 0.34
        elif name == "minions":
            for i in range(3):
                x = self.pos.x + (i - 1) * 90
                enemy = Interceptor(clamp(x, 60, WIDTH - 60), self.pos.y, self.level)
                game.enemies.append(enemy)
                game.effects.explosion(enemy.pos, MAGENTA, size=0.8, count=12)

    # ------------------------------------------------------------ Sweep-Beam
    def beam_origin(self):
        return Vector2(self.pos.x, self.pos.y + self.radius * 0.4)

    def beam_dir(self):
        return Vector2(math.cos(self.beam_angle + math.pi / 2),
                       math.sin(self.beam_angle + math.pi / 2))

    def apply_beam(self, game, dt):
        player = game.player
        if player is None or not player.alive:
            return
        origin = self.beam_origin()
        direction = self.beam_dir()
        to_player = player.pos - origin
        along = to_player.dot(direction)
        if along < 0:
            return
        perp = (to_player - direction * along).length()
        if perp < 22 + player.radius:
            if self.beam_damage_t <= 0:
                self.beam_damage_t = 0.28
                player.take_damage(16.0 * dmg_scale(self.level) * game.enemy_dmg,
                                   game, "boss-strahl")

    # -------------------------------------------------------------- Schaden
    def damage(self, amount, game):
        if self.dying or self.entering:
            return False
        if self.invulnerable:
            # Treffer prallen sichtbar ab, damit klar ist warum nichts passiert
            self.hit_flash = 0.05
            if random.random() < 0.10:
                game.effects.text(self.pos + Vector2(random.uniform(-40, 40),
                                                     -self.radius * 0.5),
                                  "IMMUN", self.color, 24)
            return False
        self.hp -= amount
        self.hit_flash = 0.07
        if self.hp <= 0:
            self.hp = 0
            self.dying = True
            self.death_timer = 1.8
            game.shake(24)
            return True
        return False

    def finish_death(self, game):
        for node in self.generators:
            if node.alive:
                node.alive = False
                node.boss = None
        self.generators = []
        game.effects.explosion(self.pos, WHITE, size=3.4, count=90)
        game.effects.explosion(self.pos, self.color, size=2.6, count=60)
        game.shake(34)
        game.on_boss_killed(self)

    # ----------------------------------------------------------------- Draw
    def draw(self, surface):
        x, y = self.pos.x, self.pos.y
        col = mix_color(self.color, WHITE, 0.8) if self.hit_flash > 0 else self.color
        r = self.radius
        pulse = 0.6 + 0.4 * math.sin(self.time * 3)

        # Strahl zuerst, damit der Rumpf darueberliegt
        if self.beam_charge > 0:
            blit_glow(surface, RED, self.beam_origin(),
                      int(40 * (1.3 - self.beam_charge)))
        if self.beam_time > 0:
            origin = self.beam_origin()
            direction = self.beam_dir()
            end = origin + direction * 1400
            width = int(20 + 8 * math.sin(self.time * 30))
            pygame.draw.line(surface, scale_color(RED, 0.5), origin, end, width + 14)
            pygame.draw.line(surface, RED, origin, end, width)
            pygame.draw.line(surface, WHITE, origin, end, max(2, width // 3))
            blit_glow(surface, RED, origin, 60)

        blit_glow(surface, self.color, (int(x), int(y)), int(r * 1.5))

        if self.invulnerable:
            # Straenge zu den Generatoren zeigen, woher die Immunitaet kommt
            for node in self.generators:
                if not node.alive:
                    continue
                pulse = 0.45 + 0.35 * math.sin(self.time * 8 + node.angle)
                pygame.draw.line(surface, scale_color(node.color, pulse),
                                 self.pos, node.pos, 3)
            dome = int(r * 1.35)
            wobble = 0.85 + 0.15 * math.sin(self.time * 5)
            pygame.draw.circle(surface, scale_color(self.color, 0.55 * wobble),
                               (int(x), int(y)), dome, 3)
            pygame.draw.circle(surface, scale_color(WHITE, 0.35 * wobble),
                               (int(x), int(y)), dome - 5, 1)
            blit_glow(surface, self.color, (int(x), int(y)), int(dome * 1.1))

        if self.variant == 1:
            hull = [(0, r * 0.95), (r * 0.62, r * 0.42), (r, -r * 0.15),
                    (r * 0.58, -r * 0.72), (0, -r * 0.5),
                    (-r * 0.58, -r * 0.72), (-r, -r * 0.15), (-r * 0.62, r * 0.42)]
            wing = [(r * 0.7, -r * 0.2), (r * 1.35, r * 0.1), (r * 1.15, r * 0.5),
                    (r * 0.6, r * 0.35)]
        else:
            hull = [(0, r), (r * 0.5, r * 0.55), (r * 1.0, r * 0.1),
                    (r * 0.8, -r * 0.55), (r * 0.3, -r * 0.35), (0, -r * 0.85),
                    (-r * 0.3, -r * 0.35), (-r * 0.8, -r * 0.55),
                    (-r * 1.0, r * 0.1), (-r * 0.5, r * 0.55)]
            wing = [(r * 0.85, -r * 0.35), (r * 1.6, -r * 0.05), (r * 1.5, r * 0.45),
                    (r * 0.75, r * 0.3)]

        for side in (1, -1):
            pts = rot_points([(px * side, py) for px, py in wing], 0, x, y)
            pygame.draw.polygon(surface, scale_color(self.accent, 0.25), pts)
            neon_poly(surface, self.accent, pts, 3)
            tip = rot_points([(wing[1][0] * side, wing[1][1])], 0, x, y)[0]
            blit_glow(surface, self.accent, tip, 16)

        pts = rot_points(hull, 0, x, y)
        pygame.draw.polygon(surface, scale_color(col, 0.28), pts)
        neon_poly(surface, col, pts, 4)

        # Rotierender Kern
        core_r = r * 0.34
        core = rot_points([(math.cos(a) * core_r, math.sin(a) * core_r)
                           for a in [math.tau * i / 6 for i in range(6)]],
                          self.time * 1.4, x, y)
        pygame.draw.polygon(surface, scale_color(WHITE, 0.35 * pulse), core)
        neon_poly(surface, mix_color(WHITE, self.accent, 0.4), core, 3)
        blit_glow(surface, self.accent, (int(x), int(y)), int(core_r * 1.6 * pulse + 10))

        # Kanonenpods
        for side in (1, -1):
            px = x + side * r * 0.62
            py = y + r * 0.5
            pygame.draw.circle(surface, scale_color(self.accent, 0.4), (int(px), int(py)), 12)
            pygame.draw.circle(surface, self.accent, (int(px), int(py)), 12, 2)
            pygame.draw.circle(surface, WHITE, (int(px), int(py)), 4)

        # Rauch bei niedriger HP
        if self.hp / self.max_hp < 0.35 and random.random() < 0.5:
            off = Vector2(random.uniform(-r * 0.8, r * 0.8), random.uniform(-r * 0.4, r * 0.4))
            pygame.draw.circle(surface, (90, 90, 100),
                               (int(x + off.x), int(y + off.y)),
                               random.randint(3, 7))

    def draw_hud(self, surface):
        """Bosslebensbalken direkt unter dem HUD, auf eigener Tafel - sonst
        verschwimmt die Schrift im Rumpf des Bosses."""
        w, h = WIDTH - 380, 20
        x, y = 190, HUD_HEIGHT + 30
        ratio = clamp(self.hp / self.max_hp, 0.0, 1.0)
        col = mix_color(RED, self.color, ratio)

        board = pygame.Rect(x - 12, y - 26, w + 24, h + 38)
        panel(surface, board, fill=(10, 8, 18), border=scale_color(col, 0.7),
              alpha=205, radius=8)

        draw_text(surface, self.name, 26, x, y - 22, mix_color(col, WHITE, 0.55),
                  bold=True, glow=col)
        draw_text(surface, "PHASE %d/%d" % (self.phase + 1, len(self.phases)), 20,
                  x + w, y - 20, WHITE, anchor="topright")
        draw_bar(surface, x, y, w, h, ratio, col, back=(30, 12, 24),
                 border=mix_color(col, WHITE, 0.3), segments=len(self.phase_hp))
        draw_text(surface, "%d / %d" % (int(self.hp), int(self.max_hp)), 18,
                  x + w // 2, y + h // 2, WHITE, anchor="center")

        if self.invulnerable:
            alive = len([g for g in self.generators if g.alive])
            pulse = 0.5 + 0.5 * math.sin(self.time * 7)
            draw_text(surface, "IMMUN - NOCH %d GENERATOR%s  (%.0fs)"
                      % (alive, "EN" if alive != 1 else "", max(0.0, self.bulwark_timer)),
                      24, x + w // 2, y + h + 12,
                      mix_color(self.color, WHITE, pulse), anchor="center", bold=True)
        elif self.rage > 0:
            draw_text(surface, "WUTSTUFE %d" % self.rage, 20, x + w // 2, y + h + 11,
                      ORANGE, anchor="center", bold=True)


# ==============================================================================
#  WELLENGENERATOR
# ==============================================================================

def wave_composition(level, count_mult=1.0):
    """Wie viele Gegner welchen Typs eine Welle enthaelt.

    Alles ist Formel, nichts ist handgeschrieben - damit funktioniert der
    Endlosmodus mit derselben Logik wie die Kampagne. Neue Typen kommen
    gestaffelt dazu, damit man sie einzeln kennenlernt."""
    tc = clamp(count_mult, 1.0, 2.4)
    # Bomber, Plattformen, Scharfschuetzen und Schildgeber bleiben stehen, bis
    # man sie abschiesst. Ihre Zahl darf deshalb nur gedaempft mitwachsen,
    # sonst steht irgendwann eine Wand aus Geschuetztuermen im Bild.
    tc_hover = 1.0 + (tc - 1.0) * HOVER_COUNT_SHARE

    def count(start_level, base, per_level, cap, mult=None):
        if level < start_level:
            return 0
        raw = min(cap, base + per_level * (level - start_level))
        return max(1, int(round(raw * (tc if mult is None else mult))))

    counts = {
        "interceptor": count(1, 8, 1.5, 24),
        "bomber":      count(2, 1, 0.40, 6, tc_hover),
        "drone":       count(3, 3, 0.75, 12),
        "splitter":    count(6, 1, 0.40, 6),
        "sentinel":    count(4, 1, 0.30, 5, tc_hover),
        "sniper":      count(7, 1, 0.30, 4, tc_hover),
        "mortar":      count(8, 1, 0.22, 3, tc_hover),
        "guardian":    count(9, 1, 0.16, 2, tc_hover),
    }
    if is_boss_level(level):
        # Vor dem Boss nur ein Vorgeplaenkel, der Boss ist das Hauptgericht
        counts = {k: max(0, int(v * 0.45)) for k, v in counts.items()}
        counts["interceptor"] = max(5, counts["interceptor"])

    # Harte Obergrenze: sonst werden Wellen im Endlosmodus minutenlang und
    # die Framerate leidet unter hunderten gleichzeitigen Gegnern.
    total = sum(counts.values())
    if total > MAX_WAVE_ENEMIES:
        factor = MAX_WAVE_ENEMIES / float(total)
        for key in counts:
            if counts[key] > 0:
                counts[key] = max(1, int(round(counts[key] * factor)))
    return counts


def build_wave(level, count_mult=1.0):
    """Erzeugt die Spawn-Tabelle einer Welle als Liste von
    (zeitpunkt, gegnertyp, x-position) plus den Zeitpunkt des Bosses."""
    rnd = random.Random(level * 7919 + 1337)
    counts = wave_composition(level, count_mult)

    groups = []
    for kind, total in counts.items():
        if total <= 0:
            continue
        if kind == "interceptor":
            size = 4 if level < 8 else 5
            while total > 0:
                take = min(size, total)
                groups.append((kind, take))
                total -= take
        elif kind == "drone":
            while total > 0:
                take = min(3, total)
                groups.append((kind, take))
                total -= take
        elif kind in ("bomber", "splitter", "sniper"):
            while total > 0:
                take = min(2, total)
                groups.append((kind, take))
                total -= take
        else:
            for _ in range(total):
                groups.append((kind, 1))
    rnd.shuffle(groups)

    # Wellenlaenge deckeln: mehr Gegner bedeutet dichtere Staffelung,
    # nicht endlos lange Wellen.
    base_gap = {"interceptor": 2.4, "bomber": 3.0, "drone": 2.6, "sentinel": 3.2,
                "splitter": 2.8, "sniper": 3.0, "guardian": 3.4, "mortar": 4.2}
    pace = clamp(1.0 - 0.035 * (level - 1), 0.42, 1.0)
    if len(groups) > 10:
        pace *= 10.0 / len(groups)

    events = []
    t = 1.2
    for kind, size in groups:
        band = rnd.uniform(150, WIDTH - 150)
        for i in range(size):
            if kind == "interceptor":
                x = band + (i - (size - 1) / 2) * 62
                delay = i * 0.22
            elif kind == "drone":
                x = band + (i - (size - 1) / 2) * 90
                delay = i * 0.30
            else:
                x = band + (i - (size - 1) / 2) * 120
                delay = i * 0.45
            events.append((t + delay, kind, clamp(x, 50, WIDTH - 50)))
        t += max(0.85, base_gap[kind] * pace) + size * 0.10

    events.sort(key=lambda e: e[0])
    if is_boss_level(level):
        boss_time = (events[-1][0] + 3.5) if events else 3.0
    else:
        boss_time = None
    return events, boss_time


# ==============================================================================
#  UI-BAUSTEINE
# ==============================================================================

def panel(surface, rect, fill=(12, 14, 26), border=(70, 90, 140), alpha=225, radius=10):
    box = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(box, (fill[0], fill[1], fill[2], alpha),
                     (0, 0, rect.width, rect.height), border_radius=radius)
    surface.blit(box, rect.topleft)
    pygame.draw.rect(surface, border, rect, 2, border_radius=radius)


def button_rects(count, top, spacing=60, width=380, height=50):
    rects = []
    for i in range(count):
        r = pygame.Rect(0, 0, width, height)
        r.center = (WIDTH // 2, top + i * spacing)
        rects.append(r)
    return rects


def draw_button(surface, rect, label, selected, t, enabled=True, sub=None,
                color=CYAN):
    if not enabled:
        color = DARKGREY
    if selected:
        glow = 0.55 + 0.45 * math.sin(t * 6)
        panel(surface, rect, fill=scale_color(color, 0.12), border=color, alpha=235)
        pygame.draw.rect(surface, mix_color(color, WHITE, glow * 0.5), rect, 2,
                         border_radius=10)
        for side in (-1, 1):
            px = rect.centerx + side * (rect.width // 2 - 16)
            pts = [(px - side * 8, rect.centery - 8), (px, rect.centery),
                   (px - side * 8, rect.centery + 8)]
            pygame.draw.polygon(surface, color, pts)
    else:
        panel(surface, rect, fill=(14, 16, 30), border=(60, 68, 96), alpha=190)
    label_col = WHITE if enabled else (110, 116, 138)
    draw_text(surface, label, 32, rect.centerx, rect.centery - (7 if sub else 0),
              label_col, anchor="center", bold=True,
              glow=color if selected else None)
    if sub:
        draw_text(surface, sub, 19, rect.centerx, rect.centery + 14,
                  GREY, anchor="center")


def draw_currency_row(surface, x, y, coins, crystals, size=26):
    pygame.draw.circle(surface, GOLD, (x + 10, y), 9)
    pygame.draw.circle(surface, mix_color(GOLD, WHITE, 0.6), (x + 10, y), 9, 2)
    r = draw_text(surface, str(int(coins)), size, x + 26, y, GOLD, anchor="midleft",
                  bold=True)
    cx = r.right + 26
    pts = [(cx, y - 10), (cx + 8, y), (cx, y + 10), (cx - 8, y)]
    pygame.draw.polygon(surface, (20, 70, 130), pts)
    pygame.draw.polygon(surface, CRYSTAL, pts, 2)
    draw_text(surface, str(int(crystals)), size, cx + 18, y, CRYSTAL,
              anchor="midleft", bold=True)


def draw_stat_bar(surface, x, y, w, label, ratio, color):
    draw_text(surface, label, 19, x, y - 1, GREY, anchor="midleft")
    bx = x + 92
    draw_bar(surface, bx, y - 6, w, 12, ratio, color)


# ==============================================================================
#  HAUPTSPIELKLASSE
# ==============================================================================

class Game:

    def __init__(self):
        pygame.init()
        pygame.display.set_caption(TITLE)
        # SCALED skaliert das Bild sauber auf Vollbild, ist aber nicht auf
        # jedem System verfuegbar - im Zweifel ohne Flag weitermachen.
        self.screen = None
        for flags in (getattr(pygame, "SCALED", 0), 0):
            try:
                self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
                break
            except pygame.error:
                continue
        if self.screen is None:                           # pragma: no cover
            raise SystemExit("Es konnte kein Fenster geoeffnet werden.")
        self._set_icon()
        self.world = pygame.Surface((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.running = True
        self.time = 0.0

        self.save = load_save()
        self.starfield = Starfield()
        self.effects = EffectSystem()

        self.state = "menu"
        self.menu_index = 0
        self.shop_index = 0
        self.shop_context = "menu"
        self.werft_index = 0
        self.werft_ship = 0
        self.message = ""
        self.message_timer = 0.0

        self.shake_amount = 0.0
        self.player = None
        self.level = 1
        self.power = 1.0
        self.threat = 1.0
        self.aggro = 1.0
        self.count_threat = 1.0
        self.mutation_p = 0.0
        self.enemy_dmg = 1.0
        self.tier = DEFAULT_TIER
        self.loot_mult = 1.0
        self.mods = []
        self.mod_mult = {"dmg": 1.0, "fire": 1.0, "hp": 1.0, "speed": 1.0,
                         "shield": 1.0, "loot": 1.0, "enemy_hp": 1.0, "taken": 1.0}
        self.mod_flags = set()
        self.draft_options = []
        self.draft_index = 0
        self.slowmo = 0.0
        self.kill_streak = 0
        self.biome = BIOMES[0]
        self.db = StatsDB()
        self.reset_run()

    # ------------------------------------------------------------------ Setup
    def _set_icon(self):
        try:
            icon = pygame.Surface((32, 32), pygame.SRCALPHA)
            pygame.draw.polygon(icon, CYAN, [(16, 2), (30, 28), (16, 21), (2, 28)])
            pygame.display.set_icon(icon)
        except pygame.error:                              # pragma: no cover
            pass

    def reset_run(self):
        self.level = 1
        self.score = 0
        self.enemies = []
        self.bullets = []
        self.enemy_bullets = []
        self.pickups = []
        self.boss = None
        self.effects.clear()
        self.wave_events = []
        self.spawn_idx = 0
        self.wave_time = 0.0
        self.boss_time = None
        self.boss_spawned = False
        self.wave_cleared = False
        self.intermission = 0.0
        self.banner_timer = 0.0
        self.banner_text = ""
        self.banner_sub = ""
        self.run_coins = 0
        self.run_crystals = 0
        self.stats = {"shots": 0, "hits": 0, "kills": 0, "time": 0.0,
                      "coins": 0, "crystals": 0, "waves": 0, "crates": 0}
        self.player = Player(self.save["ship"], self.save)

        # ---------------------------------------------------- Verbrauchsgueter
        self.mods = []                       # gewaehlte Kampfmodifikationen
        self.mod_mult = {"dmg": 1.0, "fire": 1.0, "hp": 1.0, "speed": 1.0,
                         "shield": 1.0, "loot": 1.0, "enemy_hp": 1.0, "taken": 1.0}
        self.mod_flags = set()
        self.draft_options = []
        self.draft_index = 0
        self.slowmo = 0.0
        self.kill_streak = 0
        self.consum_bought = {key: 0 for key in CONSUMABLE_ORDER}
        self.tier = int(clamp(_as_int(self.save.get("tier"), DEFAULT_TIER),
                              0, tier_top(self.save)))
        self.revives = refit_free_lives(self.save.get("refit", 0))
        self.overdrive_waves = 0
        self.endless = False
        self.mutation_count = 0
        self.last_killer = None

        self.refresh_power()
        self.apply_biome(1)
        if self.db is not None:
            key = self.save["ship"]
            self.db.start_run(key, self.save["upgrades"], self.power,
                              player_dps(self.save["upgrades"], SHIPS[key],
                                         progression_mult(self.save, key)))

    # ----------------------------------------------------- Kampfmodifikationen
    def draw_draft_options(self):
        """Drei Karten ziehen - je hoeher die Welle, desto bessere Seltenheit."""
        taken = set(self.mods)
        pool = [m for m in MODS if m["key"] not in taken or "mult" in m]
        if len(pool) < 3:
            pool = list(MODS)
        weights = []
        for mod in pool:
            base = {0: 30, 1: 16, 2: 5}[mod["rare"]]
            base += self.level * (0.4 if mod["rare"] else -0.6)
            if mod["key"] in taken:
                base *= 0.35                 # Wiederholungen sind moeglich, aber selten
            weights.append(max(1.0, base))
        picks = []
        for _ in range(3):
            if not pool:
                break
            choice = random.choices(pool, weights=weights, k=1)[0]
            idx = pool.index(choice)
            pool.pop(idx)
            weights.pop(idx)
            picks.append(choice["key"])
        return picks

    def apply_mod(self, key):
        mod = MOD_BY_KEY[key]
        self.mods.append(key)
        for stat, value in mod.get("mult", {}).items():
            self.mod_mult[stat] = self.mod_mult.get(stat, 1.0) * value
        if "flag" in mod:
            self.mod_flags.add(mod["flag"])
        if mod.get("flag") == "revive":
            self.revives += 1
        self.sync_mods()
        self.notify("%s: %s" % (mod["name"], mod["desc"]))

    def sync_mods(self):
        """Uebertraegt die Modifikationen auf Spieler und Wellenwerte."""
        if self.player is not None:
            self.player.mod_mult = self.mod_mult
            self.player.mod_flags = self.mod_flags
            before = self.player.max_hp
            self.player.max_hp = self.player.compute_max_hp()
            if self.player.max_hp > before:
                self.player.hp += self.player.max_hp - before
            self.player.apply_shield_bonus()
        self.refresh_power()

    # ------------------------------------------------- Adaptive Schwierigkeit
    def refresh_power(self):
        """Machtindex neu berechnen - nach jedem Kauf und zu jeder Welle."""
        key = self.player.ship_key if self.player else self.save["ship"]
        self.power = power_index(self.save, key)
        cfg = self.tier_cfg()
        scale = threat_ramp(self.level) * cfg["threat"]
        self.threat = 1.0 + (threat_hp(self.power) - 1.0) * scale
        self.aggro = 1.0 + (threat_aggro(self.power) - 1.0) * scale
        self.count_threat = 1.0 + (threat_count(self.power) - 1.0) * scale
        self.mutation_p = mutation_chance(self.level, self.power) * scale
        self.enemy_dmg = cfg["dmg"]
        if self.hardship("armor"):
            self.threat *= 1.20
        self.threat *= self.mod_mult.get("enemy_hp", 1.0)
        self.loot_mult = cfg["reward"] * self.mod_mult.get("loot", 1.0)
        if self.player is not None:
            self.loot_mult *= self.player_prog()["coins"]
            self.loot_mult *= 1.0 + 0.12 * self.player.addons["salvage"]

    def player_prog(self):
        key = self.player.ship_key if self.player else self.save["ship"]
        return progression_mult(self.save, key)

    def tier_cfg(self):
        return tier_cfg(self.tier)

    def hardship(self, name):
        """Ist die Sonderregel `name` auf der laufenden Gefahrenstufe aktiv?"""
        return name in tier_cfg(self.tier)["hardships"]

    def roll_mutations(self, kind):
        """Wuerfelt die Zusatzmodule eines einzelnen Gegners aus."""
        if kind in ("shard", "generator"):
            return ()
        if random.random() > self.mutation_p:
            return ()
        keys = MUTATION_KEYS
        weights = [MUTATIONS[k]["weight"] for k in keys]
        picked = set(random.choices(keys, weights=weights, k=1))
        # Bei hoher Bedrohung kann ein Gegner ein zweites Modul bekommen
        if random.random() < self.mutation_p * 0.35:
            picked |= set(random.choices(keys, weights=weights, k=1))
        self.mutation_count += len(picked)
        return tuple(picked)

    def apply_biome(self, level):
        """Kulisse an die Wellennummer anpassen."""
        self.biome = biome_for(level)
        self.starfield.set_biome(self.biome)

    def start_level(self, level):
        self.level = level
        self.endless = level > CAMPAIGN_LEVELS
        self.refresh_power()
        self.wave_events, self.boss_time = build_wave(level, self.count_threat)
        self.spawn_idx = 0
        self.wave_time = 0.0
        self.boss_spawned = False
        self.wave_cleared = False
        self.intermission = 0.0
        self.boss = None
        self.enemy_bullets.clear()

        previous = getattr(self, "biome", None)
        self.apply_biome(level)
        biome_changed = previous is not None and previous is not self.biome

        self.kill_streak = 0
        if "guard" in self.mod_flags and self.player is not None:
            self.player.shield = self.player.max_shield
        # Der Aegis-Ring wird zu jedem Wellenstart frisch aufgezogen
        if self.player is not None:
            self.player.refresh_aegis(refill=True)
            self.player.flak_timer = FLAK_INTERVAL

        # Overdrive gilt genau eine Welle
        if self.overdrive_waves > 0:
            self.overdrive_waves -= 1
            self.player.damage_mult = 1.30
        else:
            self.player.damage_mult = 1.0

        # Zaehler fuer die Wellenstatistik
        self.wave_stats = {
            "kills": 0, "shots": self.stats["shots"], "hits": self.stats["hits"],
            "damage_taken": 0.0, "coins": 0, "crystals": 0, "start": self.stats["time"],
            "boss_hp": 0.0, "boss_start": None, "boss_ttk": 0.0,
            "mutations": 0,
        }
        self.mutation_count = 0

        if is_boss_level(level):
            self.banner("WELLE %d" % level, "ACHTUNG - BOSSANFLUG")
        elif biome_changed:
            self.banner("WELLE %d" % level, "Sektor: %s" % self.biome["name"])
        else:
            self.banner("WELLE %d" % level, "%d Gegner im Anflug" % len(self.wave_events))

    def banner(self, text, sub=""):
        self.banner_text = text
        self.banner_sub = sub
        self.banner_timer = 2.6

    def notify(self, text):
        self.message = text
        self.message_timer = 2.2

    def shake(self, amount):
        self.shake_amount = min(34.0, self.shake_amount + amount)

    # ------------------------------------------------------------ Persistenz
    def persist(self):
        write_save(self.save)

    # =========================================================================
    #  EVENTS
    # =========================================================================
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.quit_game()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11:
                    try:
                        pygame.display.toggle_fullscreen()
                    except pygame.error:                  # pragma: no cover
                        pass
                    continue
                self.on_key(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.on_click(event.pos)
            elif event.type == pygame.MOUSEMOTION:
                self.on_motion(event.pos)

    def quit_game(self):
        self.persist()
        if self.state in ("playing", "paused", "shop") and self.db is not None:
            self.record_run("abbruch")
        if self.db is not None:
            self.db.close()
        self.running = False

    # ------------------------------------------------------------- Tastatur
    def on_key(self, key):
        state = self.state
        if state == "menu":
            items = self.menu_items()
            if key in (pygame.K_UP, pygame.K_w):
                self.menu_index = (self.menu_index - 1) % len(items)
            elif key in (pygame.K_DOWN, pygame.K_s):
                self.menu_index = (self.menu_index + 1) % len(items)
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                items[self.menu_index][1]()
            elif key in (pygame.K_LEFT, pygame.K_RIGHT):
                action = items[self.menu_index][1]
                if action == self.cycle_tier:
                    action(1 if key == pygame.K_RIGHT else -1)
            elif key == pygame.K_ESCAPE:
                self.quit_game()

        elif state == "shop":
            if key in (pygame.K_UP, pygame.K_w):
                self.shop_move(0, -1)
            elif key in (pygame.K_DOWN, pygame.K_s):
                self.shop_move(0, 1)
            elif key in (pygame.K_LEFT, pygame.K_a):
                self.shop_move(-1, 0)
            elif key in (pygame.K_RIGHT, pygame.K_d):
                self.shop_move(1, 0)
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.shop_activate(self.shop_index)
            elif key == pygame.K_ESCAPE:
                self.leave_shop()

        elif state == "draft":
            if key in (pygame.K_LEFT, pygame.K_a):
                self.draft_index = (self.draft_index - 1) % max(1, len(self.draft_options))
            elif key in (pygame.K_RIGHT, pygame.K_d):
                self.draft_index = (self.draft_index + 1) % max(1, len(self.draft_options))
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.choose_draft(self.draft_index)
            elif key in (pygame.K_1, pygame.K_2, pygame.K_3):
                self.choose_draft(key - pygame.K_1)

        elif state == "werft":
            if key in (pygame.K_UP, pygame.K_w):
                self.werft_index = (self.werft_index - 1) % 4
            elif key in (pygame.K_DOWN, pygame.K_s):
                self.werft_index = (self.werft_index + 1) % 4
            elif key in (pygame.K_LEFT, pygame.K_a):
                self.werft_ship = (self.werft_ship - 1) % len(SHIP_ORDER)
            elif key in (pygame.K_RIGHT, pygame.K_d):
                self.werft_ship = (self.werft_ship + 1) % len(SHIP_ORDER)
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.werft_activate(self.werft_index)
            elif key == pygame.K_ESCAPE:
                self.state = "menu"
                self.persist()

        elif state == "playing":
            if key == pygame.K_ESCAPE or key == pygame.K_p:
                self.state = "paused"
                self.menu_index = 0

        elif state == "paused":
            items = self.pause_items()
            if key in (pygame.K_UP, pygame.K_w):
                self.menu_index = (self.menu_index - 1) % len(items)
            elif key in (pygame.K_DOWN, pygame.K_s):
                self.menu_index = (self.menu_index + 1) % len(items)
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                items[self.menu_index][1]()
            elif key in (pygame.K_ESCAPE, pygame.K_p):
                self.state = "playing"

        elif state in ("gameover", "victory"):
            items = self.end_items()
            if key in (pygame.K_UP, pygame.K_w):
                self.menu_index = (self.menu_index - 1) % len(items)
            elif key in (pygame.K_DOWN, pygame.K_s):
                self.menu_index = (self.menu_index + 1) % len(items)
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                items[self.menu_index][1]()
            elif key == pygame.K_ESCAPE:
                self.state = "menu"
                self.menu_index = 0

    # ----------------------------------------------------------------- Maus
    def on_motion(self, pos):
        if self.state == "menu":
            for i, rect in enumerate(self.menu_rects()):
                if rect.collidepoint(pos):
                    self.menu_index = i
        elif self.state == "paused":
            for i, rect in enumerate(button_rects(len(self.pause_items()), 320)):
                if rect.collidepoint(pos):
                    self.menu_index = i
        elif self.state in ("gameover", "victory"):
            for i, rect in enumerate(button_rects(len(self.end_items()), 520)):
                if rect.collidepoint(pos):
                    self.menu_index = i
        elif self.state == "shop":
            for i, rect in enumerate(self.shop_rects()):
                if rect.collidepoint(pos):
                    self.shop_index = i
        elif self.state == "werft":
            for i, rect in enumerate(self.werft_rects()):
                if rect.collidepoint(pos):
                    self.werft_index = i

    def on_click(self, pos):
        if self.state == "menu":
            items = self.menu_items()
            for i, rect in enumerate(self.menu_rects()):
                if rect.collidepoint(pos):
                    items[i][1]()
                    return
        elif self.state == "paused":
            items = self.pause_items()
            for i, rect in enumerate(button_rects(len(items), 320)):
                if rect.collidepoint(pos):
                    items[i][1]()
                    return
        elif self.state in ("gameover", "victory"):
            items = self.end_items()
            for i, rect in enumerate(button_rects(len(items), 520)):
                if rect.collidepoint(pos):
                    items[i][1]()
                    return
        elif self.state == "shop":
            for i, rect in enumerate(self.shop_rects()):
                if rect.collidepoint(pos):
                    self.shop_index = i
                    self.shop_activate(i)
                    return
        elif self.state == "draft":
            for i, rect in enumerate(self.draft_rects()):
                if rect.collidepoint(pos):
                    self.choose_draft(i)
                    return
        elif self.state == "draft":
            for i, rect in enumerate(self.draft_rects()):
                if rect.collidepoint(pos):
                    self.draft_index = i
        elif self.state == "werft":
            for i, rect in enumerate(self.werft_rects()):
                if rect.collidepoint(pos):
                    self.werft_index = i
                    self.werft_activate(i)
                    return

    # =========================================================================
    #  MENUE-AKTIONEN
    # =========================================================================
    def menu_items(self):
        return [
            ("SPIEL STARTEN", self.action_start),
            ("WERFT", self.action_werft),
            ("UPGRADE SHOP", self.action_shop_from_menu),
            ("GEFAHRENSTUFE: %s" % self.tier_cfg()["name"].upper(),
             self.cycle_tier),
            ("BEENDEN", self.quit_game),
        ]

    def menu_rects(self):
        return button_rects(len(self.menu_items()), 268, 52, 380, 46)

    def cycle_tier(self, step=1):
        """Gefahrenstufe waehlen - hoechstens eine ueber der bezwungenen."""
        top = tier_top(self.save)
        tier = int(clamp(_as_int(self.save.get("tier"), DEFAULT_TIER), 0, top))
        tier = (tier + step) % (top + 1)
        self.save["tier"] = tier
        self.tier = tier
        write_save(self.save)
        self.refresh_power()
        cfg = tier_cfg(tier)
        self.notify("%s - %s  (%+d %% Beute)"
                    % (cfg["name"], cfg["desc"],
                       round((cfg["reward"] - 1.0) * 100)))

    def pause_items(self):
        return [
            ("WEITER", self.action_resume),
            ("UPGRADE SHOP", self.action_shop_from_pause),
            ("HAUPTMENUE", self.action_abandon),
        ]

    def end_items(self):
        items = []
        if self.state == "victory":
            items.append(("ENDLOS WEITERFLIEGEN", self.action_continue_endless))
        items.extend([
            ("NEUER VERSUCH", self.action_start),
            ("UPGRADE SHOP", self.action_shop_from_menu),
            ("HAUPTMENUE", self.action_to_menu),
        ])
        return items

    def action_start(self):
        self.reset_run()
        self.start_level(1)
        self.state = "playing"

    def action_resume(self):
        self.state = "playing"

    def action_to_menu(self):
        self.state = "menu"
        self.menu_index = 0
        self.persist()

    def action_abandon(self):
        self.persist()
        self.state = "menu"
        self.menu_index = 0

    def action_shop_from_menu(self):
        self.shop_context = "menu"
        self.shop_index = 0
        self.state = "shop"

    def action_shop_from_pause(self):
        self.shop_context = "pause"
        self.shop_index = 0
        self.state = "shop"

    def action_werft(self):
        self.state = "werft"
        self.werft_index = 0
        self.werft_ship = SHIP_ORDER.index(self.save["ship"]) \
            if self.save["ship"] in SHIP_ORDER else 0

    # -------------------------------------------------------- Schiffsraenge
    def werft_ship_key(self):
        return SHIP_ORDER[int(clamp(getattr(self, "werft_ship", 0),
                                    0, len(SHIP_ORDER) - 1))]

    def try_buy_rank(self):
        key = self.werft_ship_key()
        if key not in self.save["unlocked"]:
            self.notify("%s ist noch nicht freigeschaltet." % SHIPS[key]["name"])
            return
        rank = self.save["ranks"].get(key, 0)
        coins, crystals = rank_cost(rank)
        if coins is None:
            self.notify("%s ist auf dem hoechsten Rang." % SHIPS[key]["name"])
            return
        if self.save["coins"] < coins or self.save["crystals"] < crystals:
            self.notify("Rang %d kostet %d Muenzen%s." %
                        (rank + 1, coins,
                         " und %d Kristalle" % crystals if crystals else ""))
            return
        self.save["coins"] -= coins
        self.save["crystals"] -= crystals
        self.save["ranks"][key] = rank + 1
        write_save(self.save)
        if self.db is not None:
            self.db.log_purchase(self.level, "rang_%s" % key, "rang", coins,
                                 "coins", rank + 1)
        step = RANK_STEPS[rank + 1]
        if "system" in step:
            sysdef = SHIP_SYSTEMS[key][step["system"]]
            self.notify("System freigeschaltet: %s - %s"
                        % (sysdef["name"], sysdef["desc"]))
        else:
            self.notify("%s auf Rang %d." % (SHIPS[key]["name"], rank + 1))
        self.rebuild_player()

    # ---------------------------------------------------------------- Refit
    def refit_ready(self):
        ups = self.save.get("upgrades", {})
        return all(ups.get(k, 1) >= UPGRADES[k]["max"] for k in UPGRADE_ORDER)

    def try_refit(self):
        if not self.refit_ready():
            missing = [UPGRADES[k]["name"] for k in UPGRADE_ORDER
                       if self.save["upgrades"][k] < UPGRADES[k]["max"]]
            self.notify("Refit braucht alle Kernaufwertungen auf Maximum. Offen: %s"
                        % ", ".join(missing[:3]))
            return
        for key in UPGRADE_ORDER:
            self.save["upgrades"][key] = 1
        self.save["refit"] = self.save.get("refit", 0) + 1
        write_save(self.save)
        level = self.save["refit"]
        if self.db is not None:
            self.db.log_purchase(self.level, "refit", "refit", 0, "coins", level)
        self.notify("Refit %d abgeschlossen: dauerhaft +%d %% Schaden und "
                    "+%d %% Muenzfund."
                    % (level, round(REFIT_DAMAGE_PER * level * 100),
                       round(REFIT_COINS_PER * level * 100)))
        self.rebuild_player()

    def rebuild_player(self):
        """Spielerschiff neu aufbauen, damit Rang und Refit sofort greifen."""
        if self.state in ("playing", "paused"):
            if self.player is not None:
                self.player.prog = progression_mult(self.save, self.player.ship_key)
                self.player.systems = self.player.prog["systems"]
                self.player.setup_mechanic()
                self.player.max_hp = self.player.compute_max_hp()
                self.player.hp = min(self.player.hp, self.player.max_hp)
                self.player.apply_shield_bonus()
        else:
            self.player = Player(self.save["ship"], self.save)
        self.refresh_power()

    def leave_shop(self):
        self.persist()
        if self.shop_context == "menu":
            self.state = "menu"
        elif self.shop_context == "pause":
            self.state = "playing"
        else:
            nxt = self.level + 1
            if nxt > CAMPAIGN_LEVELS and not self.endless:
                self.finish_victory()
            else:
                self.start_level(nxt)
                self.state = "playing"

    # ------------------------------------------------------------- Einkaeufe
    def try_buy(self, key):
        cfg = UPGRADES[key]
        level = self.save["upgrades"][key]
        cost = upgrade_cost(key, level)
        if cost is None:
            self.notify("%s ist bereits maximal ausgebaut." % cfg["name"])
            return
        currency = cfg["currency"]
        if self.save[currency] < cost:
            self.notify("Nicht genug %s! (%d benoetigt)" %
                        ("Muenzen" if currency == "coins" else "Kristalle", cost))
            return
        self.save[currency] -= cost
        self.save["upgrades"][key] = level + 1
        write_save(self.save)
        self.notify("%s auf Stufe %d verbessert!" % (cfg["name"], level + 1))
        if self.db is not None:
            self.db.log_purchase(self.level, key, "upgrade", cost, currency, level + 1)
        if self.player is not None:
            self.player.upgrades = self.save["upgrades"]
            if key == "maxhp":
                gained = self.player.compute_max_hp() - self.player.max_hp
                self.player.max_hp = self.player.compute_max_hp()
                self.player.hp = min(self.player.max_hp, self.player.hp + max(0, gained))
        self.refresh_power()

    def select_or_buy_ship(self):
        key = self.werft_ship_key()
        ship = SHIPS[key]
        if key in self.save["unlocked"]:
            self.save["ship"] = key
            write_save(self.save)
            self.notify("%s ausgewaehlt." % ship["name"])
            self.rebuild_player()
            return
        if self.save["crystals"] >= ship["price"]:
            self.save["crystals"] -= ship["price"]
            self.save["unlocked"].append(key)
            self.save["ship"] = key
            write_save(self.save)
            self.notify("%s freigeschaltet!" % ship["name"])
            self.save["ranks"].setdefault(key, 0)
            self.rebuild_player()
        else:
            self.notify("Nicht genug Kristalle! (%d benoetigt)" % ship["price"])

    # =========================================================================
    #  SPIELLOGIK
    # =========================================================================
    def update(self, dt):
        self.time += dt
        self.message_timer = max(0.0, self.message_timer - dt)
        self.shake_amount *= 0.88 ** (dt * 60)
        if self.shake_amount < 0.1:
            self.shake_amount = 0.0

        speed = 1.0
        if self.state == "playing":
            speed = 1.0 + (0.9 if self.boss is not None else 0.0)
        self.starfield.boost = lerp(self.starfield.boost, speed, dt * 2)
        self.starfield.update(dt)

        if self.state == "playing":
            self.update_playing(dt)
        elif self.state in ("menu", "werft", "shop", "draft",
                            "gameover", "victory"):
            self.effects.update(dt)

    def update_playing(self, dt):
        if self.slowmo > 0:
            self.slowmo = max(0.0, self.slowmo - dt)
            dt *= 0.45                       # Zeitdehnung
        self.stats["time"] += dt
        self.banner_timer = max(0.0, self.banner_timer - dt)
        keys = pygame.key.get_pressed()

        player = self.player
        if player is not None and player.alive:
            player.update(dt, keys, self)

        # ------------------------------------------------------------ Spawns
        self.wave_time += dt
        while (self.spawn_idx < len(self.wave_events)
               and self.wave_events[self.spawn_idx][0] <= self.wave_time):
            _, kind, x = self.wave_events[self.spawn_idx]
            self.spawn_idx += 1
            mutations = self.roll_mutations(kind)
            enemy = ENEMY_CLASSES[kind](x, -40.0, self.level, self.threat, mutations)
            self.enemies.append(enemy)

        if (self.boss_time is not None and not self.boss_spawned
                and self.wave_time >= self.boss_time):
            self.boss_spawned = True
            self.boss = Boss(self.level, boss_variant(self.level), self.power,
                             boss_tier(self.level),
                             extra_bulwark=1 if self.hardship("bulwark") else 0)
            self.wave_stats["boss_hp"] = self.boss.max_hp
            self.wave_stats["boss_start"] = self.stats["time"]
            self.banner(self.boss.name, "BOSS")
            self.shake(14)

        # ----------------------------------------------------------- Updates
        for enemy in self.enemies:
            enemy.update(dt, self)
        self.enemies = [e for e in self.enemies if e.alive]

        if self.boss is not None:
            self.boss.update(dt, self)
            if self.boss is not None and not self.boss.alive:
                self.boss = None

        ricochet = "ricochet" in self.mod_flags
        for bullet in self.bullets:
            bullet.update(dt, self.enemies)
            if ricochet and not bullet.bounced and (bullet.pos.x < 8
                                                    or bullet.pos.x > WIDTH - 8):
                bullet.bounced = True
                bullet.vel.x *= -1
                bullet.pos.x = clamp(bullet.pos.x, 10, WIDTH - 10)
        self.bullets = [b for b in self.bullets if b.alive]

        ppos = player.pos if (player is not None and player.alive) else None
        for bullet in self.enemy_bullets:
            bullet.update(dt, ppos)
        self.enemy_bullets = [b for b in self.enemy_bullets if b.alive]

        magnet = player.magnet_radius if player is not None else 0
        for pickup in self.pickups:
            pickup.update(dt, player, magnet)
        self.pickups = [p for p in self.pickups if p.alive]

        self.effects.update(dt)
        self.handle_collisions()

        # ------------------------------------------------- Wellen-Abschluss
        if not self.wave_cleared and self.check_wave_cleared():
            self.wave_cleared = True
            self.intermission = 2.2
            bonus = int(50 * self.level * (1.0 + 0.05 * (self.power - 1))
                        * self.loot_mult)
            self.save["coins"] += bonus
            self.stats["coins"] += bonus
            self.wave_stats["coins"] += bonus

            # Garantierte Kristalle: macht den Fortschritt planbar statt
            # vom Zufall abhaengig.
            gems = self.level // 3 + 1
            if self.player is not None and self.player.prog["refit"] >= REFIT_CRYSTAL_AT:
                gems *= 2
            gems = int(round(gems * self.tier_cfg()["reward"]))
            self.save["crystals"] += gems
            self.stats["crystals"] += gems
            self.wave_stats["crystals"] += gems

            # Reparaturprotokoll (Phoenix II)
            if self.player is not None and "repair" in self.player.systems:
                self.player.heal(self.player.max_hp * 0.15)

            self.stats["waves"] = self.level
            self.score += 500 * self.level
            self.banner("WELLE %d GESCHAFFT" % self.level,
                        "+%d Muenzen, +%d Kristalle" % (bonus, gems))
            self.log_wave(cleared=True)
            write_save(self.save)

        if self.wave_cleared:
            self.intermission -= dt
            if self.intermission <= 0:
                self.enemy_bullets.clear()
                if self.level == CAMPAIGN_LEVELS and not self.endless:
                    self.finish_victory()
                else:
                    self.start_draft()

        if player is not None and not player.alive and self.state == "playing":
            if self.revives > 0:
                self.use_revive()
            else:
                self.finish_gameover()

    def use_revive(self):
        """Notfall-Rettung aus dem Shop: einmal weiterfliegen statt Game Over."""
        self.revives -= 1
        player = self.player
        player.alive = True
        player.hp = player.max_hp * 0.5
        player.shield = player.max_shield
        player.invuln = 3.0
        player.vel = Vector2(0, 0)
        self.enemy_bullets.clear()
        self.effects.explosion(player.pos, CYAN, size=3.0, count=70)
        self.effects.waves.append(Shockwave(player.pos, 320, 0.9, CYAN, 4))
        self.shake(22)
        self.banner("NOTFALL-RETTUNG", "Noch %d verfuegbar" % self.revives)

    def start_draft(self):
        """Drei Kampfmodifikationen zur Auswahl stellen."""
        self.draft_options = self.draw_draft_options()
        self.draft_index = 0
        if self.draft_options:
            self.state = "draft"
        else:
            self.open_wave_shop()

    def open_wave_shop(self):
        self.shop_context = "wave"
        self.shop_index = 0
        self.state = "shop"

    def choose_draft(self, index):
        if 0 <= index < len(self.draft_options):
            self.apply_mod(self.draft_options[index])
        self.draft_options = []
        self.open_wave_shop()

    def draft_rects(self):
        width, gap = 300, 34
        total = 3 * width + 2 * gap
        x0 = (WIDTH - total) // 2
        return [pygame.Rect(x0 + i * (width + gap), 190, width, 330)
                for i in range(3)]

    def draw_draft(self, surface):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((4, 6, 16, 236))
        surface.blit(overlay, (0, 0))
        draw_text(surface, "KAMPFMODIFIKATION", 52, WIDTH // 2, 48, WHITE,
                  anchor="center", bold=True, glow=CYAN)
        draw_text(surface, "Eine Karte waehlen - sie gilt nur fuer diesen Versuch.",
                  22, WIDTH // 2, 100, GREY, anchor="center")
        draw_text(surface, "Bereits aktiv: %d" % len(self.mods), 19, WIDTH // 2, 128,
                  mix_color(CYAN, WHITE, 0.3), anchor="center")

        for i, rect in enumerate(self.draft_rects()):
            if i >= len(self.draft_options):
                break
            mod = MOD_BY_KEY[self.draft_options[i]]
            col = MOD_RARITY_COLOR[mod["rare"]]
            selected = (i == self.draft_index)
            if selected:
                panel(surface, rect, fill=scale_color(col, 0.16), border=col)
                pygame.draw.rect(surface, mix_color(col, WHITE, 0.4), rect, 3,
                                 border_radius=10)
            else:
                panel(surface, rect, fill=(12, 14, 26), border=(56, 62, 90), alpha=210)

            draw_text(surface, MOD_RARITY_NAME[mod["rare"]].upper(), 17,
                      rect.centerx, rect.y + 16, col, anchor="center")
            draw_mod_icon(surface, mod, rect.centerx, rect.y + 96, self.time,
                          1.6 if selected else 1.3)
            draw_text(surface, mod["name"], 27, rect.centerx, rect.y + 160, WHITE,
                      anchor="center", bold=True, glow=col if selected else None)

            words = mod["desc"].split()
            line, lines = "", []
            for word in words:
                probe = (line + " " + word).strip()
                if font(19).size(probe)[0] > rect.width - 44:
                    lines.append(line)
                    line = word
                else:
                    line = probe
            lines.append(line)
            for j, text in enumerate(lines[:3]):
                draw_text(surface, text, 19, rect.centerx, rect.y + 200 + j * 24,
                          GREY, anchor="center")
            if self.mods.count(mod["key"]):
                draw_text(surface, "bereits %dx aktiv" % self.mods.count(mod["key"]),
                          17, rect.centerx, rect.bottom - 30, col, anchor="center")
            draw_text(surface, str(i + 1), 22, rect.x + 16, rect.bottom - 32,
                      GREY, anchor="midleft")

        draw_text(surface, "Links/Rechts waehlen  |  ENTER nehmen  |  1-3 direkt",
                  20, WIDTH // 2, HEIGHT - 40, GREY, anchor="center")

    def log_wave(self, cleared):
        """Wellenzeile in die Statistik-Datenbank schreiben."""
        if self.db is None or not hasattr(self, "wave_stats"):
            return
        ws = self.wave_stats
        duration = self.stats["time"] - ws["start"]
        self.db.log_wave({
            "wave": self.level, "cleared": cleared, "duration": duration,
            "kills": ws["kills"], "shots": self.stats["shots"] - ws["shots"],
            "hits": self.stats["hits"] - ws["hits"],
            "damage_taken": ws["damage_taken"],
            "hp_left": self.player.hp if self.player else 0.0,
            "coins": ws["coins"], "crystals": ws["crystals"],
            "power": self.power, "threat_hp": self.threat,
            "enemies": len(self.wave_events), "boss": bool(self.boss_time),
            "boss_hp": ws["boss_hp"], "boss_ttk": ws["boss_ttk"],
            "mutations": self.mutation_count,
        })

    def check_wave_cleared(self):
        if self.spawn_idx < len(self.wave_events):
            return False
        if self.enemies:
            return False
        if self.boss_time is not None and (not self.boss_spawned or self.boss is not None):
            return False
        return True

    # ------------------------------------------------------------ Kollisionen
    def handle_collisions(self):
        player = self.player
        # Minen sind selten - einmal je Frame sammeln statt je Geschoss suchen
        bombs = [b for b in self.enemy_bullets if b.alive and b.hp > 0]

        # Spielerprojektile -> Gegner / Boss
        for bullet in self.bullets:
            if not bullet.alive:
                continue
            hit = False
            for enemy in self.enemies:
                if not enemy.alive or id(enemy) in bullet.hits:
                    continue
                if (bullet.pos - enemy.pos).length_squared() <= (enemy.radius + bullet.radius) ** 2:
                    enemy.damage(bullet.damage, self)
                    self.effects.spark(bullet.pos, bullet.color, 5, 130, 0.22, 2)
                    self.stats["hits"] += 1
                    self.apply_hit_mods(enemy, bullet)
                    if bullet.on_hit(enemy, self):
                        continue          # Durchschuss: weiter zum naechsten Ziel
                    hit = True
                    break
            # Minen abschiessen - die Gegenwehr gegen den Moerser
            if not hit and bombs:
                for bomb in bombs:
                    if not bomb.alive:
                        continue
                    if (bullet.pos - bomb.pos).length_squared() <= \
                            (bomb.radius + bullet.radius) ** 2:
                        bomb.hp -= bullet.damage
                        self.stats["hits"] += 1
                        self.effects.spark(bullet.pos, bomb.color, 5, 140, 0.22, 2)
                        if bomb.hp <= 0:
                            self.detonate_bomb(bomb, harmless=True)
                        hit = True
                        break
            if not hit and self.boss is not None and not self.boss.dying:
                if (bullet.pos - self.boss.pos).length_squared() <= \
                        (self.boss.radius * 0.92 + bullet.radius) ** 2:
                    self.boss.damage(bullet.damage, self)
                    self.effects.spark(bullet.pos, bullet.color, 5, 150, 0.22, 2)
                    self.stats["hits"] += 1
                    if bullet.pierce > 0:
                        bullet.pierce -= 1
                    else:
                        hit = True
            if hit:
                bullet.alive = False

        self.bullets = [b for b in self.bullets if b.alive]

        if player is None or not player.alive:
            return

        # Gegnerprojektile -> Spieler
        for bullet in self.enemy_bullets:
            if not bullet.alive:
                continue
            # Minen zuenden schon in der Naehe, nicht erst bei Beruehrung
            reach = player.radius + bullet.radius + (18 if bullet.blast > 0 else 0)
            if (bullet.pos - player.pos).length_squared() <= reach ** 2:
                if bullet.blast > 0:
                    if self.detonate_bomb(bullet):
                        return
                    continue
                bullet.alive = False
                self.effects.explosion(bullet.pos, bullet.color, size=0.55, count=10)
                if player.take_damage(bullet.damage, self, bullet.source,
                                      bullet.source_mut):
                    return
        self.enemy_bullets = [b for b in self.enemy_bullets if b.alive]

        # Rammen / Kollisionsschaden
        for enemy in self.enemies:
            if not enemy.alive:
                continue
            if (enemy.pos - player.pos).length_squared() <= \
                    (enemy.radius + player.radius) ** 2:
                enemy.alive = False
                enemy.on_death(self)
                impact = enemy.contact_damage * dmg_scale(self.level) * self.enemy_dmg
                if "ram" in player.systems:
                    impact /= 3.0                # Rammsporn (Dreadnought II)
                    self.effects.spark(enemy.pos, ORANGE, 14, 220, 0.35, 4)
                if player.take_damage(impact, self, enemy.kind, enemy.mutations):
                    return
        self.enemies = [e for e in self.enemies if e.alive]

        if self.boss is not None and not self.boss.dying and not self.boss.entering:
            if (self.boss.pos - player.pos).length_squared() <= \
                    (self.boss.radius * 0.85 + player.radius) ** 2:
                if player.take_damage(self.boss.contact_damage * self.enemy_dmg,
                                      self, "boss"):
                    return

        # Aufsammeln
        for pickup in self.pickups:
            if not pickup.alive:
                continue
            if (pickup.pos - player.pos).length_squared() <= \
                    (player.radius + pickup.radius + 4) ** 2:
                pickup.alive = False
                self.collect(pickup)
        self.pickups = [p for p in self.pickups if p.alive]

    def detonate_bomb(self, bomb, harmless=False):
        """Mine zuenden. `harmless` = abgeschossen, dann gibt es nur Funken.
        Liefert True, wenn der Spieler dabei gestorben ist."""
        bomb.alive = False
        self.effects.explosion(bomb.pos, bomb.color, size=2.0, count=44)
        self.effects.ring(bomb.pos, mix_color(bomb.color, WHITE, 0.4),
                          bomb.blast, 0.4, 3)
        self.shake(8 if harmless else 18)
        if harmless:
            self.score += 120
            self.effects.text(bomb.pos, "MINE ENTSCHAERFT", self.player.ship["laser"]
                              if self.player else CYAN, 22)
            return False
        player = self.player
        if player is None or not player.alive:
            return False
        # Voller Schaden im Zentrum, am Rand des Sprengradius nur ein Drittel
        dist = (player.pos - bomb.pos).length()
        falloff = clamp(1.0 - dist / max(1.0, bomb.blast), 0.0, 1.0)
        amount = bomb.damage * lerp(0.34, 1.0, falloff)
        return player.take_damage(amount, self, bomb.source, bomb.source_mut)

    def apply_hit_mods(self, enemy, bullet):
        """Kettenblitz, Dornenfeld und Gnadenstoss nach einem Treffer."""
        if not self.mod_flags:
            return
        if "chain" in self.mod_flags:
            best, dist = None, 190.0 ** 2
            for other in self.enemies:
                if other is enemy or not other.alive:
                    continue
                d = (other.pos - enemy.pos).length_squared()
                if d < dist:
                    best, dist = other, d
            if best is not None:
                # Frueher wurde hier direkt auf self.world gezeichnet - das
                # wurde im selben Frame vom Sternenfeld ueberschrieben und war
                # deshalb nie zu sehen.
                self.effects.beam(enemy.pos, best.pos, CYAN, 0.22, 3)
                self.effects.spark(best.pos, CYAN, 6, 150, 0.25, 3)
                best.damage(bullet.damage * 0.5, self)
        if "thorns" in self.mod_flags:
            for other in self.enemies:
                if other is enemy or not other.alive:
                    continue
                if (other.pos - enemy.pos).length_squared() <= 95 ** 2:
                    other.damage(bullet.damage * 0.28, self)
        if "execute" in self.mod_flags and enemy.alive:
            if enemy.hp <= enemy.max_hp * 0.12:
                self.effects.text(enemy.pos, "GNADENSTOSS", RED, 22)
                enemy.alive = False
                enemy.on_death(self)

    def collect(self, pickup):
        if pickup.kind == Pickup.KIND_COIN:
            pickup.value = max(1, int(round(pickup.value * self.loot_mult)))
            self.save["coins"] += pickup.value
            self.stats["coins"] += pickup.value
            self.wave_stats["coins"] += pickup.value
            self.score += pickup.value * 5
            self.effects.spark(pickup.pos, GOLD, 6, 120, 0.3, 2)
        elif pickup.kind == Pickup.KIND_CRYSTAL:
            self.save["crystals"] += pickup.value
            self.stats["crystals"] += pickup.value
            self.wave_stats["crystals"] += pickup.value
            self.score += 250
            self.effects.text(pickup.pos, "+%d KRISTALL" % pickup.value, CRYSTAL, 24)
            self.effects.spark(pickup.pos, CRYSTAL, 12, 170, 0.4, 3)
        elif pickup.kind == Pickup.KIND_CRATE:
            self.open_crate(pickup.pos)
        else:
            if self.player is not None:
                amount = self.player.max_hp * (0.20 + 0.05 * pickup.value)
                missing = self.player.max_hp - self.player.hp
                self.player.heal(amount)
                if missing < 1.0:
                    # Bei voller Huelle wird das Herz zu Punkten und Schild
                    self.player.shield = min(self.player.max_shield,
                                             self.player.shield + self.player.max_shield * 0.35)
                    self.score += 400
                    self.effects.text(pickup.pos, "+SCHILD", CYAN, 24)
                else:
                    self.effects.text(pickup.pos, "+%d HUELLE" % int(min(amount, missing)),
                                      RED, 26)
                self.effects.spark(pickup.pos, RED, 12, 170, 0.4, 3)

    def open_crate(self, pos):
        """Frachtkiste oeffnen: der Anbau wird ausgewuerfelt, nicht gewaehlt."""
        self.stats["crates"] += 1
        self.effects.explosion(pos, GOLD, size=1.3, count=26)
        self.shake(8)
        if self.player is None:
            return
        key = roll_addon(self.player.addons)
        if key is None:
            # Alles montiert - die Kiste zahlt in Muenzen aus
            coins = int(round(CRATE_COIN_FALLBACK * self.loot_mult))
            self.save["coins"] += coins
            self.stats["coins"] += coins
            self.wave_stats["coins"] += coins
            self.effects.text(pos, "+%d MUENZEN" % coins, GOLD, 28)
            self.notify("Frachtkiste: alle Anbauten montiert, %d Muenzen." % coins)
            return
        addon = ADDON_BY_KEY[key]
        self.player.add_addon(key)
        level = self.player.addons[key]
        self.effects.text(pos, addon["name"].upper(), addon["color"], 30)
        self.effects.ring(pos, addon["color"], 90, 0.45, 3)
        self.notify("Frachtkiste: %s x%d - %s"
                    % (addon["name"], level, addon["desc"]))
        self.refresh_power()

    # --------------------------------------------------------------- Belohnung
    def on_enemy_killed(self, enemy):
        self.stats["kills"] += 1
        self.wave_stats["kills"] += 1
        self.kill_streak += 1
        player = self.player

        # Zeitbombe: der Abschuss detoniert
        if "explode" in self.mod_flags and player is not None:
            radius = 105.0
            self.effects.explosion(enemy.pos, ORANGE, size=1.1, count=18)
            for other in self.enemies:
                if other is enemy or not other.alive:
                    continue
                if (other.pos - enemy.pos).length_squared() <= radius ** 2:
                    other.damage(player.damage * 0.7, self)

        # Vampirkern
        if ("lifesteal" in self.mod_flags and player is not None
                and self.kill_streak % 12 == 0):
            player.heal(player.max_hp * 0.04)
            self.effects.text(player.pos, "+HUELLE", GREEN, 20)

        # Kettenreaktion (Vanguard III): der Abschuss reisst Nachbarn mit
        if player is not None and "chain" in player.systems:
            radius = 120.0
            splash = player.damage * 0.55
            self.effects.waves.append(Shockwave(enemy.pos, radius, 0.35, LIME, 2))
            for other in self.enemies:
                if other is enemy or not other.alive:
                    continue
                if (other.pos - enemy.pos).length_squared() <= radius ** 2:
                    other.damage(splash, self)

        # Truemmerfeld: zerstoerte Gegner hinterlassen kurz gefaehrliche Splitter
        if self.hardship("debris"):
            for i in range(4):
                ang = math.tau * i / 4 + random.uniform(-0.4, 0.4)
                direction = Vector2(math.cos(ang), math.sin(ang))
                self.enemy_bullets.append(EnemyBullet(
                    enemy.pos + direction * 6, direction * 95,
                    7.0 * dmg_scale(self.level) * self.enemy_dmg,
                    (170, 150, 140), 6, "orb", life=1.6, source="truemmer"))

        self.save["total_kills"] = self.save.get("total_kills", 0) + 1
        self.score += int(enemy.score * (1.0 + 0.08 * (self.level - 1))
                          * getattr(enemy, "loot_mult", 1.0))
        self.spawn_drops(enemy.pos, enemy.coin_value * getattr(enemy, "loot_mult", 1.0),
                         enemy.crystal_chance)

    def on_boss_killed(self, boss):
        self.score += boss.score
        self.stats["kills"] += 1
        self.wave_stats["kills"] += 1
        if self.wave_stats.get("boss_start") is not None:
            self.wave_stats["boss_ttk"] = self.stats["time"] - self.wave_stats["boss_start"]
        self.spawn_drops(boss.pos, boss.coin_value, 0.0, coin_chunks=14,
                         crystals=boss.crystals, hearts=3)
        # Ein Boss laesst immer eine Frachtkiste zurueck - WAS drin ist,
        # bleibt trotzdem dem Zufall ueberlassen.
        self.pickups.append(Pickup(boss.pos, Pickup.KIND_CRATE, 1))
        self.effects.text(boss.pos, "BOSS BESIEGT!", YELLOW, 44)
        self.boss = None

    def spawn_drops(self, pos, coin_value, crystal_chance, coin_chunks=0, crystals=0,
                    hearts=0):
        total = int(round(coin_value * reward_scale(self.level)))
        chunks = coin_chunks if coin_chunks else max(1, min(6, total // 3 + 1))
        per = max(1, total // chunks)
        left = total
        for _ in range(chunks):
            value = min(per, left)
            left -= value
            if value <= 0:
                break
            self.pickups.append(Pickup(pos, Pickup.KIND_COIN, value))
        if left > 0:
            self.pickups.append(Pickup(pos, Pickup.KIND_COIN, left))
        for _ in range(crystals):
            self.pickups.append(Pickup(pos, Pickup.KIND_CRYSTAL, 1))
        if crystal_chance > 0 and random.random() < crystal_chance:
            self.pickups.append(Pickup(pos, Pickup.KIND_CRYSTAL, 1))
        if self.hardship("nohearts"):
            hearts = 0                            # Funkstille

        for _ in range(hearts):
            self.pickups.append(Pickup(pos, Pickup.KIND_HEART, 2))
        # Herzen fallen haeufiger, je schwerer das Schiff beschaedigt ist -
        # das faengt Pechstraehnen ab, ohne den Kampf zu entwerten.
        if (self.player is not None and self.player.alive and not hearts
                and not self.hardship("nohearts")):
            missing = 1.0 - self.player.hp / max(1.0, self.player.max_hp)
            chance = 0.012 + 0.075 * missing ** 2
            if "hearts" in self.mod_flags:
                chance *= 3.0
            if random.random() < chance:
                self.pickups.append(Pickup(pos, Pickup.KIND_HEART, 1))

        # Frachtkiste - selten und ausdruecklich nicht garantiert
        if self.player is not None and random.random() < CRATE_DROP_CHANCE:
            self.pickups.append(Pickup(pos, Pickup.KIND_CRATE, 1))

    # ------------------------------------------------------------- Rundenende
    def finish_gameover(self):
        self.state = "gameover"
        self.menu_index = 0
        self.log_wave(cleared=False)
        killer, mut = self.last_killer or ("unbekannt", ())
        if self.db is not None:
            self.db.log_death(self.level, killer, mut, self.power, self.stats["time"])
        self.record_run("niederlage")
        self.save["highscore"] = max(self.save.get("highscore", 0), self.score)
        self.save["best_level"] = max(self.save.get("best_level", 0), self.level)
        self.save["waves_total"] = self.save.get("waves_total", 0) + max(0, self.level - 1)
        write_save(self.save)

    def finish_victory(self):
        self.state = "victory"
        self.menu_index = 0
        if self.tier > self.save.get("tier_cleared", TIER_FREE):
            self.save["tier_cleared"] = self.tier
            if self.tier < TIER_MAX:
                self.notify("%s bezwungen - %s ist jetzt waehlbar!"
                            % (self.tier_cfg()["name"],
                               tier_cfg(self.tier + 1)["name"]))
            else:
                self.notify("%s bezwungen - hoeher geht es nicht!"
                            % self.tier_cfg()["name"])
        self.score += 25000
        self.stats["waves"] = CAMPAIGN_LEVELS
        self.record_run("sieg")
        self.save["highscore"] = max(self.save.get("highscore", 0), self.score)
        self.save["best_level"] = max(self.save.get("best_level", 0), CAMPAIGN_LEVELS)
        write_save(self.save)

    def record_run(self, outcome):
        if self.db is None:
            return
        key = self.player.ship_key if self.player else self.save["ship"]
        self.db.finish_run(outcome, self.stats, self.score, self.level, self.endless,
                           self.power,
                           player_dps(self.save["upgrades"], SHIPS[key],
                                      progression_mult(self.save, key)),
                           self.save["upgrades"])

    def action_continue_endless(self):
        """Nach dem Kampagnensieg im selben Run weiterfliegen."""
        self.endless = True
        self.start_level(CAMPAIGN_LEVELS + 1)
        self.state = "playing"
        self.banner("ENDLOSMODUS", "Ab hier wird es nie wieder leichter")

    # =========================================================================
    #  RENDERING
    # =========================================================================
    def draw(self):
        world = self.world
        self.starfield.draw(world)

        if self.state in ("playing", "paused", "shop", "draft",
                          "gameover", "victory") \
                and self.player is not None and self.state != "menu":
            self.draw_world(world)

        offset = (0, 0)
        if self.shake_amount > 0.1:
            offset = (random.uniform(-1, 1) * self.shake_amount,
                      random.uniform(-1, 1) * self.shake_amount)
        self.screen.blit(world, offset)

        if self.state in ("playing", "paused"):
            self.draw_hud(self.screen)
            self.effects.draw_texts(self.screen)
            self.draw_banner(self.screen)

        if self.state == "menu":
            self.draw_menu(self.screen)
        elif self.state == "draft":
            self.draw_draft(self.screen)
        elif self.state == "werft":
            self.draw_werft(self.screen)
        elif self.state == "shop":
            self.draw_shop(self.screen)
        elif self.state == "paused":
            self.draw_pause(self.screen)
        elif self.state == "gameover":
            self.draw_gameover(self.screen)
        elif self.state == "victory":
            self.draw_victory(self.screen)

        if self.message_timer > 0:
            alpha = int(255 * clamp(self.message_timer / 0.6, 0, 1))
            draw_text(self.screen, self.message, 26, WIDTH // 2, HEIGHT - 34,
                      YELLOW, anchor="center", glow=ORANGE, alpha=alpha)

        pygame.display.flip()

    def draw_world(self, surface):
        for pickup in self.pickups:
            pickup.draw(surface)
        for enemy in self.enemies:
            enemy.draw(surface)
            enemy.draw_mutations(surface)
            enemy.draw_hp(surface)
        if self.boss is not None:
            self.boss.draw(surface)
        for bullet in self.enemy_bullets:
            bullet.draw(surface)
        if self.player is not None:
            self.player.draw(surface)
        for bullet in self.bullets:
            bullet.draw(surface)
        self.effects.draw(surface)

    # ------------------------------------------------------------------- HUD
    def draw_hud(self, surface):
        player = self.player
        bar = pygame.Surface((WIDTH, HUD_HEIGHT), pygame.SRCALPHA)
        pygame.draw.rect(bar, (8, 10, 22, 205), (0, 0, WIDTH, HUD_HEIGHT))
        pygame.draw.line(bar, (60, 90, 150), (0, HUD_HEIGHT - 1), (WIDTH, HUD_HEIGHT - 1), 2)
        surface.blit(bar, (0, 0))

        # --- Links: Schiff, Huelle, Schild
        ship = SHIPS[player.ship_key]
        ship["draw"](surface, 40, HUD_HEIGHT // 2, 0.62, self.time, 0.5)
        draw_text(surface, ship["name"], 20, 74, 14, mix_color(ship["accent"], WHITE, 0.4))
        draw_bar(surface, 74, 30, 250, 16, player.hp / max(1, player.max_hp),
                 GREEN if player.hp > player.max_hp * 0.35 else RED)
        draw_text(surface, "%d / %d" % (int(player.hp), int(player.max_hp)), 18,
                  199, 38, WHITE, anchor="center")
        if player.max_shield > 0:
            draw_bar(surface, 74, 50, 250, 9, player.shield / max(1, player.max_shield),
                     CYAN, back=(14, 26, 44))

        # --- Mitte: Welle + Fortschritt
        total = max(1, len(self.wave_events))
        remaining = len(self.enemies) + (len(self.wave_events) - self.spawn_idx)
        progress = 1.0 - clamp(remaining / total, 0.0, 1.0)
        cx = WIDTH // 2
        if self.endless:
            label = "ENDLOS - WELLE %d" % self.level
        else:
            label = "WELLE %d / %d" % (self.level, CAMPAIGN_LEVELS)
        draw_text(surface, label, 30, cx, 12, WHITE, anchor="center", bold=True,
                  glow=MAGENTA if is_boss_level(self.level) else CYAN)
        draw_bar(surface, cx - 130, 34, 260, 12, progress,
                 MAGENTA if is_boss_level(self.level) else CYAN)
        info = "Gegner: %d" % remaining if not self.wave_cleared else "GESCHAFFT"
        if self.boss is not None:
            info = "BOSS AKTIV"
        draw_text(surface, info, 18, cx - 130, 54, GREY, anchor="midleft")
        draw_text(surface, self.biome["name"], 18, cx + 130, 54,
                  mix_color(CYAN, WHITE, 0.35), anchor="midright")

        # --- Rechts: Score & Waehrungen
        draw_text(surface, "SCORE", 18, WIDTH - 20, 12, GREY, anchor="topright")
        draw_text(surface, "{:,}".format(int(self.score)).replace(",", "."), 30,
                  WIDTH - 20, 26, WHITE, anchor="topright", bold=True, glow=CYAN)
        draw_currency_row(surface, WIDTH - 230, 58, self.save["coins"],
                          self.save["crystals"], 22)

        # --- Multishot, Bedrohungsgrad und mitgefuehrte Ausruestung
        ms = self.save["upgrades"]["multishot"]
        draw_text(surface, MULTISHOT_NAMES[ms], 18, 360, 12, ship["laser"],
                  anchor="midleft")
        draw_level_pips(surface, 360, 22, ms, 4, ship["laser"], 8, 3)
        if self.mods:
            draw_text(surface, "MODS %d" % len(self.mods), 17, 360, 46,
                      mix_color(CYAN, WHITE, 0.3), anchor="midleft")
            for i, key in enumerate(self.mods[-12:]):
                col = MOD_RARITY_COLOR[MOD_BY_KEY[key]["rare"]]
                pygame.draw.circle(surface, col, (425 + i * 11, 46), 4)
        # Anbauten aus Frachtkisten - als eigene Reihe mit Stapelzahl
        if self.player is not None and any(self.player.addons.values()):
            total = sum(self.player.addons.values())
            draw_text(surface, "ANBAU %d" % total, 17, 360, 64,
                      mix_color(GOLD, WHITE, 0.3), anchor="midleft")
            slot = 0
            for addon in ADDONS:
                count = self.player.addons[addon["key"]]
                if not count:
                    continue
                px = 430 + slot * 26
                pygame.draw.rect(surface, addon["color"],
                                 (px - 5, 60, 10, 10), 0, border_radius=2)
                draw_text(surface, "%d" % count, 15, px + 8, 64,
                          mix_color(addon["color"], WHITE, 0.5), anchor="midleft")
                slot += 1
        badge_x = WIDTH - 250
        cfg = self.tier_cfg()
        label = "%s  |  BEDROHUNG x%.1f" % (cfg["name"].upper(), self.threat)
        draw_text(surface, label, 17, badge_x, 58,
                  mix_color(cfg["color"], WHITE, 0.35), anchor="midright")
        if self.revives > 0:
            draw_text(surface, "RETTUNG x%d" % self.revives, 18, badge_x, 16,
                      GREEN, anchor="midright", bold=True)
        if self.player is not None and self.player.damage_mult > 1.0:
            pulse = 0.6 + 0.4 * math.sin(self.time * 8)
            draw_text(surface, "OVERDRIVE", 18, badge_x, 34,
                      mix_color(ORANGE, WHITE, pulse), anchor="midright", bold=True)

        if self.boss is not None:
            self.boss.draw_hud(surface)

    def draw_banner(self, surface):
        if self.banner_timer <= 0:
            return
        t = self.banner_timer / 2.6
        alpha = int(255 * clamp(t * 2.2, 0, 1))
        y = 250
        col = MAGENTA if "BOSS" in self.banner_sub or is_boss_level(self.level) else CYAN
        draw_text(surface, self.banner_text, 76, WIDTH // 2, y, WHITE, anchor="center",
                  bold=True, glow=col, alpha=alpha)
        if self.banner_sub:
            draw_text(surface, self.banner_sub, 30, WIDTH // 2, y + 48,
                      mix_color(col, WHITE, 0.4), anchor="center", alpha=alpha)

    # ---------------------------------------------------------------- Menues
    def draw_title(self, surface, y=120):
        pulse = 0.5 + 0.5 * math.sin(self.time * 2)
        draw_text(surface, "GALAXY ATTACK", 96, WIDTH // 2, y, WHITE, anchor="center",
                  bold=True, glow=mix_color(CYAN, MAGENTA, pulse))
        draw_text(surface, "N E O N   V E C T O R   E D I T I O N", 26, WIDTH // 2,
                  y + 56, mix_color(CYAN, WHITE, 0.3), anchor="center")
        draw_text(surface, "Version %s" % VERSION, 19, WIDTH // 2, y + 82,
                  GREY, anchor="center")

    def draw_menu(self, surface):
        self.draw_title(surface, 120)
        items = self.menu_items()
        rects = self.menu_rects()
        cfg = self.tier_cfg()
        for i, (label, action) in enumerate(items):
            sub = None
            color = CYAN
            if action == self.cycle_tier:
                color = cfg["color"]
                sub = "%s   (Beute %+d %%)" % (cfg["desc"],
                                               round((cfg["reward"] - 1) * 100))
            elif action == self.action_werft:
                color = PURPLE
                sub = "Schiffsraenge und Refit"
            draw_button(surface, rects[i], label, i == self.menu_index, self.time,
                        sub=sub, color=color)

        # Schiffsvorschau
        ship = SHIPS[self.save["ship"]]
        px = WIDTH - 190
        py = HEIGHT - 190
        drift = math.sin(self.time * 1.6) * 14
        ship["draw"](surface, px + drift, py, 2.1, self.time, 0.8)
        draw_text(surface, ship["name"], 26, px, py + 84, ship["accent"], anchor="center",
                  bold=True)
        draw_text(surface, ship["tag"], 19, px, py + 106, GREY, anchor="center")

        # Statistikleiste
        info = pygame.Rect(38, 268, 288, 190)
        panel(surface, info)
        draw_text(surface, "PILOTENAKTE", 22, info.x + 20, info.y + 14, CYAN, bold=True)
        draw_text(surface, "Highscore: %d" % self.save.get("highscore", 0), 21,
                  info.x + 20, info.y + 44, WHITE)
        best = self.save.get("best_level", 0)
        best_txt = ("%d (Endlos)" % best) if best > CAMPAIGN_LEVELS \
            else "%d / %d" % (best, CAMPAIGN_LEVELS)
        draw_text(surface, "Beste Welle: %s" % best_txt, 21, info.x + 20,
                  info.y + 68, WHITE)
        draw_text(surface, "Abschuesse: %d" % self.save.get("total_kills", 0),
                  21, info.x + 20, info.y + 92, WHITE)
        draw_text(surface, "Refit-Stufe: %d" % self.save.get("refit", 0), 21,
                  info.x + 20, info.y + 116, mix_color(PURPLE, WHITE, 0.4))
        cleared = int(clamp(_as_int(self.save.get("tier_cleared"), TIER_FREE),
                            0, TIER_MAX))
        draw_text(surface, "Hoechste Stufe: %s" % tier_cfg(cleared)["name"], 21,
                  info.x + 20, info.y + 140,
                  mix_color(tier_cfg(cleared)["color"], WHITE, 0.4))
        draw_currency_row(surface, info.x + 20, info.y + 174, self.save["coins"],
                          self.save["crystals"], 23)

        draw_text(surface, "Pfeiltasten = Fliegen   |   Leertaste = Feuern   |   "
                           "ESC = Pause   |   F11 = Vollbild",
                  20, WIDTH // 2, HEIGHT - 16, GREY, anchor="center")

    # ------------------------------------------------------------------ Shop
    # ---------------------------------------------------------- Shop-Layout
    SHOP_COLUMNS = ([0, 1, 2, 3, 4], [5, 6, 7, 8], [9])

    def shop_rects(self):
        """Links Upgrades, rechts Verbrauchsgueter, unten der Weiter-Knopf."""
        rects = []
        top = 196
        for i in range(len(UPGRADE_ORDER)):
            rects.append(pygame.Rect(64, top + i * 66, 476, 58))
        for i in range(len(CONSUMABLE_ORDER)):
            rects.append(pygame.Rect(566, top + i * 66, 450, 58))
        rects.append(pygame.Rect(WIDTH // 2 - 190, top + 5 * 66 + 14, 380, 50))
        return rects

    def shop_move(self, dx, dy):
        """Navigation ueber zwei Spalten hinweg."""
        cols = self.SHOP_COLUMNS
        col = next(i for i, c in enumerate(cols) if self.shop_index in c)
        row = cols[col].index(self.shop_index)
        if dy:
            row = (row + dy) % len(cols[col])
            self.shop_index = cols[col][row]
        elif dx:
            ncol = (col + dx) % len(cols)
            target = cols[ncol]
            self.shop_index = target[min(row, len(target) - 1)]

    def shop_activate(self, index):
        if index < len(UPGRADE_ORDER):
            self.try_buy(UPGRADE_ORDER[index])
        elif index < len(UPGRADE_ORDER) + len(CONSUMABLE_ORDER):
            self.try_buy_consumable(CONSUMABLE_ORDER[index - len(UPGRADE_ORDER)])
        else:
            self.leave_shop()

    # ------------------------------------------------------- Verbrauchsgueter
    def consumable_state(self, key):
        """(verfuegbar, Hinweistext) fuer ein Verbrauchsgut."""
        cfg = CONSUMABLES[key]
        bought = self.consum_bought.get(key, 0)
        if cfg["stock"] and bought >= cfg["stock"]:
            return False, "AUSVERKAUFT"
        if key == "repair" and self.player is not None:
            if self.player.hp >= self.player.max_hp - 1:
                return False, "HUELLE VOLL"
        if key == "overdrive" and self.overdrive_waves > 0:
            return False, "AKTIV"
        if key == "revive":
            return True, "%d bereit" % self.revives
        if key == "shieldcell":
            return True, "Schild x%.1f" % (self.player.shield_bonus if self.player else 1.0)
        return True, ""

    def try_buy_consumable(self, key):
        cfg = CONSUMABLES[key]
        available, hint = self.consumable_state(key)
        if not available:
            self.notify("%s: %s" % (cfg["name"], hint or "nicht verfuegbar"))
            return
        bought = self.consum_bought.get(key, 0)
        cost = consumable_cost(key, self.level, bought)
        if self.save["coins"] < cost:
            self.notify("Nicht genug Muenzen! (%d benoetigt)" % cost)
            return
        self.save["coins"] -= cost
        self.consum_bought[key] = bought + 1
        player = self.player

        if key == "repair" and player is not None:
            player.heal(player.max_hp * 0.55)
            self.notify("Huelle reparariert: %d / %d" % (int(player.hp), int(player.max_hp)))
        elif key == "shieldcell" and player is not None:
            player.shield_bonus += 0.40
            player.apply_shield_bonus(refill=True)
            self.notify("Schildkapazitaet auf %.0f erhoeht." % player.max_shield)
        elif key == "overdrive":
            self.overdrive_waves = 1
            self.notify("Overdrive geladen: +30 % Schaden in der naechsten Welle.")
        elif key == "revive":
            self.revives += 1
            self.notify("Notfall-Rettung an Bord: %d" % self.revives)

        if self.db is not None:
            self.db.log_purchase(self.level, key, "verbrauch", cost, "coins",
                                 self.consum_bought[key])
        write_save(self.save)

    # ----------------------------------------------------------------- Shop
    def draw_shop(self, surface):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((4, 6, 16, 232))
        surface.blit(overlay, (0, 0))

        if self.shop_context == "wave":
            title = "WELLE %d GESCHAFFT" % self.level
            sub = "Ruestkammer - naechste Welle: %d" % (self.level + 1)
        else:
            title = "UPGRADE SHOP"
            sub = "Investiere Muenzen und Kristalle in dein Schiff"
        draw_text(surface, title, 56, WIDTH // 2, 40, WHITE, anchor="center", bold=True,
                  glow=GOLD)
        draw_text(surface, sub, 22, WIDTH // 2, 88, GREY, anchor="center")
        draw_currency_row(surface, WIDTH // 2 - 110, 122, self.save["coins"],
                          self.save["crystals"], 28)

        draw_text(surface, "SCHIFFS-UPGRADES", 20, 64, 172, CYAN, bold=True)
        draw_text(surface, "AUSRUESTUNG FUER DIESEN RUN", 20, 566, 172, GOLD, bold=True)

        rects = self.shop_rects()

        # ------------------------------------------------------- Upgrades
        for i, key in enumerate(UPGRADE_ORDER):
            cfg = UPGRADES[key]
            level = self.save["upgrades"][key]
            cost = upgrade_cost(key, level)
            selected = (self.shop_index == i)
            maxed = cost is None
            currency = cfg["currency"]
            affordable = (not maxed) and self.save[currency] >= cost
            color = GOLD if currency == "coins" else CRYSTAL
            rect = rects[i]
            if selected:
                panel(surface, rect, fill=scale_color(color, 0.14), border=color)
            else:
                panel(surface, rect, fill=(12, 14, 26), border=(56, 62, 90), alpha=200)

            draw_text(surface, cfg["name"], 25, rect.x + 14, rect.y + 12,
                      WHITE if not maxed else GREEN, bold=True)
            label = "Stufe %d/%d" % (level, cfg["max"])
            if key == "multishot":
                label = MULTISHOT_NAMES[level]
            draw_text(surface, label, 17, rect.x + 14, rect.y + 36, GREY)
            draw_text(surface, self.upgrade_preview(key, level), 17,
                      rect.x + 150, rect.y + 36, mix_color(color, WHITE, 0.4))
            draw_level_pips(surface, rect.x + 150, rect.y + 12,
                            level, min(cfg["max"], 20), color, size=6, gap=2)

            if maxed:
                draw_text(surface, "MAX", 26, rect.right - 16, rect.centery, GREEN,
                          anchor="midright", bold=True, glow=GREEN)
            else:
                col = color if affordable else (120, 80, 80)
                unit = "M" if currency == "coins" else "K"
                draw_text(surface, "%d %s" % (cost, unit), 26, rect.right - 16,
                          rect.centery, col, anchor="midright", bold=True,
                          glow=col if selected and affordable else None)

        # ------------------------------------------------ Verbrauchsgueter
        for j, key in enumerate(CONSUMABLE_ORDER):
            cfg = CONSUMABLES[key]
            idx = len(UPGRADE_ORDER) + j
            rect = rects[idx]
            selected = (self.shop_index == idx)
            available, hint = self.consumable_state(key)
            bought = self.consum_bought.get(key, 0)
            cost = consumable_cost(key, self.level, bought)
            affordable = available and self.save["coins"] >= cost
            color = GREEN if available else DARKGREY
            if selected:
                panel(surface, rect, fill=scale_color(color, 0.14), border=color)
            else:
                panel(surface, rect, fill=(12, 14, 26), border=(56, 62, 90), alpha=200)

            draw_text(surface, cfg["name"], 25, rect.x + 14, rect.y + 12,
                      WHITE if available else (120, 126, 148), bold=True)
            draw_text(surface, cfg["desc"], 16, rect.x + 14, rect.y + 36, GREY)
            if hint:
                draw_text(surface, hint, 16, rect.right - 16, rect.y + 36,
                          mix_color(color, WHITE, 0.4), anchor="topright")
            if available:
                col = GOLD if affordable else (120, 80, 80)
                draw_text(surface, "%d M" % cost, 25, rect.right - 16, rect.y + 14,
                          col, anchor="topright", bold=True,
                          glow=col if selected and affordable else None)
            else:
                draw_text(surface, "--", 25, rect.right - 16, rect.y + 14, DARKGREY,
                          anchor="topright", bold=True)

        # ---------------------------------------------------------- Weiter
        cont = rects[-1]
        if self.shop_context == "wave":
            label = "WELLE %d STARTEN" % (self.level + 1)
        elif self.shop_context == "pause":
            label = "ZURUECK INS GEFECHT"
        else:
            label = "ZURUECK"
        draw_button(surface, cont, label, self.shop_index == len(rects) - 1,
                    self.time, color=GREEN)

        if self.shop_context == "wave":
            nxt = self.level + 1
            info = "Naechste Welle: %s" % biome_for(nxt)["name"]
            if is_boss_level(nxt):
                info += "   |   BOSSKAMPF"
            info += "   |   Bedrohung x%.1f" % threat_hp(self.power)
            draw_text(surface, info, 19, WIDTH // 2, HEIGHT - 52, mix_color(CYAN, WHITE, 0.3),
                      anchor="center")
        draw_text(surface, "Pfeiltasten waehlen  |  ENTER kaufen  |  ESC weiter",
                  19, WIDTH // 2, HEIGHT - 26, GREY, anchor="center")

    def upgrade_preview(self, key, level):
        ship = SHIPS[self.save["ship"]]
        last = (level >= UPGRADES[key]["max"])
        if key == "damage":
            cur, nxt = stat_damage(level, ship), stat_damage(level + 1, ship)
            return "%.0f Schaden" % cur if last else "%.0f -> %.0f Schaden" % (cur, nxt)
        if key == "firerate":
            cur, nxt = stat_cooldown(level, ship), stat_cooldown(level + 1, ship)
            return "%.2f s Takt" % cur if last else "%.2f -> %.2f s" % (cur, nxt)
        if key == "maxhp":
            cur, nxt = stat_maxhp(level, ship), stat_maxhp(level + 1, ship)
            return "%d HP" % cur if last else "%d -> %d HP" % (cur, nxt)
        if key == "shieldmatrix":
            cur = stat_shield(level, ship, progression_mult(self.save,
                                                            self.save["ship"]))
            nxt = stat_shield(level + 1, ship, progression_mult(self.save,
                                                               self.save["ship"]))
            return "%.0f Schild" % cur if last else "%.0f -> %.0f Schild" % (cur, nxt)
        if key == "multishot":
            if level < UPGRADES[key]["max"]:
                return "%s -> %s" % (MULTISHOT_NAMES[level], MULTISHOT_NAMES[level + 1])
            return MULTISHOT_NAMES[level]
        return ""

    # ---------------------------------------------------------------- Hangar
    def werft_rects(self):
        return [pygame.Rect(74, 518, 240, 44),               # ausruesten
                pygame.Rect(326, 518, 242, 44),              # Rang
                pygame.Rect(600, 518, 406, 44),              # Refit
                pygame.Rect(WIDTH // 2 - 150, 572, 300, 40)] # zurueck

    def werft_activate(self, index):
        if index == 0:
            self.select_or_buy_ship()
        elif index == 1:
            self.try_buy_rank()
        elif index == 2:
            self.try_refit()
        else:
            self.state = "menu"
            self.persist()

    def draw_werft(self, surface):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((4, 6, 16, 234))
        surface.blit(overlay, (0, 0))
        draw_text(surface, "HANGAR", 50, WIDTH // 2, 18, WHITE, anchor="center",
                  bold=True, glow=CYAN)
        draw_currency_row(surface, WIDTH // 2 - 110, 64, self.save["coins"],
                          self.save["crystals"], 25)

        key = self.werft_ship_key()
        ship = SHIPS[key]
        unlocked = key in self.save["unlocked"]
        active = self.save["ship"] == key
        rank = self.save["ranks"].get(key, 0)
        rects = self.werft_rects()

        # ------------------------------------------------ linke Tafel: Raenge
        left = pygame.Rect(60, 96, 508, 408)
        panel(surface, left, border=ship["accent"] if unlocked else (70, 74, 96))
        ship["draw"](surface, left.x + 60, left.y + 58, 1.4, self.time, 0.5)
        draw_text(surface, ship["name"], 27, left.x + 116, left.y + 18,
                  ship["accent"] if unlocked else GREY, bold=True)
        draw_text(surface, ship["tag"], 18, left.x + 116, left.y + 44, GREY)
        status = "AUSGERUESTET" if active else ("verfuegbar" if unlocked
                                                else "%d Kristalle" % ship["price"])
        draw_text(surface, "Rang %d/%d   |   %s" % (rank, RANK_MAX, status), 20,
                  left.x + 116, left.y + 66,
                  GREEN if active else (WHITE if unlocked else CRYSTAL))
        draw_text(surface, "%d von %d Schiffen   -   Links/Rechts blaettert"
                  % (self.werft_ship + 1, len(SHIP_ORDER)), 17,
                  left.x + 116, left.y + 88, GREY)

        # Rangleiste
        track_y = left.y + 128
        node_w = (left.width - 60) / float(RANK_MAX)
        for i in range(1, RANK_MAX + 1):
            cx = int(left.x + 30 + node_w * (i - 0.5))
            done = i <= rank
            col = ship["accent"] if done else (58, 64, 88)
            if "system" in RANK_STEPS[i]:
                pts = [(cx, track_y - 11), (cx + 10, track_y), (cx, track_y + 11),
                       (cx - 10, track_y)]
                pygame.draw.polygon(surface, col if done else (40, 44, 64), pts)
                pygame.draw.polygon(surface, GOLD if done else (86, 74, 40), pts, 2)
            else:
                pygame.draw.circle(surface, col, (cx, track_y), 8)
                pygame.draw.circle(surface, scale_color(col, 1.4), (cx, track_y), 8, 1)
            if i < RANK_MAX:
                pygame.draw.line(surface, (48, 54, 76), (cx + 12, track_y),
                                 (int(cx + node_w - 12), track_y), 2)
            draw_text(surface, str(i), 15, cx, track_y + 20, GREY, anchor="center")

        # Systeme
        sys_y = track_y + 48
        draw_text(surface, "SYSTEME", 19, left.x + 22, sys_y, CYAN, bold=True)
        for idx, sysdef in enumerate(SHIP_SYSTEMS[key]):
            need = system_rank(idx)
            have = rank >= need
            box = pygame.Rect(left.x + 18, sys_y + 24 + idx * 56, left.width - 36, 50)
            panel(surface, box, fill=(16, 20, 34) if have else (12, 13, 22),
                  border=GOLD if have else (52, 56, 76), alpha=210, radius=6)
            draw_text(surface, sysdef["name"], 21, box.x + 13, box.y + 6,
                      GOLD if have else (112, 116, 138), bold=True)
            draw_text(surface, sysdef["desc"], 16, box.x + 13, box.y + 27,
                      GREY if have else (86, 90, 110))
            draw_text(surface, "AKTIV" if have else "Rang %d" % need, 17,
                      box.right - 12, box.centery, GREEN if have else (110, 114, 136),
                      anchor="midright", bold=True)

        # ----------------------------------------- rechte Tafel oben: Werte
        top = pygame.Rect(596, 96, 414, 168)
        panel(surface, top, border=(70, 90, 140))
        draw_text(surface, "WERTE", 19, top.x + 20, top.y + 12, CYAN, bold=True)
        prog = progression_mult(self.save, key)
        stats = [
            ("Huelle", ship["hp_mult"] * prog["hp"], 1.6, GREEN),
            ("Tempo", ship["speed_mult"] * prog["speed"], 1.6, CYAN),
            ("Feuerrate", ship["fire_mult"] * prog["fire"], 1.8, YELLOW),
            ("Schaden", ship["dmg_mult"] * prog["dmg"], 2.4, RED),
            ("Schild", ship["shield"] * prog["shield"] / 100.0, 1.2, CRYSTAL),
        ]
        for i, (label, value, span, col) in enumerate(stats):
            y = top.y + 42 + i * 24
            draw_text(surface, label, 18, top.x + 20, y - 1, GREY, anchor="midleft")
            draw_bar(surface, top.x + 116, y - 6, 210, 12,
                     clamp(value / span, 0.05, 1.0), col)
            draw_text(surface, "%.2f" % value, 17, top.right - 16, y, WHITE,
                      anchor="midright")

        # ---------------------------------------- rechte Tafel unten: Refit
        right = pygame.Rect(596, 276, 414, 228)
        panel(surface, right, border=PURPLE)
        level = self.save.get("refit", 0)
        draw_text(surface, "REFIT   Stufe %d" % level, 26, right.centerx, right.y + 10,
                  mix_color(PURPLE, WHITE, 0.5), anchor="center", bold=True, glow=PURPLE)
        rows = [
            ("Schaden", "+%d %%" % round(REFIT_DAMAGE_PER * level * 100)),
            ("Muenzfund", "+%d %%" % round(REFIT_COINS_PER * level * 100)),
            ("Notfall-Rettungen", "%d gratis" % refit_free_lives(level)),
            ("Kristallfund", "doppelt" if level >= REFIT_CRYSTAL_AT
             else "ab Stufe %d" % REFIT_CRYSTAL_AT),
        ]
        for i, (label, value) in enumerate(rows):
            y = right.y + 46 + i * 26
            draw_text(surface, label, 19, right.x + 20, y, GREY)
            draw_text(surface, value, 19, right.right - 20, y, WHITE,
                      anchor="topright", bold=True)
        ready = self.refit_ready()
        if ready:
            draw_text(surface, "Bereit: naechste Stufe gibt +%d %% Schaden."
                      % round(REFIT_DAMAGE_PER * (level + 1) * 100),
                      17, right.x + 20, right.y + 158, GREEN)
        else:
            offen = sum(UPGRADES[k]["max"] - self.save["upgrades"].get(k, 1)
                        for k in UPGRADE_ORDER)
            draw_text(surface, "Noch %d Upgrade-Stufen bis zum Refit." % offen,
                      17, right.x + 20, right.y + 158, (170, 140, 110))
        draw_text(surface, "Setzt die Kernaufwertungen zurueck.", 16,
                  right.x + 20, right.y + 182, GREY)

        # -------------------------------------------------------- Knoepfe
        if active:
            draw_button(surface, rects[0], "AUSGERUESTET", self.werft_index == 0,
                        self.time, enabled=False, color=GREEN)
        elif unlocked:
            draw_button(surface, rects[0], "AUSRUESTEN", self.werft_index == 0,
                        self.time, color=GREEN)
        else:
            afford = self.save["crystals"] >= ship["price"]
            draw_button(surface, rects[0], "%d KRISTALLE" % ship["price"],
                        self.werft_index == 0, self.time, enabled=afford,
                        color=CRYSTAL)

        coins, crystals = rank_cost(rank)
        if coins is None:
            draw_button(surface, rects[1], "RANG MAXIMAL", self.werft_index == 1,
                        self.time, enabled=False)
        else:
            cost = "%d M" % coins + (" +%d K" % crystals if crystals else "")
            step = RANK_STEPS[rank + 1]
            if "system" in step:
                gain = SHIP_SYSTEMS[key][step["system"]]["name"]
            else:
                names = {"dmg": "Schaden", "hp": "Huelle", "fire": "Feuerrate",
                         "speed": "Tempo", "shield": "Schild"}
                gain = ", ".join("+%d %% %s" % (round(v * 100), names[k])
                                 for k, v in step.items() if k in names)
            afford = (unlocked and self.save["coins"] >= coins
                      and self.save["crystals"] >= crystals)
            draw_button(surface, rects[1], "RANG %d  %s" % (rank + 1, cost),
                        self.werft_index == 1, self.time, enabled=afford,
                        sub=gain, color=GOLD)

        draw_button(surface, rects[2], "REFIT DURCHFUEHREN", self.werft_index == 2,
                    self.time, enabled=ready, color=PURPLE)
        draw_button(surface, rects[3], "ZURUECK", self.werft_index == 3, self.time,
                    color=GREEN)
        draw_text(surface, "Hoch/Runter waehlen  |  Links/Rechts Schiff  |  "
                           "ENTER bestaetigen  |  ESC zurueck",
                  18, WIDTH // 2, HEIGHT - 14, GREY, anchor="center")

    # ----------------------------------------------------------------- Pause
    def draw_pause(self, surface):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((4, 6, 16, 190))
        surface.blit(overlay, (0, 0))
        draw_text(surface, "PAUSE", 84, WIDTH // 2, 190, WHITE, anchor="center",
                  bold=True, glow=CYAN)
        items = self.pause_items()
        rects = button_rects(len(items), 320)
        for i, (label, _) in enumerate(items):
            draw_button(surface, rects[i], label, i == self.menu_index, self.time)
        draw_text(surface, "Welle %d  |  Score %d  |  Abschuesse %d"
                  % (self.level, self.score, self.stats["kills"]),
                  24, WIDTH // 2, HEIGHT - 90, GREY, anchor="center")
        if self.mods:
            draw_text(surface, "AKTIVE MODIFIKATIONEN", 20, WIDTH // 2, 480, CYAN,
                      anchor="center", bold=True)
            names = []
            for key in self.mods:
                mod = MOD_BY_KEY[key]
                names.append(mod["name"])
            line, lines = "", []
            for name in names:
                probe = (line + "  -  " + name) if line else name
                if font(19).size(probe)[0] > 820:
                    lines.append(line)
                    line = name
                else:
                    line = probe
            lines.append(line)
            for i, text in enumerate(lines[:4]):
                draw_text(surface, text, 19, WIDTH // 2, 506 + i * 22, GREY,
                          anchor="center")
        if self.player is not None and any(self.player.addons.values()):
            draw_text(surface, "ANBAUTEN AUS FRACHTKISTEN", 20, WIDTH // 2, 596,
                      GOLD, anchor="center", bold=True)
            parts = ["%s x%d" % (ADDON_BY_KEY[k]["name"], n)
                     for k, n in self.player.addons.items() if n]
            draw_text(surface, "   -   ".join(parts), 19, WIDTH // 2, 620,
                      GREY, anchor="center")

    # ------------------------------------------------------- Ende / Statistik
    def draw_stats_block(self, surface, top):
        accuracy = (self.stats["hits"] / self.stats["shots"] * 100.0) \
            if self.stats["shots"] else 0.0
        minutes, seconds = divmod(int(self.stats["time"]), 60)
        rows = [
            ("Punkte", "{:,}".format(int(self.score)).replace(",", ".")),
            ("Erreichte Welle", ("%d (Endlos)" % self.level) if self.endless
             else "%d / %d" % (self.level, CAMPAIGN_LEVELS)),
            ("Bedrohungsgrad", "x%.2f  (Machtindex %.1f)" % (self.threat, self.power)),
            ("Gefahrenstufe", "%s  (%d von %d)"
             % (self.tier_cfg()["name"], self.tier, TIER_MAX)),
            ("Refit / Rang", "Stufe %d  |  Rang %d"
             % (self.save.get("refit", 0),
                self.save.get("ranks", {}).get(
                    self.player.ship_key if self.player else self.save["ship"], 0))),
            ("Abschuesse", str(self.stats["kills"])),
            ("Treffergenauigkeit", "%.1f %%" % accuracy),
            ("Muenzen gesammelt", str(self.stats["coins"])),
            ("Kristalle gesammelt", str(self.stats["crystals"])),
            ("Flugzeit", "%d:%02d min" % (minutes, seconds)),
            ("Highscore", str(self.save.get("highscore", 0))),
        ]
        rect = pygame.Rect(WIDTH // 2 - 260, top, 520, len(rows) * 28 + 24)
        panel(surface, rect)
        for i, (label, value) in enumerate(rows):
            y = rect.y + 22 + i * 28
            draw_text(surface, label, 24, rect.x + 22, y, GREY, anchor="midleft")
            draw_text(surface, value, 24, rect.right - 22, y, WHITE, anchor="midright",
                      bold=True)

    def draw_gameover(self, surface):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((22, 2, 8, 205))
        surface.blit(overlay, (0, 0))
        pulse = 0.5 + 0.5 * math.sin(self.time * 3)
        draw_text(surface, "SCHIFF ZERSTOERT", 78, WIDTH // 2, 70, WHITE,
                  anchor="center", bold=True, glow=mix_color(RED, ORANGE, pulse))
        draw_text(surface, "Deine Muenzen und Kristalle bleiben erhalten - "
                           "ruest dich auf und flieg erneut!",
                  22, WIDTH // 2, 122, GREY, anchor="center")
        self.draw_stats_block(surface, 156)
        items = self.end_items()
        rects = button_rects(len(items), 520)
        for i, (label, _) in enumerate(items):
            draw_button(surface, rects[i], label, i == self.menu_index, self.time,
                        color=ORANGE)

    def draw_victory(self, surface):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((3, 14, 20, 205))
        surface.blit(overlay, (0, 0))
        pulse = 0.5 + 0.5 * math.sin(self.time * 3)
        draw_text(surface, "S I E G !", 92, WIDTH // 2, 62, WHITE, anchor="center",
                  bold=True, glow=mix_color(GOLD, CYAN, pulse))
        draw_text(surface, "Alle %d Wellen bezwungen. Weiterfliegen? Ab hier "
                           "erzeugt das Spiel endlos neue Wellen." % CAMPAIGN_LEVELS,
                  22, WIDTH // 2, 118, mix_color(GOLD, WHITE, 0.4), anchor="center")
        self.draw_stats_block(surface, 152)
        items = self.end_items()
        rects = button_rects(len(items), 520)
        for i, (label, _) in enumerate(items):
            draw_button(surface, rects[i], label, i == self.menu_index, self.time,
                        color=GOLD)
        # Konfetti
        if random.random() < 0.4:
            self.effects.add_particle(
                (random.uniform(0, WIDTH), -10),
                (random.uniform(-30, 30), random.uniform(60, 160)),
                random.uniform(1.5, 3.0),
                random.choice([GOLD, CYAN, MAGENTA, GREEN]),
                random.uniform(2, 4), drag=0.995)

    # =========================================================================
    #  HAUPTSCHLEIFE
    # =========================================================================
    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 0.05)                     # Schutz gegen Zeitspruenge
            self.handle_events()
            self.update(dt)
            self.draw()
        if self.db is not None:
            self.db.close()
        pygame.quit()


# ==============================================================================
#  BALANCE-AUSWERTUNG  (python space_shooter.py --stats)
# ==============================================================================

def print_stats_report(path=None):
    """Liest die Statistik-Datenbank und beantwortet die Frage, was zu stark
    oder zu schwach ist: Welche Welle bremst? Woran stirbt man? Wie lange
    dauern Bosse? Welche Upgrades kauft man zuerst?"""
    import sqlite3
    path = path or DB_PATH
    if not os.path.exists(path):
        print("Keine Statistik-Datenbank gefunden: %s" % path)
        print("Sie entsteht automatisch, sobald du eine Partie gespielt hast.")
        return 1
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    q = lambda sql, args=(): conn.execute(sql, args).fetchall()

    def line(char="-"):
        print(char * 78)

    runs = q("SELECT * FROM runs WHERE outcome != 'laufend'")
    line("=")
    print("  GALAXY ATTACK - BALANCE-REPORT")
    print("  %s" % path)
    line("=")
    if not runs:
        print("Noch keine abgeschlossene Partie aufgezeichnet.")
        conn.close()
        return 0

    # Verworfene Zeilen sichtbar machen - eine Statistik mit Loechern darf
    # nicht wie eine vollstaendige aussehen.
    incomplete = q("SELECT COUNT(*) AS n FROM runs WHERE outcome = 'laufend'")
    if incomplete and incomplete[0]["n"] > 0:
        print("Hinweis: %d Partie(n) ohne Abschluss (Absturz oder Abbruch)."
              % incomplete[0]["n"])

    total = len(runs)
    outcomes = {}
    for r in runs:
        outcomes[r["outcome"]] = outcomes.get(r["outcome"], 0) + 1
    waves = [r["max_wave"] for r in runs]
    print("Partien gesamt      : %d" % total)
    print("Ausgang             : %s"
          % ", ".join("%s %d" % (k, v) for k, v in sorted(outcomes.items())))
    print("Erreichte Welle     : Schnitt %.1f | Bestwert %d"
          % (sum(waves) / total, max(waves)))
    print("Spielzeit je Partie : Schnitt %.1f min"
          % (sum(r["duration"] for r in runs) / total / 60.0))
    print("Treffergenauigkeit  : Schnitt %.1f %%"
          % (100.0 * sum(r["accuracy"] for r in runs) / total))

    # ------------------------------------------------------------ Wellenhaerte
    line()
    print("WELLENHAERTE  (Abbruchquote und Schaden pro Welle)")
    line()
    print("%-6s %7s %9s %11s %10s %9s" %
          ("Welle", "Laeufe", "geschafft", "Schaden", "Dauer", "Mutant."))
    rows = q("""SELECT wave, COUNT(*) n, AVG(cleared) clear_rate,
                       AVG(damage_taken) dmg, AVG(duration) dur,
                       AVG(mutations) mut
                FROM waves GROUP BY wave ORDER BY wave""")
    for r in rows:
        flag = ""
        if r["clear_rate"] < 0.55 and r["n"] >= 3:
            flag = "  <-- Bremsklotz"
        print("%-6d %7d %8.0f %% %11.0f %9.1fs %9.1f%s"
              % (r["wave"], r["n"], 100 * r["clear_rate"], r["dmg"], r["dur"],
                 r["mut"], flag))

    # ---------------------------------------------------------- Todesursachen
    line()
    print("TODESURSACHEN")
    line()
    deaths = q("""SELECT killer, COUNT(*) n FROM deaths
                  GROUP BY killer ORDER BY n DESC""")
    dtotal = sum(d["n"] for d in deaths) or 1
    for d in deaths[:12]:
        share = 100.0 * d["n"] / dtotal
        bar = "#" * int(share / 3)
        flag = "  <-- zu stark?" if share > 40 else ""
        print("%-16s %4d  %5.1f %%  %s%s" % (d["killer"], d["n"], share, bar, flag))
    if not deaths:
        print("(keine)")

    # ------------------------------------------------------------------ Bosse
    line()
    print("BOSSKAEMPFE  (Zielfenster: 25 bis 60 Sekunden)")
    line()
    bosses = q("""SELECT wave, COUNT(*) n, AVG(boss_hp) hp, AVG(boss_ttk) ttk,
                         AVG(power) pw, AVG(cleared) win
                  FROM waves WHERE boss = 1 AND boss_ttk > 0
                  GROUP BY wave ORDER BY wave""")
    if bosses:
        print("%-6s %6s %10s %9s %9s %8s" %
              ("Welle", "Kaempfe", "HP", "Dauer", "Machtidx", "Siege"))
        for b in bosses:
            flag = ""
            if b["ttk"] < 18:
                flag = "  <-- zu schnell tot"
            elif b["ttk"] > 75:
                flag = "  <-- zaeh"
            print("%-6d %6d %10.0f %8.1fs %9.1f %7.0f %%%s"
                  % (b["wave"], b["n"], b["hp"], b["ttk"], b["pw"],
                     100 * b["win"], flag))
    else:
        print("(noch kein Boss besiegt)")

    # -------------------------------------------------------------- Upgrades
    line()
    print("KAUFVERHALTEN  (was wird zuerst und wie oft gekauft)")
    line()
    buys = q("""SELECT item, kind, COUNT(*) n, AVG(wave) avg_wave, SUM(cost) spent
                FROM purchases GROUP BY item ORDER BY n DESC""")
    for b in buys:
        print("%-14s %-10s %4d Kaeufe  ab Welle %4.1f im Schnitt  %8d ausgegeben"
              % (b["item"], b["kind"], b["n"], b["avg_wave"], b["spent"]))
    if not buys:
        print("(keine)")

    # ---------------------------------------------------- Staerke gegen Erfolg
    line()
    print("MACHTINDEX GEGEN ERFOLG  (zeigt, ob Upgrades zu stark durchschlagen)")
    line()
    buckets = {}
    for r in runs:
        key = int(clamp(r["power"], 1, 40) // 5) * 5
        buckets.setdefault(key, []).append(r["max_wave"])
    for key in sorted(buckets):
        vals = buckets[key]
        print("Machtindex %2d-%2d : %3d Partien, Welle im Schnitt %.1f"
              % (key, key + 5, len(vals), sum(vals) / len(vals)))

    ships = q("""SELECT ship, COUNT(*) n, AVG(max_wave) w, AVG(score) sc
                 FROM runs WHERE outcome != 'laufend' GROUP BY ship""")
    line()
    print("SCHIFFE")
    line()
    for sh in ships:
        print("%-14s %3d Partien  Welle %.1f  Punkte %.0f"
              % (sh["ship"], sh["n"], sh["w"], sh["sc"]))

    line("=")
    conn.close()
    return 0


def export_stats(db_path=None, out_path=None):
    """Schreibt die komplette Statistik als reine Textdatei.

    Gedacht zum Weiterschicken: eine .db ist eine Binaerdatei und laesst
    sich nicht ueberall anhaengen, eine .txt immer. Die Datei enthaelt
    erst den lesbaren Report und danach jede Tabelle vollstaendig als CSV,
    damit sich daraus alles nachrechnen laesst.

    Persoenliche Daten stehen nicht darin - die Datenbank kennt nur
    Spielwerte wie Welle, Schaden, Abschuesse und Kaeufe.
    """
    import sqlite3
    import io
    import contextlib

    db_path = db_path or DB_PATH
    out_path = out_path or os.path.join(SAVE_DIR, "galaxy_attack_export.txt")
    if not os.path.exists(db_path):
        print("Keine Statistik-Datenbank gefunden: %s" % db_path)
        print("Sie entsteht automatisch, sobald du eine Partie gespielt hast.")
        return 1

    report = io.StringIO()
    with contextlib.redirect_stdout(report):
        print_stats_report(db_path)

    conn = sqlite3.connect(db_path)
    try:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            if not r[0].startswith("sqlite_")]      # interne Tabellen weglassen
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write("Galaxy Attack %s - Statistikexport\n" % VERSION)
            fh.write("Datenbank: %s\n\n" % db_path)
            fh.write(report.getvalue())
            for table in tables:
                cur = conn.execute("SELECT * FROM %s" % table)
                columns = [d[0] for d in cur.description]
                rows = cur.fetchall()
                fh.write("\n\n" + "=" * 78 + "\n")
                fh.write("TABELLE %s  (%d Zeilen)\n" % (table.upper(), len(rows)))
                fh.write("=" * 78 + "\n")
                fh.write(";".join(columns) + "\n")
                for row in rows:
                    fh.write(";".join("" if v is None else str(v)
                                      for v in row) + "\n")
    finally:
        conn.close()

    size = os.path.getsize(out_path)
    print("Statistik exportiert nach:")
    print("  %s" % out_path)
    print("  (%.0f KB - diese Datei kannst du anhaengen und verschicken.)"
          % (size / 1024.0))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--help" in argv or "-h" in argv:
        print(__doc__)
        print("Optionen:")
        print("  --stats [datei]   Balance-Report aus der Statistik-Datenbank")
        print("  --export [datei]  Statistik als Textdatei zum Verschicken")
        print("  --help            diese Hilfe")
        return 0
    if "--stats" in argv:
        idx = argv.index("--stats")
        path = argv[idx + 1] if len(argv) > idx + 1 else None
        return print_stats_report(path)
    if "--export" in argv:
        idx = argv.index("--export")
        path = argv[idx + 1] if len(argv) > idx + 1 else None
        return export_stats(path)
    random.seed()
    game = Game()
    game.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
