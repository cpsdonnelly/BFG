"""Every kind of ordnance from every faction (owner request): for each
playable catalog ship with torpedoes, launch bays or mine launchers (and the
options that add or change ordnance), every load it can launch (each torpedo
kind, each attack craft type, CAP, mines) goes through the recorded launch
actions, then one ordnance phase moves and resolves it against an enemy ship
ahead. Replayed from the record (the launch actions again, the flow's own
resolution again), the game ends in the same state, and the launch put
ordnance on the table.

The full sweep (~4,600 cases, ~70s) runs with BFG_SWEEP=1: after any change
to ordnance and before a merge. By default one case per faction, kind of
launch and load runs (owner: keep the everyday suite lean)."""
import json
import os

import pytest

from src import recorder, actions
from src.dice import DiceRoller, DiceSource, set_source, current_source
from src.game_state import GameState
from src.headless_game import HeadlessGame
from src.models import Ship
from src.ordnance import torpedo_kind_options, craft_roles, craft_stats, EXTRA_TORPEDO_TYPES
from src.ship_catalog import (list_factions, get_faction_ships, find_ship_class,
                              get_upgrades_for_ship, apply_upgrade_effect)
from src.turn_controller import TurnController

ORD_TYPES = ("torpedo", "launch_bay", "mine_launcher")


def _ord_profile(d):
    return json.dumps([w for w in d["weapons"] if w.get("weapon_type") in ORD_TYPES],
                      sort_keys=True) + "|" + ",".join(sorted(
                          r for r in d["special_rules"] if r.startswith("torpedo")))


def _variants(entry):
    """The ship as listed, and once per option that changes its ordnance."""
    base = entry.to_ship_dict(entry.ship_class, 1, ship_id="me")
    out = [("", base)]
    seen = {_ord_profile(base)}
    for up in get_upgrades_for_ship(entry):
        d = json.loads(json.dumps(base))
        try:
            apply_upgrade_effect(d, up.effect)
        except Exception:                 # noqa: BLE001 (an option needing a fleet context)
            continue
        key = _ord_profile(d)
        if key not in seen:
            seen.add(key)
            out.append((up.name, d))
    return out


def _cases():
    cases = []
    for faction in list_factions():
        for entry in get_faction_ships(faction):
            for opt, d in _variants(entry):
                ship = Ship.from_dict(d)
                for i, w in enumerate(ship.weapons):
                    wt = w.get("weapon_type")
                    if wt == "torpedo":
                        kinds = {k for k, _l in torpedo_kind_options(ship, w, True)}
                        if w.get("torpedo_type") != "guided":
                            kinds |= set(EXTRA_TORPEDO_TYPES)     # every bought / rolled load
                        for k in sorted(kinds):
                            cases.append((entry.ship_class, opt, "torp", i, k))
                    elif wt == "launch_bay":
                        for ct in w.get("craft_types", []):
                            cases.append((entry.ship_class, opt, "craft", i, ct))
                            if "fighter" in craft_roles(ct):
                                cases.append((entry.ship_class, opt, "cap", i, ct))
                    elif wt == "mine_launcher":
                        cases.append((entry.ship_class, opt, "mines", i, ""))
    return cases


SWEEP = os.environ.get("BFG_SWEEP") == "1"


def _sample(cases, key):
    seen, out = set(), []
    for c in cases:
        k = key(c)
        if k not in seen:
            seen.add(k)
            out.append(c)
    return out


CASES = _cases()
if not SWEEP:
    CASES = _sample(CASES, lambda c: (find_ship_class(c[0]).faction, c[2], c[4]))


def _setup(cls, opt, kind, load):
    entry = find_ship_class(cls)
    d = dict(_variants(entry))[opt]
    d = json.loads(json.dumps(d))
    if kind == "torp" and load in EXTRA_TORPEDO_TYPES:
        d["special_rules"].append(f"torpedo_type:{load}")
    d.update(x=40.0, y=45.0, heading=0.0, leadership=8)
    gs = GameState(game_name="ord", game_seed=5)
    gs.table_width, gs.table_height, gs.dice_mode = 180.0, 120.0, "auto"
    gs.rule_hit_and_run = True
    gs.ai_spectator = True
    gs.add_ship(Ship.from_dict(d))
    t = find_ship_class("Lunar Class Cruiser").to_ship_dict("Lunar Class Cruiser", 2,
                                                            ship_id="foe")
    t.update(x=58.0, y=45.0, heading=180.0, leadership=8)     # within every craft's move
    gs.add_ship(Ship.from_dict(t))
    gs.current_phase, gs.active_player, gs.turn_number = "ordnance", 1, 1
    tc = TurnController(gs, DiceRoller(mode="auto"), save_dir=None)
    recorder.set_current_gs(gs)
    game = HeadlessGame(tc)
    return gs, game


def _launch(gs, game, kind, w_idx, load):
    dice = game.ctx.dice
    ship = gs.get_ship_by_id("me")
    w = ship.weapons[w_idx]
    if kind == "torp":
        return actions.launch_torpedo_volley(gs, dice, "me", w_idx, 0.0, None, None, load,
                                             w.get("strength", 0) or 1)
    if kind == "mines":
        return actions.lay_ship_mines(gs, "me", w_idx)
    return actions.launch_bays(gs, dice, "me", [w_idx], 0.0, [[load, "1"]], kind == "cap",
                               "me", ship.name, {"lone": "0", "cap": "0"}, None, True,
                               "close", 9)


def _state(gs):
    return json.dumps({"ships": gs.ships, "ordnance": gs.ordnance, "bm": gs.blast_markers},
                      sort_keys=True, default=str)


def _play(cls, opt, kind, w_idx, load, source):
    set_source(source)
    recorder.start_recording()
    gs, game = _setup(cls, opt, kind, load)
    replay = source.replay is not None
    if replay:
        for e in _play.events:
            if e["depth"] == 0 and e["seat"] and e["turn"] == 1:
                actions.replay_event(gs, game.ctx.tc, game.ctx.dice, e, panel=game.combat)
    else:
        _launch(gs, game, kind, w_idx, load)
        _play.events = [e for e in recorder.events()]
    launched = len(gs.ordnance)
    with recorder.flow():
        game.ordnance._resolve_ordnance_movement()
    # The next turn: torpedo bombers / Tiger Sharks fire their salvos (s.21),
    # then ordnance moves and attacks again
    gs.turn_number = 2
    for o in gs.ordnance:
        o["moved_this_phase"] = False
    import math
    from src.ordnance import torpedo_bomber_groups
    foe = gs.get_ship_by_id("foe")
    groups = torpedo_bomber_groups(gs, 1)
    for g in groups:
        for m in g:                     # (fixture) 15cm short of the target to fire
            o = next(o for o in gs.ordnance if o["id"] == m.id)
            o["x"], m.x = foe.x - 15.0, foe.x - 15.0
    if not replay:
        for g in groups:
            aim = math.degrees(math.atan2(foe.y - g[0].y, foe.x - g[0].x))
            actions.fire_bomber_salvo(gs, [m.id for m in g], aim, "foe")
        _play.events = [e for e in recorder.events()]
    else:
        for e in _play.events:
            if e["depth"] == 0 and e["seat"] and e["turn"] == 2:
                actions.replay_event(gs, game.ctx.tc, game.ctx.dice, e, panel=game.combat)
    with recorder.flow():
        game.ordnance._resolve_ordnance_movement()
    foe = gs.get_ship_by_id("foe")
    ours = sum(1 for o in gs.ordnance if o["owner_player"] == 1)
    # engaged: the enemy took damage, or our ordnance was spent attacking it /
    # shot down by its turrets
    _play.hit[(cls, opt, kind, w_idx, load)] = (foe.hits_remaining < foe.hits_max
                                                or bool(foe.critical_damage)
                                                or ours < launched)
    return _state(gs), launched


_play.hit = {}


@pytest.mark.parametrize("cls,opt,kind,w_idx,load", CASES,
                         ids=[f"{c[0]}|{c[1] or 'base'}|{c[2]}{c[3]}|{c[4]}" for c in CASES])
def test_every_ordnance_launches_moves_and_replays(cls, opt, kind, w_idx, load):
    try:
        s1, n = _play(cls, opt, kind, w_idx, load, DiceSource(5, record=True))
        record = [list(e) for e in current_source().record]
        s2, _n = _play(cls, opt, kind, w_idx, load, DiceSource(0, replay=record))
    finally:
        set_source(DiceSource())
        recorder.stop_recording()
    assert n > 0, "nothing was launched"
    assert s2 == s1


def test_every_faction_with_ordnance_is_covered():
    factions = {find_ship_class(c[0]).faction for c in CASES}
    kinds = {c[2] for c in CASES}
    assert kinds == {"torp", "craft", "cap", "mines"}
    assert len(factions) >= 8, sorted(factions)


def test_launched_ordnance_reaches_and_attacks():
    """The sweep above is no use if nothing arrives: torpedoes, bombers,
    assault boats and torpedo bombers' salvos must damage the enemy ship in
    some cases, and every faction's ordnance must engage it (damage, or
    spent attacking / shot down)."""
    if not _play.hit:
        pytest.skip("run with the sweep")
    def hits(pred):
        return sum(1 for c, h in _play.hit.items() if pred(c) and h)
    assert sum(1 for c in _play.hit if c[2] == "torp") > 0
    assert hits(lambda c: c[2] == "torp") > 0
    assert hits(lambda c: c[2] == "craft" and "bomber" in c[4]) > 0
    assert hits(lambda c: c[2] == "craft" and "assault" in c[4]) > 0
    assert hits(lambda c: c[4] in ("torpedo_bomber", "tiger_shark")) > 0
    from src.ship_catalog import find_ship_class
    for faction in {find_ship_class(c[0]).faction for c in _play.hit}:
        assert hits(lambda c, f=faction: find_ship_class(c[0]).faction == f) > 0, faction


def _ai_cases():
    out = []
    for c in CASES:
        load = c[4] if c[2] == "torp" and c[4] in EXTRA_TORPEDO_TYPES else ""
        key = (c[0], c[1], "ai", 0, load)
        if key not in out:
            out.append(key)
    return out


AI_CASES = _ai_cases()
if not SWEEP:
    AI_CASES = _sample(AI_CASES, lambda c: (find_ship_class(c[0]).faction, c[4]))


def _ai_play(cls, opt, load, source):
    from src.ai_player import AIPlayer
    set_source(source)
    recorder.start_recording()
    gs, game = _setup(cls, opt, "torp" if load else "ai", load)
    if source.replay is None:
        ai = AIPlayer(1, game.ctx.tc, gs, game.ctx.dice, "normal")
        ai.run_ordnance_phase()
        _ai_play.events = list(recorder.events())
    else:
        for e in _ai_play.events:
            if e["depth"] == 0 and e["seat"]:
                actions.replay_event(gs, game.ctx.tc, game.ctx.dice, e, panel=game.combat)
    with recorder.flow():
        game.ordnance._resolve_ordnance_movement()
    return _state(gs)


@pytest.mark.parametrize("cls,opt,kind,w_idx,load", AI_CASES,
                         ids=[f"{c[0]}|{c[1] or 'base'}|{c[4] or 'any'}" for c in AI_CASES])
def test_ai_ordnance_phase_replays(cls, opt, kind, w_idx, load):
    """The AI's own launches (its choice of load, craft and target) for every
    ship and option, replayed from the record: the same game."""
    try:
        s1 = _ai_play(cls, opt, load, DiceSource(5, record=True))
        record = [list(e) for e in current_source().record]
        s2 = _ai_play(cls, opt, load, DiceSource(0, replay=record))
    finally:
        set_source(DiceSource())
        recorder.stop_recording()
    assert s2 == s1
