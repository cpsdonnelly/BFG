"""BFG:XR Movement UI — Drag-and-Drop path computation.

This module provides compute_drag_path, which takes a ship's current state
and a cursor position and returns the best legal movement path the ship can
take in that direction. It is used by board_view.py during drag-and-drop to
preview and commit ship movement.
"""

import math
from typing import List, Optional, Tuple
from .models import Ship, BlastMarker, SpecialOrder
from .movement import (MoveCommand, MovementResult, validate_movement,
                       get_effective_speed, MIN_TURN_DISTANCE)


def compute_drag_path(ship: Ship,
                      target_x: float,
                      target_y: float,
                      special_order: str,
                      aaf_bonus: int = 0,
                      blast_markers: List[BlastMarker] = None,
                      table_width: float = 120,
                      table_height: float = 120) -> Tuple[List[MoveCommand], Optional[MovementResult]]:
    """
    Compute the best legal movement path from the ship toward (target_x, target_y).

    Strategy:
      1. Calculate bearing from ship to target and relative angle vs current heading.
      2. If the target is roughly ahead (within turn_angle), move straight toward it.
      3. Otherwise: move the minimum pre-turn distance forward, apply the turn
         (capped at ship's max turn_angle), then move remaining distance forward.
      4. Total distance is clamped to the ship's maximum speed.
      5. The resulting command list is run through validate_movement — the caller
         receives the result so it can colour the preview green or red.

    Ships on AAF or Lock On cannot turn, so only straight movement is generated.
    Burn Retros caps at half speed.
    Escorts have no minimum pre-turn distance requirement.

    Returns (commands, MovementResult). Returns ([], None) if target is trivially
    close or the ship type cannot be determined.
    """
    blast_markers = blast_markers or []

    dx = target_x - ship.x
    dy = target_y - ship.y
    dist_to_target = math.sqrt(dx * dx + dy * dy)

    if dist_to_target < 0.5:
        return [], None

    bearing = math.degrees(math.atan2(dy, dx)) % 360
    relative = (bearing - ship.heading + 360) % 360

    # Determine turn direction and capped angle
    if relative <= 180:
        turn_dir = "turn_left"
        turn_deg = min(relative, float(ship.turn_angle))
    else:
        turn_dir = "turn_right"
        turn_deg = min(360.0 - relative, float(ship.turn_angle))

    needs_turn = turn_deg > 1.0

    # Speed limits for this order
    _, max_spd = get_effective_speed(ship, special_order, aaf_bonus)
    min_turn_dist = MIN_TURN_DISTANCE.get(ship.ship_type, 10)

    # No turns allowed on AAF or Lock On
    no_turns = special_order in (
        SpecialOrder.ALL_AHEAD_FULL.value,
        SpecialOrder.LOCK_ON.value,
    )

    # Clamp total movement to max speed
    move_dist = min(dist_to_target, float(max_spd))
    if move_dist < 0.5:
        move_dist = max(float(max_spd), 1.0)

    commands: List[MoveCommand] = []

    if not needs_turn or no_turns:
        # Straight ahead — AAF must use exact max speed
        if special_order == SpecialOrder.ALL_AHEAD_FULL.value:
            commands.append(MoveCommand("forward", float(max_spd)))
        else:
            commands.append(MoveCommand("forward", move_dist))
    else:
        # Pre-turn straight segment (escorts: 0, others: min_turn_dist)
        pre_turn = float(min_turn_dist)
        # Don't pre-turn more than ~40% of total distance so there's room to move after
        pre_turn = min(pre_turn, move_dist * 0.5)
        post_turn = max(0.0, move_dist - pre_turn)

        if pre_turn > 0.1:
            commands.append(MoveCommand("forward", pre_turn))
        commands.append(MoveCommand(turn_dir, turn_deg))
        if post_turn > 0.1:
            commands.append(MoveCommand("forward", post_turn))

    result = validate_movement(
        ship, commands, special_order, aaf_bonus,
        blast_markers, table_width, table_height)

    return commands, result
