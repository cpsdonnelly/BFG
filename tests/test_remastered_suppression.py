"""Turret suppression, Remastered mode (owner: follow Remastered p.82 exactly).
Each fighter in a wave of bombers attacking a ship adds +1 attack to the wave's
total (not to each bomber's roll), shot down by turrets or not; capped at the
bombers surviving turret fire, needing at least one; fighters intercepted by
defending fighters / CAP add nothing; turrets remove fighters first; bombers
still roll D6 - turrets (min 0) and the bonus is added on top; no fixed 3
attacks (XR only, s.27, the default)."""
from tests.conftest import make_ship, make_gs, make_marker, DiceStub
from src.waves import ship_attack_plan, wave_split_value
from src.ordnance import resolve_bomber_attack


def _wave(n_f, n_b, fighters_first=True):
    fs = [make_marker(id=f"f{i}", ordnance_type="fighter", owner_player=1) for i in range(n_f)]
    bs = [make_marker(id=f"b{i}", ordnance_type="bomber", owner_player=1) for i in range(n_b)]
    return fs + bs if fighters_first else bs + fs


def _devastation():
    # 3 turrets, Emperor wave, no CAP (Remastered p.82 examples)
    return make_ship(id="dev", player=2, turrets=3, armor_prow="5+", armor_side="5+",
                     hits_max=8, shields_max=2, points_value=190)


def test_example_one_3_bombers_5_fighters():
    plan = ship_attack_plan(_wave(5, 3), 3, remastered=True)
    assert plan["killed"] == ["f0", "f1", "f2"]          # turrets take three fighters
    assert len(plan["attackers"]) == 3
    assert plan["bonus"] == 3                              # 5 fighters, capped at 3 bombers
    assert plan["suppressed"] == set()                     # no fixed 3 attacks


def test_example_two_4_bombers_4_fighters():
    plan = ship_attack_plan(_wave(4, 4), 3, remastered=True)
    assert plan["killed"] == ["f0", "f1", "f2"]
    assert plan["bonus"] == 4                              # 4 fighters, 4 bombers


def test_bonus_needs_a_surviving_bomber_and_turrets_take_fighters_first():
    plan = ship_attack_plan(_wave(2, 2, fighters_first=False), 3, remastered=True)
    assert set(plan["killed"]) == {"f0", "f1", "b0"}      # fighters first, then the front
    assert plan["bonus"] == 1                              # capped at the 1 surviving bomber
    assert ship_attack_plan(_wave(2, 1), 3, remastered=True)["bonus"] == 0   # no bomber left


def test_xr_default_unchanged():
    plan = ship_attack_plan(_wave(5, 3), 3, remastered=False)
    assert plan["bonus"] == 0 and len(plan["suppressed"]) == 2   # 2 surviving fighters


def test_bombers_roll_normally_and_the_bonus_is_added_once():
    """Example one's dice: each bomber rolls D6 - 3; the wave's 3 bonus attacks
    go on top of one bomber's attacks."""
    t = _devastation()
    gs = make_gs([t])
    m = make_marker(id="b0", ordnance_type="bomber", owner_player=1)
    # D6 = 5: 5 - 3 = 2, + 3 bonus = 5 attacks; then 5 to-hit dice (2 hits),
    # then the damage step's critical-hit rolls (no crits)
    dice = DiceStub([5, 6, 5, 4, 2, 1, 2, 2])
    r = resolve_bomber_attack(m, t, dice, gs, bonus_attacks=3)
    assert r["attacks"] == 5 and r["hits"] == 2 and dice._idx == len(dice._results)
    # D6 = 2: 2 - 3 -> 0 (minimum 0), + 4 bonus = 4 attacks (example two)
    t2 = _devastation()
    gs2 = make_gs([t2])
    dice = DiceStub([2, 1, 1, 1, 1])
    r = resolve_bomber_attack(m, t2, dice, gs2, bonus_attacks=4)
    assert r["attacks"] == 4 and r["hits"] == 0 and dice._idx == len(dice._results)


def test_planner_values_remastered_mode():
    """The wave planner follows the mode: 5 fighters + 3 bombers vs 3 turrets."""
    xr = wave_split_value(5, 3, 3, 3, 0, 5, 0.5, remastered=False)
    rem = wave_split_value(5, 3, 3, 3, 0, 5, 0.5, remastered=True)
    assert rem != xr and rem > 0
