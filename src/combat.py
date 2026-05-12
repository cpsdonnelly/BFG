"""BFG:XR Combat System - Shooting phase resolution"""
import math
import random
from typing import List, Dict, Tuple, Optional
from .models import Ship, BlastMarker, Arc, SpecialOrder
from .game_state import GameState
from .tables import (lookup_gunnery_dice, get_gunnery_column, CRITICAL_HITS,
                     lookup_catastrophic)
from .dice import DiceRoller
from .geometry import count_blast_markers_touching


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


class ShootingResult:
    """Result of all weapons from one ship firing at one target."""
    def __init__(self, attacker: str, target: str):
        self.attacker_name = attacker
        self.target_name = target
        self.shots: List[ShotResult] = []
        self.total_hull_damage = 0
        self.total_shield_hits = 0
        self.target_destroyed = False
        self.target_crippled = False
        self.blast_markers_placed = 0
        self.log_lines: List[str] = []


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
    from .los import check_los_ships
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
    from .los import check_los_ships
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


def resolve_batteries(attacker: Ship, target: Ship, weapon: Dict,
                      dice: DiceRoller, blast_markers: List[BlastMarker],
                      lock_on: bool = False,
                      phenomena: list = None,
                      all_ships: list = None,
                      no_column_shifts: bool = False) -> ShotResult:
    """Resolve a weapons battery attack."""
    result = ShotResult(weapon["name"], "battery")
    firepower = weapon["strength"]

    # Halve if crippled
    if attacker.is_crippled:
        firepower = (firepower + 1) // 2

    # Halve if on certain special orders
    if attacker.special_order in (
        SpecialOrder.ALL_AHEAD_FULL.value,
        SpecialOrder.BURN_RETROS.value,
        SpecialOrder.COME_TO_NEW_HEADING.value,
    ):
        firepower = (firepower + 1) // 2

    # Halve again if braced
    if attacker.special_order == SpecialOrder.BRACE_FOR_IMPACT.value:
        firepower = (firepower + 1) // 2

    if firepower <= 0:
        result.description = f"{weapon['name']}: no firepower available"
        return result

    # Determine target type for gunnery table
    if target.ship_type in ("battleship", "cruiser"):
        target_type = "capital"
    elif target.ship_type == "escort":
        target_type = "escort"
    else:
        target_type = "defense"

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
    armor = target.armor_side_value
    # Check if hitting prow
    target_arc_from_attacker = target.get_arc_for_bearing(
        target.bearing_to(attacker.x, attacker.y))
    if target_arc_from_attacker == Arc.FRONT:
        armor = target.armor_prow_value

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
    template_radius = 2.5  # outer radius
    center_radius = 0.6    # center hole radius

    any_ship_hit = False
    for s_dict in game_state.ships:
        s = Ship.from_dict(s_dict)
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
    }

    remaining_hits = hits

    if not ignores_shields:
        # Count blast markers already touching ship to reduce available shields
        existing_blasts = count_blast_markers_touching(target, game_state.get_blast_markers())
        max_shields = target.effective_shields
        available_shields = max(0, max_shields - existing_blasts)

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
    was_crippled = target.is_crippled

    for i in range(summary["hull_hits"]):
        target.hits_remaining -= 1

        if target.hits_remaining <= 0:
            summary["destroyed"] = True
            break

        # Critical hit check: D6 per hull hit, 6 = crit
        crit_roll = dice.roll_d6(1, f"Crit check for hit on {target.name}")
        if crit_roll[0] == 6:
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
                    extra = dice.roll_d3(f"Hull Breach extra damage")
                elif extra == "D6":
                    extra = sum(dice.roll_d6(1, f"Bulkhead Collapse extra damage"))
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
                source=turn_label
            )
            game_state.add_blast_marker(bm)
            existing_bms.append(bm)  # track for overlap checking
            placed += 1

    game_state.update_ship(target)
    return summary




def resolve_catastrophic(ship: Ship, dice: DiceRoller, game_state: GameState) -> str:
    """Roll on catastrophic damage table for a destroyed capital ship."""
    if ship.ship_type == "escort":
        # Escorts just become a blast marker and are removed
        ship.status = "destroyed"
        ship.hits_remaining = 0
        game_state.update_ship(ship)
        game_state.add_log(f"{ship.name} destroyed - replaced with blast marker")
        bm = BlastMarker(id=f"wreck_{ship.id}", x=ship.x, y=ship.y,
                          source="destroyed_escort")
        game_state.add_blast_marker(bm)
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

        # Explosion
        num_markers = ship.hits_max // 2 if result == "plasma_drive_overload" else ship.hits_max
        lance_str = ship.hits_max // 2 if result == "plasma_drive_overload" else ship.hits_max

        blast_radius_roll = dice.roll_d6(3, "Explosion blast radius")
        blast_radius = sum(blast_radius_roll)

        game_state.add_log(
            f"  EXPLOSION: {blast_radius}cm radius, "
            f"{lance_str} lance shots, {num_markers} blast markers")

        # Place blast markers
        for i in range(num_markers):
            angle = (360 / num_markers) * i
            bx = ship.x + 1.5 * math.cos(math.radians(angle))
            by = ship.y + 1.5 * math.sin(math.radians(angle))
            game_state.add_blast_marker(
                BlastMarker(id=f"explosion_{ship.id}_{i}", x=bx, y=by,
                            source="explosion"))

        # Damage nearby ships
        for s_dict in game_state.ships:
            other = Ship.from_dict(s_dict)
            if other.id == ship.id or other.is_destroyed:
                continue
            dist = ship.distance_to(other)
            if dist <= blast_radius:
                game_state.add_log(
                    f"  {other.name} within blast radius ({dist:.1f}cm)")
                lance_dice = dice.roll_d6(
                    lance_str,
                    f"Explosion lance hits on {other.name} (4+)")
                explosion_hits = sum(1 for d in lance_dice if d >= 4)
                if explosion_hits > 0:
                    apply_damage(other, explosion_hits, dice, game_state,
                                ignores_shields=False)

    return result


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
                f"  Prow Armament crit ignored (Ablative Prow Armor)")
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


