"""The action layer (To do 18 item 7, To do 17): each kind of player action is
one engine function, called by the window, the AI and a replay alike, which
records one "act" event with what it needs to be done again exactly. A
replay calls the same function with the recorded inputs (dice from the roll
record, questions from ReplayPrompter), so a game with human players replays
like an AI's.

A replay repeats the depth-0 events (recorder: calls made directly by a
player, not inside another recorded call) through `replay_event`.

Built so far: the movement phase. Moves (apply_move: the AI's and every
human move path), ram declarations and rams after the move, boarding
declarations; the recorded engine calls it also replays: special orders
and their re-rolls, All Ahead Full speed rolls, marking a ship moved,
disengage tests. The shooting phase (the AI's so far; the Fire dialogs
next): each attack resolved and its hits applied by one action
(fire_weapons, fire_siege_cannons, fire_squadron_volley, fire_nova_cannon,
fire_area_weapon, fire_at_marker; apply_hits), Brace before an attack
(declare_brace), a ship done firing (mark_fired)."""
from . import recorder
from .movement import (MovementResult, MoveCommand, execute_movement,
                       record_staged_move)


def _result_data(result: MovementResult) -> dict:
    return {k: v for k, v in vars(result).items()}


def result_from(data: dict) -> MovementResult:
    """A recorded movement result, as it was applied."""
    r = MovementResult()
    for k, v in data.items():
        if k == "path":
            v = [tuple(p) for p in v]
        setattr(r, k, v)
    return r


@recorder.logged("act_move", lambda r, A: (A["gs"], dict(
    ship=A["ship"].id, result=_result_data(A["result"]),
    commands=[[c.action, c.value] for c in A["commands"] or []], on_aaf=A["on_aaf"],
    contacts=A["contacts"] is not None)))
def apply_move(gs, dice, ship, result: MovementResult, commands, on_aaf: bool,
               contacts=None, log=None):
    """Make a validated move: the ship moves (execute_movement), the ordnance
    it ran into attacks it (`contacts`, s.15; the AI's are resolved after its
    whole phase for now), the asteroid / warp rift / cloud tests it ran into
    (s.39), and its movement this phase is counted (staged moves).
    Returns the ship as it ends."""
    execute_movement(ship, result, gs, dice)
    if contacts is not None:
        contacts()
    from .terrain_effects import resolve_post_move_terrain
    if log is None:
        resolve_post_move_terrain(gs, ship.id, dice, on_aaf)
    else:
        resolve_post_move_terrain(gs, ship.id, dice, on_aaf, log=log)
    return record_staged_move(gs, ship.id, result, list(commands or []))


def commands_from(data) -> list:
    return [MoveCommand(a, v) for a, v in data]


def resolve_kill(gs, dice, ship_id: str, log=None):
    """A ship reduced to 0 rolls on the Catastrophic Damage table (an escort
    becomes a blast marker); one shared by the AI and the window."""
    ship = gs.get_ship_by_id(ship_id)
    if not ship or ship.hits_remaining > 0 or ship.status != "active":
        return None
    from .combat import resolve_catastrophic
    result = resolve_catastrophic(ship, dice, gs)
    if log:
        log(f"  {ship.name}: {result}")
    return result


@recorder.logged("declare_ram", lambda r, A: (A["gs"], dict(
    ship=A["ship_id"], target=A["target_id"], passed=r)))
def declare_ram(gs, dice, ship_id: str, target_id: str) -> bool:
    """Declare a ram on All Ahead Full, before the speed roll (s.12): the
    Leadership test (1D6 / 2D6 / 3D6 by size; Goffs pass), then the target is
    set. Returns whether the test passed."""
    from .combat import ram_ld_dice
    ship, target = gs.get_ship_by_id(ship_id), gs.get_ship_by_id(target_id)
    n = ram_ld_dice(ship.ship_type, target.ship_type)
    if "goffs" in ship.special_rules:
        passed = True
    else:
        total = sum(dice.roll_d6(n, f"{ship.name} ram Leadership test ({n}D6)"))
        passed = total <= ship.leadership
    if passed:
        ship.ramming_target_id = target.id
        gs.update_ship(ship)
    return passed


@recorder.logged("resolve_ram", lambda r, A: (A["gs"], dict(
    ship=A["ship_id"], start=list(A["start"]), hit=r)))
def resolve_declared_ram(gs, dice, ship_id: str, start, log=None) -> bool:
    """After the move: a declared ram connects if the path touched the
    target's base (resolve_ram; deferred to the end phase in alternate
    activation), the ships reduced to 0 roll catastrophic damage, and the
    ram target is cleared. Returns whether it connected."""
    from .geometry import line_passes_near
    from .combat import resolve_ram
    ship = gs.get_ship_by_id(ship_id)
    if ship is None or not ship.ramming_target_id:
        return False
    target = gs.get_ship_by_id(ship.ramming_target_id)
    hit = (target is not None and not target.is_destroyed and line_passes_near(
        start[0], start[1], ship.x, ship.y, target.x, target.y,
        ship.base_radius + target.base_radius))
    if hit:
        from .aa_turn import defer_ram
        if not defer_ram(gs, ship.id, target.id):
            resolve_ram(ship, target, dice, gs)
            for sid in (target.id, ship.id):
                resolve_kill(gs, dice, sid, log)
    elif target is not None and log:
        log(f"  {ship.name} missed the ram — {target.name} not contacted")
    ship = gs.get_ship_by_id(ship_id)
    if ship is not None:
        ship.ramming_target_id = None
        gs.update_ship(ship)
    return hit


@recorder.logged("declare_boarding", lambda r, A: (A["gs"], dict(
    ship=A["ship_id"], target=A["target_id"])))
def declare_boarding(gs, ship_id: str, target_id: str) -> None:
    """Declare a boarding action against a ship in base contact (s.32),
    resolved in the end phase (locked at once in alternate activation)."""
    ship = gs.get_ship_by_id(ship_id)
    ship.boarding_target_id = target_id
    ship.has_boarded = True
    gs.update_ship(ship)
    from .aa_turn import lock_boarding
    lock_boarding(gs, ship_id, target_id)


class ReplayDivergence(Exception):
    """A replayed action came out differently from the record."""


def replay_event(gs, tc, dice, ev: dict, contacts=None, panel=None) -> None:
    """Do a recorded depth-0 action again, with the same inputs (its dice come
    from the roll record). `contacts`: the flow's resolver for ordnance a
    moving ship touched, for moves that resolved it at once."""
    k = ev["kind"]
    ship = gs.get_ship_by_id(ev["ship"]) if "ship" in ev and ev["ship"] else None
    if k == "act_move":
        apply_move(gs, dice, ship, result_from(ev["result"]), commands_from(ev["commands"]),
                   ev["on_aaf"], contacts=contacts if ev.get("contacts") else None)
    elif k == "order":
        ships = [gs.get_ship_by_id(i) for i in ev["ships"]]
        res = (tc.issue_squadron_order(ships, ev["order"]) if ev.get("squadron")
               else tc.issue_special_order(ships[0], ev["order"]))
        _same(ev, "passed", res.get("success"))
    elif k == "order_reroll":
        _same(ev, "passed", tc.attempt_reroll_command_check(ship, ev["order"]).get("success"))
    elif k == "aaf":
        from .movement import resolve_aaf_speed, squadron_aaf_bonuses
        if "ships" in ev:
            squadron_aaf_bonuses([gs.get_ship_by_id(i) for i in ev["ships"]], dice)
        else:
            resolve_aaf_speed(ship, dice)
    elif k == "mark_moved":
        tc.mark_ship_moved(ev["ship"])
    elif k == "declare_ram":
        _same(ev, "passed", declare_ram(gs, dice, ev["ship"], ev["target"]))
    elif k == "resolve_ram":
        _same(ev, "hit", resolve_declared_ram(gs, dice, ev["ship"], ev["start"]))
    elif k == "declare_boarding":
        declare_boarding(gs, ev["ship"], ev["target"])
    elif k == "disengage":
        from .disengage import attempt_disengage
        _same(ev, "passed", attempt_disengage(ship, dice, gs, ev.get("forced", False)).get("success"))
    elif k == "reroll":
        tc.use_fleet_reroll(ev["player"], ship)
    elif k == "act_fire":
        fire_weapons(gs, dice, ev["ship"], ev["target"], ev["weapons"], ev["lock_on"],
                     marker_ids=ev.get("markers"), tag=ev.get("tag", ""))
    elif k == "act_siege":
        fire_siege_cannons(gs, dice, ev["ship"], ev["target"], ev["macro"], ev["bc"],
                           ev["lock_on"], tag=ev.get("tag", ""))
    elif k == "act_volley":
        fire_squadron_volley(gs, dice, ev["ship"], ev["firers"], ev["target"], ev.get("aspects"),
                             ev["lock_on"], marker_ids=ev.get("markers"), tag=ev.get("tag", ""))
    elif k == "act_nova":
        fire_nova_cannon(gs, dice, ev["ship"], ev["at"][0], ev["at"][1], tag=ev.get("tag", ""))
    elif k == "act_area":
        fire_area_weapon(gs, dice, ev["ship"], ev["what"])
    elif k == "act_fire_ordnance":
        fire_at_marker(gs, dice, ev["ship"], ev["weapon"], ev["marker"], ev["avail"])
    elif k == "act_hits":
        apply_hits(gs, dice, ev["target"], ev["hits"], ev["crit_on"], ev["attacker"],
                   bypass_hits=ev.get("bypass", 0), origin=ev.get("origin"),
                   tag=ev.get("tag", ""))
    elif k == "act_brace":
        _same(ev, "passed", declare_brace(gs, dice, ev["ship"], ev["attacker"],
                                          ev.get("group", ())).get("passed"))
    elif k == "brace":
        from .movement import attempt_brace
        _same(ev, "passed", attempt_brace(ship, gs, dice).get("passed"))
    elif k == "act_fired":
        mark_fired(tc, ev["ship"])
    elif k == "act_volley_fire":
        if panel is None:
            raise ReplayDivergence(f"event {ev['n']}: a Fire dialog volley needs the panel")
        fire_volley(panel, ev["ship"], ev["orders"], ev.get("together", False),
                    context=ev.get("context"))
    else:
        raise ReplayDivergence(f"event {ev['n']}: '{k}' can't be replayed yet")


def _same(ev, key, got):
    if ev.get(key) != got:
        raise ReplayDivergence(f"event {ev['n']} {ev['kind']}: recorded {key}={ev.get(key)}, "
                               f"the replay got {got}")


# --- Shooting (To do 18 / 17): each attack one action, for the AI and a replay ---------

def _ids(markers):
    return None if markers is None else [m.id for m in markers]


def _markers(gs, ids):
    """The blast markers an attack rolls against: those in play now (s.11:
    markers come into effect at once), or, for gunnery fired simultaneously,
    the ones that were in play before it (their ids)."""
    bms = gs.get_blast_markers()
    return bms if ids is None else [m for m in bms if m.id in set(ids)]


@recorder.logged("act_hits", lambda r, A: (A["gs"], dict(
    target=A["target_id"], hits=A["hits"], crit_on=A["crit_on"], attacker=A["attacker_id"],
    bypass=A["bypass_hits"], origin=A["origin"], tag=A["tag"])))
def apply_hits(gs, dice, target_id: str, hits: int, crit_on: int = 6, attacker_id: str = "",
               bypass_hits: int = 0, origin=None, log=None, tag: str = ""):
    """Hits from one attack applied to one ship (apply_damage: shields, Brace
    saves if it is braced, criticals), then a ship reduced to 0 rolls
    catastrophic damage. A hulk takes hits too (it re-rolls catastrophic
    damage). `origin`: where the attack came from (the attacker by default).
    Returns (hits left unused because the ship was destroyed, destroyed)."""
    from .combat import apply_damage
    from .models import SpecialOrder
    t = gs.get_ship_by_id(target_id)
    hulk = t is not None and t.status in ("drifting_hulk", "burning_hulk")
    if not t or (t.is_destroyed and not hulk):
        return hits, True
    braced = t.special_order == SpecialOrder.BRACE_FOR_IMPACT.value
    if origin is None and attacker_id:
        src = gs.get_ship_by_id(attacker_id)
        origin = (src.x, src.y) if src else None
    dmg = apply_damage(t, hits, dice, gs, target_braced=braced, crit_on=crit_on,
                       attacker_key=attacker_id, origin=tuple(origin) if origin else None,
                       bypass_hits=bypass_hits)
    if log:
        for c in dmg.get("crits") or []:
            log(f"{tag}  CRIT: {c}")
        if dmg.get("crippled"):
            log(f"{tag}  {t.name} CRIPPLED")
        if dmg.get("destroyed"):
            log(f"{tag}  {t.name} DESTROYED")
    resolve_kill(gs, dice, t.id)
    return dmg["unused_hits"], dmg["destroyed"]


def _hits_fn(gs, dice, crit_on, attacker_id, log, tag):
    return lambda m, n: apply_hits(gs, dice, m.id, n, crit_on, attacker_id, log=log, tag=tag)


@recorder.logged("act_fire", lambda r, A: (A["gs"], dict(
    ship=A["ship_id"], target=A["target_id"], weapons=list(A["w_idxs"]),
    lock_on=A["lock_on"], markers=A["marker_ids"], tag=A["tag"])))
def fire_weapons(gs, dice, ship_id: str, target_id: str, w_idxs, lock_on: bool,
                 marker_ids=None, log=None, tag: str = ""):
    """One attack at one target (s.13): the weapons' firepower fixed as they
    fire (random values rolled, Heavy Gunz by range: weapon_fire_pool), then
    macrobatteries of one gunnery type as ONE roll on their total firepower
    (resolve_battery_group), or one lance weapon; a target in a squadron is
    fired on as the squadron, hits nearest first (s.8). Hits applied
    (apply_hits), a Kustom Kannon's load spent. `marker_ids`: the blast
    markers from before, for gunnery types fired simultaneously.
    Returns the ShotResult."""
    from .combat import (weapon_fire_pool, shot_weapon, squadron_group, fire_at_squadron,
                         resolve_battery_group, resolve_lances, spend_kustom_kannon)
    log = log or gs.add_log
    ship, target = gs.get_ship_by_id(ship_id), gs.get_ship_by_id(target_id)
    weapons = [ship.weapons[i] for i in w_idxs]
    shots = []
    for i, w in zip(w_idxs, weapons):
        pool, _mode, _err = weapon_fire_pool(ship, w, i, ship.distance_to(target), dice, gs)
        if w.get("strength_dice"):
            log(f"{tag}{ship.name} {w['name']}: rolled {w['strength_dice']} = {pool}")
        shots.append(shot_weapon(w, pool))
    group = squadron_group(target, gs.get_ships())
    crit_on = weapons[0].get("crit_on", 6)
    hits_fn = _hits_fn(gs, dice, crit_on, ship.id, log, tag)
    phenomena = gs.get_phenomena()
    if weapons[0].get("weapon_type") == "battery":
        sr, applied = resolve_battery_group(
            ship, target, shots, dice, _markers(gs, marker_ids), lock_on, phenomena,
            gs.get_ships(), group=group, apply_hits=hits_fn)
        for w in weapons:
            if w.get("kustom_kannon"):
                spend_kustom_kannon(ship, w, gs)
    elif len(group) > 1:
        sr, applied = fire_at_squadron(ship, shots[0], target, group, dice, hits_fn, lock_on,
                                       _markers(gs, marker_ids), phenomena, gs.get_ships())
    else:
        sr, applied = resolve_lances(ship, target, shots[0], dice, lock_on=lock_on), None
    if applied is not None:
        log(f"{tag}{ship.name} → squadron {target.squadron_id}: "
            f"{sr.weapon_name or weapons[0]['name']} {sr.hits} hit(s)")
        return sr
    log(f"{tag}{ship.name} → {target.name}: {sr.weapon_name or weapons[0]['name']} "
        f"{sr.hits} hit(s)")
    if sr.hits > 0:
        apply_hits(gs, dice, target.id, sr.hits, crit_on, ship.id,
                   bypass_hits=sr.bypass_hits, log=log, tag=tag)
    return sr


@recorder.logged("act_siege", lambda r, A: (A["gs"], dict(
    ship=A["ship_id"], target=A["target_id"], macro=list(A["macro"]), bc=list(A["bc"]),
    lock_on=A["lock_on"], tag=A["tag"])))
def fire_siege_cannons(gs, dice, ship_id: str, target_id: str, macro, bc, lock_on: bool,
                       log=None, tag: str = ""):
    """Siege Cannons: macrobatteries and bombardment cannons in one lookup
    (resolve_siege_cannons), each kind's hits applied with its own crits."""
    from .combat import weapon_fire_pool, shot_weapon, resolve_siege_cannons
    log = log or gs.add_log
    ship, target = gs.get_ship_by_id(ship_id), gs.get_ship_by_id(target_id)
    shots = {}
    for i in list(macro) + list(bc):
        w = ship.weapons[i]
        pool, _m, _e = weapon_fire_pool(ship, w, i, ship.distance_to(target), dice)
        shots[i] = shot_weapon(w, pool)
    m_res, b_res = resolve_siege_cannons(
        ship, target, [shots[i] for i in macro], [shots[i] for i in bc], dice,
        gs.get_blast_markers(), lock_on, gs.get_phenomena(), gs.get_ships())
    log(f"{tag}{ship.name} → {target.name}: Siege Cannons {m_res.hits}+{b_res.hits} hit(s)")
    if m_res.hits:
        apply_hits(gs, dice, target.id, m_res.hits, 6, ship.id, log=log, tag=tag)
    if b_res.hits:
        apply_hits(gs, dice, target.id, b_res.hits, 4, ship.id, log=log, tag=tag)
    return m_res, b_res


@recorder.logged("act_volley", lambda r, A: (A["gs"], dict(
    ship=A["lead_id"], firers=[list(p) for p in A["firers"]], target=A["target_id"],
    aspects=A["aspects"], lock_on=A["lock_on"], markers=A["marker_ids"], tag=A["tag"])))
def fire_squadron_volley(gs, dice, lead_id: str, firers, target_id: str, aspects=None,
                         lock_on: bool = False, marker_ids=None, log=None, tag: str = ""):
    """Shooting by Squadrons (s.8): the firers' batteries ([ship id, weapon
    index]) as one planned volley at the target or its squadron
    (plan_squadron_volley; aspects "best": best_aspect_choice), rolled and
    applied nearest first. Returns {ship id: hits applied}."""
    from .combat import (plan_squadron_volley, resolve_squadron_volley, squadron_group,
                         best_aspect_choice)
    log = log or gs.add_log
    target = gs.get_ship_by_id(target_id)
    bms, phen, all_ships = _markers(gs, marker_ids), gs.get_phenomena(), gs.get_ships()
    group = squadron_group(target, all_ships)
    pairs = []
    for sid, i in firers:
        m = gs.get_ship_by_id(sid)
        pairs.append((m, m.weapons[i]))
    choice = (best_aspect_choice(pairs, group, bms, phen, all_ships)
              if aspects == "best" and len(group) > 1 else None)
    plan = plan_squadron_volley(pairs, group, bms, phen, all_ships, aspect_choice=choice)
    applied = resolve_squadron_volley(
        plan, group, dice,
        lambda t, n: apply_hits(gs, dice, t.id, n, 6, lead_id, log=log, tag=tag),
        lock_on=lock_on, game_state=gs)
    lead = gs.get_ship_by_id(lead_id)
    log(f"{tag}squadron {lead.squadron_id if lead else ''} combined batteries at "
        f"{target.name}: {sum(a['dice'] for a in plan['attacks'])} dice, "
        f"{sum(applied.values())} hit(s)")
    return applied


@recorder.logged("act_nova", lambda r, A: (A["gs"], dict(
    ship=A["ship_id"], at=[A["x"], A["y"]], tag=A["tag"])))
def fire_nova_cannon(gs, dice, ship_id: str, x: float, y: float, log=None, tag: str = ""):
    """The Nova Cannon aimed at (x, y) (s.14): the scatter, then each ship
    under the template takes its hits from where the template landed."""
    from .combat import resolve_nova_cannon
    log = log or gs.add_log
    ship = gs.get_ship_by_id(ship_id)
    nc = resolve_nova_cannon(ship, x, y, dice, gs)
    if "error" in nc:
        return nc
    log(f"{tag}{ship.name} nova cannon at ({x:.0f},{y:.0f})")
    for sid, hd in nc.get("ship_hits", {}).items():
        apply_hits(gs, dice, sid, hd["hits"], 6, ship.id,
                   origin=(nc["template_x"], nc["template_y"]), log=log, tag=tag)
    # s.14: no ship hit, a blast marker under the centre of the template
    from .models import BlastMarker
    for bx, by in nc.get("blast_markers", []):
        gs.add_blast_marker(BlastMarker(id=f"nova_miss_{gs.next_serial()}", x=bx, y=by,
                                        source="nova_cannon_miss"))
    return nc


@recorder.logged("act_area", lambda r, A: (A["gs"], dict(ship=A["ship_id"], what=A["what"])))
def fire_area_weapon(gs, dice, ship_id: str, what: str):
    """A weapon with no target to pick: a Necron star pulse generator or the
    Armageddon Gun; ships it reduced to 0 roll catastrophic damage."""
    from .combat import resolve_star_pulse, resolve_armageddon_gun
    ship = gs.get_ship_by_id(ship_id)
    res = (resolve_star_pulse if what == "star_pulse" else resolve_armageddon_gun)(ship, gs, dice)
    for sid in res.get("hits", {}):
        resolve_kill(gs, dice, sid)
    return res


@recorder.logged("act_fire_ordnance", lambda r, A: (A["gs"], dict(
    ship=A["ship_id"], weapon=A["w_idx"], marker=A["marker_id"], avail=A["avail"])))
def fire_at_marker(gs, dice, ship_id: str, w_idx: int, marker_id: str, avail: int):
    """A weapon fired at an enemy ordnance marker (s.30, fire_at_ordnance)."""
    from .combat import fire_at_ordnance
    ship = gs.get_ship_by_id(ship_id)
    return fire_at_ordnance(ship, ship.weapons[w_idx], marker_id, gs, dice, avail)


@recorder.logged("act_brace", lambda r, A: (A["gs"], dict(
    ship=A["target_id"], attacker=A["attacker_key"], group=list(A["group_ids"]),
    passed=r["passed"])))
def declare_brace(gs, dice, target_id: str, attacker_key: str, group_ids=()) -> dict:
    """Brace for Impact before an attack (s.7): the command check; passed,
    the target's whole squadron is braced (s.8); failed, none of them may try
    again against this attacker this turn. Returns the command check."""
    from .movement import attempt_brace
    from .models import SpecialOrder
    target = gs.get_ship_by_id(target_id)
    check = attempt_brace(target, gs, dice)
    others = [i for i in group_ids if i != target_id]
    if check["passed"]:
        for i in others:
            m = gs.get_ship_by_id(i)
            if m and m.special_order != SpecialOrder.BRACE_FOR_IMPACT.value:
                m.previous_order = m.special_order
                m.special_order = SpecialOrder.BRACE_FOR_IMPACT.value
                m.brace_set_on_turn = gs.turn_number
                gs.update_ship(m)
    else:
        for i in [target_id] + others:
            m = gs.get_ship_by_id(i)
            if m:
                m.brace_failed_vs = list(m.brace_failed_vs or []) + [attacker_key]
                gs.update_ship(m)
    return check


@recorder.logged("act_fired", lambda r, A: (A["tc"].gs, dict(ship=A["ship_id"])))
def mark_fired(tc, ship_id: str) -> None:
    """A ship has finished its shooting this phase."""
    gs = tc.gs
    ship = gs.get_ship_by_id(ship_id)
    if ship is not None and not ship.has_fired:
        ship.has_fired = True
        gs.update_ship(ship)
    tc.mark_ship_fired(ship_id)


@recorder.logged("act_volley_fire", lambda r, A: (A["panel"].ctx.gs, dict(
    ship=A["ship_id"], orders=[list(o) for o in A["orders"]], together=A["together"],
    context=A["context"])))
def fire_volley(panel, ship_id: str, orders, together: bool = False, log=None,
                context=None):
    """A player's volley from the Fire dialog (fire_volley.FireVolley): orders
    [[weapon index, target id or None, firepower or None], ...]; together:
    different gunnery types fire simultaneously (s.13); context: what the
    dialog was opened with (the closest visible enemy for target priority,
    Lock On, an asteroid field, the enemies on offer)."""
    from .fire_volley import FireVolley
    FireVolley(panel, ship_id, [tuple(o) for o in orders], together, log=log,
               context=context).run()
