"""BFG:XR Map Maker - Celestial phenomena generation and map editor"""
import math
import json
import os
import random
from typing import List, Dict
from .dice import DiceRoller


# Battlezone types (from rulebook p48-51)
BATTLEZONES = {
    1: "Flare Region",
    2: "Mercurial Zone",
    3: "Inner Biosphere",
    4: "Primary Biosphere",
    5: "Outer Reaches",
    6: "Deep Space",
}

# Phenomena tables per battlezone (D6 roll -> result)
# Results: "solar_flare", "radiation_burst", "asteroid_field", "gas_dust_cloud",
#          "planet_small", "planet_medium", "planet_large", "warp_rift"
# Some results require sub-rolls (e.g. D3 asteroid fields)

PHENOMENA_TABLES = {
    1: {  # Flare Region
        1: ("effect", "solar_flare"),
        2: ("effect", "solar_flare"),
        3: ("effect", "radiation_burst"),
        4: ("feature", "asteroid_field", 1),
        5: ("feature", "gas_dust_cloud", "D3"),
        6: ("feature", "planet", "small_or_medium"),
    },
    2: {  # Mercurial Zone
        1: ("effect", "solar_flare"),
        2: ("effect", "radiation_burst"),
        3: ("feature", "asteroid_field", 1),
        4: ("feature", "gas_dust_cloud", "D3"),
        5: ("feature", "gas_dust_cloud", "D3"),
        6: ("feature", "planet", "small_or_medium"),
    },
    3: {  # Inner Biosphere
        1: ("effect", "solar_flare_or_radiation"),
        2: ("feature", "asteroid_field", 1),
        3: ("feature", "asteroid_field", "D3"),
        4: ("feature", "gas_dust_cloud", "D3"),
        5: ("feature", "gas_dust_cloud", "D3"),
        6: ("feature", "planet", "small_or_medium"),
    },
    4: {  # Primary Biosphere
        1: ("feature", "asteroid_field", 1),
        2: ("feature", "asteroid_field", "D3"),
        3: ("feature", "gas_dust_cloud", 1),
        4: ("feature", "gas_dust_cloud", "D3"),
        5: ("feature", "planet", "small_or_medium"),
        6: ("feature", "planet", "small_or_medium"),
    },
    5: {  # Outer Reaches
        1: ("feature", "asteroid_field", "D3+1"),
        2: ("feature", "asteroid_field", "D3"),
        3: ("feature", "gas_dust_cloud", "D3"),
        4: ("feature", "gas_dust_cloud", 1),
        5: ("feature", "planet", "small_or_large"),
        6: ("feature", "planet", "small_or_large"),
    },
    6: {  # Deep Space
        1: ("feature", "asteroid_field", "D3"),
        2: ("feature", "asteroid_field", 1),
        3: ("feature", "gas_dust_cloud", "D3"),
        4: ("feature", "gas_dust_cloud", 1),
        5: ("feature", "warp_rift", 1),
        6: ("feature", "planet_small", 1),  # rogue moon
    },
}


def generate_random_map(table_width: float, table_height: float,
                        battlezone: int, dice: DiceRoller) -> List[Dict]:
    """
    Generate random celestial phenomena using the BFG:XR rules.
    Divides table into 60cm squares, rolls D6 per square (4+ = phenomena).
    Returns list of phenomenon dicts ready for GameState.
    """
    phenomena = []
    planet_placed = False
    feature_id = 0

    # Divide into 60cm grid
    cols = max(1, int(table_width / 60))
    rows = max(1, int(table_height / 60))

    for row in range(rows):
        for col in range(cols):
            # Roll D6: 4+ = phenomena in this square
            roll = dice.roll_d6(1, f"Phenomena check for grid ({col},{row})")[0]
            if roll < 4:
                continue

            # Roll on battlezone table
            table_roll = dice.roll_d6(1, f"Phenomena type for grid ({col},{row})")[0]
            entry = PHENOMENA_TABLES[battlezone][table_roll]

            # Grid center position
            cx = (col + 0.5) * 60
            cy = (row + 0.5) * 60
            # Add some randomness within the grid square
            cx += random.uniform(-20, 20)
            cy += random.uniform(-20, 20)
            cx = max(10, min(table_width - 10, cx))
            cy = max(10, min(table_height - 10, cy))

            if entry[0] == "effect":
                # Effects are noted but don't create terrain
                continue

            feature_type = entry[1]

            # Count
            count_spec = entry[2] if len(entry) > 2 else 1
            if count_spec == "D3":
                count = dice.roll_d3("Number of features")
            elif count_spec == "D3+1":
                count = dice.roll_d3("Number of features") + 1
            elif isinstance(count_spec, int):
                count = count_spec
            else:
                count = 1

            for i in range(count):
                # Offset multiple features within the grid
                fx = cx + random.uniform(-15, 15) * (i > 0)
                fy = cy + random.uniform(-15, 15) * (i > 0)
                fx = max(5, min(table_width - 5, fx))
                fy = max(5, min(table_height - 5, fy))

                if "planet" in feature_type:
                    if planet_placed:
                        continue  # random gen: max one planet per table (re-roll rule)
                    planet_placed = True
                    planet_list = _create_planet(feature_type, fx, fy, feature_id, dice)
                    phenomena.extend(planet_list)
                    feature_id += len(planet_list)
                elif feature_type == "asteroid_field":
                    p = _create_asteroid(fx, fy, feature_id, dice)
                    if p:
                        phenomena.append(p)
                        feature_id += 1
                elif feature_type == "gas_dust_cloud":
                    p = _create_dust_cloud(fx, fy, feature_id, dice)
                    if p:
                        phenomena.append(p)
                        feature_id += 1
                elif feature_type == "warp_rift":
                    p = _create_warp_rift(fx, fy, feature_id)
                    if p:
                        phenomena.append(p)
                        feature_id += 1
                else:
                    continue

    return phenomena


def _create_planet(ptype: str, x: float, y: float, fid: int,
                   dice: DiceRoller) -> List[Dict]:
    """Create a planet with optional moons and rings. Returns list of phenomena."""
    results = []

    if "small_or_medium" in ptype:
        size_roll = dice.roll_d6(1, "Planet size (1-5=small, 6=medium)")[0]
        size = "planet_medium" if size_roll == 6 else "planet_small"
    elif "small_or_large" in ptype:
        size_roll = dice.roll_d6(1, "Planet size (1-3=small, 4-6=large)")[0]
        size = "planet_large" if size_roll >= 4 else "planet_small"
    elif "small" in ptype:
        size = "planet_small"
    elif "large" in ptype:
        size = "planet_large"
    else:
        size = "planet_medium"

    radius_map = {"planet_small": 3, "planet_medium": 5, "planet_large": 8}
    radius = radius_map.get(size, 5)

    # Main planet
    results.append({
        "id": f"planet_{fid}",
        "phenomenon_type": size,
        "x": x, "y": y,
        "width": radius * 2, "height": radius * 2,
        "radius": radius,
        "rotation": 0,
        "special_rules": [],
    })

    # Moons (medium: D3-1, large: D6-2)
    num_moons = 0
    if size == "planet_medium":
        num_moons = max(0, dice.roll_d3("Medium planet moons (D3-1)") - 1)
    elif size == "planet_large":
        num_moons = max(0, dice.roll_d6(1, "Large planet moons (D6-2)")[0] - 2)

    for m in range(num_moons):
        # Place moon at random distance and angle from planet
        moon_dist = radius + 5 + random.uniform(3, 12)
        moon_angle = random.uniform(0, 360)
        moon_x = x + moon_dist * math.cos(math.radians(moon_angle))
        moon_y = y + moon_dist * math.sin(math.radians(moon_angle))
        results.append({
            "id": f"moon_{fid}_{m}",
            "phenomenon_type": "planet_small",  # moons are small planets
            "x": moon_x, "y": moon_y,
            "width": 4, "height": 4,
            "radius": 2,
            "rotation": 0,
            "special_rules": [],
        })

    # Rings (large planets only: D6, 5-6 = D3 rings)
    if size == "planet_large":
        ring_roll = dice.roll_d6(1, "Large planet rings (5-6 = rings)")[0]
        if ring_roll >= 5:
            num_rings = dice.roll_d3("Number of rings (D3)")
            for r in range(num_rings):
                ring_width = dice.roll_d6(1, f"Ring {r+1} width (D6 cm)")[0]
                ring_dist_roll = dice.roll_d6(1, f"Ring {r+1} distance (D6 x 5cm)")[0]
                ring_distance = ring_dist_roll * 5  # cm from planet edge
                ring_inner = radius + ring_distance
                ring_outer = ring_inner + ring_width

                # Ring type: D6, 1-4 = gas/dust, 5-6 = asteroid
                ring_type_roll = dice.roll_d6(1, f"Ring {r+1} type (1-4=dust, 5-6=asteroid)")[0]
                ring_ptype = "gas_dust_cloud" if ring_type_roll <= 4 else "asteroid_field"

                # Represent ring as a wide thin rectangle (approximation)
                # Actually a ring is circular - we'll place it as a phenomenon
                # with special rendering. For now, approximate as a donut shape
                # by noting inner/outer radius
                results.append({
                    "id": f"ring_{fid}_{r}",
                    "phenomenon_type": ring_ptype,
                    "x": x, "y": y,
                    "width": ring_outer * 2,
                    "height": ring_outer * 2,
                    "radius": 0,
                    "rotation": 0,
                    "special_rules": [f"ring_inner_{ring_inner}", f"ring_outer_{ring_outer}"],
                })

    return results


def _create_asteroid(x: float, y: float, fid: int,
                     dice: DiceRoller) -> Dict:
    """Create an asteroid field."""
    width = random.uniform(12, 25)
    height = random.uniform(10, 20)
    return {
        "id": f"asteroid_{fid}",
        "phenomenon_type": "asteroid_field",
        "x": x, "y": y,
        "width": width, "height": height,
        "radius": 0, "rotation": 0,
        "special_rules": [],
    }


def _create_dust_cloud(x: float, y: float, fid: int,
                       dice: DiceRoller) -> Dict:
    """Create a gas/dust cloud."""
    width = random.uniform(10, 20)
    height = random.uniform(8, 16)
    return {
        "id": f"dust_{fid}",
        "phenomenon_type": "gas_dust_cloud",
        "x": x, "y": y,
        "width": width, "height": height,
        "radius": 0, "rotation": 0,
        "special_rules": [],
    }


def _create_warp_rift(x: float, y: float, fid: int) -> Dict:
    """Create a warp rift."""
    width = random.uniform(8, 15)
    height = random.uniform(8, 15)
    return {
        "id": f"warp_rift_{fid}",
        "phenomenon_type": "warp_rift",
        "x": x, "y": y,
        "width": width, "height": height,
        "radius": 0, "rotation": 0,
        "special_rules": [],
    }


def save_map(phenomena: List[Dict], table_width: float, table_height: float,
             sunward: str, filepath: str):
    """Save a map to a JSON file."""
    map_data = {
        "table_width": table_width,
        "table_height": table_height,
        "sunward_edge": sunward,
        "phenomena": phenomena,
    }
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(map_data, f, indent=2)


def load_map(filepath: str) -> Dict:
    """Load a map from a JSON file."""
    with open(filepath) as f:
        return json.load(f)
