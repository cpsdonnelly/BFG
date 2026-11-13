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
        # AI craft fly round asteroid fields, warp rifts and blast markers when
        # a detour is worth more (owner; ai_hazards.best_route); a human's craft
        # go straight at the target they were given
        ai = getattr(game_state, "ai_player", None)
        if (ai is not None and marker.owner_player == ai
                and marker.ordnance_type in ATTACK_CRAFT_TYPES):
            from .ai_hazards import best_route
            route = best_route(marker.x, marker.y, ship.x, ship.y, game_state, "craft",
                               marker.speed or 20)
            if route[3] is not None and math.hypot(route[3][0] - marker.x,
                                                   route[3][1] - marker.y) > 1.0:
                return route[3]
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
    most threatening enemy ordnance within two moves (ai_hazards.marker_threat_vp,
    nearest on a tie); craft that attack ships go for the
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
            # the most dangerous first (a mine before a small salvo), then the nearest
            from .ai_hazards import marker_threat_vp
            return max(enemy_ord, key=lambda o: (
                marker_threat_vp(OrdnanceMarker.from_dict(o), game_state, marker.owner_player),
                -dist(o["x"], o["y"])))["id"]
    if enemy_ships:
        return min(enemy_ships, key=lambda s: dist(s.x, s.y)).id
    return ""


def plan_fighter_intercepts(game_state: GameState, player: int) -> Dict[str, str]:
    """Owner guidance: do the most good with the fighters. A fighter removes
    one marker it meets: a whole torpedo salvo, one mine, or one squadron of a
    wave (lead first). Greedy across the fleet: take the fighter / target pair
    that saves the most VP (ai_hazards.intercept_gain; half for a target only
    reachable next phase), then update what's covered (a mine or salvo needs one
    fighter; each further fighter on a wave meets its next squadron), repeat.
    Returns {fighter id: target id}."""
    from .ai_hazards import intercept_gain
    fighters = [OrdnanceMarker.from_dict(o) for o in game_state.ordnance
                if o["owner_player"] == player and o["ordnance_type"] in ATTACK_CRAFT_TYPES
                and not o.get("cap_ship_id") and "fighter" in craft_roles(o["ordnance_type"])]
    enemies = [OrdnanceMarker.from_dict(o) for o in game_state.ordnance
               if o["owner_player"] != player and not o.get("cap_ship_id")
               and o["ordnance_type"] != "mine_field"]
    # a wave is one target (its lead); lone markers are their own
    targets = {}
    for e in enemies:
        targets.setdefault(e.wave_id or e.id, e)
    taken: Dict[str, int] = {}
    plan: Dict[str, str] = {}
    free = list(fighters)
    while free:
        best = None
        for f in free:
            for key, t in targets.items():
                d = math.hypot(t.x - f.x, t.y - f.y)
                if d > 2 * (f.speed or 0):
                    continue
                gain = intercept_gain(game_state, player, t, taken.get(key, 0))
                if d > (f.speed or 0):
                    gain *= 0.5                    # only next phase
                if gain > 0 and (best is None or (gain, -d) > (best[0], -best[3])):
                    best = (gain, f, key, d)
        if best is None:
            break
        _, f, key, _ = best
        plan[f.id] = targets[key].id
        taken[key] = taken.get(key, 0) + 1
        free.remove(f)
    return plan


def plan_has_run(plan: Dict[str, str], game_state: GameState, player: int) -> bool:
    """True when the fighter plan considered some enemy ordnance (so a fighter
    left out of it has nothing useful in reach)."""
    return bool(plan) or not any(o["owner_player"] != player for o in game_state.ordnance)


def assign_ai_craft_targets(game_state: GameState, player: int) -> int:
    """Give each of the player's attack craft (not on CAP) a target for this
    ordnance phase: fighters by plan_fighter_intercepts, the rest (and spare
    fighters) by ai_craft_target. Returns how many were assigned."""
    plan = plan_fighter_intercepts(game_state, player)
    # Bombers / assault boats (and the fighters in their waves): by expected VP
    # with focus, fleet-wide (ai_hazards.plan_strike_targets)
    from .ai_hazards import plan_strike_targets
    strikes = plan_strike_targets(game_state, player)
    n = 0
    for i, o in enumerate(game_state.ordnance):
        if (o["owner_player"] != player or o["ordnance_type"] not in ATTACK_CRAFT_TYPES
                or o.get("cap_ship_id")):
            continue
        m = OrdnanceMarker.from_dict(o)
        if m.id in strikes and (m.wave_id or attacks_ships(m.ordnance_type)):
            m.craft_target_id = strikes[m.id]
        elif m.id in plan:
            m.craft_target_id = plan[m.id]
        elif "fighter" in craft_roles(m.ordnance_type) and plan_has_run(plan, game_state, player):
            # a spare fighter: everything in reach is already covered, so it
            # doesn't double up; it advances on the nearest enemy ship
            ships = [x for x in game_state.get_ships() if x.player != player
                     and not x.is_destroyed and not x.is_disengaged
                     and x.status not in ("drifting_hulk", "burning_hulk")]
            m.craft_target_id = (min(ships, key=lambda x: math.hypot(x.x - m.x, x.y - m.y)).id
                                 if ships else "")
        else:
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
    pool = list(all_ships) + ([] if any(a.id == ship.id for a in all_ships) else [ship])
    for ally in pool:
        # Fleet Defence Turrets (Mechanicus Gift): +1 to every friendly ship
        # within 15cm, itself included
        # A crippled ship can't contribute massed turrets, so a crippled Fleet
        # Defence Turrets ship gives no +1, not even to itself (owner ruling)
        if ("fleet_defence_turrets" in ally.special_rules and ally.player == ship.player
                and not (ally.is_destroyed or ally.is_disengaged or ally.is_crippled)
                and ally.status not in ("drifting_hulk", "burning_hulk")
                and math.hypot(ally.x - ship.x, ally.y - ship.y)
                - ally.base_radius - ship.base_radius <= 15.0):
            bonus += 1
        if ally.id == ship.id:
            continue
        if ally.player != ship.player:
            continue
        if ally.is_destroyed or ally.is_disengaged or ally.is_crippled:
            continue
        dist = math.sqrt((ally.x - ship.x)**2 + (ally.y - ship.y)**2)
        if dist <= ally.base_radius + ship.base_radius + BASE_CONTACT_MARGIN_CM:
            bonus += 1
    return min(3, bonus)


def check_torpedo_contact(marker: OrdnanceMarker, ship: Ship) -> bool:
    """Check if a torpedo marker contacts a ship's base."""
    return circle_touches_torpedo(ship.x, ship.y, ship.base_radius,
                                   marker.x, marker.y, marker.heading)


def is_boarding_torpedo(marker: OrdnanceMarker) -> bool:
    return marker.ordnance_type == OrdnanceType.TORPEDO_BOARDING.value


def ignores_friendly(marker: OrdnanceMarker) -> bool:
    """Boarding and seeking torpedoes ignore friendly ships and attack craft (s.16)."""
    return marker.ordnance_type in (OrdnanceType.TORPEDO_BOARDING.value,
                                    OrdnanceType.TORPEDO_SEEKING.value)


def torpedo_valid_target(marker: OrdnanceMarker, ship: Ship) -> bool:
    """Ordnance attacks the first valid target it contacts (s.15). Any ship is a
    valid target for torpedoes (s.16: friend or foe), hulks included (a hulk
    that takes damage rolls catastrophic damage again, owner ruling). Boarding
    torpedoes always ignore friendly ships and may ignore hulks (s.16, Torpedo
    Types); here they always pass over hulks, where a raid would do nothing."""
    if marker.ordnance_type == OrdnanceType.TORPEDO_SEEKING.value:
        return ship.player != marker.owner_player
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


def seeking_turn(marker: OrdnanceMarker, ships: List[Ship]) -> float:
    """Seeking torpedoes (s.16) must turn up to 45° before moving, in each
    ordnance phase after launch, to point as close as possible at the nearest
    enemy ship (the largest, if several are equally near). Returns the turn."""
    enemies = [s for s in ships if s.player != marker.owner_player
               and not s.is_destroyed and not s.is_disengaged
               and s.status not in ("drifting_hulk", "burning_hulk")]
    if not enemies:
        return 0.0
    size = {"escort": 0, "cruiser": 1, "battleship": 2}
    dist = {s.id: math.hypot(s.x - marker.x, s.y - marker.y) for s in enemies}
    near = min(dist.values())
    t = max((s for s in enemies if dist[s.id] - near < 1e-6),
            key=lambda s: (size.get(s.ship_type, 1), s.hits_max))
    desired = math.degrees(math.atan2(t.y - marker.y, t.x - marker.x)) % 360
    diff = signed_angle_diff(desired, marker.heading)
    return max(-BOARDING_TORP_MAX_TURN, min(BOARDING_TORP_MAX_TURN, diff))


def guided_control(marker: OrdnanceMarker, game_state: GameState, dice: DiceRoller,
                   reroll_fn=None, choose_enemy_fn=None) -> Tuple[Optional[int], List[str]]:
    """Guided torpedoes (s.16) may turn up to 45° before moving (not in the
    ordnance phase of their launch), only if the launching ship first passes a
    Leadership test; a launching ship no longer in play can't, so the salvo
    doesn't turn. If it fails, one enemy ship, chosen by the enemy player, may
    try to take control with a Leadership test of its own; if it passes, its
    owner turns them.

    reroll_fn(player, ship, roll) -> bool: whether that player spends a fleet
    commander re-roll on a failed test (None: no re-rolls). choose_enemy_fn(
    enemy player, candidate ships) -> ship or None (None: no attempt);
    without one, the enemy ship with the best Leadership tries.
    Returns (player who turns the salvo or None, log lines)."""
    logs = []
    if marker.launched_turn >= game_state.turn_number:
        return None, logs
    launcher = game_state.get_ship_by_id(marker.launched_by)
    if launcher is None or launcher.is_destroyed or launcher.is_disengaged:
        logs.append("  Guided torpedoes: the launching ship is gone; they can't turn")
        return None, logs

    def test(ship, label):
        roll = dice.roll_2d6(f"{ship.name} {label} (Ld {ship.leadership})")
        if roll > ship.leadership and reroll_fn is not None and reroll_fn(ship.player, ship, roll):
            logs.append(f"  {ship.name} rolled {roll}: fleet re-roll")
            roll = dice.roll_2d6(f"{ship.name} {label} re-roll (Ld {ship.leadership})")
        return roll

    roll = test(launcher, "guides torpedoes")
    if roll <= launcher.leadership:
        logs.append(f"  {launcher.name} guides its torpedoes (rolled {roll})")
        return marker.owner_player, logs
    logs.append(f"  {launcher.name} fails to guide its torpedoes (rolled {roll})")
    enemies = [s for s in game_state.get_ships() if s.player != marker.owner_player
               and not s.is_destroyed and not s.is_disengaged
               and s.status not in ("drifting_hulk", "burning_hulk")]
    if not enemies:
        return None, logs
    enemy_player = enemies[0].player
    if choose_enemy_fn is not None:
        e = choose_enemy_fn(enemy_player, enemies)
        if e is None:
            logs.append("  The enemy doesn't try to take control")
            return None, logs
    else:
        e = max(enemies, key=lambda s: s.leadership)
    roll = test(e, "tries to take control")
    if roll <= e.leadership:
        logs.append(f"  {e.name} takes control of the torpedoes (rolled {roll})")
        return e.player, logs
    logs.append(f"  {e.name} fails to take control (rolled {roll})")
    return None, logs


def guided_suggested_turn(marker: OrdnanceMarker, ships: List[Ship], controller: int) -> float:
    """The turn a controller would like: at the nearest ship of the controller's
    enemy (for the owner, an enemy ship; for an enemy who took control, one of
    the owner's ships)."""
    targets = [s for s in ships if s.player != controller
               and not s.is_destroyed and not s.is_disengaged
               and s.status not in ("drifting_hulk", "burning_hulk")]
    if not targets:
        return 0.0
    t = min(targets, key=lambda s: math.hypot(s.x - marker.x, s.y - marker.y))
    desired = math.degrees(math.atan2(t.y - marker.y, t.x - marker.x)) % 360
    diff = signed_angle_diff(desired, marker.heading)
    return max(-BOARDING_TORP_MAX_TURN, min(BOARDING_TORP_MAX_TURN, diff))


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


def turret_hit_on(ship: Ship) -> int:
    """Turrets hit ordnance on 4+ (s.28); Ork turrets on 5+ (Xenos, Turret Defences)."""
    return 5 if "ork_turrets" in ship.special_rules else 4


def turrets_blocked(ship: Ship, kind: str) -> bool:
    """s.28: a ship that uses its turrets against attack craft ("craft") may not
    use them against torpedoes or mines ("torp") in the same phase, and vice
    versa. Ork ships always use their turrets against all ordnance."""
    if "ork_turrets" in ship.special_rules:
        return False
    return bool(ship.turrets_used_vs) and ship.turrets_used_vs != kind


def mark_turrets_used(ship: Ship, kind: str, game_state: GameState) -> None:
    if not ship.turrets_used_vs:
        ship.turrets_used_vs = kind
        game_state.update_ship(ship)


def choose_turret_target(ship: Ship, craft: List[OrdnanceMarker],
                         torps: List[OrdnanceMarker], game_state: GameState,
                         ai: bool = True) -> str:
    """Attack craft and torpedoes / mines touch the ship in one phase (s.28):
    "craft" or "torp". A human owner is asked (GameState.turret_choice_hook);
    the AI takes whichever saves more expected hits."""
    hook = getattr(game_state, "turret_choice_hook", None)
    if not ai and hook is not None:
        choice = hook(ship, craft, torps)
        if choice in ("craft", "torp"):
            return choice
    t = ordnance_turrets(ship, game_state)
    p = (7 - turret_hit_on(ship)) / 6.0
    ph = max(1, 7 - ship.lowest_armor_value) / 6.0
    # Turrets fire their full value at each wave / lone squadron, salvo and mine
    groups: Dict[str, int] = {}
    for m in craft:
        groups[m.wave_id or m.id] = groups.get(m.wave_id or m.id, 0) + 1
    # hits a bomber squadron would do: D6 attacks less one per turret
    per_sq = sum(max(0, k - ship.effective_turrets) for k in range(1, 7)) / 6.0 * ph
    vs_craft = sum(min(n, t * p) * per_sq for n in groups.values())
    vs_torp = 0.0
    for m in torps:
        if "mine" in m.ordnance_type:             # any success: 4D6 instead of 8D6
            vs_torp += (1 - (1 - p) ** t) * 4 * ph
        else:                                     # each success: one torpedo fewer
            vs_torp += min(m.strength, t * p) * ph
    return "craft" if vs_craft >= vs_torp else "torp"


def ordnance_turrets(target: Ship, game_state: GameState) -> int:
    """Turrets a ship fires at ordnance: halved (rounding up) for the next
    ordnance attack after Promethean Unguents barrage bombs hit it this turn."""
    t = target.effective_turrets
    if t and target.turrets_halved_turn == game_state.turn_number:
        t = (t + 1) // 2
    return t


def end_ordnance_attack(target: Ship, game_state: GameState) -> None:
    """An ordnance attack has been resolved: Promethean turret halving is used up."""
    if target.turrets_halved_turn == game_state.turn_number:
        fresh = game_state.get_ship_by_id(target.id) or target
        fresh.turrets_halved_turn = target.turrets_halved_turn = -1
        game_state.update_ship(fresh)


def promethean_barrage(marker: OrdnanceMarker) -> bool:
    return (marker.ordnance_type == OrdnanceType.TORPEDO_BARRAGE.value
            and "chapter_tactic:promethean_unguents" in (marker.special_rules or []))


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
    turrets = 0 if is_hulk else ordnance_turrets(target, game_state)

    # Massed turrets: +1 per non-crippled friendly ship in base contact (max +3)
    if all_ships and not is_hulk:
        bonus = get_massed_turret_bonus(target, all_ships)
        if bonus > 0:
            turrets += bonus
            game_state.add_log(
                f"  {target.name} massed turrets: +{bonus} "
                f"(total {turrets})")

    # s.28: turrets used against attack craft this phase can't fire at torpedoes
    if turrets > 0 and turrets_blocked(target, "torp"):
        game_state.add_log(f"  {target.name} turrets already used vs attack craft this phase")
        turrets = 0

    if turrets > 0:
        need = turret_hit_on(target)
        turret_rolls = dice.roll_d6(turrets, f"{target.name} turrets vs torpedoes ({need}+)")
        turret_kills = sum(1 for d in turret_rolls if d >= need)
        result["turret_kills"] = turret_kills
        result["remaining_strength"] = max(0, marker.strength - turret_kills)
        game_state.add_log(f"{target.name} turrets destroy {turret_kills} torpedoes")
        mark_turrets_used(target, "torp", game_state)

    end_ordnance_attack(target, game_state)
    if result["remaining_strength"] <= 0:
        return result

    # Determine armor facing (Promethean Unguents barrage bombs always hit on 4+)
    promethean = promethean_barrage(marker)
    armor = 4 if promethean else target.armor_vs(marker.x, marker.y)

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
    elif result["hits"] > 0 and promethean:
        # Promethean Unguents (Salamanders): no damage; a blast marker per hit,
        # fanned out like shield impacts, and half turrets vs the next ordnance
        # attack on it this turn
        from .combat import _place_shield_impacts
        game_state.add_log(
            f"Promethean barrage bombs hit {target.name} {result['hits']} time(s): "
            f"{result['hits']} blast marker(s), turrets halved for the next ordnance "
            f"attack this turn; {result['remaining_strength']} pass through")
        _place_shield_impacts(target, result["hits"], game_state, (marker.x, marker.y))
        fresh = game_state.get_ship_by_id(target.id) or target
        fresh.turrets_halved_turn = target.turrets_halved_turn = game_state.turn_number
        game_state.update_ship(fresh)
    elif result["hits"] > 0 and marker.ordnance_type == OrdnanceType.TORPEDO_MELTA.value:
        # Melta: no damage; each hit is an automatic Fire critical hit, even on
        # ships whose critical hit table has no Fire result. A hulk takes no damage.
        game_state.add_log(f"Melta torpedoes hit {target.name} {result['hits']} time(s): "
                           f"{result['hits']} Fire critical hit(s), no damage; "
                           f"{result['remaining_strength']} pass through")
        if not is_hulk:
            from .combat import add_fire_crits
            add_fire_crits(target, result["hits"], game_state)
        elif target.status == "drifting_hulk":
            # Owner ruling: a hulk hit by a melta salvo becomes a burning hulk
            fresh = game_state.get_ship_by_id(target.id) or target
            fresh.status = target.status = "burning_hulk"
            game_state.update_ship(fresh)
            game_state.add_log(f"  {target.name} (hulk) is set ablaze: now a burning hulk")
    elif result["hits"] > 0 and marker.ordnance_type == OrdnanceType.TORPEDO_VORTEX.value:
        game_state.add_log(f"Vortex torpedoes hit {target.name} {result['hits']} time(s): "
                           f"1 damage and an automatic critical hit each; "
                           f"{result['remaining_strength']} pass through")
        from .combat import apply_damage
        braced = target.special_order == SpecialOrder.BRACE_FOR_IMPACT.value
        apply_damage(target, result["hits"], dice, game_state,
                     ignores_shields=True, target_braced=braced,
                     attacker_key=marker.id, auto_crit=True)
    elif result["hits"] > 0 and marker.ordnance_type == OrdnanceType.TORPEDO_BARRAGE.value:
        game_state.add_log(
            f"Barrage bombs hit {target.name} {result['hits']} time(s) (stopped by shields); "
            f"{result['remaining_strength']} pass through")
        from .combat import apply_damage
        braced = target.special_order == SpecialOrder.BRACE_FOR_IMPACT.value
        apply_damage(target, result["hits"], dice, game_state,
                     ignores_shields=False, target_braced=braced,
                     attacker_key=marker.id, origin=(marker.x, marker.y))
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
    Turret split (s.28): mines count with torpedoes, so turrets already used
    against attack craft this phase can't fire at a mine (Orks excepted); Ork
    turrets need 5+.
    """
    result = {"hits": 0, "attack_dice": 8}

    turrets = ordnance_turrets(ship, game_state)
    end_ordnance_attack(ship, game_state)

    # Massed turrets: +1 per non-crippled friendly ship in base contact (max +3)
    if all_ships:
        bonus = get_massed_turret_bonus(ship, all_ships)
        if bonus > 0:
            turrets += bonus
            game_state.add_log(
                f"  {ship.name} massed turrets: +{bonus} (total {turrets})")
    attack_dice = 8
    if turrets > 0 and turrets_blocked(ship, "torp"):
        game_state.add_log(f"  {ship.name} turrets already used vs attack craft this phase")
        turrets = 0

    if turrets > 0:
        need = turret_hit_on(ship)
        turret_rolls = dice.roll_d6(
            turrets, f"{ship.name} turrets vs mine (any {need}+ reduces to 4D6)")
        mark_turrets_used(ship, "torp", game_state)
        if any(r >= need for r in turret_rolls):
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
    turrets = ordnance_turrets(target, game_state)
    bonus = get_massed_turret_bonus(target, all_ships) if all_ships else 0
    turrets += bonus

    if turrets <= 0 or bomber_count <= 0:
        return {"killed": 0, "log": []}
    if turrets_blocked(target, "craft"):
        # s.28 "vice versa": turrets used against torpedoes / mines this phase
        return {"killed": 0, "log": [f"  {target.name} turrets already used vs "
                                     f"torpedoes / mines this phase: no shots at the attack craft"]}

    need = turret_hit_on(target)
    rolls = dice.roll_d6(
        turrets,
        f"Phase 1 interception: {target.name} vs {bomber_count} attack craft ({need}+)")
    kills = min(sum(1 for r in rolls if r >= need), bomber_count)

    bonus_str = f" +{bonus} massed" if bonus else ""
    log = [
        f"  Phase 1 interception vs {target.name}: "
        f"{turrets} turrets{bonus_str}, "
        f"rolls {rolls} → {kills}/{bomber_count} attack craft destroyed"
    ]

    # Mark turrets as used vs craft this phase (blocks torpedo defence)
    mark_turrets_used(target, "craft", game_state)

    return {"killed": kills, "log": log}


def resolve_bomber_attack(marker: OrdnanceMarker, target: Ship,
                          dice: DiceRoller, game_state: GameState,
                          suppressed_by_fighter: bool = False,
                          bonus_attacks: int = 0) -> Dict:
    """
    Resolve bomber attack. D6 attacks per squadron vs lowest armor. Bypasses shields.

    Per XR rules:
    - Turret reduction uses base turrets ONLY; massed turret bonus does not apply.
    - Turret reduction always applies, even if turrets fired at torpedoes or mines this
      phase (owner ruling: only the shoot-down roll is blocked by s.28's "vice versa").

    Turret suppression modes:
      XR (default): suppressed_by_fighter=True → exactly 3 attacks, turrets bypassed.
      Remastered p.82: the wave's fighter bonus (waves.ship_attack_plan "bonus")
      is added once, as `bonus_attacks`, on top of one bomber's normal D6 -
      turrets (minimum 0 before the bonus).
    """
    result = {"attacks": 0, "hits": 0, "turret_reduction": 0, "suppressed": False}

    # Base turrets only — massed turret bonus does NOT apply to bomber attack reduction
    turret_reduction = ordnance_turrets(target, game_state)
    end_ordnance_attack(target, game_state)

    if marker.ordnance_type == OrdnanceType.FIGHTA_BOMMER.value:
        # Ork rules: Fighta-Bommerz make only D3+1 attacks per squadron, and
        # turrets cannot reduce them below 1 (Ork pilots always try to ram)
        mark_turrets_used(target, "craft", game_state)
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
        # Mark turrets as used vs craft so torpedo defence knows (owner ruling:
        # the attack reduction applies even after turrets fired at torpedoes)
        mark_turrets_used(target, "craft", game_state)

        attack_roll = dice.roll_d6(1, f"Bomber attacks on {target.name}")[0]
        total_attacks = max(0, attack_roll - turret_reduction)
        if bonus_attacks > 0:
            # Remastered p.82: the wave's fighters add their attacks on top
            total_attacks += bonus_attacks
            game_state.add_log(
                f"  Remastered suppression: roll {attack_roll} - {turret_reduction} "
                f"turrets + {bonus_attacks} from the wave's fighters "
                f"= {total_attacks} attacks")

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

    is_torpedo = is_torpedo_salvo(target)

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

        # s.23: if both pass, they must keep interacting and, unable to save
        # twice in a phase, both are removed
        if not result["fighter_removed"] and not result["target_removed"]:
            result["fighter_removed"] = result["target_removed"] = True
            game_state.add_log("  Both passed their saves: they interact again and "
                               "both are removed")

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
    boarding and seeking torpedoes ignore friendly attack craft (s.16)."""
    t1, t2 = is_torpedo_salvo(m1), is_torpedo_salvo(m2)
    if t1 and t2:
        return "collide"
    for f, t, t_is_torp in ((m1, m2, t2), (m2, m1, t1)):
        if is_fighter_type(f) and t_is_torp and not ignores_friendly(t):
            return "intercept"
    return None


def _interaction_pass(ordnance, to_remove, logs, dice, game_state, is_lead):
    """One pass over every pair of touching markers; markers in a wave only
    interact while they lead it."""
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
            if m1.wave_id and m1.wave_id == m2.wave_id:
                continue  # a wave's own squadrons
            if not (is_lead(m1, ordnance, to_remove) and is_lead(m2, ordnance, to_remove)):
                continue
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
    from .waves import is_lead

    # Waves interact one squadron at a time from the lead (s.25): repeat until
    # nothing more happens, so the next squadron of a wave meets what's left
    while True:
        before = (len(to_remove), sum(1 for m in ordnance if m.resilient_used))
        _interaction_pass(ordnance, to_remove, logs, dice, game_state, is_lead)
        if (len(to_remove), sum(1 for m in ordnance if m.resilient_used)) == before:
            break

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
            need = 5 if marker.ordnance_type == OrdnanceType.TORPEDO_SEEKING.value else 6
            roll = dice.roll_d6(1, f"Ordnance through blast marker ({need}+ = destroyed)")[0]
            return roll >= need
    return False


def check_ordnance_vs_blast_contact(dice: DiceRoller) -> bool:
    """Modern / Remastered blast markers: ordnance attacking a ship in contact
    with blast markers is treated as moving through them: destroyed on a 6."""
    return dice.roll_d6(1, "Ordnance attacking a ship in blast markers (6 = destroyed)")[0] == 6


_TORP_LIKE = {
    OrdnanceType.TORPEDO_STANDARD.value,
    OrdnanceType.TORPEDO_SHORT_BURN.value,
    OrdnanceType.TORPEDO_BARRAGE.value,
    OrdnanceType.TORPEDO_GUIDED_LD.value,
    OrdnanceType.TORPEDO_SEEKING.value,
    OrdnanceType.TORPEDO_MELTA.value,
    OrdnanceType.TORPEDO_VORTEX.value,
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
        gas/dust cloud = D6=6 destroys (owner ruling)

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
            elif ptype == "gas_dust_cloud":
                # Owner ruling: attack craft in a gas / dust cloud are destroyed
                # on a 6, like torpedoes ("may destroy ordnance")
                roll = dice.roll_d6(1, "Attack craft in dust cloud (6=destroyed)")[0]
                if roll == 6:
                    return True, "gas_dust_cloud"
            # Planets have no effect on attack craft
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
    """Ship IDs the torpedoes launched by `launcher` pass through: the launcher
    and every friendly ship in contiguous base contact with it when they are
    fired (s.15-16: "fire its torpedoes 'through' an allied ship ... in base
    contact"; combined salvos "will not hit vessels in contiguous base
    contact"). combined_exempt() does the same for a combining group."""
    return combined_exempt([launcher], game_state)


def combined_exempt(launchers: List[Ship], game_state: GameState) -> List[str]:
    from .boarding import ships_in_base_contact
    friends = [s for s in game_state.get_ships()
               if s.player == launchers[0].player and not s.is_destroyed and not s.is_disengaged]
    chain = {s.id for s in launchers}
    grew = True
    while grew:
        grew = False
        for s in friends:
            if s.id in chain:
                continue
            if any(ships_in_base_contact(s, o) for o in friends if o.id in chain):
                chain.add(s.id)
                grew = True
    return sorted(chain)


def mine_launch_strength(ship: Ship, weapon: Dict) -> int:
    """Mines a launcher lays now (s.17: one per launcher a turn), halved
    (rounding up) when crippled and again when braced, as all ordnance (s.15)."""
    n = weapon.get("strength", 0) or 0
    if ship.is_crippled:
        n = ship.crippled_value(n)
    if ship.special_order == "brace_for_impact":
        n = (n + 1) // 2
    return n


def lay_mines(ship: Ship, weapon: Dict, gs: GameState) -> List[OrdnanceMarker]:
    """Launch one mine per mine launcher (s.17) at the end of the shooting
    phase, placed on the ship's base; they move 10cm towards the nearest enemy
    vessel in every ordnance phase. Unloads the ship (mark_launched). Returns
    the markers."""
    import random as _rng
    fresh = gs.get_ship_by_id(ship.id) or ship
    if not fresh.ordnance_loaded_mines:
        return []
    n = mine_launch_strength(fresh, weapon)
    exempt = compute_torpedo_launch_exempt(fresh, gs)
    out = []
    for i in range(n):
        m = OrdnanceMarker(
            id=f"mine_{fresh.id}_{gs.turn_number}_{i}_{_rng.randint(0, 9999)}",
            ordnance_type=OrdnanceType.MINE_FIELD.value, owner_player=fresh.player,
            launched_by=fresh.id, x=fresh.x + (i - n / 2) * 1.5, y=fresh.y,
            heading=fresh.heading, strength=1, speed=weapon.get("mine_speed", 10),
            launched_turn=gs.turn_number, launch_exempt_ships=list(exempt))
        gs.add_ordnance(m)
        out.append(m)
    fresh.mark_launched("mines")
    gs.update_ship(fresh)
    gs.add_log(f"{fresh.name} lays {n} mine(s)")
    return out


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
        strength = ship.crippled_value(strength)
    if ship.special_order == SpecialOrder.BRACE_FOR_IMPACT.value:
        strength = (strength + 1) // 2
    return strength, rolled


def boarding_ok(weapon: Dict, boarding: bool) -> bool:
    """Boarding torpedoes only from launchers that carry them."""
    return bool(boarding and weapon.get("boarding_torpedoes")
                and weapon.get("torpedo_type", "standard") != "guided")


# Torpedo types a ship can buy or roll for (s.16) that the engine plays.
# Carried in addition to the launcher's own types (owner ruling); the ship
# has the special rule "torpedo_type:<key>".
EXTRA_TORPEDO_TYPES = {
    "short_burn": (OrdnanceType.TORPEDO_SHORT_BURN.value, "Short burn torpedoes (40cm, out of fuel on a 6)"),
    "barrage": (OrdnanceType.TORPEDO_BARRAGE.value, "Barrage bombs (hits stopped by shields)"),
    "guided": (OrdnanceType.TORPEDO_GUIDED_LD.value, "Guided torpedoes (turn 45° on a Leadership test)"),
    "seeking": (OrdnanceType.TORPEDO_SEEKING.value, "Seeking torpedoes (home on the nearest enemy; once per game)"),
    "melta": (OrdnanceType.TORPEDO_MELTA.value, "Melta torpedoes (Fire crit per hit, no damage; once per game)"),
    "vortex": (OrdnanceType.TORPEDO_VORTEX.value, "Vortex torpedoes (1 damage + automatic crit per hit; once per game)"),
    # Ordo Hereticus Inferno Torpedoes: melta torpedoes usable any number of times
    "inferno": (OrdnanceType.TORPEDO_MELTA.value, "Inferno torpedoes (melta: Fire crit per hit, no damage)"),
}
ONCE_PER_GAME_TORPEDOES = ("seeking", "melta", "vortex")
# Game-start torpedo rolls (ship rule "torpedo_roll:<table>"), rolled per ship
TORPEDO_ROLL_TABLES = {
    "d3_anointed": ["seeking", "melta", "vortex"],                       # Chaos, Imperial Navy
    "d6_refitted": ["short_burn", "barrage", "guided", "seeking", "melta", "vortex"],  # AdMech, RT, Orks
}


def unused_once_torpedoes(ship) -> List[str]:
    return [k for k in ship_torpedo_types(ship) if k in ONCE_PER_GAME_TORPEDOES
            and k not in (getattr(ship, "once_torps_used", None) or [])]


def roll_torpedo_types(game_state: GameState, dice: DiceRoller,
                       ai_dice: Optional[DiceRoller] = None) -> List[str]:
    """Game start: each ship with a "torpedo_roll:<table>" rule rolls for its
    extra torpedo type (Anointed Munitions D3; Refitted / Looted Torpedoes D6).
    ai_dice rolls for AI-controlled ships."""
    logs = []
    for i, d in enumerate(game_state.ships):
        ai = game_state.ai_spectator or game_state.ai_player == d.get("player")
        roller = ai_dice if (ai and ai_dice is not None) else dice
        rules = list(d.get("special_rules", []))
        rolls = [r for r in rules if r.startswith("torpedo_roll:")]
        for r in rolls:
            table = TORPEDO_ROLL_TABLES.get(r.split(":", 1)[1])
            if not table:
                continue
            if len(table) == 3:
                n = roller.roll_d3(f"{d.get('name')} torpedo type (D3)")
            else:
                n = roller.roll_d6(1, f"{d.get('name')} torpedo type (D6)")[0]
            kind = table[n - 1]
            rules.remove(r)
            rules.append(f"torpedo_type:{kind}")
            logs.append(f"{d.get('name')} rolls {n}: {EXTRA_TORPEDO_TYPES[kind][1]}")
        if rolls:
            game_state.ships[i] = {**d, "special_rules": rules}
    return logs
SHORT_BURN_SPEED = 40


def ship_torpedo_types(ship) -> List[str]:
    return [r.split(":", 1)[1] for r in (getattr(ship, "special_rules", None) or [])
            if r.startswith("torpedo_type:") and r.split(":", 1)[1] in EXTRA_TORPEDO_TYPES]


def torpedo_kind_options(ship, weapon: Dict, hit_and_run: bool = True) -> List[Tuple[str, str]]:
    """(kind, label) loads a launcher may fire: standard, boarding where the
    profile lists it, and any bought or rolled torpedo types. Guided launchers
    (Tau missiles) fire only themselves."""
    if weapon.get("torpedo_type") == "guided":
        return [("standard", "Guided missiles")]
    kinds = [("standard", "Standard torpedoes")]
    if (weapon.get("boarding_torpedoes") and hit_and_run
            and "no_boarding_torps" not in (getattr(ship, "special_rules", None) or [])):
        kinds.append(("boarding", "Boarding torpedoes (1 hit-and-run raid per hit)"))
    used = getattr(ship, "once_torps_used", None) or []
    kinds += [(k, EXTRA_TORPEDO_TYPES[k][1]) for k in ship_torpedo_types(ship)
              if k not in used]
    return kinds


def mark_once_torpedoes_used(ship, kind: str, game_state: GameState) -> None:
    """Seeking, melta and vortex torpedoes: one salvo per ship per game."""
    if kind in ONCE_PER_GAME_TORPEDOES:
        fresh = game_state.get_ship_by_id(ship.id) or ship
        if kind not in fresh.once_torps_used:
            fresh.once_torps_used = list(fresh.once_torps_used) + [kind]
            game_state.update_ship(fresh)
        ship.once_torps_used = fresh.once_torps_used


def torpedo_ordnance_type(weapon: Dict, boarding: bool = False, kind: str = "") -> str:
    if weapon.get("torpedo_type") == "guided":
        return OrdnanceType.TORPEDO_GUIDED.value
    if kind == "boarding":
        boarding = True
    if boarding_ok(weapon, boarding):
        return OrdnanceType.TORPEDO_BOARDING.value
    if kind in EXTRA_TORPEDO_TYPES:
        return EXTRA_TORPEDO_TYPES[kind][0]
    return OrdnanceType.TORPEDO_STANDARD.value


def torpedo_speed_for(weapon: Dict, o_type: str) -> float:
    if o_type == OrdnanceType.TORPEDO_SHORT_BURN.value:
        return SHORT_BURN_SPEED
    return weapon.get("torpedo_speed", TORPEDO_SPEED_DEFAULT)


def torpedo_kind_name(o_type: str) -> str:
    return {OrdnanceType.TORPEDO_GUIDED.value: "guided missiles",
            OrdnanceType.TORPEDO_BOARDING.value: "boarding torpedoes",
            OrdnanceType.TORPEDO_SHORT_BURN.value: "short burn torpedoes",
            OrdnanceType.TORPEDO_BARRAGE.value: "barrage bombs",
            OrdnanceType.TORPEDO_GUIDED_LD.value: "guided torpedoes",
            OrdnanceType.TORPEDO_SEEKING.value: "seeking torpedoes",
            OrdnanceType.TORPEDO_MELTA.value: "melta torpedoes",
            OrdnanceType.TORPEDO_VORTEX.value: "vortex torpedoes"}.get(o_type, "torpedoes")


def short_burn_fuel_checks(game_state: GameState, dice: DiceRoller,
                           player: Optional[int] = None) -> List[str]:
    """After a short burn salvo has moved and made any attacks, roll a D6: on
    a 6 it runs out of fuel and is replaced with a blast marker (s.16)."""
    logs, gone = [], set()
    for o in list(game_state.ordnance):
        if o.get("ordnance_type") != OrdnanceType.TORPEDO_SHORT_BURN.value:
            continue
        if player is not None and o.get("owner_player") != player:
            continue
        roll = dice.roll_d6(1, f"Short burn torpedoes Str {o.get('strength')} fuel (6 = out)")[0]
        if roll == 6:
            gone.add(o["id"])
            game_state.add_blast_marker(BlastMarker(
                id=f"short_burn_{o['id']}", x=o.get("x", 0.0), y=o.get("y", 0.0),
                source="short_burn"))
            logs.append("  Short burn torpedoes run out of fuel (rolled 6): "
                        "replaced with a blast marker")
    if gone:
        game_state.ordnance = [o for o in game_state.ordnance if o["id"] not in gone]
    return logs


def launch_torpedoes(ship: Ship, weapon: Dict, game_state: GameState,
                     heading: Optional[float] = None,
                     boarding: bool = False,
                     dice: Optional[DiceRoller] = None,
                     kind: str = "") -> OrdnanceMarker:
    """Create a torpedo marker from a ship's launcher.

    `heading` lets the caller aim the salvo (e.g. an AI leading a target).
    It is clamped to ±45° of the ship's heading — the same forward-arc
    constraint the human launch dialog enforces. Defaults to ship heading.
    """
    torpedo_type = weapon.get("torpedo_type", "standard")
    if not getattr(game_state, "rule_hit_and_run", True):
        # Owner: no boarding torpedoes while hit-and-run raids are disabled (each
        # hit is a raid, s.16 / s.31): a standard salvo instead
        if boarding or kind == "boarding":
            boarding, kind = False, ("" if kind == "boarding" else kind)
    o_type = torpedo_ordnance_type(weapon, boarding, kind)
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
        speed=torpedo_speed_for(weapon, o_type),
        launched_turn=game_state.turn_number,
        can_turn=(torpedo_type == "guided"),
        turn_angle=45 if torpedo_type == "guided" else 0,
        launch_exempt_ships=compute_torpedo_launch_exempt(ship, game_state),
        # The launcher's raid bonuses go with its boarding torps (s.31)
        special_rules=list(ship.special_rules),
    )
    game_state.add_ordnance(marker)
    ship.mark_launched("torps")
    if kind in ONCE_PER_GAME_TORPEDOES and kind in ship_torpedo_types(ship):
        ship.once_torps_used = list(ship.once_torps_used) + [kind]
    game_state.update_ship(ship)
    game_state.add_log(f"{ship.name} launches {torpedo_kind_name(o_type)} (Str {strength})")
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
        total = ship.crippled_value(total)
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


def mr_attack_mode_ai(target: Ship, gs: Optional[GameState] = None, owner: int = 0,
                      rules=None) -> str:
    """AI choice for craft that can attack as bombers or assault boats (s.24):
    whichever is worth more in expected VP (waves.best_attack_mode). Without a
    game state, the old rule: raid ships with 3+ turrets."""
    if gs is None:
        return "assault_boat" if target.effective_turrets >= 3 else "bomber"
    from .waves import best_attack_mode
    return best_attack_mode(target, gs, owner, rules)


def craft_type_allowed(craft_type: str, bay_weapons: List[Dict], game_state) -> bool:
    """Owner: with hit-and-run raids disabled (`rule_hit_and_run` off), assault
    boats can't be launched (s.22: they only make raids). Multi-role craft that
    also act as fighters / bombers (Thunderhawks, Gun-Cutters) still launch;
    only their raid mode is off."""
    if getattr(game_state, "rule_hit_and_run", True):
        return True
    roles = set(craft_roles(craft_stats(craft_type, bay_weapons)[0]))
    return roles != {"assault_boat"}


def launch_attack_craft(ship: Ship, weapon: Dict, craft_type: str,
                        count: int, game_state: GameState) -> List[OrdnanceMarker]:
    """Create attack craft markers from launch bays. Assault boats aren't
    launched while hit-and-run raids are disabled (craft_type_allowed)."""
    if not craft_type_allowed(craft_type, [weapon], game_state):
        game_state.add_log(f"{ship.name}: assault boats can't launch (hit-and-run raids "
                           f"are disabled)")
        return []
    o_type, speed, resilient = craft_stats(craft_type, [weapon])

    markers = []
    taken = {o["id"] for o in game_state.ordnance}
    for i in range(count):
        mid = f"craft_{ship.id}_{craft_type}_{i}_{game_state.turn_number}"
        n = 1
        while mid in taken:                  # several launches of one type in a phase
            mid = f"craft_{ship.id}_{craft_type}_{i}_{game_state.turn_number}_{n}"
            n += 1
        taken.add(mid)
        marker = OrdnanceMarker(
            id=mid,
            ordnance_type=o_type, owner_player=ship.player,
            launched_by=ship.id, x=ship.x, y=ship.y,
            heading=ship.heading, speed=speed,
            launched_turn=game_state.turn_number,
            resilient_save=resilient,
            special_rules=list(ship.special_rules),
        )
        markers.append(marker)
        game_state.add_ordnance(marker)

    ship.mark_launched("craft")
    game_state.update_ship(ship)
    game_state.add_log(f"{ship.name} launches {count}x {craft_type}")
    return markers
