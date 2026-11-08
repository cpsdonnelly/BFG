"""Fleet lists (core rules s.4 and each faction's "Fleet Composition").

A fleet list says which ships a fleet may take, at what cost, in what numbers,
and which lists it may take reserves from. Each list here is transcribed from
the booklet (bfgxr/rules/0N_<faction>.md); limits the engine can't check yet are
kept as text in "unenforced" and shown to the player.

List format (a dict):
  key, name, faction (catalog faction id it is shown under), source,
  kind: "fleet" or "detachment" (a detachment joins one of `joins`),
  sections: [{
      name, ships: {catalog class name: cost in this list},
      max: absolute maximum ships in the section (None = any),
      ratio: (n, [section names]) at most one per n ships in those sections,
      per_points: at most one per this many points of the points limit,
      class_max: {class: n} (0-n of that class),
      class_min_points: {class: points} (class needs a points limit of at least),
      count_as: section name whose limits these ships also count against,
  }],
  group_caps: [{classes, max, per_points, label}]  at most `max` of these
      classes per `per_points` points (or part thereof if `or_part`),
  reserves: [list keys], reserve_ratio: n (default 3),
  options: {option name prefix: True} options this list allows that are list-only,
  unenforced: [text]
"""
from typing import Dict, List, Optional

# ── Imperial Navy (bfgxr/rules/01_imperial-navy.md, Sector Fleet Lists) ─────

_NAVY_UNENFORCED = [
    "Up to two cruisers or battlecruisers may swap launch bays for mine launchers; power "
    "rams: not in the fleet builder yet.",
]
_NAVY_ESC = {"Firestorm Frigate": 35, "Sword Frigate": 35, "Cobra Destroyer": 30}

NAVY_LISTS = [
    {"key": "navy_gothic", "faction": "imperial_navy_gothic", "nova_per_points": 500,
     "name": "Gothic Sector, Segmentum Obscurus (Imperium p.89)",
     "sections": [
         {"name": "Battleships", "ratio": (3, ["Cruisers", "Battlecruisers"]),
          "ships": {"Emperor Battleship": 365, "Retribution Battleship": 355}},
         {"name": "Battlecruisers", "ratio": (2, ["Cruisers"]),
          "ships": {"Mars Battlecruiser": 260, "Overlord Battlecruiser": 220}},
         {"name": "Cruisers", "max": 12,
          "ships": {"Dictator Cruiser": 210, "Dominator Cruiser": 190, "Gothic Cruiser": 180,
                    "Lunar Cruiser": 180, "Tyrant Cruiser": 175,
                    "Dauntless Light Cruiser": 110}},
         {"name": "Escorts", "ships": dict(_NAVY_ESC)},
     ],
     "reserves": ["navy_gothic", "navy_armageddon", "navy_bakka", "navy_bastion",
                  "admech_explorator"],
     "unenforced": list(_NAVY_UNENFORCED)},
    {"key": "navy_armageddon", "faction": "imperial_navy_gothic", "nova_per_points": 500,
     "name": "Armageddon Sector, Segmentum Solar (Imperium p.92)",
     "sections": [
         {"name": "Battleships", "ratio": (3, ["Cruisers", "Battlecruisers"]),
          "class_max": {"Space Marine Battle Barge": 1},
          "ships": {"Space Marine Battle Barge": 425, "Apocalypse Battleship": 365,
                    "Emperor Battleship": 365, "Oberon Battleship": 355}},
         {"name": "Battlecruisers", "ratio": (1, ["Cruisers"]),
          "ships": {"Mars Battlecruiser": 260, "Armageddon Battlecruiser": 235}},
         {"name": "Cruisers", "max": 12, "class_max": {"Strike Cruiser": 4},
          "ships": {"Dictator Cruiser": 210, "Gothic Cruiser": 180, "Lunar Cruiser": 180,
                    "Tyrant Cruiser": 175, "Strike Cruiser": 145,
                    "Endeavour Light Cruiser": 110, "Endurance Light Cruiser": 110,
                    "Defiant Light Cruiser": 110}},
         {"name": "Escorts",
          "ships": {"Nova Frigate": 45, "Gladius Frigate": 40, "Hunter Destroyer": 40,
                    "Firestorm Frigate": 35, "Sword Frigate": 35, "Falchion Frigate": 35}},
     ],
     "group_caps": [{"classes": ["Endurance Light Cruiser", "Defiant Light Cruiser"],
                     "max": 2, "per_points": 500, "or_part": True,
                     "label": "Endurance and Defiant light cruisers (combined)"}],
     "reserves": ["navy_gothic", "navy_armageddon", "navy_bakka", "navy_bastion",
                  "admech_explorator"],
     # Seconded Space Marine vessels are allies of convenience: no Chapter Tactics,
     # no Tactical Flexibility (Strike Cruiser Variants pay full price). The
     # commander may instead be a Master of the Fleet on the Battle Barge
     # (_attach_commanders); Admirals are only offered on Navy capital ships.
     "list_excludes": ["Chapter tactic:"],
     "no_tactical_flexibility": True,
     "extra_commanders": ["Master of the Fleet (Ld 10)"],
     "unenforced": list(_NAVY_UNENFORCED)},
    {"key": "navy_bakka", "faction": "imperial_navy_gothic", "nova_per_points": 500,
     "name": "Bakka Sector, Segmentum Tempestus (Imperium p.93)",
     "sections": [
         {"name": "Battleships", "per_points": 750, "or_part": True,
          "class_max": {"The Vae Victis (unique)": 1},
          "ships": {"Retribution Battleship": 355, "Victory Battleship": 355,
                    "The Vae Victis (unique)": 330}},
         # The Forgeworld of Bakka: Mechanicus cruisers may take any number of the
         # battlecruiser places, as a normal part of the fleet (Explorator list costs)
         {"name": "Battlecruisers", "ratio": (3, ["Cruisers", "Light Cruisers"]),
          "ships": {"Dominion Battlecruiser": 260, "Mercury Battlecruiser": 255,
                    "Cardinal Battlecruiser": 200,
                    "Mechanicus Dictator Cruiser": 245, "Mechanicus Gothic Cruiser": 215,
                    "Mechanicus Lunar Cruiser": 215, "Mechanicus Tyrant Cruiser": 215}},
         {"name": "Cruisers", "ratio": (2, ["Light Cruisers"]),
          "ships": {"Gothic Cruiser": 185, "Lunar Cruiser": 185, "Tyrant Cruiser": 180}},
         {"name": "Light Cruisers", "max": 12, "class_max": {"Dauntless Light Cruiser": 2},
          "ships": {"Dauntless Light Cruiser": 115, "Endeavour Light Cruiser": 115,
                    "Endurance Light Cruiser": 115, "Siluria Light Cruiser": 100}},
         {"name": "Escorts",
          "ships": {"Havoc Frigate": 35, "Viper Destroyer": 35, "Firestorm Frigate": 35,
                    "Sword Frigate": 35}},
     ],
     "reserves": ["navy_gothic", "navy_armageddon", "navy_bastion"], "reserve_ratio": 4,
     # *starred classes: +1 Turret when taken from this list (cost included)
     "stat_changes": {"classes": ["Gothic Cruiser", "Lunar Cruiser", "Tyrant Cruiser",
                                  "Dauntless Light Cruiser", "Endeavour Light Cruiser",
                                  "Endurance Light Cruiser"],
                      "delta": {"turrets": 1}},
     # Secondary commanders are 0-3 Veteran Captains; any Navy capital ship may buy
     # Fleet Defence Turrets (Mechanicus Gifts)
     "list_options": ["Veteran Captain", "Refit: Fleet Defence Turrets"],
     "list_excludes": ["Strategic Commander"],
     "unenforced": list(_NAVY_UNENFORCED) + [
         "Lord Admiral Rath (Ld10) 150 at 1500+pts (The Pride of Bakka's random refits) "
         "isn't in the fleet builder yet. The list has no mine launcher upgrade (none "
         "exists in the fleet builder)."]},
    {"key": "navy_bastion", "faction": "imperial_navy_gothic", "nova_per_points": 500,
     "name": "Bastion Sector, Segmentum Obscurus (Imperium p.90-91)",
     "sections": [
         {"name": "Battleships", "ratio": (3, ["Cruisers", "Battlecruisers & Grand Cruisers"]),
          "ratio_excludes": ["Exorcist Grand Cruiser", "Vengeance Grand Cruiser",
                             "Avenger Grand Cruiser"],
          "ships": {"Apocalypse Battleship": 365, "Emperor Battleship": 365,
                    "Retribution Battleship": 355}},
         {"name": "Battlecruisers & Grand Cruisers", "ratio": (2, ["Cruisers"]),
          "ships": {"Mars Battlecruiser": 260, "Armageddon Battlecruiser": 235,
                    "Overlord Battlecruiser": 220, "Exorcist Grand Cruiser": 260,
                    "Vengeance Grand Cruiser": 230, "Avenger Grand Cruiser": 200}},
         {"name": "Cruisers", "max": 12,
          "ships": {"Dictator Cruiser": 210, "Gothic Cruiser": 180, "Lunar Cruiser": 180,
                    "Tyrant Cruiser": 175, "Dauntless Light Cruiser": 110,
                    "Endeavour Light Cruiser": 110, "Endurance Light Cruiser": 110,
                    "Defiant Light Cruiser": 110}},
         {"name": "Escorts", "ships": dict(_NAVY_ESC)},
     ],
     "group_caps": [{"classes": ["Endurance Light Cruiser", "Defiant Light Cruiser"],
                     "max": 2, "per_points": 500, "or_part": True,
                     "label": "Endurance and Defiant light cruisers (combined)"}],
     "reserves": ["navy_gothic", "navy_armageddon", "navy_bakka", "navy_bastion",
                  "admech_explorator"],
     "unenforced": list(_NAVY_UNENFORCED) + [
         "Battlefleet Cadia and the Segmentum Obscurus reserve fleets (Imperium p.91) are "
         "variants of this list with their own rules."]},
]

# ── Adeptus Mechanicus (02_adeptus-mechanicus.md, Explorator Fleet List) ───

ADMECH_LISTS = [
    {"key": "admech_explorator", "faction": "adeptus_mechanicus",
     "name": "Explorator Fleet (Imperium p.17)",
     "sections": [
         {"name": "Battleships", "ratio": (3, ["Cruisers"]),
          "class_max": {"Ark Mechanicus Omnissiah's Victory (unique)": 1},
          "class_min_points": {"Ark Mechanicus Omnissiah's Victory (unique)": 1000},
          "ships": {"Ark Mechanicus Omnissiah's Victory (unique)": 405,
                    "Mechanicus Emperor Battleship": 390,
                    "Mechanicus Retribution Battleship": 380,
                    "Mechanicus Oberon Battleship": 380}},
         {"name": "Cruisers", "max": 15,
          "ships": {"Mechanicus Dictator Cruiser": 245, "Mechanicus Gothic Cruiser": 215,
                    "Mechanicus Lunar Cruiser": 215, "Mechanicus Tyrant Cruiser": 215,
                    "Mechanicus Endeavour Light Cruiser": 130,
                    "Mechanicus Endurance Light Cruiser": 130,
                    "Mechanicus Defiant Light Cruiser": 130}},
         {"name": "Escorts",
          "ships": {"Mechanicus Nova Frigate": 45, "Mechanicus Gladius Frigate": 40,
                    "Mechanicus Hunter Destroyer": 40, "Mechanicus Firestorm Frigate": 35,
                    "Mechanicus Sword Frigate": 35, "Mechanicus Falchion Frigate": 35,
                    "Mechanicus Cobra Destroyer": 30}},
     ],
     "reserves": ["navy_gothic", "navy_armageddon", "navy_bakka", "navy_bastion",
                  "sm_dominion"],
     "unenforced": [
         "Archmagos Explorator (required at 1000+pts) and Magi Explorators are not in the "
         "fleet builder yet.",
         "Battle Barges taken as reserves count as battleships, Strike Cruisers as cruisers.",
         "Mine launcher swaps (two cruisers) and improved defences: not checked."]},
]

# ── Space Marines (03_space-marines.md, Crusade & Dominion Fleet Lists) ─────

_SM_ESC = {"Nova Frigate": 45, "Gladius Frigate": 40, "Hunter Destroyer": 40}
# Venerable Battle Barges (the profiles' costs; the lists print "varies")
_SM_VENERABLE = {"Emperor Battle Barge": 475, "Apocalypse Battle Barge": 475,
                 "Oberon Battle Barge": 470, "Desecrator Battle Barge": 465,
                 "Retribution Battle Barge": 460, "Relictor Battle Barge": 430}
# Export 15: both lists, "Battle barges: one per 1000pts (or portion thereof); the
# fleet must be worth 1000+pts to include the Chapter flagship. (0-1) Chapter
# Flagship: Venerable Battle Barge, Ultima Battle Barge 450, Space Marine Battle Barge
# 425; (0-2) Command Ships: Space Marine Battle Barge 425."
def _venerable_scs() -> Dict[str, int]:
    """Venerable strike cruisers designed from Navy / Chaos profiles (catalog
    entries "Venerable Strike Cruiser (<class>)"), at their designed cost."""
    from .ship_catalog import get_faction_ships
    return {e.ship_class: e.points_cost for e in get_faction_ships("space_marines", True)
            if e.ship_class.startswith("Venerable Strike Cruiser (")}


_SM_BARGES = {"name": "Battle barges", "per_points": 1000, "or_part": True, "sm_barges": True,
              "ships": dict(_SM_VENERABLE, **{"Ultima Battle Barge": 450,
                                              "Space Marine Battle Barge": 425})}
_SM_UNENFORCED = [
    "Venerable strike cruisers are designed (Imperium p.137); the catalog has one for each "
    "eligible Navy / Chaos class.",
]

SM_LISTS = [
    {"key": "sm_crusade", "faction": "space_marines", "name": "Crusade Fleet (Imperium p.148)",
     "commander": {"options": ["Master of the Fleet (Ld 10)"], "required_at": 751},
     "sections": [
         dict(_SM_BARGES),
         {"name": "Strike Cruisers", "max": 10, "venerable_sc": True,
          "ships": dict({"Strike Cruiser": 145}, **_venerable_scs())},
         {"name": "Vanguard Cruisers", "max": 6, "ships": {"Vanguard Cruiser": 130},
          "lightning_thrusters": "Strike Cruisers"},
         {"name": "Escorts", "ships": dict(_SM_ESC)},
     ],
     "reserves": [],
     "list_options": ["Veteran honour guard"],
     "unenforced": list(_SM_UNENFORCED) + [
         "No reserves; only an Inquisitorial Fleet Detachment may join it."]},
    {"key": "sm_dominion", "faction": "space_marines", "name": "Dominion Fleet (Imperium p.149)",
     "commander": {"options": ["Master of the Fleet (Ld 10)"], "required_at": 751},
     "sections": [
         dict(_SM_BARGES),
         {"name": "Strike Cruisers", "max": 10, "venerable_sc": True,
          "ships": dict({"Strike Cruiser": 145}, **_venerable_scs())},
         {"name": "Vanguard Cruisers", "max": 0, "ships": {"Vanguard Cruiser": 130},
          "lightning_thrusters": "Strike Cruisers"},
         {"name": "Escorts",
          "ships": dict(_SM_ESC, **{"Firestorm Rapid Strike Vessel": 35,
                                     "Sword Rapid Strike Vessel": 35,
                                     "Falchion Rapid Strike Vessel": 35,
                                     "Cobra Rapid Strike Vessel": 30})},
     ],
     "reserves": ["navy_gothic", "navy_armageddon", "navy_bakka", "navy_bastion",
                  "admech_explorator"],
     "reserve_rule": "sm_dominion", "nova_per_points": 1000,
     # Space Marine Captains (25) on Imperial Navy reserve capital ships; veteran
     # honour guards on Space Marine capital ships and Captains' ships
     "list_options": ["Veteran honour guard", "Space Marine Captain"],
     "unenforced": list(_SM_UNENFORCED) + [
         "Mine launcher swaps (two cruisers): not in the fleet builder yet."]},
]

# ── Inquisition (04_inquisition-grey-knights.md) ─────────────────────────────

_INQ_LORD = "Ordo Malleus Inquisitor Lord (Ld 10)"

INQ_LISTS = [
    {"key": "inq_banisher", "faction": "inquisition_grey_knights",
     "name": "Ordo Malleus Banisher Fleet (Imperium p.109)",
     "commander": {"options": [_INQ_LORD], "required_at": 750},
     "sections": [
         {"name": "Battleship", "max": 1,
          "class_min_points": {"Grey Knights Battle Barge": 1000},
          "ships": {"Grey Knights Battle Barge": 430}},
         {"name": "Cruisers", "max": 12,
          "class_max": {"Inquisitorial Cruiser": 6, "Grey Knights Strike Cruiser": 6},
          "ships": {"Inquisitorial Cruiser": 250, "Grey Knights Strike Cruiser": 165}},
         {"name": "Escorts",
          "ships": {"Grey Knights Nova Frigate": 45, "Grey Knights Gladius Frigate": 40,
                    "Grey Knights Hunter Destroyer": 40, "Inquisitorial Firestorm Frigate": 35,
                    "Inquisitorial Sword Frigate": 35, "Inquisitorial Cobra Destroyer": 30}},
     ],
     "class_needs_option": {"Inquisitorial Cruiser": (3, [_INQ_LORD])},
     "reserves": [],
     "list_options": ["Vortex Torpedoes"],
     "unenforced": [
         "The Grey Knights Grand Master, Elite Daemonhunters, honour guards and retinues are "
         "not in the fleet builder yet; a Grey Knights battle barge needs a Grand Master and "
         "more than three Grey Knights strike cruisers need a Grey Knights commander.",
         "Inquisitorial battleships (any non-unique Navy battleship, with an Inquisitor Lord) "
         "aren't offered yet.",
         "Blessing of Chaos, sub-plots: not modelled. No detachments, reserves or allies."]},
    {"key": "inq_detachment", "faction": "inquisition_grey_knights", "kind": "detachment",
     "name": "Inquisitorial Fleet Detachment (Imperium p.108)",
     "joins": ["navy_gothic", "navy_armageddon", "navy_bakka", "navy_bastion",
               "admech_explorator", "sm_crusade", "sm_dominion"],
     "sections": [
         {"name": "Inquisitorial Cruisers", "max": 3, "ratio": (3, ["*cruisers"]),
          "ships": {"Inquisitorial Cruiser": 250}},
         {"name": "Grey Knights Battle Barge", "max": 1,
          "class_min_points": {"Grey Knights Battle Barge": 1000},
          "ships": {"Grey Knights Battle Barge": 430}},
         {"name": "Grey Knights Strike Cruisers", "max": 3, "per_points": 500, "or_part": True,
          "ships": {"Grey Knights Strike Cruiser": 165}},
     ],
     "list_options": ["Inferno Torpedoes", "Vortex Torpedoes"],
     "unenforced": [
         "1-3 Inquisitors (each of one Ordo) must be included; only the Inquisitor Lord option "
         "is in the fleet builder so far. Ordo upgrades need an Inquisitor of that Ordo; a ship "
         "can't take upgrades from more than one Ordo.",
         "The Grey Knights ships need an Ordo Malleus Inquisitor. Inquisitorial cruisers count "
         "against the joined fleet's battlecruiser limit (Imperial Navy, Mechanicus).",
         "Elite Captains, retinues, gun-cutter swaps on Navy / Mechanicus ships: not yet."]},
]

ALL_LISTS: List[Dict] = NAVY_LISTS + ADMECH_LISTS + SM_LISTS + INQ_LISTS
try:                                   # Chaos, Orks, Tau, Rogue Traders
    from .fleet_list_data_other import OTHER_LISTS
    ALL_LISTS += OTHER_LISTS
except ImportError:                    # pragma: no cover
    pass

def _attach_commanders() -> None:
    """Each list's required fleet commander, now that the commanders are
    fleet-builder options (booklet_options.COMMANDERS / ORK_BOSSES): 750+pts
    (core s.5); Explorator 1000+pts; Green Tide one Boss at 500+pts and at
    most one per 500pts; a Rogue Trader detachment always has its Rogue
    Trader; a Tau fleet with a Custodian is led by a Kor'O."""
    from .booklet_options import commander_names
    by_faction = {"imperial_navy_gothic": "Imperial Navy", "chaos": "Chaos",
                  "adeptus_mechanicus": "Adeptus Mechanicus", "tau_kororvesh": "Tau & Allies",
                  "rogue_traders": "Rogue Traders", "orks": "Orks"}
    for fl in ALL_LISTS:
        rule = by_faction.get(fl["faction"])
        if rule is None or fl.get("commander") or fl.get("no_commander"):
            continue
        names = commander_names(rule)
        if rule == "Rogue Traders":
            want = ["Pirate Captain (Ld 8)"] if fl["key"] == "rt_wolf_pack" else [
                n for n in names if "Lord Captain" in n]
            names = want
        # Core s.5 (export 26): "more than 750 points"; Explorator "1000+",
        # Green Tide "500+"
        req = {"adeptus_mechanicus": 1000, "orks": 500}.get(fl["faction"], 751)
        if fl.get("kind") == "detachment":
            req = 0
        fl["commander"] = {"options": names + fl.get("extra_commanders", []),
                           "required_at": req}
        if fl["faction"] == "orks":
            fl["commander"]["per_points"] = 500
        if fl["faction"] == "tau_kororvesh":
            fl.setdefault("class_needs_option", {})["Custodian Battleship"] = (0, ["Kor'O (Ld 9)"])
        fl["unenforced"] = [u for u in fl.get("unenforced", [])
                            if not u.lower().startswith("fleet commander")]


_attach_commanders()
LISTS: Dict[str, Dict] = {fl["key"]: fl for fl in ALL_LISTS}


def lists_for_faction(faction: str, kind: str = "fleet") -> List[Dict]:
    return [fl for fl in ALL_LISTS if fl["faction"] == faction
            and fl.get("kind", "fleet") == kind]


def detachments_for(list_key: str) -> List[Dict]:
    return [fl for fl in ALL_LISTS if fl.get("kind") == "detachment"
            and list_key in fl.get("joins", [])]


def list_ships(fl: Dict) -> Dict[str, int]:
    """{class name: cost} of every ship a list offers."""
    out = {}
    for sec in fl["sections"]:
        out.update(sec["ships"])
    return out


def section_of(fl: Dict, ship_class: str) -> Optional[Dict]:
    for sec in fl["sections"]:
        if ship_class in sec["ships"]:
            return sec
    return None


def list_cost(fl: Optional[Dict], ship_class: str, default: int) -> int:
    if fl is None:
        return default
    return list_ships(fl).get(ship_class, default)


NOTABLE_XENOS_SQUADRON = 30


def _notable_squadrons(rows: List[Dict]) -> Dict[str, List[Dict]]:
    """Notable Xenos ships grouped by squadron (an unsquadroned one is its own)."""
    out: Dict[str, List[Dict]] = {}
    for i, r in enumerate(rows):
        if "(Notable Xenos)" in r["entry"].ship_class:
            out.setdefault(r.get("squadron_id") or f"#{i}", []).append(r)
    return out


def notable_xenos_cost(rows: List[Dict]) -> int:
    """A xenos cutter squadron made a Notable Xenos costs +30pts per squadron
    on top of 35pts per ship (Rogue Traders, Xenos Cutter notes)."""
    return NOTABLE_XENOS_SQUADRON * len(_notable_squadrons(rows))


def notable_xenos_first(rows: List[Dict]) -> set:
    """Row indexes that carry the squadron's +30pts in the saved fleet (the
    first ship of each Notable Xenos squadron), so victory points count it."""
    firsts = {id(rs[0]) for rs in _notable_squadrons(rows).values()}
    return {i for i, r in enumerate(rows) if id(r) in firsts}


def xenos_cutter_errors(rows: List[Dict]) -> List[str]:
    """Xenos cutters can't squadron with other types, and a Notable Xenos
    squadron uses one profile; Pthuxutl can't serve a fleet with Ork vessels,
    the Fra'al Raider one with Imperial Navy vessels."""
    errors = []
    squads: Dict[str, List[Dict]] = {}
    for r in rows:
        if r.get("squadron_id"):
            squads.setdefault(r["squadron_id"], []).append(r)
    for sid, ms in squads.items():
        classes = {m["entry"].ship_class for m in ms}
        if len(classes) > 1 and any("Xenos Cutter" == c or "(Notable Xenos)" in c
                                    for c in classes):
            errors.append(f"Squadron '{sid}': xenos cutters squadron only with the same "
                          f"type ({', '.join(sorted(classes))}).")
    factions = {r["entry"].faction for r in rows}
    for r in rows:
        c = r["entry"].ship_class
        if c.startswith("Pthuxutl") and "orks" in factions:
            errors.append("Pthuxutl War Cruisers can't be taken by a fleet with Ork vessels.")
        if c.startswith("Fra'al Raider") and "imperial_navy_gothic" in factions:
            errors.append("Fra'al Raiders can't be taken by a fleet with Imperial Navy vessels.")
    return sorted(set(errors), key=errors.index)


def reserve_allowed(main_key: str, reserve_key: str, ship_class: str) -> bool:
    """Whether a reserve list's ship may be offered (Demiurg War Host:
    Kor'or'vesh vessels only)."""
    if ship_class in (LISTS.get(main_key) or {}).get("reserve_excludes", []):
        return False                   # Chaos: no Planet Killer or space hulk as reserves
    allowed = (LISTS.get(main_key) or {}).get("reserve_sections", {}).get(reserve_key)
    if not allowed:
        return True
    sec = (section_of(LISTS[reserve_key], ship_class) or {}).get("name", "")
    return any(sec.startswith(a) for a in allowed)


def _war_host_errors(rows: List[Dict]) -> List[str]:
    """Demiurg War Host (Xenos p.101): more Demiurg commerce vessels than all
    other cruisers combined (reserves included); one escort squadron per three
    Demiurg capital ships; Wardens only with Castellans, Orcas only with
    Defenders, Dhows only with Dhows, no squadrons mixing factions; the
    re-rolls bought once."""
    errors = []
    demiurg = [r for r in rows if "demiurg_commerce" in r["entry"].special_rules]
    others = [r for r in rows if r["entry"].ship_type == "cruiser" and r not in demiurg]
    if len(demiurg) <= len(others):
        errors.append(f"A Demiurg War Host needs more Demiurg commerce vessels ({len(demiurg)}) "
                      f"than all other cruisers combined ({len(others)}).")
    squads: Dict[str, List[Dict]] = {}
    for i, r in enumerate(rows):
        if r["entry"].ship_type == "escort":
            squads.setdefault(r.get("squadron_id") or f"#{i}", []).append(r)
    if len(squads) > len(demiurg) // 3:
        errors.append(f"Escorts: {len(squads)} squadron(s), at most one per three Demiurg "
                      f"capital ships ({len(demiurg) // 3}).")
    partners = {"Warden Gunship": "Castellan Escort", "Orca Gunship": "Defender Starship"}
    for sid, ms in squads.items():
        classes = {m["entry"].ship_class for m in ms}
        for towed, mate in partners.items():
            if towed in classes and classes - {towed, mate}:
                errors.append(f"Squadron '{sid}': {towed}s may only be mixed with {mate}s.")
        if "Nicassar Dhow" in classes and len(classes) > 1:
            errors.append(f"Squadron '{sid}': Dhows may not be mixed with other escorts.")
    caps: Dict[str, set] = {}
    for r in rows:
        if r.get("squadron_id") and r["entry"].ship_type != "escort":
            caps.setdefault(r["squadron_id"], set()).add(
                "demiurg" if r in demiurg else r["entry"].ship_class.split()[0])
    for sid, kinds in caps.items():
        if "demiurg" in kinds and len(kinds) > 1:
            errors.append(f"Squadron '{sid}': Demiurg and Tau ships can't squadron together "
                          f"(allies of convenience).")
    bought = [r for r in rows if any(u.startswith("War Host re-roll") for u in r.get("upgrades", []))]
    if len(bought) > 1:
        errors.append("War Host re-rolls are bought once for the whole host.")
    return errors


_CHAOS_LEADERS = ("Chaos Lord (Ld 8)", "Chaos Warmaster (Ld 9)",
                  "Aspiring Champion (+1 Ld, max 9)")


def _chaos_option_errors(cfg: Dict, rows: List[Dict], points: int) -> List[str]:
    """Marks of Chaos and Chaos Space Marine crews by list (07_chaos.md):
    "marks_need": "leader" (a Lord, Warmaster or Aspiring Champion's ship) or
    "leader_or_csm"; "marks_unique": one of each Mark, each on a different
    ship; "csm_per_750": one crew per full 750pts; "terminators_on":
    hull types that may take Terminators. A squadron mixes only same-mark or
    unmarked ships."""
    errors = []
    for r in rows:
        ups = r.get("upgrades", [])
        marks = [u for u in ups if u.startswith("Mark of ")]
        leader = any(u in _CHAOS_LEADERS for u in ups)
        csm = "Chaos Space Marine crew" in ups or "csm_crew" in r["entry"].special_rules
        need = cfg.get("marks_need")
        if marks and need == "leader" and not leader:
            errors.append(f"{r['entry'].ship_class}: a Mark of Chaos needs a Chaos Lord, "
                          f"Warmaster or Aspiring Champion aboard.")
        if marks and need == "leader_or_csm" and not (leader or csm):
            errors.append(f"{r['entry'].ship_class}: a Mark of Chaos needs a Chaos Space Marine "
                          f"crew or a Chaos Lord, Warmaster or Aspiring Champion aboard.")
        if "Chaos Terminators" in ups and cfg.get("terminators") and not (
                r["entry"].ship_type == "battleship" or "Grand Cruiser" in r["entry"].ship_class):
            errors.append(f"{r['entry'].ship_class}: Chaos Terminators only on battleships and "
                          f"grand cruisers with Chaos Space Marines.")
    if cfg.get("marks_unique"):
        taken: Dict[str, int] = {}
        for r in rows:
            for u in r.get("upgrades", []):
                if u.startswith("Mark of "):
                    taken[u] = taken.get(u, 0) + 1
        for m, n in taken.items():
            if n > 1:
                errors.append(f"{m}: one of each Mark, each on a different ship ({n} chosen).")
    if cfg.get("csm_per_750"):
        n = sum(1 for r in rows if "Chaos Space Marine crew" in r.get("upgrades", []))
        if n > points // 750:
            errors.append(f"Chaos Space Marine crews: {n}, one capital ship per full 750pts "
                          f"({points // 750}).")
    squads: Dict[str, set] = {}
    for r in rows:
        if r.get("squadron_id"):
            mark = next((u for u in r.get("upgrades", []) if u.startswith("Mark of ")), None) or \
                next((x for x in r["entry"].special_rules if x.startswith("mark:")), "")
            squads.setdefault(r["squadron_id"], set()).add(mark.replace("Mark of ", "mark:").lower())
    for sid, ms in squads.items():
        if len(ms - {""}) > 1:
            errors.append(f"Squadron '{sid}': marked ships squadron only with the same Mark or "
                          f"unmarked ships.")
    return errors


def no_tactical_flexibility(list_key: str) -> bool:
    """Armageddon: Space Marine ships are allies of convenience, so Strike
    Cruiser Variants lose the Tactical Flexibility discount."""
    src = list_key.split(":", 1)[1] if list_key.startswith("reserve:") else list_key
    return bool((LISTS.get(src) or {}).get("no_tactical_flexibility"))


def list_stat_changes(list_key: str, ship_class: str) -> Dict:
    """Stat changes a list makes to the classes taken from it (Bakka's starred
    classes: +1 Turret)."""
    sc = (LISTS.get(list_key) or {}).get("stat_changes")
    if not sc:
        return {}
    if isinstance(sc, dict) and "classes" in sc:
        return dict(sc["delta"]) if ship_class in sc["classes"] else {}
    sec = (section_of(LISTS[list_key], ship_class) or {}).get("name")
    for entry in (sc if isinstance(sc, list) else [sc]):
        if sec in entry["sections"]:
            return {"special_rules": list(entry["add_rules"])}
    return {}


def option_allowed(option_name: str, list_keys: List[str]) -> bool:
    """Options that only some lists allow (Inferno torpedoes: the Fleet
    Detachment; vortex torpedoes: either Inquisition list)."""
    if any(option_name.startswith(x) for k in list_keys if k in LISTS
           for x in LISTS[k].get("list_excludes", [])):
        return False                   # Bakka: Veteran Captains, not Strategic Commanders
    if (option_name.startswith("Chapter tactic:") and list_keys and list_keys[0] in LISTS
            and LISTS[list_keys[0]]["faction"] != "space_marines"):
        return False                   # only Space Marine fleets use Chapter tactics
    gated = {name for fl in ALL_LISTS for name in fl.get("list_options", [])}
    if not list_keys or not any(option_name.startswith(g) for g in gated):
        return True
    return any(option_name.startswith(o) for k in list_keys if k in LISTS
               for o in LISTS[k].get("list_options", []))


def _hull(entry) -> str:
    return {"battleship": "battleship", "cruiser": "cruiser", "escort": "escort"}.get(
        entry.ship_type, "other")


def fleet_list_errors(main_key: Optional[str], rows: List[Dict], fleet_points: int,
                      detachment_keys: Optional[List[str]] = None) -> List[str]:
    """Problems with a fleet against its fleet list. rows: fleet-builder rows
    with "entry" (ShipClassEntry), "upgrades", and "list" (the list key the
    ship was taken from: the main list, a detachment, or "reserve:<key>").
    fleet_points: what the fleet is worth (owner ruling: points-based limits
    use the fleet's actual total, "for every full 750" rounding down and
    "(or portion thereof)" rounding up)."""
    points_limit = fleet_points
    if not main_key or main_key not in LISTS:
        return []
    main = LISTS[main_key]
    errors: List[str] = []
    dets = [LISTS[k] for k in (detachment_keys or []) if k in LISTS]
    for d in dets:
        if main_key not in d.get("joins", []):
            errors.append(f"{d['name']} can't join {main['name']}.")

    by_list: Dict[str, List[Dict]] = {}
    for r in rows:
        by_list.setdefault(r.get("list") or main_key, []).append(r)

    for fl in [main] + dets:
        mine = by_list.get(fl["key"], [])
        errors += _list_errors(fl, mine, points_limit, rows)

    # Ships not in any of the fleet's lists
    known = {main_key} | {d["key"] for d in dets}
    for key, rs in by_list.items():
        if key in known or key.startswith("reserve:"):
            continue
        for r in rs:
            errors.append(f"{r['entry'].ship_class} isn't in {main['name']}.")

    # Reserves (s.4): one per n battleships / cruisers / escorts of the list
    own = by_list.get(main_key, [])
    ratio = main.get("reserve_ratio", 3)
    for key, rs in by_list.items():
        if not key.startswith("reserve:"):
            continue
        src = key.split(":", 1)[1]
        if src not in main.get("reserves", []):
            errors.append(f"{main['name']} can't take reserves from "
                          f"{LISTS[src]['name'] if src in LISTS else src}.")
    reserves = [r for k, rs in by_list.items() if k.startswith("reserve:") for r in rs]
    if main.get("reserve_rule") == "sm_dominion":
        # Imperial Navy reserves only by these ratios (they replace the normal
        # ones): a battleship or grand cruiser per three strike cruisers, against
        # the battle barge limit; a battlecruiser, cruiser or light cruiser per
        # two, against the strike cruiser limit; no escorts. Mechanicus
        # reserves are taken normally (3:1) and count against the same limits.
        navy = [r for k, rs in by_list.items() if k.startswith("reserve:navy_") for r in rs]
        admech = [r for r in reserves if r not in navy]
        strike = sum(1 for r in own if r["entry"].ship_class in ("Strike Cruiser",))
        big = [r for r in navy if _hull(r["entry"]) == "battleship"
               or "Grand Cruiser" in r["entry"].ship_class]
        cru = [r for r in navy if _hull(r["entry"]) == "cruiser" and r not in big]
        esc = [r for r in navy if _hull(r["entry"]) == "escort"]
        if len(big) > strike // 3:
            errors.append(f"Reserves: {len(big)} battleship(s) or grand cruiser(s), at most one "
                          f"per three strike cruisers ({strike // 3}).")
        if len(cru) > strike // 2:
            errors.append(f"Reserves: {len(cru)} cruiser(s), at most one per two strike "
                          f"cruisers ({strike // 2}).")
        if esc:
            errors.append(f"Reserves: a Dominion fleet takes no Imperial Navy escorts "
                          f"({', '.join(r['entry'].ship_class for r in esc)}).")
        for hull, label in (("battleship", "battleships"), ("cruiser", "cruisers"),
                            ("escort", "escorts")):
            n_own = sum(1 for r in own if _hull(r["entry"]) == hull)
            n_res = sum(1 for r in admech if _hull(r["entry"]) == hull)
            if n_res > n_own // 3:
                errors.append(f"Reserves: {n_res} Mechanicus {label}, at most one per 3 "
                              f"{label} from the fleet list ({n_own // 3}).")
        barges = sum(1 for r in own if (section_of(main, r["entry"].ship_class) or {})
                     .get("name") == "Battle barges")
        barges += len(big) + sum(1 for r in admech if _hull(r["entry"]) == "battleship")
        most = -(-points_limit // 1000)
        if barges > most:
            errors.append(f"Battle barges: {barges} with the reserves counted against them, at "
                          f"most one per 1000pts or portion thereof ({most}).")
        scs = sum(1 for r in own if (section_of(main, r["entry"].ship_class) or {})
                  .get("name") == "Strike Cruisers")
        scs += len(cru) + sum(1 for r in admech if _hull(r["entry"]) == "cruiser")
        if scs > 10:
            errors.append(f"Strike Cruisers: {scs} with the reserves counted against them, at "
                          f"most 10.")
    else:
        for hull, label in (("battleship", "battleships"), ("cruiser", "cruisers"),
                            ("escort", "escorts")):
            n_own = sum(1 for r in own if _hull(r["entry"]) == hull)
            n_res = sum(1 for r in reserves if _hull(r["entry"]) == hull)
            if n_res > n_own // ratio:
                errors.append(f"Reserves: {n_res} {label}, at most one per {ratio} {label} "
                              f"from the fleet list ({n_own // ratio}).")

    # Nova cannons: Navy lists one armed ship per 500pts or part thereof,
    # Dominion one per 1000pts (or portion thereof); refits count
    if main.get("nova_per_points"):
        per = main["nova_per_points"]
        nova = sum(1 for r in rows if any(
            w.get("weapon_type") == "nova_cannon" for w in r["entry"].to_ship_dict(
                name="", player=0, upgrades=r.get("upgrades", []))["weapons"]))
        most = -(-points_limit // per)
        if nova > most:
            errors.append(f"Nova cannons: {nova} armed ships, at most one per {per}pts or "
                          f"part thereof ({most}).")

    # Rogue Trader Expedition: one supporting fleet; a Space Marine one bars xenos
    if main.get("expedition"):
        factions = {LISTS[k.split(":", 1)[1]]["faction"] for k in by_list
                    if k.startswith("reserve:") and k.split(":", 1)[1] in LISTS}
        if len(factions) > 1:
            errors.append("An Expedition takes reserves from one supporting fleet only "
                          f"({len(factions)} factions chosen).")
        mercs = [r["entry"].ship_class for k, rs in by_list.items() if k.startswith("reserve:")
                 for r in rs if (section_of(LISTS.get(k.split(":", 1)[1], {"sections": []}),
                                            r["entry"].ship_class) or {}).get("name", "")
                 .startswith("Allies")]
        if mercs:
            errors.append("Demiurg and Kroot can't be taken as an Expedition's reserves "
                          f"({', '.join(mercs)}); take them as mercenaries.")
        if "space_marines" in factions:
            xenos = [r["entry"].ship_class for r in own
                     if (section_of(main, r["entry"].ship_class) or {}).get("xenos")]
            if xenos:
                errors.append("With a Space Marine supporting fleet no Demiurg, Kroot or "
                              f"other xenos ships may be present ({', '.join(xenos)}).")

    # Commander required (core s.5: a fleet of more than 750pts; lists may
    # change the threshold), and Ork Bosses at most one per 500pts
    for fl in [main] + dets:
        cmd = fl.get("commander")
        if not cmd:
            continue
        mine = rows if fl is main else by_list.get(fl["key"], [])
        n_cmd = sum(1 for r in mine for u in r.get("upgrades", []) if u in cmd["options"])
        if points_limit >= cmd.get("required_at", 750) and not n_cmd:
            what = ("a fleet of more than 750 pts needs" if cmd["required_at"] == 751 else
                    f"a fleet of {cmd['required_at']}+ pts needs" if cmd["required_at"]
                    else "needs")
            errors.append(f"{fl['name']}: {what} a fleet commander "
                          f"({' or '.join(cmd['options'])}).")
        if cmd.get("per_points") and n_cmd > max(1, -(-points_limit // cmd["per_points"])):
            errors.append(f"{fl['name']}: {n_cmd} commanders, at most one per "
                          f"{cmd['per_points']}pts.")

    errors += xenos_cutter_errors(rows)
    if main.get("demiurg_war_host"):
        errors += _war_host_errors(rows)
    if main.get("chaos_options"):
        errors += _chaos_option_errors(main["chaos_options"], rows, points_limit)
    # Reserves limited to some sections of their list (Demiurg War Host:
    # Kor'or'vesh vessels only)
    for key, rs in by_list.items():
        src = key.split(":", 1)[1] if key.startswith("reserve:") else None
        for r in rs if src else []:
            if r["entry"].ship_class in main.get("reserve_excludes", []):
                errors.append(f"{r['entry'].ship_class} can't be taken as a reserve.")
        allowed = main.get("reserve_sections", {}).get(src) if src else None
        for r in rs if allowed else []:
            sec = (section_of(LISTS[src], r["entry"].ship_class) or {}).get("name", "")
            if not any(sec.startswith(a) for a in allowed):
                errors.append(f"{r['entry'].ship_class}: only {', '.join(allowed)} vessels "
                              f"may be taken as reserves.")

    # Options a list doesn't allow
    keys = [main_key] + [d["key"] for d in dets]
    for r in rows:
        for u in r.get("upgrades", []):
            if not option_allowed(u, keys):
                errors.append(f"{r['entry'].ship_class}: {u} isn't available in this fleet list.")
    return errors


def _sm_barge_errors(classes: Dict[str, int], fleet_points: int) -> List[str]:
    """Space Marine Crusade / Dominion battle barges: (0-1) Chapter Flagship
    (a Venerable Battle Barge, the Ultima or a Space Marine Battle Barge), which
    needs a fleet of 1000+pts, and (0-2) Command Ships (Space Marine Battle
    Barges)."""
    errors = []
    flag = sum(classes.get(c, 0) for c in list(_SM_VENERABLE) + ["Ultima Battle Barge"])
    smbb = classes.get("Space Marine Battle Barge", 0)
    if flag > 1:
        errors.append(f"Chapter Flagship: {flag} Venerable / Ultima battle barges, at most one.")
    if smbb > (2 if flag else 3):
        errors.append(f"Space Marine Battle Barges: {smbb}, at most two Command Ships"
                      + ("" if flag else " and one Chapter Flagship") + ".")
    if (flag or smbb > 2) and fleet_points < 1000:
        errors.append("The Chapter Flagship needs a fleet worth at least 1000pts.")
    return errors


def towed_errors(rows: List[Dict]) -> List[str]:
    """Towed escorts (Warden, Orca, Dhow) need gravitic hooks configured to
    carry them in the fleet (owner ruling), one per hook ("hooks:<type>:<n>"
    rules; "any" hooks carry any type). Every Nicassar Rig must be bought with
    four Dhows (export 15)."""
    cap: Dict[str, int] = {}
    for r in rows:
        for rule in r["entry"].special_rules:
            if rule.startswith("hooks:"):
                _, kind, n = rule.split(":")
                cap[kind] = cap.get(kind, 0) + int(n)
    need: Dict[str, int] = {}
    for r in rows:
        if "towed" in r["entry"].special_rules:
            kind = next((k for k in ("warden", "orca", "dhow")
                         if k in r["entry"].ship_class.lower()), "other")
            need[kind] = need.get(kind, 0) + 1
    errors = []
    spare_any = cap.get("any", 0)
    for kind, n in sorted(need.items()):
        short = max(0, n - cap.get(kind, 0))
        used = min(short, spare_any)
        spare_any -= used
        if short - used:
            errors.append(f"{n} towed {kind}(s) but gravitic hooks for only "
                          f"{n - (short - used)}.")
    rigs = sum(1 for r in rows if r["entry"].ship_class == "Nicassar Rig")
    if rigs and need.get("dhow", 0) < 4 * rigs:
        errors.append(f"Every Nicassar Rig needs four Dhows bought with it "
                      f"({rigs} Rig(s), {need.get('dhow', 0)} Dhow(s)).")
    return errors


def _list_errors(fl: Dict, rows: List[Dict], points_limit: int,
                 all_rows: List[Dict]) -> List[str]:
    errors: List[str] = []
    counts: Dict[str, int] = {}
    excluded: Dict[str, int] = {}
    classes: Dict[str, int] = {}
    lt_moved = 0
    has_lt = any(u.startswith("Chapter tactic: Lightning Thrusters")
                 for r in all_rows for u in r.get("upgrades", []))
    for r in rows:
        cls = r["entry"].ship_class
        sec = section_of(fl, cls)
        if sec is None:
            errors.append(f"{cls} isn't in {fl['name']}.")
            continue
        classes[cls] = classes.get(cls, 0) + 1
        name = sec["name"]
        # Lightning Thrusters: up to 4 vanguard cruisers count against the
        # strike cruiser maximum instead
        if has_lt and sec.get("lightning_thrusters") and lt_moved < 4:
            lt_moved += 1
            name = sec["lightning_thrusters"]
        counts[name] = counts.get(name, 0) + 1
        # Ships that don't count towards another section's ratio (Bastion:
        # grand cruisers don't count for battleships)
        if any(cls in (s.get("ratio_excludes") or []) for s in fl["sections"]):
            excluded[name] = excluded.get(name, 0) + 1

    for sec in fl["sections"]:
        n = counts.get(sec["name"], 0)
        if sec.get("max") is not None and n > sec["max"]:
            errors.append(f"{sec['name']}: {n} taken, at most {sec['max']}.")
        if sec.get("ratio"):
            per, others = sec["ratio"]
            if others == ["*cruisers"]:          # the joined fleet's cruisers
                base = sum(1 for r in all_rows if _hull(r["entry"]) == "cruiser"
                           and r.get("list") != fl["key"])
            else:
                base = sum(counts.get(o, 0) - (excluded.get(o, 0)
                                                if sec.get("ratio_excludes") else 0)
                           for o in others)
            if n > base // per:
                what = "the joined fleet's cruisers" if others == ["*cruisers"] else \
                    " / ".join(o.lower() for o in others)
                errors.append(f"{sec['name']}: {n} taken, at most one per {per} {what} "
                              f"({base // per}).")
        if sec.get("per_points"):
            pp = sec["per_points"]
            worth = points_limit
            if sec.get("per_points_of"):            # Tau: "of Tau vessels" only
                prefixes = tuple(sec["per_points_of"])
                worth = sum(r.get("points", 0) for r in rows
                            if (section_of(fl, r["entry"].ship_class) or {}).get(
                                "name", "").startswith(prefixes))
            cap = (-(-worth // pp)) if sec.get("or_part") else worth // pp
            if n > cap:
                errors.append(f"{sec['name']}: {n} taken, at most one per {pp}pts"
                              f"{' or portion thereof' if sec.get('or_part') else ''} "
                              f"({cap} for {worth}pts).")
        if sec.get("sm_barges"):
            errors += _sm_barge_errors(classes, points_limit)
        if sec.get("venerable_sc"):
            # Owner ruling: with a fleet of 1000+pts, up to one venerable strike
            # cruiser per three standard ones (variants count), at most two
            ven = sum(n for c, n in classes.items() if c.startswith("Venerable Strike Cruiser ("))
            std = classes.get("Strike Cruiser", 0)
            if ven and points_limit < 1000:
                errors.append("Venerable strike cruisers need a fleet worth at least 1000pts.")
            if ven > min(2, std // 3):
                errors.append(f"Venerable strike cruisers: {ven}, at most one per three "
                              f"standard strike cruisers and two in all ({min(2, std // 3)}).")
        for cls, mx in (sec.get("class_max") or {}).items():
            if classes.get(cls, 0) > mx:
                errors.append(f"{cls}: {classes[cls]} taken, at most {mx}.")
        for cls, pts in (sec.get("class_min_points") or {}).items():
            if classes.get(cls, 0) and points_limit < pts:
                errors.append(f"{cls} needs a fleet of at least {pts}pts.")

    for cap in fl.get("group_caps", []):
        n = sum(classes.get(c, 0) for c in cap["classes"])
        per = cap.get("per_points")
        mx = (cap["max"] * ((-(-points_limit // per)) if cap.get("or_part") else points_limit // per)
              if per else cap["max"])
        if n > mx:
            errors.append(f"{cap['label']}: {n} taken, at most {cap['max']} per "
                          f"{cap['per_points']}pts ({mx}).")

    for a, b in fl.get("class_not_more_than", []):          # Demiurg Stronghold vs Bastion
        if classes.get(a, 0) > classes.get(b, 0):
            errors.append(f"Never more {a}s than {b}s ({classes.get(a, 0)} vs "
                          f"{classes.get(b, 0)}).")

    for cls, (free, opts) in (fl.get("class_needs_option") or {}).items():
        if classes.get(cls, 0) > free and not any(
                u in opts for r in all_rows for u in r.get("upgrades", [])):
            errors.append(f"More than {free} {cls}s need {' or '.join(opts)}.")
    return errors
