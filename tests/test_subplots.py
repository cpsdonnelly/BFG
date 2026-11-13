"""Sub-plots (src/subplots.py, XR p.80-82; CLAUDE.md To do 7 b)."""
from src import subplots as sp_mod
from src.movement import do_command_check
from tests.conftest import DiceStub, make_gs, make_ship


def _gs(*ships):
    gs = make_gs(list(ships))
    gs.table_width, gs.table_height = 180.0, 120.0
    return gs


def test_generation_tables():
    gs = _gs()
    for t, n, key in ((1, 1, "gunnery_practice"), (2, 6, "vendetta"), (3, 1, "meteor_storm"),
                      (4, 6, "enemy_plans"), (5, 3, "experimental_ship"), (6, 6, "hit_and_run")):
        dice = DiceStub([t, n])
        sp = sp_mod.generate(gs, 1, dice)
        assert sp["key"] == key and dice._idx == 2
    sp = sp_mod.generate(gs, 1, DiceStub([3, 3]))
    assert sp["key"] == "unexpected_help" and "unbuilt" in sp


def test_gunnery_practice_and_extended_duty_modify_command_checks():
    a = make_ship(id="a", player=1, leadership=7)
    b = make_ship(id="b", player=1, leadership=7)
    gs = _gs(a, b, make_ship(id="e", player=2))
    sp = sp_mod.generate(gs, 1, DiceStub([1, 1]))
    dice = DiceStub([5, 2])                   # a 4+: +1 for Lock On; b not
    sp_mod.apply_setup(gs, 1, sp, dice)
    assert dice._idx == 2
    a, b = gs.get_ship_by_id("a"), gs.get_ship_by_id("b")
    assert "gunnery_practice" in a.special_rules and "gunnery_practice" not in b.special_rules
    assert do_command_check(a, "lock_on", DiceStub([8]), gs=gs)["passed"]       # Ld 8
    assert not do_command_check(b, "lock_on", DiceStub([8]), gs=gs)["passed"]
    assert not do_command_check(a, "reload_ordnance", DiceStub([8]), gs=gs)["passed"]
    # Extended Duty: a 1 costs D3 damage, a 2 -1 to Lock On / Reload
    gs = _gs(make_ship(id="c", player=1, leadership=8, hits_remaining=8),
             make_ship(id="d", player=1, leadership=8))
    sp = sp_mod.generate(gs, 1, DiceStub([1, 2]))
    dice = DiceStub([1, 2, 2])                # c: 1 then D3=2; d: 2
    sp_mod.apply_setup(gs, 1, sp, dice)
    assert dice._idx == 3 and gs.get_ship_by_id("c").hits_remaining == 6
    assert not do_command_check(gs.get_ship_by_id("d"), "reload_ordnance", DiceStub([8]),
                                gs=gs)["passed"]


def test_vendetta_desperate_mission_and_battle_results():
    big = make_ship(id="big", player=2, points_value=300)
    small = make_ship(id="sm", player=2, points_value=100)
    mine = make_ship(id="m", player=1, points_value=200)
    gs = _gs(big, small, mine)
    sp = sp_mod.generate(gs, 1, DiceStub([2, 6]))
    sp_mod.apply_setup(gs, 1, sp, DiceStub([]))
    assert sp_mod.get(gs, 1)["target"] == "big"          # the AI nominates the dearest
    assert sp_mod.battle_result(gs, 1, 1)["result"] == "Victory!"
    b = gs.get_ship_by_id("big")
    b.hits_remaining = 3                                    # crippled
    gs.update_ship(b)
    r = sp_mod.battle_result(gs, 1, 1)
    assert r["result"] == "Heroic Victory!" and r["renown"] == 1
    assert sp_mod.battle_result(gs, 1, 2)["result"] == "Heroic Defeat!"
    assert sp_mod.battle_result(gs, 2, 1) is None
    sp = sp_mod.generate(gs, 2, DiceStub([5, 4]))         # Desperate Mission
    sp_mod.apply_setup(gs, 2, sp, DiceStub([]))
    assert sp_mod.get(gs, 2)["ship"] == "big"
    r = sp_mod.battle_result(gs, 2, 1)
    assert r["result"] == "Miserable Defeat!" and r["renown"] == -1


def test_surprise_attack_blocks_enemy_orders_for_d3_turns():
    from src.scenarios import orders_forbidden
    e = make_ship(id="e", player=2)
    gs = _gs(make_ship(id="a", player=1), e)
    sp = sp_mod.generate(gs, 1, DiceStub([5, 1]))
    sp_mod.apply_setup(gs, 1, sp, DiceStub([3]))         # D3 = 2 turns
    assert sp_mod.get(gs, 1)["turns"] == 2
    gs.turn_number = 4
    assert orders_forbidden(gs, e)
    assert orders_forbidden(gs, gs.get_ship_by_id("a")) is None
    gs.turn_number = 5
    assert orders_forbidden(gs, e) is None


def test_enemy_plans_and_secret_intelligence():
    from src.boarding import resolve_boarding  # noqa: F401  (the hook's home)
    flag = make_ship(id="f", player=2, is_flagship=True, points_value=200)
    a = make_ship(id="a", player=1)
    gs = _gs(flag, a)
    sp = sp_mod.generate(gs, 1, DiceStub([3, 6]))
    sp_mod.apply_setup(gs, 1, sp, DiceStub([]))
    sp_mod.record_boarding(gs, 1, flag, DiceStub([3]))    # 3 + 1 (flagship) = 4
    assert sp_mod.get(gs, 1)["done"]
    assert sp_mod.battle_result(gs, 1, 2)["result"] == "Heroic Defeat!"
    gs.subplots = {}
    sp = sp_mod.generate(gs, 1, DiceStub([5, 2]))         # Secret Intelligence
    flag2 = gs.get_ship_by_id("f")
    flag2.is_flagship = False
    gs.add_ship(make_ship(id="g", player=1, is_flagship=True, rerolls_remaining=1))
    sp_mod.apply_setup(gs, 1, sp, DiceStub([]))
    assert gs.get_ship_by_id("g").rerolls_remaining == 2
    assert not sp_mod.objective_met(gs, 1, True)
    sp_mod.record_raid(gs, 1, gs.get_ship_by_id(sp_mod.get(gs, 1)["target"]))
    assert sp_mod.objective_met(gs, 1, True)


def test_experimental_ship_and_hit_and_run():
    s = make_ship(id="x", player=1, speed=20, shields_max=2, leadership=8,
                  weapons=[{"name": "B", "weapon_type": "battery", "strength": 6,
                            "range_cm": 30, "arcs": ["left"]}])
    gs = _gs(s, make_ship(id="e", player=2))
    sp = sp_mod.generate(gs, 1, DiceStub([6, 3]))
    sp_mod.apply_setup(gs, 1, sp, DiceStub([1, 1, 2, 4]))   # ship 1; +50% range; side 2
    x = gs.get_ship_by_id("x")                               # contradicts, re-rolled: 4
    assert x.weapons[0]["range_cm"] == 45 and x.speed == 15
    gs.subplots = {}
    sp = sp_mod.generate(gs, 1, DiceStub([6, 6]))
    sp_mod.apply_setup(gs, 1, sp, DiceStub([2, 3]))         # 5 turns
    gs.turn_number = 9                                       # game turn 5
    assert sp_mod.objective_met(gs, 1, True)
    gs.turn_number = 11
    assert not sp_mod.objective_met(gs, 1, True)


def test_ai_values_subplot_ships():
    from src.ai_hazards import damage_vp
    big = make_ship(id="big", player=2, points_value=300, hits_remaining=2)
    gs = _gs(big, make_ship(id="m", player=1, points_value=200))
    plain = damage_vp(gs.get_ship_by_id("big"), gs, 3.0)
    sp = sp_mod.generate(gs, 1, DiceStub([2, 6]))            # Vendetta on "big"
    sp_mod.apply_setup(gs, 1, sp, DiceStub([]))
    assert damage_vp(gs.get_ship_by_id("big"), gs, 3.0) > plain + 30
