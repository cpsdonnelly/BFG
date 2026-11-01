"""Brace for Impact before the damage is rolled (s.7): ramming (after the
Leadership test), exploding ships (after the blast radius), asteroid fields
(after the failed navigation test). The game supplies GameState.brace_hook."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.combat import offer_brace, resolve_ram, resolve_explosion
from src.terrain_effects import resolve_asteroid_navigation


def _hook(gs, answer=True, calls=None):
    def hook(ship, key, name, expected):
        if calls is not None:
            calls.append((ship.id, key))
        if answer:
            s = gs.get_ship_by_id(ship.id)
            s.special_order = "brace_for_impact"
            gs.update_ship(s)
        return answer
    return hook


def test_offer_brace_without_hook_uses_current_orders():
    s = make_ship(id="s")
    gs = make_gs([s])
    assert not offer_brace(gs, s, "a", "A", 1.0)
    s.special_order = "brace_for_impact"
    gs.update_ship(s)
    assert offer_brace(gs, s, "a", "A", 1.0)


def test_ram_both_ships_may_brace_and_save():
    rammer = make_ship(id="r", player=1, x=0.0, y=0.0, heading=0.0, hits_max=2,
                       armor_prow="6+", armor_side="5+", shields_max=0)
    target = make_ship(id="t", player=2, x=5.0, y=0.0, heading=90.0, hits_max=2,
                       armor_prow="6+", armor_side="5+", shields_max=0)
    gs = make_gs([rammer, target])
    calls = []
    gs.brace_hook = _hook(gs, True, calls)
    rolls = [5, 5,       # rammer's 2 dice vs target side 5+: 2 hits
             4, 4,       # target braced: both saved
             6]          # counter: 1 die (half of 2) vs rammer prow 6+: 1 hit
    rolls += [4]         # rammer braced: saved
    dice = DiceStub(rolls)
    r = resolve_ram(rammer, target, dice, gs)
    assert dice._idx == len(rolls)
    assert [c[0] for c in calls] == ["t", "r"]
    assert gs.get_ship_by_id("t").hits_remaining == 2 and gs.get_ship_by_id("r").hits_remaining == 2
    assert r["target_hits"] == 2 and r["rammer_hits"] == 1


def test_explosion_victims_asked_after_the_blast_radius():
    boom = make_ship(id="b", player=1, x=50.0, y=50.0, hits_max=8)
    near = make_ship(id="n", player=2, x=55.0, y=50.0, hits_max=8, shields_max=0)
    gs = make_gs([boom, near])
    calls = []
    gs.brace_hook = _hook(gs, False, calls)
    rolls = [3, 3, 3,            # blast radius 9cm
             1, 1, 1, 1]         # 4 lance shots (plasma overload: half of 8), all miss
    dice = DiceStub(rolls)
    resolve_explosion(boom, "plasma_drive_overload", dice, gs)
    assert dice._idx == len(rolls) and calls == [("n", "b")]


def test_asteroid_brace_after_failed_test():
    s = make_ship(id="s", player=1, leadership=6, shields_max=0, hits_max=8)
    gs = make_gs([s])
    calls = []
    gs.brace_hook = _hook(gs, True, calls)
    rolls = [6, 6,       # 2D6 = 12 vs Ld 6: failed
             3,          # D6 asteroid damage = 3
             4, 1, 5]    # brace saves: 2 of 3
    dice = DiceStub(rolls)
    r = resolve_asteroid_navigation(s, dice, gs)
    assert dice._idx == len(rolls) and calls == [("s", "asteroid_field")]
    assert s.hits_remaining == 7 and s.special_order == "brace_for_impact"
