"""BFG:XR ship catalog built from the companion booklet (bfgxr/data/ships.json).

Converts each booklet roster row into the engine's ship class format. Ships
that use rules the engine can't play yet are still converted, with the reasons
listed in `unsupported`, so the fleet builder can show them greyed out.
Nothing here invents stats: every number comes from ships.json.
"""
import json
import os
import re
from typing import Dict, List, Optional, Tuple

SHIPS_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "..", "bfgxr", "data", "ships.json")

# Booklet faction -> (faction id, display name, Appendix 4 Leadership column).
# The Imperial Navy and Tau ids predate the booklet and are kept so saved
# fleets still match.
FACTIONS: Dict[str, Tuple[str, str, str]] = {
    "Imperial Navy": ("imperial_navy_gothic", "Imperial Navy", "Default"),
    "Adeptus Mechanicus": ("adeptus_mechanicus", "Adeptus Mechanicus", "Mechanicus"),
    "Space Marines": ("space_marines", "Space Marines", "Astartes"),
    "Inquisition & Grey Knights": ("inquisition_grey_knights", "Inquisition & Grey Knights", "Default"),
    "Rogue Traders": ("rogue_traders", "Rogue Traders", "Default"),
    "Support Assets": ("support_assets", "Support Assets", "Default"),
    "Chaos": ("chaos", "Chaos", "Default"),
    "Orks": ("orks", "Orks", "Orks"),
    "Tau & Allies": ("tau_kororvesh", "Tau & Allies", "Default"),
    # Export 13 (updates 48-49). Appendix 4 has no Necron column ("factions not
    # listed use Default"); Eldar use the Eldar column (Default +1).
    "Eldar": ("eldar", "Eldar", "Eldar"),
    "Necrons": ("necrons", "Necrons", "Default"),
}

# Factions whose own rules the engine doesn't play yet: every ship is listed
# but greyed out (CLAUDE.md To do 14).
UNBUILT_FACTION_RULES = {
    # Eldar (MMS v2.0) are playable now (src/eldar.py); their remaining gaps are
    # listed in CLAUDE.md To do 14
    # Necrons are playable too (src/necrons.py); the ground defences and Deathseed
    # mines stay unsupported for their own reasons (no movement / profile)
}

# Appendix 4 - Leadership Tables: D6 roll -> Leadership, per column.
LEADERSHIP_TABLES: Dict[str, List[int]] = {
    "Default":    [6, 7, 7, 8, 8, 9],
    "Mechanicus": [7, 8, 8, 9, 9, 9],
    "Astartes":   [8, 8, 9, 9, 10, 10],
    "Orks":       [5, 6, 6, 7, 7, 8],
    "Eldar":      [7, 8, 8, 9, 9, 10],
}

# Booklet weapon name -> engine weapon_type. Tau terms per the Tau faction rules:
# Railguns = macrobatteries, Ion Cannon = lance, Gravitic Launcher = missile launcher.
WEAPON_TYPES = {
    "Macrobatteries": "battery", "Macrobattery": "battery",
    "Railguns": "battery", "Railgun": "battery",
    "Lances": "lance", "Lance": "lance",
    # Ork Zzapp Gunz: lances hitting on 5+ (Ork weapons, Xenos)
    "Zzapp Gunz": "lance",
    "Ion Cannons": "lance", "Ion Cannon": "lance",
    "Cutting Beam": "lance",          # Demiurg: FP1+ (1 + collected blast markers, max 8)
    # Nekulli Whip: "The whisperlance cannon follows the rules for lances"
    "Whisperlance Cannon": "lance",
    "Torps": "torpedo", "Gravitic Launcher": "torpedo",
    # Ork faction rules: Gunz follow all the usual macrobattery rules; Heavy Gunz are
    # macrobatteries with a second firepower used within 15cm, e.g. FP6(10)
    "Gunz": "battery", "Heavy Gunz": "battery",
    # Space Marine Bombardment Cannons and Ork Killkannons: fire as macrobatteries
    # but always hit on 4+ regardless of Armour (even vs ordnance), and crits
    # from them succeed on 4+ instead of 6 (WEAPON_RULES)
    "Bombardment Cannon": "battery", "Killkannon": "battery",
    "Nova Cannon": "nova_cannon",
    # Eldar (MMS v2.0): weapons batteries (a left column shift), pulsar and
    # phantom lances (lances with their own hit rules), torpedoes (re-roll misses)
    "Weapons Battery": "battery", "Pulsar Lance": "lance", "Phantom Lance": "lance",
    "Torpedoes": "torpedo",
    # Necrons (Xenos p.40): lightning arcs are weapons batteries, particle whips lances
    "Lightning Arc": "battery", "Particle Whip": "lance",
}
_NECRON_WEAPON_FLAGS = {"Lightning Arc": "lightning_arc", "Particle Whip": "particle_whip"}
_ELDAR_WEAPON_FLAGS = {"Weapons Battery": "eldar_battery", "Pulsar Lance": "pulsar",
                       "Phantom Lance": "phantom", "Torpedoes": "eldar_torpedo"}
# Eldar craft (MMS p.4): fighters, bombers and (Vampire) assault boats with their own
# rules, so their own types: Darkstar / Nightwing fighters, Eagle / Phoenix bombers
_ELDAR_CRAFT = {"ASF": "eldar_fighter", "BMR": "eldar_bomber", "AB": "vampire_assault_boat"}

WEAPON_RULES = {
    "Bombardment Cannon": {"hits_on": 4, "crit_on": 4},
    "Killkannon": {"hits_on": 4, "crit_on": 4},
    "Zzapp Gunz": {"hits_on": 5, "zzapp": True},
    "Cutting Beam": {"cutting_beam": True},
}

ARC_CODES = {"L": ["left"], "R": ["right"], "F": ["front"], "Rear": ["rear"],
             "All Round": ["front", "left", "right", "rear"]}

# Attack craft: booklet code -> engine craft type, per faction where the faction
# rules name them (Imperial Navy: Fury, Starhawk, Shark; Tau: Barracuda, Manta).
_IN_CRAFT = {"ASF": "fury_fighter", "BMR": "starhawk_bomber", "AB": "shark_assault_boat"}
_TAU_CRAFT = {"ASF": "barracuda", "BMR": "manta"}
GENERIC_CRAFT = {"ASF": "fighter", "BMR": "bomber", "AB": "assault_boat",
                 "Gun-Cutters": "gun_cutter"}
# Multi-role craft (MR) by faction, as the faction rules name them
MR_CRAFT = {"Space Marines": "thunderhawk", "Inquisition & Grey Knights": "thunderhawk",
            "Orks": "fighta_bommer"}


def _ship_type(row: dict) -> Optional[str]:
    """Engine hull type from the booklet's hull type, name or roster group."""
    hull = (row.get("hull_type") or "").lower()
    if hull:
        if "escort" in hull:
            return "escort"
        if "battleship" in hull:
            return "battleship"
        if "defen" in hull:
            return "defense"
        if "cruiser" in hull:
            return "cruiser"
    for text in (row["name"].lower(), (row.get("roster_group") or "").lower()):
        if "battleship" in text or "battle barge" in text:
            return "battleship"
        if "cruiser" in text or "kroozer" in text:
            return "cruiser"
        if "escort" in text or "frigate" in text or "destroyer" in text:
            return "escort"
        if "defen" in text:
            return "defense"
    return None


def _armour(row: dict) -> Optional[Tuple[str, str, str]]:
    """(prow, side, rear) armour; rear is "" unless the ship shows three values
    (front / abeam / rear, e.g. Ork cruisers 6+/5+/4+)."""
    a = row.get("armour")
    if a and a.get("front") is not None and a.get("other") is not None:
        return f"{a['front']}+", f"{a['other']}+", ""
    raw = (row.get("armour_raw") or "").strip()
    m = re.fullmatch(r"(\d)\+\s*/\s*(\d)\+\s*/\s*(\d)\+", raw)
    if m:
        return f"{m.group(1)}+", f"{m.group(2)}+", f"{m.group(3)}+"
    # Owner ruling: "5+ / 4+R" is 5+ everywhere except the rear quadrant (4+)
    m = re.fullmatch(r"(\d)\+\s*/\s*(\d)\+R", raw)
    if m:
        return f"{m.group(1)}+", f"{m.group(1)}+", f"{m.group(2)}+"
    return None


def _mount_name(weapon: dict, arcs: List[str], n_mounts: int) -> str:
    base = weapon["name"]
    if weapon.get("location"):
        return f"{weapon['location']} {base}"
    if n_mounts > 1 and arcs and arcs[0] == "L":
        return f"Port {base}"
    if n_mounts > 1 and arcs and arcs[0] == "R":
        return f"Starboard {base}"
    return base


def gravitic_hook_rules(row: dict) -> List[str]:
    """"hooks:<type>:<n>" for a profile's gravitic hooks ("3 Orcas", "1 Warden
    each" on port + stbd, "capacity 2"): what towed escorts the fleet can bring."""
    out = []
    for w in row.get("weapons") or []:
        if w.get("kind") != "gravitic_hooks":
            continue
        m = re.match(r"(?:capacity )?(\d+)\s*([A-Za-z]*?)s?(?: each)?$", (w.get("capacity") or "").strip())
        if not m:
            continue
        n = int(m.group(1)) * (len(w.get("sides") or []) if "each" in w["capacity"] else 1)
        out.append(f"hooks:{(m.group(2) or 'any').lower()}:{n}")
    return out


def _eldar_bays(w: dict) -> dict:
    """Eldar keel launch bays the export leaves unparsed ("Keel Launch Bays S4
    (Darkstar ASF 30cm, Eagle BMR 20cm)"): read them as a launch_bays entry.
    (An export gap to report: the parser doesn't know the Keel location.)"""
    if w.get("kind") == "launch_bays":
        # "Darkstar ASF" -> "ASF": the Eldar names their craft, the code is what counts
        return {**w, "craft": [{**c, "type": (c.get("type") or "").split()[-1]}
                               for c in w.get("craft") or []]}
    if w.get("kind") != "unparsed":
        return w
    m = re.fullmatch(r"(?:(\w+) )?Launch Bays? S(\d+) \((.+)\)", w.get("raw", "").strip())
    if not m:
        return w
    craft = []
    for part in m.group(3).split(","):
        cm = re.fullmatch(r"\s*(?:\w+ )?(ASF|BMR|AB) (\d+)cm\s*", part)
        if cm:
            craft.append({"type": cm.group(1), "speed_cm": int(cm.group(2))})
    return {"kind": "launch_bays", "raw": w["raw"], "location": m.group(1),
            "bays": [{"side": None, "strength": int(m.group(2))}], "craft": craft,
            "stat": "S", "parsed": True}


def _convert_weapon(w: dict, craft_map: Dict[str, str],
                    problems: List[str]) -> List[dict]:
    if w["kind"] == "gravitic_hooks":
        return []   # tow escorts into battle: fleet building only, no battle effect
    if w.get("name") == "Armageddon Gun":
        # The Planet Killer: a template swept 90cm straight ahead
        # (combat.resolve_armageddon_gun)
        return [{"name": "Armageddon Gun", "weapon_type": "armageddon_gun",
                 "range_cm": w.get("range_max_cm") or 90, "strength": 0, "arcs": ["front"]}]
    if w.get("name") == "Kustom Kannon":
        # Hammer Battlekroozer: fires as an FP6 killkannon or launches S D6+2
        # torps, one mode per turn, reloaded by Reload Ordnance after either
        # (its notes); both share the torpedo load (`kustom_kannon`)
        rng = w.get("range_max_cm") or 30
        return [{"name": "Prow Kustom Kannon", "weapon_type": "battery", "range_cm": rng,
                 "strength": 6, "arcs": ["front"], "hits_on": 4, "crit_on": 4,
                 "kustom_kannon": True},
                {"name": "Prow Kustom Kannon Torps", "weapon_type": "torpedo", "range_cm": 30,
                 "strength": 5, "strength_dice": "D6+2", "arcs": ["front"],
                 "torpedo_type": "standard", "torpedo_speed": 30, "kustom_kannon": True}]
    if w["kind"] == "unparsed":
        m = re.match(r"Dorsal Modular Launch Bays S(\d+) or S(\d+) Torps", w["raw"])
        if m:
            # Demiurg Bastion: launch bays or torpedoes, chosen at each launch
            # (owner ruling); launching either uses both (Ship.mark_launched)
            return [{"name": "Dorsal Modular Launch Bays", "weapon_type": "launch_bay",
                     "range_cm": 30, "strength": int(m.group(1)), "arcs": [],
                     "craft_types": ["fighter", "bomber", "assault_boat"],
                     "craft_speeds": {"fighter": 30, "bomber": 20, "assault_boat": 30},
                     "craft_speed": 30},
                    {"name": "Dorsal Modular Torps", "weapon_type": "torpedo", "range_cm": 30,
                     "strength": int(m.group(2)), "arcs": ["left", "front", "right", "rear"],
                     "torpedo_type": "standard", "torpedo_speed": 30}]
        problems.append(f"weapon not parsed: {w['raw']}")
        return []
    if w["kind"] == "launch_bays":
        out = []
        craft_types, speeds = [], {}
        for c in w["craft"]:
            ctype = craft_map.get(c["type"]) or GENERIC_CRAFT.get(c["type"])
            if not ctype:
                problems.append(f"{c['type']} attack craft not modelled yet")
                continue
            craft_types.append(ctype)
            speeds[ctype] = c["speed_cm"]
        for bay in w["bays"]:
            side = {"port": "Port", "stbd": "Starboard", "prow": "Prow",
                    "dorsal": "Dorsal"}.get(bay.get("side") or "", "")
            strength_dice = None
            try:
                strength = int(bay["strength"])
            except (TypeError, ValueError):
                from .combat import is_dice_value, dice_value_max
                if not is_dice_value(str(bay["strength"])):
                    problems.append(f"launch bay strength {bay['strength']} not modelled yet")
                    continue
                # Random strength: rolled just before launching (owner ruling);
                # counts its maximum towards the fleet's attack craft limit (s.15)
                strength_dice = str(bay["strength"]).replace(" ", "").upper()
                strength = dice_value_max(strength_dice)
            bay_d = {"name": f"{side} Launch Bays".strip(), "weapon_type": "launch_bay",
                     "range_cm": 30, "strength": strength, "arcs": [],
                     "craft_types": list(craft_types), "craft_speeds": dict(speeds),
                     "craft_speed": max(speeds.values()) if speeds else 0}
            if strength_dice:
                bay_d["strength_dice"] = strength_dice
            out.append(bay_d)
        return out

    wtype = WEAPON_TYPES.get(w["name"])
    if not wtype:
        problems.append(f"{w['name']} not modelled yet")
        return []
    if w.get("per_face") or w.get("per_quadrant") or w.get("group"):
        problems.append("fortress weapons not modelled yet")
        return []
    strength = w.get("value_int")
    strength_close = None
    if w["name"] == "Heavy Gunz":
        m = re.fullmatch(r"(\d+)\((\d+)\)", (w.get("value") or "").replace(" ", ""))
        if m:
            strength, strength_close = int(m.group(1)), int(m.group(2))
    strength_dice = None
    if w["name"] == "Cutting Beam" and (w.get("value") or "") == "1+":
        strength = 1                   # combat.cutting_beam_profile adds the markers
    if strength is None and wtype in ("battery", "lance", "torpedo"):
        from .combat import is_dice_value, dice_value_average
        if is_dice_value(w.get("value") or ""):
            # Owner ruling: random Ork values are rolled when used
            strength_dice = w["value"].replace(" ", "").upper()
            strength = dice_value_average(strength_dice)
    if wtype != "nova_cannon" and strength is None:
        problems.append(f"variable firepower ({w['value']}) not modelled yet")
        return []

    mounts = w.get("mounts") or [{"arcs": ["F"]}]
    out = []
    for m in mounts:
        arcs = [a for code in m["arcs"] for a in ARC_CODES.get(code, [])]
        d = {"name": _mount_name(w, m["arcs"], len(mounts)), "weapon_type": wtype,
             "range_cm": w.get("range_max_cm") or 0, "strength": strength or 0,
             "arcs": arcs}
        d.update(WEAPON_RULES.get(w["name"], {}))
        if strength_close is not None:
            d["strength_close"] = strength_close   # firepower within 15cm
        if strength_dice:
            d["strength_dice"] = strength_dice     # rolled when used; strength = average
        if wtype == "nova_cannon":
            d.update(range_cm=w.get("range_max_cm") or 150,
                     min_range_cm=w.get("range_min_cm") or 30, strength=0)
        elif wtype == "torpedo":
            guided = w["name"] == "Gravitic Launcher"
            d["torpedo_type"] = "guided" if guided else "standard"
            d["torpedo_speed"] = w.get("range_max_cm") or 30
            if guided and w.get("range_min_cm"):
                d["torpedo_speed_min"] = w["range_min_cm"]
            if w.get("qualifier") and "boarding" in w["qualifier"]:
                d["boarding_torpedoes"] = True
        out.append(d)
    return out


def faction_special_rules(row: dict) -> List[str]:
    """Engine special rules for the faction rules a ship follows (ships.json
    faction_rules: its own faction unless its Notes say otherwise)."""
    rules: List[str] = []
    followed = row.get("faction_rules") or []
    if "Space Marines" in followed or "Grey Knights" in followed:
        # Space Marine faction rules: +2 crew damage boarding, +1 to their (and
        # their ordnance's) hit-and-run attacks, enemy raids -1, and Teleport
        # Assault (may teleport-attack targets with more remaining hits)
        rules += ["space_marine_crew", "teleport_assault"]
    if "Grey Knights" in followed:
        rules.append("knights_of_titan")   # re-roll boarding actions
    if "Orks" in followed:
        rules.append("ere_we_go")          # auto-pass All Ahead Full, +3D6cm only
        rules.append("ork_crew")           # +1 crew damage boarding (s.32)
        rules.append("ork_turrets")        # turrets hit on 5+, fire at every ordnance type
    if "Chaos" in followed:
        rules.append("chaos_crew")         # +1 crew damage boarding (s.32)
    group = row.get("roster_group") or ""
    if group.startswith("Kor'vattra"):
        rules.append("kor_vattra")         # always halve troop rating; no teleport
    if group.startswith("Allies: Nicassar"):
        rules.append("frail_crew")         # halve troop rating when boarded
    if "Support Assets" in followed:
        # Fleet Support: Ld 7 for all checks and tests; system and convoy ships
        # add only +3D6cm on All Ahead Full
        rules.append("fleet_support")
    return rules


def transport_capacity(notes: str):
    """Convoy ships' transport capacity from the notes ("Transport capacity
    2", "½ transport capacity", "Convoy ship (transport capacity 8)"), as
    (capacity, counts for scenario requirements only), or None."""
    m = re.search(r"(?:[Tt]ransport capacity (\d+|½))|(?:(½) transport capacity)", notes or "")
    if not m:
        return None
    raw = m.group(1) or m.group(2)
    cap = 0.5 if raw == "½" else float(raw)
    build_only = bool(re.search(r"scenario (?:requirements )?only|does not count for sc",
                                notes))
    return cap, build_only


def _has_built_in_thrusters(notes: str) -> bool:
    """+D6cm on All Ahead Full built into the profile (Improved Thrusters,
    Sigils of Quickening...), not offered as a refit for points."""
    for m in re.finditer(r"\+1?D6cm (?:extra Speed )?on All Ahead Full(?:\))?([^;.]*)", notes):
        if not re.match(r"\s*\(?[^;.]*\+\d+\s*pts", m.group(1)):
            return True
    return False


def convert_row(row: dict) -> dict:
    """One booklet roster row -> keyword arguments for ShipClassEntry, plus
    'unsupported' (reasons the engine can't play it yet; empty if playable)."""
    faction_id, _, ld_table = FACTIONS.get(row["faction"],
                                           (row["faction"].lower(), row["faction"], "Default"))
    problems: List[str] = []

    ship_type = _ship_type(row)
    if not ship_type:
        problems.append("hull type not recognised")
    armour = _armour(row)
    if not armour:
        problems.append(f"armour profile {row.get('armour_raw')} not modelled yet")
    from .eldar import parse_speeds, parse_holofield
    eldar_speeds = parse_speeds(row.get("speed_raw")) if row["faction"] == "Eldar" else None
    holo = parse_holofield(row.get("shields_raw")) if row["faction"] == "Eldar" else None
    notes0 = row.get("notes") or ""
    immobile = (ship_type == "defense" and row.get("speed_raw") == "-"
                and (notes0.startswith("Immobile") or row["name"] == "Blackstone Fortress"))
    if eldar_speeds or immobile:
        pass                          # MMS movement (src/eldar.py); immobile defences
    elif row.get("speed_cm") is None or row.get("turn_deg") is None:
        problems.append(f"special movement ({row.get('speed_raw')}, "
                        f"{row.get('turn_raw')}) not modelled yet")
    transport = transport_capacity(notes0) if (
        "Convoy ship" in notes0 or row.get("roster_group") == "Convoy Ships") else None
    if row.get("points") is None and not (transport and row.get("points_raw") == "Free"):
        problems.append(f"points cost '{row.get('points_raw')}' is not a fixed number")
    if not row["weapons"] and not (transport and ship_type in ("escort", "cruiser")):
        # unarmed convoy ships (Fast Clipper) are playable; their cargo is the point
        problems.append(f"no weapon profile ({row.get('armament_raw')})")
    if row["faction"] in UNBUILT_FACTION_RULES:
        problems.append(UNBUILT_FACTION_RULES[row["faction"]])

    if row["faction"] == "Imperial Navy":
        craft_map = dict(_IN_CRAFT)
    elif row["faction"] == "Tau & Allies" and "demiurg" not in (row.get("roster_group") or "").lower():
        craft_map = dict(_TAU_CRAFT)
    elif row["faction"] == "Eldar":
        craft_map = dict(_ELDAR_CRAFT)
    else:
        craft_map = {}
    if row["faction"] in MR_CRAFT:
        craft_map["MR"] = MR_CRAFT[row["faction"]]
    rows_w = row["weapons"]
    if row["faction"] == "Eldar":
        rows_w = [_eldar_bays(w) for w in rows_w]
    necron_extra = []
    if row["faction"] == "Necrons":
        keep = []
        for w in rows_w:
            raw = (w.get("raw") or "")
            pm = re.match(r"Portals? (\d+)cm S(\d+)", raw)
            if w.get("name") in ("Portals", "Portal") or pm:
                pm = pm or re.match(r"Portals? (\d+)cm S(\d+)", raw)
                # Portals replace the teleport attack (src/necrons.py): not a gun
                necron_extra.append({"name": "Portals", "weapon_type": "portal",
                                     "range_cm": int(pm.group(1)) if pm else 10,
                                     "strength": int(pm.group(2)) if pm else
                                     (w.get("value_int") or 1), "arcs": []})
            elif raw.startswith("Star Pulse Generator"):
                necron_extra.append({"name": "Star Pulse Generator", "weapon_type": "star_pulse",
                                     "range_cm": 20, "strength": 1, "arcs": []})
            else:
                keep.append(w)
        rows_w = keep
    weapons = [d for w in rows_w for d in _convert_weapon(w, craft_map, problems)]
    weapons += necron_extra
    if row["faction"] == "Necrons":
        for d in weapons:
            for k, flag in _NECRON_WEAPON_FLAGS.items():
                if k in d.get("name", ""):
                    d[flag] = True
    if row["faction"] == "Eldar":
        for d in weapons:
            src = next((k for k in _ELDAR_WEAPON_FLAGS if d.get("name", "").endswith(k)
                        or k in d.get("name", "")), None)
            if src:
                d[_ELDAR_WEAPON_FLAGS[src]] = True
    if "Chaos" in (row.get("faction_rules") or []):
        # Chaos: "any vessel with torpedo tubes is armed with both ordinary and
        # boarding torpedoes"
        for d in weapons:
            if d.get("weapon_type") == "torpedo" and d.get("torpedo_type") != "guided":
                d["boarding_torpedoes"] = True

    notes = row.get("notes") or ""
    group_notes = row.get("roster_group_notes") or ""
    special_rules = faction_special_rules(row)
    # Ponderous from the ship's notes or its roster group's (e.g. all Venerable
    # Battle Barges)
    if re.search(r"\bponderous\b", notes + " " + group_notes, re.I):
        special_rules.append("ponderous")
    if "towed" in (row.get("hull_type") or "").lower():
        special_rules.append("towed")
    if "Ablative Prow Armour" in notes:
        # Ignores Prow Armament Damaged crits; lost if prow torpedoes are taken
        special_rules.append("ablative_prow_armor")
    if ("Fra'al targeting matrix (free): treats all gunnery targets as closing" in notes
            or "Fra'al targeting matrix for no extra cost, allowing it to treat all gunnery "
               "targets as closing" in notes):
        special_rules.append("fraal_targeting")           # Fra'al Raider
    if "Chaos" in (row.get("faction_rules") or []):
        from .booklet_options import _built_in_csm
        special_rules += _built_in_csm(row)       # dedicated battleships
    if "Always rolls 3D6 on the Catastrophic Damage table" in notes:
        special_rules.append("catastrophic_3d6")          # Mercury
    if "Sensors +1 Ld at all times (max 10)" in notes:
        special_rules.append("ld_always:1")               # Emperor, Oberon
    special_rules += gravitic_hook_rules(row)
    if _has_built_in_thrusters(notes):
        # Sigils of Quickening are their own rule so a campaign Improved
        # Thrusters upgrade stacks with them (owner ruling)
        special_rules.append("sigils_of_quickening" if "Sigils of Quickening" in notes
                             else "improved_thrusters")
    if row.get("roster_group") in ("Venerable Battle Barges", "Venerable Strike Cruisers"):
        special_rules.append("venerable")         # VP 50% crippled / 125% destroyed
    if row.get("roster_group") == "Venerable Strike Cruisers":
        # "otherwise gains boarding torpedoes free"
        for d in weapons:
            if d.get("weapon_type") == "torpedo":
                d["boarding_torpedoes"] = True
    if "Grey Knights" in (row.get("faction_rules") or []):
        ld_table = "Astartes"          # Grey Knights use all Space Marine rules
    elif row.get("faction") == "Space Marines" and not row.get("faction_rules"):
        ld_table = "Default"           # Rapid Strike Vessels: no Space Marine rules
    fixed_ld = 0
    if "fleet_support" in special_rules:
        ld_table, fixed_ld = "", 7     # Fleet Support: Ld 7, not rolled
    m = re.search(r"Automated Ld (\d+)", notes)
    if m and "demiurg" in (row.get("roster_group") or "").lower() + group_notes.lower():
        # Demiurg commerce vessels: fixed Ld, -1 per point of damage (min 5)
        ld_table, fixed_ld = "", int(m.group(1))
        special_rules += ["demiurg_commerce", f"nominal_ld:{m.group(1)}"]
        vp = re.search(r"VP \d+ \((\d+) in the circumstances below\)", notes)
        if vp:
            special_rules.append(f"demiurg_vp:{vp.group(1)}")   # Demiurg VP
        if "modular" in (row.get("armament_raw") or "").lower():
            special_rules.append("modular_bays")
    if row["faction"] == "Necrons":
        from .necrons import parse_reactive_hull
        rh = parse_reactive_hull(row.get("shields_raw"))
        special_rules += ["necron"] + ([f"reactive_hull:{rh}"] if rh else [])
    if row["faction"] == "Eldar":
        # MMS v2.0 faction rules (src/eldar.py); Ghostships keep 6+ crits
        special_rules += ["eldar_mms", "fragile"] + (["holofield"] if holo is not None else [])
        if eldar_speeds:
            special_rules.append("eldar_speeds:" + "/".join(str(v) for v in eldar_speeds))
    if transport:
        cap, build_only = transport
        special_rules.append(f"transport:{cap:g}")
        if build_only:
            special_rules.append("transport_build_only")   # counts for fleet building only
    if immobile:
        # Immobile defences (Support Assets, Rulebook p.61-62): they never move
        special_rules.append("immobile")
        if (row.get("roster_group") or "").startswith("High Orbit") and (row.get("hits") or 0) >= 3:
            special_rules.append("space_station_crits")   # Appendix 3
    if re.search(r"\+5D6cm on All Ahead Full instead of \+3D6cm", notes):
        special_rules.append("aaf_5d6")      # Fast Clipper

    return {
        "ship_class": row["name"],
        "faction": faction_id,
        "ship_type": ship_type or "cruiser",
        "base_size": "large" if row.get("base") == "60mm" else "small",
        "speed": (max(eldar_speeds) if eldar_speeds else row.get("speed_cm") or 0),
        "turn_angle": row.get("turn_deg") or 0,
        "shields_max": (holo if holo is not None else row.get("shields") or 0),
        "armor_prow": armour[0] if armour else "",
        "armor_side": armour[1] if armour else "",
        "armor_rear": armour[2] if armour else "",
        "turrets": row.get("turrets") or 0,
        "hits_max": row.get("hits") or 0,
        "leadership": fixed_ld,          # 0: rolled at game start (Appendix 4)
        "weapons": weapons,
        "special_rules": special_rules,
        "points_cost": row.get("points") or 0,
        "leadership_table": ld_table,
        "notes": "" if notes == "-" else notes,
        "source": row.get("source") or "",
        "unsupported": sorted(set(problems)),
    }


def load_rows(path: str = SHIPS_JSON) -> List[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)["ships"]


# ── Venerable Strike Cruisers (Designing a Venerable Strike Cruiser, Imperium
#    p.137, in 03_space-marines.md) ─────────────────────────────────────────

def venerable_strike_cruiser_rows(rows: List[dict]) -> List[dict]:
    """A venerable strike cruiser "may be any non-unique grand cruiser,
    battlecruiser, or heavy cruiser from an Imperial Navy or Chaos list, at
    normal cost +25pts for its Space Marine crew", and is a Space Marine vessel
    in all respects. Its attack craft become Thunderhawks with each hangar's
    launch bay strength halved (rounding up, owner ruling); a nova cannon must be
    replaced by the Strike Cruiser Prow (6+ prow armour, prow torpedoes 30cm S6
    F; free with 6+ prow armour, otherwise +25pts) for 10pts less. The other
    refits are options (booklet_options.venerable_strike_cruiser_options)."""
    import copy
    out = []
    for row in rows:
        if row["faction"] not in ("Imperial Navy", "Chaos"):
            continue
        if not re.search(r"Grand Cruiser|Battlecruiser|Heavy Cruiser", row["name"]):
            continue
        if not isinstance(row.get("points"), int):       # export 18: "non-unique" removed
            continue
        v = copy.deepcopy(row)
        v["base_class"] = row["name"]
        v["name"] = f"Venerable Strike Cruiser ({row['name']})"
        v["faction"] = "Space Marines"
        v["faction_rules"] = ["Space Marines"]
        v["roster_group"] = "Venerable Strike Cruisers"
        v["roster_group_notes"] = None
        v["points"] = row["points"] + 25
        v["points_raw"] = str(v["points"])
        bays = [w for w in v["weapons"] if w.get("kind") == "launch_bays"]
        for w in bays:
            w["craft"] = [{"type": "MR", "speed_cm": 20}]       # Thunderhawks only
            for b in w["bays"]:
                # Owner ruling: each hangar is halved separately, rounding up
                if str(b.get("strength", "")).isdigit():
                    b["strength"] = str(-(-int(b["strength"]) // 2))
        v["weapons"] = [w for w in v["weapons"]
                        if not (w.get("kind") == "launch_bays" and not w["bays"])]
        if any("Nova" in (w.get("name") or "") for w in v["weapons"]):
            prow_six = (v.get("armour") or {}).get("front") == 6
            v["weapons"] = [w for w in v["weapons"] if w.get("location") != "Prow"]
            v["weapons"].append(STRIKE_CRUISER_PROW_ROW)
            v["points"] += (0 if prow_six else 25) - 10
            v["points_raw"] = str(v["points"])
            v["strike_cruiser_prow"] = True
            if v.get("armour"):
                v["armour"] = {**v["armour"], "front": 6}
        out.append(v)
    return out


STRIKE_CRUISER_PROW_ROW = {
    "kind": "weapon", "name": "Torps", "location": "Prow", "stat": "S", "value": "6",
    "value_int": 6, "range_max_cm": 30, "qualifier": "standard or boarding",
    "mounts": [{"arcs": ["F"]}], "category": "ordnance", "group": None,
    "raw": "Prow Torps 30cm S6 (F)", "parsed": True}

