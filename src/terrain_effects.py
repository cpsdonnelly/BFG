"""BFG:XR Terrain Effects - Asteroid fields, dust clouds, warp rifts, tabletop effects"""
import math
import random
from typing import List, Dict
from .models import Ship, Phenomenon, BlastMarker
from .game_state import GameState
from .dice import DiceRoller


def check_ship_terrain_contact(ship: Ship, phenomena: List[Phenomenon]) -> List[Dict]:
    """
    Check if a ship is in contact with any terrain features.
    Returns list of {phenomenon, type, effects}.
    """
    contacts = []
    for p in phenomena:
        if _ship_contacts_phenomenon(ship, p):
            effects = get_phenomenon_effects(p)
            contacts.append({
                "phenomenon": p,
                "type": p.phenomenon_type,
                "effects": effects,
            })
    return contacts


def _ship_contacts_phenomenon(ship: Ship, p: Phenomenon) -> bool:
    """Check if a ship's base contacts a phenomenon."""
    r = ship.base_radius
    if "planet" in p.phenomenon_type and p.radius > 0:
        dist = math.sqrt((ship.x - p.x)**2 + (ship.y - p.y)**2)
        return dist <= p.radius + r
    else:
        # Rectangle check with base radius
        return (abs(ship.x - p.x) <= p.width / 2 + r and
                abs(ship.y - p.y) <= p.height / 2 + r)


def get_phenomenon_effects(p: Phenomenon) -> Dict:
    """Get the gameplay effects of a phenomenon type."""
    effects = {
        "blocks_los": False,
        "blocks_torpedoes": False,
        "destroys_attack_craft_on_6": False,
        "destroys_attack_craft": False,
        "speed_reduction": 0,
        "gunnery_shift": 0,  # right column shifts
        "shields_as_blast": False,  # treated as blast marker for shields
        "navigation_test": False,
        "navigation_dice": 2,  # 2D6 or 3D6
        "damage_on_fail": "D6",
        "max_fire_range": None,
        "half_firepower": False,
        "no_fire_if_crippled": False,
    }

    ptype = p.phenomenon_type

    if ptype == "asteroid_field":
        effects["blocks_los"] = True
        effects["blocks_torpedoes"] = True
        effects["destroys_attack_craft_on_6"] = True
        effects["navigation_test"] = True
        effects["navigation_dice"] = 2  # 3D6 if on AAF
        effects["damage_on_fail"] = "D6"
        effects["max_fire_range"] = 10  # can only fire within 10cm inside
        effects["half_firepower"] = True
        effects["no_fire_if_crippled"] = True

    elif ptype == "gas_dust_cloud":
        effects["shields_as_blast"] = True
        effects["speed_reduction"] = 5
        effects["gunnery_shift"] = 1

    elif ptype == "warp_rift":
        effects["blocks_los"] = True
        effects["blocks_torpedoes"] = True
        effects["destroys_attack_craft"] = True
        effects["navigation_test"] = True
        effects["navigation_dice"] = 3  # always 3D6
        effects["damage_on_fail"] = "lost_in_warp"

    elif "planet" in ptype:
        effects["blocks_los"] = True
        effects["blocks_torpedoes"] = True

    return effects


def resolve_asteroid_navigation(ship: Ship, dice: DiceRoller,
                                 gs: GameState,
                                 on_aaf: bool = False) -> Dict:
    """
    Resolve a ship navigating through an asteroid field.
    Requires Ld test (3D6 if on AAF). Escorts can re-roll.
    On failure: D6 damage (shields block normally, no blast markers).
    """
    num_dice = 3 if on_aaf else 2
    ld = ship.leadership

    roll = sum(dice.roll_d6(num_dice,
        f"{ship.name} asteroid navigation ({num_dice}D6 vs Ld {ld})"))
    passed = roll <= ld

    result = {"passed": passed, "roll": roll, "needed": ld, "damage": 0}

    # Escorts can re-roll on failure
    if not passed and ship.ship_type == "escort":
        gs.add_log(f"  {ship.name} failed but escorts may re-roll")
        roll2 = sum(dice.roll_d6(num_dice,
            f"{ship.name} asteroid re-roll ({num_dice}D6 vs Ld {ld})"))
        passed = roll2 <= ld
        result["roll"] = roll2
        result["passed"] = passed
        if passed:
            gs.add_log(f"  Re-roll passed ({roll2} vs Ld {ld})")

    if not passed:
        # D6 damage, shields block normally, no blast markers from shields
        dmg_roll = dice.roll_d6(1, f"Asteroid damage on {ship.name}")[0]
        result["damage"] = dmg_roll
        gs.add_log(
            f"  {ship.name} fails asteroid navigation! "
            f"Takes {dmg_roll} asteroid damage")

        # Apply damage (shields absorb but no blast markers placed)
        shields = ship.effective_shields
        absorbed = min(dmg_roll, shields)
        hull_dmg = max(0, dmg_roll - absorbed)
        if hull_dmg > 0:
            ship.hits_remaining = max(0, ship.hits_remaining - hull_dmg)
            gs.add_log(f"  {absorbed} absorbed by shields, {hull_dmg} hull damage")

        # Speed reduction: ship is forced back 5cm along reverse heading
        result["speed_reduction"] = 5
        reverse_rad = math.radians((ship.heading + 180) % 360)
        ship.x = max(0, min(gs.table_width, ship.x + 5 * math.cos(reverse_rad)))
        ship.y = max(0, min(gs.table_height, ship.y + 5 * math.sin(reverse_rad)))
        gs.add_log(f"  {ship.name} pushed back 5cm by asteroid impact")
        gs.update_ship(ship)
    else:
        gs.add_log(
            f"  {ship.name} navigates asteroids successfully "
            f"({roll} vs Ld {ld})")

    return result


def resolve_warp_rift_navigation(ship: Ship, dice: DiceRoller,
                                  gs: GameState) -> Dict:
    """
    Resolve a ship entering a warp rift.
    3D6 Ld test. Pass: reposition 2D6x10cm away. Fail: lost in warp.
    """
    ld = ship.leadership
    roll = sum(dice.roll_d6(3, f"{ship.name} warp rift navigation (3D6 vs Ld {ld})"))
    passed = roll <= ld

    result = {"passed": passed, "roll": roll, "needed": ld}

    if passed:
        # Reposition 2D6 x 10cm away
        dist_dice = dice.roll_d6(2, "Reposition distance (2D6 x 10cm)")
        reposition_dist = sum(dist_dice) * 10
        # Pick random direction
        import random
        angle = random.uniform(0, 360)
        new_x = ship.x + reposition_dist * math.cos(math.radians(angle))
        new_y = ship.y + reposition_dist * math.sin(math.radians(angle))
        # Clamp to table
        new_x = max(5, min(gs.table_width - 5, new_x))
        new_y = max(5, min(gs.table_height - 5, new_y))

        ship.x = new_x
        ship.y = new_y
        gs.update_ship(ship)

        result["new_position"] = (new_x, new_y)
        result["distance"] = reposition_dist
        gs.add_log(
            f"  {ship.name} navigates warp rift! "
            f"Repositioned {reposition_dist}cm to ({new_x:.0f}, {new_y:.0f})")
    else:
        # Lost in warp
        ship.status = "disengaged"
        ship.is_disengaged = True
        gs.update_ship(ship)
        gs.add_log(
            f"  {ship.name} LOST IN THE WARP! "
            f"(rolled {roll} vs Ld {ld})")
        # Post-game: D6: 1=destroyed, 2-6=disengaged
        result["post_game_note"] = "Roll D6 after game: 1=destroyed permanently, 2-6=temporarily lost"

    return result


def resolve_gas_dust_contact(ship: Ship, dice: DiceRoller,
                              gs: GameState) -> Dict:
    """
    Resolve a ship in contact with gas/dust cloud.
    Same effect as a single blast marker: -5cm speed,
    shieldless ships take 1 damage on D6=6.
    """
    result = {"speed_penalty": 5, "damage": 0}

    # If ship has no shields at all (permanently disabled, not just depleted)
    has_shields = ship.shields_max > 0
    shield_collapsed = any(
        c.get("crit_type") == "shields_collapse"
        for c in ship.critical_damage)

    if not has_shields or shield_collapsed:
        roll = dice.roll_d6(1, f"{ship.name} dust cloud damage (no shields, 6=1 damage)")[0]
        if roll == 6:
            result["damage"] = 1
            ship.hits_remaining = max(0, ship.hits_remaining - 1)
            gs.update_ship(ship)
            gs.add_log(f"  {ship.name} takes 1 damage from gas/dust cloud")

    return result


# --- Tabletop Effects ---

class TabletopEffects:
    """Manages game-wide effects like solar flares and radiation bursts."""

    def __init__(self):
        self.solar_flare_count = 0      # number of solar flare entries
        self.radiation_burst_count = 0  # number of radiation burst entries
        self.solar_flare_occurred = False  # max once per game
        self.fighting_sunward = False    # inner biosphere or closer
        self.enabled = True

    def check_start_of_turn(self, gs: GameState, dice: DiceRoller) -> List[str]:
        """Check for tabletop effects at the start of a turn."""
        logs = []
        if not self.enabled:
            return logs

        # Solar Flare check
        if self.solar_flare_count > 0 and not self.solar_flare_occurred:
            for _ in range(self.solar_flare_count):
                roll = dice.roll_d6(1, "Solar flare check (6=flare)")[0]
                if roll == 6:
                    self.solar_flare_occurred = True
                    logs.extend(self._resolve_solar_flare(gs, dice))
                    break

        # Radiation Burst check
        if self.radiation_burst_count > 0:
            for _ in range(self.radiation_burst_count):
                roll = dice.roll_d6(1, "Radiation burst check (5+=burst)")[0]
                if roll >= 5:
                    logs.extend(self._resolve_radiation_burst(gs, dice))
                    break

        return logs

    def _resolve_solar_flare(self, gs: GameState, dice: DiceRoller) -> List[str]:
        """Resolve a solar flare event."""
        logs = ["SOLAR FLARE!"]

        # Each ship gets a blast marker
        for s in gs.get_ships():
            if s.is_destroyed or s.is_disengaged:
                continue

            bm = BlastMarker(
                id=f"flare_{s.id}",
                x=s.x + s.base_radius * 0.5,
                y=s.y,
                source="solar_flare",
                heading=random.uniform(0, 360))
            gs.add_blast_marker(bm)

            # Ships without shields take damage
            has_shields = s.shields_max > 0
            shield_collapsed = any(
                c.get("crit_type") == "shields_collapse"
                for c in s.critical_damage)

            if not has_shields or shield_collapsed:
                s.hits_remaining = max(0, s.hits_remaining - 1)
                # Critical on 4+ instead of 6
                crit_roll = dice.roll_d6(1, f"Solar flare crit check on {s.name} (4+)")[0]
                if crit_roll >= 4:
                    logs.append(f"  {s.name}: CRITICAL from solar flare!")
                gs.update_ship(s)
                logs.append(f"  {s.name}: 1 damage (no shields)")

        # Ordnance: 4+ removed
        to_remove = []
        for o_dict in gs.ordnance:
            roll = dice.roll_d6(1, "Ordnance solar flare survival")[0]
            if roll >= 4:
                to_remove.append(o_dict["id"])
        gs.ordnance = [o for o in gs.ordnance if o["id"] not in to_remove]
        if to_remove:
            logs.append(f"  {len(to_remove)} ordnance markers destroyed")

        return logs

    def _resolve_radiation_burst(self, gs: GameState, dice: DiceRoller) -> List[str]:
        """Resolve a radiation burst event."""
        interference = dice.roll_d6(1, "Radiation interference level")[0]
        logs = [f"RADIATION BURST! All ships -{interference} Leadership this turn"]

        # Apply to all ships
        for i, s_dict in enumerate(gs.ships):
            s = Ship.from_dict(s_dict)
            if s.is_destroyed or s.is_disengaged:
                continue
            # Temporarily reduce leadership (will need to be restored at end of turn)
            # Store original Ld for restoration
            gs.ships[i]["_original_ld"] = s.leadership
            gs.ships[i]["leadership"] = max(1, s.leadership - interference)

        logs.append("  Fleet commanders may only re-roll for their own ship")
        return logs

    def restore_leadership(self, gs: GameState):
        """Restore leadership values after radiation burst."""
        for i, s_dict in enumerate(gs.ships):
            if "_original_ld" in s_dict:
                gs.ships[i]["leadership"] = s_dict["_original_ld"]
                del gs.ships[i]["_original_ld"]
