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
    "Fleet commander (Admiral, Strategic Commanders) and their re-rolls are not in the "
    "fleet builder yet.",
    "Up to two cruisers or battlecruisers may swap launch bays for mine launchers; power rams; "
    "one nova-cannon ship per 500pts or part thereof: not checked.",
]
_NAVY_ESC = {"Firestorm Frigate": 35, "Sword Frigate": 35, "Cobra Destroyer": 30}

NAVY_LISTS = [
    {"key": "navy_gothic", "faction": "imperial_navy_gothic",
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
    {"key": "navy_armageddon", "faction": "imperial_navy_gothic",
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
                     "max": 2, "per_points": 500,
                     "label": "Endurance and Defiant light cruisers (combined)"}],
     "reserves": ["navy_gothic", "navy_armageddon", "navy_bakka", "navy_bastion",
                  "admech_explorator"],
     "unenforced": list(_NAVY_UNENFORCED) + [
         "Seconded Space Marine vessels are allies of convenience (no Chapter Tactics or "
         "Tactical Flexibility); the commander may instead be a Master of the Fleet on a "
         "Battle Barge."]},
    {"key": "navy_bakka", "faction": "imperial_navy_gothic",
     "name": "Bakka Sector, Segmentum Tempestus (Imperium p.93)",
     "sections": [
         {"name": "Battleships", "per_points": 750,
          "class_max": {"The Vae Victis (unique)": 1},
          "ships": {"Retribution Battleship": 355, "Victory Battleship": 355,
                    "The Vae Victis (unique)": 330}},
         {"name": "Battlecruisers", "ratio": (3, ["Cruisers", "Light Cruisers"]),
          "ships": {"Dominion Battlecruiser": 260, "Mercury Battlecruiser": 255,
                    "Cardinal Battlecruiser": 200}},
         {"name": "Cruisers", "ratio": (2, ["Light Cruisers"]),
          "ships": {"Gothic Cruiser": 185, "Lunar Cruiser": 185, "Tyrant Cruiser": 180}},
         {"name": "Light Cruisers", "max": 12, "class_max": {"Dauntless Light Cruiser": 2},
          "ships": {"Dauntless Light Cruiser": 115, "Endeavour Light Cruiser": 115,
                    "Endurance Light Cruiser": 115, "Siluria Light Cruiser": 100}},
         {"name": "Escorts",
          "ships": {"Firestorm Frigate": 35, "Sword Frigate": 35, "Viper Destroyer": 35,
                    "Cobra Destroyer": 30}},
     ],
     "reserves": ["navy_gothic", "navy_armageddon", "navy_bastion"], "reserve_ratio": 4,
     "unenforced": list(_NAVY_UNENFORCED) + [
         "Starred Bakka classes gain extra rules (the cost premium is included).",
         "Secondary commanders are 0-3 Veteran Captains; Lord Admiral Rath (Ld10) 150 at "
         "1500+pts."]},
    {"key": "navy_bastion", "faction": "imperial_navy_gothic",
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
                     "max": 2, "per_points": 500,
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
_SM_BARGES = {"name": "Battle barges", "per_points": 1000, "or_part": True, "sm_barges": True,
              "ships": dict(_SM_VENERABLE, **{"Ultima Battle Barge": 450,
                                              "Space Marine Battle Barge": 425})}
_SM_UNENFORCED = [
    "The Master of the Fleet must ride a battle barge, the Chapter flagship if present.",
    "Venerable Strike Cruisers (designed from the Space Marine rules) aren't in the catalog: "
    "with a fleet of 1000+pts, up to one per three standard strike cruisers (variants count), "
    "at most two.",
]

SM_LISTS = [
    {"key": "sm_crusade", "faction": "space_marines", "name": "Crusade Fleet (Imperium p.148)",
     "commander": {"options": ["Master of the Fleet (Ld 10)"], "required_at": 750},
     "sections": [
         dict(_SM_BARGES),
         {"name": "Strike Cruisers", "ships": {"Strike Cruiser": 145}},
         {"name": "Vanguard Cruisers", "max": 6, "ships": {"Vanguard Cruiser": 130},
          "lightning_thrusters": "Strike Cruisers"},
         {"name": "Escorts", "ships": dict(_SM_ESC)},
     ],
     "reserves": [],
     "unenforced": list(_SM_UNENFORCED) + [
         "No reserves; only an Inquisitorial Fleet Detachment may join it."]},
    {"key": "sm_dominion", "faction": "space_marines", "name": "Dominion Fleet (Imperium p.149)",
     "commander": {"options": ["Master of the Fleet (Ld 10)"], "required_at": 750},
     "sections": [
         dict(_SM_BARGES),
         {"name": "Strike Cruisers", "max": 10, "ships": {"Strike Cruiser": 145}},
         {"name": "Vanguard Cruisers", "max": 0, "ships": {"Vanguard Cruiser": 130},
          "lightning_thrusters": "Strike Cruisers"},
         {"name": "Escorts",
          "ships": dict(_SM_ESC, **{"Firestorm Rapid Strike Vessel": 35,
                                     "Falchion Rapid Strike Vessel": 35,
                                     "Cobra Rapid Strike Vessel": 30})},
     ],
     "reserves": ["navy_gothic", "navy_armageddon", "navy_bakka", "navy_bastion"],
     "reserve_rule": "sm_dominion",
     "unenforced": list(_SM_UNENFORCED) + [
         "Space Marine Captains (25pts) on Imperial Navy reserve capital ships.",
         "Mine launcher swaps (two cruisers): not checked."]},
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


def option_allowed(option_name: str, list_keys: List[str]) -> bool:
    """Options that only some lists allow (Inferno torpedoes: the Fleet
    Detachment; vortex torpedoes: either Inquisition list)."""
    gated = {name for fl in ALL_LISTS for name in fl.get("list_options", [])}
    gate = next((g for g in gated if option_name.startswith(g)), None)
    if gate is None or not list_keys:
        return True
    return any(gate in LISTS[k].get("list_options", []) for k in list_keys if k in LISTS)


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
        strike = sum(1 for r in own if r["entry"].ship_class in ("Strike Cruiser",))
        big = [r for r in reserves if _hull(r["entry"]) == "battleship"
               or "Grand Cruiser" in r["entry"].ship_class]
        cru = [r for r in reserves if _hull(r["entry"]) == "cruiser" and r not in big]
        if len(big) > strike // 3:
            errors.append(f"Reserves: {len(big)} battleship(s) or grand cruiser(s), at most one "
                          f"per three strike cruisers ({strike // 3}).")
        if len(cru) > strike // 2:
            errors.append(f"Reserves: {len(cru)} cruiser(s), at most one per two strike "
                          f"cruisers ({strike // 2}).")
    else:
        for hull, label in (("battleship", "battleships"), ("cruiser", "cruisers"),
                            ("escort", "escorts")):
            n_own = sum(1 for r in own if _hull(r["entry"]) == hull)
            n_res = sum(1 for r in reserves if _hull(r["entry"]) == hull)
            if n_res > n_own // ratio:
                errors.append(f"Reserves: {n_res} {label}, at most one per {ratio} {label} "
                              f"from the fleet list ({n_own // ratio}).")

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

    # Commander required
    cmd = main.get("commander")
    if cmd and cmd.get("required_at") and points_limit >= cmd["required_at"]:
        if not any(u in cmd["options"] for r in rows for u in r.get("upgrades", [])):
            errors.append(f"{main['name']}: a fleet of {cmd['required_at']}+ pts needs a "
                          f"fleet commander ({' or '.join(cmd['options'])}).")

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
        for cls, mx in (sec.get("class_max") or {}).items():
            if classes.get(cls, 0) > mx:
                errors.append(f"{cls}: {classes[cls]} taken, at most {mx}.")
        for cls, pts in (sec.get("class_min_points") or {}).items():
            if classes.get(cls, 0) and points_limit < pts:
                errors.append(f"{cls} needs a fleet of at least {pts}pts.")

    for cap in fl.get("group_caps", []):
        n = sum(classes.get(c, 0) for c in cap["classes"])
        mx = cap["max"] * (points_limit // cap["per_points"]) if cap.get("per_points") \
            else cap["max"]
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
