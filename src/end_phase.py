"""BFG:XR End Phase - Damage control, blast removal, fire damage"""
import math
import random
from typing import List, Dict, Optional
from .models import Ship, BlastMarker, SpecialOrder
from .game_state import GameState
from .dice import DiceRoller
from .geometry import (count_blast_markers_touching, BLAST_MARKER_RADIUS_CM,
                       first_contact_along_segment)


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
    touching_blast = count_blast_markers_touching(ship, gs.get_blast_markers())
    if touching_blast > 0:
        num_dice = (num_dice + 1) // 2
        logs.append(f"{ship.name}: damage control with {num_dice} dice "
                    f"(halved, {touching_blast} blast markers)")
    else:
        logs.append(f"{ship.name}: damage control with {num_dice} dice")

    if num_dice <= 0:
        return logs

    # Ork kustom upgrades: Mad Meks repair on 4+; a Big Mek rolls an extra D6
    need = 4 if ("mad_meks" in ship.special_rules or "necron" in ship.special_rules) else 6  # Necrons: 4+
    if "big_mek" in ship.special_rules:
        num_dice += 1
    rolls = dice.roll_d6(num_dice, f"{ship.name} damage control ({need}+ to repair)")
    sixes = sum(1 for r in rolls if r >= need)

    if sixes == 0:
        logs.append("  No repairs (no 6s rolled)")
        gs.update_ship(ship)
        return logs

    logs.append(f"  Rolled {sixes} repair(s) available!")

    # Apply repairs
    repairs_available = min(sixes, len(repairable_crits))

    if repair_choices is not None:
        # Player specified which crits to repair
        for choice in repair_choices[:repairs_available]:
            for c in ship.critical_damage:
                if c.get("description") == choice and c.get("repairable", False):
                    ship.critical_damage.remove(c)
                    logs.append(f"  Repaired: {c['description']}")
                    break
    else:
        # Auto mode: the repairs worth most expected VP (To do 11 e,
        # ai_hazards.repair_value); the fixed priority (fire first, then
        # engine, then the rest) breaks ties and is the fallback
        priority = ["fire", "engine_room", "thrusters_damaged",
                     "shields_collapse", "dorsal_armament", "port_armament",
                     "starboard_armament", "prow_armament", "bridge_smashed"]
        from .ai_hazards import repair_value
        vals = {id(c): repair_value(ship, c, gs) for c in ship.critical_damage
                if c.get("repairable", False)}
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
                if vals:
                    p = -vals.get(id(c), 0.0) * 1000 + p   # value first, then priority
                if p < best_priority:
                    best_priority = p
                    best = c
            if best:
                ship.critical_damage.remove(best)
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
    touching_blast = count_blast_markers_touching(ship, gs.get_blast_markers())
    if touching_blast > 0:
        num_dice = (num_dice + 1) // 2

    if num_dice <= 0:
        return {"sixes": 0, "repairable": [], "num_dice": 0}

    # Ork kustom upgrades: Mad Meks repair on 4+; a Big Mek rolls an extra D6
    need = 4 if ("mad_meks" in ship.special_rules or "necron" in ship.special_rules) else 6  # Necrons: 4+
    if "big_mek" in ship.special_rules:
        num_dice += 1
    rolls = dice.roll_d6(num_dice, f"{ship.name} damage control ({need}+ to repair)")
    sixes = sum(1 for r in rolls if r >= need)

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
            if dist <= s.base_radius + BLAST_MARKER_RADIUS_CM:
                touching = True
                break
        if not touching:
            free_markers.append(bm)

    if not free_markers:
        logs.append("No free blast markers to remove")
        return logs

    roll = dice.roll_d6(1, "Blast marker removal (remove this many)")
    num_remove = min(roll[0], len(free_markers))

    # Which ones (To do 9): the player whose turn it is removes those that
    # hinder its own ships most and its enemies least, judged by how near
    # each marker is to the ships that may run into it next turn (within a
    # ship's speed + 10cm: speed loss, shields down, gunnery shifts, s.11)
    player = gs.active_player

    def hindrance(bm):
        score = 0.0
        for s in ships:
            if s.is_destroyed or s.is_disengaged:
                continue
            reach = (s.speed or 0) + 10.0
            d = math.hypot(bm.x - s.x, bm.y - s.y)
            if d <= reach:
                w = 1.0 - d / reach
                score += w if s.player == player else -w
        return score
    ranked = sorted(free_markers, key=hindrance, reverse=True)
    removed_ids = {bm.id for bm in ranked[:num_remove]}

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
    for ship in gs.get_ships():
        needs_update = False

        # Clear per-turn failed brace tracking (regardless of brace status)
        if ship.brace_failed_vs:
            ship.brace_failed_vs = []
            needs_update = True

        if ship.special_order == SpecialOrder.BRACE_FOR_IMPACT.value:
            brace_turn = ship.brace_set_on_turn
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

    # 1. Damage control (both players' ships)
    for ship in gs.get_ships():
        if ship.is_destroyed or ship.is_disengaged:
            continue
        if ship.status in ("drifting_hulk", "burning_hulk"):
            continue  # hulks don't repair
        dc_logs = resolve_damage_control(ship, dice, gs)
        all_logs.extend(dc_logs)

    # 2. Fires not extinguished by damage control each deal 1 damage
    for ship in gs.get_ships():
        if ship.is_destroyed or ship.is_disengaged:
            continue
        fire_logs = resolve_fire_damage(ship, dice, gs)
        all_logs.extend(fire_logs)

    # 3. Remove blast markers (active player rolls)
    bm_logs = remove_blast_markers(gs, dice)
    all_logs.extend(bm_logs)

    # 4. Remove Brace orders
    brace_logs = remove_brace_orders(gs)
    all_logs.extend(brace_logs)

    return all_logs


def _gravity_well_planet(ship, gs):
    for p in gs.get_phenomena():
        gw = getattr(p, "gravity_well_radius", 0) or 0
        if gw and math.hypot(ship.x - p.x, ship.y - p.y) <= gw:
            return p
    return None


def _gravity_turn(ship, gs, logs):
    """A hulk in a gravity well turns towards its centre, the full free turn:
    up to 45 degrees, or less if that faces the centre (s.34, s.41)."""
    p = _gravity_well_planet(ship, gs)
    if p is None:
        return
    want = math.degrees(math.atan2(p.y - ship.y, p.x - ship.x)) % 360
    diff = (want - ship.heading + 180) % 360 - 180
    turn = max(-45.0, min(45.0, diff))
    if abs(turn) > 0.01:
        ship.heading = (ship.heading + turn) % 360
        logs.append(f"  {ship.name} turns {turn:+.0f} degrees in the gravity well")


def _hulk_wrecked_by_terrain(ship, gs) -> bool:
    for p in gs.get_phenomena():
        ptype = getattr(p, "phenomenon_type", "")
        if "planet" in ptype or ptype == "moon":
            if math.hypot(ship.x - p.x, ship.y - p.y) <= p.radius + ship.base_radius:
                return True
        elif ptype == "asteroid_field":
            if (abs(ship.x - p.x) <= p.width / 2 + ship.base_radius
                    and abs(ship.y - p.y) <= p.height / 2 + ship.base_radius):
                return True
    return False


def resolve_hulk_drift(gs: GameState, dice: DiceRoller,
                       player: Optional[int] = None) -> List[str]:
    """
    Move the hulks (drifting and burning) at the start of a movement phase.
    Owner ruling: hulks move only in their owner's movement phase, so only
    `player`'s hulks drift (all hulks when player is None).
    Hulks move 4D6cm forward. Place blast marker after each move.
    Burning hulks then re-roll on catastrophic damage table.
    Called at the START of the movement phase, before ships move.
    """
    logs = []

    for ship in gs.get_ships():  # snapshot; loop may modify gs.ships
        if ship.status not in ("drifting_hulk", "burning_hulk"):
            continue
        if player is not None and ship.player != player:
            continue

        # Drift: 4D6cm forward (Appendix 5), turning towards the centre of a
        # gravity well it starts in (s.34: hulks always take the full free turn)
        drift_roll = dice.roll_d6(4, f"{ship.name} hulk drift (4D6cm)")
        drift_dist = float(sum(drift_roll))
        _gravity_turn(ship, gs, logs)

        # Blast markers (not the one it left itself) slow it by 5cm where it
        # first touches one, and a hulk has no shields: 1 damage on a 6 (s.34)
        rad = math.radians(ship.heading)
        ex = ship.x + drift_dist * math.cos(rad)
        ey = ship.y + drift_dist * math.sin(rad)
        others = [bm for bm in gs.get_blast_markers()
                  if not bm.id.startswith(f"hulk_drift_{ship.id}_")]
        reach = BLAST_MARKER_RADIUS_CM + ship.base_radius
        hits = [first_contact_along_segment(ship.x, ship.y, ex, ey, bm.x, bm.y, reach)
                for bm in others]
        hits = [h for h in hits if h is not None]
        crossed = bool(hits)
        if crossed:
            slowed = drift_dist - 5
            drift_dist = min(hits) if slowed <= min(hits) else slowed
        ship.x += drift_dist * math.cos(rad)
        ship.y += drift_dist * math.sin(rad)
        logs.append(f"{ship.name} ({ship.status}) drifts {drift_dist:g}cm"
                    + (" (slowed by blast markers)" if crossed else ""))
        _gravity_turn(ship, gs, logs)            # and again if it ends in the well

        # Place blast marker after move
        bm = BlastMarker(
            id=f"hulk_drift_{ship.id}_{random.randint(0,9999)}",
            x=ship.x, y=ship.y,
            source="hulk_drift",
            heading=random.uniform(0, 360))
        gs.add_blast_marker(bm)

        # Check if hulk drifted off table
        if (ship.x < -5 or ship.x > gs.table_width + 5 or
                ship.y < -5 or ship.y > gs.table_height + 5):
            ship.status = "destroyed"
            gs.update_ship(ship)
            logs.append(f"  {ship.name} drifted off the table!")
            continue

        # Hulks which drift into a planet or an asteroid field are destroyed (s.39)
        if _hulk_wrecked_by_terrain(ship, gs):
            ship.status = "destroyed"
            gs.update_ship(ship)
            logs.append(f"  {ship.name} drifts into a planet or asteroid field "
                        f"and is destroyed")
            continue

        gs.update_ship(ship)

        if crossed and dice.roll_d6(1, f"{ship.name} hulk through blast markers "
                                       f"(6 = 1 damage)")[0] == 6:
            from .combat import apply_damage
            logs.append(f"  {ship.name} takes 1 damage from blast markers")
            apply_damage(ship, 1, dice, gs, ignores_shields=True)   # re-rolls catastrophic
            ship = gs.get_ship_by_id(ship.id) or ship
            if ship.status not in ("drifting_hulk", "burning_hulk"):
                continue

        # Burning hulk: re-roll on catastrophic damage table
        if ship.status == "burning_hulk":
            from .combat import resolve_explosion
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
                logs.extend(resolve_explosion(ship, cat_result, dice, gs))

    return logs


