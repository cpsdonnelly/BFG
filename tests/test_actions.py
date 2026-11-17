"""To do 18 item 7: the action layer. One move function for the AI and every
human move path: the move, the ordnance it touched, the terrain tests it ran
into, its staged-move count, and an exact record of it."""
from src import recorder
from src.actions import apply_move, result_from
from src.movement import MoveCommand, validate_movement
from tests.conftest import DiceStub, make_gs, make_phenomenon, make_ship


def test_apply_move_runs_terrain_tests_and_records_the_move():
    ship = make_ship(id="a", x=20.0, y=50.0, heading=0.0, speed=20, leadership=8)
    gs = make_gs([ship])
    gs.add_phenomenon(make_phenomenon("asteroid_field", x=35.0, y=50.0,
                                      width=10.0, height=10.0, radius=0))
    cmds = [MoveCommand("forward", 20.0)]
    r = validate_movement(ship, cmds, "", 0, [], 180, 120)
    assert r.valid
    recorder.start_recording()
    dice = DiceStub([3, 3])                 # the asteroid navigation test, 2D6 = 6 vs Ld 8
    out = apply_move(gs, dice, gs.get_ship_by_id("a"), r, cmds, False)
    assert dice._idx == 2                   # the test was taken
    assert out.distance_moved_this_turn == 20.0
    assert "in_asteroid_field" not in out.special_rules    # resolved and cleared
    ev = [e for e in recorder.events() if e["kind"] == "act_move"][0]
    again = result_from(ev["result"])
    assert (again.final_x, again.final_y, again.path) == (r.final_x, r.final_y,
                                                          [tuple(p) for p in r.path])
    recorder.stop_recording()
