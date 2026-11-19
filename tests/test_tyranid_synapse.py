"""Tyranids, slice 2b (CLAUDE.md To do 19): synaptic control, Instinctive
Behaviour, Brace on the nearest synapse creature, the shooting rule and the
Vanguard fleet's Leadership."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.models import Phenomenon
from src.turn_controller import TurnController
from src import tyranids as ty
from src.movement import do_command_check


def _hive(**kw):
    base = dict(id="hive", player=1, x=60.0, y=20.0, heading=90.0, leadership=8, hits_max=10,
                special_rules=["tyranid", "synapse:8:45", "spore_cloud"])
    base.update(kw)
    return make_ship(**base)


def _drone(i, **kw):
    base = dict(id=f"d{i}", player=1, x=60.0 + i * 5, y=30.0, heading=90.0, leadership=7,
                ship_type="escort", hits_max=1, special_rules=["tyranid"])
    base.update(kw)
    return make_ship(**base)


def _gs(ships):
    gs = make_gs(ships)
    gs.active_player = 1
    gs.current_phase = "movement"
    return gs


def test_synaptic_control_chain_ends_on_a_failure():
    enemy = make_ship(id="e", player=2, x=60.0, y=110.0)
    gs = _gs([_hive(), _drone(1), _drone(2), enemy])
    tc = TurnController(gs, DiceStub([7, 9]))     # first passes, second fails
    ty.start_turn(gs, tc, tc.dice, 1)
    assert tc.dice._idx == 2
    st = gs.tyranid_state["1"]
    assert len(st["controlled"]) == 1 and st["failed"] == ["hive"]
    free = [i for i in ("d1", "d2") if i not in st["controlled"]][0]
    assert st["instinct"][free]["action"] in ("aaf", "drift", "close")


def test_instinct_chart():
    gs = _gs([_drone(1, x=60.0, y=30.0, heading=90.0), make_ship(id="e", player=2, x=60.0, y=40.0)])
    d = gs.get_ship_by_id("d1")
    assert ty.instinct(gs, d)["action"] == "board"            # in front, under 15cm
    gs = _gs([_drone(1, heading=90.0), make_ship(id="e", player=2, x=60.0, y=110.0)])
    assert ty.instinct(gs, gs.get_ship_by_id("d1"))["order"] == "all_ahead_full"
    gs = _gs([_drone(1, heading=90.0), make_ship(id="e", player=2, x=60.0, y=5.0)])
    assert ty.instinct(gs, gs.get_ship_by_id("d1"))["order"] == "come_to_new_heading"
    gun = {"name": "Pyro", "weapon_type": "battery", "strength": 4, "range_cm": 30,
           "arcs": ["front"], "pyro_acid": True}
    gs = _gs([_drone(1, heading=90.0, weapons=[gun]), make_ship(id="e", player=2, x=60.0, y=55.0)])
    assert ty.instinct(gs, gs.get_ship_by_id("d1"))["order"] == "lock_on"
    gs = _gs([_drone(1, heading=90.0), make_ship(id="e", player=2, x=120.0, y=30.0)])
    gs.add_phenomenon(Phenomenon(id="ast", phenomenon_type="asteroid_field", x=60.0, y=45.0,
                                 width=10.0, height=10.0))
    assert ty.instinct(gs, gs.get_ship_by_id("d1"))["order"] == "burn_retros"


def test_orders_auto_or_denied_and_brace_on_synapse_ld():
    enemy = make_ship(id="e", player=2, x=60.0, y=110.0)
    gs = _gs([_hive(), _drone(1), enemy])
    tc = TurnController(gs, DiceStub([12]))       # the hive fails to control the drone
    ty.start_turn(gs, tc, tc.dice, 1, choose=lambda c, cs: gs.get_ship_by_id("d1"))
    d = gs.get_ship_by_id("d1")
    assert d.special_order == "all_ahead_full"             # instinct order, no check
    assert tc.issue_special_order(d, "lock_on").get("error")
    assert tc.issue_special_order(gs.get_ship_by_id("hive"), "lock_on").get("error")
    assert ty.brace_ld(gs, d) == 8
    far = _drone(9, x=5.0, y=5.0)
    gs.add_ship(far)
    assert ty.brace_ld(gs, gs.get_ship_by_id("d9")) == 7
    assert do_command_check(gs.get_ship_by_id("d1"), "brace_for_impact", DiceStub([8]),
                            gs=gs)["passed"]


def test_controlled_unit_takes_any_order_without_a_check():
    enemy = make_ship(id="e", player=2, x=60.0, y=110.0)
    gs = _gs([_hive(), _drone(1), enemy])
    tc = TurnController(gs, DiceStub([2, 2]))     # the hive controls itself, then the drone
    ty.start_turn(gs, tc, tc.dice, 1)
    res = tc.issue_special_order(gs.get_ship_by_id("d1"), "burn_retros")
    assert res["success"] and tc.dice._idx == 2


def test_shooting_closest_or_highlighted():
    att = _drone(1, x=60.0, y=30.0)
    near = make_ship(id="n", player=2, x=60.0, y=45.0)
    far = make_ship(id="f", player=2, x=60.0, y=55.0)
    gs = _gs([att, near, far])
    assert ty.shooting_target_error(gs, att, far, [near, far])
    assert not ty.shooting_target_error(gs, att, near, [near, far])
    gs.add_ship(_drone(2, x=62.0, y=60.0, special_rules=["tyranid", "pheromone_sprayers"]))
    assert not ty.shooting_target_error(gs, att, far, [near, far])


def test_instinct_moves_and_errors():
    gs = _gs([_drone(1, heading=90.0, speed=15), make_ship(id="e", player=2, x=150.0, y=30.0)])
    tc = TurnController(gs, DiceStub([]))
    ty.assign_instinct(gs, tc, 1)
    d = gs.get_ship_by_id("d1")
    assert ty.instinct_of(gs, d)["action"] == "drift"
    cmds = ty.instinct_commands(gs, d, "", 0)
    assert cmds[0].action == "forward" and abs(cmds[0].value - 7.5) < 1e-9


def test_vanguard_leadership():
    a = _drone(1, squadron_id="sq", special_rules=["tyranid"])
    b = _drone(2, squadron_id="sq", special_rules=["tyranid"])
    k = _drone(3, squadron_id="sq", ship_class="Kraken", special_rules=["tyranid"])
    gs = _gs([a, b, k])
    assert ty.vanguard_fleet(gs, 1)
    assert ty.unit_ld(gs, gs.get_ship_by_id("d1")) == 6         # 4 counted, min 6
