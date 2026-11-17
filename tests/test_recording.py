"""To do 17: seeded dice, the roll record and replay. A few AI turns of
movement, shooting and ordnance (no Tk) played twice from one seed give the
same game; replayed from the recorded dice they give it again; a replay that
asks for a different roll stops at once."""
import hashlib
import json

import pytest

from src.ai_player import AIPlayer
from src.dice import DiceRoller, DiceSource, ReplayDivergence, set_source, current_source
from src.game_state import GameState
from src.models import Ship
from src.rng import game_random
from src.ship_catalog import find_ship_class
from src.turn_controller import TurnController

P1 = ["Lunar Class Cruiser", "Gothic Class Cruiser", "Dauntless Class Light Cruiser"]
P2 = ["Slaughter Class Cruiser", "Murder Class Cruiser", "Infidel Class Raider"]


def _play(tmp_path, source: DiceSource, seed: int = 7, turns: int = 3) -> str:
    set_source(source)
    gs = GameState(game_name="rec")
    gs.table_width, gs.table_height = 180.0, 120.0
    gs.game_seed = seed
    for p, names, x in ((1, P1, 50.0), (2, P2, 110.0)):
        for i, n in enumerate(names):
            d = find_ship_class(n).to_ship_dict(n, p, ship_id=f"p{p}_{i}")
            d.update(x=x, y=35.0 + 25 * i, heading=0.0 if p == 1 else 180.0, leadership=8)
            gs.add_ship(Ship.from_dict(d))
    dice = DiceRoller(mode="auto")
    tc = TurnController(gs, dice, save_dir=str(tmp_path / "save"))
    tc.start_game()
    ais = {p: AIPlayer(p, tc, gs, dice) for p in (1, 2)}
    while gs.turn_number <= turns:
        ai = ais[gs.active_player]
        phase = gs.current_phase
        if phase == "movement":
            ai.run_movement_phase()
        elif phase == "shooting":
            ai.run_shooting_phase()
        elif phase == "ordnance":
            ai.run_ordnance_phase()
        tc.end_phase()
        tc.advance_phase()
    state = json.dumps({"ships": gs.ships, "ordnance": gs.ordnance,
                        "blast": gs.blast_markers, "log": gs.log}, sort_keys=True, default=str)
    return hashlib.sha256(state.encode()).hexdigest()


def test_same_seed_same_game_and_replay(tmp_path):
    a = _play(tmp_path, DiceSource(7, record=True))
    record = current_source().record
    assert len(record) > 20                      # the dice were used and recorded
    assert all(e[4] == "auto" for e in record)
    b = _play(tmp_path, DiceSource(7, record=True))
    assert a == b                                # one seed, one game
    c = _play(tmp_path, DiceSource(999, replay=[list(e) for e in record]))
    assert c == a                                # the recorded dice replay it, whatever the seed
    assert current_source().pos == len(record)   # every recorded roll used


def test_replay_divergence_is_reported():
    set_source(DiceSource(1, replay=[["d6", 2, [3, 4], "x", "auto"]]))
    with pytest.raises(ReplayDivergence):
        DiceRoller(mode="auto").roll_d6(3, "three dice")
    set_source(DiceSource(1, replay=[]))
    with pytest.raises(ReplayDivergence):
        DiceRoller(mode="auto").roll_d6(1, "one past the end")
    set_source(DiceSource())


def test_manual_dice_replay_without_asking():
    # a manual roller with no window falls back to the game's dice; in replay
    # it returns the record and never asks
    set_source(DiceSource(1, replay=[["d6", 2, [6, 1], "typed", "manual"], ["angle", 1, 90.0, "dir", "auto"]]))
    d = DiceRoller(mode="manual")
    assert d.roll_d6(2, "typed") == [6, 1]
    assert d.roll_direction("dir") == 90.0
    set_source(DiceSource())


def test_source_state_round_trip():
    src = DiceSource(42, record=True)
    set_source(src)
    DiceRoller(mode="auto").roll_d6(5)
    st = json.loads(json.dumps(src.state()))
    again = DiceSource.from_state(st)
    assert again.d6s(10) == src.d6s(10)          # the generator carries on where it was
    assert again.record == src.record
    set_source(DiceSource())


def test_game_random_repeats_from_seed_and_counter():
    g1, g2 = GameState(game_seed=5), GameState(game_seed=5)
    assert [game_random(g1).random() for _ in range(3)] == [game_random(g2).random() for _ in range(3)]
    assert g1.rng_counter == 3
