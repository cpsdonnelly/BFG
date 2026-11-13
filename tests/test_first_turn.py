"""s.2 First turn: roll-off and the AI's choice (To do 11 e)."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.first_turn import roll_off, ai_moves_first
from src.turn_controller import TurnController

GUN = {"name": "Guns", "weapon_type": "battery", "range_cm": 30, "strength": 6, "arcs": ["front"]}


def test_roll_off_rerolls_ties():
    d = DiceStub([3, 3, 2, 5])
    assert roll_off(d) == (2, (2, 5)) and d._idx == 4


def test_ai_moves_first_when_its_guns_can_reach():
    near = make_gs([make_ship(id="a", player=1, x=0.0, y=0.0, speed=20, weapons=[GUN]),
                    make_ship(id="b", player=2, x=45.0, y=0.0)])
    far = make_gs([make_ship(id="a", player=1, x=0.0, y=0.0, speed=20, weapons=[GUN]),
                   make_ship(id="b", player=2, x=90.0, y=0.0)])
    assert ai_moves_first(near, 1) and not ai_moves_first(far, 1)


def test_start_game_uses_the_choice(tmp_path):
    gs = make_gs([make_ship(id="a", player=1), make_ship(id="b", player=2)])
    gs.first_player = 2
    tc = TurnController(gs, DiceStub([]), save_dir=str(tmp_path))
    tc.start_game()
    assert gs.active_player == 2
