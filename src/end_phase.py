"""BFG:XR End Phase - Damage control, blast removal, fire damage"""
import math
import random
from typing import List, Dict
from .models import Ship, BlastMarker, SpecialOrder
from .game_state import GameState
from .dice import DiceRoller
from .geometry import count_blast_markers_touching, BASE_CONTACT_THRESHOLD_CM


def resolve_fire_damage(ship: Ship, dice: DiceRoller, gs: GameState) -> List[str]:
    """
    Each unrepaired Fire! crit deals 1 damage in the end phase.
    Returns log messages.
    """
    logs = []
    fires = [c for c in ship.critical_damage if c.get("crit_type") == "fire"]
    if not fires:
        return logs

    for fire in fires:
        ship.hits_remaining -= 1
        logs.append(f"{ship.name}: Fire! deals 1 damage (now {ship.hits_remaining} HP)")

        if ship.hits_remaining <= 0:
            logs.append(f"{ship.name} destroyed by fire!")
            break

    gs.update_ship(ship)
    return logs


def resolve_damage_control(ship: Ship, dice: DiceRoller, gs: GameState,
                           repair_choices: List[str] = None) -> List[str]:
    """
    Damage control: roll 1D6 per remaining HP.
    Each 6 repairs one repairable critical (player chooses which).
    Ships touching blast markers: half dice (round up).

    If repair_choices is None, auto-picks first repairable crits (for AI/auto mode).
    If repair_choices is provided, it's a list of crit descriptions to repair.
    """
    logs = []
    if ship.is_destroyed:
        return logs

    repairable_crits = [c for c in ship.critical_damage if c.get("repairable", False)]
    if not repairable_crits:
        return logs

    num_dice = ship.hits_remaining

    # Check if ship is touching blast markers (halves dice)
    touching_blast = _count_blast_markers_touching(ship, gs.get_blast_markers())
    if touching_blast > 0:
        num_dice = (num_dice + 1) // 2
        logs.append(f"{ship.name}: damage control with {num_dice} dice "
                    f"(halved, {touching_blast} blast markers)")
    else:
        logs.append(f"{ship.name}: damage control with {num_dice} dice")

    if num_dice <= 0:
        return logs

    rolls = dice.roll_d6(num_dice, f"{ship.name} damage control (6 to repair)")
    sixes = sum(1 for r in rolls if r == 6)

    if sixes == 0:
        logs.append(f"  No repairs (no 6s rolled)")
        gs.update_ship(ship)
        return logs

    logs.append(f"  Rolled {sixes} repair(s) available!")

    # Apply repairs
    repairs_available = min(sixes, len(repairable_crits))

    if repair_choices is not None:
        # Player specified which crits to repair
        repaired = 0
        for choice in repair_choices[:repairs_available]:
            for c in ship.critical_damage:
                if c.get("description") == choice and c.get("repairable", False):
                    ship.critical_damage.remove(c)
                    repaired += 1
                    logs.append(f"  Repaired: {c['description']}")
                    break
    else:
        # Auto mode: repair in priority order (fire first, then engine, then others)
        priority = ["fire", "engine_room", "thrusters_damaged",
                     "shields_collapse", "dorsal_armament", "port_armament",
                     "starboard_armament", "prow_armament", "bridge_smashed"]
        repaired = 0
        for _ in range(repairs_available):
            best = None
            best_priority = 999
            for c in ship.critical_damage:
                if not c.get("repairable", False):
                    continue
                ct = c.get("crit_type", "")
                try:
                    p = priority.index(ct)
                except ValueError:
                    p = 100
                if p < best_priority:
                    best_priority = p
                    best = c
            if best:
                ship.critical_damage.remove(best)
                repaired += 1
                logs.append(f"  Repaired: {best['description']}")

    gs.update_ship(ship)
    return logs


def get_repair_info(ship: Ship, dice: DiceRoller, gs: GameState) -> Dict:
    """
    Roll damage control dice and return info for player to choose repairs.
    Does NOT apply repairs yet.
    """
    if ship.is_destroyed:
        return {"sixes": 0, "repairable": [], "num_dice": 0}

    repairable_crits = [c for c in ship.critical_damage if c.get("repairable", False)]
    if not repairable_crits:
        return {"sixes": 0, "repairable": [], "num_dice": 0}

    num_dice = ship.hits_remaining
    touching_blast = _count_blast_markers_touching(ship, gs.get_blast_markers())
    if touching_blast > 0:
        num_dice = (num_dice + 1) // 2

    if num_dice <= 0:
        return {"sixes": 0, "repairable": [], "num_dice": 0}

    rolls = dice.roll_d6(num_dice, f"{ship.name} damage control (6 to repair)")
    sixes = sum(1 for r in rolls if r == 6)

    return {
        "sixes": sixes,
        "num_dice": num_dice,
        "touching_blast": touching_blast,
        "repairable": [c["description"] for c in repairable_crits],
        "rolls": rolls,
    }


def apply_repair_choices(ship: Ship, choices: List[str], gs: GameState) -> List[str]:
    """Apply the player's chosen repairs to a ship."""
    logs = []
    for choice in choices:
        for c in ship.critical_damage:
            if c.get("description") == choice and c.get("repairable", False):
                ship.critical_damage.remove(c)
                logs.append(f"  Repaired: {c['description']}")
                break
    gs.update_ship(ship)
    return logs


def remove_blast_markers(gs: GameState, dice: DiceRoller) -> List[str]:
    """
    Active player rolls D6, removes that many blast markers
    not touching any ship.
    """
    logs = []
    ships = gs.get_ships()
    blast_markers = gs.get_blast_markers()

    # Find blast markers not touching any ship
    free_markers = []
    for bm in blast_markers:
        touching = False
        for s in ships:
            if s.is_destroyed:
                continue
            dist = math.sqrt((bm.x - s.x)**2 + (bm.y - s.y)**2)
            if dist <= s.base_radius + BASE_CONTACT_THRESHOLD_CM:
                touching = True
                break
        if not touching:
            free_markers.append(bm)

    if not free_markers:
        logs.append("No free blast markers to remove")
        return logs

    roll = dice.roll_d6(1, "Blast marker removal (remove this many)")
    num_remove = min(roll[0], len(free_markers))

    # Remove first N free markers
    removed_ids = set()
    for i in range(num_remove):
        removed_ids.add(free_markers[i].id)

    gs.blast_markers = [bm for bm in gs.blast_markers
                        if bm.get("id") not in removed_ids]

    logs.append(f"Removed {num_remove} blast markers (rolled {roll[0]}, "
                f"{len(free_markers)} were free)")

    return logs


def remove_brace_orders(gs: GameState) -> List[str]:
    """
    End-of-turn brace cleanup.
    - Expire Brace For Impact if set on a previous turn, restoring previous_order.
    - Clear brace_failed_vs for ALL ships (failed attempts are per-turn, not persistent).
    """
    logs = []
    for s_dict in gs.ships:
        ship = Ship.from_dict(s_dict)
        needs_update = False

        # Clear per-turn failed brace tracking (regardless of brace status)
        if ship.brace_failed_vs:
            ship.brace_failed_vs = []
            needs_update = True

        if s_dict.get("special_order") == SpecialOrder.BRACE_FOR_IMPACT.value:
            brace_turn = s_dict.get("brace_set_on_turn", 0)
            if brace_turn < gs.turn_number:
                # Set on a previous turn, time to expire
                prev = ship.previous_order or SpecialOrder.NONE.value
                ship.special_order = prev
                ship.previous_order = SpecialOrder.NONE.value
                ship.brace_set_on_turn = 0
                needs_update = True
                if prev != SpecialOrder.NONE.value:
                    logs.append(
                        f"{ship.name}: Brace For Impact expired, "
                        f"restored to {prev}")
                else:
                    logs.append(f"{ship.name}: Brace For Impact expired")
            else:
                # Set this turn, persists through next turn
                logs.append(f"{ship.name}: Brace For Impact persists (set this turn)")

        if needs_update:
            gs.update_ship(ship)
    return logs


def resolve_end_phase(gs: GameState, dice: DiceRoller,
                      active_player: int) -> List[str]:
    """
    Run the complete end phase.
    Returns all log messages.
    """
    all_logs = []
    all_logs.append("=== END PHASE ===")

    # 1. Fire damage (both players' ships)
    for s_dict in gs.ships:
        ship = Ship.from_dict(s_dict)
        if ship.is_destroyed or ship.is_disengaged:
            continue
        fire_logs = resolve_fire_damage(ship, dice, gs)
        all_logs.extend(fire_logs)

    # 2. Damage control (both players' ships)
    for s_dict in gs.ships:
        ship = Ship.from_dict(s_dict)
        if ship.is_destroyed or ship.is_disengaged:
            continue
        if ship.status in ("drifting_hulk", "burning_hulk"):
            continue  # hulks don't repair
        dc_logs = resolve_damage_control(ship, dice, gs)
        all_logs.extend(dc_logs)

    # 3. Remove blast markers (active player rolls)
    bm_logs = remove_blast_markers(gs, dice)
    all_logs.extend(bm_logs)

    # 4. Remove Brace orders
    brace_logs = remove_brace_orders(gs)
    all_logs.extend(brace_logs)

    return all_logs


def resolve_hulk_drift(gs: GameState, dice: DiceRoller) -> List[str]:
    """
    Move all hulks (drifting and burning) at the start of movement phase.
    Hulks move 4D6cm forward. Place blast marker after each move.
    Burning hulks then re-roll on catastrophic damage table.
    Called at the START of the movement phase, before ships move.
    """
    logs = []

    for s_dict in list(gs.ships):  # copy list since we may modify
        ship = Ship.from_dict(s_dict)
        if ship.status not in ("drifting_hulk", "burning_hulk"):
            continue

        # Drift: 4D6cm forward
        drift_roll = dice.roll_d6(4, f"{ship.name} hulk drift (4D6cm)")
        drift_dist = sum(drift_roll)
        rad = math.radians(ship.heading)
        ship.x += drift_dist * math.cos(rad)
        ship.y += drift_dist * math.sin(rad)

        logs.append(f"{ship.name} ({ship.status}) drifts {drift_dist}cm")

        # Place blast marker after move
        bm = BlastMarker(
            id=f"hulk_drift_{ship.id}_{random.randint(0,9999)}",
            x=ship.x, y=ship.y,
            source="hulk_drift")
        gs.add_blast_marker(bm)

        # Check if hulk drifted off table
        if (ship.x < -5 or ship.x > gs.table_width + 5 or
                ship.y < -5 or ship.y > gs.table_height + 5):
            ship.status = "destroyed"
            gs.update_ship(ship)
            logs.append(f"  {ship.name} drifted off the table!")
            continue

        gs.update_ship(ship)

        # Burning hulk: re-roll on catastrophic damage table
        if ship.status == "burning_hulk":
            from .combat import apply_damage, resolve_catastrophic
            from .tables import lookup_catastrophic

            roll = dice.roll_2d6(f"{ship.name} burning hulk re-roll")
            cat_result = lookup_catastrophic(roll)

            if cat_result == "drifting_hulk":
                # Fire burns out
                ship.status = "drifting_hulk"
                gs.update_ship(ship)
                logs.append(f"  {ship.name}: fire burns out (rolled {roll}), "
                           f"now a drifting hulk")
            elif cat_result == "burning_hulk":
                # Still burning
                logs.append(f"  {ship.name}: still burning (rolled {roll})")
            else:
                # Plasma overload or warp implosion: explodes
                logs.append(f"  {ship.name}: EXPLODES! (rolled {roll}: {cat_result})")
                ship.status = "destroyed"
                gs.update_ship(ship)

                # Explosion effects
                num_markers = ship.hits_max // 2 if cat_result == "plasma_drive_overload" else ship.hits_max
                lance_str = num_markers

                blast_radius_roll = dice.roll_d6(3, "Explosion blast radius")
                blast_radius = sum(blast_radius_roll)
                logs.append(f"  Explosion: {blast_radius}cm radius, "
                           f"{lance_str} lance shots")

                for bi in range(num_markers):
                    angle = (360 / max(1, num_markers)) * bi
                    bx = ship.x + 1.5 * math.cos(math.radians(angle))
                    by = ship.y + 1.5 * math.sin(math.radians(angle))
                    gs.add_blast_marker(
                        BlastMarker(id=f"hulk_exp_{ship.id}_{bi}",
                                    x=bx, y=by, source="explosion"))

                for s_dict in gs.ships:
                    other = Ship.from_dict(s_dict)
                    if other.id == ship.id or other.is_destroyed:
                        continue
                    dist = math.sqrt((ship.x - other.x)**2 + (ship.y - other.y)**2)
                    if dist <= blast_radius:
                        lance_dice = dice.roll_d6(
                            lance_str,
                            f"Explosion hits on {other.name} (4+)")
                        hits = sum(1 for d in lance_dice if d >= 4)
                        if hits > 0:
                            apply_damage(other, hits, dice, gs)
                            logs.append(f"  {other.name}: {hits} explosion hits")

    return logs


