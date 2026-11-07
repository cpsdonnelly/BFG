"""Ship options and fleet commanders from the booklet, as fleet-builder upgrades.

Owner ruling: booklet refits, options and fleet commanders are prose in each
ship's notes and get added one at a time. Each option is a dict that
ship_catalog turns into an UpgradeEntry:

  name, description, points_cost
  effect:        "stat_delta" {field: delta}, "set" {field: value},
                 "remove_weapons" [names], "add_weapons" [weapon dicts],
                 "add_special_rules" [rules], "rerolls" n, "flagship" True
  restrictions:  "group:<g>"      at most one option of group g per ship
                 "requires:<name>" needs that option on the same ship
                 "fleet_unique"   at most one ship in the fleet may take it
                 "sc_variant"     Strike Cruiser Variant: up to half the fleet's
                                  strike cruisers (round down) may take any
"""
from typing import Dict, List

from .chapter_tactics import TACTICS

_THUNDERHAWK_BAY = {"weapon_type": "launch_bay", "range_cm": 30, "strength": 1, "arcs": [],
                    "craft_types": ["thunderhawk"], "craft_speeds": {"thunderhawk": 20},
                    "craft_speed": 20}

# Tactical Flexibility: a Space Marine fleet with no Chapter tactic takes 10pts
# off each Strike Cruiser Variant refit (minimum 0). Variant costs below include
# it; a fleet whose Master of the Fleet takes a Chapter tactic pays the
# difference back (tactical_flexibility_refund).
TACTICAL_FLEXIBILITY = 10


def _variant_cost(pts: int) -> int:
    return max(0, pts - TACTICAL_FLEXIBILITY)


def space_marine_options(row: dict) -> List[Dict]:
    name = row["name"]
    opts: List[Dict] = []
    if name in ("Strike Cruiser", "Vanguard Cruiser"):
        opts.append({
            "name": "Secondary Shield (+1 Shield)",
            "description": "Any number may add +1 Shield for +15pts each.",
            "points_cost": 15, "effect": {"stat_delta": {"shields_max": 1}}})
    if name == "Strike Cruiser":
        opts += [
            {"name": "Variant: prow Bombardment Cannon",
             "description": "Swap prow launch bays for a Bombardment Cannon (30cm FP5 F), "
                            "+10pts (-10 Tactical Flexibility).",
             "points_cost": _variant_cost(10),
             "effect": {"remove_weapons": ["Launch Bays"],
                        "add_weapons": [{"name": "Prow Bombardment Cannon (refit)",
                                         "weapon_type": "battery", "range_cm": 30,
                                         "strength": 5, "arcs": ["front"],
                                         "hits_on": 4, "crit_on": 4}]},
             "restrictions": ["group:prow_bays", "sc_variant", "base_cost:10"]},
            {"name": "Variant: prow torpedoes",
             "description": "Swap prow launch bays for torps (30cm S6 F), free; may fire "
                            "standard or boarding torpedoes.",
             "points_cost": _variant_cost(0),
             "effect": {"remove_weapons": ["Launch Bays"],
                        "add_weapons": [{"name": "Prow Torps", "weapon_type": "torpedo",
                                         "range_cm": 30, "strength": 6, "arcs": ["front"],
                                         "torpedo_type": "standard", "torpedo_speed": 30,
                                         "boarding_torpedoes": True}]},
             "restrictions": ["group:prow_bays", "sc_variant", "base_cost:0"]},
            {"name": "Variant: macrobatteries to launch bays",
             "description": "Swap both macrobatteries for port and starboard launch bays "
                            "(1 Thunderhawk squadron each), +20pts (-10 Tactical Flexibility).",
             "points_cost": _variant_cost(20),
             "effect": {"remove_weapons": ["Port Macrobatteries", "Starboard Macrobatteries"],
                        "add_weapons": [dict(_THUNDERHAWK_BAY, name="Port Launch Bays"),
                                        dict(_THUNDERHAWK_BAY, name="Starboard Launch Bays")]},
             "restrictions": ["sc_variant", "base_cost:20"]},
        ]
    if row.get("hull_type") == "Battleship" or "Battle Barge" in name:
        mof = "Master of the Fleet (Ld 10)"
        opts += [
            {"name": mof,
             "description": "Fleet commander, 50pts (required at 750+ pts); rides a battle "
                            "barge. Ld 10.",
             "points_cost": 50,
             "effect": {"set": {"leadership": 10, "leadership_table": ""},
                        "add_special_rules": ["fleet_commander"], "flagship": True},
             "restrictions": ["fleet_unique"]},
        ] + [
            {"name": f"Master of the Fleet: {n} re-roll{'s' if n > 1 else ''}",
             "description": f"{n} fleet re-roll{'s' if n > 1 else ''} ({25 * n}pts).",
             "points_cost": 25 * n, "effect": {"rerolls": n},
             "restrictions": ["group:mof_rerolls", f"requires:{mof}"]}
            for n in (1, 2, 3)
        ] + [
            {"name": f"Chapter tactic: {label}",
             "description": ("+15pts. The Master of the Fleet's Chapter tactic, affecting all "
                             "relevant ships (replaces Tactical Flexibility)."),
             "points_cost": 15,
             "effect": {"add_special_rules": [f"chapter_tactic:{key}"]},
             "restrictions": ["group:chapter_tactic", f"requires:{mof}"]}
            for key, label in TACTICS.items()
        ] + [
            {"name": "Master of the Fleet: Terminator honour guard",
             "description": "+25pts. Double teleport range; teleport attacks roll 3D6 and "
                            "use the best two as two raids.",
             "points_cost": 25,
             "effect": {"add_special_rules": ["terminator_honour_guard"]},
             "restrictions": [f"requires:{mof}"]},
        ]
    return opts


def torpedo_strength(row: dict) -> int:
    """Total printed strength of a booklet ship's torpedo launchers."""
    return sum(int(w["value"]) for w in row.get("weapons") or []
               if w.get("kind") == "weapon" and "Torp" in (w.get("name") or "")
               and w.get("stat") == "S" and str(w.get("value", "")).isdigit())


def torpedo_type_options(row: dict) -> List[Dict]:
    """Imperial Navy and Chaos fleet lists: capital ships armed with torpedoes
    may take short burn, guided torpedoes or barrage bombs at +5 per torpedo
    strength, or the +50pt D3 roll. Owner ruling: one
    type per ship, carried in addition to its other torpedoes. (Guided
    torpedoes and anointed munitions aren't playable yet.)"""
    st = torpedo_strength(row)
    from .booklet_ships import _ship_type
    if not st or _ship_type(row) not in ("cruiser", "battleship"):
        return []                      # "any capital ship armed with torpedoes"
    opts = [{"name": f"Torpedoes: {label}",
             "description": f"Carried as well as its other torpedoes; chosen at each launch. "
                            f"+5pts per torpedo strength ({st}).",
             "points_cost": 5 * st,
             "effect": {"add_special_rules": [f"torpedo_type:{key}"]},
             "restrictions": ["group:torpedo_type"]}
            for key, label in (("short_burn", "short burn (40cm; out of fuel on a 6)"),
                               ("barrage", "barrage bombs (hits stopped by shields)"),
                               ("guided", "guided (turn 45° on a Leadership test)"))]
    # Chaos Anointed Munitions; Imperial Navy "+50 to roll once per game for
    # Seeking/Melta/Vortex" (owner ruling: per ship, the same D3 roll)
    name = ("Torpedoes: Anointed Munitions (D3 at game start)" if "Chaos" in row.get("faction_rules", [])
            else "Torpedoes: roll for Seeking / Melta / Vortex (D3 at game start)")
    opts.append({"name": name,
                 "description": "+50pts. At game start roll a D3: 1 Seeking, 2 Melta, 3 Vortex "
                                "torpedoes, as well as its other torpedoes; one salvo per game.",
                 "points_cost": 50,
                 "effect": {"add_special_rules": ["torpedo_roll:d3_anointed"]},
                 "restrictions": ["group:torpedo_type"]})
    return opts


_REFIT_TABLE = ("D6 at game start: 1 Short Burn, 2 Barrage Bombs, 3 Guided, 4 Seeking*, "
                "5 Melta*, 6 Vortex* (*one salvo per game), as well as its other torpedoes.")


def _ork_torps(dice: str) -> Dict:
    from .combat import dice_value_average
    return {"name": "Prow Torps", "weapon_type": "torpedo", "range_cm": 30,
            "strength": int(dice_value_average(dice)), "arcs": ["front"],
            "strength_dice": dice, "torpedo_type": "standard", "torpedo_speed": 30}


def ork_launcha_options(row: dict) -> List[Dict]:
    """Ork kroozers: "Replace prow heavy gunz with a prow torpedo launcha (30cm
    D6+N F) +Xpts" (Kill Kroozer: with the launcha, may drop both side heavy gunz
    to add +D6, 2D6+N, free). The zzapp gunz alternatives aren't playable yet."""
    import re
    notes = row.get("notes") or ""
    m = re.search(r"prow torpedo launcha \(30cm (D6\+\d+) F\) (free|\+(\d+)pts)", notes)
    if not m:
        return []
    dice, cost = m.group(1), int(m.group(3) or 0)
    opts = [{"name": f"Prow torpedo launcha ({dice})",
             "description": f"Replace the prow heavy gunz with a prow torpedo launcha "
                            f"(30cm S {dice}, F), {'free' if not cost else f'+{cost}pts'}.",
             "points_cost": cost,
             "effect": {"remove_weapons": ["Prow Heavy Gunz"], "add_weapon": _ork_torps(dice)},
             "restrictions": ["group:ork_prow"]}]
    if "may drop both side heavy gunz to add +D6" in notes:
        big = "2" + dice
        opts.append({"name": f"Prow torpedo launcha ({big}, no side heavy gunz)",
                     "description": f"The torpedo launcha with both side heavy gunz dropped to "
                                    f"add +D6 (30cm S {big}, F), +{cost}pts.",
                     "points_cost": cost,
                     "effect": {"remove_weapons": ["Prow Heavy Gunz", "Port Heavy Gunz",
                                                   "Starboard Heavy Gunz"],
                                "add_weapon": _ork_torps(big)},
                     "restrictions": ["group:ork_prow"]})
    return opts


INQ_LORD = "Ordo Malleus Inquisitor Lord (Ld 10)"
INQ_TORPS = "Refit: launch bays to Torpedo Salvo"


def inquisition_options(row: dict) -> List[Dict]:
    """Inquisition vessels: the Inquisitorial Cruiser's special refits (no
    change in cost), the Ordo Malleus Inquisitor Lord (Banisher Fleet: Ld 10,
    75pts, one free re-roll), Inferno Torpedoes (+20pts, owner ruling) and
    vortex torpedoes on the Inquisitor Lord's ship if it has torpedoes (+50pts,
    owner ruling)."""
    name = row["name"]
    opts: List[Dict] = []
    has_torps = bool(torpedo_strength(row))
    if name == "Inquisitorial Cruiser":
        opts += [
            {"name": "Refit: dorsal lances to Bombardment Cannon",
             "description": "No change in cost: Bombardment Cannon 30cm FP6 (L/F/R), the "
                            "Space Marine bombardment cannon rules.",
             "points_cost": 0,
             "effect": {"remove_weapons": ["Dorsal Lances"],
                        "add_weapon": {"name": "Dorsal Bombardment Cannon", "weapon_type": "battery",
                                       "range_cm": 30, "strength": 6,
                                       "arcs": ["left", "front", "right"],
                                       "hits_on": 4, "crit_on": 4}}},
            {"name": INQ_TORPS,
             "description": "No change in cost: Torpedo Salvo 30cm S6 (F), standard or "
                            "boarding torpedoes.",
             "points_cost": 0,
             "effect": {"remove_weapons": ["Launch Bays"],
                        "add_weapon": {"name": "Prow Torpedo Salvo", "weapon_type": "torpedo",
                                       "range_cm": 30, "strength": 6, "arcs": ["front"],
                                       "torpedo_type": "standard", "torpedo_speed": 30,
                                       "boarding_torpedoes": True}}},
        ]
    capital = row.get("hits") and row.get("hits") > 1 and "Grey Knights" not in name
    if capital:
        opts.append({"name": INQ_LORD,
                     "description": "Fleet commander (Banisher Fleet), 75pts: Ld 10, one free "
                                    "re-roll.",
                     "points_cost": 75,
                     "effect": {"set": {"leadership": 10, "leadership_table": ""},
                                "rerolls": 1,
                                "add_special_rules": ["fleet_commander"], "flagship": True},
                     "restrictions": ["fleet_unique"]})
        opts += [{"name": f"Inquisitor Lord: {n} extra re-roll{'s' if n > 1 else ''}",
                  "description": f"{n} more fleet commander re-roll{'s' if n > 1 else ''} "
                                 f"({25 * n}pts).",
                  "points_cost": 25 * n, "effect": {"rerolls": 1 + n},
                  "restrictions": ["group:inq_rerolls", f"requires:{INQ_LORD}"]}
                 for n in (1, 2)]
    torp_needs = [] if has_torps else ([f"requires:{INQ_TORPS}"] if name == "Inquisitorial Cruiser"
                                       else None)
    if torp_needs is not None:
        opts.append({"name": "Inferno Torpedoes",
                     "description": "+20pts (Ordo Hereticus). Melta torpedoes usable any number "
                                    "of times, as well as its other torpedoes; a torpedo-launcher "
                                    "critical hit inflicts D6 Fire results.",
                     "points_cost": 20,
                     "effect": {"add_special_rules": ["torpedo_type:inferno"]},
                     "restrictions": ["group:torpedo_type"] + torp_needs})
        if capital:
            opts.append({"name": "Vortex Torpedoes (Inquisitor Lord's ship)",
                         "description": "+50pts (Ordo Malleus). Vortex torpedoes, one salvo per "
                                        "game, as well as its other torpedoes.",
                         "points_cost": 50,
                         "effect": {"add_special_rules": ["torpedo_type:vortex"]},
                         "restrictions": ["group:torpedo_type", f"requires:{INQ_LORD}"]
                         + torp_needs})
    return opts


def refitted_torpedo_options(row: dict) -> List[Dict]:
    """Adeptus Mechanicus "refitted torpedoes +Npts" and Ork "torps to looted
    torps +20pts" in a ship's notes: a D6 roll at game start (owner ruling for
    Orks: each ship that buys them rolls)."""
    import re
    notes = row.get("notes") or ""
    launcha = ork_launcha_options(row)
    if launcha:
        opts = launcha
        m = re.search(r"torps to looted torps \+(\d+)pts", notes)
        if m:
            opts.append({"name": "Looted Torpedoes (D6 at game start)",
                         "description": f"+{m.group(1)}pts. Needs the torpedo launcha. {_REFIT_TABLE}",
                         "points_cost": int(m.group(1)),
                         "effect": {"add_special_rules": ["torpedo_roll:d6_refitted"]},
                         "restrictions": ["group:torpedo_type", "requires_any:"
                                          + "|".join(o["name"] for o in launcha)]})
        return opts
    if not torpedo_strength(row) and not any(
            "Torp" in (w.get("name") or "") for w in row.get("weapons") or []):
        return []
    m = re.search(r"refitted torpedoes \+(\d+)pts", notes)
    if m:
        return [{"name": "Refitted Torpedoes (D6 at game start)",
                 "description": f"+{m.group(1)}pts. {_REFIT_TABLE}",
                 "points_cost": int(m.group(1)),
                 "effect": {"add_special_rules": ["torpedo_roll:d6_refitted"]},
                 "restrictions": ["group:torpedo_type"]}]
    m = re.search(r"torps to looted torps \+(\d+)pts", notes)
    if m:
        return [{"name": "Looted Torpedoes (D6 at game start)",
                 "description": f"+{m.group(1)}pts. {_REFIT_TABLE}",
                 "points_cost": int(m.group(1)),
                 "effect": {"add_special_rules": ["torpedo_roll:d6_refitted"]},
                 "restrictions": ["group:torpedo_type"]}]
    return []


VSC_PROW = "Strike Cruiser Prow"


def venerable_strike_cruiser_options(row: dict) -> List[Dict]:
    """Designing a Venerable Strike Cruiser (Imperium p.137): the Strike
    Cruiser Prow (6+ prow armour and prow torpedoes 30cm S6 F, replacing any
    prow armament; free with 6+ prow armour, otherwise +25pts; already fitted
    on nova cannon ships), and short-burn torpedoes +5pts or barrage bombs
    +10pts instead of the free boarding torpedoes. Its own profile's refits
    can't be used."""
    opts: List[Dict] = []
    has_torps = bool(torpedo_strength(row))
    if not row.get("strike_cruiser_prow"):
        prow = [f"Prow {w['name']}" for w in row.get("weapons") or [] if w.get("location") == "Prow"]
        six = (row.get("armour") or {}).get("front") == 6
        opts.append({
            "name": VSC_PROW,
            "description": "6+ prow armour and prow torpedoes (30cm S6 F, standard or boarding), "
                           "replacing any prow armament; "
                           + ("free (already 6+ prow armour)." if six else "+25pts."),
            "points_cost": 0 if six else 25,
            "effect": {"remove_weapons": prow,
                       "add_weapon": {"name": "Prow Torps", "weapon_type": "torpedo",
                                      "range_cm": 30, "strength": 6, "arcs": ["front"],
                                      "torpedo_type": "standard", "torpedo_speed": 30,
                                      "boarding_torpedoes": True},
                       "set": {"armor_prow": "6+"}},
        })
    needs = [] if has_torps or row.get("strike_cruiser_prow") else [f"requires:{VSC_PROW}"]
    for key, label, cost in (("short_burn", "short burn torpedoes", 5),
                             ("barrage", "barrage bombs", 10)):
        opts.append({
            "name": f"Torpedoes: {label} (instead of boarding torpedoes)",
            "description": f"+{cost}pts.",
            "points_cost": cost,
            "effect": {"add_special_rules": [f"torpedo_type:{key}", "no_boarding_torps"]},
            "restrictions": ["group:torpedo_type"] + needs})
    return opts


def options_for(row: dict) -> List[Dict]:
    """Options for one booklet ship (Space Marine options, Imperial Navy and
    Chaos torpedo types so far)."""
    rules = row.get("faction_rules") or []
    if row.get("roster_group") == "Venerable Strike Cruisers":
        return venerable_strike_cruiser_options(row)
    if "Space Marines" in rules:
        return space_marine_options(row)
    if "Imperial Navy" in rules or "Chaos" in rules:
        return torpedo_type_options(row)
    if "Adeptus Mechanicus" in rules or "Orks" in rules:
        return refitted_torpedo_options(row)
    if "Inquisition & Grey Knights" in rules:
        return inquisition_options(row)
    return []


def ship_option_errors(entry, chosen: List[str]) -> List[str]:
    """Problems with one ship's chosen options: two from one group, or an
    option without the one it requires."""
    by_name = {u.name: u for u in entry.upgrades_available}
    errors, groups = [], {}
    for name in chosen:
        u = by_name.get(name)
        if u is None:
            continue
        for r in u.restrictions:
            if r.startswith("group:"):
                groups.setdefault(r[6:], []).append(name)
            elif r.startswith("requires:") and r[9:] not in chosen:
                errors.append(f"{name} needs {r[9:]}.")
            elif r.startswith("requires_any:"):
                need = r[len("requires_any:"):].split("|")
                if not any(n in chosen for n in need):
                    errors.append(f"{name} needs one of: {', '.join(need)}.")
    for names in groups.values():
        if len(names) > 1:
            errors.append(f"Choose only one of: {', '.join(names)}.")
    return errors


def fleet_option_errors(rows: List[tuple], total_points: int = 0) -> List[str]:
    """Fleet-wide option limits. rows: (ShipClassEntry, chosen option names).
    One Master of the Fleet (required at 750+ pts in a Space Marine fleet), and
    Strike Cruiser Variants on at most half the fleet's strike cruisers (round
    down)."""
    errors = []
    restr = [(e, n, r) for e, chosen in rows for n in chosen
             for u in e.upgrades_available if u.name == n for r in u.restrictions]
    unique = {}
    for e, n, r in restr:
        if r == "fleet_unique":
            unique[n] = unique.get(n, 0) + 1
    for n, c in unique.items():
        if c > 1:
            errors.append(f"Only one ship may take {n} ({c} chosen).")
    strike = [chosen for e, chosen in rows if e.ship_class == "Strike Cruiser"]
    with_variant = sum(1 for chosen in strike if any(n.startswith("Variant:") for n in chosen))
    if with_variant > len(strike) // 2:
        errors.append(f"Strike Cruiser Variants: at most {len(strike) // 2} of the fleet's "
                      f"{len(strike)} strike cruisers (half, round down); {with_variant} chosen.")
    sm = [e for e, _ in rows if "space_marine_crew" in e.special_rules]
    if sm and len(sm) == len(rows) and total_points >= 750 and not unique.get(
            "Master of the Fleet (Ld 10)"):
        errors.append("A Space Marine fleet of 750+ pts needs a Master of the Fleet "
                      "(option on a battle barge).")
    return errors


def tactical_flexibility_refund(fleet_upgrades: List[List[str]], entries) -> int:
    """Points to add back when the fleet takes a Chapter tactic: its Strike
    Cruiser Variant refits lose the Tactical Flexibility discount.
    fleet_upgrades: each ship's chosen options; entries: the matching
    ShipClassEntry objects."""
    if not any(n.startswith("Chapter tactic:") for ups in fleet_upgrades for n in ups):
        return 0
    extra = 0
    for ups, entry in zip(fleet_upgrades, entries):
        for u in entry.upgrades_available:
            if u.name in ups:
                for r in u.restrictions:
                    if r.startswith("base_cost:"):
                        extra += int(r[10:]) - u.points_cost
    return extra
