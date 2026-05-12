"""BFG:XR Ordnance Phase - Torpedo and attack craft resolution"""
import math
from typing import List, Dict, Optional, Tuple
from .models import Ship, OrdnanceMarker, BlastMarker, OrdnanceType
from .game_state import GameState
from .geometry import (BASE_CONTACT_MARGIN_CM, circle_touches_torpedo,
                        TORP_BODY_HALF_W_CM, ATTACK_CRAFT_HALF_SIDE_CM)
from .dice import DiceRoller


def move_ordnance(marker: OrdnanceMarker, game_state: GameState):
    """Move a single ordnance marker forward along its heading.
    Tau guided missiles are player-controlled and should be moved via the dialog,
    not auto-moved here. This function only handles non-guided ordnance."""
    # Skip Tau missiles - they are player-controlled
    if (marker.ordnance_type == OrdnanceType.TORPEDO_GUIDED.value
            and marker.can_turn):
        return  # player moves these via dialog

    # CAP fighters stay with their parent ship; position updated separately
    if marker.cap_ship_id:
        return

    # Mine fields home on the nearest enemy ship automatically
    if marker.ordnance_type == OrdnanceType.MINE_FIELD.value:
        ships = game_state.get_ships()
        enemies = [s for s in ships
                   if s.player != marker.owner_player
                   and not s.is_destroyed and not s.is_disengaged]
        if not enemies:
            return
        nearest = min(enemies,
                      key=lambda s: math.sqrt((s.x - marker.x)**2
                                              + (s.y - marker.y)**2))
        dx = nearest.x - marker.x
        dy = nearest.y - marker.y
        dist = math.sqrt(dx**2 + dy**2)
        if dist > 0:
            marker.x += marker.speed * dx / dist
            marker.y += marker.speed * dy / dist
            marker.heading = math.degrees(math.atan2(dy, dx)) % 360
        return

    rad = math.radians(marker.heading)
    marker.x += marker.speed * math.cos(rad)
    marker.y += marker.speed * math.sin(rad)


def degrade_tau_missiles(game_state: GameState, dice: DiceRoller,
                         current_turn: int):
    """
    Tau missile degradation: for salvos from previous turns,
    roll 1D6 per strength point. Each 1 reduces strength by 1.
    """
    to_remove = []
    for i, o_dict in enumerate(game_state.ordnance):
        marker = OrdnanceMarker.from_dict(o_dict)
        if (marker.ordnance_type == OrdnanceType.TORPEDO_GUIDED.value
                and marker.launched_turn < current_turn
                and marker.strength > 0):
            rolls = dice.roll_d6(
                marker.strength,
                f"Tau missile Str {marker.strength} degradation (each 1 = lose 1 Str)")
            losses = rolls.count(1)
            if losses > 0:
                marker.strength = max(0, marker.strength - losses)
                game_state.add_log(
                    f"Tau missile salvo lost {losses} strength (now {marker.strength})")
                game_state.ordnance[i] = marker.to_dict()
            if marker.strength <= 0:
                to_remove.append(marker.id)
                game_state.add_log("Tau missile salvo burned out")
    game_state.ordnance = [o for o in game_state.ordnance if o["id"] not in to_remove]


def get_massed_turret_bonus(ship: Ship, all_ships: List[Ship]) -> int:
    """
    Massed turrets: +1 per non-crippled friendly ship in base contact, max +3.
    Crippled ships cannot contribute.
    """
    bonus = 0
    for ally in all_ships:
        if ally.id == ship.id:
            continue
        if ally.player != ship.player:
            continue
        if ally.is_destroyed or ally.is_disengaged or ally.is_crippled:
            continue
        dist = math.sqrt((ally.x - ship.x)**2 + (ally.y - ship.y)**2)
        if dist <= ally.base_radius + ship.base_radius + BASE_CONTACT_MARGIN_CM:
            bonus += 1
            if bonus >= 3:
                break
    return bonus


def check_torpedo_contact(marker: OrdnanceMarker, ship: Ship) -> bool:
    """Check if a torpedo marker contacts a ship's base."""
    return circle_touches_torpedo(ship.x, ship.y, ship.base_radius,
                                   marker.x, marker.y, marker.heading)


def resolve_torpedo_attack(marker: OrdnanceMarker, target: Ship,
                           dice: DiceRoller, game_state: GameState,
                           all_ships: List[Ship] = None) -> Dict:
    """Resolve torpedo attack. Bypasses shields. Turrets defend first.
    Turrets cannot fire if already used against attack craft this phase."""
    result = {"hits": 0, "turret_kills": 0, "remaining_strength": marker.strength}

    turrets = target.effective_turrets

    # Massed turrets: +1 per non-crippled friendly ship in base contact (max +3)
    if all_ships:
        bonus = get_massed_turret_bonus(target, all_ships)
        if bonus > 0:
            turrets += bonus
            game_state.add_log(
                f"  {target.name} massed turrets: +{bonus} "
                f"(total {turrets})")

    # Check turret restriction: can't use vs torps if already used vs craft
    turret_blocked = (target.turrets_used_vs == "craft")
    if turret_blocked:
        game_state.add_log(f"  {target.name} turrets already used vs attack craft this phase")
        turrets = 0

    if turrets > 0:
        turret_rolls = dice.roll_d6(turrets, f"{target.name} turrets vs torpedoes (4+)")
        turret_kills = sum(1 for d in turret_rolls if d >= 4)
        result["turret_kills"] = turret_kills
        result["remaining_strength"] = max(0, marker.strength - turret_kills)
        game_state.add_log(f"{target.name} turrets destroy {turret_kills} torpedoes")
        # Mark turrets as used vs torps
        target.turrets_used_vs = "torp"
        game_state.update_ship(target)

    if result["remaining_strength"] <= 0:
        return result

    # Determine armor facing
    target_arc = target.get_arc_for_bearing(target.bearing_to(marker.x, marker.y))
    armor = target.armor_prow_value if target_arc.value == "front" else target.armor_side_value

    attack_rolls = dice.roll_d6(
        result["remaining_strength"],
        f"Torpedoes vs {target.name} (need {armor}+)")
    result["hits"] = sum(1 for d in attack_rolls if d >= armor)

    if result["hits"] > 0:
        game_state.add_log(
            f"Torpedoes hit {target.name} for {result['hits']} damage (bypasses shields)")
        from .combat import apply_damage
        apply_damage(target, result["hits"], dice, game_state, ignores_shields=True)

    return result


def resolve_mine_contact(marker: OrdnanceMarker, ship: Ship,
                         dice: DiceRoller, game_state: GameState,
                         all_ships: List[Ship] = None) -> Dict:
    """
    Resolve a single mine detonating against a ship.

    Turret defense: roll the ship's effective turrets (plus massed turret bonus).
    - If ANY die scores 4+: mine attacks with 4D6 instead of 8D6.
    - Otherwise: mine attacks with 8D6.
    Mine damage CAN be blocked by shields (unlike torpedoes/bombers).
    Turret restriction (torp/craft split) does not apply to mines.
    """
    result = {"hits": 0, "attack_dice": 8}

    turrets = ship.effective_turrets

    # Massed turrets: +1 per non-crippled friendly ship in base contact (max +3)
    if all_ships:
        bonus = get_massed_turret_bonus(ship, all_ships)
        if bonus > 0:
            turrets += bonus
            game_state.add_log(
                f"  {ship.name} massed turrets: +{bonus} (total {turrets})")
    attack_dice = 8

    if turrets > 0:
        turret_rolls = dice.roll_d6(
            turrets, f"{ship.name} turrets vs mine (any 4+ reduces to 4D6)")
        if any(r >= 4 for r in turret_rolls):
            attack_dice = 4
            game_state.add_log(
                f"  Turrets reduce mine attack to 4D6")
        else:
            game_state.add_log(
                f"  Turrets fail — mine attacks with 8D6")

    result["attack_dice"] = attack_dice

    # Bearing determines which armor face the mine hits
    target_arc = ship.get_arc_for_bearing(ship.bearing_to(marker.x, marker.y))
    armor = (ship.armor_prow_value if target_arc.value == "front"
             else ship.armor_side_value)

    attack_rolls = dice.roll_d6(attack_dice,
                                 f"Mine vs {ship.name} ({armor}+)")
    result["hits"] = sum(1 for r in attack_rolls if r >= armor)

    if result["hits"] > 0:
        from .combat import apply_damage
        apply_damage(ship, result["hits"], dice, game_state, ignores_shields=False)
        game_state.add_log(
            f"  Mine: {result['hits']} hit(s) on {ship.name} (shields apply)")

    return result


def resolve_bomber_attack(marker: OrdnanceMarker, target: Ship,
                          dice: DiceRoller, game_state: GameState,
                          suppressed_by_fighter: bool = False,
                          remastered_fighter_bonus: int = 0,
                          remastered_bomber_cap: int = 1,
                          all_ships: List[Ship] = None) -> Dict:
    """
    Resolve bomber attack. D6 attacks per squadron vs lowest armor. Bypasses shields.

    Per XR rules:
    - Turret reduction uses base turrets ONLY; massed turret bonus does not apply.
    - Turret reduction always applies, even if turrets fired at torpedoes this phase
      (the restriction is one-way: craft→blocks torp, but torp does NOT block craft).

    Turret suppression modes:
      XR (default): suppressed_by_fighter=True → exactly 3 attacks, turrets bypassed.
      Remastered:   remastered_fighter_bonus added to D6 roll, capped at remastered_bomber_cap.
    """
    result = {"attacks": 0, "hits": 0, "turret_reduction": 0, "suppressed": False}

    # Base turrets only — massed turret bonus does NOT apply to bomber attack reduction
    turret_reduction = target.effective_turrets

    if suppressed_by_fighter:
        # XR mode: fighter suppression gives this bomber exactly 3 attacks, ignoring turrets
        total_attacks = 3
        result["suppressed"] = True
        result["turret_reduction"] = 0
        game_state.add_log(
            f"  Fighter suppression: {marker.ordnance_type} gets 3 attacks "
            f"(turrets bypassed)")
    else:
        # Mark turrets as used vs craft so torpedo defence knows
        target.turrets_used_vs = "craft"
        game_state.update_ship(target)

        attack_roll = dice.roll_d6(1, f"Bomber attacks on {target.name}")[0]

        if remastered_fighter_bonus > 0:
            # Remastered mode: add fighter bonus, cap at total attacking bombers
            raw = attack_roll + remastered_fighter_bonus
            total_attacks = max(0, min(raw, remastered_bomber_cap) - turret_reduction)
            game_state.add_log(
                f"  Remastered suppression: roll {attack_roll} "
                f"+{remastered_fighter_bonus} fighters "
                f"(cap {remastered_bomber_cap}) - {turret_reduction} turrets "
                f"= {total_attacks} attacks")
        else:
            total_attacks = max(0, attack_roll - turret_reduction)

        result["turret_reduction"] = turret_reduction

    result["attacks"] = total_attacks

    if total_attacks > 0:
        armor = min(target.armor_prow_value, target.armor_side_value)
        hit_rolls = dice.roll_d6(total_attacks, f"Bomber hits vs {target.name} ({armor}+)")
        result["hits"] = sum(1 for d in hit_rolls if d >= armor)

        if result["hits"] > 0:
            from .combat import apply_damage
            apply_damage(target, result["hits"], dice, game_state, ignores_shields=True)
            game_state.add_log(f"Bombers hit {target.name} for {result['hits']} damage")

    return result


def resolve_fighter_intercept(fighter: OrdnanceMarker,
                              target: OrdnanceMarker,
                              dice: DiceRoller,
                              game_state: GameState) -> Dict:
    """
    Resolve fighter vs ordnance contact. Fighters MUST intercept.

    Fighter vs torpedo/missile: BOTH removed. Entire salvo destroyed regardless of strength.
    Fighter vs attack craft: mutual destruction. Resilient saves apply.
    Fighter vs fighter: mutual destruction. Resilient saves apply.
    Fighter vs mine: both removed.

    Returns {"fighter_removed": bool, "target_removed": bool}
    """
    result = {"fighter_removed": True, "target_removed": True}

    is_torpedo = target.ordnance_type in (
        OrdnanceType.TORPEDO_STANDARD.value,
        OrdnanceType.TORPEDO_GUIDED.value,
    )

    if is_torpedo:
        # One fighter marker destroys the ENTIRE torpedo salvo
        # Both the fighter and the full salvo are removed
        game_state.add_log(
            f"Fighter intercepts {target.ordnance_type} "
            f"Str {target.strength} - entire salvo destroyed!")

        # Fighter resilient save
        if fighter.resilient_save > 0 and not fighter.resilient_used:
            save = dice.roll_d6(1,
                f"Resilient save for fighter ({fighter.resilient_save}+)")[0]
            if save >= fighter.resilient_save:
                result["fighter_removed"] = False
                fighter.resilient_used = True
                game_state.add_log(f"  Fighter passes resilient save, survives!")

    else:
        # Fighter vs attack craft: mutual destruction
        game_state.add_log(
            f"Fighter intercepts {target.ordnance_type} - mutual destruction")

        # Fighter resilient save
        if fighter.resilient_save > 0 and not fighter.resilient_used:
            save = dice.roll_d6(1,
                f"Resilient save for fighter ({fighter.resilient_save}+)")[0]
            if save >= fighter.resilient_save:
                result["fighter_removed"] = False
                fighter.resilient_used = True
                game_state.add_log(f"  Fighter passes resilient save!")

        # Target resilient save
        if target.resilient_save > 0 and not target.resilient_used:
            save = dice.roll_d6(1,
                f"Resilient save for {target.ordnance_type} ({target.resilient_save}+)")[0]
            if save >= target.resilient_save:
                result["target_removed"] = False
                target.resilient_used = True
                game_state.add_log(
                    f"  {target.ordnance_type} passes resilient save!")

    return result


def check_ordnance_contact(marker1: OrdnanceMarker,
                           marker2: OrdnanceMarker) -> bool:
    """Check if two ordnance markers are in contact."""
    dist = math.sqrt((marker1.x - marker2.x)**2 + (marker1.y - marker2.y)**2)
    return dist <= 2.5  # roughly base contact for ordnance markers


def is_fighter_type(marker: OrdnanceMarker) -> bool:
    """Check if an ordnance marker acts as a fighter (intercepts ordnance)."""
    return marker.ordnance_type in (
        OrdnanceType.FIGHTER.value,
        OrdnanceType.BARRACUDA.value,
        OrdnanceType.MANTA.value,  # Manta is multi-role: fighter + bomber
    )


def resolve_ordnance_interactions(game_state: GameState,
                                   dice: DiceRoller) -> List[str]:
    """
    Resolve all ordnance-vs-ordnance interactions after movement.
    Fighters intercept enemy ordnance they contact (compulsory).
    Torpedo salvos that contact each other are both destroyed.
    Returns log messages.
    """
    logs = []
    to_remove = set()

    ordnance = [OrdnanceMarker.from_dict(o) for o in game_state.ordnance]

    for i, m1 in enumerate(ordnance):
        if m1.id in to_remove:
            continue
        if m1.cap_ship_id:
            continue  # CAP fighters intercept via ship contact, not open-space interactions
        for j, m2 in enumerate(ordnance):
            if i >= j or m2.id in to_remove or m1.id in to_remove:
                continue
            if m2.cap_ship_id:
                continue  # same for the other marker
            if m1.owner_player == m2.owner_player:
                continue  # friendly ordnance doesn't interact
            if not check_ordnance_contact(m1, m2):
                continue

            # Fighter vs anything: compulsory intercept
            m1_is_fighter = is_fighter_type(m1)
            m2_is_fighter = is_fighter_type(m2)

            if m1_is_fighter and not m2_is_fighter:
                result = resolve_fighter_intercept(m1, m2, dice, game_state)
                if result["fighter_removed"]:
                    to_remove.add(m1.id)
                if result["target_removed"]:
                    to_remove.add(m2.id)

            elif m2_is_fighter and not m1_is_fighter:
                result = resolve_fighter_intercept(m2, m1, dice, game_state)
                if result["fighter_removed"]:
                    to_remove.add(m2.id)
                if result["target_removed"]:
                    to_remove.add(m1.id)

            elif m1_is_fighter and m2_is_fighter:
                # Fighter vs fighter: mutual destruction with resilient saves
                result = resolve_fighter_intercept(m1, m2, dice, game_state)
                if result["fighter_removed"]:
                    to_remove.add(m1.id)
                if result["target_removed"]:
                    to_remove.add(m2.id)

            else:
                # Non-fighter vs non-fighter (e.g. torpedo vs torpedo)
                # Both torpedo salvos are destroyed on contact
                is_torp1 = "torpedo" in m1.ordnance_type
                is_torp2 = "torpedo" in m2.ordnance_type
                if is_torp1 and is_torp2:
                    to_remove.add(m1.id)
                    to_remove.add(m2.id)
                    logs.append(
                        f"Torpedo salvos collide and detonate!")

    # Remove destroyed ordnance and persist state changes on survivors
    # (resilient_used flag may have been set on markers that survived)
    surviving = {m.id: m for m in ordnance if m.id not in to_remove}
    if to_remove:
        game_state.ordnance = [
            surviving[o["id"]].to_dict() if o["id"] in surviving else o
            for o in game_state.ordnance
            if o["id"] not in to_remove]
        logs.append(f"  {len(to_remove)} ordnance markers removed")
    elif any(m.resilient_used for m in ordnance):
        # No removals but resilient_used flags changed — persist them
        id_to_marker = {m.id: m for m in ordnance}
        game_state.ordnance = [
            id_to_marker[o["id"]].to_dict() if o["id"] in id_to_marker else o
            for o in game_state.ordnance]

    return logs


def check_ordnance_vs_blast(marker: OrdnanceMarker,
                            blast_markers: List[BlastMarker],
                            dice: DiceRoller) -> bool:
    """Check if ordnance moving through blast markers is destroyed (D6=6). Returns True if destroyed."""
    for bm in blast_markers:
        dist = math.sqrt((marker.x - bm.x)**2 + (marker.y - bm.y)**2)
        if dist < 2.0:
            roll = dice.roll_d6(1, "Ordnance through blast marker (6=destroyed)")[0]
            return roll == 6
    return False


_TORP_LIKE = {
    OrdnanceType.TORPEDO_STANDARD.value,
    OrdnanceType.TORPEDO_GUIDED.value,
    OrdnanceType.MINE_FIELD.value,
}

_ATTACK_CRAFT = {
    OrdnanceType.FIGHTER.value,
    OrdnanceType.BOMBER.value,
    OrdnanceType.ASSAULT_BOAT.value,
    OrdnanceType.TORPEDO_BOMBER.value,
    OrdnanceType.MANTA.value,
    OrdnanceType.BARRACUDA.value,
}


def check_ordnance_vs_phenomena(marker: OrdnanceMarker,
                                 phenomena,
                                 dice: DiceRoller) -> Tuple[bool, str]:
    """
    Check if ordnance is destroyed by terrain phenomena.

    Torpedoes/mines: asteroid fields, planets, warp rifts = auto-destroyed;
                     gas/dust cloud = D6=6 destroys.
    Attack craft:    asteroid field = D6=6 destroys; warp rift/planets = auto-destroyed;
                     gas/dust cloud = no effect.

    Returns (destroyed: bool, reason: str).
    """
    is_torp = marker.ordnance_type in _TORP_LIKE
    is_craft = marker.ordnance_type in _ATTACK_CRAFT
    if not is_torp and not is_craft:
        return False, ""

    # Approximate marker half-size for terrain contact (circular bounding radius)
    marker_r = TORP_BODY_HALF_W_CM if is_torp else ATTACK_CRAFT_HALF_SIDE_CM

    for p in phenomena:
        if "planet" in p.phenomenon_type and p.radius > 0:
            dist = math.sqrt((marker.x - p.x)**2 + (marker.y - p.y)**2)
            in_contact = dist <= p.radius + marker_r
        else:
            in_contact = (abs(marker.x - p.x) <= p.width / 2 + marker_r and
                          abs(marker.y - p.y) <= p.height / 2 + marker_r)

        if not in_contact:
            continue

        ptype = p.phenomenon_type

        if is_craft:
            if ptype == "asteroid_field":
                roll = dice.roll_d6(1, f"Attack craft in asteroid field (6=destroyed)")[0]
                if roll == 6:
                    return True, "asteroid_field"
            elif ptype == "warp_rift" or "planet" in ptype:
                return True, ptype
            # Gas/dust clouds have no effect on attack craft
        else:
            # Torpedoes and mines
            if ptype in ("asteroid_field", "warp_rift") or "planet" in ptype:
                return True, ptype
            if ptype == "gas_dust_cloud":
                roll = dice.roll_d6(1, "Ordnance through dust cloud (6=destroyed)")[0]
                if roll == 6:
                    return True, "gas_dust_cloud"

    return False, ""


def launch_torpedoes(ship: Ship, weapon: Dict, game_state: GameState) -> OrdnanceMarker:
    """Create a torpedo marker from a ship's launcher."""
    torpedo_type = weapon.get("torpedo_type", "standard")
    o_type = (OrdnanceType.TORPEDO_GUIDED.value if torpedo_type == "guided"
              else OrdnanceType.TORPEDO_STANDARD.value)

    marker = OrdnanceMarker(
        id=f"torp_{ship.id}_{game_state.turn_number}",
        ordnance_type=o_type, owner_player=ship.player,
        launched_by=ship.id, x=ship.x, y=ship.y,
        heading=ship.heading, strength=weapon["strength"],
        speed=weapon.get("torpedo_speed", 30),
        launched_turn=game_state.turn_number,
        can_turn=(torpedo_type == "guided"),
        turn_angle=45 if torpedo_type == "guided" else 0,
    )
    game_state.add_ordnance(marker)
    ship.ordnance_loaded_torps = False
    game_state.update_ship(ship)
    game_state.add_log(f"{ship.name} launches torpedo salvo (Str {weapon['strength']})")
    return marker


def launch_attack_craft(ship: Ship, weapon: Dict, craft_type: str,
                        count: int, game_state: GameState) -> List[OrdnanceMarker]:
    """Create attack craft markers from launch bays."""
    craft_stats = {
        "manta": (OrdnanceType.MANTA.value, 20, 4),
        "barracuda": (OrdnanceType.BARRACUDA.value, 25, 0),
        "fury_fighter": (OrdnanceType.FIGHTER.value, 30, 0),
        "starhawk_bomber": (OrdnanceType.BOMBER.value, 20, 0),
    }
    o_type, speed, resilient = craft_stats.get(
        craft_type, (OrdnanceType.FIGHTER.value, 30, 0))

    markers = []
    for i in range(count):
        marker = OrdnanceMarker(
            id=f"craft_{ship.id}_{craft_type}_{i}_{game_state.turn_number}",
            ordnance_type=o_type, owner_player=ship.player,
            launched_by=ship.id, x=ship.x, y=ship.y,
            heading=ship.heading, speed=speed,
            launched_turn=game_state.turn_number,
            resilient_save=resilient,
        )
        markers.append(marker)
        game_state.add_ordnance(marker)

    ship.ordnance_loaded_craft = False
    game_state.update_ship(ship)
    game_state.add_log(f"{ship.name} launches {count}x {craft_type}")
    return markers
