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


def options_for(row: dict) -> List[Dict]:
    """Options for one booklet ship (only ships following Space Marine rules so far)."""
    if "Space Marines" in (row.get("faction_rules") or []):
        return space_marine_options(row)
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
