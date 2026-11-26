"""To do 18: the game flow runs with no window (headless_game.HeadlessGame),
to game over, and replays from its recorded dice to the same state."""
import hashlib
import json

from src import recorder
from src.dice import DiceRoller, DiceSource, set_source, current_source
from src.game_state import GameState
from src.headless_game import HeadlessGame
from src.models import Ship
from src.ship_catalog import find_ship_class
from src.turn_controller import TurnController


def _game(tmp_path, source):
    set_source(source)
    recorder.start_recording()
    gs = GameState(game_name="headless", game_seed=11)
    gs.table_width, gs.table_height = 120.0, 90.0
    gs.dice_mode = "auto"
    gs.turn_limit = 4
    for p, names, x in ((1, ["Lunar Class Cruiser", "Dauntless Class Light Cruiser"], 40.0),
                        (2, ["Murder Class Cruiser", "Infidel Class Raider"], 80.0)):
        for i, n in enumerate(names):
            d = find_ship_class(n).to_ship_dict(n, p, ship_id=f"p{p}_{i}")
            d.update(x=x, y=30.0 + 25 * i, heading=0.0 if p == 1 else 180.0, leadership=8)
            gs.add_ship(Ship.from_dict(d))
    tc = TurnController(gs, DiceRoller(mode="auto"), save_dir=str(tmp_path / "s"))
    game = HeadlessGame(tc)
    res = game.play(timeout=120)
    state = json.dumps({"ships": gs.ships, "ordnance": gs.ordnance, "log": gs.log},
                       sort_keys=True, default=str)
    return res, hashlib.sha256(state.encode()).hexdigest(), game


def test_headless_game_plays_to_the_end_and_replays(tmp_path):
    res, h, game = _game(tmp_path, DiceSource(11, record=True))
    assert res is not None and game._game_over       # it reached game over
    assert game.ctx.lines                            # the flow logged as it went
    record = current_source().record
    res2, h2, _ = _game(tmp_path, DiceSource(0, replay=[list(e) for e in record]))
    assert h2 == h and res2 == res                   # the record replays it exactly
    recorder.stop_recording()


def test_movement_phases_replay_from_the_recorded_actions(tmp_path):
    """Every movement phase played from the record (replay.ReplaySeat) instead
    of decided, the other phases by the AI: the same game (To do 17)."""
    def state(gs):
        return json.dumps({"ships": gs.ships, "ordnance": gs.ordnance,
                           "bm": gs.blast_markers}, sort_keys=True, default=str)
    _res, _h, game = _game(tmp_path, DiceSource(11, record=True))
    s1 = state(game.ctx.gs)
    record, evs = current_source().record, recorder.events()
    assert any(e["kind"] == "act_move" and e["depth"] == 0 and e["seat"] for e in evs)

    set_source(DiceSource(0, replay=[list(e) for e in record]))
    recorder.start_recording()
    gs = GameState(game_name="headless", game_seed=11)
    gs.table_width, gs.table_height, gs.dice_mode, gs.turn_limit = 120.0, 90.0, "auto", 4
    for p, names, x in ((1, ["Lunar Class Cruiser", "Dauntless Class Light Cruiser"], 40.0),
                        (2, ["Murder Class Cruiser", "Infidel Class Raider"], 80.0)):
        for i, n in enumerate(names):
            d = find_ship_class(n).to_ship_dict(n, p, ship_id=f"p{p}_{i}")
            d.update(x=x, y=30.0 + 25 * i, heading=0.0 if p == 1 else 180.0, leadership=8)
            gs.add_ship(Ship.from_dict(d))
    tc = TurnController(gs, DiceRoller(mode="auto"), save_dir=str(tmp_path / "r"))
    HeadlessGame(tc, replay_events=evs, replay_phases=("movement",)).play(timeout=120)
    assert state(gs) == s1
    recorder.stop_recording()


def test_movement_and_shooting_phases_replay_from_the_recorded_actions(tmp_path):
    """Movement and shooting played from the record (each attack one action:
    actions.fire_weapons and friends), ordnance and the end phase by the AI:
    the same game."""
    def state(gs):
        return json.dumps({"ships": gs.ships, "ordnance": gs.ordnance,
                           "bm": gs.blast_markers}, sort_keys=True, default=str)
    _res, _h, game = _game(tmp_path, DiceSource(11, record=True))
    s1 = state(game.ctx.gs)
    record, evs = current_source().record, recorder.events()
    assert any(e["kind"] == "act_fire" and e["depth"] == 0 and e["seat"] for e in evs)
    set_source(DiceSource(0, replay=[list(e) for e in record]))
    recorder.start_recording()
    gs = GameState(game_name="headless", game_seed=11)
    gs.table_width, gs.table_height, gs.dice_mode, gs.turn_limit = 120.0, 90.0, "auto", 4
    for p, names, x in ((1, ["Lunar Class Cruiser", "Dauntless Class Light Cruiser"], 40.0),
                        (2, ["Murder Class Cruiser", "Infidel Class Raider"], 80.0)):
        for i, n in enumerate(names):
            d = find_ship_class(n).to_ship_dict(n, p, ship_id=f"p{p}_{i}")
            d.update(x=x, y=30.0 + 25 * i, heading=0.0 if p == 1 else 180.0, leadership=8)
            gs.add_ship(Ship.from_dict(d))
    tc = TurnController(gs, DiceRoller(mode="auto"), save_dir=str(tmp_path / "r2"))
    HeadlessGame(tc, replay_events=evs, replay_phases=("movement", "shooting")).play(timeout=120)
    assert state(gs) == s1
    recorder.stop_recording()



CARRIERS = ((1, ["Dictator Class Cruiser", "Lunar Class Cruiser"], 40.0),
            (2, ["Devastation Class Cruiser", "Murder Class Cruiser"], 80.0))


def _carrier_gs(save):
    gs = GameState(game_name="headless", game_seed=21)
    gs.table_width, gs.table_height, gs.dice_mode, gs.turn_limit = 120.0, 90.0, "auto", 6
    for p, names, x in CARRIERS:
        for i, n in enumerate(names):
            d = find_ship_class(n).to_ship_dict(n, p, ship_id=f"p{p}_{i}")
            d.update(x=x, y=30.0 + 25 * i, heading=0.0 if p == 1 else 180.0, leadership=8)
            gs.add_ship(Ship.from_dict(d))
    return gs, TurnController(gs, DiceRoller(mode="auto"), save_dir=save)


def test_ordnance_phases_replay_from_the_recorded_actions(tmp_path):
    """Carriers and torpedo ships: movement, shooting and ordnance played from
    the record (launches, waves, craft targets, steering as actions), the end
    phase by the AI: the same game."""
    def state(gs):
        return json.dumps({"ships": gs.ships, "ordnance": gs.ordnance,
                           "bm": gs.blast_markers}, sort_keys=True, default=str)
    set_source(DiceSource(21, record=True))
    recorder.start_recording()
    gs, tc = _carrier_gs(str(tmp_path / "a"))
    HeadlessGame(tc).play(timeout=180)
    s1, record, evs = state(gs), current_source().record, recorder.events()
    kinds = {e["kind"] for e in evs if e["depth"] == 0 and e["seat"] and e["phase"] == "ordnance"}
    assert "act_launch_craft" in kinds
    set_source(DiceSource(0, replay=[list(e) for e in record]))
    recorder.start_recording()
    gs2, tc2 = _carrier_gs(str(tmp_path / "b"))
    HeadlessGame(tc2, replay_events=evs,
                 replay_phases=("movement", "shooting", "ordnance")).play(timeout=180)
    set_source(DiceSource())
    recorder.stop_recording()
    assert state(gs2) == s1


BOARDERS = ((1, ["Strike Cruiser", "Strike Cruiser"], 45.0),
            (2, ["Kill Kroozer", "Terror Ship"], 75.0))


def _boarders_gs(save):
    gs = GameState(game_name="headless", game_seed=12)
    gs.table_width, gs.table_height, gs.dice_mode, gs.turn_limit = 120.0, 90.0, "auto", 6
    gs.rule_boarding = gs.rule_teleport = gs.rule_hit_and_run = gs.rule_ramming = True
    for p, names, x in BOARDERS:
        for i, n in enumerate(names):
            d = find_ship_class(n).to_ship_dict(n, p, ship_id=f"p{p}_{i}")
            d.update(x=x, y=35.0 + 20 * i, heading=0.0 if p == 1 else 180.0, leadership=8)
            gs.add_ship(Ship.from_dict(d))
    return gs, TurnController(gs, DiceRoller(mode="auto"), save_dir=save)


def test_every_phase_replays_from_the_recorded_actions(tmp_path):
    """Space Marines v Orks with boarding, teleports, raids and rams on:
    every phase, the end phase's teleports / braces / repairs included,
    played from the record gives the same game (To do 18: a game with
    human players replays in full)."""
    def state(gs):
        return json.dumps({"ships": gs.ships, "ordnance": gs.ordnance,
                           "bm": gs.blast_markers}, sort_keys=True, default=str)
    set_source(DiceSource(12, record=True))
    recorder.start_recording()
    gs, tc = _boarders_gs(str(tmp_path / "a"))
    HeadlessGame(tc).play(timeout=180)
    s1, record, evs = state(gs), current_source().record, recorder.events()
    set_source(DiceSource(0, replay=[list(e) for e in record]))
    recorder.start_recording()
    gs2, tc2 = _boarders_gs(str(tmp_path / "b"))
    HeadlessGame(tc2, replay_events=evs,
                 replay_phases=("movement", "shooting", "ordnance", "end")).play(timeout=180)
    set_source(DiceSource())
    recorder.stop_recording()
    assert state(gs2) == s1
    whats = {e["what"] for e in evs if e["kind"] == "end_choice"}
    assert whats, "no end-phase decisions were made"
