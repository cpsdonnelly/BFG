"""BFG:XR Deployment Phase

Handles the pre-game ship placement phase that runs before Turn 1 begins.
Each player places their ships one at a time within their assigned deployment
zone.

DEPLOYMENT ZONES
----------------
Standard BFG deployment: each player deploys within 30cm of their own table
edge. Player 1 deploys along the bottom edge (y = 0 to 30cm), Player 2 along
the top edge (y = table_height-30 to table_height). These are the defaults;
scenarios may override them.

A deployment zone is defined by a rectangle: (x_min, y_min, x_max, y_max).
Ships must be placed so their base center falls within this rectangle.

DEPLOYMENT ORDER
----------------
  1. Both players secretly write down (or lock in) their fleet lists.
  2. Players alternate placing one ship at a time, starting with the player
     who lost the scenario roll-off (or Player 2 by default).
  3. A player may place a ship anywhere within their deployment zone, at any
     heading.
  4. Squadrons: all ships in a squadron must be placed within coherency range
     of each other (within 10cm) at deployment.
  5. Once all ships are placed, the game begins at Turn 1 Movement Phase.

INTEGRATION
-----------
  - Called from game_panel.py at game startup, before the first turn.
  - After deployment completes, game_panel transitions to the normal
    turn structure.
  - Ship positions set during deployment are written to game state the same
    way execute_movement writes them — just without the movement validation.

CLASSES / FUNCTIONS PLANNED
----------------------------

DeploymentZone(dataclass)
  - x_min, y_min, x_max, y_max: float
  - player: int
  - label: str  (e.g. "Player 1 Deployment Zone")

  Methods:
    contains(x, y) -> bool
      - Returns True if the point is within the zone boundaries.
    draw(canvas, board_view)
      - Draws the zone outline on the board canvas as a dashed rectangle
        with a label.

get_default_zones(table_width, table_height) -> List[DeploymentZone]
  - Returns the standard two-zone layout (30cm from each short edge).
  - Used when no scenario overrides are in effect.

DeploymentController
  - Manages the full deployment phase dialog.
  - Tracks which ships have been placed and whose turn it is to place.

  Methods:
    start(gs, board_view, on_complete_callback)
      - Begins the deployment phase.
      - Draws deployment zones on the board.
      - Prompts the first player to place their first ship.
    place_ship(ship, x, y, heading)
      - Validates the placement (within zone, no overlap with other ships).
      - Writes the position to game state.
      - Advances to the next player's placement turn.
    _validate_placement(ship, x, y) -> (valid: bool, reason: str)
      - Checks zone bounds and base overlap with already-placed ships.
    _next_placement_turn()
      - Alternates between players until all ships are placed.
      - Calls on_complete_callback when deployment is finished.
    on_board_click(x_cm, y_cm)
      - Called when the player clicks the board to place the currently
        selected ship.
"""
