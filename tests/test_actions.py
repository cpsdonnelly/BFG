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


def test_ram_and_boarding_declarations_replay(tmp_path):
    from src.actions import declare_ram, declare_boarding, replay_event
    from src.dice import DiceRoller, DiceSource, set_source
    from src.turn_controller import TurnController
    import copy

    def setup():
        a = make_ship(id="a", x=20.0, y=50.0, heading=0.0, leadership=8)
        b = make_ship(id="b", player=2, x=30.0, y=50.0, heading=180.0)
        return make_gs([a, b])
    gs = setup()
    start = copy.deepcopy(gs.ships)
    set_source(DiceSource(5, record=True))
    recorder.start_recording()
    dice = DiceRoller(mode="auto")
    passed = declare_ram(gs, dice, "a", "b")
    declare_boarding(gs, "a", "b")
    evs = [e for e in recorder.events() if e["depth"] == 0]
    assert [e["kind"] for e in evs] == ["declare_ram", "declare_boarding"]
    from src.dice import current_source
    rec = current_source().record
    after = copy.deepcopy(gs.ships)

    gs2 = setup()
    gs2.ships = start
    set_source(DiceSource(0, replay=[list(e) for e in rec]))
    tc = TurnController(gs2, DiceRoller(mode="auto"), save_dir=str(tmp_path))
    for e in evs:
        replay_event(gs2, tc, DiceRoller(mode="auto"), e)
    assert gs2.ships == after
    assert gs2.get_ship_by_id("a").ramming_target_id == ("b" if passed else None)
    recorder.stop_recording()
    set_source(DiceSource())
