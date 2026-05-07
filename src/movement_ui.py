"""BFG:XR Movement UI — Drag-and-Drop and Scroll Wheel Movement Dialog

This module will replace the movement dialog currently embedded in game_panel.py.
Extracting it here keeps game_panel.py manageable as the movement UI grows
in complexity with drag-and-drop support.

CURRENT STATE
-------------
The existing movement dialog in game_panel.py works via typed numeric inputs:
the player enters a distance and clicks Forward, or clicks Turn Left/Right
by a set number of degrees. The path is previewed on the canvas as a line.

PLANNED IMPROVEMENTS
--------------------

SCROLL WHEEL TURNING
  - While a ship is selected in the movement dialog, scrolling the mouse wheel
    over the board canvas applies a turn in the scroll direction.
  - Each scroll tick = one turn increment (likely 5° or the ship's full
    turn_angle, TBD with user).
  - The heading preview arrow on the board updates live.
  - This is a binding added to the board canvas, not a separate widget.

DRAG-AND-DROP MOVEMENT
  - Click and hold on a ship token to start a drag.
  - As the mouse moves, the path is computed in real time from the ship's
    current position to the cursor, respecting:
      - Minimum move-before-turn distance (10cm for cruisers, 15cm for battleships)
      - Maximum turn angle per turn action
      - Maximum turn count for the current special order
      - Speed limits (min and max) for the current order
  - The path is drawn on the canvas as it is dragged: straight segments in
    green, turn arcs shown distinctly, violations highlighted in red.
  - On mouse release, if the path is valid it is committed. If invalid,
    the user is shown the errors and the drag is cancelled.
  - The drag-computed path is converted into a List[MoveCommand] (the same
    format validate_movement and execute_movement already use) so no changes
    are needed to the movement validation logic itself.

PATH COMPUTATION
  - Computing a legal BFG movement path from a start point and end point is
    non-trivial: the ship must move forward, can only turn at specific points,
    and turn angle is capped. The drag system will likely use a simplified
    heuristic:
      1. Move forward the minimum required distance before the first turn.
      2. Turn toward the target heading (capped at max turn angle).
      3. Move forward to the destination.
    More complex paths (double turns via Come to New Heading) may need a
    secondary UI mode or a point-and-click waypoint system rather than
    pure drag.

CLASSES / FUNCTIONS PLANNED
----------------------------

MovementUIController
  - Owns the movement dialog window and all its widgets.
  - Replaces the anonymous _move_dialog closure in game_panel.py.
  - Holds references to: the ship being moved, current command list,
    the board canvas, the game state, and the dice roller.

  Methods:
    open(ship, special_order, aaf_bonus)
      - Creates the dialog and wires up all bindings.
    on_canvas_scroll(event)
      - Handles mouse wheel events: applies turn increment to current heading.
    on_drag_start(event)
      - Records the click position and which ship was clicked.
    on_drag_motion(event)
      - Recomputes the candidate path from start to cursor.
      - Redraws the path preview.
    on_drag_release(event)
      - Validates the final path.
      - Commits or cancels.
    _draw_path_preview(commands, valid)
      - Draws the movement path on the board canvas.
      - Green = valid segment, red = violation.
    _confirm()
      - Final commit: calls execute_movement and closes the dialog.
      - Same logic as the current _confirm() closure in game_panel.py.
"""
