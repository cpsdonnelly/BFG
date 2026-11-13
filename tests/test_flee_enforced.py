"""To do 6: a human's ship that failed a forced disengage test must move as
fast as possible towards the nearest table edge (s.37)."""
from tests.conftest import make_ship, make_gs
from src.movement import validate_movement, MoveCommand
from src.disengage import flee_move_errors


def _res(ship, gs, cmds):
    return validate_movement(ship, cmds, "", table_width=gs.table_width,
                             table_height=gs.table_height)


def test_flee_needs_full_speed_towards_the_edge():
    s = make_ship(id="s", player=1, x=20.0, y=60.0, heading=180.0, speed=20, must_flee=True)
    gs = make_gs([s])
    gs.table_width, gs.table_height = 180.0, 120.0
    good = _res(s, gs, [MoveCommand("forward", 20)])
    assert not flee_move_errors(s, good, gs)
    short = _res(s, gs, [MoveCommand("forward", 12)])
    assert flee_move_errors(s, short, gs)
    away = _res(s, gs, [MoveCommand("forward", 10), MoveCommand("turn_left", 45),
                        MoveCommand("forward", 10)])
    assert flee_move_errors(s, away, gs)
    calm = make_ship(id="c", player=1, x=20.0, y=60.0, heading=180.0, speed=20)
    assert not flee_move_errors(calm, short, gs)
