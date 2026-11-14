"""BFG:XR Movement Phase - Validation and Execution"""
import math
from typing import List, Optional, Tuple
from .models import Ship, BlastMarker, SpecialOrder
from .game_state import GameState
from .dice import DiceRoller
from .geometry import (first_contact_along_segment, count_blast_markers_touching,
                       BLAST_MARKER_RADIUS_CM)
from .disengage import check_off_table, process_involuntary_disengage
from .terrain_effects import check_ship_terrain_contact


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
        self.max_allowed: float = 0     # phase distance limit after blast markers
        self.distance_since_last_turn: float = 0   # forward movement since the last turn
        self.counts_as_defense: bool = False  # moved <5cm

    def add_error(self, msg):
        self.valid = False
        self.errors.append(msg)

    def add_warning(self, msg):
        self.warnings.append(msg)


def get_effective_speed(ship: Ship, special_order: str, aaf_bonus: int = 0,
                        blast_slowdown: bool = False) -> Tuple[float, float]:
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

    # Blast markers: -5cm, applied after the order's own speed change (owner
    # ruling: Burn Retros halves first, then the blast marker penalty)
    penalty = 5 if blast_slowdown else 0

    if effective_order == SpecialOrder.BURN_RETROS.value:
        return (0, max(0, base / 2 - penalty))

    if effective_order == SpecialOrder.ALL_AHEAD_FULL.value:
        total = max(0, base + aaf_bonus - penalty)
        return (total, total)

    # Normal, CtNH, Lock On, Reload, Brace (without AAF)
    min_spd = base / 2      # exact half: movement is never rounded
    max_spd = base

    if blast_slowdown:
        max_spd = max(0, max_spd - 5)
        min_spd = min(min_spd, max_spd)
    if "in_low_orbit" in ship.special_rules:
        min_spd = 0          # s.39: ships in low orbit don't have to move

    return (min_spd, max_spd)


def blast_markers_to_slow(ship: Ship) -> int:
    """Blast markers a ship must touch at once to be slowed: 1, or 2 for battle
    barges with the Tactical Reserves Chapter tactic."""
    from .chapter_tactics import tactical_reserves_barge
    if "demiurg_commerce" in ship.special_rules or "necron" in ship.special_rules:
        return 10 ** 6       # Absorber fields / Necron reactive hulls: never slowed
    return 2 if tactical_reserves_barge(ship) else 1


def collect_blast_markers(ship: Ship, gs: GameState, path=None) -> int:
    """Demiurg absorber / repulsor fields: the ship collects every blast marker
    its base touches while it moves (those in contact at the start first),
    removing them from the table; they power its cutting beam this turn.
    path: [(x, y), ...] points of the move (default: where it stands)."""
    if "demiurg_commerce" not in ship.special_rules:
        return 0
    points = list(path or []) or [(ship.x, ship.y)]
    reach = BLAST_MARKER_RADIUS_CM + ship.base_radius
    dense = []
    for (x1, y1), (x2, y2) in zip(points, points[1:] or points):
        n = max(1, int(math.hypot(x2 - x1, y2 - y1) / 0.5))
        dense += [(x1 + (x2 - x1) * k / n, y1 + (y2 - y1) * k / n) for k in range(n + 1)]
    taken = [bm for bm in gs.get_blast_markers()
             if any(math.hypot(bm.x - px, bm.y - py) <= reach for px, py in dense)]
    if taken:
        ids = {bm.id for bm in taken}
        # kept so an undone move can put them back (TurnController.undo_ship_movement)
        log = gs.__dict__.setdefault("_bm_collected", {})
        log.setdefault((gs.turn_number, ship.id), []).extend(
            b for b in gs.blast_markers if b["id"] in ids)
        gs.blast_markers = [b for b in gs.blast_markers if b["id"] not in ids]
        ship.collected_blast_markers += len(taken)
        gs.add_log(f"{ship.name} collects {len(taken)} blast marker(s) "
                   f"({ship.collected_blast_markers} this turn)")
    return len(taken)


def _first_multi_contact(x1, y1, x2, y2, markers, radius, need, step=0.25):
    """Distance along the segment at which a point first lies within `radius`
    of at least `need` markers at the same time, or None."""
    length = math.hypot(x2 - x1, y2 - y1)
    n = max(1, int(length / step))
    for k in range(n + 1):
        t = k / n
        px, py = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
        if sum(1 for bm in markers if math.hypot(bm.x - px, bm.y - py) <= radius) >= need:
            return length * t
    return None


def movement_budget(ship: Ship, special_order: str, aaf_bonus: int = 0,
                    blast_markers: List[BlastMarker] = None) -> Tuple[float, float]:
    """Remaining (min, max) distance the ship may still move this phase.

    Accounts for staged movement already made, and for the -5cm blast marker
    penalty if the ship has moved through markers this phase or is touching
    one now (core rules s.11).
    """
    slowed = (ship.crossed_blast_this_turn
              or count_blast_markers_touching(ship, blast_markers or [])
              >= blast_markers_to_slow(ship))
    min_spd, max_spd = get_effective_speed(ship, special_order, aaf_bonus, slowed)
    already = ship.distance_moved_this_turn
    return max(0.0, min_spd - already), max(0.0, max_spd - already)


def get_max_turns(special_order: str, ship: Ship) -> int:
    """How many turns can this ship make?"""
    # Engine Room Damaged: no turns at all until repaired
    for crit in ship.critical_damage:
        # Engine Room Damaged; Necron Main Drive Damaged / Eldar Mast Lines Severed
        if crit.get("crit_type") in ("engine_room", "main_drive", "mast_lines"):
            return 0
    if special_order == SpecialOrder.ALL_AHEAD_FULL.value and "necron" in ship.special_rules:
        return 99      # inertialess drive: a turn for every 20cm (validate_movement)
    if special_order == SpecialOrder.ALL_AHEAD_FULL.value:
        # Lightning Thrusters: vanguard cruisers may turn up to 45 degrees on AAF
        from .chapter_tactics import lightning_vanguard
        return 1 if lightning_vanguard(ship) else 0
    if special_order == SpecialOrder.LOCK_ON.value:
        return 0
    if special_order == SpecialOrder.COME_TO_NEW_HEADING.value:
        if "ponderous" in ship.special_rules:
            return 0  # ponderous ships cannot use CtNH
        return 2
    return 1


def _validate_eldar(ship: Ship, commands, special_order: str, aaf_bonus: int,
                    result: "MovementResult", table_width: float, table_height: float,
                    blast_markers=None):
    """Eldar MMS v2.0 movement (src/eldar.py): two moves, each a turn on the
    spot then a move up to the speed for the new heading. First form: no
    staged moves. Blast markers slow it like any ship (sign-off answer 58):
    -5cm from the first touch, on that move and the later one."""
    from . import eldar
    speeds = eldar.ship_speeds(ship) or (ship.speed, ship.speed, ship.speed)
    crits = [c.get("crit_type") for c in ship.critical_damage]
    # Eldar critical hits (Appendix 3): Mainsail Scarred -5cm on each speed per hit,
    # Mast Lines Severed no turns, Mainsail Shredded one move a phase
    cut = 5 * crits.count("mainsail_scarred")
    speeds = tuple(max(0, v - cut) for v in speeds)
    turn_limit = 0 if "mast_lines" in crits else ship.turn_angle
    legs, extra = eldar.commands_to_legs(commands)
    if "mainsail_shredded" in crits and len(legs) > 1:
        result.add_error("Mainsail Shredded: one move this phase")
    slowed_at = None
    markers = blast_markers or []
    if markers:
        need = blast_markers_to_slow(ship)
        reach = BLAST_MARKER_RADIUS_CM + ship.base_radius
        if count_blast_markers_touching(ship, markers) >= need:
            slowed_at = (0, 0.0)
        else:
            import math as _mm
            x0, y0, h0 = ship.x, ship.y, ship.heading
            for i, (turn, dist) in enumerate(legs):
                h0 = (h0 + turn) % 360.0
                x1 = x0 + dist * _mm.cos(_mm.radians(h0))
                y1 = y0 + dist * _mm.sin(_mm.radians(h0))
                d = _first_multi_contact(x0, y0, x1, y1, markers, reach, need)
                if d is not None:
                    slowed_at = (i, d)
                    break
                x0, y0 = x1, y1
    if slowed_at is not None:
        result.crossed_blast_markers = True
    for e in eldar.validate_mms_move(speeds, ship.heading, turn_limit, legs,
                                     special_order or "", eldar.sunward_edge(),
                                     aaf_bonus, extra, ship.is_crippled, slowed_at):
        result.add_error(e)
    import math as _m
    x, y, h = ship.x, ship.y, ship.heading
    result.path.append((x, y))
    for turn, dist in legs:
        h = (h + turn) % 360.0
        x += dist * _m.cos(_m.radians(h))
        y += dist * _m.sin(_m.radians(h))
        result.path.append((x, y))
    h = (h + extra) % 360.0
    result.final_x, result.final_y, result.final_heading = x, y, h
    result.total_distance = sum(d for _t, d in legs)
    result.turns_used = sum(1 for t, _d in legs if t) + (1 if extra else 0)
    result.counts_as_defense = result.total_distance < 5
    if not (0 <= x <= table_width and 0 <= y <= table_height):
        result.add_warning("the move ends off the table")
    return result


def validate_movement(ship: Ship, commands: List[MoveCommand],
                      special_order: str, aaf_bonus: int = 0,
                      blast_markers: List[BlastMarker] = None,
                      table_width: float = 120, table_height: float = 120,
                      turns_already_used: int = 0,
                      distance_already_moved: float = 0.0,
                      blast_already_crossed: bool = False,
                      distance_since_last_turn: Optional[float] = None) -> MovementResult:
    """
    Validate a sequence of movement commands for a ship.
    Returns a MovementResult with path, errors, warnings.

    Staged moves: distance_already_moved, turns_already_used,
    blast_already_crossed and distance_since_last_turn (forward movement since
    the last turn made in an earlier stage; defaults to the ship's own
    distance_since_last_turn) describe earlier stages this phase, so speed and
    turning limits apply to the whole phase, not each stage alone.
    """
    result = MovementResult()
    blast_markers = blast_markers or []
    if "eldar_mms" in (ship.special_rules or []):
        return _validate_eldar(ship, commands, special_order, aaf_bonus, result,
                               table_width, table_height, blast_markers)

    # Current position tracking
    cx, cy = ship.x, ship.y
    heading = ship.heading
    result.path.append((cx, cy))

    # Moving away from blast markers the ship touches counts as moving through
    # them (core rules s.11)
    need = blast_markers_to_slow(ship)
    starts_in_blast = count_blast_markers_touching(ship, blast_markers) >= need
    blast_contact_cm = BLAST_MARKER_RADIUS_CM + ship.base_radius

    max_turns = get_max_turns(special_order, ship)
    # Lightning Thrusters vanguards turn at most 45 degrees on All Ahead Full
    turn_cap = (min(ship.turn_angle, 45)
                if special_order == SpecialOrder.ALL_AHEAD_FULL.value else ship.turn_angle)
    min_turn_dist = MIN_TURN_DISTANCE.get(ship.ship_type, 10)
    if special_order == SpecialOrder.ALL_AHEAD_FULL.value and "necron" in ship.special_rules:
        # Inertialess drive (Xenos p.39): a turn for every 20cm travelled
        # (reading: each turn after a further 20cm)
        min_turn_dist = 20

    # Burn Retros: no minimum distance before turning; in low orbit capital
    # ships need none either (s.39)
    if special_order == SpecialOrder.BURN_RETROS.value or "in_low_orbit" in ship.special_rules:
        min_turn_dist = 0
    elif "turn_distance_plus5" in ship.special_rules:
        min_turn_dist += 5          # Experimental Ship (Quest) side effect

    # Track state
    distance_moved = 0.0
    # Forward movement this phase counts toward the distance before a turn (s.10)
    if turns_already_used == 0:
        distance_since_last_turn = distance_already_moved
    elif distance_since_last_turn is None:
        distance_since_last_turn = getattr(ship, "distance_since_last_turn", 0.0)
    turns_made = 0          # turns committed in this command sequence
    # Net signed rotation for current turn action (positive = anticlockwise/left)
    net_turn_degrees = 0.0
    in_a_turn = False
    crossed_any_blast = blast_already_crossed or starts_in_blast
    # Phase distance at which the ship first touched a blast marker
    first_contact = distance_already_moved if crossed_any_blast else None

    for cmd in commands:
        if cmd.action == "forward":
            if cmd.value < 0:
                result.add_error("Cannot move backwards")
                continue

            # If we were in a turn, finalize it
            if in_a_turn:
                if abs(net_turn_degrees) > turn_cap + 0.1:
                    result.add_error(
                        f"Net turn of {abs(net_turn_degrees):.0f}° "
                        f"exceeds maximum {turn_cap}°")
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

            from .low_orbit import bounds_for as _bounds_for
            bx0, by0, bx1, by1 = _bounds_for(cy, table_width, table_height)
            if new_x < bx0 or new_x > bx1 or new_y < by0 or new_y > by1:
                result.add_warning(f"Ship would leave the table at ({new_x:.1f}, {new_y:.1f})")
                new_x = max(bx0, min(bx1, new_x))
                new_y = max(by0, min(by1, new_y))

            if first_contact is None and need > 1:
                hit = _first_multi_contact(cx, cy, new_x, new_y, blast_markers,
                                           blast_contact_cm, need)
                if hit is not None:
                    crossed_any_blast = True
                    first_contact = distance_already_moved + distance_moved + hit
            elif first_contact is None:
                hits = [first_contact_along_segment(cx, cy, new_x, new_y,
                                                    bm.x, bm.y, blast_contact_cm)
                        for bm in blast_markers]
                hits = [h for h in hits if h is not None]
                if hits:
                    crossed_any_blast = True
                    first_contact = distance_already_moved + distance_moved + min(hits)

            distance_moved += cmd.value
            distance_since_last_turn += cmd.value
            cx, cy = new_x, new_y
            result.path.append((cx, cy))

        elif cmd.action in ("turn_left", "turn_right"):
            turn_degrees = cmd.value
            # Signed: left/anticlockwise = positive, right/clockwise = negative
            signed = turn_degrees if cmd.action == "turn_left" else -turn_degrees

            if not in_a_turn:
                # Starting a new turn action (account for turns used in prior staged moves)
                if turns_made + turns_already_used >= max_turns:
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
                        total_used = turns_made + turns_already_used
                        result.add_error(
                            f"Already used {total_used}/{max_turns} turns")
                    continue

                # Minimum straight-ahead distance before every turn (s.10; Come to
                # New Heading must still move the minimum before each turn)
                if distance_since_last_turn < min_turn_dist:
                    after = " since its last turn" if (turns_made or turns_already_used) else ""
                    result.add_error(
                        f"Must move {min_turn_dist}cm before turning "
                        f"(only moved {distance_since_last_turn:.1f}cm{after}). "
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
        if abs(net_turn_degrees) > turn_cap + 0.1:
            result.add_error(
                f"Net turn of {abs(net_turn_degrees):.0f}° "
                f"exceeds maximum {turn_cap}°")
        elif abs(net_turn_degrees) > 0.1:
            turns_made += 1

    # Speed limits for the whole phase. Blast markers (owner ruling on s.11): the
    # 5cm reduction applies at the point of first contact; a ship with no
    # movement left by then stops where it touched the marker.
    min_spd, max_spd = get_effective_speed(ship, special_order, aaf_bonus,
                                           crossed_any_blast)
    stop_at_contact = False
    if first_contact is not None:
        _, unslowed_max = get_effective_speed(ship, special_order, aaf_bonus, False)
        if first_contact > max_spd:
            max_spd = min(unslowed_max, first_contact)
            stop_at_contact = True
            if special_order != SpecialOrder.ALL_AHEAD_FULL.value:
                min_spd = min(min_spd, max_spd)
    if special_order == SpecialOrder.ALL_AHEAD_FULL.value:
        min_spd = max_spd
    result.max_allowed = max_spd
    phase_distance = distance_already_moved + distance_moved

    # Final validation
    result.total_distance = distance_moved
    result.final_x = cx
    result.final_y = cy
    result.final_heading = heading
    result.turns_used = turns_made
    result.crossed_blast_markers = crossed_any_blast
    result.distance_since_last_turn = 0.0 if in_a_turn else distance_since_last_turn

    # Check distance constraints
    blast_note = (f" (stops where it touched a blast marker at {max_spd:.1f}cm)"
                  if stop_at_contact else
                  " (-5cm: moved through blast markers)" if crossed_any_blast else "")
    if special_order == SpecialOrder.BURN_RETROS.value:
        if phase_distance > max_spd + 0.05:
            result.add_error(
                f"Burn Retros: max speed is {max_spd}cm{blast_note}, moved {phase_distance:.1f}cm")
    elif special_order == SpecialOrder.ALL_AHEAD_FULL.value:
        if abs(phase_distance - max_spd) > 0.5:
            result.add_error(
                f"All Ahead Full: must move exactly {max_spd:.1f}cm{blast_note}, "
                f"moved {phase_distance:.1f}cm")
    else:
        if phase_distance < min_spd and phase_distance < ship.effective_speed:
            # Ships unable to reach half speed move max possible
            result.add_error(
                f"Must move at least {min_spd}cm (half speed), moved {phase_distance:.1f}cm")
        if phase_distance > max_spd + 0.05:
            result.add_error(
                f"Max speed is {max_spd:.1f}cm{blast_note}, moved {phase_distance:.1f}cm")

    # Check <5cm defense rule
    if phase_distance < 5:
        result.counts_as_defense = True
        if special_order != SpecialOrder.BURN_RETROS.value and phase_distance == 0:
            result.add_error("Ships must move unless on Burn Retros")
        elif phase_distance > 0:
            result.add_warning("Moved <5cm: counts as Defences on Gunnery table")

    return result


def record_staged_move(gs: GameState, ship_id: str, result: MovementResult,
                       commands: List[MoveCommand]) -> Optional[Ship]:
    """After execute_movement: add this stage to the ship's per-phase movement
    tracking (distance, turns, net rotation, distance since its last turn)."""
    ship = gs.get_ship_by_id(ship_id)
    if not ship:
        return None
    ship.distance_moved_this_turn += result.total_distance
    ship.turns_used_this_turn += result.turns_used
    left = sum(c.value for c in commands if c.action == "turn_left")
    right = sum(c.value for c in commands if c.action == "turn_right")
    ship.net_rotation_this_turn += left - right
    ship.distance_since_last_turn = result.distance_since_last_turn
    gs.update_ship(ship)
    return ship


def ordnance_touched_along_path(ship: Ship, path: List[Tuple[float, float]],
                                gs: GameState, step_cm: float = 0.5) -> List[str]:
    """Ordnance markers the ship's base touches anywhere along its move, in the
    order it reaches them (s.15: contact made by a ship moving into ordnance
    during its own move counts). Fighters on combat air patrol are skipped."""
    from .geometry import circle_touches_torpedo, circle_touches_square
    if not path:
        return []
    points = [path[0]]
    for (x1, y1), (x2, y2) in zip(path, path[1:]):
        n = max(1, int(math.hypot(x2 - x1, y2 - y1) / step_cm))
        points += [(x1 + (x2 - x1) * k / n, y1 + (y2 - y1) * k / n) for k in range(1, n + 1)]
    touched = []
    for o in gs.ordnance:
        if o.get("cap_ship_id"):
            continue
        is_torp = ("torpedo" in o["ordnance_type"]
                   and o["ordnance_type"] != "torpedo_bomber")
        for i, (px, py) in enumerate(points):
            hit = (circle_touches_torpedo(px, py, ship.base_radius, o["x"], o["y"], o["heading"])
                   if is_torp else
                   circle_touches_square(px, py, ship.base_radius, o["x"], o["y"], o["heading"]))
            if hit:
                touched.append((i, o["id"]))
                break
    return [mid for _, mid in sorted(touched)]


def execute_movement(ship: Ship, result: MovementResult, gs: GameState,
                     dice: DiceRoller = None):
    """Apply a validated movement result to the ship and game state.

    dice: needed for the blast marker test a shieldless ship makes when it
    moves through markers; without it the test is skipped.
    """
    # Ordnance the ship runs into on the way attacks it once the move is made
    touched = ordnance_touched_along_path(ship, result.path, gs)
    if touched:
        ship.pending_ordnance_contacts = list(dict.fromkeys(
            list(ship.pending_ordnance_contacts or []) + touched))

    collect_blast_markers(ship, gs, [(ship.x, ship.y)] + [tuple(p[:2]) for p in (result.path or [])]
                          + [(result.final_x, result.final_y)])
    # Convoy (narrative): the path, turns included, for contact marker activation
    from .convoy_narrative import record_path
    _pts = [(ship.x, ship.y)] + [tuple(p[:2]) for p in (result.path or [])] \
        + [(result.final_x, result.final_y)]
    record_path(gs, ship, _pts)
    from .subplots import record_survey          # Expeditionary Group
    record_survey(gs, ship, _pts)
    ship.x = result.final_x
    ship.y = result.final_y
    ship.heading = result.final_heading
    ship.moved_this_turn = True

    # Low orbit (s.39): landing, returning to high orbit, the planet edge
    from .low_orbit import handle_move_end as _lo_move_end
    if _lo_move_end(gs, ship, dice):
        return

    # Check for off-table (involuntary disengage)
    if check_off_table(ship, gs.table_width, gs.table_height):
        from .scenarios import off_table_destroyed, record_exit
        record_exit(gs, ship)
        if off_table_destroyed(gs, ship):
            ship.status = "destroyed"
            ship.hits_remaining = 0
            gs.update_ship(ship)
            gs.add_log(f"{ship.name} moved off the wrong table edge: destroyed (Rescue)")
            return
        process_involuntary_disengage(ship, gs, dice)
        return

    if result.crossed_blast_markers:
        gs.add_log(f"{ship.name} moved through blast markers (-5cm speed)")
        first_time_this_phase = not ship.crossed_blast_this_turn
        ship.crossed_blast_this_turn = True
        if first_time_this_phase and dice is not None and "materialising" not in ship.special_rules \
                and _blast_marker_damage(ship, gs, dice):
            return

    if result.counts_as_defense:
        gs.add_log(f"{ship.name} moved <5cm, counts as Defences on gunnery table")

    # Check terrain interactions at final position
    phenomena = gs.get_phenomena()
    # Navigate the Storm: a materialising ship interacts with nothing
    contacts = [] if "materialising" in ship.special_rules else \
        check_ship_terrain_contact(ship, phenomena)
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


def _blast_marker_damage(ship: Ship, gs: GameState, dice: DiceRoller) -> bool:
    """Core rules s.11: a ship with no shields, or permanently disabled ones,
    that moves through blast markers takes 1 damage on a D6 roll of 6 (once
    per move). Returns True if the ship was destroyed."""
    if ship.effective_shields > 0 or "necron" in ship.special_rules:
        return False             # Necrons: immune to blast marker damage (Xenos p.40)
    roll = dice.roll_d6(1, f"{ship.name} through blast markers, no shields (6 = 1 damage)")[0]
    if roll != 6:
        return False
    from .combat import apply_damage, resolve_catastrophic
    gs.add_log(f"{ship.name} takes 1 damage moving through blast markers (no shields)")
    apply_damage(ship, 1, dice, gs, ignores_shields=True,
                 target_braced=ship.special_order == SpecialOrder.BRACE_FOR_IMPACT.value)
    if ship.hits_remaining <= 0 and ship.status == "active":
        resolve_catastrophic(ship, dice, gs)
        return True
    return False


def slaanesh_penalty(ship: Ship, gs) -> int:
    """Mark of Slaanesh: enemy ships within 15cm of a marked ship suffer -1 Ld
    (not cumulative across marked ships)."""
    if gs is None:
        return 0
    for o in gs.get_ships():
        if (o.player != ship.player and "mark:slaanesh" in o.special_rules
                and not o.is_destroyed and not o.is_disengaged
                and math.hypot(o.x - ship.x, o.y - ship.y) - o.base_radius - ship.base_radius
                <= 15.0):
            return 1
    return 0


def _sirens_summon(ship: Ship, gs) -> bool:
    """Siren's Summon (Pleasure Fleet of Slaanesh): an enemy vessel within 15cm
    of a Siren's Summon ship can't use special orders or take any Leadership
    test (Brace included); a test it is forced to take fails."""
    if gs is None or ship is None:
        return False
    return any(s.player != ship.player and "sirens_summon" in s.special_rules
               and not s.is_destroyed and not s.is_disengaged
               and ship.distance_to(s) <= 15.0 for s in gs.get_ships())


sirens_summon = _sirens_summon


def do_command_check(ship: Ship, order: str, dice: DiceRoller,
                     enemy_on_special: bool = False,
                     in_blast: bool = False, gs=None) -> dict:
    """
    Perform a command check for special orders.
    Returns dict with 'passed', 'roll', 'needed' (effective Ld).
    """
    # Orks, 'Ere We Go!: automatically pass command checks for All Ahead Full
    if order == SpecialOrder.ALL_AHEAD_FULL.value and "ere_we_go" in ship.special_rules:
        return {"passed": True, "roll": 0, "needed": ship.leadership,
                "mods": ["'Ere We Go! (automatic pass)"]}
    if gs is not None:
        # Mark of Chaos Undivided: before a command check (07_chaos.md)
        from .chaos_undivided import offer as _undivided
        if _undivided(gs, ship, order):
            fresh = gs.get_ship_by_id(ship.id)
            if fresh is not None:
                ship.leadership = fresh.leadership
    from .subplots import leadership as _sp_ld
    ld = _sp_ld(gs, ship)            # Fleet Experience / Blood Bond
    mods = []
    if gs is not None and _sirens_summon(ship, gs):
        # Siren's Summon (Pleasure Fleet of Slaanesh): no special orders or
        # Leadership tests within 15cm of it; a forced test fails
        return {"passed": False, "roll": 0, "needed": 0,
                "mods": ["Siren's Summon: no orders or Leadership tests"]}
    if in_blast and "necron" not in ship.special_rules:   # Necrons: no blast marker Ld penalty
        ld -= 1
        mods.append("Under Fire -1")
    if slaanesh_penalty(ship, gs):
        ld -= 1
        mods.append("Mark of Slaanesh -1")
    from .subplots import command_check_modifier
    sp_mod = command_check_modifier(ship, order)
    if sp_mod:
        ld += sp_mod
        mods.append(f"sub-plot {sp_mod:+d}")
    if order == SpecialOrder.RELOAD_ORDNANCE.value and "grot_riggers" in ship.special_rules:
        ld += 1
        mods.append("Grot Riggers +1")
    if enemy_on_special:
        # Cobra improved sensor array: +2 instead of +1; a Mechanicus
        # Experimental Ship within 15cm adds +1 (Quest for Knowledge)
        bonus = 2 if "improved_sensor_array" in ship.special_rules else 1
        from .subplots import mech_ld_aura
        bonus += mech_ld_aura(gs, ship)
        ld += bonus
        mods.append(f"Enemy Contacts +{bonus}")
    # Modifiers can't take Ld above 10 or below 0 (s.6); at Ld 1 or less a
    # ship always fails (s.3), which a 2D6 roll against it does
    ld = max(0, min(10, ld))

    mod_str = f" ({', '.join(mods)})" if mods else ""
    roll = dice.roll_2d6(
        f"{ship.name} command check for {order} (need <= {ld}{mod_str})")
    passed = roll <= ld

    return {"passed": passed, "roll": roll, "needed": ld, "mods": mods}


def fleet_reroll_offered(gs: GameState, ship: Ship, label: str, roll: int, needed: int) -> bool:
    """A failed Leadership test may use one fleet commander re-roll (s.5:
    "a failed command check or leadership test for any ship or squadron";
    only one re-roll per test). GameState.ld_reroll_hook(ship, label, roll,
    needed) asks the owner (the AI decides) and spends the re-roll; without a
    hook nothing is offered. Special orders have their own re-roll prompt."""
    hook = getattr(gs, "ld_reroll_hook", None)
    return bool(hook and hook(ship, label, roll, needed))


def attempt_brace(ship: Ship, gs: GameState, dice: DiceRoller) -> dict:
    """
    Roll a Brace For Impact command check and, on success, apply the order:
    preserve the previous special order, set BFI, record the turn it was set,
    and persist the ship. Returns the command-check result dict.
    """
    from .scenarios import orders_forbidden
    why = orders_forbidden(gs, ship)
    if why:
        gs.add_log(f"{ship.name} can't Brace for Impact: {why}")
        return {"passed": False, "roll": 0, "needed": 0, "forbidden": why}
    # A command check, so Under Fire and Enemy Contacts apply (s.6)
    in_blast = count_blast_markers_touching(ship, gs.get_blast_markers()) > 0
    enemy_on_special = any(
        s.player != ship.player and not s.is_destroyed and not s.is_disengaged
        and s.special_order not in ("none", "")
        for s in gs.get_ships())
    check = do_command_check(ship, "brace_for_impact", dice,
                             enemy_on_special=enemy_on_special, in_blast=in_blast, gs=gs)
    if not check["passed"] and fleet_reroll_offered(gs, ship, "Brace for Impact",
                                                    check["roll"], check["needed"]):
        check = do_command_check(ship, "brace_for_impact", dice,
                                 enemy_on_special=enemy_on_special, in_blast=in_blast, gs=gs)
        check["rerolled"] = True
    if check["passed"]:
        if ship.special_order != SpecialOrder.BRACE_FOR_IMPACT.value:
            ship.previous_order = ship.special_order
        ship.special_order = SpecialOrder.BRACE_FOR_IMPACT.value
        ship.brace_set_on_turn = gs.turn_number
        gs.update_ship(ship)
    return check


def aaf_bonus_dice(ship: Ship) -> int:
    """D6s rolled for the All Ahead Full speed bonus: 4 normally (Appendix 6),
    3 for Orks ('Ere We Go!), +1 for each "+D6cm on All Ahead Full" source
    (Improved Thrusters, Sigils of Quickening): they stack (owner ruling)."""
    if "aaf_5d6" in ship.special_rules or "eldar_mms" in ship.special_rules:
        return 5        # Fast Clipper: +5D6cm instead of +3D6cm; Eldar +5D6cm (MMS p.3)
    n = 3 if ("ere_we_go" in ship.special_rules
              or "fleet_support" in ship.special_rules) else 4
    n += sum(1 for r in ("improved_thrusters", "sigils_of_quickening")
             if r in ship.special_rules)
    if "clan:evil_sunz" in ship.special_rules:
        n += 2                         # Evil Sunz: an extra +2D6cm on All Ahead Full
    if "secondary_reactors" in ship.special_rules:
        n += 2                         # Secondary Reactors: +2D6cm (Advanced Engines)
    return n


def squadron_aaf_bonuses(ships: List[Ship], dice: DiceRoller) -> dict:
    """A squadron on All Ahead Full rolls once and every member adds the result.
    If members roll different numbers of dice, roll the most any member is
    allowed; members allowed fewer use the highest results, up to their own
    number (s.7). Returns {ship id: bonus}."""
    if not ships:
        return {}
    if all("necron" in s.special_rules for s in ships):
        from .necrons import inertialess_extra
        b = inertialess_extra(dice.roll_d6(1, "Squadron inertialess drive (D6 x 10cm)")[0])
        return {s.id: b for s in ships}
    n = max(aaf_bonus_dice(s) for s in ships)
    rolls = sorted(dice.roll_d6(n, f"Squadron All Ahead Full speed bonus ({n}D6)"),
                   reverse=True)
    return {s.id: sum(rolls[:aaf_bonus_dice(s)]) for s in ships}


def resolve_aaf_speed(ship: Ship, dice: DiceRoller) -> int:
    """Roll the All Ahead Full bonus speed (aaf_bonus_dice D6s)."""
    if "necron" in ship.special_rules:
        # Inertialess drive (Xenos p.39): D6 x 10cm instead of the usual bonus
        from .necrons import inertialess_extra
        return inertialess_extra(dice.roll_d6(1, f"{ship.name} inertialess drive (D6 x 10cm)")[0])
    n = aaf_bonus_dice(ship)
    results = dice.roll_d6(n, f"{ship.name} All Ahead Full speed bonus ({n}D6)")
    return sum(results)


