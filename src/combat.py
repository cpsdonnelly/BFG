"""BFG:XR Combat System - Shooting phase resolution"""
import math
import random
import re
from typing import List, Dict, Tuple, Optional
from .models import Ship, BlastMarker, Arc, SpecialOrder
from .game_state import GameState
from .tables import (lookup_gunnery_dice, get_gunnery_column, CRITICAL_HITS,
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
    w_range = weapon.get("range_cm", 0)
    if w_range == 0:
        return True  # torpedoes/bays don't have a direct fire range
    return dist <= w_range


def get_column_shifts(ship: Ship, target_ship: Ship,
                      blast_markers: List[BlastMarker],
                      phenomena: list = None,
                      all_ships: list = None) -> int:
    """Calculate gunnery column shifts for weapons batteries."""
    dist = ship.distance_to(target_ship)
    shifts = 0

    # Range modifiers
    if dist < 15:
        shifts -= 1  # left shift (better)
    elif dist > 30:
        shifts += 1  # right shift (worse)

    # LoS-based shifts (blast markers and dust clouds in line of fire)
    phenomena = phenomena or []
    los = check_los_ships(ship, target_ship, phenomena, blast_markers)
    shifts += los.get("column_shifts", 0)

    # Targeting matrix upgrade (Imperial Mars)
    if "targeting_matrix" in ship.special_rules:
        shifts -= 1

    # Tau tracking systems aura - ignore >30cm penalty
    if dist > 30 and _has_tracking_support(ship, all_ships):
        shifts -= 1  # cancel the >30cm right shift

    return shifts


def check_los_clear(ship: Ship, target_ship: Ship,
                    phenomena: list = None,
                    blast_markers: list = None) -> dict:
    """Check if line of sight is clear between attacker and target."""
    phenomena = phenomena or []
    blast_markers = blast_markers or []
    return check_los_ships(ship, target_ship, phenomena, blast_markers)


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


def weapon_fire_pool(attacker: Ship, weapon: Dict, w_idx: int, target_dist: float,
                     dice: DiceRoller) -> Tuple[int, Optional[str], Optional[str]]:
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
    fp = battery_base_firepower(attacker, weapon, target)
    if attacker.is_crippled:
        fp = (fp + 1) // 2
    if attacker.special_order in (
        SpecialOrder.ALL_AHEAD_FULL.value,
        SpecialOrder.BURN_RETROS.value,
        SpecialOrder.COME_TO_NEW_HEADING.value,
    ):
        fp = (fp + 1) // 2
    if attacker.special_order == SpecialOrder.BRACE_FOR_IMPACT.value:
        fp = (fp + 1) // 2
    return fp


def gunnery_target_type(ship: Ship) -> str:
    """Gunnery table target type for a ship: capital, escort or defense.

    A ship that moved less than 5cm in its last movement phase (for any
    reason) counts as Defenses (core rules s.7, Movement).
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
        attacker, target, blast_markers, phenomena, all_ships)

    # Look up dice count
    num_dice = lookup_gunnery_dice(firepower, column, shifts)

    if num_dice <= 0:
        result.description = f"{weapon['name']}: FP {firepower}, 0 dice to roll"
        return result

    # Roll dice
    armor = target.armor_vs(attacker.x, attacker.y)

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

    total_fp = sum(effective_battery_firepower(a, w, target) for a, w in contributions)
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


def resolve_lances(attacker: Ship, target: Ship, weapon: Dict,
                   dice: DiceRoller, lock_on: bool = False) -> ShotResult:
    """Resolve a lance weapon attack."""
    result = ShotResult(weapon["name"], "lance")
    strength = weapon["strength"]

    # Halve if crippled
    if attacker.is_crippled:
        strength = (strength + 1) // 2

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

    # Lances hit on 4+ regardless of armor
    result.dice_rolled = dice.roll_d6(
        strength, f"{attacker.name} lances vs {target.name} (need 4+)")

    result.hits = sum(1 for d in result.dice_rolled if d >= 4)

    # Lock On rerolls
    if lock_on and result.hits < strength:
        misses = [d for d in result.dice_rolled if d < 4]
        if misses:
            result.reroll_dice = dice.roll_d6(
                len(misses), f"{attacker.name} Lock On lance rerolls")
            extra_hits = sum(1 for d in result.reroll_dice if d >= 4)
            result.hits += extra_hits

    result.description = (
        f"{weapon['name']}: Str {strength} lances vs {target.name} "
        f"(4+) = {result.hits} hits")

    return result


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


def apply_damage(target: Ship, hits: int, dice: DiceRoller,
                 game_state: GameState,
                 ignores_shields: bool = False,
                 target_braced: bool = False) -> Dict:
    """
    Apply hits to a ship, handling shields, damage, crits.
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

    if not ignores_shields:
        available_shields = current_shields(target, game_state.get_blast_markers())
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

            # Critical hit check: D6 per hull hit, 6 = crit
            crit_roll = dice.roll_d6(1, f"Crit check for hit on {target.name}")
            if crit_roll[0] == 6 and not uses_crit_table(target):
                # Small escorts/defenses take +1 damage instead of a critical
                target.hits_remaining -= 1
                game_state.add_log(f"Critical on {target.name}: +1 damage")
                if target.hits_remaining <= 0:
                    summary["destroyed"] = True
                    break
            elif crit_roll[0] == 6:
                crit_2d6 = dice.roll_2d6(f"Critical hit on {target.name}")
                crit_data = _resolve_crit_cascade(crit_2d6, target, game_state)

                if crit_data is None:
                    # All results cascaded off the top of the table
                    game_state.add_log(
                        f"Critical on {target.name}: rolled {crit_2d6}, "
                        f"all results cascaded, no effect")
                else:
                    extra = crit_data["extra_damage"]
                    if extra == "D3":
                        extra = dice.roll_d3("Hull Breach extra damage")
                    elif extra == "D6":
                        extra = sum(dice.roll_d6(1, "Bulkhead Collapse extra damage"))
                    elif isinstance(extra, int) and extra > 0:
                        pass

                    crit_entry = {
                        "crit_type": crit_data["crit_type"],
                        "description": crit_data["name"],
                        "repairable": crit_data["repairable"],
                        "turn_inflicted": game_state.turn_number,
                    }
                    target.critical_damage.append(crit_entry)
                    summary["crits"].append(crit_data["name"])

                    game_state.add_log(
                        f"CRITICAL HIT on {target.name}: {crit_data['name']}")

                    if isinstance(extra, int) and extra > 0:
                        target.hits_remaining = max(0, target.hits_remaining - extra)
                        game_state.add_log(f"  Extra damage: {extra} HP")
                        if target.hits_remaining <= 0:
                            summary["destroyed"] = True
                            break

                    if crit_data["crit_type"] == "bridge_smashed":
                        target.leadership = max(1, target.leadership - 3)

        if summary["destroyed"]:
            summary["unused_hits"] = summary["hull_hits"] - hull_hits_applied

        if not was_crippled and target.is_crippled and not summary["destroyed"]:
            summary["crippled"] = True
            game_state.add_log(f"{target.name} is now CRIPPLED")

    # Place blast markers for SHIELD hits only (not hull damage)
    # Rules: no overlapping, fan around ship, max 3-5 (small) or 5-8 (large) per turn
    if summary["blast_markers_placed"] > 0:
        max_per_turn = 5 if target.base_size == "large" else 3
        existing_bms = game_state.get_blast_markers()
        # Count how many blast markers were already placed on this ship this turn
        turn_label = f"shield_impact_t{game_state.turn_number}"
        already_this_turn = sum(
            1 for bm in existing_bms
            if bm.source == turn_label
            and math.sqrt((bm.x - target.x)**2 + (bm.y - target.y)**2) <= target.base_radius + 3
        )
        can_place = max(0, max_per_turn - already_this_turn)
        to_place = min(summary["blast_markers_placed"], can_place)

        if to_place < summary["blast_markers_placed"]:
            game_state.add_log(
                f"  Max blast markers this turn ({max_per_turn}): "
                f"only placing {to_place} of {summary['blast_markers_placed']}")
            summary["blast_markers_placed"] = to_place

        placed = 0
        bm_spacing = 2.2  # minimum cm between blast marker centers
        offset = target.base_radius + 1.2

        for j in range(to_place):
            # Try angles around the ship to find non-overlapping position
            best_angle = None
            for attempt in range(36):
                angle = (2 * math.pi * (already_this_turn + j)) / max_per_turn + (attempt * 0.17)
                bx = target.x + offset * math.cos(angle)
                by = target.y + offset * math.sin(angle)

                # Check overlap with all existing blast markers
                overlaps = False
                for ebm in existing_bms:
                    dist = math.sqrt((bx - ebm.x)**2 + (by - ebm.y)**2)
                    if dist < bm_spacing:
                        overlaps = True
                        break

                if not overlaps:
                    best_angle = angle
                    break

            if best_angle is None:
                # Couldn't find non-overlapping spot, use best effort
                best_angle = (2 * math.pi * (already_this_turn + j)) / max_per_turn

            bx = target.x + offset * math.cos(best_angle)
            by = target.y + offset * math.sin(best_angle)

            bm = BlastMarker(
                id=f"bm_{target.id}_t{game_state.turn_number}_{j}_{random.randint(0,9999)}",
                x=bx, y=by,
                source=turn_label,
                heading=(math.degrees(best_angle) + 180) % 360,
            )
            game_state.add_blast_marker(bm)
            existing_bms.append(bm)  # track for overlap checking
            placed += 1

    game_state.update_ship(target)
    return summary




# Orientation difficulty (from attacker's perspective): lower = easier to target = better column
# If attacker picks difficulty D, eligible ships are those with difficulty ≤ D
ORIENTATION_DIFFICULTY = {"closing": 0, "moving_away": 1, "abeam": 2}


def eligible_orientations(chosen: str) -> List[str]:
    """Return all orientations an attacker can score hits on when targeting `chosen`."""
    max_diff = ORIENTATION_DIFFICULTY.get(chosen, 2)
    return [o for o, d in ORIENTATION_DIFFICULTY.items() if d <= max_diff]


def allocate_squadron_hits(dice_values: List[int], ships: List[Ship],
                           armor_of, apply_hits) -> Dict[str, int]:
    """Core rules s.5, Shooting at Squadrons: hits go to the nearest eligible
    ship until it is destroyed (critical damage included), then the next
    nearest takes the remaining hits, and so on.

    ships: eligible squadron members, nearest first.
    armor_of(ship): the armour a die must equal or beat to hit that ship.
    apply_hits(ship, n): applies n hits and returns (unused_hits, destroyed).
    A ship that survives keeps every hit; nothing passes beyond it.
    Returns hits applied per ship id.
    """
    remaining = sorted(dice_values)
    applied: Dict[str, int] = {}
    for ship in ships:
        usable = [d for d in remaining if d >= armor_of(ship)]
        if not usable:
            break
        unused, destroyed = apply_hits(ship, len(usable))
        consumed = len(usable) - unused
        applied[ship.id] = consumed
        for d in usable[:consumed]:
            remaining.remove(d)
        if not destroyed:
            break
    return applied


def squadron_group(target: Ship, all_ships: List[Ship]) -> List[Ship]:
    """The squadron a target belongs to, as fired upon (core rules s.5): the
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
    the one fired at (core rules s.5).
    """
    allowed = eligible_orientations(orientation) if orientation else None
    max_range = weapon.get("range_cm", 999)
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

    A Leadership test can't pick out one ship in a squadron (s.5): picking a
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
                                   phenomena, all_ships)
    num_dice = lookup_gunnery_dice(fp, column, shifts)

    raw_dice = dice.roll_d6(num_dice, f"Sqn fire {weapon['name']} FP{fp}")

    def armor_for(ship: "Ship") -> int:
        return ship.armor_vs(attacker.x, attacker.y)

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

    # --- Damage to target ---
    n_target_dice = rammer.hits_max
    target_rolls = dice.roll_d6(n_target_dice, f"Ram: {rammer.name} hits {target.name}")
    target_raw_hits = sum(1 for r in target_rolls if r >= target_armor)
    if target_raw_hits > 0:
        apply_damage(target, target_raw_hits, dice, game_state, ignores_shields=True)

    # --- Counter-damage to rammer ---
    if front_to_front or target.ship_type == "defense":
        n_rammer_dice = target.hits_max
    else:
        n_rammer_dice = (target.hits_max + 1) // 2
    rammer_armor = rammer.armor_prow_value
    rammer_rolls = dice.roll_d6(n_rammer_dice, f"Ram counter: {target.name} hits {rammer.name}")
    rammer_raw_hits = sum(1 for r in rammer_rolls if r >= rammer_armor)
    if rammer_raw_hits > 0:
        apply_damage(rammer, rammer_raw_hits, dice, game_state, ignores_shields=True)

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
        if not other or other.id == ship.id or other.is_destroyed:
            continue
        dist = ship.distance_to(other)
        if dist > blast_radius:
            continue
        lance_dice = dice.roll_d6(
            strength, f"Explosion lance hits on {other.name} (4+)")
        hits = sum(1 for d in lance_dice if d >= 4)
        log(f"  {other.name} within blast radius ({dist:.1f}cm): {hits} hit(s)")
        if hits:
            apply_damage(other, hits, dice, game_state)
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
                      "port_armament", "prow_armament"}

    test_roll = roll_2d6
    while test_roll <= 12:
        crit_data = CRITICAL_HITS.get(test_roll)
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
                f"  Crit cascaded from {CRITICAL_HITS[roll_2d6]['name']} "
                f"to {crit_data['name']}")
        return crit_data

    return None  # cascaded off the top of the table


