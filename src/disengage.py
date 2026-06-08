"""BFG:XR Disengagement - Voluntary and involuntary disengagement"""
import math
from typing import List, Dict
from .models import Ship, BlastMarker, Phenomenon, OrdnanceMarker
from .game_state import GameState
from .dice import DiceRoller


def check_off_table(ship: Ship, table_width: float, table_height: float) -> bool:
    """Check if a ship has moved off the table edge (involuntary disengage)."""
    r = ship.base_radius
    return (ship.x - r < 0 or ship.x + r > table_width or
            ship.y - r < 0 or ship.y + r > table_height)


def process_involuntary_disengage(ship: Ship, gs: GameState):
    """Handle a ship that has moved off the table edge."""
    ship.is_disengaged = True
    ship.status = "disengaged"
    gs.update_ship(ship)
    gs.add_log(f"{ship.name} has moved off the table and DISENGAGED!")


def get_disengage_ld_modifiers(ship: Ship, gs: GameState) -> Dict:
    """
    Calculate Ld modifiers for voluntary disengagement.
    Returns dict with modifier breakdown and final Ld.
    """
    base_ld = ship.leadership
    modifiers = []
    total_mod = 0

    blast_markers = gs.get_blast_markers()
    phenomena = gs.get_phenomena()
    all_ships = gs.get_ships()
    all_ordnance = gs.get_ordnance()

    # Each blast marker within 5cm: +1 Ld (makes it easier to disengage)
    blast_count = 0
    for bm in blast_markers:
        dist = math.sqrt((bm.x - ship.x)**2 + (bm.y - ship.y)**2)
        if dist <= 5:
            blast_count += 1
    if blast_count > 0:
        total_mod += blast_count
        modifiers.append(f"+{blast_count} Ld (blast markers within 5cm)")

    # Celestial phenomena within 15cm: +3 Ld
    for p in phenomena:
        dist = math.sqrt((p.x - ship.x)**2 + (p.y - ship.y)**2)
        if dist <= 15:
            total_mod += 3
            modifiers.append("+3 Ld (celestial phenomena within 15cm)")
            break  # only count once

    # Each enemy ship within 15cm: -1 Ld
    enemy_count = 0
    for s in all_ships:
        if s.player != ship.player and not s.is_destroyed and not s.is_disengaged:
            dist = ship.distance_to(s)
            if dist <= 15:
                enemy_count += 1
    # Each enemy ordnance within 15cm: -1 Ld
    for o in all_ordnance:
        if o.owner_player != ship.player:
            dist = math.sqrt((o.x - ship.x)**2 + (o.y - ship.y)**2)
            if dist <= 15:
                enemy_count += 1
    if enemy_count > 0:
        total_mod -= enemy_count
        modifiers.append(f"-{enemy_count} Ld (enemies/ordnance within 15cm)")

    effective_ld = min(10, max(2, base_ld + total_mod))

    return {
        "base_ld": base_ld,
        "modifiers": modifiers,
        "total_modifier": total_mod,
        "effective_ld": effective_ld,
    }


def attempt_disengage(ship: Ship, dice: DiceRoller, gs: GameState) -> Dict:
    """
    Attempt voluntary disengagement at end of movement phase.
    Returns dict with success status and details.
    In carrier_escape scenario, the escaping player cannot disengage until ftl_available_turn.
    """
    if gs.ftl_available_turn and gs.turn_number < gs.ftl_available_turn:
        if gs.scenario_mode == "capture_artefact" and gs.artefact_submode == "carrier_escape":
            if ship.player == gs.scenario_attacker:
                return {
                    "success": False,
                    "roll": 0,
                    "needed": 0,
                    "modifiers": [f"FTL not charged until turn {gs.ftl_available_turn}"],
                    "blocked": True,
                }
        elif gs.scenario_mode != "capture_artefact":
            return {
                "success": False,
                "roll": 0,
                "needed": 0,
                "modifiers": [f"FTL not charged until turn {gs.ftl_available_turn}"],
                "blocked": True,
            }

    ld_info = get_disengage_ld_modifiers(ship, gs)
    ld = ld_info["effective_ld"]

    roll = dice.roll_2d6(
        f"{ship.name} disengage check (need <= {ld})")
    passed = roll <= ld

    result = {
        "success": passed,
        "roll": roll,
        "needed": ld,
        "modifiers": ld_info["modifiers"],
    }

    if passed:
        ship.is_disengaged = True
        ship.status = "disengaged"
        gs.update_ship(ship)
        gs.add_log(
            f"{ship.name} DISENGAGED successfully "
            f"(rolled {roll} vs Ld {ld})")
    else:
        # Failed: cannot fire, launch ordnance, or use special orders
        # (except Brace) for rest of turn
        ship.disengage_failed_this_turn = True
        ship.has_fired = True  # prevent firing
        gs.update_ship(ship)
        gs.add_log(
            f"{ship.name} disengage FAILED (rolled {roll} vs Ld {ld}). "
            f"No firing or orders this turn!")

    return result
