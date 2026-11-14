"""Sub-plots (bfgxr/rules/14_scenarios.md, XR p.80-82; CLAUDE.md To do 7 b),
pure logic: generation (D6 for the table, D6 for the entry), the set-up
effects, the objectives judged at the end of the game and the battle result
(Heroic Victory / Victory / Heroic Defeat / Miserable Defeat).

State: `GameState.subplots` {"1": {...}, "2": {...}}, each with the key, the
name, the renown (success, failure) and whatever the sub-plot nominated or
rolled. Effects that need engine hooks read it through the helpers below.
Readings to confirm with the owner are marked "reading"; sub-plots whose
effects aren't built are flagged `unbuilt` and say why."""
from typing import Callable, Dict, List, Optional

TABLES = {
    "legacies": {
        1: ("gunnery_practice", "Gunnery Practice", (1, -1)),
        2: ("extended_duty", "Extended Duty", (1, 0)),
        3: ("blood_bond", "Blood Bond", (1, -1)),
        4: ("fleet_experience", "Fleet Experience", (1, 0)),
        5: ("no_quarter", "No Quarter!", (1, -1)),
        6: ("vendetta", "Vendetta", (1, -2)),
    },
    "chance": {
        1: ("meteor_storm", "Meteor Storm!", (3, -2)),
        2: ("signaling_problems", "Signaling Problems", (1, -1)),
        3: ("unexpected_help", "Unexpected Help", (0, -2)),
        4: ("navigational_hazards", "Navigational Hazards", (1, -1)),
        5: ("fresh_captain", "Fresh Captain", (1, -1)),
        6: ("enemy_plans", "Enemy Plans", (1, -1)),
    },
    "ploys": {
        1: ("surprise_attack", "Surprise Attack!", (2, -2)),
        2: ("secret_intelligence", "Secret Intelligence", (0, -1)),
        3: ("experimental_ship", "Experimental Ship", (1, -1)),
        4: ("desperate_mission", "Desperate Mission", (1, -1)),
        5: ("decoy", "Decoy", (1, -1)),
        6: ("hit_and_run", "Hit and Run", (1, -1)),
    },
}

# Effects the engine doesn't play yet (the objective is still judged where it can be)
UNBUILT = {
    "decoy": "the hidden decoy isn't built: the objective can't be met",
}
COMMAND_RANGE = 30.0      # Fleet Experience / Signaling Problems: within 30cm of the commander


def capital_ships(gs, player: int):
    return [s for s in gs.get_ships() if s.player == player and s.ship_type != "escort"
            and "immobile" not in s.special_rules and s.ship_type != "defense"]


def generate(gs, player: int, dice) -> Dict:
    """Roll a sub-plot: D6 1-2 Legacies of War, 3-4 Chance Circumstances, 5-6
    Secret Ploys; then a D6 on that table."""
    t = dice.roll_d6(1, f"Player {player} sub-plot table (D6)")[0]
    table = "legacies" if t <= 2 else ("chance" if t <= 4 else "ploys")
    n = dice.roll_d6(1, f"Player {player} sub-plot ({table})")[0]
    key, name, renown = TABLES[table][n]
    sp = {"key": key, "name": name, "renown": list(renown), "table": table}
    if key in UNBUILT:
        sp["unbuilt"] = UNBUILT[key]
    return sp


def _set(gs, player: int, sp: Dict) -> None:
    subs = dict(getattr(gs, "subplots", None) or {})
    subs[str(player)] = sp
    gs.subplots = subs


def get(gs, player: int) -> Optional[Dict]:
    return (getattr(gs, "subplots", None) or {}).get(str(player))


def apply_setup(gs, player: int, sp: Dict, dice,
                choose_ship: Optional[Callable] = None) -> List[str]:
    """The sub-plot's set-up effects and nominations (before deployment).
    choose_ship(candidates, prompt) -> ship: a human's nomination; None picks
    for the AI (the enemy's dearest capital ship, or our dearest for a
    mission). Returns log lines."""
    from .combat import roll_critical_hit
    key = sp["key"]
    logs = [f"Player {player} sub-plot: {sp['name']}"]
    own = capital_ships(gs, player)
    enemy = capital_ships(gs, 3 - player)
    pick = choose_ship or (lambda cands, _p: max(cands, key=lambda s: s.points_value,
                                                 default=None))
    if key == "gunnery_practice":
        for s in own:
            if dice.roll_d6(1, f"Gunnery Practice: {s.name}")[0] >= 4:
                s.special_rules = list(s.special_rules) + ["gunnery_practice"]
                gs.update_ship(s)
                logs.append(f"  {s.name}: +1 Ld for Lock On")
    elif key == "extended_duty":
        for s in own:
            r = dice.roll_d6(1, f"Extended Duty: {s.name}")[0]
            if r == 1:
                lost = dice.roll_d3(f"Extended Duty: {s.name} damage")
                s.hits_remaining = max(1, s.hits_remaining - lost)
                gs.update_ship(s)
                logs.append(f"  {s.name} starts with {lost} damage")
            elif r == 2:
                s.special_rules = list(s.special_rules) + ["extended_duty"]
                gs.update_ship(s)
                logs.append(f"  {s.name}: -1 to Lock On and Reload Ordnance checks")
    elif key in ("vendetta", "secret_intelligence"):
        t = pick(enemy, f"{sp['name']}: nominate an enemy capital ship")
        if t is not None:
            sp["target"] = t.id
            logs.append(f"  target: {t.name}")
    elif key == "desperate_mission":
        t = pick(own, "Desperate Mission: nominate one of your capital ships")
        if t is not None:
            sp["ship"] = t.id
            logs.append(f"  ship: {t.name}")
    elif key == "meteor_storm":
        for s in own:
            if dice.roll_d6(1, f"Meteor Storm: {s.name}")[0] <= 3:
                roll_critical_hit(s, dice, gs)
                gs.update_ship(s)
                logs.append(f"  {s.name} takes a critical hit")
    elif key == "fresh_captain":
        cands = [s for s in own if not s.is_flagship] or own
        if cands:
            i = dice.roll_d6(1, "Fresh Captain: which ship")[0]
            s = cands[(i - 1) % len(cands)]
            s.leadership = max(1, s.leadership - 1)
            gs.update_ship(s)
            sp["ship"] = s.id
            logs.append(f"  {s.name}: -1 Ld; it must cripple or destroy enemy ships worth "
                        f"its own points")
    elif key == "surprise_attack":
        sp["turns"] = dice.roll_d6(1, "Surprise Attack: D3 turns")[0]
        sp["turns"] = (sp["turns"] + 1) // 2
        logs.append(f"  the enemy can't use special orders for {sp['turns']} turn(s)")
    elif key == "experimental_ship":
        if own:
            i = dice.roll_d6(1, "Experimental Ship: which ship")[0]
            s = own[(i - 1) % len(own)]
            sp["ship"] = s.id
            imp = dice.roll_d6(1, "Experimental Ship improvement")[0]
            while True:
                side = dice.roll_d6(1, "Experimental Ship side effect")[0]
                if not _contradicts(imp, side):
                    break
            _experiment(s, imp, side)
            gs.update_ship(s)
            sp["improvement"], sp["side_effect"] = imp, side
            logs.append(f"  {s.name}: improvement {imp}, side effect {side}")
    elif key == "hit_and_run":
        sp["turns"] = sum(dice.roll_d6(2, "Hit and Run: 2D6 turns"))
        logs.append(f"  win within {sp['turns']} turns")
    elif key == "navigational_hazards":
        _place_hazards(gs, dice, logs)
    elif key == "unexpected_help":
        _unexpected_help(gs, player, sp, dice, logs)
    elif key == "blood_bond":
        sp["lost_seen"] = sum(1 for s in own if _lost(s))
    if key == "secret_intelligence":
        flag = next((s for s in gs.get_ships() if s.player == player and s.is_flagship), None)
        if flag is not None:
            flag.rerolls_remaining += 1
            gs.update_ship(flag)
            logs.append("  +1 fleet commander re-roll")
    if sp.get("unbuilt"):
        logs.append(f"  not built yet: {sp['unbuilt']}")
    _set(gs, player, sp)
    for line in logs:
        gs.add_log(f"[Sub-plot] {line}")
    return logs


def _unexpected_help(gs, player: int, sp: Dict, dice, logs: List[str]) -> None:
    """Add a single capital ship or escort squadron totalling D3 x 50 points
    (judgement for the pick, also for a human until a dialog exists: the
    dearest capital ship within the limit, else the escorts worth most within
    it; the fleet's main faction). Its Leadership is rolled as the others'."""
    from .models import Ship
    from .convoy_narrative import _pick_capital, _pick_escorts
    from .scenarios import _main_faction
    from .booklet_ships import LEADERSHIP_TABLES
    limit = 50 * ((dice.roll_d6(1, "Unexpected Help: D3 x 50 points")[0] + 1) // 2)
    faction = _main_faction(gs, player) or "imperial_navy_gothic"
    e = _pick_capital(faction, limit)
    n = 1
    if e is None:
        e, n = _pick_escorts(faction, limit)
    if e is None or n <= 0:
        logs.append(f"  no {faction} ship fits within {limit}pts")
        return
    ids = []
    sq = f"help_{player}" if e.ship_type == "escort" else ""
    ld = 0
    if e.leadership_table:
        ld = LEADERSHIP_TABLES.get(e.leadership_table, LEADERSHIP_TABLES["Default"])[
            dice.roll_d6(1, f"Unexpected Help: {e.ship_class} Leadership")[0] - 1]
    for k in range(n):
        sid = f"help_{player}_{k}"
        d = e.to_ship_dict(e.ship_class, player, ship_id=sid)
        d.update(x=0.0, y=0.0, heading=0.0, squadron_id=sq)
        if ld:
            d["leadership"] = ld
        gs.add_ship(Ship.from_dict(d))
        ids.append(sid)
    sp["ships"] = ids
    logs.append(f"  reinforcements ({limit}pts): {n} x {e.ship_class}")


def _flagship(gs, player: int):
    return next((s for s in gs.get_ships() if s.player == player and s.is_flagship
                 and not s.is_destroyed and not s.is_disengaged), None)


def _near_commander(gs, ship) -> bool:
    """The ship, or a member of its squadron, within 30cm of its fleet
    commander's ship."""
    flag = _flagship(gs, ship.player)
    if flag is None:
        return False
    group = [ship]
    if ship.squadron_id:
        group = [s for s in gs.get_ships() if s.squadron_id == ship.squadron_id
                 and s.player == ship.player and not s.is_destroyed] or [ship]
    return any(s.id == flag.id or s.distance_to(flag) <= COMMAND_RANGE for s in group)


def leadership(gs, ship) -> int:
    """A ship's Leadership for its tests with the sub-plots' effects: Fleet
    Experience (within 30cm of the commander's ship it may use the
    commander's Ld: the better, reading) and Blood Bond (+1 for the turn after
    a capital ship of the fleet was crippled or destroyed, max 10)."""
    ld = ship.leadership
    if gs is None:
        return ld
    sp = get(gs, ship.player)
    if not sp:
        return ld
    if sp["key"] == "fleet_experience":
        flag = _flagship(gs, ship.player)
        if flag is not None and flag.id != ship.id and ship.distance_to(flag) <= COMMAND_RANGE:
            ld = max(ld, flag.leadership)
    if (sp["key"] == "blood_bond" and sp.get("bond_turn") == gs.turn_number
            and ship.ship_type != "escort" and not _lost(ship)):
        ld = min(10, ld + 1)
    return ld


def reroll_blocked(gs, player: int, ship) -> bool:
    """Signaling Problems: fleet commander re-rolls only for squadrons with a
    ship within 30cm of the commander's ship (reading: single ships too, a
    ship being its own squadron)."""
    sp = get(gs, player)
    if not sp or sp["key"] != "signaling_problems" or ship is None:
        return False
    return not _near_commander(gs, ship)


def turn_start(gs, player: int) -> None:
    """Blood Bond: at the start of the player's turn, if one of its capital
    ships was crippled or destroyed since its last turn, the others gain +1 Ld
    for this turn (reading: "the next turn" is the player's next turn)."""
    sp = get(gs, player)
    if not sp or sp["key"] != "blood_bond":
        return
    lost = sum(1 for s in capital_ships(gs, player) if _lost(s))
    if lost > sp.get("lost_seen", 0):
        sp = dict(sp)
        sp["lost_seen"] = lost
        sp["bond_turn"] = gs.turn_number
        _set(gs, player, sp)
        gs.add_log(f"[Sub-plot] Blood Bond: player {player}'s capital ships are at +1 Ld "
                   f"this turn")


def _contradicts(imp: int, side: int) -> bool:
    """Improvement and side effect that cancel (re-roll the side effect)."""
    return (imp, side) in {(1, 2), (2, 1), (3, 4), (4, 3), (6, 5)}


def _experiment(s, imp: int, side: int) -> None:
    """Experimental Ship: the improvement and side effect (p.82)."""
    guns = [w for w in s.weapons if w.get("weapon_type") in ("battery", "lance")]
    if imp == 1:
        for w in guns:
            w["range_cm"] = int(w.get("range_cm", 0) * 1.5)
    elif imp == 2:
        s.shields_max += 1
    elif imp == 3:
        s.speed += 5
    elif imp == 4:
        s.hits_max += 2
        s.hits_remaining += 2
    elif imp == 5:
        s.turn_angle = max(s.turn_angle, 90)
    elif imp == 6:
        s.leadership = min(10, s.leadership + 1)
    if side == 1:
        s.shields_max = max(0, s.shields_max - 1)
    elif side == 2:
        for w in guns:
            w["range_cm"] = int(w.get("range_cm", 0) / 2)
    elif side == 3:
        s.hits_max = max(1, s.hits_max - 2)
        s.hits_remaining = min(s.hits_remaining, s.hits_max)
    elif side == 4:
        s.speed = max(5, s.speed - 5)
    elif side == 5:
        s.leadership = max(1, s.leadership - 1)
    elif side == 6:
        for w in guns:
            w["strength"] = (int(w.get("strength", 0)) + 1) // 2


def _place_hazards(gs, dice, logs) -> None:
    """Navigational Hazards: 1-2 one gas / dust cloud, 3-4 two, 5 an asteroid
    field, 6 an asteroid field and D3 clouds. Reading: placed at random, at
    least 30cm from the long edges (the deployment zones)."""
    from .models import Phenomenon
    r = dice.roll_d6(1, "Navigational Hazards")[0]
    clouds, fields = {1: 1, 2: 1, 3: 2, 4: 2, 5: 0, 6: 0}[r], (1 if r >= 5 else 0)
    if r == 6:
        clouds = (dice.roll_d6(1, "D3 clouds")[0] + 1) // 2
    n = len(gs.phenomena)
    for kind, count in (("gas_cloud", clouds), ("asteroid_field", fields)):
        for _ in range(count):
            x = 20 + (dice.roll_d6(1, "hazard x")[0] - 1) * (gs.table_width - 40) / 5
            y = 35 + (dice.roll_d6(1, "hazard y")[0] - 1) * (gs.table_height - 70) / 5
            n += 1
            gs.add_phenomenon(Phenomenon(id=f"subplot_{kind}_{n}", phenomenon_type=kind,
                                         x=x, y=y, width=15.0, height=10.0))
            logs.append(f"  {kind.replace('_', ' ')} at ({x:.0f}, {y:.0f})")


# --- Effects during the game -------------------------------------------------------

def command_check_modifier(ship, order: str) -> int:
    """Gunnery Practice +1 to go onto Lock On; Extended Duty -1 for Lock On
    and Reload Ordnance."""
    mod = 0
    if order == "lock_on" and "gunnery_practice" in ship.special_rules:
        mod += 1
    if order in ("lock_on", "reload_ordnance") and "extended_duty" in ship.special_rules:
        mod -= 1
    return mod


def orders_forbidden(gs, ship) -> Optional[str]:
    """Surprise Attack!: the enemy of the player who rolled it can't go on
    special orders for the first D3 turns (reading: game turns, both players'
    turns counted together, so turn_number up to 2 x D3)."""
    sp = get(gs, 3 - ship.player)
    if sp and sp["key"] == "surprise_attack":
        limit = 2 * sp.get("turns", 1)
        if getattr(gs, "turn_system", "igougo") == "aa":
            limit = sp.get("turns", 1)
        if gs.turn_number <= limit:
            return "Surprise Attack!: no special orders yet (enemy sub-plot)"
    return None


def record_boarding(gs, player: int, target, dice) -> None:
    """A boarding action launched by `player` against `target`: Enemy Plans
    (a capital ship, D6 +1 against the fleet commander's ship, 4+: the plans
    are found) and Secret Intelligence (the nominated ship boarded)."""
    sp = get(gs, player)
    if not sp:
        return
    if sp["key"] == "enemy_plans" and target.ship_type != "escort" and not sp.get("done"):
        r = dice.roll_d6(1, "Enemy Plans: search the enemy ship") + \
            [1 if target.is_flagship else 0]
        if sum(r) >= 4:
            sp["done"] = True
            gs.add_log(f"[Sub-plot] Enemy Plans: player {player} captures the battle plans")
        _set(gs, player, sp)
    record_raid(gs, player, target)


def record_raid(gs, player: int, target) -> None:
    """A boarding action or hit-and-run attack on `target` (Secret
    Intelligence: the informant extracted)."""
    sp = get(gs, player)
    if sp and sp["key"] == "secret_intelligence" and sp.get("target") == target.id:
        sp["done"] = True
        _set(gs, player, sp)
        gs.add_log(f"[Sub-plot] Secret Intelligence: player {player} extracts the informant")


# --- AI: what a ship is worth to the sub-plots ------------------------------------
SUBPLOT_WEIGHT = 0.1     # judgement: a sub-plot objective ~ a tenth of the points on the table


def kill_bonus_vp(gs, ship) -> float:
    """VP-equivalent the sub-plots put on crippling or destroying `ship`:
    the target of a Vendetta, or of Secret Intelligence (reading: boarding it
    is the objective, but a ship destroyed can't be raided, so this only
    weights it), and our own Desperate Mission / Experimental Ship /
    Fleet Experience flagship, whose loss fails the objective. Used by the
    AI's damage and disengage values (`scenarios.kill_bonus_vp`)."""
    subs = getattr(gs, "subplots", None) or {}
    if not subs:
        return 0.0
    total = float(sum(s.points_value for s in gs.get_ships()) or 1000)
    v = 0.0
    for p, sp in subs.items():
        key = sp.get("key")
        if key == "vendetta" and sp.get("target") == ship.id:
            v += SUBPLOT_WEIGHT * total
        if key in ("desperate_mission", "experimental_ship") and sp.get("ship") == ship.id:
            v += SUBPLOT_WEIGHT * total
        if key == "fleet_experience" and ship.is_flagship and str(ship.player) == p:
            v += SUBPLOT_WEIGHT * total
        if key == "unexpected_help" and ship.id in sp.get("ships", []):
            # the objective needs one of them to survive: shared out (judgement)
            v += SUBPLOT_WEIGHT * total / max(1, len(sp.get("ships", [])))
    return v


# --- Objectives and the battle result -------------------------------------------

def _lost(ship) -> bool:
    return ship.is_destroyed or ship.damage_crippled


def objective_met(gs, player: int, won: bool) -> Optional[bool]:
    """Whether `player`'s sub-plot objective is met at the end of the game
    (None: no sub-plot)."""
    sp = get(gs, player)
    if not sp:
        return None
    key = sp["key"]
    ships = gs.get_ships()
    mine = [s for s in ships if s.player == player]
    theirs = [s for s in ships if s.player != player]
    by_id = {s.id: s for s in ships}
    if key == "gunnery_practice":
        return all(s.hits_remaining < s.hits_max or s.is_destroyed
                   for s in capital_ships(gs, 3 - player))
    if key == "extended_duty":
        return _points_lost(theirs) > _points_lost(mine)
    if key == "blood_bond":
        caps = capital_ships(gs, player)
        return sum(1 for s in caps if _lost(s)) * 2 < len(caps)
    if key == "fleet_experience":
        flag = next((s for s in mine if s.is_flagship), None)
        return bool(flag and not flag.is_destroyed and flag.hits_remaining * 4 >= flag.hits_max * 3)
    if key == "no_quarter":
        total = sum(s.points_value for s in theirs)
        return total > 0 and _points_lost(theirs) * 2 >= total
    if key == "vendetta":
        t = by_id.get(sp.get("target"))
        return bool(t and _lost(t))
    if key in ("meteor_storm", "navigational_hazards", "surprise_attack"):
        return won
    if key == "signaling_problems":
        esc = [s for s in mine if s.ship_type == "escort"]
        return sum(1 for s in esc if not s.is_destroyed) * 2 >= len(esc)
    if key in ("enemy_plans", "secret_intelligence"):
        return bool(sp.get("done"))
    if key == "fresh_captain":
        # The chosen ship must cripple or destroy enemy ships worth at least its
        # own points (reading: each ship once, at its full points, whether it
        # crippled or destroyed it; ordnance it launched counts)
        s = by_id.get(sp.get("ship"))
        if s is None:
            return False
        hit = {c["target"] for c in getattr(gs, "kill_credit", []) or [] if c["by"] == s.id}
        return sum(by_id[t].points_value for t in hit if t in by_id) >= s.points_value
    if key == "unexpected_help":
        return any(not _lost(by_id[i]) and not by_id[i].is_disengaged
                   for i in sp.get("ships", []) if i in by_id)
    if key in ("experimental_ship", "desperate_mission"):
        s = by_id.get(sp.get("ship"))
        return bool(s and not _lost(s))
    if key == "hit_and_run":
        game_turn = (gs.turn_number + 1) // 2 if getattr(gs, "turn_system", "igougo") != "aa" \
            else gs.turn_number
        return won and game_turn <= sp.get("turns", 0)
    return False          # Decoy: not judged (see UNBUILT)


def _points_lost(ships) -> float:
    """Points of ships destroyed (full) or crippled (their points, reading:
    "destroy/cripple more points of enemy ships than you lose" counts a
    crippled ship's whole value)."""
    return sum(s.points_value for s in ships if _lost(s))


RESULTS = {(True, True): "Heroic Victory!", (True, False): "Victory!",
           (False, True): "Heroic Defeat!", (False, False): "Miserable Defeat!"}


def battle_result(gs, player: int, winner: Optional[int]) -> Optional[Dict]:
    """The player's battle result with a sub-plot (p.80): main mission (the
    scenario won; reading: a draw is not a win) and sub-plot, with renown."""
    sp = get(gs, player)
    if not sp:
        return None
    won = winner == player
    met = bool(objective_met(gs, player, won))
    renown = sp["renown"][0] if met else sp["renown"][1]
    return {"sub_plot": sp["name"], "objective": met, "result": RESULTS[(won, met)],
            "renown": renown}
