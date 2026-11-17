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
