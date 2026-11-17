"""BFG:XR Table Lookups - Gunnery, Critical Hits, Catastrophic Damage"""

# Gunnery table structure (6 columns, 0-5):
#   Col 0: Initial Firepower (= the FP value itself, leftmost)
#   Col 1: Defenses (ships that moved <5cm)
#   Col 2: Closing Capital Ships
#   Col 3: Closing Escorts / Moving Away Capital Ships
#   Col 4: Moving Away Escorts / Abeam Capital Ships
#   Col 5: Abeam Escorts / Ordnance Waves (rightmost)
#
# Left shift past col 0 = return FP value (can't get better)
# Right shift past col 5 = return 0 (can't hit)
#
# Array stores columns 1-5 (indices 0-4).
# Column 0 is simply the FP key.

GUNNERY_TABLE = {
    1:  [1, 1, 1, 0, 0],
    2:  [2, 1, 1, 1, 0],
    3:  [3, 2, 2, 1, 1],
    4:  [4, 3, 2, 1, 1],
    5:  [5, 4, 3, 2, 1],
    6:  [5, 4, 3, 2, 1],
    7:  [6, 5, 4, 2, 1],
    8:  [7, 6, 4, 3, 2],
    9:  [8, 6, 5, 3, 2],
    10: [9, 7, 5, 4, 2],
    11: [10, 8, 6, 4, 2],
    12: [11, 8, 6, 4, 2],
    13: [12, 9, 7, 5, 3],
    14: [13, 10, 7, 5, 3],
    15: [14, 11, 8, 5, 3],
    16: [14, 11, 8, 6, 3],
    17: [15, 12, 9, 6, 3],
    18: [16, 13, 9, 6, 4],
    19: [17, 13, 10, 7, 4],
    20: [18, 14, 10, 7, 4],
}

# Column indices (0-5)
COL_INITIAL_FP = 0          # FP value itself (leftmost, shift cap)
COL_DEFENSES = 1            # array[0]
COL_CLOSING_CAPITAL = 2     # array[1]
COL_CLOSING_ESCORT = 3      # array[2] (also Moving Away Capital)
COL_MOVING_AWAY_ESCORT = 4  # array[3] (also Abeam Capital)
COL_ABEAM_ESCORT = 5        # array[4] (also Ordnance)


def get_gunnery_column(target_type: str, target_aspect: str,
                       is_ordnance: bool = False) -> int:
    """
    Returns the column index (0-5) for the gunnery table.
    target_type: "capital", "escort", "defense", "ordnance"
    target_aspect: "closing", "moving_away", "abeam"
    """
    if is_ordnance or target_type == "ordnance":
        return COL_ABEAM_ESCORT  # col 5

    if target_type == "defense":
        return COL_DEFENSES  # col 1

    if target_type == "capital":
        if target_aspect == "closing":
            return COL_CLOSING_CAPITAL      # col 2
        elif target_aspect == "moving_away":
            return COL_CLOSING_ESCORT       # col 3 (shared with closing escort)
        elif target_aspect == "abeam":
            return COL_MOVING_AWAY_ESCORT   # col 4 (shared with moving away escort)
        return COL_CLOSING_CAPITAL

    if target_type == "escort":
        if target_aspect == "closing":
            return COL_CLOSING_ESCORT       # col 3 (shared with moving away capital)
        elif target_aspect == "moving_away":
            return COL_MOVING_AWAY_ESCORT   # col 4 (shared with abeam capital)
        elif target_aspect == "abeam":
            return COL_ABEAM_ESCORT         # col 5 (shared with ordnance)
        return COL_CLOSING_ESCORT

    return COL_CLOSING_CAPITAL  # fallback



def lookup_gunnery_dice(firepower: int, column: int, shifts: int = 0) -> int:
    """
    Look up how many dice to roll on the gunnery table.
    firepower: effective FP (after halving, cripple, etc.)
    column: base column index (0-5) from get_gunnery_column
    shifts: net column shifts (negative = left/better, positive = right/worse)
    Returns number of dice to roll (minimum 0).
    """
    if firepower <= 0:
        return 0

    # Handle FP > 20: split into 20 + remainder
    if firepower > 20:
        dice_20 = lookup_gunnery_dice(20, column, shifts)
        dice_rem = lookup_gunnery_dice(firepower - 20, column, shifts)
        return dice_20 + dice_rem

    fp = min(20, max(1, firepower))

    # Apply shifts to column
    final_col = column + shifts

    # Left shift past col 0 (Initial FP) = return the FP value itself
    if final_col <= COL_INITIAL_FP:
        return fp

    # Right shift past col 5 (Abeam Escort / Ordnance) = 0 dice
    if final_col > COL_ABEAM_ESCORT:
        return 0

    # Convert column index (1-5) to array index (0-4)
    array_idx = final_col - 1
    return GUNNERY_TABLE[fp][array_idx]


# Critical Hits Table (2D6)
CRITICAL_HITS = {
    2:  {"name": "Dorsal Armament Damaged", "extra_damage": 0, "crit_type": "dorsal_armament", "repairable": True},
    3:  {"name": "Starboard Armament Damaged", "extra_damage": 0, "crit_type": "starboard_armament", "repairable": True},
    4:  {"name": "Port Armament Damaged", "extra_damage": 0, "crit_type": "port_armament", "repairable": True},
    5:  {"name": "Prow Armament Damaged", "extra_damage": 0, "crit_type": "prow_armament", "repairable": True},
    6:  {"name": "Engine Room Damaged", "extra_damage": 1, "crit_type": "engine_room", "repairable": True},
    7:  {"name": "Fire!", "extra_damage": 0, "crit_type": "fire", "repairable": True},
    8:  {"name": "Thrusters Damaged", "extra_damage": 1, "crit_type": "thrusters_damaged", "repairable": True},
    9:  {"name": "Bridge Smashed", "extra_damage": 0, "crit_type": "bridge_smashed", "repairable": False},
    10: {"name": "Shields Collapse", "extra_damage": 0, "crit_type": "shields_collapse", "repairable": False},
    11: {"name": "Hull Breach", "extra_damage": "D3", "crit_type": "hull_breach", "repairable": False},
    12: {"name": "Bulkhead Collapse", "extra_damage": "D6", "crit_type": "bulkhead_collapse", "repairable": False},
}

# Eldar Critical Hits Table (Appendix 3, MMS p.5): all Corsair and Craftworld
# Eldar vessels
ELDAR_CRITICAL_HITS = {
    2:  {"name": "Infinity Circuit Damaged", "extra_damage": 0, "crit_type": "infinity_circuit", "repairable": True},
    3:  {"name": "Keel Armament Damaged", "extra_damage": 0, "crit_type": "keel_armament", "repairable": True},
    4:  {"name": "Prow Armament Damaged", "extra_damage": 0, "crit_type": "prow_armament", "repairable": True},
    5:  {"name": "Mast Lines Severed", "extra_damage": 0, "crit_type": "mast_lines", "repairable": True},
    6:  {"name": "Mainsail Scarred", "extra_damage": 0, "crit_type": "mainsail_scarred", "repairable": True},
    7:  {"name": "Superstructure Damaged", "extra_damage": 1, "crit_type": "superstructure", "repairable": True},
    8:  {"name": "Mainsail Shredded", "extra_damage": 0, "crit_type": "mainsail_shredded", "repairable": True},
    9:  {"name": "Holofield Generators Destroyed", "extra_damage": 1, "crit_type": "holofield_destroyed", "repairable": False},
    10: {"name": "Shields Collapse", "extra_damage": 1, "crit_type": "shields_collapse", "repairable": False},
    11: {"name": "Hull Breach", "extra_damage": "D3", "crit_type": "hull_breach", "repairable": False},
    12: {"name": "Bulkhead Collapse", "extra_damage": "D6", "crit_type": "bulkhead_collapse", "repairable": False},
}


# Necron Critical Hits Table (Appendix 3, Xenos p.41); "ld_loss" is a Leadership
# penalty applied each time, never removed during the game (even when repaired)
NECRON_CRITICAL_HITS = {
    2:  {"name": "Port Power Relays Damaged", "extra_damage": 0, "crit_type": "port_relays", "repairable": True},
    3:  {"name": "Starboard Power Relays Damaged", "extra_damage": 0, "crit_type": "starboard_relays", "repairable": True},
    4:  {"name": "Main Capacitors Damaged", "extra_damage": 0, "crit_type": "main_capacitors", "repairable": True},
    5:  {"name": "Power Flow Disrupted", "extra_damage": 0, "crit_type": "power_flow", "repairable": True},
    6:  {"name": "Main Drive Damaged", "extra_damage": 0, "crit_type": "main_drive", "repairable": True, "ld_loss": 1},
    7:  {"name": "Impulse Power Disrupted", "extra_damage": 0, "crit_type": "impulse_power", "repairable": True, "ld_loss": 1},
    8:  {"name": "Inertialess Drive Damaged", "extra_damage": 0, "crit_type": "inertialess_drive", "repairable": True, "ld_loss": 1},
    9:  {"name": "Monument Damaged", "extra_damage": 0, "crit_type": "monument", "repairable": True, "ld_loss": 2},
    10: {"name": "Command Core Damaged", "extra_damage": 0, "crit_type": "command_core", "repairable": True, "ld_loss": 3},
    11: {"name": "Power Surge", "extra_damage": "D3", "crit_type": "power_surge", "repairable": False, "ld_loss": 2},
    12: {"name": "Power Core Ruptured", "extra_damage": "D6", "crit_type": "power_core", "repairable": False, "ld_loss": 2},
}


# Space Station Critical Hits (Appendix 3, Rulebook p.62): high orbit
# defences with 3 or more starting hits
SPACE_STATION_CRITICAL_HITS = {
    2:  {"name": "Lances Damaged", "extra_damage": 0, "crit_type": "station_lances", "repairable": True},
    3:  {"name": "Lances Damaged", "extra_damage": 0, "crit_type": "station_lances", "repairable": True},
    4:  {"name": "Main Armament Damaged", "extra_damage": 0, "crit_type": "station_batteries", "repairable": True},
    5:  {"name": "Ordnance Bays Hit", "extra_damage": 0, "crit_type": "station_bays", "repairable": True},
    6:  {"name": "Reactors Damaged", "extra_damage": 1, "crit_type": "station_reactors", "repairable": True},
    7:  {"name": "Fire!", "extra_damage": 0, "crit_type": "fire", "repairable": True},
    8:  {"name": "Orbit Lost", "extra_damage": 1, "crit_type": "orbit_lost", "repairable": True},
    9:  {"name": "Orbit Lost", "extra_damage": 1, "crit_type": "orbit_lost", "repairable": True},
    10: {"name": "Shields Collapse", "extra_damage": 0, "crit_type": "shields_collapse", "repairable": False},
    11: {"name": "Hull Breach", "extra_damage": "D3", "crit_type": "hull_breach", "repairable": False},
    12: {"name": "Bulkhead Collapse", "extra_damage": "D6", "crit_type": "bulkhead_collapse", "repairable": False},
}


def crit_table_for(ship) -> dict:
    """The critical hits table a ship rolls on (Appendix 3 / 5)."""
    if "space_station_crits" in (getattr(ship, "special_rules", None) or []):
        return SPACE_STATION_CRITICAL_HITS
    if "eldar_mms" in (getattr(ship, "special_rules", None) or []):
        return ELDAR_CRITICAL_HITS
    if "necron" in (getattr(ship, "special_rules", None) or []):
        return NECRON_CRITICAL_HITS
    return CRITICAL_HITS


# Boarding Action Results Table
# diff: score difference between winner and loser
# winner_crit: minimum 1D6 roll for winner to suffer a crit (None = no crit check)
# loser_crit: minimum 1D6 roll for loser to suffer a crit (0 = auto-crit)
BOARDING_RESULTS = {
    1: {"winner_crit": 5, "loser_crit": 5},
    2: {"winner_crit": 5, "loser_crit": 4},
    3: {"winner_crit": 6, "loser_crit": 3},
    4: {"winner_crit": 6, "loser_crit": 2},
    5: {"winner_crit": None, "loser_crit": 0},  # None=no check, 0=auto
}


# Catastrophic Damage Table (2D6)
CATASTROPHIC_DAMAGE = {
    (2, 6):  "drifting_hulk",
    (7, 8):  "burning_hulk",
    (9, 11): "plasma_drive_overload",
    (12, 12): "warp_drive_implosion",
}


def lookup_catastrophic(roll_2d6):
    """Look up catastrophic damage result from a 2D6 roll"""
    for (low, high), result in CATASTROPHIC_DAMAGE.items():
        if low <= roll_2d6 <= high:
            return result
    return "drifting_hulk"


