"""Space Marine Chapter Tactics (Space Marines faction rules, Ships of the
Imperium p.133). The Master of the Fleet may take one; it affects all relevant
ships. The fleet builder records it on the Master of the Fleet's ship as the
special rule "chapter_tactic:<key>"; apply_fleet_tactics copies it to every ship
of that player that follows Space Marine rules at game start."""
import math
from typing import List, Optional

TACTICS = {
    "dark_age_plasma": "Dark Age Plasma Batteries",
    "lightning_thrusters": "Lightning Thrusters",
    "pack_hunter": "Pack Hunter Protocols",
    "siege_cannons": "Siege Cannons",
    "wings_of_fury": "Wings of Fury",
    "shadow_engines": "Shadow Engines",
    "tactical_reserves": "Tactical Reserves",
    "promethean_unguents": "Promethean Unguents",
    "machine_spirit": "Heed the Machine Spirit",
}
PREFIX = "chapter_tactic:"

_SIZE = {"escort": 0, "cruiser": 1, "battleship": 2}


def tactic_rule(key: str) -> str:
    return PREFIX + key


def has_tactic(ship, key: str) -> bool:
    return tactic_rule(key) in (getattr(ship, "special_rules", None) or [])


def is_battle_barge(ship) -> bool:
    return ship.ship_type == "battleship" and "space_marine_crew" in ship.special_rules


def is_strike_cruiser(ship) -> bool:
    return "Strike Cruiser" in ship.ship_class


def is_vanguard(ship) -> bool:
    return "Vanguard Cruiser" in ship.ship_class


def apply_fleet_tactics(gs) -> List[str]:
    """Copy each player's Chapter tactic to all their Space Marine ships and
    apply its fixed effects: Dark Age Plasma Batteries (capital ships' Speed at
    most 20cm) and Wings of Fury (Thunderhawks 30cm)."""
    logs = []
    for player in (1, 2):
        ships = [s for s in gs.ships if s.get("player") == player]
        tags = {r for s in ships for r in s.get("special_rules", []) if r.startswith(PREFIX)}
        if not tags:
            continue
        tag = sorted(tags)[0]
        key = tag[len(PREFIX):]
        for s in ships:
            if "space_marine_crew" not in s.get("special_rules", []):
                continue
            # No Tactical Flexibility: variant refits are worth their full cost
            s["points_value"] = s.get("points_value", 0) + _variant_refund(s)
            if tag not in s["special_rules"]:
                s["special_rules"] = list(s["special_rules"]) + [tag]
            if key == "dark_age_plasma" and s.get("ship_type") != "escort":
                s["speed"] = min(s.get("speed", 0), 20)
            if key == "wings_of_fury":
                for w in s.get("weapons", []):
                    if "thunderhawk" in (w.get("craft_speeds") or {}):
                        w["craft_speeds"] = {**w["craft_speeds"], "thunderhawk": 30}
        logs.append(f"Player {player} Chapter tactic: {TACTICS.get(key, key)}")
    return logs


def _variant_refund(ship_dict) -> int:
    from .ship_catalog import find_ship_class
    entry = find_ship_class(ship_dict.get("ship_class", ""))
    if entry is None:
        return 0
    from .booklet_options import tactical_flexibility_refund
    ups = list(ship_dict.get("upgrades", []))
    return tactical_flexibility_refund([ups + ["Chapter tactic:"]], [entry])


# ── Dark Age Plasma Batteries ────────────────────────────────────────────────

def dark_age_batteries(ship, weapon) -> bool:
    """Capital ship macrobatteries (not bombardment cannons) of a ship that has
    moved no more than 10cm this turn: 45cm range, no right column shift for
    targets beyond 30cm."""
    return (has_tactic(ship, "dark_age_plasma") and ship.ship_type != "escort"
            and weapon.get("weapon_type") == "battery" and not weapon.get("hits_on")
            and ship.distance_moved_this_turn <= 10)


def weapon_range(ship, weapon) -> float:
    r = weapon.get("range_cm", 0)
    if r and dark_age_batteries(ship, weapon):
        return max(r, 45)
    return r


# ── Lightning Thrusters ──────────────────────────────────────────────────────

def lightning_vanguard(ship) -> bool:
    return has_tactic(ship, "lightning_thrusters") and is_vanguard(ship)


# ── Pack Hunter Protocols ────────────────────────────────────────────────────

def pack_hunter_bonus(attackers, target) -> int:
    """+1 troop rating per escort / vanguard cruiser boarding a larger ship
    together with only members of its own squadron."""
    if len(attackers) < 2:
        return 0
    sq = {a.squadron_id for a in attackers}
    if len(sq) != 1 or not next(iter(sq)):
        return 0
    if not all(has_tactic(a, "pack_hunter") and (a.ship_type == "escort" or is_vanguard(a))
               for a in attackers):
        return 0
    if all(_SIZE.get(target.ship_type, 1) > _SIZE.get(a.ship_type, 1) for a in attackers):
        return len(attackers)
    return 0


# ── Siege Cannons ────────────────────────────────────────────────────────────

def siege_ship(ship) -> bool:
    return has_tactic(ship, "siege_cannons") and (is_battle_barge(ship) or is_strike_cruiser(ship))


def siege_alone_shift(ship, weapon) -> int:
    """A ship with bombardment cannons firing its macrobatteries on their own
    suffers an extra right column shift."""
    if (siege_ship(ship) and weapon.get("weapon_type") == "battery" and not weapon.get("hits_on")
            and any(w.get("hits_on") for w in ship.weapons)):
        return 1
    return 0


# ── Shadow Engines ───────────────────────────────────────────────────────────

def shadow_engines_hidden(attacker, target, candidates) -> bool:
    """Escorts with Shadow Engines can't be targeted by lances or gunnery beyond
    30cm unless they are the closest target (regardless of target priority)."""
    if not (has_tactic(target, "shadow_engines") and target.ship_type == "escort"):
        return False
    d = attacker.distance_to(target)
    if d <= 30:
        return False
    nearest = min((attacker.distance_to(c) for c in candidates), default=d)
    return d > nearest + 1e-6


# ── Tactical Reserves ────────────────────────────────────────────────────────

def tactical_reserves_barge(ship) -> bool:
    return has_tactic(ship, "tactical_reserves") and is_battle_barge(ship)


def reduce_for_movement_order(ship, fp: int, gunnery: bool) -> int:
    """Firepower on All Ahead Full / Burn Retros / Come to New Heading: halved
    (rounding up). Tactical Reserves battle barges lose only 25% (rounding up)
    of their gunnery weapons on All Ahead Full or Burn Retros."""
    if (gunnery and tactical_reserves_barge(ship)
            and ship.special_order in ("all_ahead_full", "burn_retros")):
        return math.ceil(fp * 0.75)
    return (fp + 1) // 2


# ── Heed the Machine Spirit ──────────────────────────────────────────────────

def machine_spirit_ship(ship) -> bool:
    return has_tactic(ship, "machine_spirit") and ship.ship_type != "escort"


def fleet_tactic(ships) -> Optional[str]:
    for s in ships:
        for r in getattr(s, "special_rules", []) or []:
            if r.startswith(PREFIX):
                return r[len(PREFIX):]
    return None
