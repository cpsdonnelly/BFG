"""BFG:XR Disengagement - Voluntary and involuntary disengagement"""
import math
from typing import Dict, List, Optional
from .models import Ship
from .game_state import GameState
from .dice import DiceRoller


def check_off_table(ship: Ship, table_width: float, table_height: float) -> bool:
    """Check if a ship has moved off the table edge (involuntary disengage)."""
    r = ship.base_radius
    return (ship.x - r < 0 or ship.x + r > table_width or
            ship.y - r < 0 or ship.y + r > table_height)


def process_involuntary_disengage(ship: Ship, gs: GameState, dice: DiceRoller = None):
    """Handle a ship that has moved off the table edge.

    Core rules s.8 (Maneuvering Squadrons): if it was an escort in a squadron,
    the rest of the squadron must immediately, and in later turns, attempt to
    disengage. The immediate test is taken right away (owner ruling); without
    dice the squadron is only flagged and tests at the end of the phase.
    """
    ship.is_disengaged = True
    ship.status = "disengaged"
    gs.update_ship(ship)
    gs.add_log(f"{ship.name} has moved off the table and DISENGAGED!")

    if ship.ship_type != "escort" or not ship.squadron_id:
        return
    rest = [s for s in gs.get_ships()
            if s.squadron_id == ship.squadron_id and s.player == ship.player
            and s.id != ship.id and not s.is_destroyed and not s.is_disengaged]
    if not rest:
        return
    for s in rest:
        s.must_disengage = True
        gs.update_ship(s)
    gs.add_log(f"  Squadron {ship.squadron_id} lost {ship.name} off the table: "
               f"the rest of the squadron must attempt to disengage")
    if dice is not None:
        squadron_disengage_test(rest, dice, gs)


def squadron_disengage_test(ships: List[Ship], dice: DiceRoller, gs: GameState) -> Dict:
    """One disengage test for an escort squadron (s.8, s.37).

    Owner ruling: the Leadership modifiers are those of the best-placed member
    (the highest resulting Leadership). Pass: the whole squadron disengages.
    Fail: none of it may fire, launch ordnance or use special orders (except
    Brace) for the rest of the turn.
    """
    ships = [gs.get_ship_by_id(s.id) for s in ships]
    ships = [s for s in ships if s and not s.is_destroyed and not s.is_disengaged]
    if not ships:
        return {"success": False, "roll": 0, "needed": 0, "modifiers": [], "ships": []}

    blocked = _ftl_blocked(ships[0], gs)
    if blocked:
        return {"success": False, "roll": 0, "needed": 0, "modifiers": [blocked],
                "blocked": True, "ships": [s.id for s in ships]}

    best_ship, best = max(((s, get_disengage_ld_modifiers(s, gs)) for s in ships),
                          key=lambda pair: pair[1]["effective_ld"])
    ld = best["effective_ld"]
    roll = dice.roll_2d6(
        f"Squadron {best_ship.squadron_id} disengage check "
        f"(need <= {ld}, from {best_ship.name}'s position)")
    passed = roll <= ld

    for s in ships:
        s.must_disengage_tested_turn = gs.turn_number
        if passed:
            s.is_disengaged = True
            s.status = "disengaged"
        else:
            s.disengage_failed_this_turn = True
            s.has_fired = True
        gs.update_ship(s)
    names = ", ".join(s.name for s in ships)
    gs.add_log(f"Squadron {best_ship.squadron_id} ({names}) disengage "
               f"{'PASSED' if passed else 'FAILED'} (rolled {roll} vs Ld {ld})")
    return {"success": passed, "roll": roll, "needed": ld,
            "modifiers": best["modifiers"], "ships": [s.id for s in ships]}


def mercenary_must_disengage(ship: Ship, gs: GameState) -> bool:
    """Demiurg Mercenaries (Xenos p.91-94): unless its fleet is all Demiurg, a
    crippled Demiurg ship attempts to disengage every turn (with Ork vessels
    in the opposing fleet, only at 2 or fewer hits remaining)."""
    if "demiurg_commerce" not in ship.special_rules:
        return False
    ships = gs.get_ships()
    if all("demiurg_commerce" in s.special_rules for s in ships if s.player == ship.player):
        return False
    if any(s.player != ship.player and s.faction == "orks" for s in ships):
        return 0 < ship.hits_remaining <= 2
    return ship.is_crippled


def forced_disengage_tests(gs: GameState, dice: DiceRoller, player: int) -> List[Dict]:
    """End of a player's movement phase (s.8, s.37): escort squadrons that must
    disengage, ships or squadrons at Leadership 1 or less (Forced
    Disengagement) and Demiurg mercenaries take their test, unless they
    already tested this turn. A ship that fails heads for the nearest table
    edge next turn (`must_flee`)."""
    squadrons: Dict[str, List[Ship]] = {}
    singles: List[Ship] = []
    for s in gs.get_ships():
        if (s.player != player or s.is_destroyed or s.is_disengaged
                or s.must_disengage_tested_turn == gs.turn_number):
            continue
        forced = s.leadership <= 1 or mercenary_must_disengage(s, gs)
        if s.must_disengage or (forced and s.ship_type == "escort" and s.squadron_id):
            squadrons.setdefault(s.squadron_id, []).append(s)
        elif forced:
            singles.append(s)
    results = []
    for members in squadrons.values():
        mates = [m for m in gs.get_ships() if m.squadron_id == members[0].squadron_id
                 and m.player == player and not m.is_destroyed and not m.is_disengaged]
        results.append(squadron_disengage_test(mates, dice, gs))
    for s in singles:
        gs.add_log(f"{s.name} must attempt to disengage"
                   + (" (Demiurg mercenaries)" if mercenary_must_disengage(s, gs)
                      else " (Leadership 1 or less)"))
        results.append(attempt_disengage(s, dice, gs))
        fresh = gs.get_ship_by_id(s.id)
        fresh.must_disengage_tested_turn = gs.turn_number
        gs.update_ship(fresh)
    for r in results:
        if not r.get("success") and not r.get("blocked"):
            for sid in r.get("ships") or []:
                fresh = gs.get_ship_by_id(sid)
                fresh.must_flee = True
                gs.update_ship(fresh)
    return results


def _ftl_blocked(ship: Ship, gs: GameState) -> Optional[str]:
    """Reason a ship can't disengage yet in an FTL-charging scenario, or None."""
    if gs.ftl_available_turn and gs.turn_number < gs.ftl_available_turn:
        reason = f"FTL not charged until turn {gs.ftl_available_turn}"
        if gs.scenario_mode == "capture_artefact" and gs.artefact_submode == "carrier_escape":
            if ship.player == gs.scenario_attacker:
                return reason
        elif gs.scenario_mode != "capture_artefact":
            return reason
    return None


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
        # Measured to the phenomenon's edge: a planet's circle, else its rectangle
        if "planet" in p.phenomenon_type and p.radius > 0:
            dist = max(0.0, math.hypot(p.x - ship.x, p.y - ship.y) - p.radius)
        else:
            dx = max(0.0, abs(ship.x - p.x) - p.width / 2)
            dy = max(0.0, abs(ship.y - p.y) - p.height / 2)
            dist = math.hypot(dx, dy)
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

    from .movement import slaanesh_penalty
    if slaanesh_penalty(ship, gs):
        total_mod -= 1
        modifiers.append("-1 Ld (Mark of Slaanesh within 15cm)")

    effective_ld = min(10, max(0, base_ld + total_mod))   # Ld 1 or less always fails

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
    blocked = _ftl_blocked(ship, gs)
    if blocked:
        return {"success": False, "roll": 0, "needed": 0,
                "modifiers": [blocked], "blocked": True}

    # An escort squadron tests once, together (s.37)
    if ship.ship_type == "escort" and ship.squadron_id:
        mates = [s for s in gs.get_ships() if s.squadron_id == ship.squadron_id
                 and s.player == ship.player and not s.is_destroyed and not s.is_disengaged]
        if len(mates) > 1:
            return squadron_disengage_test(mates, dice, gs)

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
        "ships": [ship.id],
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
        if ship.squadron_id and ship.ship_type != "escort":
            # A capital ship that fails falls out of its squadron for good (s.37)
            gs.add_log(f"{ship.name} falls out of squadron {ship.squadron_id}")
            ship.squadron_id = ""
        gs.update_ship(ship)
        gs.add_log(
            f"{ship.name} disengage FAILED (rolled {roll} vs Ld {ld}). "
            f"No firing or orders this turn!")

    return result
