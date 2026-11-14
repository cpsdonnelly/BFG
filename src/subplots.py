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

# Faction sub-plots, taken in addition to the rolled one (`faction_subplot`):
# the Adeptus Mechanicus Quest for Knowledge (02_adeptus-mechanicus.md) and the
# Rogue Trader Business as Usual table (05_rogue-traders.md). Quest entries
# reuse the core effects they repeat (`extra` narrows them to Mechanicus ships).
QUEST = {
    1: ("extended_duty", "Extended Duty (Quest)", (1, 0), {"mech_only": True, "vc": "count"}),
    2: ("meteor_storm", "Xenos Logic Engine", (2, -1), {"mech_only": True}),
    3: ("decoy", "Mimic Drive", (1, -1), {}),
    4: ("desperate_mission", "Sacred Vessel", (1, -1), {"mech_only": True}),
    5: ("vendetta", "The Prize", (1, -2), {}),
    6: ("mech_experimental", "Experimental Ship (Quest)", (1, -1), {"mech_only": True}),
}
BUSINESS = {
    1: ("trooping_the_colour", "Trooping the Colour", (2, -1)),
    2: ("punitive_strike", "Punitive Strike", (1, -1)),
    3: ("colony_settlement", "Colony Settlement", (0, -1)),
    4: ("reclamation_crusade", "Reclamation Crusade", (1, 0)),
    5: ("expeditionary_group", "Expeditionary Group", (1, -1)),
    6: ("treasure_haul", "Treasure Haul", (1, -2)),
}
RT_CONVOY_CLASSES = ("Sloop", "Caravel", "Carrack")

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


def _slot(player: int, sp: Dict) -> str:
    return f"{player}:{sp['slot']}" if sp.get("slot") else str(player)


def _set(gs, player: int, sp: Dict) -> None:
    subs = dict(getattr(gs, "subplots", None) or {})
    subs[_slot(player, sp)] = sp
    gs.subplots = subs


def get(gs, player: int) -> Optional[Dict]:
    return (getattr(gs, "subplots", None) or {}).get(str(player))


def all_for(gs, player: int) -> List[Dict]:
    """Every sub-plot the player has: the rolled one and a faction one."""
    subs = getattr(gs, "subplots", None) or {}
    return [sp for k, sp in sorted(subs.items()) if k.split(":")[0] == str(player)]


def has(gs, player: int, key: str) -> Optional[Dict]:
    return next((sp for sp in all_for(gs, player) if sp["key"] == key), None)


def _main_faction(gs, player: int) -> Optional[str]:
    from .scenarios import _main_faction as mf
    return mf(gs, player)


def rt_convoy(ship) -> bool:
    """A Rogue Trader sloop, caravel or carrack (Business as Usual)."""
    return ship.faction == "rogue_traders" and any(c in ship.ship_class
                                                   for c in RT_CONVOY_CLASSES)


def faction_subplot(gs, player: int, dice) -> Optional[Dict]:
    """The faction sub-plot a fleet must take besides the rolled one: an
    Adeptus Mechanicus fleet (reading: any fleet whose main faction is the
    Mechanicus, ships don't carry their list) the Quest for Knowledge; a fleet
    with Rogue Trader convoy ships the Business as Usual table, unless the
    scenario already scores its convoy ships (Convoy / Navigate the Storm /
    narrative Convoy defender, Planetary Assault attacker); an Ordo Malleus
    fleet led by an Inquisitor Lord a random Secret Ploys sub-plot."""
    from .scenarios import defender
    ships = [s for s in gs.get_ships() if s.player == player]
    mode = getattr(gs, "scenario_mode", "")
    if _main_faction(gs, player) == "adeptus_mechanicus":
        n = dice.roll_d6(1, f"Player {player} Quest for Knowledge (D6)")[0]
        key, name, renown, extra = QUEST[n]
        sp = {"key": key, "name": name, "renown": list(renown), "table": "quest", **extra}
    elif any(s.faction == "rogue_traders" and any(r.startswith("transport:")
                                                  for r in s.special_rules) for s in ships) \
            and not ((mode in ("convoy_matched", "navigate_storm", "convoy_narrative", "gauntlet")
                      and player == defender(gs))
                     or (mode in ("planetary_assault", "craftworld_assault")
                         and player == gs.scenario_attacker)):
        n = dice.roll_d6(1, f"Player {player} Business as Usual (D6)")[0]
        key, name, renown = BUSINESS[n]
        sp = {"key": key, "name": name, "renown": list(renown), "table": "business"}
    elif any("Inquisitor Lord" in u for s in ships for u in (s.upgrades or [])):
        n = dice.roll_d6(1, f"Player {player} Secret Ploys (Inquisitor Lord)")[0]
        key, name, renown = TABLES["ploys"][n]
        sp = {"key": key, "name": name, "renown": list(renown), "table": "ploys"}
    else:
        return None
    sp["slot"] = "faction"
    if key in UNBUILT:
        sp["unbuilt"] = UNBUILT[key]
    return sp


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
    if sp.get("mech_only"):
        own = [s for s in own if s.faction == "adeptus_mechanicus"]
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
                if roll_critical_hit(s, dice, gs):
                    # Its extra damage destroyed it (reading: destroyed before the
                    # battle, no catastrophic roll since it isn't on the table)
                    s.hits_remaining, s.status = 0, "destroyed"
                    logs.append(f"  {s.name} is destroyed by the meteor storm")
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
    elif key == "mech_experimental":
        cruisers = [s for s in own if s.ship_type == "cruiser"] or own
        if cruisers:
            i = dice.roll_d6(1, "Experimental Ship (Quest): which cruiser")[0]
            s = cruisers[(i - 1) % len(cruisers)]
            sp["ship"] = s.id
            imp = _mech_roll(dice, s, "improvement")
            side = _mech_roll(dice, s, "side effect")
            _mech_experiment(s, imp, side)
            gs.update_ship(s)
            sp["improvement"], sp["side_effect"] = imp, side
            logs.append(f"  {s.name}: improvement {imp}, side effect {side}")
    elif key in BUSINESS_KEYS:
        _business_setup(gs, player, sp, dice, logs)
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
    sp = has(gs, ship.player, "fleet_experience") or has(gs, ship.player, "blood_bond")
    if not sp:
        return ld
    if has(gs, ship.player, "fleet_experience"):
        flag = _flagship(gs, ship.player)
        if flag is not None and flag.id != ship.id and ship.distance_to(flag) <= COMMAND_RANGE:
            ld = max(ld, flag.leadership)
    bond = has(gs, ship.player, "blood_bond")
    if (bond and bond.get("bond_turn") == gs.turn_number
            and ship.ship_type != "escort" and not _lost(ship)):
        ld = min(10, ld + 1)
    return ld


def reroll_blocked(gs, player: int, ship) -> bool:
    """Signaling Problems: fleet commander re-rolls only for squadrons with a
    ship within 30cm of the commander's ship (reading: single ships too, a
    ship being its own squadron)."""
    if not has(gs, player, "signaling_problems") or ship is None:
        return False
    return not _near_commander(gs, ship)


def turn_start(gs, player: int) -> None:
    """Blood Bond: at the start of the player's turn, if one of its capital
    ships was crippled or destroyed since its last turn, the others gain +1 Ld
    for this turn (reading: "the next turn" is the player's next turn)."""
    sp = has(gs, player, "blood_bond")
    if not sp:
        return
    lost = sum(1 for s in capital_ships(gs, player) if _lost(s))
    if lost > sp.get("lost_seen", 0):
        sp = dict(sp)
        sp["lost_seen"] = lost
        sp["bond_turn"] = gs.turn_number
        _set(gs, player, sp)
        gs.add_log(f"[Sub-plot] Blood Bond: player {player}'s capital ships are at +1 Ld "
                   f"this turn")


def _lances_dorsal_prow(s) -> List[Dict]:
    return [w for w in s.weapons if w.get("weapon_type") == "lance"
            and (str(w.get("name", "")).startswith(("Dorsal", "Prow"))
                 or (w.get("location") or "").lower() in ("dorsal", "prow"))]


def _mech_roll(dice, s, table: str) -> int:
    """A Mechanicus Experimental Ship roll, re-rolled when it can't be applied
    (the lance results without dorsal or prow lances)."""
    while True:
        r = dice.roll_d6(1, f"Experimental Ship (Quest) {table}")[0]
        if r == 6 and not _lances_dorsal_prow(s):
            continue
        return r


def _mech_experiment(s, imp: int, side: int) -> None:
    """The Quest for Knowledge Experimental Ship tables (02_adeptus-mechanicus)."""
    direct = [w for w in s.weapons if w.get("weapon_type") in ("battery", "lance")]
    if imp == 1:
        for w in direct:
            w["range_cm"] = int(w.get("range_cm", 0)) + 15
    elif imp == 2:
        s.shields_max += 1
    elif imp == 3:
        s.special_rules = list(s.special_rules) + ["turret_reroll"]
    elif imp == 4:
        s.turn_angle = 90
    elif imp == 5:
        s.special_rules = list(s.special_rules) + ["mech_ld_aura"]
    elif imp == 6:
        for w in _lances_dorsal_prow(s):
            w["shield_bypass_6"] = True
    if side == 1:
        for w in direct:
            w["strength"] = (int(w.get("strength", 0)) + 1) // 2
    elif side == 2:
        s.hits_max = max(1, s.hits_max - 2)
        s.hits_remaining = min(s.hits_remaining, s.hits_max)
    elif side == 3:
        s.turrets = max(0, s.turrets - 2)
    elif side == 4:
        s.special_rules = list(s.special_rules) + ["turn_distance_plus5"]
    elif side == 5:
        s.speed = max(5, s.speed - 5)
    elif side == 6:
        for w in _lances_dorsal_prow(s):
            w["hits_on"] = 6


def mech_ld_aura(gs, ship) -> int:
    """Experimental Ship (Quest) improvement 5: friendly ships within 15cm
    of it gain +1 Ld against enemies on special orders (with Enemy
    Contacts, reading), max 10."""
    if gs is None:
        return 0
    return 1 if any("mech_ld_aura" in s.special_rules and s.player == ship.player
                    and not s.is_destroyed and s.distance_to(ship) <= 15.0
                    for s in gs.get_ships() if s.id != ship.id) else 0


# --- Business as Usual (Rogue Traders) ------------------------------------------------
BUSINESS_KEYS = {v[0] for v in BUSINESS.values()}


def _business_setup(gs, player: int, sp: Dict, dice, logs: List[str]) -> None:
    from .scenarios import transport
    mine = [s for s in gs.get_ships() if s.player == player and rt_convoy(s)]
    key = sp["key"]
    if key == "punitive_strike":
        sp["capacity"] = sum(transport(s, building=True) for s in gs.get_ships()
                             if s.player == player and any(r.startswith("transport:")
                                                           for r in s.special_rules))
    elif key == "reclamation_crusade":
        for s in mine:
            for w in s.weapons:
                if w.get("weapon_type") in ("battery", "lance"):
                    w["range_cm"] = max(30, int(w.get("range_cm", 0)))
            gs.update_ship(s)
        logs.append("  sloops, caravels and carracks fire to 30cm")
    elif key == "expeditionary_group":
        sp["surveyed"] = []
    elif key == "treasure_haul" and mine:
        i = dice.roll_d6(1, "Treasure Haul: the ship carrying the treasure (secret)")[0]
        sp["holder"] = mine[(i - 1) % len(mine)].id
        sp["revealed"] = False
        logs.append("  the treasure is aboard one of the sloops / caravels / carracks")


def punitive_target(gs, attacker, candidates) -> Optional[object]:
    """Punitive Strike: enemy direct fire must target one of our sloops,
    caravels or carracks if possible, unless it passes a target priority test:
    the nearest such ship among `candidates` (the weapon's valid targets)."""
    marked = [c for c in candidates if rt_convoy(c) and has(gs, c.player, "punitive_strike")
              and c.player != attacker.player and not c.is_destroyed and not c.is_disengaged]
    return min(marked, key=attacker.distance_to, default=None)


def record_survey(gs, ship, path) -> None:
    """Expeditionary Group: a sloop, caravel or carrack touching an
    un-surveyed feature along its move marks it surveyed."""
    sp = has(gs, ship.player, "expeditionary_group")
    if not sp or not rt_convoy(ship):
        return
    from .terrain_effects import check_ship_terrain_contact
    from .models import Ship
    done = set(sp.get("surveyed", []))
    probe = Ship.from_dict(ship.to_dict())
    phen = gs.get_phenomena()
    new = []
    for (x, y) in path:
        probe.x, probe.y = x, y
        for c in check_ship_terrain_contact(probe, phen):
            pid = getattr(c.get("phenomenon"), "id", None)
            if pid and pid not in done:
                done.add(pid)
                new.append(pid)
        for p in phen:
            if "planet" in p.phenomenon_type and p.id not in done and \
                    ((x - p.x) ** 2 + (y - p.y) ** 2) ** 0.5 <= p.radius + ship.base_radius:
                done.add(p.id)
                new.append(p.id)
    if new:
        sp = dict(sp)
        sp["surveyed"] = sorted(done)
        _set(gs, ship.player, sp)
        gs.add_log(f"[Sub-plot] Expeditionary Group: {ship.name} surveys {len(new)} feature(s)")


def _treasure_event(gs, player: int, target) -> None:
    """A boarding action or hit-and-run raid by `player` on `target`: a
    sloop / caravel / carrack reveals whether it carries the treasure; the
    treasure's holder (once known) loses it to the attacker (reading: the
    attacking player's nearest ship, with launch bays if any, stands for the
    ship that made the attack)."""
    for owner in (1, 2):
        sp = has(gs, owner, "treasure_haul")
        if not sp or sp.get("holder") != target.id:
            continue
        if not (rt_convoy(target) or sp.get("revealed")):
            continue
        ships = [s for s in gs.get_ships() if s.player == player and not s.is_destroyed
                 and not s.is_disengaged]
        if not ships:
            continue
        carriers = [s for s in ships if any(w.get("weapon_type") == "launch_bay"
                                            for w in s.weapons)]
        taker = min(carriers or ships, key=target.distance_to)
        sp = dict(sp)
        sp["holder"], sp["revealed"] = taker.id, True
        _set(gs, owner, sp)
        gs.add_log(f"[Sub-plot] Treasure Haul: the treasure was aboard {target.name}; "
                   f"{taker.name} takes it")


def treasure_controller(gs, sp: Dict) -> Optional[int]:
    """Who controls the treasure at the end: the player of the ship carrying
    it; a hulk's goes to the player holding the field; destroyed, lost."""
    from .victory_points import _holds_field
    s = gs.get_ship_by_id(sp.get("holder", ""))
    if s is None or s.is_destroyed:
        return None
    if s.status in ("drifting_hulk", "burning_hulk"):
        for p in (1, 2):
            if _holds_field(p, gs.get_ships()):
                return p
        return None
    return s.player


def vp_bonus(gs, result: Dict) -> None:
    """Business as Usual victory points: Trooping the Colour doubles what the
    enemy scores for our sloops / caravels / carracks; Colony Settlement
    replaces it (boarded or raided to death: the enemy gets their cost;
    otherwise whoever destroyed it loses their cost); Expeditionary Group +50
    a surveyed feature; Treasure Haul 1000 to the player controlling it."""
    for p in (1, 2):
        enemy = 3 - p
        for sp in all_for(gs, p):
            key = sp["key"]
            if key == "trooping_the_colour":
                for s in gs.get_ships():
                    if s.player != p or not rt_convoy(s):
                        continue
                    v = s.points_value if s.is_destroyed else (
                        s.points_value // 4 if s.damage_crippled else 0)
                    if v:
                        result[enemy]["scenario"] = result[enemy].get("scenario", 0) + v
                        result[enemy]["details"].append(f"Trooping the Colour: {s.name} "
                                                        f"counts double: +{v} VP")
            elif key == "colony_settlement":
                raided = set(sp.get("raided", []))
                for s in gs.get_ships():
                    if s.player != p or not rt_convoy(s) or not s.is_destroyed:
                        continue
                    if s.id in raided:
                        result[enemy]["scenario"] = result[enemy].get("scenario", 0) + s.points_value
                        result[enemy]["details"].append(f"Colony Settlement: {s.name} taken "
                                                        f"by boarding / raid: +{s.points_value}")
                        continue
                    by = next((c["by"] for c in getattr(gs, "kill_credit", []) or []
                               if c["target"] == s.id and c["kind"] == "destroyed"), None)
                    shooter = gs.get_ship_by_id(by) if by else None
                    if shooter is not None:
                        q = shooter.player
                        result[q]["scenario"] = result[q].get("scenario", 0) - s.points_value
                        result[q]["details"].append(f"Colony Settlement: {s.name} destroyed: "
                                                    f"-{s.points_value} VP")
            elif key == "expeditionary_group":
                n = len(sp.get("surveyed", []))
                if n:
                    result[p]["scenario"] = result[p].get("scenario", 0) + 50 * n
                    result[p]["details"].append(f"Expeditionary Group: {n} feature(s) "
                                                f"surveyed: +{50 * n} VP")
            elif key == "treasure_haul":
                q = treasure_controller(gs, sp)
                if q:
                    result[q]["scenario"] = result[q].get("scenario", 0) + 1000
                    result[q]["details"].append("Treasure Haul: the treasure: +1000 VP")


def scores_normally(gs, ship) -> bool:
    """Colony Settlement's sloops, caravels and carracks are scored only by
    `vp_bonus`."""
    return not (rt_convoy(ship) and has(gs, ship.player, "colony_settlement"))


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
    sp = has(gs, 3 - ship.player, "surprise_attack")
    if sp:
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
    sp = has(gs, player, "enemy_plans")
    if sp and target.ship_type != "escort" and not sp.get("done"):
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
    sp = has(gs, player, "secret_intelligence")
    if sp and sp.get("target") == target.id:
        sp["done"] = True
        _set(gs, player, sp)
        gs.add_log(f"[Sub-plot] Secret Intelligence: player {player} extracts the informant")
    col = has(gs, target.player, "colony_settlement")
    if col and rt_convoy(target):
        col = dict(col)
        col["raided"] = sorted(set(col.get("raided", [])) | {target.id})
        _set(gs, target.player, col)
    _treasure_event(gs, player, target)


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
        if key == "fleet_experience" and ship.is_flagship and str(ship.player) == p.split(":")[0]:
            v += SUBPLOT_WEIGHT * total
        if key == "trooping_the_colour" and rt_convoy(ship) and str(ship.player) == p.split(":")[0]:
            v += ship.points_value              # they count double
        if key == "colony_settlement" and rt_convoy(ship) and str(ship.player) == p.split(":")[0]:
            v -= 2.0 * ship.points_value        # destroying one costs the shooter its cost
        if key == "treasure_haul" and sp.get("holder") == ship.id and sp.get("revealed"):
            v += 0.5 * 1000                     # judgement: losing it with the ship
        if key == "unexpected_help" and ship.id in sp.get("ships", []):
            # the objective needs one of them to survive: shared out (judgement)
            v += SUBPLOT_WEIGHT * total / max(1, len(sp.get("ships", [])))
    return v


# --- Objectives and the battle result -------------------------------------------

def _lost(ship) -> bool:
    return ship.is_destroyed or ship.damage_crippled


def objective_met(gs, player: int, won: bool, sp: Optional[Dict] = None) -> Optional[bool]:
    """Whether `player`'s sub-plot objective is met at the end of the game
    (None: no sub-plot). `sp`: one of its sub-plots (default the rolled one)."""
    sp = sp or get(gs, player)
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
    if key == "extended_duty" and sp.get("vc") == "count":
        # Quest for Knowledge: more enemy ships crippled / destroyed than ours
        return sum(1 for s in theirs if _lost(s)) > sum(1 for s in mine if _lost(s))
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
    if key in BUSINESS_KEYS:
        return _business_met(gs, player, sp, mine, theirs)
    if key in ("experimental_ship", "desperate_mission", "mech_experimental"):
        s = by_id.get(sp.get("ship"))
        return bool(s and not _lost(s))
    if key == "hit_and_run":
        game_turn = (gs.turn_number + 1) // 2 if getattr(gs, "turn_system", "igougo") != "aa" \
            else gs.turn_number
        return won and game_turn <= sp.get("turns", 0)
    return False          # Decoy: not judged (see UNBUILT)


def _business_met(gs, player: int, sp: Dict, mine, theirs) -> bool:
    from .scenarios import transport
    from .victory_points import _holds_field
    key = sp["key"]
    convoy = [s for s in mine if rt_convoy(s)]
    if key == "trooping_the_colour":
        alive = any(not s.is_destroyed and not (s.ship_type != "escort" and s.damage_crippled)
                    for s in convoy)
        scored = sum(2 * (s.points_value if s.is_destroyed else
                          (s.points_value // 4 if s.damage_crippled else 0)) for s in convoy)
        limit = sum(s.points_value for s in theirs)
        return alive and scored <= 0.1 * limit
    if key == "punitive_strike":
        left = sum(transport(s, building=True) for s in mine if not s.is_destroyed
                   and any(r.startswith("transport:") for r in s.special_rules))
        return left * 2 >= sp.get("capacity", 0)
    if key == "colony_settlement":
        return any(not s.is_destroyed for s in convoy) and \
            not _holds_field(3 - player, gs.get_ships())
    if key == "reclamation_crusade":
        ids = {s.id for s in convoy}
        killed = [gs.get_ship_by_id(c["target"]) for c in getattr(gs, "kill_credit", []) or []
                  if c["by"] in ids and c["kind"] == "destroyed"]
        killed = [k for k in killed if k is not None]
        return any(k.ship_type != "escort" for k in killed) or \
            sum(1 for k in killed if k.ship_type == "escort") >= 6
    if key == "expeditionary_group":
        n = len(gs.get_phenomena())
        return n > 0 and len(sp.get("surveyed", [])) * 2 >= n
    if key == "treasure_haul":
        return treasure_controller(gs, sp) == player
    return False


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
    sps = all_for(gs, player)
    if not sps:
        return None
    won = winner == player
    mets = [bool(objective_met(gs, player, won, sp)) for sp in sps]
    met = all(mets)          # reading: a heroic result needs every sub-plot met
    renown = sum(sp["renown"][0] if m else sp["renown"][1] for sp, m in zip(sps, mets))
    return {"sub_plot": " + ".join(sp["name"] for sp in sps), "objective": met,
            "result": RESULTS[(won, met)], "renown": renown}
