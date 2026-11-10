"""Defence turrets (core s.28) and Ork turrets (Xenos, Turret Defences)."""
from tests.conftest import make_gs, make_ship, make_marker, DiceStub
from src.ordnance import (resolve_torpedo_attack, resolve_mine_contact,
                          resolve_bomber_interception, choose_turret_target, turrets_blocked)


def test_mines_count_with_torpedoes_in_the_split():
    s = make_ship(id="s", turrets=2, hits_max=8, hits_remaining=8, armor_side="5+")
    s.turrets_used_vs = "craft"
    gs = make_gs([s])
    mine = make_marker(id="m", ordnance_type="mine_launcher", owner_player=2, x=3.0, y=0.0)
    dice = DiceStub([1, 1, 1, 1, 1, 1, 1, 1])          # no turret dice: 8D6 straight away
    r = resolve_mine_contact(mine, s, dice, gs)
    assert dice._idx == 8 and r["attack_dice"] == 8


def test_split_works_both_ways():
    s = make_ship(id="s", turrets=2)
    s.turrets_used_vs = "torp"
    gs = make_gs([s])
    dice = DiceStub([])
    r = resolve_bomber_interception(3, s, [s], dice, gs)
    assert dice._idx == 0 and r["killed"] == 0 and "already used" in r["log"][0]


def test_ork_turrets_hit_on_5_and_fire_at_everything():
    o = make_ship(id="o", turrets=2, special_rules=["ork_turrets"], hits_max=8, hits_remaining=8)
    o.turrets_used_vs = "craft"
    assert not turrets_blocked(o, "torp")
    gs = make_gs([o])
    torp = make_marker(id="t", owner_player=2, x=3.0, y=0.0, strength=2)
    dice = DiceStub([4, 5, 1])                       # turrets: 4 misses (Orks need 5+), 5 hits
    r = resolve_torpedo_attack(torp, o, dice, gs)
    assert r["turret_kills"] == 1 and dice._idx == 3
    from src.ship_catalog import find_ship_class
    assert "ork_turrets" in find_ship_class("Kill Kroozer").special_rules


def test_choice_between_attack_craft_and_torpedoes():
    s = make_ship(id="s", turrets=3, armor_side="5+")
    gs = make_gs([s])
    one_bomber = [make_marker(id="b", ordnance_type="bomber", owner_player=2)]
    big_salvo = [make_marker(id="t", owner_player=2, strength=8)]
    assert choose_turret_target(s, one_bomber, big_salvo, gs) == "torp"
    wave = [make_marker(id=f"b{i}", ordnance_type="bomber", owner_player=2, wave_id="w")
            for i in range(5)]
    small = [make_marker(id="t2", owner_player=2, strength=1)]
    assert choose_turret_target(s, wave, small, gs) == "craft"
    gs.turret_choice_hook = lambda ship, c, t: "torp"
    assert choose_turret_target(s, wave, small, gs, ai=False) == "torp"
