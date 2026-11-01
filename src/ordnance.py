"""BFG:XR Ordnance Phase - Torpedo and attack craft resolution"""
import math
import uuid as _uuid
from typing import List, Dict, Optional, Tuple
from .models import (Ship, OrdnanceMarker, BlastMarker, OrdnanceType,
                     SpecialOrder, signed_angle_diff)
from .game_state import GameState
from .geometry import (BASE_CONTACT_MARGIN_CM, circle_touches_torpedo,
                        TORP_BODY_HALF_W_CM, ATTACK_CRAFT_HALF_SIDE_CM)
from .dice import DiceRoller


# Default torpedo marker speed (cm/turn) when the weapon entry has no override
TORPEDO_SPEED_DEFAULT = 30


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

    # Attack craft fly at their target, turning freely, up to their speed (s.18)
    if marker.ordnance_type in ATTACK_CRAFT_TYPES and marker.craft_target_id:
        point = craft_target_point(marker, game_state)
        if point is not None:
            move_craft_toward(marker, *point)
            return
        marker.craft_target_id = ""     # target gone: carry straight on

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


def craft_target_point(marker: OrdnanceMarker,
                       game_state: GameState) -> Optional[Tuple[float, float]]:
    """Where an attack craft squadron's target is now: a ship still in play or
    an ordnance marker still on the table. None if it's gone."""
    tid = marker.craft_target_id
    ship = game_state.get_ship_by_id(tid)
    if ship is not None:
        if ship.is_destroyed or ship.is_disengaged:
            return None
        return ship.x, ship.y
    for o in game_state.ordnance:
        if o["id"] == tid and o["id"] != marker.id:
            return o["x"], o["y"]
    return None


def move_craft_toward(marker: OrdnanceMarker, tx: float, ty: float) -> float:
    """Move straight at (tx, ty), up to the craft's speed, stopping there if it
    is closer (s.18: attack craft may turn as often as desired). Returns the
    distance moved."""
    dx, dy = tx - marker.x, ty - marker.y
    dist = math.hypot(dx, dy)
    if dist < 1e-9:
        return 0.0
    step = min(marker.speed, dist)
    marker.heading = math.degrees(math.atan2(dy, dx)) % 360
    marker.x += dx / dist * step
    marker.y += dy / dist * step
    return step


def ai_craft_target(marker: OrdnanceMarker, game_state: GameState) -> str:
    """AI choice of target for one attack craft squadron: fighters intercept the
    nearest enemy ordnance within two moves; craft that attack ships go for the
    nearest enemy ship; anything else heads for the nearest enemy ship too."""
    def dist(x, y):
        return math.hypot(x - marker.x, y - marker.y)

    enemy_ships = [s for s in game_state.get_ships()
                   if s.player != marker.owner_player and not s.is_destroyed
                   and not s.is_disengaged
                   and s.status not in ("drifting_hulk", "burning_hulk")]
    if "fighter" in craft_roles(marker.ordnance_type):
        enemy_ord = [o for o in game_state.ordnance
                     if o["owner_player"] != marker.owner_player
                     and dist(o["x"], o["y"]) <= 2 * marker.speed]
        if enemy_ord:
            return min(enemy_ord, key=lambda o: dist(o["x"], o["y"]))["id"]
    if enemy_ships:
        return min(enemy_ships, key=lambda s: dist(s.x, s.y)).id
    return ""


def assign_ai_craft_targets(game_state: GameState, player: int) -> int:
    """Give each of the player's attack craft (not on CAP) a target for this
    ordnance phase. Returns how many were assigned."""
    n = 0
    for i, o in enumerate(game_state.ordnance):
        if (o["owner_player"] != player or o["ordnance_type"] not in ATTACK_CRAFT_TYPES
                or o.get("cap_ship_id")):
            continue
        m = OrdnanceMarker.from_dict(o)
        m.craft_target_id = ai_craft_target(m, game_state)
        game_state.ordnance[i] = m.to_dict()
        n += 1
    return n


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


def is_boarding_torpedo(marker: OrdnanceMarker) -> bool:
    return marker.ordnance_type == OrdnanceType.TORPEDO_BOARDING.value


def torpedo_valid_target(marker: OrdnanceMarker, ship: Ship) -> bool:
    """Ordnance attacks the first valid target it contacts (s.15). Any ship is a
    valid target for torpedoes (s.16: friend or foe), hulks included (a hulk
    that takes damage rolls catastrophic damage again, owner ruling). Boarding
    torpedoes always ignore friendly ships and may ignore hulks (s.16, Torpedo
    Types); here they always pass over hulks, where a raid would do nothing."""
    if not is_boarding_torpedo(marker):
        return True
    return (ship.player != marker.owner_player
            and ship.status not in ("drifting_hulk", "burning_hulk"))


BOARDING_TORP_MAX_TURN = 45.0


def boarding_torp_may_turn(marker: OrdnanceMarker, turn_number: int) -> bool:
    """Boarding torpedoes are manned and may turn up to 45° before moving, but
    not in the ordnance phase of the turn they were launched (s.16)."""
    return is_boarding_torpedo(marker) and marker.launched_turn < turn_number


def boarding_torp_suggested_turn(marker: OrdnanceMarker, ships: List[Ship]) -> float:
    """Signed turn (+ = anticlockwise) pointing the salvo as close as 45° allows
    at the nearest enemy ship that isn't a hulk; 0 if there is none."""
    enemies = [s for s in ships if s.player != marker.owner_player
               and not s.is_destroyed and not s.is_disengaged
               and s.status not in ("drifting_hulk", "burning_hulk")]
    if not enemies:
        return 0.0
    t = min(enemies, key=lambda s: math.hypot(s.x - marker.x, s.y - marker.y))
    desired = math.degrees(math.atan2(t.y - marker.y, t.x - marker.x)) % 360
    diff = signed_angle_diff(desired, marker.heading)
    return max(-BOARDING_TORP_MAX_TURN, min(BOARDING_TORP_MAX_TURN, diff))


def turn_boarding_torp(marker: OrdnanceMarker, degrees: float) -> None:
    """Rotate the salvo about its centre (clamped to 45°) before it moves."""
    degrees = max(-BOARDING_TORP_MAX_TURN, min(BOARDING_TORP_MAX_TURN, degrees))
    marker.heading = (marker.heading + degrees) % 360


def torpedo_in_launch_arc(marker: OrdnanceMarker, ship: Ship,
                          game_state: GameState) -> bool:
    """On the turn it is launched, a salvo cannot attack a target that is not
    in its firing arc (s.16): the arc of the launcher's torpedo weapon, seen
    from the launcher (which hasn't moved since it launched this turn)."""
    if marker.launched_turn != game_state.turn_number:
        return True
    launcher = game_state.get_ship_by_id(marker.launched_by)
    if launcher is None:
        return True
    arcs = next((w.get("arcs") for w in launcher.weapons
                 if w.get("weapon_type") == "torpedo"), None) or ["front"]
    return launcher.get_target_arc(ship.x, ship.y).value in arcs


def torpedo_may_attack(marker: OrdnanceMarker, ship: Ship,
                       game_state: GameState) -> bool:
    """A torpedo salvo touching this ship attacks it (s.15, s.16) unless it is
    not a valid target (torpedo_valid_target), it is outside the salvo's arc on
    its launch turn, or the salvo already attacked it this full turn (one
    player's turn and the other's: two turn numbers in this game)."""
    if not torpedo_valid_target(marker, ship):
        return False
    if not torpedo_in_launch_arc(marker, ship, game_state):
        return False
    last = (marker.attacked_turns or {}).get(ship.id)
    return last is None or game_state.turn_number - last >= 2


def resolve_torpedo_attack(marker: OrdnanceMarker, target: Ship,
                           dice: DiceRoller, game_state: GameState,
                           all_ships: List[Ship] = None,
                           brace_decision_fn=None) -> Dict:
    """Resolve torpedo attack. Bypasses shields. Turrets defend first.
    Turrets cannot fire if already used against attack craft this phase.

    Boarding torpedoes (core rules s.31): each hit is one hit-and-run raid
    instead of a point of damage. The target may brace before the raids are
    rolled: brace_decision_fn(target, msg, n_raids) -> (wanted, passed), as for
    assault boats; a ship already on Brace for Impact saves each raid on 4+.
    Without a callback an unbraced target does not brace."""
    result = {"hits": 0, "turret_kills": 0, "remaining_strength": marker.strength,
              "raids": None}

    # A hulk can no longer fight (s.34): no turret fire
    is_hulk = target.status in ("drifting_hulk", "burning_hulk")
    turrets = 0 if is_hulk else target.effective_turrets

    # Massed turrets: +1 per non-crippled friendly ship in base contact (max +3)
    if all_ships and not is_hulk:
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
    armor = target.armor_vs(marker.x, marker.y)

    attack_rolls = dice.roll_d6(
        result["remaining_strength"],
        f"Torpedoes vs {target.name} (need {armor}+)")
    result["hits"] = sum(1 for d in attack_rolls if d >= armor)

    # Torpedoes that scored hits are spent; the rest pass through and keep moving.
    result["remaining_strength"] = max(0, result["remaining_strength"] - result["hits"])

    if result["hits"] > 0 and is_boarding_torpedo(marker):
        game_state.add_log(
            f"Boarding torpedoes hit {target.name}: {result['hits']} hit-and-run "
            f"raid(s); {result['remaining_strength']} torp(s) pass through")
        result["raids"] = _boarding_torpedo_raids(
            marker, target, result["hits"], dice, game_state, brace_decision_fn)
    elif result["hits"] > 0:
        game_state.add_log(
            f"Torpedoes hit {target.name} for {result['hits']} damage (bypasses shields); "
            f"{result['remaining_strength']} torp(s) pass through")
        from .combat import apply_damage
        braced = target.special_order == SpecialOrder.BRACE_FOR_IMPACT.value
        apply_damage(target, result["hits"], dice, game_state,
                     ignores_shields=True, target_braced=braced,
                     attacker_key=marker.id)

    return result


def _boarding_torpedo_raids(marker: OrdnanceMarker, target: Ship, n_raids: int,
                            dice: DiceRoller, game_state: GameState,
                            brace_decision_fn) -> Dict:
    from .hit_and_run import resolve_raids
    target = game_state.get_ship_by_id(target.id) or target
    if target.special_order == SpecialOrder.BRACE_FOR_IMPACT.value:
        wanted, passed = True, True
        game_state.add_log(f"  {target.name} already braced — will roll to repel each raid")
    elif brace_decision_fn is not None:
        msg = (f"{target.name} is hit by {n_raids} boarding torpedo(es): "
               f"{n_raids} hit-and-run raid(s)!\n"
               f"Attempt Brace For Impact before the raids are rolled?\n"
               f"(A passed brace lets you roll 4+ to repel each raid)")
        wanted, passed = brace_decision_fn(target, msg, n_raids)
        target = game_state.get_ship_by_id(target.id) or target
    else:
        wanted, passed = False, False
    summary = resolve_raids(n_raids, target, passed, dice, game_state,
                            source_name="Boarding torpedo",
                            attacker_rules=marker.special_rules)
    summary["brace_wanted"] = wanted
    summary["brace_passed"] = passed
    return summary


def resolve_mine_contact(marker: OrdnanceMarker, ship: Ship,
                         dice: DiceRoller, game_state: GameState,
                         all_ships: List[Ship] = None) -> Dict:
    """
    Resolve a single mine detonating against a ship.

    Turret defense: roll the ship's effective turrets (plus massed turret bonus).
    - If ANY die scores 4+: mine attacks with 4D6 instead of 8D6.
    - Otherwise: mine attacks with 8D6.
    Mine damage ignores shields (core rules s.17; some rulebook printings say
    otherwise, which the booklet calls an error).
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
                "  Turrets reduce mine attack to 4D6")
        else:
            game_state.add_log(
                "  Turrets fail — mine attacks with 8D6")

    result["attack_dice"] = attack_dice

    # Bearing determines which armor face the mine hits
    armor = ship.armor_vs(marker.x, marker.y)

    attack_rolls = dice.roll_d6(attack_dice,
                                 f"Mine vs {ship.name} ({armor}+)")
    result["hits"] = sum(1 for r in attack_rolls if r >= armor)

    if result["hits"] > 0:
        from .combat import apply_damage
        braced = ship.special_order == SpecialOrder.BRACE_FOR_IMPACT.value
        apply_damage(ship, result["hits"], dice, game_state,
                     ignores_shields=True, target_braced=braced)
        game_state.add_log(
            f"  Mine: {result['hits']} hit(s) on {ship.name} (ignores shields)")

    return result


def resolve_bomber_interception(bomber_count: int,
                                 target: Ship,
                                 all_ships: List[Ship],
                                 dice: DiceRoller,
                                 game_state: GameState) -> Dict:
    """
    Phase 1 turret interception: the target ship (plus massed turret bonus from
    non-crippled allies in base contact) fires at an incoming wave of attacking
    craft (bombers and assault boats) before they attack (core rules s.28).

    Each turret rolls D6; 4+ kills one marker (capped at bomber_count).
    Massed turret bonus applies here (long-range interception).
    Sets turrets_used_vs='craft' on the target so torpedo defence is blocked.

    Returns {"killed": int, "log": [str]}
    """
    turrets = target.effective_turrets
    bonus = get_massed_turret_bonus(target, all_ships) if all_ships else 0
    turrets += bonus

    if turrets <= 0 or bomber_count <= 0:
        return {"killed": 0, "log": []}

    rolls = dice.roll_d6(
        turrets,
        f"Phase 1 interception: {target.name} vs {bomber_count} attack craft (4+)")
    kills = min(sum(1 for r in rolls if r >= 4), bomber_count)

    bonus_str = f" +{bonus} massed" if bonus else ""
    log = [
        f"  Phase 1 interception vs {target.name}: "
        f"{turrets} turrets{bonus_str}, "
        f"rolls {rolls} → {kills}/{bomber_count} attack craft destroyed"
    ]

    # Mark turrets as used vs craft this phase (blocks torpedo defence)
    target.turrets_used_vs = "craft"
    game_state.update_ship(target)

    return {"killed": kills, "log": log}


def resolve_bomber_attack(marker: OrdnanceMarker, target: Ship,
                          dice: DiceRoller, game_state: GameState,
                          suppressed_by_fighter: bool = False,
                          remastered_fighter_bonus: int = 0,
                          remastered_bomber_cap: int = 1) -> Dict:
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

    if marker.ordnance_type == OrdnanceType.FIGHTA_BOMMER.value:
        # Ork rules: Fighta-Bommerz make only D3+1 attacks per squadron, and
        # turrets cannot reduce them below 1 (Ork pilots always try to ram)
        target.turrets_used_vs = "craft"
        game_state.update_ship(target)
        roll = dice.roll_d3(f"Fighta-Bommerz attacks on {target.name} (D3+1)")
        total_attacks = max(1, roll + 1 - turret_reduction)
        result["turret_reduction"] = turret_reduction
        game_state.add_log(f"  Fighta-Bommerz: D3+1 = {roll + 1} - {turret_reduction} "
                           f"turrets = {total_attacks} attack(s) (minimum 1)")
    elif suppressed_by_fighter:
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
        armor = target.lowest_armor_value
        hit_rolls = dice.roll_d6(total_attacks, f"Bomber hits vs {target.name} ({armor}+)")
        result["hits"] = sum(1 for d in hit_rolls if d >= armor)

        if result["hits"] > 0:
            from .combat import apply_damage
            braced = target.special_order == SpecialOrder.BRACE_FOR_IMPACT.value
            apply_damage(target, result["hits"], dice, game_state,
                         ignores_shields=True, target_braced=braced,
                         attacker_key=marker.id)
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
                game_state.add_log("  Fighter passes resilient save, survives!")

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
                game_state.add_log("  Fighter passes resilient save!")

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
    """Check if an ordnance marker acts as a fighter (intercepts ordnance).

    Mantas are bombers (resilient), not fighters — they do not intercept.
    """
    return "fighter" in craft_roles(marker.ordnance_type)


def is_torpedo_salvo(marker: OrdnanceMarker) -> bool:
    """A torpedo marker (any torpedo type); torpedo bombers are attack craft."""
    return ("torpedo" in marker.ordnance_type
            and marker.ordnance_type != OrdnanceType.TORPEDO_BOMBER.value)


def friendly_ordnance_contact(m1: OrdnanceMarker, m2: OrdnanceMarker) -> Optional[str]:
    """What happens when two markers of the same player touch:
    "collide" (two torpedo salvos detonate, s.16), "intercept" (a fighter
    intercepts torpedoes, friend or foe, s.19), or None (no interaction).
    Bombers and assault boats avoid ordnance other than enemy fighters
    (s.20, s.22); mines ignore all ordnance except enemy fighters (s.17);
    boarding torpedoes ignore friendly attack craft (s.16)."""
    t1, t2 = is_torpedo_salvo(m1), is_torpedo_salvo(m2)
    if t1 and t2:
        return "collide"
    for f, t, t_is_torp in ((m1, m2, t2), (m2, m1, t1)):
        if is_fighter_type(f) and t_is_torp and not is_boarding_torpedo(t):
            return "intercept"
    return None


def resolve_ordnance_interactions(game_state: GameState,
                                   dice: DiceRoller) -> List[str]:
    """
    Resolve all ordnance-vs-ordnance interactions after movement.
    Fighters intercept enemy ordnance they contact (compulsory).
    Torpedo salvos that contact each other are both destroyed.
    Between friendly markers see friendly_ordnance_contact.
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

            same_player = (m1.owner_player == m2.owner_player)
            if same_player:
                kind = friendly_ordnance_contact(m1, m2)
                if kind is None or not check_ordnance_contact(m1, m2):
                    continue
                rm1, rm2 = True, True
                if kind == "intercept":
                    # A friendly fighter intercepts a torpedo salvo (s.19);
                    # a resilient fighter may save
                    fighter = m1 if is_fighter_type(m1) else m2
                    if fighter.resilient_save > 0 and not fighter.resilient_used:
                        save = dice.roll_d6(
                            1, f"Resilient save vs friendly torpedoes ({fighter.resilient_save}+)")[0]
                        if save >= fighter.resilient_save:
                            fighter.resilient_used = True
                            if fighter is m1:
                                rm1 = False
                            else:
                                rm2 = False
                logs.append(
                    f"  Friendly fire: {m1.ordnance_type} vs {m2.ordnance_type}")
                if rm1:
                    to_remove.add(m1.id)
                if rm2:
                    to_remove.add(m2.id)
                continue

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
                is_torp1 = is_torpedo_salvo(m1)
                is_torp2 = is_torpedo_salvo(m2)
                if is_torp1 and is_torp2:
                    to_remove.add(m1.id)
                    to_remove.add(m2.id)
                    logs.append(
                        "Torpedo salvos collide and detonate!")

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
    # Promethean Unguents: Thunderhawks move through blast markers without a roll
    if (marker.ordnance_type == OrdnanceType.THUNDERHAWK.value
            and "chapter_tactic:promethean_unguents" in (marker.special_rules or [])):
        return False
    for bm in blast_markers:
        dist = math.sqrt((marker.x - bm.x)**2 + (marker.y - bm.y)**2)
        if dist < 2.0:
            roll = dice.roll_d6(1, "Ordnance through blast marker (6=destroyed)")[0]
            return roll == 6
    return False


_TORP_LIKE = {
    OrdnanceType.TORPEDO_STANDARD.value,
    OrdnanceType.TORPEDO_BOARDING.value,
    OrdnanceType.TORPEDO_GUIDED.value,
    OrdnanceType.TORPEDO_BOARDING_GUIDED.value,
    OrdnanceType.MINE_FIELD.value,
}

_ATTACK_CRAFT = {
    OrdnanceType.FIGHTER.value,
    OrdnanceType.BOMBER.value,
    OrdnanceType.ASSAULT_BOAT.value,
    OrdnanceType.TORPEDO_BOMBER.value,
    OrdnanceType.MANTA.value,
    OrdnanceType.BARRACUDA.value,
    OrdnanceType.THUNDERHAWK.value,
    OrdnanceType.GUN_CUTTER.value,
    OrdnanceType.FIGHTA_BOMMER.value,
}

# Ordnance types that navigate around planets (no auto-destroy on planet contact).
# Attack craft and guided boarding torps qualify; standard torps and mines do not.
_PLANET_IMMUNE = _ATTACK_CRAFT | {
    OrdnanceType.TORPEDO_BOARDING_GUIDED.value,
}


def check_ordnance_vs_phenomena(marker: OrdnanceMarker,
                                 phenomena,
                                 dice: DiceRoller) -> Tuple[bool, str]:
    """
    Check if ordnance is destroyed by terrain phenomena.

    Standard torpedoes / mines:
        asteroid fields, planets, warp rifts = auto-destroyed
        gas/dust cloud = D6=6 destroys
    Guided boarding torpedoes:
        asteroid fields, warp rifts = auto-destroyed
        planets = no effect (navigate around)
        gas/dust cloud = D6=6 destroys
    Attack craft (fighters, bombers, assault boats, Manta, Barracuda, torpedo bombers):
        asteroid field = D6=6 destroys
        warp rift = auto-destroyed
        planets = no effect
        gas/dust cloud = no effect

    Returns (destroyed: bool, reason: str).
    """
    is_torp = marker.ordnance_type in _TORP_LIKE
    is_craft = marker.ordnance_type in _ATTACK_CRAFT
    if not is_torp and not is_craft:
        return False, ""

    planet_immune = marker.ordnance_type in _PLANET_IMMUNE

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
                roll = dice.roll_d6(1, "Attack craft in asteroid field (6=destroyed)")[0]
                if roll == 6:
                    return True, "asteroid_field"
            elif ptype == "warp_rift":
                return True, ptype
            # Planets and gas/dust clouds have no effect on attack craft
        else:
            # Torpedoes and mines
            if "planet" in ptype:
                if not planet_immune:
                    return True, ptype
                # guided boarding torps navigate around planets
            elif ptype in ("asteroid_field", "warp_rift"):
                return True, ptype
            elif ptype == "gas_dust_cloud":
                roll = dice.roll_d6(1, "Ordnance through dust cloud (6=destroyed)")[0]
                if roll == 6:
                    return True, "gas_dust_cloud"

    return False, ""


def compute_torpedo_launch_exempt(launcher: Ship,
                                   game_state: GameState) -> List[str]:
    """Return ship IDs immune to friendly fire from torpedoes launched by `launcher`.

    Only the launcher itself is exempt for individual launches.  For combined
    squadron ordnance, the caller passes the full combining-group IDs directly
    as launch_exempt_ships on the created OrdnanceMarker.
    """
    return [launcher.id]


def reload_ship_ordnance(ship: Ship) -> List[str]:
    """Reload a ship's ordnance (Reload Ordnance order effect).

    Sets ordnance_loaded_torps True if the ship has torpedo weapons;
    sets ordnance_loaded_craft True if it has launch bay weapons.
    Returns log lines describing what was reloaded. Mutates `ship` in place;
    the caller is responsible for persisting via gs.update_ship.
    """
    has_torps = any(w.get("weapon_type") == "torpedo" for w in ship.weapons)
    has_bays = any(w.get("weapon_type") == "launch_bay" for w in ship.weapons)
    has_mines = any(w.get("weapon_type") == "mine_launcher" for w in ship.weapons)
    reloaded = []
    if has_torps and not ship.ordnance_loaded_torps:
        ship.ordnance_loaded_torps = True
        reloaded.append("torpedoes")
    if has_bays and not ship.ordnance_loaded_craft:
        ship.ordnance_loaded_craft = True
        reloaded.append("attack craft")
    if has_mines and not ship.ordnance_loaded_mines:
        ship.ordnance_loaded_mines = True
        reloaded.append("mines")
    if reloaded:
        return [f"{ship.name}: Reload Ordnance — reloaded {' & '.join(reloaded)}"]
    if has_torps or has_bays or has_mines:
        return [f"{ship.name}: Reload Ordnance — ordnance already loaded"]
    return []



def torpedo_split_error(total: int, first: int, heading1: float,
                        heading2: Optional[float]) -> Optional[str]:
    """Splitting Torpedo Salvos (s.16): a single ship firing strength 7 or more
    may split into two salvos going in different directions, neither with fewer
    than three torpedoes. Returns an error message, or None if allowed.
    first == total means no split."""
    if first == total:
        return None
    if total < 7:
        return f"Only salvos of strength 7 or more can be split (this is {total})."
    if first < 3 or total - first < 3:
        return (f"Each salvo needs at least 3 torpedoes "
                f"(Str {first} + {total - first}).")
    if heading2 is None or abs(signed_angle_diff(heading1, heading2)) < 0.5:
        return "The two salvos must go in different directions."
    return None


def torpedo_launch_strength(ship: Ship, weapon: Dict,
                            dice: Optional[DiceRoller] = None) -> Tuple[int, Optional[int]]:
    """Strength of a salvo launched now: (strength, rolled). A random strength
    (strength_dice, e.g. Ork Torps S D6) is rolled just before launching (owner
    ruling); then it is halved (rounding up) if the ship is crippled, and again
    if it is braced, as for any ordnance (s.15)."""
    rolled = None
    if weapon.get("strength_dice") and dice is not None:
        from .combat import roll_dice_value
        rolled = roll_dice_value(weapon["strength_dice"], dice,
                                 f"{ship.name} {weapon['name']} strength")
        strength = rolled
    else:
        strength = weapon["strength"]
    if ship.is_crippled:
        strength = (strength + 1) // 2
    if ship.special_order == SpecialOrder.BRACE_FOR_IMPACT.value:
        strength = (strength + 1) // 2
    return strength, rolled


def boarding_ok(weapon: Dict, boarding: bool) -> bool:
    """Boarding torpedoes only from launchers that carry them."""
    return bool(boarding and weapon.get("boarding_torpedoes")
                and weapon.get("torpedo_type", "standard") != "guided")


def torpedo_ordnance_type(weapon: Dict, boarding: bool = False) -> str:
    if weapon.get("torpedo_type") == "guided":
        return OrdnanceType.TORPEDO_GUIDED.value
    if boarding_ok(weapon, boarding):
        return OrdnanceType.TORPEDO_BOARDING.value
    return OrdnanceType.TORPEDO_STANDARD.value


def launch_torpedoes(ship: Ship, weapon: Dict, game_state: GameState,
                     heading: Optional[float] = None,
                     boarding: bool = False,
                     dice: Optional[DiceRoller] = None) -> OrdnanceMarker:
    """Create a torpedo marker from a ship's launcher.

    `heading` lets the caller aim the salvo (e.g. an AI leading a target).
    It is clamped to ±45° of the ship's heading — the same forward-arc
    constraint the human launch dialog enforces. Defaults to ship heading.
    """
    torpedo_type = weapon.get("torpedo_type", "standard")
    o_type = torpedo_ordnance_type(weapon, boarding)
    strength, rolled = torpedo_launch_strength(ship, weapon, dice)
    if rolled is not None:
        game_state.add_log(f"{ship.name} {weapon['name']}: rolled "
                           f"{weapon['strength_dice']} = {rolled}")

    if heading is None:
        launch_heading = ship.heading
    else:
        diff = signed_angle_diff(heading, ship.heading)
        diff = max(-45.0, min(45.0, diff))
        launch_heading = (ship.heading + diff) % 360

    marker = OrdnanceMarker(
        id=f"torp_{ship.id}_{game_state.turn_number}_{_uuid.uuid4().hex[:6]}",
        ordnance_type=o_type, owner_player=ship.player,
        launched_by=ship.id, x=ship.x, y=ship.y,
        heading=launch_heading, strength=strength,
        speed=weapon.get("torpedo_speed", TORPEDO_SPEED_DEFAULT),
        launched_turn=game_state.turn_number,
        can_turn=(torpedo_type == "guided"),
        turn_angle=45 if torpedo_type == "guided" else 0,
        launch_exempt_ships=compute_torpedo_launch_exempt(ship, game_state),
        # The launcher's raid bonuses go with its boarding torps (s.31)
        special_rules=list(ship.special_rules),
    )
    game_state.add_ordnance(marker)
    ship.ordnance_loaded_torps = False
    game_state.update_ship(ship)
    kind = "boarding torpedo" if boarding_ok(weapon, boarding) else "torpedo"
    game_state.add_log(f"{ship.name} launches {kind} salvo (Str {strength})")
    return marker


# Craft type -> (ordnance type, default speed, resilient save)
CRAFT_STATS = {
    "manta": (OrdnanceType.MANTA.value, 20, 4),
    "barracuda": (OrdnanceType.BARRACUDA.value, 25, 0),
    "fury_fighter": (OrdnanceType.FIGHTER.value, 30, 0),
    "starhawk_bomber": (OrdnanceType.BOMBER.value, 20, 0),
    "shark_assault_boat": (OrdnanceType.ASSAULT_BOAT.value, 30, 0),
    # Generic attack craft (factions whose rules don't name them)
    "fighter": (OrdnanceType.FIGHTER.value, 30, 0),
    "bomber": (OrdnanceType.BOMBER.value, 20, 0),
    "assault_boat": (OrdnanceType.ASSAULT_BOAT.value, 30, 0),
    # Multi-role craft (s.24)
    "thunderhawk": (OrdnanceType.THUNDERHAWK.value, 20, 4),
    "gun_cutter": (OrdnanceType.GUN_CUTTER.value, 20, 4),
    "fighta_bommer": (OrdnanceType.FIGHTA_BOMMER.value, 25, 0),
}

# What each attack craft type can act as. Multi-role craft follow the rules of
# every role they have (s.24): Thunderhawks fighter/bomber/assault boat (Space
# Marine rules), Gun-Cutters fighter + assault boat (Inquisition rules),
# Fighta-Bommerz fighter + bomber (Ork rules: "multi-role", D3+1 attacks).
CRAFT_ROLES = {
    OrdnanceType.FIGHTER.value: ("fighter",),
    OrdnanceType.BARRACUDA.value: ("fighter",),
    OrdnanceType.BOMBER.value: ("bomber",),
    OrdnanceType.MANTA.value: ("bomber",),
    OrdnanceType.ASSAULT_BOAT.value: ("assault_boat",),
    OrdnanceType.THUNDERHAWK.value: ("fighter", "bomber", "assault_boat"),
    OrdnanceType.GUN_CUTTER.value: ("fighter", "assault_boat"),
    OrdnanceType.FIGHTA_BOMMER.value: ("fighter", "bomber"),
}
MULTI_ROLE_TYPES = {t for t, r in CRAFT_ROLES.items() if len(r) > 1}
ATTACK_CRAFT_TYPES = set(CRAFT_ROLES) | {OrdnanceType.TORPEDO_BOMBER.value}


def craft_roles(ordnance_type: str) -> Tuple[str, ...]:
    return CRAFT_ROLES.get(ordnance_type, ())


def attacks_ships(ordnance_type: str) -> bool:
    """Attack craft that must attack enemy ships they contact: bombers and
    assault boats, including multi-role craft with either role (s.24)."""
    roles = craft_roles(ordnance_type)
    return "bomber" in roles or "assault_boat" in roles


def craft_stats(craft_type: str, bay_weapons: List[Dict]) -> Tuple[str, float, int]:
    """(ordnance type, speed, resilient save) for a craft type. The carrier's
    profile gives the speed of each craft it carries (booklet data)."""
    o_type, speed, resilient = CRAFT_STATS.get(
        craft_type, (OrdnanceType.FIGHTER.value, 30, 0))
    for w in bay_weapons:
        if craft_type in (w.get("craft_speeds") or {}):
            speed = w["craft_speeds"][craft_type]
            break
    return o_type, speed, resilient


def bay_launch_capacity(ship: Ship, bay_weapons: List[Dict],
                        dice: Optional[DiceRoller] = None) -> Tuple[int, List[str]]:
    """Squadrons this ship may launch now: one per launch bay (s.18). Random bay
    strengths (strength_dice, e.g. Ork D3+1) are rolled just before launching
    (owner ruling); then halved (rounding up) if crippled, and again if braced
    (s.15). Returns (capacity, log lines)."""
    from .combat import roll_dice_value
    total, log = 0, []
    for w in bay_weapons:
        if w.get("strength_dice") and dice is not None:
            n = roll_dice_value(w["strength_dice"], dice, f"{ship.name} {w['name']}")
            log.append(f"{ship.name} {w['name']}: rolled {w['strength_dice']} = {n}")
            total += n
        else:
            total += w.get("strength", 0)
    if ship.is_crippled:
        total = (total + 1) // 2
    if ship.special_order == SpecialOrder.BRACE_FOR_IMPACT.value:
        total = (total + 1) // 2
    return total, log


def fleet_craft_slots(game_state: GameState, player: int) -> int:
    """Attack craft markers the player may still put in play: launch bays
    remaining in the fleet (random bays count their maximum) minus markers
    already in play (s.15)."""
    bays = sum(w.get("strength", 0)
               for s in game_state.player_ships(player)
               if not s.is_destroyed and not s.is_disengaged
               for w in s.weapons if w.get("weapon_type") == "launch_bay")
    in_play = sum(1 for o in game_state.ordnance
                  if o.get("owner_player") == player
                  and o.get("ordnance_type") in ATTACK_CRAFT_TYPES)
    return max(0, bays - in_play)


def fleet_craft_excess(game_state: GameState, player: int) -> int:
    """Attack craft markers in play beyond the fleet's remaining launch bays
    (after critical damage or lost ships). The owner must remove that many the
    next time a new squadron is launched (s.15)."""
    bays = sum(w.get("strength", 0)
               for s in game_state.player_ships(player)
               if not s.is_destroyed and not s.is_disengaged
               for w in s.weapons if w.get("weapon_type") == "launch_bay")
    in_play = sum(1 for o in game_state.ordnance
                  if o.get("owner_player") == player
                  and o.get("ordnance_type") in ATTACK_CRAFT_TYPES)
    return max(0, in_play - bays)


def recall_craft(game_state: GameState, player: int, marker_ids: List[str]) -> int:
    """Remove the player's own attack craft squadrons from play (recalling them
    frees launch capacity, s.15). Returns how many were removed."""
    ids = set(marker_ids)
    keep = [o for o in game_state.ordnance
            if not (o["id"] in ids and o.get("owner_player") == player
                    and o.get("ordnance_type") in ATTACK_CRAFT_TYPES)]
    n = len(game_state.ordnance) - len(keep)
    game_state.ordnance = keep
    if n:
        game_state.add_log(f"Player {player} recalls {n} attack craft squadron(s)")
    return n


def ai_craft_to_recall(game_state: GameState, player: int, n: int) -> List[str]:
    """The AI recalls its oldest squadrons first, keeping combat air patrols."""
    own = [o for o in game_state.ordnance
           if o.get("owner_player") == player and o.get("ordnance_type") in ATTACK_CRAFT_TYPES]
    own.sort(key=lambda o: (bool(o.get("cap_ship_id")), o.get("launched_turn", 0)))
    return [o["id"] for o in own[:n]]


def mr_attack_mode_ai(target: Ship) -> str:
    """AI choice for craft that can attack as bombers or assault boats (s.24):
    raid ships whose turrets would cut bomber attacks down."""
    return "assault_boat" if target.effective_turrets >= 3 else "bomber"


def launch_attack_craft(ship: Ship, weapon: Dict, craft_type: str,
                        count: int, game_state: GameState) -> List[OrdnanceMarker]:
    """Create attack craft markers from launch bays."""
    o_type, speed, resilient = craft_stats(craft_type, [weapon])

    markers = []
    for i in range(count):
        marker = OrdnanceMarker(
            id=f"craft_{ship.id}_{craft_type}_{i}_{game_state.turn_number}",
            ordnance_type=o_type, owner_player=ship.player,
            launched_by=ship.id, x=ship.x, y=ship.y,
            heading=ship.heading, speed=speed,
            launched_turn=game_state.turn_number,
            resilient_save=resilient,
            special_rules=list(ship.special_rules),
        )
        markers.append(marker)
        game_state.add_ordnance(marker)

    ship.ordnance_loaded_craft = False
    game_state.update_ship(ship)
    game_state.add_log(f"{ship.name} launches {count}x {craft_type}")
    return markers
