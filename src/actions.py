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
disengage tests."""
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


def replay_event(gs, tc, dice, ev: dict, contacts=None) -> None:
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
    else:
        raise ReplayDivergence(f"event {ev['n']}: '{k}' can't be replayed yet")


def _same(ev, key, got):
    if ev.get(key) != got:
        raise ReplayDivergence(f"event {ev['n']} {ev['kind']}: recorded {key}={ev.get(key)}, "
                               f"the replay got {got}")
