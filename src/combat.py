"""BFG:XR Combat System - Shooting phase resolution"""
import math
import random
import re
from typing import List, Dict, Tuple, Optional
from .models import Ship, BlastMarker, Arc, SpecialOrder
from .game_state import GameState
from .tables import (lookup_gunnery_dice, get_gunnery_column, CRITICAL_HITS,  # noqa: F401 (re-exported)
                     lookup_catastrophic)
from .dice import DiceRoller
from .geometry import (current_shields,
                       EXPLOSION_BLAST_OFFSET_CM,
                       NOVA_CANNON_TEMPLATE_RADIUS_CM,
                       NOVA_CANNON_CENTER_HOLE_RADIUS_CM)
from .los import check_los_ships


class ShotResult:
    """Result of a single weapon firing."""
    def __init__(self, weapon_name: str, weapon_type: str):
        self.weapon_name = weapon_name
        self.weapon_type = weapon_type
        self.dice_rolled: List[int] = []
        self.reroll_dice: List[int] = []
        self.hits = 0
        self.hits_on_shields = 0
        self.hits_on_hull = 0
        self.critical_results: List[Dict] = []
        self.brace_saves = 0
        self.description = ""
        self.hits_by_ship: Dict[str, int] = {}  # ship_id → hits for squadron fire



def check_weapon_in_arc(ship: Ship, weapon: Dict, target_x: float, target_y: float) -> bool:
    """Check if target is within the weapon's fire arc."""
    target_arc = ship.get_target_arc(target_x, target_y)
    weapon_arcs = weapon.get("arcs", [])
    # Launch bays and some weapons have no arc restriction
    if not weapon_arcs:
        return True
    return target_arc.value in weapon_arcs


def check_weapon_in_range(ship: Ship, weapon: Dict,
                          target_x: float, target_y: float) -> bool:
    """Check if target is within weapon range."""
    dist = math.sqrt((ship.x - target_x)**2 + (ship.y - target_y)**2)
    from .chapter_tactics import weapon_range
    w_range = weapon_range(ship, weapon)     # Dark Age Plasma Batteries: 45cm
    if w_range == 0:
        return True  # torpedoes/bays don't have a direct fire range
    return dist <= w_range


def get_column_shifts(ship: Ship, target_ship: Ship,
                      blast_markers: List[BlastMarker],
                      phenomena: list = None,
                      all_ships: list = None,
                      weapon: Optional[Dict] = None) -> int:
    """Calculate gunnery column shifts for weapons batteries."""
    from .chapter_tactics import dark_age_batteries, siege_alone_shift
    dist = ship.distance_to(target_ship)
    shifts = 0

    # Range modifiers (Dark Age Plasma Batteries: no shift beyond 30cm).
    # Fighting Sunward (s.40): firing towards the sunward edge doubles them
    from .optional_rules import sunward_edge
    edge = sunward_edge()
    from .celestial import is_sunward
    rng = 2 if edge and is_sunward(ship, target_ship, edge) else 1
    if dist < 15:
        shifts -= rng  # left shift (better)
    elif (dist > 30 and not (weapon and dark_age_batteries(ship, weapon))
          and "fraal_targeting" not in ship.special_rules):     # Fra'al targeting matrix
        shifts += rng  # right shift (worse)

    # Siege Cannons: macrobatteries fired on their own shift right
    if weapon:
        shifts += siege_alone_shift(ship, weapon)

    # LoS-based shifts (blast markers and dust clouds in line of fire)
    phenomena = phenomena or []
    los = check_los_ships(ship, target_ship, phenomena, blast_markers)
    # Optional Modern / Remastered blast markers (s.11): targets in contact count
    # as behind them, and in Remastered a firing ship in contact shifts too
    from .optional_rules import blast_gunnery_shift
    # Owner ruling: blast markers and dust clouds in the way give one shift
    # between them (los column_shifts is 0 or 1); in contact (Modern /
    # Remastered) it is still at most one
    line = los.get("column_shifts", 0)
    shifts += blast_gunnery_shift(ship, target_ship, line, blast_markers, all_ships)

    # Targeting matrix upgrade (Imperial Mars)
    if "targeting_matrix" in ship.special_rules:
        shifts -= 1

    # Eldar (MMS p.4): holofields force a right shift, not under 15cm; Eldar
    # weapons batteries gain a left shift
    if "holofield" in target_ship.special_rules and dist >= 15:
        shifts += 1
    if weapon and weapon.get("eldar_battery"):
        shifts -= 1

    # Pleasure Fleet of Slaanesh, Veil of Lust: an automatic right shift
    if "veil_of_lust" in target_ship.special_rules:
        shifts += 1
    # Plague Fleet of Nurgle, Miasma of Pestilence: no left shift within 15cm
    if "miasma" in target_ship.special_rules and dist < 15:
        shifts += rng

    # Advanced Shields (Mechanicus Gift): a right shift while its shields are up
    if ("advanced_shields" in target_ship.special_rules
            and current_shields(target_ship, blast_markers or []) > 0):
        shifts += 1

    # Tau tracking systems aura - ignore >30cm penalty
    if dist > 30 and _has_tracking_support(ship, all_ships):
        shifts -= 1  # cancel the >30cm right shift

    return shifts


def check_los_clear(ship: Ship, target_ship: Ship,
                    phenomena: list = None,
                    blast_markers: list = None,
                    ships: list = None) -> dict:
    """Check if line of sight is clear between attacker and target. ships: the
    ships on the table, so hulks block lines of fire (s.34)."""
    phenomena = phenomena or []
    blast_markers = blast_markers or []
    return check_los_ships(ship, target_ship, phenomena, blast_markers, ships)


def _has_tracking_support(ship: Ship, all_ships: list = None) -> bool:
    """
    Check if this Tau ship is within range of a tracking system.
    Checks the ship itself AND nearby friendly Tau ships with tracking systems.
    """
    # Check self
    for rule in ship.special_rules:
        if rule.startswith("tracking_systems"):
            return True

    # Check nearby allies
    if all_ships:
        for s_dict in all_ships:
            ally = Ship.from_dict(s_dict) if isinstance(s_dict, dict) else s_dict
            if ally.id == ship.id or ally.player != ship.player:
                continue
            if ally.is_destroyed:
                continue
            for rule in ally.special_rules:
                if rule.startswith("tracking_systems"):
                    # Parse range from rule name (e.g. "tracking_systems_20")
                    parts = rule.split("_")
                    try:
                        ts_range = int(parts[-1])
                    except (ValueError, IndexError):
                        ts_range = 10
                    dist = ship.distance_to(ally)
                    if dist <= ts_range:
                        return True
    return False


_DICE_EXPR = re.compile(r"^(\d*)D([36])([+-]\d+)?$")


def is_dice_value(text: str) -> bool:
    """A random value printed as dice, e.g. D6, D6+1, 2D6+6, D3+3."""
    return bool(_DICE_EXPR.match((text or "").replace(" ", "").upper()))


def dice_value_average(text: str) -> int:
    """Rounded-down average of a dice value (for AI estimates and labels only)."""
    n, sides, add = _DICE_EXPR.match(text.replace(" ", "").upper()).groups()
    return int((int(n or 1) * (int(sides) + 1) / 2) + int(add or 0))


def dice_value_max(text: str) -> int:
    n, sides, add = _DICE_EXPR.match(text.replace(" ", "").upper()).groups()
    return int(n or 1) * int(sides) + int(add or 0)


def roll_dice_value(text: str, dice: DiceRoller, label: str = "") -> int:
    """Roll a value printed as dice. Owner ruling: random Ork firepower and
    strength are rolled when they are used."""
    n, sides, add = _DICE_EXPR.match(text.replace(" ", "").upper()).groups()
    n = int(n or 1)
    if sides == "6":
        total = sum(dice.roll_d6(n, f"{label} ({text})"))
    else:
        total = sum(dice.roll_d3(f"{label} ({text})") for _ in range(n))
    return max(0, total + int(add or 0))


def _zzapp_firepower(attacker: Ship, weapon: Dict, dice: DiceRoller, gs) -> int:
    """Zzapp Gunz' random firepower (Ork weapons): rolled with D6s so the
    actual dice are seen (a D3 is a D6 halved, rounding up); a 1 on any of
    them puts a blast marker in contact with the ship's rear arc, once a turn."""
    n, sides, add = _DICE_EXPR.match(weapon["strength_dice"].replace(" ", "").upper()).groups()
    raw = dice.roll_d6(int(n or 1), f"{attacker.name} {weapon['name']} ({weapon['strength_dice']})")
    total = sum(raw) if sides == "6" else sum((r + 1) // 2 for r in raw)
    if 1 in raw and gs is not None:
        done = gs.__dict__.setdefault("_zzapp_blast", set())
        key = (gs.turn_number, attacker.id)
        if key not in done:
            done.add(key)
            back = math.radians(attacker.heading + 180)
            _place_shield_impacts(attacker, 1, gs, origin=(attacker.x + 50 * math.cos(back),
                                                           attacker.y + 50 * math.sin(back)))
            gs.add_log(f"  {attacker.name}'s zzapp gunz overload: a blast marker at its stern")
    return max(0, total + int(add or 0))


def weapon_fire_pool(attacker: Ship, weapon: Dict, w_idx: int, target_dist: float,
                     dice: DiceRoller, gs=None) -> Tuple[int, Optional[str], Optional[str]]:
    """Firepower/strength available to this weapon for a shot at a target
    target_dist away: (pool, range_mode, error).

    The first shot of the turn fixes the pool:
      - random values (strength_dice, e.g. Gunz FP D6+1) are rolled now, when
        the weapon is used (owner ruling);
      - Heavy Gunz use their bracketed value within 15cm, else the first value.
    Later shots (split fire) use what is left in attacker.weapons_remaining.
    Owner ruling on splitting Heavy Gunz: fire shared between targets uses the
    worse value, so once a shot used the within-15cm value ("close" mode) the
    rest may only go at targets within 15cm. Fire at the further target first
    to split at the 15cm+ value.
    Returns a printed value before crippled/special-order halving."""
    key = str(w_idx)
    remaining = (attacker.weapons_remaining or {}).get(key)
    mode = (attacker.weapon_pool_mode or {}).get(key)
    close = weapon.get("strength_close")
    if remaining is not None:
        if close is not None and mode == "close" and target_dist >= 15:
            return 0, mode, (f"{weapon['name']} already fired with their within-15cm "
                             f"firepower; when splitting between near and far targets, "
                             f"fire at the far target first (worse firepower is shared).")
        return remaining, mode, None
    if weapon.get("strength_dice"):
        if weapon.get("zzapp"):
            return _zzapp_firepower(attacker, weapon, dice, gs), None, None
        return roll_dice_value(weapon["strength_dice"], dice,
                               f"{attacker.name} {weapon['name']}"), None, None
    if close is not None:
        if target_dist < 15:
            return close, "close", None
        return weapon["strength"], "long", None
    return weapon["strength"], None, None


def shot_weapon(weapon: Dict, strength: int) -> Dict:
    """Weapon dict for one shot with its firepower already decided."""
    d = {k: v for k, v in weapon.items() if k not in ("strength_close", "strength_dice")}
    d["strength"] = strength
    return d


def battery_base_firepower(attacker: Ship, weapon: Dict,
                           target: Optional[Ship] = None) -> int:
    """Printed firepower for this shot. Ork Heavy Gunz have two values: the
    first at 15cm or more, the second (in brackets, "strength_close") within
    15cm (Ork faction rules). Range is measured as for the gunnery range shift."""
    close = weapon.get("strength_close")
    if close is not None and target is not None and attacker.distance_to(target) < 15:
        return close
    return weapon["strength"]


def effective_battery_firepower(attacker: Ship, weapon: Dict,
                                target: Optional[Ship] = None) -> int:
    """Return the effective firepower of a battery weapon after all modifiers."""
    from .chapter_tactics import reduce_for_movement_order, lightning_vanguard
    fp = battery_base_firepower(attacker, weapon, target)
    if attacker.is_crippled:
        fp = attacker.crippled_value(fp)
    if attacker.special_order in (
        SpecialOrder.ALL_AHEAD_FULL.value,
        SpecialOrder.BURN_RETROS.value,
        SpecialOrder.COME_TO_NEW_HEADING.value,
    ):
        # Lightning Thrusters: a vanguard cruiser on All Ahead Full fires its
        # macrobatteries at full effectiveness unless it turned this move
        if not (attacker.special_order == SpecialOrder.ALL_AHEAD_FULL.value
                and lightning_vanguard(attacker) and attacker.turns_used_this_turn == 0):
            fp = reduce_for_movement_order(attacker, fp, gunnery=True)
    if attacker.special_order == SpecialOrder.BRACE_FOR_IMPACT.value:
        fp = (fp + 1) // 2
    return fp


def gunnery_target_type(ship: Ship) -> str:
    """Gunnery table target type for a ship: capital, escort or defense.

    A ship that moved less than 5cm in its last movement phase (for any
    reason) counts as Defenses (core rules s.10, Movement).
    """
    if ship.last_move_cm is not None and ship.last_move_cm < 5:
        return "defense"
    if ship.ship_type in ("battleship", "cruiser"):
        return "capital"
    if ship.ship_type == "escort":
        return "escort"
    return "defense"


def resolve_batteries(attacker: Ship, target: Ship, weapon: Dict,
                      dice: DiceRoller, blast_markers: List[BlastMarker],
                      lock_on: bool = False,
                      phenomena: list = None,
                      all_ships: list = None,
                      no_column_shifts: bool = False) -> ShotResult:
    """Resolve a weapons battery attack."""
    result = ShotResult(weapon["name"], "battery")
    firepower = effective_battery_firepower(attacker, weapon, target)

    if firepower <= 0:
        result.description = f"{weapon['name']}: no firepower available"
        return result

    # Determine target type for gunnery table
    target_type = gunnery_target_type(target)

    # Determine orientation
    target_orientation = attacker.get_target_orientation(target)

    # Get column and shifts
    column = get_gunnery_column(target_type, target_orientation)
    shifts = 0 if no_column_shifts else get_column_shifts(
        attacker, target, blast_markers, phenomena, all_ships, weapon)

    # Look up dice count
    num_dice = lookup_gunnery_dice(firepower, column, shifts)

    if num_dice <= 0:
        result.description = f"{weapon['name']}: FP {firepower}, 0 dice to roll"
        return result

    # Roll dice (bombardment cannons / killkannons always hit on 4+)
    armor = weapon.get("hits_on") or target.armor_vs(attacker.x, attacker.y)

    result.dice_rolled = dice.roll_d6(
        num_dice,
        f"{attacker.name} batteries vs {target.name} "
        f"(FP {firepower}, {target_orientation} {target_type}, need {armor}+)")

    result.hits = sum(1 for d in result.dice_rolled if d >= armor)

    # Lock On rerolls
    if lock_on and result.hits < num_dice:
        misses = [d for d in result.dice_rolled if d < armor]
        if misses:
            result.reroll_dice = dice.roll_d6(
                len(misses), f"{attacker.name} Lock On rerolls")
            extra_hits = sum(1 for d in result.reroll_dice if d >= armor)
            result.hits += extra_hits

    col_desc = f"col {column}" + (f" shifted {shifts:+d}" if shifts else "")
    result.description = (
        f"{weapon['name']}: FP {firepower} vs {target_orientation} {target_type} "
        f"({col_desc}) = {num_dice} dice vs {armor}+ = {result.hits} hits")

    return result


def resolve_siege_cannons(attacker: Ship, target: Ship, macro_weapons: List[Dict],
                          bc_weapons: List[Dict], dice: DiceRoller,
                          blast_markers: List[BlastMarker], lock_on: bool = False,
                          phenomena: list = None, all_ships: list = None,
                          no_column_shifts: bool = False) -> Tuple[ShotResult, ShotResult]:
    """Siege Cannons Chapter tactic: a battle barge or strike cruiser firing its
    macrobatteries and bombardment cannons together adds both firepowers and
    looks up the to-hit rolls on the gunnery table. Rolls in excess of the
    bombardment cannons' firepower are made by the macrobatteries (vs Armour),
    the rest by the bombardment cannons (4+, crits on 4+).
    Returns (macrobattery result, bombardment cannon result)."""
    macro = ShotResult("Macrobatteries (Siege Cannons)", "battery")
    bc = ShotResult("Bombardment cannons (Siege Cannons)", "battery")
    macro_fp = sum(effective_battery_firepower(attacker, w, target) for w in macro_weapons)
    bc_fp = sum(effective_battery_firepower(attacker, w, target) for w in bc_weapons)
    target_type = gunnery_target_type(target)
    orientation = attacker.get_target_orientation(target)
    column = get_gunnery_column(target_type, orientation)
    shifts = 0 if no_column_shifts else get_column_shifts(
        attacker, target, blast_markers, phenomena, all_ships)
    num = lookup_gunnery_dice(macro_fp + bc_fp, column, shifts)
    macro_rolls = max(0, num - bc_fp)
    bc_rolls = num - macro_rolls
    armour = target.armor_vs(attacker.x, attacker.y)
    for res, n, need in ((macro, macro_rolls, armour), (bc, bc_rolls, 4)):
        if n <= 0:
            continue
        res.dice_rolled = dice.roll_d6(n, f"{attacker.name} {res.weapon_name} vs "
                                          f"{target.name} (need {need}+)")
        res.hits = sum(1 for d in res.dice_rolled if d >= need)
        if lock_on and res.hits < n:
            misses = n - res.hits
            res.reroll_dice = dice.roll_d6(misses, f"{attacker.name} Lock On rerolls")
            res.hits += sum(1 for d in res.reroll_dice if d >= need)
    col_desc = f"col {column}" + (f" shifted {shifts:+d}" if shifts else "")
    macro.description = (f"Siege Cannons: FP {macro_fp}+{bc_fp} vs {orientation} {target_type} "
                         f"({col_desc}) = {num} dice: {macro_rolls} macrobattery vs {armour}+ "
                         f"= {macro.hits} hits")
    bc.description = f"  {bc_rolls} bombardment cannon dice vs 4+ = {bc.hits} hits"
    return macro, bc


def resolve_combined_batteries(primary_attacker: Ship,
                               contributions: List[Tuple[Ship, Dict]],
                               target: Ship,
                               dice: DiceRoller,
                               blast_markers: List[BlastMarker],
                               lock_on: bool = False,
                               phenomena: list = None,
                               all_ships: list = None,
                               no_column_shifts: bool = False) -> ShotResult:
    """Pool battery firepower from multiple squadron ships into one gunnery roll.

    contributions: list of (attacker_ship, battery_weapon_dict) pairs all firing
    at `target`.  Firepower is summed after per-ship modifiers; orientation, column
    shifts, and armour facing are taken from `primary_attacker`.
    """
    contributors = [a.name for a, _ in contributions]
    result = ShotResult(f"Squadron fire ({', '.join(contributors)})", "battery")

    # Escorts total their firepower first and then halve it (rounding up);
    # capital ships halve individually (s.8, Shooting by Squadrons)
    escorts = [(a, w) for a, w in contributions if a.ship_type == "escort"]
    others = [(a, w) for a, w in contributions if a.ship_type != "escort"]
    total_fp = sum(effective_battery_firepower(a, w, target) for a, w in others)
    if escorts:
        esc_fp = sum(battery_base_firepower(a, w, target) for a, w in escorts)
        lead = escorts[0][0]
        if lead.special_order in (SpecialOrder.ALL_AHEAD_FULL.value,
                                  SpecialOrder.BURN_RETROS.value,
                                  SpecialOrder.COME_TO_NEW_HEADING.value):
            esc_fp = (esc_fp + 1) // 2
        if lead.special_order == SpecialOrder.BRACE_FOR_IMPACT.value:
            esc_fp = (esc_fp + 1) // 2
        total_fp += esc_fp
    if total_fp <= 0:
        result.description = "Combined squadron fire: no firepower available"
        return result

    target_type = gunnery_target_type(target)

    target_orientation = primary_attacker.get_target_orientation(target)
    column = get_gunnery_column(target_type, target_orientation)
    shifts = (0 if no_column_shifts
              else get_column_shifts(primary_attacker, target, blast_markers,
                                     phenomena, all_ships))
    num_dice = lookup_gunnery_dice(total_fp, column, shifts)

    if num_dice <= 0:
        result.description = (
            f"Squadron batteries: pooled FP {total_fp}, 0 dice to roll")
        return result

    armor = target.armor_vs(primary_attacker.x, primary_attacker.y)

    result.dice_rolled = dice.roll_d6(
        num_dice,
        f"Squadron fire vs {target.name} "
        f"(pooled FP {total_fp}, {target_orientation} {target_type}, need {armor}+)")
    result.hits = sum(1 for d in result.dice_rolled if d >= armor)

    if lock_on and result.hits < num_dice:
        misses = [d for d in result.dice_rolled if d < armor]
        if misses:
            result.reroll_dice = dice.roll_d6(
                len(misses), "Squadron Lock On rerolls")
            result.hits += sum(1 for d in result.reroll_dice if d >= armor)

    col_desc = f"col {column}" + (f" shifted {shifts:+d}" if shifts else "")
    result.description = (
        f"Squadron fire [{', '.join(contributors)}]: "
        f"pooled FP {total_fp} vs {target_orientation} {target_type} "
        f"({col_desc}) = {num_dice} dice vs {armor}+ = {result.hits} hits")

    return result


def ordnance_fire_dice(attacker: Ship, weapon: Dict, x: float, y: float, gs,
                       avail: int) -> int:
    """Dice a direct-fire weapon rolls at an ordnance marker (s.30): gunnery
    on the Ordnance column with range, blast marker and special-rule shifts
    (no target aspect); lances their firepower."""
    wtype = weapon.get("weapon_type", "")
    if wtype == "lance":
        return avail
    if wtype != "battery":
        return 0
    from .tables import lookup_gunnery_dice, COL_ABEAM_ESCORT
    from .los import check_los
    dist = math.hypot(x - attacker.x, y - attacker.y)
    shifts = -1 if dist < 15 else (1 if dist > 30 else 0)
    shifts += check_los(attacker.x, attacker.y, x, y, gs.get_phenomena(),
                        gs.get_blast_markers()).get("column_shifts", 0)
    if "targeting_matrix" in attacker.special_rules:
        shifts -= 1
    return lookup_gunnery_dice(avail, COL_ABEAM_ESCORT, shifts)


def fire_at_ordnance(attacker: Ship, weapon: Dict, marker_id: str, gs, dice,
                     avail: int) -> Dict:
    """Shoot one weapon at an enemy marker (s.30): 6+ to hit (bombardment
    cannons 4+); one hit removes the marker, or its whole wave. Returns
    {"dice", "hits", "removed": [ids]}."""
    m = next((o for o in gs.ordnance if o["id"] == marker_id), None)
    if m is None:
        return {"dice": 0, "hits": 0, "removed": []}
    n = ordnance_fire_dice(attacker, weapon, m["x"], m["y"], gs, avail)
    if n <= 0:
        return {"dice": 0, "hits": 0, "removed": []}
    need = weapon.get("hits_on") or 6
    rolls = dice.roll_d6(n, f"{weapon['name']} vs {m['ordnance_type']} ({need}+ to hit)")
    hits = sum(1 for r in rolls if r >= need)
    removed = []
    if hits:
        from .waves import whole_wave_ids
        removed = list(whole_wave_ids(gs, marker_id))
        gs.ordnance = [o for o in gs.ordnance if o["id"] not in set(removed)]
    return {"dice": n, "hits": hits, "removed": removed}


def cutting_beam_firepower(ship: Ship, dist: float) -> int:
    """Demiurg cutting beam (lance, 15cm, front): FP 1 + each blast marker the
    ship collected in its movement phase, at most 8; beyond 15cm two markers
    are expended to reach 30cm and the rest add firepower."""
    markers = ship.collected_blast_markers
    if dist > 15:
        markers -= 2
    return min(8, 1 + max(0, markers))


def resolve_lances(attacker: Ship, target: Ship, weapon: Dict,
                   dice: DiceRoller, lock_on: bool = False) -> ShotResult:
    """Resolve a lance weapon attack."""
    result = ShotResult(weapon["name"], "lance")
    strength = weapon["strength"]
    if weapon.get("cutting_beam"):
        strength = cutting_beam_firepower(attacker, attacker.distance_to(target))

    # Halve if crippled
    if attacker.is_crippled:
        strength = attacker.crippled_value(strength)

    # Halve if on movement special orders
    if attacker.special_order in (
        SpecialOrder.ALL_AHEAD_FULL.value,
        SpecialOrder.BURN_RETROS.value,
        SpecialOrder.COME_TO_NEW_HEADING.value,
    ):
        strength = (strength + 1) // 2

    if attacker.special_order == SpecialOrder.BRACE_FOR_IMPACT.value:
        strength = (strength + 1) // 2

    if strength <= 0:
        result.description = f"{weapon['name']}: no strength available"
        return result

    # Lances hit on 4+ regardless of armor (Ork Zzapp Gunz on 5+)
    need = weapon.get("hits_on", 4)
    result.dice_rolled = dice.roll_d6(
        strength, f"{attacker.name} lances vs {target.name} (need {need}+)")

    if weapon.get("pulsar") or weapon.get("phantom"):
        result.hits = _eldar_lance_hits(attacker, target, weapon, result, dice, need,
                                        lock_on)
        result.hits -= _holofield(attacker, target, result.hits, dice)
        result.description = (f"{weapon['name']}: Str {strength} vs {target.name} = "
                              f"{result.hits} hits")
        return result

    result.hits = sum(1 for d in result.dice_rolled if d >= need)

    # Lock On rerolls
    if lock_on and result.hits < strength:
        misses = [d for d in result.dice_rolled if d < need]
        if misses:
            result.reroll_dice = dice.roll_d6(
                len(misses), f"{attacker.name} Lock On lance rerolls")
            extra_hits = sum(1 for d in result.reroll_dice if d >= need)
            result.hits += extra_hits

    result.hits -= _holofield(attacker, target, result.hits, dice)
    result.description = (
        f"{weapon['name']}: Str {strength} lances vs {target.name} "
        f"(4+) = {result.hits} hits")

    return result


def _holofield(attacker: Ship, target: Ship, hits: int, dice: DiceRoller) -> int:
    """Eldar holofields (MMS p.4) against lances and other direct attacks off
    the gunnery table: a save per hit by range (5+ beyond 30cm, 6+ at 15-30cm,
    none under 15cm); a saved hit is thwarted (no blast marker, no damage)."""
    if hits <= 0 or "holofield" not in (target.special_rules or []):
        return 0
    from .eldar import holofield_saves
    return holofield_saves(dice, hits, attacker.distance_to(target),
                           f"{target.name} holofield")


def _eldar_lance_hits(attacker: Ship, target: Ship, weapon: Dict, result, dice: DiceRoller,
                      need: int, lock_on: bool) -> int:
    """Pulsar lances (MMS p.4): a hit gives another attack, and a second hit a
    third (at most three hits a shot); on Lock On only the first miss is
    re-rolled. Phantom lances: 1 hit on a 4 or 5, 2 on a 6 (Lock On re-rolls
    misses as usual)."""
    if weapon.get("phantom"):
        def value(d):
            return 2 if d >= 6 else (1 if d >= need else 0)
        hits = sum(value(d) for d in result.dice_rolled)
        misses = [d for d in result.dice_rolled if d < need]
        if lock_on and misses:
            result.reroll_dice = dice.roll_d6(len(misses), f"{attacker.name} Lock On re-rolls")
            hits += sum(value(d) for d in result.reroll_dice)
        return hits
    hits = 0
    rerolled = False
    for d in result.dice_rolled:
        if d < need and lock_on and not rerolled:
            rerolled = True
            d = dice.roll_d6(1, f"{attacker.name} Lock On re-roll (first miss)")[0]
        if d < need:
            continue
        hits += 1
        for _k in range(2):                  # the follow-up attacks
            if dice.roll_d6(1, f"{attacker.name} pulsar follow-up (need {need}+)")[0] < need:
                break
            hits += 1
    return hits


def resolve_nova_cannon(attacker: Ship, target_x: float, target_y: float,
                        dice: DiceRoller, game_state: GameState) -> Dict:
    """
    Resolve a nova cannon shot.
    Returns dict with hits per ship and blast marker placements.
    """
    dist = math.sqrt((attacker.x - target_x)**2 + (attacker.y - target_y)**2)

    # Cannot fire if crippled or on special orders other than Lock On/Reload/None
    if attacker.is_crippled:
        return {"error": "Crippled ships cannot fire nova cannon"}

    if attacker.special_order not in (SpecialOrder.NONE.value,
                                      SpecialOrder.LOCK_ON.value,
                                      SpecialOrder.RELOAD_ORDNANCE.value):
        return {"error": f"Cannot fire nova cannon on {attacker.special_order}"}

    if dist < 30 or dist > 150:
        return {"error": f"Target at {dist:.1f}cm, nova cannon range is 30-150cm"}

    # Scatter
    if dist <= 45:
        scatter_dice = 1
    elif dist <= 60:
        scatter_dice = 2
    else:
        scatter_dice = 3

    is_hit = dice.roll_scatter(f"Nova cannon scatter ({scatter_dice}D6 if miss)")

    result = {"hit": False, "scatter_distance": 0, "template_x": target_x,
              "template_y": target_y, "ship_hits": {}, "blast_markers": []}

    if not is_hit:
        scatter_roll = dice.roll_d6(scatter_dice, "Scatter distance")
        scatter_dist = sum(scatter_roll)
        scatter_angle = dice.roll_scatter_direction()

        # Move template
        rad = math.radians(scatter_angle)
        result["template_x"] = target_x + scatter_dist * math.cos(rad)
        result["template_y"] = target_y + scatter_dist * math.sin(rad)
        result["scatter_distance"] = scatter_dist

    # Check what the template hits (5cm diameter circle, 1.2cm center hole)
    template_x = result["template_x"]
    template_y = result["template_y"]
    template_radius = NOVA_CANNON_TEMPLATE_RADIUS_CM
    center_radius = NOVA_CANNON_CENTER_HOLE_RADIUS_CM

    any_ship_hit = False
    for s in game_state.get_ships():
        if s.is_destroyed:
            continue
        base_r = s.base_radius
        dist_to_template = math.sqrt((s.x - template_x)**2 + (s.y - template_y)**2)

        if dist_to_template <= center_radius + base_r:
            # Base touches center hole: D6 hits ignoring armor
            hits = sum(dice.roll_d6(1, f"Nova cannon D6 hits on {s.name} (center)"))
            result["ship_hits"][s.id] = {"hits": hits, "ignores_armor": True}
            any_ship_hit = True
        elif dist_to_template <= template_radius + base_r:
            # Base touches template: 1 automatic hit
            result["ship_hits"][s.id] = {"hits": 1, "ignores_armor": True}
            any_ship_hit = True

    if not any_ship_hit:
        # Place blast marker at template center
        result["blast_markers"].append((template_x, template_y))

    result["hit"] = any_ship_hit or is_hit
    return result


def offer_brace(game_state: GameState, ship: Ship, attacker_key: str,
                attacker_name: str, expected: float) -> bool:
    """A ship about to take damage may Brace for Impact before the damage is
    rolled (s.7). The game sets game_state.brace_hook (asks the player, or the
    AI for its own ships); without it only a ship already braced counts.
    Returns True if the ship is braced."""
    fresh = game_state.get_ship_by_id(ship.id) or ship
    if fresh.special_order == SpecialOrder.BRACE_FOR_IMPACT.value:
        return True
    hook = getattr(game_state, "brace_hook", None)
    if hook is None or fresh.status != "active" or fresh.is_destroyed:
        return False
    from .aa_turn import brace_is_reactive
    if not brace_is_reactive(game_state):
        return False                # AA: Brace is a command-phase order
    return bool(hook(fresh, attacker_key, attacker_name, expected))


SHIELD_IMPACT_OFFSET_CM = 1.2      # marker centre beyond the base edge (touching)
SHIELD_IMPACT_SPACING_CM = 2.2     # marker centres closer than this overlap


def _place_shield_impacts(target: Ship, n: int, game_state: GameState,
                          origin: Optional[Tuple[float, float]] = None,
                          attacker_key: str = "") -> None:
    """Shield impacts (s.11): one blast marker touching the target's base per
    hit blocked, as close as possible to the origin of the attack, fanned out
    so markers don't overlap. Avoid overlapping other blast markers and
    touching nearby ships not in base contact; if forced to choose, overlap
    other blast markers first. No fixed limit per turn."""
    from .geometry import BLAST_MARKER_RADIUS_CM, BASE_CONTACT_MARGIN_CM
    r = target.base_radius + SHIELD_IMPACT_OFFSET_CM
    a0 = (math.atan2(origin[1] - target.y, origin[0] - target.x)
          if origin else math.radians(target.heading))
    step = 2 * math.asin(min(1.0, (SHIELD_IMPACT_SPACING_CM / 2) / r))
    n_slots = max(1, int(2 * math.pi / step))
    order = [0]
    for k in range(1, n_slots // 2 + 1):
        order += [k, -k]
    angles = [a0 + k * step for k in order][:n_slots]
    others = [s for s in game_state.get_ships()
              if s.id != target.id and not s.is_disengaged and s.status != "destroyed"
              and math.hypot(s.x - target.x, s.y - target.y)
              > s.base_radius + target.base_radius + BASE_CONTACT_MARGIN_CM]
    turn_label = f"shield_impact_t{game_state.turn_number}"
    placed_now = []
    for j in range(n):
        existing = game_state.get_blast_markers()

        def spot(a):
            return (target.x + r * math.cos(a), target.y + r * math.sin(a))

        def overlaps(xy, markers):
            return any(math.hypot(xy[0] - m.x, xy[1] - m.y) < SHIELD_IMPACT_SPACING_CM - 1e-3
                       for m in markers)

        # Remastered spill-over limit (optional, s.11): one round of shooting by
        # a ship or squadron touches at most the target and one other ship;
        # ships in base contact with (or overlapping) the target are exempt.
        spill = getattr(game_state, "rule_remastered_spillover", False)
        key = (game_state.turn_number, game_state.current_phase, attacker_key)
        touched = game_state.__dict__.setdefault("_spillover_touched", {}).setdefault(key, set())

        def touching_ids(xy):
            return {s.id for s in others
                    if math.hypot(xy[0] - s.x, xy[1] - s.y) <= s.base_radius + BLAST_MARKER_RADIUS_CM}

        def touches_others(xy):
            """A spot to avoid: it touches a ship it shouldn't. Normally any other
            ship; with the spill-over limit, any but the one other ship this
            round may touch (the first one touched becomes it)."""
            ids = touching_ids(xy)
            if spill and attacker_key and ids:
                return not (ids <= touched or (not touched and len(ids) == 1))
            return bool(ids)

        free = [a for a in angles if not overlaps(spot(a), placed_now)]
        best = (next((a for a in free if not overlaps(spot(a), existing)
                      and not touches_others(spot(a))), None)
                or next((a for a in free if not touches_others(spot(a))), None)
                # spill-over limit: overlap this round's markers rather than touch
                # a forbidden ship
                or (next((a for a in angles if not touches_others(spot(a))), None)
                    if spill and attacker_key else None)
                or next(iter(free), None))
        if best is None:
            best = angles[j % len(angles)]
        bx, by = spot(best)
        if spill and attacker_key:
            touched.update(touching_ids((bx, by)))
        bm = BlastMarker(
            id=f"bm_{target.id}_t{game_state.turn_number}_{j}_{random.randint(0,9999)}",
            x=bx, y=by, source=turn_label,
            heading=(math.degrees(best) + 180) % 360)
        game_state.add_blast_marker(bm)
        placed_now.append(bm)


def expected_hits(attacker: Ship, weapon: Dict, target: Ship, gs=None) -> float:
    """Rough number of hits a weapon will score on a target (for deciding
    whether to brace before the attack is rolled, and the AI's targeting).
    With the game state, batteries take their column shifts (range, blast
    markers / dust in the line of fire or in contact, s.11 / s.13); lances
    don't use the gunnery table, so blast markers don't affect them."""
    wtype = weapon.get("weapon_type", "")
    if wtype == "lance":
        return weapon.get("strength", 0) * (7 - (weapon.get("hits_on") or 4)) / 6.0
    if wtype != "battery":
        return 0.0
    fp = effective_battery_firepower(attacker, weapon, target)
    column = get_gunnery_column(gunnery_target_type(target),
                                attacker.get_target_orientation(target))
    shifts = 0
    if gs is not None:
        shifts = get_column_shifts(attacker, target, gs.get_blast_markers(),
                                   gs.get_phenomena(), gs.get_ships(), weapon)
    n = lookup_gunnery_dice(fp, column, shifts)
    need = weapon.get("hits_on") or target.armor_vs(attacker.x, attacker.y)
    return n * max(0, 7 - need) / 6


def apply_damage(target: Ship, hits: int, dice: DiceRoller,
                 game_state: GameState,
                 ignores_shields: bool = False,
                 target_braced: bool = False,
                 crit_on: int = 6,
                 attacker_key: str = "",
                 origin: Optional[Tuple[float, float]] = None,
                 auto_crit: bool = False,
                 rolled_to_hit: bool = True) -> Dict:
    """
    Apply hits to a ship, handling shields, damage, crits. auto_crit: every
    hull hit is a critical hit, with no D6 check (vortex torpedoes).
    Shields are reduced by blast markers already touching the ship.
    Brace saves apply only to hull damage (not shield hits).
    Returns summary dict.
    """
    summary = {
        "shield_hits": 0, "hull_hits": 0, "brace_saves": 0,
        "crits": [], "destroyed": False, "crippled": False,
        "blast_markers_placed": 0,
        "unused_hits": 0,   # hits left over because the ship was destroyed first
    }

    remaining_hits = hits
    # Eldar are Fragile (MMS p.4): critical hits on 5+ (Ghostships excepted)
    from .eldar import crit_threshold
    crit_on = min(crit_on, crit_threshold(target))
    summary["attacker_key"] = attacker_key

    if not ignores_shields:
        available_shields = current_shields(target, game_state.get_blast_markers())
        # Overloaded Shield Capacitors (Advanced Shields): after the enemy rolls
        # to hit, a D6 per active shield; each 6 discards one hit
        if ("overloaded_shields" in target.special_rules and rolled_to_hit
                and available_shields > 0 and remaining_hits > 0):
            rolls = dice.roll_d6(available_shields,
                                 f"{target.name} Overloaded Shield Capacitors (6s discard hits)")
            gone = min(remaining_hits, sum(1 for r in rolls if r == 6))
            if gone:
                remaining_hits -= gone
                summary["capacitor_discards"] = gone
                game_state.add_log(f"{target.name}: Overloaded Shield Capacitors discard "
                                   f"{gone} hit(s)")
        shield_absorb = min(remaining_hits, available_shields)
        summary["shield_hits"] = shield_absorb
        summary["blast_markers_placed"] = shield_absorb
        remaining_hits -= shield_absorb

    # Brace saves (4+ per HULL hit only, not shield hits)
    if target_braced and remaining_hits > 0:
        saves = 0
        for _ in range(remaining_hits):
            save_roll = dice.roll_d6(1, f"{target.name} Brace save (4+)")
            if save_roll[0] >= 4:
                saves += 1
        # Heed the Machine Spirit: a braced capital ship may test on Ld 7
        # (ignoring modifiers); if passed, one failed save succeeds. Once per
        # attacker per turn.
        failed = remaining_hits - saves
        from .chapter_tactics import machine_spirit_ship
        key = attacker_key or "?"
        from .movement import sirens_summon
        if (failed > 0 and machine_spirit_ship(target)
                and key not in (target.machine_spirit_used_vs or [])
                and not sirens_summon(target, game_state)):
            target.machine_spirit_used_vs = list(target.machine_spirit_used_vs or []) + [key]
            ld_roll = dice.roll_2d6(f"{target.name} Heed the Machine Spirit (Ld 7)")
            if ld_roll <= 7:
                saves += 1
                game_state.add_log(f"  {target.name}: Heed the Machine Spirit passed "
                                   f"({ld_roll}) — one failed save succeeds")
            else:
                game_state.add_log(f"  {target.name}: Heed the Machine Spirit failed ({ld_roll})")
        summary["brace_saves"] = saves
        remaining_hits -= saves

    # Apply hull damage
    summary["hull_hits"] = max(0, remaining_hits)

    # Owner ruling: a hulk that takes at least one point of damage rolls on
    # the Catastrophic Damage table again (no critical hits on a hulk)
    if target.status in ("drifting_hulk", "burning_hulk"):
        if summary["hull_hits"] > 0:
            target.hits_remaining = 0
            game_state.add_log(f"{target.name} (hulk) takes {summary['hull_hits']} "
                               f"damage: rolls on the Catastrophic Damage table again")
            summary["catastrophic"] = resolve_catastrophic(target, dice, game_state)
            summary["destroyed"] = target.status == "destroyed"
    else:
        was_crippled = target.is_crippled

        hull_hits_applied = 0
        for i in range(summary["hull_hits"]):
            hull_hits_applied += 1
            target.hits_remaining -= 1

            if target.hits_remaining <= 0:
                summary["destroyed"] = True
                break

            # Critical hit check: D6 per hull hit, 6 = crit (crit_on 4 for
            # bombardment cannons and killkannons)
            if auto_crit:
                is_crit = True             # vortex torpedoes: every hit is a critical hit
            else:
                crit_roll = dice.roll_d6(1, f"Crit check for hit on {target.name}"
                                         + (f" ({crit_on}+)" if crit_on != 6 else ""))
                is_crit = crit_roll[0] >= crit_on
            if is_crit and not uses_crit_table(target):
                # Small escorts/defenses take +1 damage instead of a critical
                target.hits_remaining -= 1
                game_state.add_log(f"Critical on {target.name}: +1 damage")
                if target.hits_remaining <= 0:
                    summary["destroyed"] = True
                    break
            elif is_crit:
                if roll_critical_hit(target, dice, game_state, summary):
                    summary["destroyed"] = True
                    break

        if summary["destroyed"]:
            summary["unused_hits"] = summary["hull_hits"] - hull_hits_applied

        if not was_crippled and target.is_crippled and not summary["destroyed"]:
            summary["crippled"] = True
            game_state.add_log(f"{target.name} is now CRIPPLED")

    # Place blast markers for SHIELD hits only (not hull damage), s.11
    if summary["blast_markers_placed"] > 0:
        _place_shield_impacts(target, summary["blast_markers_placed"], game_state, origin,
                              attacker_key)

    demiurg_leadership(target)
    game_state.update_ship(target)
    return summary




def demiurg_leadership(ship: Ship) -> None:
    """Demiurg commerce vessels lose 1 Ld per point of damage suffered, to a
    minimum of Ld 5, from their nominal (automated) Ld."""
    rule = next((r for r in ship.special_rules if r.startswith("nominal_ld:")), None)
    if rule is None:
        return
    nominal = int(rule.split(":", 1)[1])
    ship.leadership = max(5, nominal - max(0, ship.hits_max - ship.hits_remaining))


def roll_critical_hit(target: Ship, dice: DiceRoller, game_state: GameState,
                      summary: Optional[Dict] = None) -> bool:
    """Roll 2D6 on the critical hits table for a ship that uses it, apply the
    result (cascading, extra damage) and any torpedo-launcher explosion.
    Changes target in place (the caller writes it back). True if the ship is
    reduced to 0."""
    crit_2d6 = dice.roll_2d6(f"Critical hit on {target.name}")
    crit_data = _resolve_crit_cascade(crit_2d6, target, game_state)
    if _tzeentch_reroll(target, crit_2d6, crit_data, game_state, summary):
        crit_2d6 = dice.roll_2d6(f"Critical hit on {target.name} (Mark of Tzeentch re-roll)")
        crit_data = _resolve_crit_cascade(crit_2d6, target, game_state)
    if crit_data is None:
        game_state.add_log(f"Critical on {target.name}: rolled {crit_2d6}, "
                           f"all results cascaded, no effect")
        return False
    extra = crit_data["extra_damage"]
    if extra == "D3":
        extra = dice.roll_d3("Hull Breach extra damage")
    elif extra == "D6":
        extra = sum(dice.roll_d6(1, "Bulkhead Collapse extra damage"))
    target.critical_damage.append({
        "crit_type": crit_data["crit_type"],
        "description": crit_data["name"],
        "repairable": crit_data["repairable"],
        "turn_inflicted": game_state.turn_number,
    })
    if summary is not None:
        summary.setdefault("crits", []).append(crit_data["name"])
    game_state.add_log(f"CRITICAL HIT on {target.name}: {crit_data['name']}")
    if isinstance(extra, int) and extra > 0:
        target.hits_remaining = max(0, target.hits_remaining - extra)
        game_state.add_log(f"  Extra damage: {extra} HP")
        if target.hits_remaining <= 0:
            return True
    if crit_data["crit_type"] == "infinity_circuit":
        target.leadership = max(1, target.leadership - 1)     # Eldar: -1 Ld per hit
    if crit_data["crit_type"] == "holofield_destroyed":
        target.special_rules = [r for r in target.special_rules if r != "holofield"]
    if crit_data["crit_type"] == "bridge_smashed":
        if "demiurg_commerce" in target.special_rules:
            # Demiurg: one extra point of damage instead of -3 Ld
            target.hits_remaining = max(0, target.hits_remaining - 1)
            game_state.add_log(f"  {target.name} (Demiurg): Bridge Smashed deals 1 extra damage")
            if target.hits_remaining <= 0:
                return True
        else:
            target.leadership = max(1, target.leadership - 3)
    if mine_launcher_crit(target, crit_data["crit_type"], dice, game_state):
        return True
    return torpedo_launcher_crit(target, crit_data["crit_type"], dice, game_state, summary)


def mine_launcher_crit(target: Ship, crit_type: str, dice: DiceRoller,
                       game_state: GameState) -> bool:
    """s.17: a ship whose mine launchers' location suffers critical damage
    takes an extra D3 damage as some mines explode. True if reduced to 0."""
    if not any(w.get("weapon_type") == "mine_launcher" and weapon_in_crit_slot(w, crit_type)
               for w in target.weapons):
        return False
    n = dice.roll_d3(f"{target.name} mines explode in their launchers (D3)")
    game_state.add_log(f"  {target.name}'s mines explode: {n} extra damage")
    target.hits_remaining = max(0, target.hits_remaining - n)
    return target.hits_remaining <= 0


def _tzeentch_reroll(target: Ship, roll: int, crit_data: Optional[Dict],
                     game_state: GameState, summary: Optional[Dict]) -> bool:
    """Mark of Tzeentch: the marked ship may re-roll a Critical Hits result it
    suffers or inflicts (the second stands). One re-roll per critical; the
    target's owner is asked first. GameState.crit_reroll_hook(player, text) ->
    bool asks a human owner; the AI (or no hook) re-rolls its own ship's 9+
    and an enemy's 5 or less."""
    attacker = None
    key = (summary or {}).get("attacker_key")
    if key:
        attacker = game_state.get_ship_by_id(key)
    name = crit_data["name"] if crit_data else "no effect"
    for ship, own in ((target, True), (attacker, False)):
        if ship is None or "mark:tzeentch" not in ship.special_rules:
            continue
        ai = game_state.ai_spectator or game_state.ai_player == ship.player
        hook = getattr(game_state, "crit_reroll_hook", None)
        best = roll >= 9 if own else roll <= 5          # the AI's choice
        if hook is not None and not ai:
            use = hook(ship.player, f"{target.name} critical hit: {name} (rolled {roll}). "
                                    f"Re-roll it with {ship.name}'s Mark of Tzeentch?", best)
        else:
            use = best
        if use:
            game_state.add_log(f"{ship.name}: Mark of Tzeentch re-rolls the critical ({name})")
            return True
    return False


ARMAMENT_CRIT_TYPES = ("dorsal_armament", "starboard_armament", "port_armament", "prow_armament")


def weapon_in_crit_slot(weapon: Dict, crit_type: str) -> bool:
    """Is this weapon knocked out by an armament critical of crit_type? By its
    name (Port / Starboard / Prow / Dorsal ...) or, failing that, its arcs
    (left only = port, right only = starboard, front only = prow, left + front
    + right = dorsal), the same slots the crit cascade checks."""
    name = (weapon.get("name") or "").lower()
    arcs = weapon.get("arcs") or []
    word = {"dorsal_armament": "dorsal", "port_armament": "port",
            "starboard_armament": "starboard", "prow_armament": "prow",
            "keel_armament": "keel"}.get(crit_type)
    if word is None:
        return False
    if word in name:
        return True
    if any(w in name for w in ("dorsal", "port", "starboard", "prow")):
        return False                         # named for another location
    if crit_type == "port_armament":
        return arcs == ["left"]
    if crit_type == "starboard_armament":
        return arcs == ["right"]
    if crit_type == "prow_armament":
        return arcs == ["front"]
    return "left" in arcs and "front" in arcs and "right" in arcs


def weapon_disabled_by_crit(ship: Ship, weapon: Dict) -> bool:
    """Is this weapon out of action because of an armament critical hit? (Also
    a Kustom Kannon's gun mode once its shared load is spent: it needs Reload
    Ordnance after firing in either mode.)"""
    if weapon.get("kustom_kannon") and weapon.get("weapon_type") == "battery" \
            and not ship.ordnance_loaded_torps:
        return True
    return any(weapon_in_crit_slot(weapon, c.get("crit_type", ""))
               for c in ship.critical_damage)


def spend_kustom_kannon(ship: Ship, weapon: Dict, game_state) -> None:
    """After its gun mode fires, the Kustom Kannon must be reloaded (the torps
    mode unloads it by launching)."""
    if weapon.get("kustom_kannon") and weapon.get("weapon_type") == "battery":
        fresh = game_state.get_ship_by_id(ship.id) or ship
        fresh.ordnance_loaded_torps = False
        game_state.update_ship(fresh)


def _torpedo_crit_location(ship: Ship) -> set:
    """Armament crit results that hit a ship's torpedo launchers."""
    locs = set()
    for w in ship.weapons:
        if w.get("weapon_type") != "torpedo":
            continue
        arcs = w.get("arcs", [])
        if "left" in arcs and "front" in arcs and "right" in arcs:
            locs.add("dorsal_armament")
        elif "front" in arcs:
            locs.add("prow_armament")
        elif "left" in arcs:
            locs.add("port_armament")
        elif "right" in arcs:
            locs.add("starboard_armament")
    return locs


def torpedo_launcher_crit(target: Ship, crit_type: str, dice: DiceRoller,
                          game_state: GameState, summary: Optional[Dict] = None) -> bool:
    """A ship carrying unused melta torpedoes that suffers a critical hit to its
    torpedo launcher location takes D3 extra Fire critical hits; unused vortex
    torpedoes deal D3 extra damage and an automatic critical hit (s.16). The
    salvo isn't lost when they explode (owner ruling): only firing it ends the
    risk. Inferno torpedoes (Ordo Hereticus) inflict D6 Fire results every time.
    True if the ship is reduced to 0."""
    if crit_type not in _torpedo_crit_location(target):
        return False
    from .ordnance import unused_once_torpedoes, ship_torpedo_types
    if "inferno" in ship_torpedo_types(target):
        # Inferno Torpedoes: a torpedo-launcher critical inflicts D6 Fire results
        n = dice.roll_d6(1, f"{target.name} inferno torpedoes ignite (D6 Fire)")[0]
        game_state.add_log(f"  {target.name}'s inferno torpedoes ignite: {n} Fire critical hit(s)")
        add_fire_crits(target, n, game_state, write=False)
    unused = unused_once_torpedoes(target)
    for kind in ("melta", "vortex"):
        if kind not in unused:
            continue
        n = dice.roll_d3(f"{target.name} unused {kind} torpedoes explode (D3)")
        if kind == "melta":
            game_state.add_log(f"  {target.name}'s unused melta torpedoes explode: "
                               f"{n} Fire critical hit(s)")
            add_fire_crits(target, n, game_state, write=False)
        else:
            game_state.add_log(f"  {target.name}'s unused vortex torpedoes explode: "
                               f"{n} extra damage and a critical hit")
            target.hits_remaining = max(0, target.hits_remaining - n)
            if target.hits_remaining <= 0:
                return True
            if roll_critical_hit(target, dice, game_state, summary):
                return True
    return False


def add_fire_crits(target: Ship, n: int, game_state: GameState, write: bool = True) -> None:
    """n automatic Fire critical hits (melta torpedoes), even on ships whose
    critical hit table has no Fire result."""
    for _ in range(n):
        target.critical_damage.append({
            "crit_type": "fire", "description": "Fire!", "repairable": True,
            "turn_inflicted": game_state.turn_number})
    if write:
        fresh = game_state.get_ship_by_id(target.id) or target
        fresh.critical_damage = list(target.critical_damage)
        game_state.update_ship(fresh)


# Orientation difficulty (from attacker's perspective): lower = easier to target = better column
# If attacker picks difficulty D, eligible ships are those with difficulty ≤ D
ORIENTATION_DIFFICULTY = {"closing": 0, "moving_away": 1, "abeam": 2}


def eligible_orientations(chosen: str) -> List[str]:
    """Return all orientations an attacker can score hits on when targeting `chosen`."""
    max_diff = ORIENTATION_DIFFICULTY.get(chosen, 2)
    return [o for o, d in ORIENTATION_DIFFICULTY.items() if d <= max_diff]


def allocate_squadron_hits(dice_values: List[int], ships: List[Ship],
                           armor_of, apply_hits) -> Dict[str, int]:
    """Core rules s.8, Shooting at Squadrons: hits go to the nearest eligible
    ship until it is destroyed (critical damage included), then the next
    nearest takes the remaining hits, and so on. Mixed armour: roll against the
    lowest Armour and allocate the dice one at a time, lowest rolls first, each
    to the nearest ship it can hit.

    ships: eligible squadron members, nearest first.
    armor_of(ship): the armour a die must equal or beat to hit that ship.
    apply_hits(ship, n): applies n hits and returns (unused_hits, destroyed).
    A ship that survives keeps the dice given to it.
    Returns hits applied per ship id.
    """
    alive = list(ships)
    buckets: Dict[str, List[int]] = {sh.id: [] for sh in ships}

    def allocate(dice):
        for d in sorted(dice):
            target = next((sh for sh in alive if d >= armor_of(sh)), None)
            if target is not None:
                buckets[target.id].append(d)

    allocate(dice_values)
    applied: Dict[str, int] = {}
    for ship in list(ships):
        dice = sorted(buckets[ship.id])
        if not dice:
            continue
        unused, destroyed = apply_hits(ship, len(dice))
        consumed = len(dice) - unused
        applied[ship.id] = consumed
        if destroyed:
            alive.remove(ship)
            allocate(dice[consumed:])       # leftover dice move on
    return applied


def squadron_group(target: Ship, all_ships: List[Ship]) -> List[Ship]:
    """The squadron a target belongs to, as fired upon (core rules s.8): the
    living members chain-coherent with it. A ship not in a squadron, or one
    that has broken formation, is just itself."""
    if not target.squadron_id:
        return [target]
    members = [s for s in all_ships
               if s.squadron_id == target.squadron_id and s.player == target.player
               and not s.is_destroyed and not s.is_disengaged and s.status == "active"]
    if len(members) <= 1:
        return [target]
    from .squadron import get_coherency_components
    groups, _ = get_coherency_components(members)
    for group in groups:
        if any(m.id == target.id for m in group):
            return group
    return [target]


def squadron_fire_preview(attacker: Ship, weapon: Dict, group: List[Ship],
                          orientation: Optional[str] = None,
                          phenomena: list = None, blast_markers: list = None,
                          range_cap: Optional[float] = None) -> Dict:
    """Which members of a targeted squadron this weapon can hit, and why not.

    Returns {"eligible": [ships nearest first], "ineligible": [(ship, reason)]}.
    A member is eligible if it is in arc, in range and line of sight, and (for
    gunnery, when an orientation is given) not presenting a harder aspect than
    the one fired at (core rules s.8).
    """
    allowed = eligible_orientations(orientation) if orientation else None
    from .chapter_tactics import weapon_range
    max_range = weapon_range(attacker, weapon) or 999
    if range_cap is not None:
        max_range = min(max_range, range_cap)
    eligible, ineligible = [], []
    for m in sorted(group, key=attacker.distance_to):
        aspect = attacker.get_target_orientation(m)
        if allowed is not None and aspect not in allowed:
            reason = f"{aspect.replace('_', ' ')}: harder than {orientation.replace('_', ' ')}"
        elif not check_weapon_in_arc(attacker, weapon, m.x, m.y):
            reason = "out of arc"
        elif attacker.distance_to(m) > max_range:
            reason = "out of range"
        elif not check_los_clear(attacker, m, phenomena or [], blast_markers or []).get("clear", True):
            reason = "no line of sight"
        else:
            eligible.append(m)
            continue
        ineligible.append((m, reason))
    return {"eligible": eligible, "ineligible": ineligible}


def eligible_squadron_targets(attacker: Ship, weapon: Dict, group: List[Ship],
                              orientation: Optional[str] = None,
                              phenomena: list = None, blast_markers: list = None,
                              range_cap: Optional[float] = None) -> List[Ship]:
    """Members of a targeted squadron this weapon can hit, nearest first."""
    return squadron_fire_preview(attacker, weapon, group, orientation, phenomena,
                                 blast_markers, range_cap)["eligible"]


def fire_at_squadron(attacker: Ship, weapon: Dict, target: Ship, group: List[Ship],
                     dice: DiceRoller, apply_hits, lock_on: bool = False,
                     blast_markers: list = None, phenomena: list = None,
                     all_ships: list = None, no_column_shifts: bool = False,
                     range_cap: Optional[float] = None):
    """Fire one battery or lance weapon at the squadron `target` belongs to.

    A Leadership test can't pick out one ship in a squadron (s.8): picking a
    member declares the squadron as the target and that ship's aspect as the
    aspect fired at. Hits then go nearest-first via allocate_squadron_hits;
    apply_hits(ship, n) -> (unused_hits, destroyed).
    Returns (ShotResult, hits applied per ship id).
    """
    is_battery = weapon.get("weapon_type") == "battery"
    orientation = attacker.get_target_orientation(target) if is_battery else None
    eligible = eligible_squadron_targets(attacker, weapon, group, orientation,
                                         phenomena, blast_markers, range_cap)
    if not eligible:
        eligible = [target]
    if is_battery:
        sr = resolve_batteries_vs_squadron(
            attacker, weapon, gunnery_target_type(target), orientation, eligible,
            dice, blast_markers or [], lock_on, phenomena, all_ships, no_column_shifts)
        applied = allocate_squadron_hits(sr.dice_rolled, eligible,
                                         lambda m: sr.armors[m.id], apply_hits)
    else:
        # Lances hit on 4+ whatever the armour, so every hit can go to any ship
        sr = resolve_lances(attacker, eligible[0], weapon, dice, lock_on)
        applied = allocate_squadron_hits([4] * sr.hits, eligible, lambda m: 4, apply_hits)
    sr.hits = sum(applied.values())
    return sr, applied


_ASPECT_ORDER = ("closing", "moving_away", "abeam")       # easiest to hardest


def plan_squadron_volley(contributions: List[Tuple[Ship, Dict]], targets: List[Ship],
                         blast_markers: list, phenomena: list = None,
                         all_ships: list = None, no_column_shifts: bool = False,
                         aspect_choice: Optional[Dict[tuple, str]] = None) -> Dict:
    """Plan combined squadron battery fire (s.8, Shooting by Squadrons) at one
    ship or at a squadron (`targets`, the target's squadron group).

    Members that see the target(s) from different aspects or ranges work out
    their firepower separately (one gunnery lookup per group); the dice are
    then combined into one attack per set of target ships and Armour values
    they need. Against a squadron, each group of attackers seeing a different
    mix of target aspects chooses the aspect it fires at (`aspect_choice`:
    {view key: aspect}; default the hardest aspect present, so every ship it
    can see is eligible) and can only hit ships presenting that aspect or an
    easier one.

    Returns {"attacks": [{"dice", "eligible" (nearest first), "armors" {id:
    armour}, "label"}], "views": {view key: [aspects present]}, "skipped":
    [(attacker, weapon, reason)]}."""
    aspect_choice = aspect_choice or {}
    groups: Dict[tuple, Dict] = {}
    views: Dict[tuple, List[str]] = {}
    skipped = []
    for attacker, weapon in contributions:
        aspects = {m.id: attacker.get_target_orientation(m) for m in targets}
        view = tuple(sorted(aspects.items()))
        present = sorted(set(aspects.values()), key=_ASPECT_ORDER.index)
        views[view] = present
        chosen = aspect_choice.get(view) or present[-1]
        eligible = eligible_squadron_targets(attacker, weapon, targets, chosen,
                                             phenomena, blast_markers)
        if not eligible:
            skipped.append((attacker, weapon, "no target it can hit"))
            continue
        shifts = (0 if no_column_shifts else
                  get_column_shifts(attacker, eligible[0], blast_markers, phenomena,
                                    all_ships, weapon))
        column = get_gunnery_column(gunnery_target_type(eligible[0]), chosen)
        armors = tuple((m.id, weapon.get("hits_on") or m.armor_vs(attacker.x, attacker.y))
                       for m in eligible)
        key = (column, shifts, tuple(m.id for m in eligible), armors)
        g = groups.setdefault(key, {"members": [], "eligible": eligible, "column": column,
                                    "shifts": shifts, "aspect": chosen})
        g["members"].append((attacker, weapon))

    attacks: Dict[tuple, Dict] = {}
    for (column, shifts, ids, armors), g in groups.items():
        members = g["members"]
        escorts = [(a, w) for a, w in members if a.ship_type == "escort"]
        others = [(a, w) for a, w in members if a.ship_type != "escort"]
        fp = sum(effective_battery_firepower(a, w, g["eligible"][0]) for a, w in others)
        if escorts:
            # Escorts total their firepower first, then halve it (rounding up)
            esc = sum(battery_base_firepower(a, w, g["eligible"][0]) for a, w in escorts)
            lead = escorts[0][0]
            if lead.special_order in (SpecialOrder.ALL_AHEAD_FULL.value,
                                      SpecialOrder.BURN_RETROS.value,
                                      SpecialOrder.COME_TO_NEW_HEADING.value):
                esc = (esc + 1) // 2
            if lead.special_order == SpecialOrder.BRACE_FOR_IMPACT.value:
                esc = (esc + 1) // 2
            fp += esc
        n = lookup_gunnery_dice(fp, column, shifts) if fp > 0 else 0
        if n <= 0:
            continue
        a = attacks.setdefault((ids, armors), {"dice": 0, "eligible": g["eligible"],
                                                "armors": dict(armors), "parts": []})
        a["dice"] += n
        a["parts"].append(f"{', '.join(m.name for m, _ in members)}: FP{fp} "
                          f"{g['aspect'].replace('_', ' ')} col {column}"
                          f"{f' {shifts:+d} shift' if shifts else ''} -> {n} dice")
    out = []
    for a in attacks.values():
        need = sorted(set(a["armors"].values()))
        a["label"] = (f"{a['dice']} dice vs {'/'.join(f'{x}+' for x in need)} "
                      f"({'; '.join(a['parts'])})")
        out.append(a)
    return {"attacks": out, "views": views, "skipped": skipped}


def volley_expected_hits(plan: Dict) -> float:
    """Rough expected hits of a planned volley: each attack's dice against the
    Armour of the nearest ship it can hit (hits go nearest first, s.8)."""
    total = 0.0
    for a in plan["attacks"]:
        need = a["armors"][a["eligible"][0].id] if a["eligible"] else 6
        total += a["dice"] * max(1, 7 - need) / 6.0
    return total


def best_aspect_choice(contributions, targets, blast_markers, phenomena=None,
                       all_ships=None, no_column_shifts: bool = False) -> Dict[tuple, str]:
    """"Best for expected hits" (Combine Squadron Fire against a squadron): for
    each group of firers that sees a mix of target aspects, the aspect that gives
    the volley the most expected hits (volley_expected_hits). A harder aspect
    lets the group hit more of the squadron; an easier one gives more dice on
    the gunnery table but fewer ships it can hit. Views are improved one at a
    time, twice over. Returns {view key: aspect}."""
    kw = dict(no_column_shifts=no_column_shifts)
    views = plan_squadron_volley(contributions, targets, blast_markers, phenomena,
                                 all_ships, **kw)["views"]
    choice = {v: present[-1] for v, present in views.items()}
    for _ in range(2):
        for v, present in views.items():
            if len(present) < 2:
                continue
            best_a, best_h = choice[v], -1.0
            for a in present:
                trial = {**choice, v: a}
                h = volley_expected_hits(plan_squadron_volley(
                    contributions, targets, blast_markers, phenomena, all_ships,
                    aspect_choice=trial, **kw))
                if h > best_h + 1e-9:
                    best_a, best_h = a, h
            choice[v] = best_a
    return choice


def resolve_squadron_volley(plan: Dict, targets: List[Ship], dice: DiceRoller,
                            apply_hits, lock_on: bool = False,
                            game_state: Optional[GameState] = None) -> Dict[str, int]:
    """Roll and apply a planned volley. Against one ship, every attack's hits
    are applied together; against a squadron each attack (a set of target
    ships and scores) resolves separately with hits allocated nearest first.
    Blast markers placed by one attack don't make the target harder to hit
    for the others: every group's column shifts were worked out from the
    markers before the volley (plan_squadron_volley). Shields knocked down by
    one attack stay down for the rest (owner ruling). apply_hits(ship, n) ->
    (unused, destroyed). Returns hits applied per ship id."""
    applied: Dict[str, int] = {}
    rolled = []
    for a in plan["attacks"]:
        need = min(a["armors"].values())
        ds = dice.roll_d6(a["dice"], f"Squadron volley: {a['label']}")
        if lock_on and any(d < need for d in ds):
            ds = [dice.roll_d6(1, "Lock On re-roll")[0] if d < need else d for d in ds]
        rolled.append((a, ds))
    if len(targets) == 1:
        t = targets[0]
        hits = sum(1 for a, ds in rolled for d in ds if d >= a["armors"][t.id])
        if hits:
            apply_hits(t, hits)
            applied[t.id] = hits
    else:
        for a, ds in rolled:
            got = allocate_squadron_hits(ds, a["eligible"], lambda m, a=a: a["armors"][m.id],
                                         apply_hits)
            for k, v in got.items():
                applied[k] = applied.get(k, 0) + v
    return applied


def resolve_batteries_vs_squadron(
        attacker: Ship, weapon: Dict, target_type: str,
        chosen_orientation: str, eligible_ships: List["Ship"],
        dice: "DiceRoller", blast_markers: List,
        lock_on: bool = False, phenomena: list = None,
        all_ships: list = None, no_column_shifts: bool = False) -> "ShotResult":
    """Fire a battery weapon at a group of squadron ships (hit-allocation rules).

    chosen_orientation: the orientation the attacker declared ("closing", "moving_away",
        or "abeam").  Only ships presenting that orientation or an easier one are eligible.
    eligible_ships: filtered to range + arc + orientation, sorted nearest-first.

    Rolls the dice only. The caller allocates them with allocate_squadron_hits,
    using result.armors, because overflow to the next ship depends on how the
    damage (shields, brace saves, critical hits) resolves on each one.
    """
    result = ShotResult(weapon.get("name", "Battery"), "battery")
    if not eligible_ships:
        result.description = "no eligible targets"
        return result

    fp = effective_battery_firepower(attacker, weapon, eligible_ships[0])
    if fp <= 0:
        result.description = "no firepower"
        return result

    column = get_gunnery_column(target_type, chosen_orientation)
    if no_column_shifts:
        shifts = 0
    else:
        shifts = get_column_shifts(attacker, eligible_ships[0], blast_markers,
                                   phenomena, all_ships, weapon)
    num_dice = lookup_gunnery_dice(fp, column, shifts)

    raw_dice = dice.roll_d6(num_dice, f"Sqn fire {weapon['name']} FP{fp}")

    def armor_for(ship: "Ship") -> int:
        return weapon.get("hits_on") or ship.armor_vs(attacker.x, attacker.y)

    armors = {s.id: armor_for(s) for s in eligible_ships}
    min_armor = min(armors.values()) if armors else 7

    if lock_on:
        final_dice = [dice.roll_d6(1, "Lock On reroll")[0] if d < min_armor else d
                      for d in raw_dice]
        result.reroll_dice = [r for r, d in zip(final_dice, raw_dice) if r != d]
    else:
        final_dice = list(raw_dice)

    result.dice_rolled = final_dice
    result.armors = armors
    result.description = (
        f"{attacker.name} fires {weapon['name']} FP{fp} at squadron "
        f"[{chosen_orientation} col {column}]: {num_dice} dice {sorted(final_dice)}"
    )
    return result


_RAM_SIZE_RANK = {"escort": 1, "cruiser": 2, "battleship": 3, "defense": 4}


def ram_ld_dice(rammer_type: str, target_type: str) -> int:
    """Return number of d6 to roll for the ramming leadership test.

    Target larger → 1D6 (easier); same size → 2D6; target smaller → 3D6 (harder).
    Defences count as the largest type (most immobile).
    """
    r = _RAM_SIZE_RANK.get(rammer_type, 2)
    t = _RAM_SIZE_RANK.get(target_type, 2)
    if t > r:
        return 1
    if t < r:
        return 3
    return 2


def resolve_ram(rammer: Ship, target: Ship, dice: DiceRoller,
                game_state: GameState) -> Dict:
    """Resolve ramming damage for both ships.

    Damage ignores shields on both sides.  The caller is responsible for calling
    check_destruction / resolve_catastrophic after this returns.
    Returns a summary dict with rolls and hits for both ships.
    """
    # Determine which armor face of the target the rammer struck
    target_bearing_to_rammer = target.bearing_to(rammer.x, rammer.y)
    target_arc = target.get_arc_for_bearing(target_bearing_to_rammer)
    target_armor = target.armor_for_arc(target_arc)
    target_facing = ("prow" if target_arc == Arc.FRONT
                     else "rear" if target_arc == Arc.REAR and target.armor_rear else "side")

    # Front-to-front: rammer is in target's front arc AND target is in rammer's front
    rammer_bearing_to_target = rammer.bearing_to(target.x, target.y)
    rammer_arc = rammer.get_arc_for_bearing(rammer_bearing_to_target)
    front_to_front = (target_arc == Arc.FRONT and rammer_arc == Arc.FRONT)

    if front_to_front or target.ship_type == "defense":
        n_rammer_dice = target.hits_max
    else:
        n_rammer_dice = (target.hits_max + 1) // 2
    rammer_armor = rammer.armor_prow_value

    # Both ships face damage: each may brace before the dice are rolled (s.7;
    # the ram's Leadership test has already been passed)
    target_braced = offer_brace(game_state, target, rammer.id, f"{rammer.name} (ram)",
                                rammer.hits_max * max(0, 7 - target_armor) / 6)
    rammer_braced = offer_brace(game_state, rammer, target.id, f"{target.name} (ram)",
                                n_rammer_dice * max(0, 7 - rammer_armor) / 6)
    target = game_state.get_ship_by_id(target.id) or target
    rammer = game_state.get_ship_by_id(rammer.id) or rammer

    # --- Damage to target ---
    n_target_dice = rammer.hits_max
    target_rolls = dice.roll_d6(n_target_dice, f"Ram: {rammer.name} hits {target.name}")
    target_raw_hits = sum(1 for r in target_rolls if r >= target_armor)
    if target_raw_hits > 0:
        apply_damage(target, target_raw_hits, dice, game_state, ignores_shields=True,
                     target_braced=target_braced, attacker_key=rammer.id)

    # --- Counter-damage to rammer ---
    rammer_rolls = dice.roll_d6(n_rammer_dice, f"Ram counter: {target.name} hits {rammer.name}")
    rammer_raw_hits = sum(1 for r in rammer_rolls if r >= rammer_armor)
    if rammer_raw_hits > 0:
        rammer = game_state.get_ship_by_id(rammer.id) or rammer
        apply_damage(rammer, rammer_raw_hits, dice, game_state, ignores_shields=True,
                     target_braced=rammer_braced, attacker_key=target.id)

    game_state.add_log(
        f"  RAM: {rammer.name} ({n_target_dice}d6 vs {target_armor}+) → "
        f"{target_raw_hits} hits on {target.name} [{target_facing}]; "
        f"{target.name} counter ({n_rammer_dice}d6 vs {rammer_armor}+) → "
        f"{rammer_raw_hits} hits on {rammer.name}")

    return {
        "target_facing": target_facing,
        "front_to_front": front_to_front,
        "target_rolls": target_rolls,
        "target_hits": target_raw_hits,
        "rammer_rolls": rammer_rolls,
        "rammer_hits": rammer_raw_hits,
    }


def uses_crit_table(ship: Ship) -> bool:
    """Escorts and defenses with fewer than 3 starting hits don't roll on the
    Critical Hits table: a critical hit is 1 extra point of damage instead."""
    return not (ship.ship_type in ("escort", "defense") and ship.hits_max < 3)


def becomes_blast_marker(ship: Ship) -> bool:
    """Escorts, and defenses with fewer than 3 starting hits, are replaced by a
    blast marker at 0 hits; they never roll catastrophic damage or become hulks."""
    return ship.ship_type == "escort" or (
        ship.ship_type == "defense" and ship.hits_max < 3)


def replace_with_blast_marker(ship: Ship, game_state: GameState) -> None:
    """Remove a destroyed escort (or small defense) and leave a blast marker."""
    ship.status = "destroyed"
    ship.hits_remaining = 0
    game_state.update_ship(ship)
    game_state.add_log(f"{ship.name} destroyed - replaced with blast marker")
    marker_id = f"wreck_{ship.id}"
    if not any(bm["id"] == marker_id for bm in game_state.blast_markers):
        game_state.add_blast_marker(BlastMarker(
            id=marker_id, x=ship.x, y=ship.y, source="destroyed_escort",
            heading=random.uniform(0, 360)))


def resolve_catastrophic(ship: Ship, dice: DiceRoller, game_state: GameState) -> str:
    """Roll on catastrophic damage table for a destroyed capital ship."""
    if becomes_blast_marker(ship):
        replace_with_blast_marker(ship, game_state)
        return "escort_destroyed"

    if "catastrophic_3d6" in ship.special_rules:
        # Mercury: 3D6 instead of 2D6, any result over 12 counts as 12
        roll = min(12, sum(dice.roll_d6(3, f"Catastrophic Damage for {ship.name} (3D6)")))
    else:
        roll = dice.roll_2d6(f"Catastrophic Damage for {ship.name}")
    result = lookup_catastrophic(roll)
    game_state.add_log(f"Catastrophic Damage on {ship.name}: {result} (rolled {roll})")

    if result == "drifting_hulk":
        ship.status = "drifting_hulk"
        ship.hits_remaining = 0
        game_state.update_ship(ship)
        game_state.add_log(f"  {ship.name} is now a DRIFTING HULK")

    elif result == "burning_hulk":
        ship.status = "burning_hulk"
        ship.hits_remaining = 0
        game_state.update_ship(ship)
        game_state.add_log(f"  {ship.name} is now a BURNING HULK")

    elif result in ("plasma_drive_overload", "warp_drive_implosion"):
        ship.status = "destroyed"
        ship.hits_remaining = 0
        game_state.update_ship(ship)
        resolve_explosion(ship, result, dice, game_state)

    return result


def resolve_explosion(ship: Ship, result: str, dice: DiceRoller,
                      game_state: GameState) -> List[str]:
    """Plasma drive overload or warp drive implosion centred on `ship`.

    Places blast markers, destroys ordnance in the 3D6cm radius, and hits
    every ship inside it with lance shots. A ship the blast destroys rolls
    its own catastrophic damage, so explosions can chain. Returns the log
    lines (also written to the game log).
    """
    lines: List[str] = []

    def log(msg):
        lines.append(msg)
        game_state.add_log(msg)

    strength = (ship.hits_max // 2 if result == "plasma_drive_overload"
                else ship.hits_max)
    blast_radius = sum(dice.roll_d6(3, "Explosion blast radius"))
    log(f"  EXPLOSION: {blast_radius}cm radius, "
        f"{strength} lance shots, {strength} blast markers")

    for i in range(strength):
        angle = (360 / strength) * i
        game_state.add_blast_marker(BlastMarker(
            id=f"explosion_{ship.id}_{i}",
            x=ship.x + EXPLOSION_BLAST_OFFSET_CM * math.cos(math.radians(angle)),
            y=ship.y + EXPLOSION_BLAST_OFFSET_CM * math.sin(math.radians(angle)),
            source="explosion", heading=angle))

    surviving = [o for o in game_state.ordnance
                 if math.hypot(o["x"] - ship.x, o["y"] - ship.y) > blast_radius]
    if len(surviving) < len(game_state.ordnance):
        log(f"  {len(game_state.ordnance) - len(surviving)} ordnance marker(s) "
            f"destroyed in the blast")
        game_state.ordnance = surviving

    for other_id in [s.id for s in game_state.get_ships()]:
        # Re-read each ship: a chained explosion may already have hit it
        other = game_state.get_ship_by_id(other_id)
        # Hulks in the blast are hit too (they re-roll catastrophic damage)
        if (not other or other.id == ship.id or other.status == "destroyed"
                or other.is_disengaged
                or (other.is_destroyed
                    and other.status not in ("drifting_hulk", "burning_hulk"))):
            continue
        dist = ship.distance_to(other)
        if dist > blast_radius:
            continue
        # The blast radius is known: ships caught in it may brace before the
        # lance shots are rolled (s.7)
        braced = offer_brace(game_state, other, ship.id, f"{ship.name} exploding",
                             strength * 0.5)
        other = game_state.get_ship_by_id(other.id) or other
        lance_dice = dice.roll_d6(
            strength, f"Explosion lance hits on {other.name} (4+)")
        hits = sum(1 for d in lance_dice if d >= 4)
        log(f"  {other.name} within blast radius ({dist:.1f}cm): {hits} hit(s)")
        if hits:
            apply_damage(other, hits, dice, game_state, target_braced=braced, rolled_to_hit=False,
                         attacker_key=ship.id, origin=(ship.x, ship.y))
            victim = game_state.get_ship_by_id(other.id)
            # A hulk already re-rolled inside apply_damage
            if victim and victim.hits_remaining <= 0 and victim.status == "active":
                log(f"  {victim.name} is destroyed by the explosion!")
                log(f"  {victim.name}: "
                    f"{resolve_catastrophic(victim, dice, game_state)}")
    return lines


def _resolve_crit_cascade(roll_2d6: int, ship: Ship,
                           game_state: GameState) -> Optional[Dict]:
    """
    Resolve a critical hit with cascade rules.
    - If the rolled crit can't apply (no weapons in that slot), cascade to next highest
    - If an unrepairable crit already exists at that location, cascade to next highest
    - Ablative Prow Armor: ignore prow armament crits entirely (don't cascade)
    Returns the resolved crit data dict, or None if all cascaded off the table.
    """
    # Armament crit types (in table order by roll value)
    ARMAMENT_CRITS = {"dorsal_armament", "starboard_armament",
                      "port_armament", "prow_armament", "keel_armament"}
    from .tables import crit_table_for
    table = crit_table_for(ship)

    test_roll = roll_2d6
    while test_roll <= 12:
        crit_data = table.get(test_roll)
        if crit_data is None:
            test_roll += 1
            continue

        crit_type = crit_data["crit_type"]

        # Special: Ablative Prow Armor ignores prow armament crits entirely
        if (crit_type == "prow_armament" and
                "ablative_prow_armor" in ship.special_rules):
            game_state.add_log(
                "  Prow Armament crit ignored (Ablative Prow Armor)")
            return None  # absorbed, not cascaded

        # Check if armament slot exists on this ship
        if crit_type in ARMAMENT_CRITS:
            if not ship.has_armament_slot(crit_type):
                game_state.add_log(
                    f"  {crit_data['name']}: no matching weapons, cascading up")
                test_roll += 1
                continue

        # Check if unrepairable crit already exists at this location
        if not crit_data["repairable"]:
            already_has = any(
                c.get("crit_type") == crit_type
                for c in ship.critical_damage)
            if already_has:
                game_state.add_log(
                    f"  {crit_data['name']}: already present (unrepairable), cascading up")
                test_roll += 1
                continue

        # This crit can apply
        if test_roll != roll_2d6:
            game_state.add_log(
                f"  Crit cascaded from {table[roll_2d6]['name']} "
                f"to {crit_data['name']}")
        return crit_data

    return None  # cascaded off the top of the table




ARMAGEDDON_RANGE = 90.0


def armageddon_ready(ship: Ship) -> Optional[str]:
    """None if the Planet Killer's Armageddon Gun may fire now, else why not:
    not crippled, not on All Ahead Full / Burn Retros / Brace, loaded."""
    if ship.is_crippled:
        return "the Planet Killer is crippled"
    if ship.special_order in (SpecialOrder.ALL_AHEAD_FULL.value, SpecialOrder.BURN_RETROS.value,
                              SpecialOrder.BRACE_FOR_IMPACT.value):
        return "it is on All Ahead Full, Burn Retros or Brace for Impact"
    if "armageddon_broken" in ship.special_rules:
        return "the gun has shut down for the battle"
    if "armageddon_spent" in ship.special_rules:
        return "it needs Reload Ordnance"
    return None


def armageddon_path(ship: Ship, gs) -> Tuple[float, float, float, float, bool]:
    """(x0, y0, x1, y1, blocked): the template's centre track from the ship's
    stem straight ahead 90cm, stopping where it first meets a phenomenon that
    blocks line of sight (planets, moons, asteroid fields)."""
    from .los import check_los
    h = math.radians(ship.heading)
    x0 = ship.x + ship.base_radius * math.cos(h)
    y0 = ship.y + ship.base_radius * math.sin(h)
    phen = gs.get_phenomena()
    step, d = 0.5, 0.0
    while d < ARMAGEDDON_RANGE:
        nd = min(ARMAGEDDON_RANGE, d + step)
        ax, ay = x0 + d * math.cos(h), y0 + d * math.sin(h)
        bx, by = x0 + nd * math.cos(h), y0 + nd * math.sin(h)
        if not check_los(ax, ay, bx, by, phen).get("clear", True):
            return x0, y0, ax, ay, True
        d = nd
    return x0, y0, x0 + d * math.cos(h), y0 + d * math.sin(h), False


def resolve_armageddon_gun(ship: Ship, gs, dice: DiceRoller) -> Dict:
    """The Planet Killer's Armageddon Gun (07_chaos.md): the nova cannon
    template moved 90cm straight ahead from the stem. A ship whose base the
    centre hole passes over takes D6 hits, any other the template crosses 1;
    shields apply; ordnance it touches is removed; blocked, it stops and
    leaves D6 blast markers at the contact point. It then needs Reload
    Ordnance (`armageddon_spent`). Returns {"hits": {ship id: n}, "blocked",
    "path"} or {"error"}. Not yet: the double / double-6 malfunction on the
    reload roll, exterminating planets (To do 7)."""
    from .geometry import (NOVA_CANNON_TEMPLATE_RADIUS_CM as TR,
                           NOVA_CANNON_CENTER_HOLE_RADIUS_CM as CR)
    from .models import BlastMarker
    why = armageddon_ready(ship)
    if why:
        return {"error": why}
    x0, y0, x1, y1, blocked = armageddon_path(ship, gs)

    def seg(px, py):
        dx, dy = x1 - x0, y1 - y0
        L = dx * dx + dy * dy
        t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L))
        return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))
    hits = {}
    for s in gs.get_ships():
        if s.id == ship.id or s.is_destroyed or s.is_disengaged:
            continue
        d = seg(s.x, s.y)
        if d <= s.base_radius + CR:
            hits[s.id] = dice.roll_d6(1, f"Armageddon Gun: centre over {s.name} (D6 hits)")[0]
        elif d <= s.base_radius + TR:
            hits[s.id] = 1
    gs.ordnance = [o for o in gs.ordnance if seg(o["x"], o["y"]) > TR + 1.0]
    if blocked:
        n = dice.roll_d6(1, "Armageddon Gun blocked: D6 blast markers")[0]
        import random as _r
        for i in range(n):
            gs.add_blast_marker(BlastMarker(id=f"armageddon_{_r.randint(0, 99999)}_{i}",
                                            x=x1 + (i - n / 2) * 1.0, y=y1))
    for sid, n in hits.items():
        t = gs.get_ship_by_id(sid)
        apply_damage(t, n, dice, gs, target_braced=t.special_order
                     == SpecialOrder.BRACE_FOR_IMPACT.value, attacker_key=ship.id,
                     origin=(x0, y0))
    fresh = gs.get_ship_by_id(ship.id)
    fresh.special_rules = list(fresh.special_rules) + ["armageddon_spent"]
    gs.update_ship(fresh)
    gs.add_log(f"{ship.name} fires the Armageddon Gun"
               + (" (blocked)" if blocked else "") + f": {len(hits)} ship(s) hit")
    return {"hits": hits, "blocked": blocked, "path": (x0, y0, x1, y1)}
