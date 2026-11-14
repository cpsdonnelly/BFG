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
    sp = sp_mod.generate(gs, 1, DiceStub([5, 5]))
    assert sp["key"] == "decoy" and "unbuilt" in sp
    assert "unbuilt" not in sp_mod.generate(gs, 1, DiceStub([3, 3]))     # Unexpected Help


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


def test_blood_bond_and_fleet_experience_leadership():
    flag = make_ship(id="f", player=1, leadership=9, is_flagship=True, x=50.0, y=50.0)
    near = make_ship(id="n", player=1, leadership=6, x=70.0, y=50.0)
    far = make_ship(id="r", player=1, leadership=6, x=150.0, y=50.0)
    gs = _gs(flag, near, far, make_ship(id="e", player=2))
    sp_mod._set(gs, 1, {"key": "fleet_experience", "name": "Fleet Experience",
                        "renown": [1, 0]})
    assert sp_mod.leadership(gs, gs.get_ship_by_id("n")) == 9      # within 30cm
    assert sp_mod.leadership(gs, gs.get_ship_by_id("r")) == 6
    r = do_command_check(gs.get_ship_by_id("n"), "lock_on", DiceStub([9]), gs=gs)
    assert r["passed"] and r["needed"] == 9
    # Blood Bond: after a capital ship is lost, +1 for the player's next turn
    gs2 = _gs(make_ship(id="a", player=1, leadership=7), make_ship(id="b", player=1,
                                                                   leadership=7),
              make_ship(id="e", player=2))
    sp = {"key": "blood_bond", "name": "Blood Bond", "renown": [1, -1]}
    sp_mod.apply_setup(gs2, 1, sp, DiceStub([]))
    a = gs2.get_ship_by_id("a")
    a.status, a.hits_remaining = "destroyed", 0
    gs2.update_ship(a)
    gs2.turn_number = 3
    sp_mod.turn_start(gs2, 1)
    assert sp_mod.leadership(gs2, gs2.get_ship_by_id("b")) == 8
    gs2.turn_number = 4
    assert sp_mod.leadership(gs2, gs2.get_ship_by_id("b")) == 7


def test_signaling_problems_limits_rerolls():
    from src.turn_controller import TurnController
    flag = make_ship(id="f", player=1, is_flagship=True, x=50.0, y=50.0)
    flag.rerolls_remaining = 2
    near = make_ship(id="n", player=1, x=70.0, y=50.0)
    far = make_ship(id="r", player=1, x=150.0, y=50.0)
    gs = _gs(flag, near, far, make_ship(id="e", player=2))
    sp_mod._set(gs, 1, {"key": "signaling_problems", "name": "Signaling Problems",
                        "renown": [1, -1]})
    tc = TurnController(gs, DiceStub([]))
    assert tc.get_fleet_rerolls(1, gs.get_ship_by_id("n")) == 2
    assert tc.get_fleet_rerolls(1, gs.get_ship_by_id("r")) == 0
    assert not tc.use_fleet_reroll(1, gs.get_ship_by_id("r"))


def test_unexpected_help_adds_reinforcements_and_judges_them():
    gs = _gs(make_ship(id="a", player=1, faction="imperial_navy_gothic", points_value=500),
             make_ship(id="e", player=2))
    sp = {"key": "unexpected_help", "name": "Unexpected Help", "renown": [0, -2]}
    # D3 = 3 -> 150pts: the dearest Navy capital ship within it (a light cruiser); Ld roll 4
    sp_mod.apply_setup(gs, 1, sp, DiceStub([6, 4]))
    sp = sp_mod.get(gs, 1)
    ships = [gs.get_ship_by_id(i) for i in sp["ships"]]
    assert ships and sum(s.points_value for s in ships) <= 150
    assert len(ships) == 1 and ships[0].ship_type == "cruiser" and ships[0].leadership == 8
    assert sp_mod.objective_met(gs, 1, True)
    for s in ships:
        s.status, s.hits_remaining = "destroyed", 0
        gs.update_ship(s)
    assert not sp_mod.objective_met(gs, 1, True)
