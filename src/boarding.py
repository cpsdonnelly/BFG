"""BFG:XR Boarding Actions

Boarding is declared during the movement phase when an attacker moves into base
contact with an enemy. Resolution occurs in the attacker's end phase (before damage
control) if the ships are still in contact.

Multi-ship boarding: several attackers may pool their troop ratings against one target.
If the attacking group loses, the owning player distributes damage across attackers.
While grappled in a drawn combat, ships cannot move, fire, launch ordnance, or
disengage. Turrets are not added to the troop rating while grappled.

Ships reduced to 0 damage by boarding become drifting hulks (no catastrophic roll).
"""

from typing import List, Dict, Optional, Tuple
from .models import Ship
from .game_state import GameState
from .dice import DiceRoller
from .tables import BOARDING_RESULTS
from .geometry import count_blast_markers_touching


_TROOP_BONUS_TABLE = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4}  # floored at 0, capped at 4


def troop_rating(ship: Ship, grappled: bool = False) -> int:
    """Return a ship's troop rating: hits_remaining (+ turrets if not grappled)."""
    if ship.hits_remaining <= 0:
        return 0
    t = 0 if grappled else ship.turrets
    return ship.hits_remaining + t


def _troop_advantage_bonus(attacker_rating: int, defender_rating: int) -> int:
    if attacker_rating <= 0 or defender_rating <= 0:
        return 0
    ratio = attacker_rating / defender_rating
    if ratio >= 4:
        return 4
    if ratio >= 3:
        return 3
    if ratio >= 2:
        return 2
    if ratio > 1:
        return 1
    return 0


def _crew_damage_bonus(ship: Ship) -> int:
    """Faction-specific boarding bonus. Extend per-faction rules here."""
    return 0


def _get_ship_modifier(ship: Ship, gs: GameState) -> int:
    """Return sum of modifiers that apply to the OPPONENT's roll due to this ship's status."""
    mod = 0
    if ship.is_crippled:
        mod += 2
    if ship.special_order not in ("none", ""):
        mod += 1
    blast_markers = gs.get_blast_markers()
    touching = count_blast_markers_touching(ship, blast_markers)
    if touching > 0:
        mod += 1
    return mod


def _boarding_crit_check(ship: Ship, threshold: Optional[int],
                          dice: DiceRoller, gs: GameState) -> Optional[Dict]:
    """Roll 1D6 for a boarding crit check. Return the applied crit or None."""
    from .hit_and_run import _apply_raid_crit
    if threshold is None:
        return None
    if threshold == 0:
        # Auto-crit: use a fresh roll to determine which crit
        roll = dice.roll_d6(1, f"Auto boarding crit on {ship.name}")[0]
        # Clamp to 2 (minimum valid crit roll on the raid crit table)
        roll = max(2, roll)
        return _apply_raid_crit(roll, ship, gs, dice)
    roll = dice.roll_d6(1, f"Boarding crit check on {ship.name} (need {threshold}+)")[0]
    gs.add_log(f"  {ship.name} crit check: rolled {roll} (need {threshold}+)")
    if roll >= threshold:
        crit_roll = max(2, dice.roll_d6(1, f"Boarding crit type on {ship.name}")[0])
        return _apply_raid_crit(crit_roll, ship, gs, dice)
    return None


def resolve_boarding(attackers: List[Ship], target: Ship,
                     dice: DiceRoller, gs: GameState) -> Dict:
    """Resolve a boarding action between one or more attackers and a target.

    Returns a summary dict:
      {
        "attacker_roll": int,       # total roll for attacker side
        "defender_roll": int,       # total roll for defender side
        "winner": str,              # "attacker" | "defender" | "draw"
        "damage": int,              # damage applied to loser (0 on draw)
        "loser_ships": List[Ship],  # ships that take the damage (defenders or attackers)
        "attacker_crits": List,     # crits applied to attacker ships
        "defender_crits": List,     # crits applied to target
        "grapple": bool,            # True if combat was a draw
      }
    """
    # Troop ratings
    a_rating = sum(troop_rating(a, a.is_grappled) for a in attackers)
    d_rating = troop_rating(target, target.is_grappled)

    # Modifiers: each ship's weaknesses add to the OPPONENT's roll
    # Attacker's modifiers (from target's perspective)
    a_mod = _get_ship_modifier(target, gs)
    # Defender's modifiers (from attackers' perspective)
    d_mod = max(_get_ship_modifier(a, gs) for a in attackers)

    a_troop_bonus = _troop_advantage_bonus(a_rating, d_rating)
    d_troop_bonus = _troop_advantage_bonus(d_rating, a_rating)
    a_crew = max(_crew_damage_bonus(a) for a in attackers)
    d_crew = _crew_damage_bonus(target)

    a_roll = dice.roll_d6(1, "boarding attacker roll")[0]
    d_roll = dice.roll_d6(1, "boarding defender roll")[0]

    a_total = a_roll + a_mod + a_troop_bonus + a_crew
    d_total = d_roll + d_mod + d_troop_bonus + d_crew

    gs.add_log(
        f"  Boarding: {'+'.join(a.name for a in attackers)} vs {target.name}")
    gs.add_log(
        f"  Attacker: {a_roll}+{a_mod}(mods)+{a_troop_bonus}(troops)"
        f"+{a_crew}(crew) = {a_total}  |  "
        f"Defender: {d_roll}+{d_mod}(mods)+{d_troop_bonus}(troops)"
        f"+{d_crew}(crew) = {d_total}")

    summary: Dict = {
        "attacker_roll": a_total,
        "defender_roll": d_total,
        "winner": "draw",
        "damage": 0,
        "loser_ships": [],
        "attacker_crits": [],
        "defender_crits": [],
        "grapple": False,
    }

    diff = abs(a_total - d_total)
    crit_key = min(diff, 5)
    crit_row = BOARDING_RESULTS.get(crit_key, BOARDING_RESULTS[5])

    if a_total > d_total:
        summary["winner"] = "attacker"
        summary["damage"] = diff
        summary["loser_ships"] = [target]
        # Apply damage to target — ignores shields and brace
        _apply_boarding_damage(target, diff, gs)
        gs.add_log(f"  Attackers WIN by {diff} — {target.name} takes {diff} damage")
        attacker_crit = _boarding_crit_check(
            attackers[0], crit_row["winner_crit"], dice, gs)
        if attacker_crit:
            summary["attacker_crits"].append(attacker_crit)
        defender_crit = _boarding_crit_check(target, crit_row["loser_crit"], dice, gs)
        if defender_crit:
            summary["defender_crits"].append(defender_crit)

    elif d_total > a_total:
        summary["winner"] = "defender"
        summary["damage"] = diff
        summary["loser_ships"] = list(attackers)
        # Losing attackers distribute damage (player's choice handled in UI)
        # For pure logic: apply evenly, remainder to first attacker
        _distribute_boarding_damage(attackers, diff, gs)
        gs.add_log(f"  Defender WINS by {diff} — attackers take {diff} total damage")
        defender_crit = _boarding_crit_check(
            target, crit_row["winner_crit"], dice, gs)
        if defender_crit:
            summary["defender_crits"].append(defender_crit)
        for attacker in attackers:
            a_crit = _boarding_crit_check(attacker, crit_row["loser_crit"], dice, gs)
            if a_crit:
                summary["attacker_crits"].append(a_crit)

    else:
        # Draw — grapple
        summary["grapple"] = True
        gs.add_log("  Boarding DRAW — ships grapple! Combat repeats each end phase.")
        # Still apply crit checks on a draw (both treated as if diff=1 each side)
        draw_row = BOARDING_RESULTS[1]
        for attacker in attackers:
            a_crit = _boarding_crit_check(attacker, draw_row["winner_crit"], dice, gs)
            if a_crit:
                summary["attacker_crits"].append(a_crit)
        d_crit = _boarding_crit_check(target, draw_row["winner_crit"], dice, gs)
        if d_crit:
            summary["defender_crits"].append(d_crit)

    return summary


def _apply_boarding_damage(ship: Ship, damage: int, gs: GameState) -> None:
    """Apply boarding damage directly to hull — ignores shields and brace.
    If ship reaches 0, marks as drifting_hulk (no catastrophic roll).
    """
    ship.hits_remaining = max(0, ship.hits_remaining - damage)
    if ship.hits_remaining <= 0:
        ship.status = "drifting_hulk"
        gs.add_log(f"  {ship.name} overwhelmed — drifting hulk (no explosion roll)")
    gs.update_ship(ship)


def _distribute_boarding_damage(attackers: List[Ship], total_damage: int,
                                 gs: GameState) -> None:
    """Distribute boarding damage across attacking ships (evenly, remainder to first)."""
    if not attackers:
        return
    per_ship = total_damage // len(attackers)
    remainder = total_damage % len(attackers)
    for i, ship in enumerate(attackers):
        dmg = per_ship + (remainder if i == 0 else 0)
        if dmg > 0:
            _apply_boarding_damage(ship, dmg, gs)


def ships_in_base_contact(ship_a: Ship, ship_b: Ship) -> bool:
    """True if the bases of two ships are touching."""
    from .geometry import BASE_CONTACT_MARGIN_CM
    dist = ship_a.distance_to(ship_b)
    return dist <= ship_a.base_radius + ship_b.base_radius + BASE_CONTACT_MARGIN_CM


def contiguous_contact_groups(ships: List[Ship]) -> List[List[Ship]]:
    """Partition `ships` into connected components by base contact.

    Two ships are connected if their bases touch; a group is the transitive
    closure of that relation. Returns every component, including singletons.
    Input order is preserved within each group.
    """
    visited = set()
    groups: List[List[Ship]] = []
    for start in ships:
        if start.id in visited:
            continue
        group: List[Ship] = []
        stack = [start]
        while stack:
            current = stack.pop()
            if current.id in visited:
                continue
            visited.add(current.id)
            group.append(current)
            for other in ships:
                if other.id not in visited and ships_in_base_contact(current, other):
                    stack.append(other)
        group.sort(key=lambda s: ships.index(s))
        groups.append(group)
    return groups
