"""Eldar MMS v2.0 first slice (To do 14; bfgxr/rules/08_eldar.md)."""
from tests.conftest import DiceStub
from src import eldar


def test_speeds_and_aspects():
    sp = eldar.parse_speeds("10/15/20")
    assert sp == (10, 15, 20)
    assert eldar.parse_holofield("2+H") == 2 and eldar.parse_holofield("2") is None
    # sunward edge north (90 degrees): into the sun, away, abeam
    assert eldar.speed_for(sp, 90.0) == 10
    assert eldar.speed_for(sp, 270.0) == 15
    assert eldar.speed_for(sp, 0.0) == 20 and eldar.speed_for(sp, 135.0) == 20
    assert eldar.sun_aspect(0.0, "east") == eldar.SUN


def test_two_moves_turning_on_the_spot():
    sp = (10, 15, 20)
    ok = [(0.0, 20.0), (45.0, 10.0)]      # abeam 20, then turn into the sun at 45 -> abeam
    assert eldar.validate_mms_move(sp, 0.0, 45.0, ok) == []
    assert eldar.validate_mms_move(sp, 0.0, 45.0, [(90.0, 5.0)])         # beyond 45
    assert eldar.validate_mms_move(sp, 90.0, 45.0, [(0.0, 12.0)])        # into the sun: 10
    assert eldar.validate_mms_move(sp, 0.0, 45.0, [(0, 1), (0, 1), (0, 1)])
    assert eldar.validate_mms_move(sp, 0.0, 45.0, [(0.0, 5.0)], order="burn_retros")
    assert eldar.validate_mms_move(sp, 0.0, 45.0, [(10.0, 5.0)], order="lock_on")
    # All Ahead Full: +5D6 on one move only, no turns
    assert eldar.validate_mms_move(sp, 0.0, 45.0, [(0, 35.0), (0, 20.0)],
                                   order="all_ahead_full", aaf_bonus=17.0) == []
    assert eldar.validate_mms_move(sp, 0.0, 45.0, [(0, 35.0), (0, 30.0)],
                                   order="all_ahead_full", aaf_bonus=17.0)
    # Come to New Heading: one extra turn at the end of the second move
    assert eldar.validate_mms_move(sp, 0.0, 45.0, [(0, 10), (0, 10)],
                                   order="come_to_new_heading", extra_turn=45.0) == []
    assert eldar.validate_mms_move(sp, 0.0, 45.0, [(0, 10)], extra_turn=45.0)
    x, y, h = eldar.mms_end(0.0, 0.0, 0.0, [(0.0, 10.0), (90.0, 10.0)])
    assert abs(x - 10) < 1e-9 and abs(y - 10) < 1e-9 and abs(h - 90) < 1e-9


def test_holofields_and_fragile():
    assert eldar.holofield_gunnery_shift(14.9) == 0 and eldar.holofield_gunnery_shift(20) == 1
    assert eldar.holofield_save(31) == 5 and eldar.holofield_save(30) == 6
    assert eldar.holofield_save(10) is None
    dice = DiceStub([5, 6, 4])
    assert eldar.holofield_saves(dice, 3, 25.0) == 1 and dice._idx == 3
    assert abs(eldar.p_holofield_save(40) - 1 / 3) < 1e-9

    class S:
        special_rules = ["fragile"]
    assert eldar.crit_threshold(S()) == 5
    S.special_rules = ["fragile", "ghostship"]
    assert eldar.crit_threshold(S()) == 6
