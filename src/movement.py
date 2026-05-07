"""BFG:XR Movement Phase - Validation and Execution"""
import math
from typing import List, Tuple, Optional, Dict
from .models import Ship, BlastMarker, SpecialOrder
from .game_state import GameState
from .dice import DiceRoller


# Minimum distance before turning by ship type
MIN_TURN_DISTANCE = {
    "battleship": 15,
    "cruiser": 10,
    "escort": 0,
    "defense": 0,
}


class MoveCommand:
    """A single step in a movement sequence."""
    def __init__(self, action: str, value: float = 0):
        """
        action: "forward", "turn_left", "turn_right"
        value: cm for forward, degrees for turn
        """
        self.action = action
        self.value = value

    def __repr__(self):
        if self.action == "forward":
            return f"FORWARD {self.value:.1f}cm"
        elif self.action == "turn_left":
            return f"TURN ANTICLOCKWISE {self.value:.0f}°"
        else:
            return f"TURN CLOCKWISE {self.value:.0f}°"


class MovementResult:
    """Result of validating/executing a movement sequence."""
    def __init__(self):
        self.valid = True
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.path: List[Tuple[float, float]] = []  # waypoints (x, y)
        self.final_x: float = 0
        self.final_y: float = 0
        self.final_heading: float = 0
        self.total_distance: float = 0
        self.turns_used: int = 0
        self.crossed_blast_markers: bool = False
        self.counts_as_defense: bool = False  # moved <5cm

    def add_error(self, msg):
        self.valid = False
        self.errors.append(msg)

    def add_warning(self, msg):
        self.warnings.append(msg)


def get_effective_speed(ship: Ship, special_order: str, aaf_bonus: int = 0,
                        blast_slowdown: bool = False) -> Tuple[int, int]:
    """
    Returns (min_speed, max_speed) for this ship given its order.
    aaf_bonus: the 4D6 roll result for All Ahead Full.
    If braced with previous_order = AAF, AAF speed persists.
    """
    base = ship.effective_speed

    # Check if AAF persists through brace
    effective_order = special_order
    if (special_order == SpecialOrder.BRACE_FOR_IMPACT.value
            and ship.previous_order == SpecialOrder.ALL_AHEAD_FULL.value):
        effective_order = SpecialOrder.ALL_AHEAD_FULL.value

    if effective_order == SpecialOrder.BURN_RETROS.value:
        return (0, base // 2)

    if effective_order == SpecialOrder.ALL_AHEAD_FULL.value:
        total = base + aaf_bonus
        return (total, total)

    # Normal, CtNH, Lock On, Reload, Brace (without AAF)
    min_spd = max(1, base // 2)
    max_spd = base

    if blast_slowdown:
        max_spd = max(0, max_spd - 5)
        min_spd = min(min_spd, max_spd)

    return (min_spd, max_spd)


def get_max_turns(special_order: str, ship: Ship) -> int:
    """How many turns can this ship make?"""
    # Engine Room Damaged: no turns at all until repaired
    for crit in ship.critical_damage:
        if crit.get("crit_type") == "engine_room":
            return 0
    if special_order in (SpecialOrder.ALL_AHEAD_FULL.value, SpecialOrder.LOCK_ON.value):
        return 0
    if special_order == SpecialOrder.COME_TO_NEW_HEADING.value:
        if "ponderous" in ship.special_rules:
            return 0  # ponderous ships cannot use CtNH
        return 2
    return 1


def validate_movement(ship: Ship, commands: List[MoveCommand],
                      special_order: str, aaf_bonus: int = 0,
                      blast_markers: List[BlastMarker] = None,
                      table_width: float = 120, table_height: float = 120) -> MovementResult:
    """
    Validate a sequence of movement commands for a ship.
    Returns a MovementResult with path, errors, warnings.
    """
    result = MovementResult()
    blast_markers = blast_markers or []

    # Current position tracking
    cx, cy = ship.x, ship.y
    heading = ship.heading
    result.path.append((cx, cy))

    # Check if ship starts in contact with blast markers
    starts_in_blast = any(
        math.sqrt((cx - bm.x)**2 + (cy - bm.y)**2) < 2.0
        for bm in blast_markers
    )

    # Speed limits
    blast_slow = starts_in_blast  # moving away from blast markers counts
    min_spd, max_spd = get_effective_speed(ship, special_order, aaf_bonus, blast_slow)
    max_turns = get_max_turns(special_order, ship)
    min_turn_dist = MIN_TURN_DISTANCE.get(ship.ship_type, 10)

    # Burn Retros: no minimum distance before turning
    if special_order == SpecialOrder.BURN_RETROS.value:
        min_turn_dist = 0

    # Track state
    distance_moved = 0.0
    distance_since_last_turn = 0.0
    turns_made = 0
    # Net signed rotation for current turn action (positive = anticlockwise/left)
    net_turn_degrees = 0.0
    in_a_turn = False
    crossed_any_blast = starts_in_blast

    for cmd in commands:
        if cmd.action == "forward":
            if cmd.value < 0:
                result.add_error("Cannot move backwards")
                continue

            # If we were in a turn, finalize it
            if in_a_turn:
                if abs(net_turn_degrees) > ship.turn_angle + 0.1:
                    result.add_error(
                        f"Net turn of {abs(net_turn_degrees):.0f}° "
                        f"exceeds maximum {ship.turn_angle}°")
                elif abs(net_turn_degrees) > 0.1:  # non-zero net turn
                    turns_made += 1
                # else: turns cancelled out, no turn consumed
                in_a_turn = False
                net_turn_degrees = 0.0
                distance_since_last_turn = 0.0

            # Move forward
            rad = math.radians(heading)
            new_x = cx + cmd.value * math.cos(rad)
            new_y = cy + cmd.value * math.sin(rad)

            if new_x < 0 or new_x > table_width or new_y < 0 or new_y > table_height:
                result.add_warning(f"Ship would leave the table at ({new_x:.1f}, {new_y:.1f})")
                new_x = max(0, min(table_width, new_x))
                new_y = max(0, min(table_height, new_y))

            for bm in blast_markers:
                if _line_passes_near_point(cx, cy, new_x, new_y, bm.x, bm.y, 1.5):
                    crossed_any_blast = True

            distance_moved += cmd.value
            distance_since_last_turn += cmd.value
            cx, cy = new_x, new_y
            result.path.append((cx, cy))

        elif cmd.action in ("turn_left", "turn_right"):
            turn_degrees = cmd.value
            # Signed: left/anticlockwise = positive, right/clockwise = negative
            signed = turn_degrees if cmd.action == "turn_left" else -turn_degrees

            if not in_a_turn:
                # Starting a new turn action
                if turns_made >= max_turns:
                    if max_turns == 0:
                        # Determine why turns are blocked
                        has_engine_crit = any(
                            c.get("crit_type") == "engine_room"
                            for c in ship.critical_damage)
                        if has_engine_crit:
                            reason = "Engine Room Damaged (no turns until repaired)"
                        elif "ponderous" in ship.special_rules and special_order == SpecialOrder.COME_TO_NEW_HEADING.value:
                            reason = "Ponderous (cannot use Come to New Heading)"
                        elif special_order in (SpecialOrder.ALL_AHEAD_FULL.value, SpecialOrder.LOCK_ON.value):
                            reason = f"on {special_order} (no turns allowed)"
                        else:
                            reason = special_order
                        result.add_error(f"No turns allowed: {reason}")
                    else:
                        result.add_error(f"Already used {turns_made}/{max_turns} turns")
                    continue

                # Check minimum distance before first turn
                if turns_made == 0 and distance_since_last_turn < min_turn_dist:
                    result.add_error(
                        f"Must move {min_turn_dist}cm before turning "
                        f"(only moved {distance_since_last_turn:.1f}cm). "
                        f"{ship.ship_type}s need {min_turn_dist}cm minimum.")
                    continue

                in_a_turn = True
                net_turn_degrees = 0.0

            # Accumulate: no max check here, validated on finalization
            net_turn_degrees += signed

            # Apply to heading
            if cmd.action == "turn_left":
                heading = (heading + turn_degrees) % 360
            else:
                heading = (heading - turn_degrees) % 360

    # Finalize any pending turn
    if in_a_turn:
        if abs(net_turn_degrees) > ship.turn_angle + 0.1:
            result.add_error(
                f"Net turn of {abs(net_turn_degrees):.0f}° "
                f"exceeds maximum {ship.turn_angle}°")
        elif abs(net_turn_degrees) > 0.1:
            turns_made += 1

    # Final validation
    result.total_distance = distance_moved
    result.final_x = cx
    result.final_y = cy
    result.final_heading = heading
    result.turns_used = turns_made
    result.crossed_blast_markers = crossed_any_blast

    # Check distance constraints
    if special_order == SpecialOrder.BURN_RETROS.value:
        if distance_moved > max_spd:
            result.add_error(
                f"Burn Retros: max speed is {max_spd}cm, moved {distance_moved:.1f}cm")
    elif special_order == SpecialOrder.ALL_AHEAD_FULL.value:
        if abs(distance_moved - max_spd) > 0.5:
            result.add_error(
                f"All Ahead Full: must move exactly {max_spd}cm, moved {distance_moved:.1f}cm")
    else:
        if distance_moved < min_spd and distance_moved < ship.effective_speed:
            # Ships unable to reach half speed move max possible
            result.add_error(
                f"Must move at least {min_spd}cm (half speed), moved {distance_moved:.1f}cm")
        if distance_moved > max_spd:
            result.add_error(
                f"Max speed is {max_spd}cm, moved {distance_moved:.1f}cm")

    # Check <5cm defense rule
    if distance_moved < 5:
        result.counts_as_defense = True
        if special_order != SpecialOrder.BURN_RETROS.value and distance_moved == 0:
            result.add_error("Ships must move unless on Burn Retros")
        elif distance_moved > 0:
            result.add_warning("Moved <5cm: counts as Defenses on Gunnery table")

    return result


def execute_movement(ship: Ship, result: MovementResult, gs: GameState):
    """Apply a validated movement result to the ship and game state."""
    ship.x = result.final_x
    ship.y = result.final_y
    ship.heading = result.final_heading
    ship.moved_this_turn = True

    # Check for off-table (involuntary disengage)
    from .disengage import check_off_table, process_involuntary_disengage
    if check_off_table(ship, gs.table_width, gs.table_height):
        process_involuntary_disengage(ship, gs)
        return

    if result.crossed_blast_markers:
        gs.add_log(f"{ship.name} moved through blast markers (-5cm speed)")

    if result.counts_as_defense:
        gs.add_log(f"{ship.name} moved <5cm, counts as Defenses on gunnery table")

    # Check terrain interactions at final position
    from .terrain_effects import check_ship_terrain_contact
    phenomena = gs.get_phenomena()
    contacts = check_ship_terrain_contact(ship, phenomena)
    for contact in contacts:
        ptype = contact["type"]
        effects = contact["effects"]
        if ptype == "asteroid_field" and effects.get("navigation_test"):
            # Hulks are automatically destroyed when entering asteroid fields
            if ship.status in ("drifting_hulk", "burning_hulk"):
                ship.status = "destroyed"
                gs.update_ship(ship)
                gs.add_log(f"{ship.name} HULK DESTROYED by asteroid field!")
                return
            gs.add_log(f"{ship.name} enters asteroid field - navigation test required")
            # Navigation test will be resolved by the game panel
            ship.special_rules = list(set(ship.special_rules + ["in_asteroid_field"]))
        elif ptype == "gas_dust_cloud":
            gs.add_log(f"{ship.name} in gas/dust cloud (acts as blast marker)")
            ship.special_rules = list(set(ship.special_rules + ["in_dust_cloud"]))
        elif ptype == "warp_rift":
            gs.add_log(f"{ship.name} enters WARP RIFT - navigation test required!")
            ship.special_rules = list(set(ship.special_rules + ["in_warp_rift"]))

    gs.update_ship(ship)
    gs.add_log(f"{ship.name} moved to ({ship.x:.1f}, {ship.y:.1f}) "
               f"heading {ship.heading:.0f}° ({result.total_distance:.1f}cm)")


def do_command_check(ship: Ship, order: str, dice: DiceRoller,
                     enemy_on_special: bool = False,
                     in_blast: bool = False) -> dict:
    """
    Perform a command check for special orders.
    Returns dict with 'passed', 'roll', 'needed' (effective Ld).
    """
    ld = ship.leadership
    mods = []
    if in_blast:
        ld -= 1
        mods.append("Under Fire -1")
    if enemy_on_special:
        ld += 1
        mods.append("Enemy Contacts +1")
    ld = max(2, min(10, ld))

    mod_str = f" ({', '.join(mods)})" if mods else ""
    roll = dice.roll_2d6(
        f"{ship.name} command check for {order} (need <= {ld}{mod_str})")
    passed = roll <= ld

    return {"passed": passed, "roll": roll, "needed": ld, "mods": mods}


def resolve_aaf_speed(ship: Ship, dice: DiceRoller) -> int:
    """Roll 4D6 for All Ahead Full bonus speed."""
    results = dice.roll_d6(4, f"{ship.name} All Ahead Full speed bonus")
    return sum(results)


def _line_passes_near_point(x1, y1, x2, y2, px, py, threshold):
    """Check if a line segment from (x1,y1) to (x2,y2) passes within threshold of point (px,py)."""
    dx, dy = x2 - x1, y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.sqrt((px - x1)**2 + (py - y1)**2) <= threshold

    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / length_sq))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    dist = math.sqrt((px - proj_x)**2 + (py - proj_y)**2)
    return dist <= threshold
