"""BFG:XR Ship Catalog — Static ship class definitions for the fleet builder.

This module holds the authoritative database of all ship classes across all
factions: their base stats, weapon loadouts, available upgrades, and points
costs. It is read-only reference data — it never touches live game state.

The fleet builder (fleet_builder.py) reads from this catalog to populate
ship selection menus. When a game starts, ships chosen in the fleet builder
are instantiated as Ship objects (from models.py) using this data as the
template.

STRUCTURE
---------
Each ship class entry contains everything needed to create a Ship instance:
  - ship_class name (e.g. "Emperor Class Battleship")
  - faction
  - ship_type (battleship / cruiser / escort / defense)
  - base_size (small / large)
  - base stats: speed, turn_angle, shields_max, armor_prow, armor_side,
    turrets, hits_max, leadership
  - default weapons list (same format as Ship.weapons)
  - special_rules list
  - available upgrades and their points costs
  - base points cost (hull only, before upgrades)

FACTIONS PLANNED
----------------
  - imperial_navy
  - chaos_fleet
  - space_marines (Adeptus Astartes)
  - eldar_craftworld
  - ork_freebooterz
  - tau_kor_vattra (or kor_vesh depending on XR naming)
  - necron_fleet
  - tyranid_hive_fleet

Each faction will be a dict or list of ShipClassEntry objects.

CLASSES / STRUCTURES PLANNED
-----------------------------

ShipClassEntry(dataclass)
  - All the fields described above.
  - to_ship_dict(name, player, ship_id) -> dict
      Converts this catalog entry into a Ship-compatible dict with a given
      instance name, player assignment, and unique ID. Used by the fleet
      builder when finalising a fleet list for play.

UpgradeEntry(dataclass)
  - name: str
  - description: str
  - points_cost: int
  - effect: str or dict  (how it modifies the ship — adds special_rule,
    modifies a stat, replaces a weapon, etc.)
  - restrictions: List[str]  (e.g. "flagship_only", "cruiser_only")

CATALOG FUNCTIONS PLANNED
--------------------------

get_faction_ships(faction: str) -> List[ShipClassEntry]
  - Returns all ship classes available to the given faction.

get_ship_class(faction: str, ship_class: str) -> Optional[ShipClassEntry]
  - Looks up a specific ship class by name within a faction.

get_upgrades_for_ship(entry: ShipClassEntry) -> List[UpgradeEntry]
  - Returns the list of upgrades available to a given ship class.

list_factions() -> List[str]
  - Returns all faction identifiers present in the catalog.
"""
