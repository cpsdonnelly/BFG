"""BFG:XR Fleet Builder — UI for constructing and saving fleet lists.

Players use this tool before a game to select a faction, add ships from the
catalog, assign upgrades, designate a flagship and admiral, and enforce the
points limit. The completed fleet is saved and can be loaded at game start.

This module handles only the UI and fleet construction logic. It reads ship
data from ship_catalog.py and produces a fleet list dict that game_panel.py
can load to set up a game.

FLEET RULES SUMMARY (for validation purposes)
----------------------------------------------
  - Each fleet has a points limit agreed before the game.
  - All ships must be from the same faction (mixed fleets are a scenario rule,
    not the default).
  - At most one flagship per fleet.
  - Admiral type depends on fleet points total:
      0–499 pts:   no admiral
      500–999 pts: Rear Admiral or equivalent
      1000+ pts:   Vice Admiral or equivalent
      1500+ pts:   Full Admiral or equivalent
  - Squadrons: 2–6 escort-class ships of the same class per squadron.
    Squadrons act as a unit for orders and morale.
  - Defense platforms and system ships may have their own restrictions
    depending on scenario type.

FLEET LIST FORMAT
-----------------
A saved fleet list is a JSON file containing:
  {
    "faction": str,
    "player_name": str,
    "points_limit": int,
    "total_points": int,
    "admiral": { type, leadership_bonus, rerolls },
    "ships": [
      {
        "ship_class": str,
        "custom_name": str,
        "upgrades": [str, ...],
        "is_flagship": bool,
        "squadron_id": str or ""
      },
      ...
    ]
  }

When loaded for a game, each entry is expanded using ship_catalog to produce
a full Ship dict and assigned a unique ID.

CLASSES / FUNCTIONS PLANNED
----------------------------

FleetBuilderWindow
  - The top-level Tkinter window for fleet construction.
  - Opened from the main menu or pre-game setup.

  Methods:
    open(root, on_save_callback)
      - Creates the window and populates the faction selector.
    _on_faction_selected(faction)
      - Loads the ship list for the selected faction into the ship browser.
    _add_ship(ship_class_entry)
      - Adds a ship to the current fleet list.
      - Updates the points total and validates the limit.
    _remove_ship(index)
      - Removes a ship from the fleet list.
    _edit_ship_upgrades(index)
      - Opens a sub-dialog to assign upgrades and a custom name to a ship.
    _assign_flagship(index)
      - Marks a ship as the flagship and prompts for admiral type.
    _assign_squadron(indices)
      - Groups selected escort ships into a squadron.
    _validate_fleet() -> (valid: bool, errors: List[str])
      - Checks points total, admiral eligibility, squadron rules, etc.
    _save_fleet()
      - Writes the fleet list to a JSON file.
      - Calls on_save_callback with the fleet data.
    _load_fleet()
      - Opens a file dialog to load a previously saved fleet list.

ShipEditDialog
  - Sub-dialog opened by _edit_ship_upgrades.
  - Shows available upgrades with checkboxes, points cost per upgrade,
    a text field for custom ship name.

fleet_list_to_ships(fleet_list: dict, player: int) -> List[dict]
  - Converts a saved fleet list into a list of Ship dicts ready for
    use in game state.
  - Assigns unique IDs, sets player number, expands upgrades into
    special_rules / weapon modifications using ship_catalog data.
  - Called by game_panel.py at game start.
"""
