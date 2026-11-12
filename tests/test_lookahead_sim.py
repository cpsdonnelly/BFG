"""Expert AI search (lookahead_ai): its deterministic sim and leaf evaluation
use the normal AI's expected-VP terms (CLAUDE.md To do 1)."""
from tests.conftest import make_ship, make_gs
from src.models import Ship
from src.lookahead_ai import (SimState, SimShip, _apply_expected_combat, _expected_weapon_hits,
                              _evaluate, _simulate_turn)

GUNS = [{"name": "Port Battery", "weapon_type": "battery", "range_cm": 30, "strength": 6,
         "arcs": ["left"]},
        {"name": "Starboard Battery", "weapon_type": "battery", "range_cm": 30, "strength": 6,
         "arcs": ["right"]}]
LANCE = {"name": "Prow Lance", "weapon_type": "lance", "range_cm": 30, "strength": 2,
         "arcs": ["front"]}
TORP = {"name": "Prow Torpedoes", "weapon_type": "torpedo", "range_cm": 30, "strength": 6,
        "arcs": ["front"], "torpedo_speed": 30}


def _state(ships, gs_kw=None):
    gs = make_gs(ships)
    for k, v in (gs_kw or {}).items():
        setattr(gs, k, v)
    return SimState.from_gs(gs)


def test_lances_hit_on_4_whatever_the_armour():
    a = SimShip.from_ship(make_ship(id="a", player=1, x=0.0, y=0.0, heading=0.0,
                                    weapons=[dict(LANCE)]))
    t = SimShip.from_ship(make_ship(id="t", player=2, x=20.0, y=0.0, armor_prow="6+",
                                    armor_side="6+"))
    assert _expected_weapon_hits(a, LANCE, t) == 1.0


def test_sim_shooting_focuses_without_overkill():
    """The first ship finishes the 1-hit enemy; the next goes for the other."""
    ours = [make_ship(id=f"o{i}", player=1, x=20.0, y=10.0 * i, heading=90.0,
                      weapons=[dict(w) for w in GUNS]) for i in range(2)]
    dying = make_ship(id="dying", player=2, x=40.0, y=0.0, hits_remaining=1, shields_max=1,
                      points_value=200, armor_side="5+", armor_prow="5+")
    fresh = make_ship(id="fresh", player=2, x=40.0, y=10.0, shields_max=1, points_value=200,
                      armor_side="5+", armor_prow="5+")
    st = _state(ours + [dying, fresh])
    scored = _apply_expected_combat(st, 1)
    by = {s.id: s for s in st.ships}
    assert by["dying"].is_destroyed
    assert by["fresh"].hits_remaining < by["fresh"].hits_max      # the second ship moved on
    # the kill adds its 200 VP less what crippling it already scored (25% + 0.2 a hit)
    assert 110 < scored < 200


def test_sim_torpedoes_fire_once_and_ignore_shields():
    me = make_ship(id="me", player=1, x=0.0, y=0.0, heading=0.0, weapons=[dict(TORP)])
    me.ordnance_loaded_torps = True
    t = make_ship(id="t", player=2, x=25.0, y=0.0, shields_max=4, turrets=0,
                  armor_prow="4+", armor_side="4+", points_value=100)
    st = _state([me, t])
    _apply_expected_combat(st, 1)
    by = {s.id: s for s in st.ships}
    assert abs(by["t"].hits_remaining - (8 - 6 * 0.5)) < 1e-9     # 4 shields untouched
    assert by["t"].shields_remaining == 4 and not by["me"].torps_loaded


def test_sim_explosion_hits_ships_close_by():
    """A capital ship killed in the sim may blow up (s.34): nearby ships take
    the expected blast."""
    killer = make_ship(id="k", player=1, x=0.0, y=0.0, heading=90.0, weapons=[dict(w) for w in GUNS])
    victim = make_ship(id="v", player=2, x=20.0, y=0.0, hits_remaining=1, shields_max=0,
                       points_value=150)
    neighbour = make_ship(id="n", player=2, x=26.0, y=0.0, shields_max=0, points_value=150)
    st = _state([killer, victim, neighbour])
    _apply_expected_combat(st, 1)
    by = {s.id: s for s in st.ships}
    assert by["v"].is_destroyed and by["n"].hits_remaining < by["n"].hits_max


def test_sim_uses_the_real_table_and_resets_shields():
    me = make_ship(id="me", player=1, x=170.0, y=50.0, heading=0.0, speed=20)
    st = _state([me, make_ship(id="t", player=2, x=10.0, y=10.0)],
                {"table_width": 180.0, "table_height": 120.0})
    st.ships[0].shields_remaining = 0
    nxt = _simulate_turn(st, 1, {"me": (0.0, 20.0)}, {})
    me2 = next(s for s in nxt.ships if s.id == "me")
    assert me2.x == 180.0 and me2.shields_remaining == me2.shields_max


def test_leaf_values_staying_out_of_the_enemy_guns():
    """Same VP banked, but in one state our ship sits on an enemy broadside:
    next turn's expected swing makes that worse."""
    enemy = make_ship(id="e", player=2, x=40.0, y=40.0, heading=0.0,
                      weapons=[dict(w) for w in GUNS], points_value=150)
    safe = make_ship(id="me", player=1, x=0.0, y=0.0, heading=0.0, points_value=150)
    exposed = make_ship(id="me", player=1, x=40.0, y=55.0, heading=0.0, points_value=150)
    assert _evaluate(_state([safe, enemy]), 1) > _evaluate(_state([exposed, enemy]), 1)


def test_win_score_gambles_when_behind_and_plays_safe_when_ahead():
    """Owner (To do 2): with a turn limit the expert AI scores the chance of
    winning. Behind, more fighting to come (wider spread) is worth more;
    ahead, less is."""
    from src.lookahead_ai import win_score
    behind_quiet = win_score(-100.0, 10.0, 150.0, 1, 1000.0)
    behind_brawl = win_score(-100.0, 200.0, 150.0, 1, 1000.0)
    ahead_quiet = win_score(100.0, 10.0, 150.0, 1, 1000.0)
    ahead_brawl = win_score(100.0, 200.0, 150.0, 1, 1000.0)
    assert behind_brawl > behind_quiet and ahead_quiet > ahead_brawl
    # more VP is always better, even when the result is all but settled
    assert win_score(900.0, 0.0, 150.0, 0, 1000.0) > win_score(800.0, 0.0, 150.0, 0, 1000.0)


def _brawl_states(behind: bool):
    """Our gunship and theirs, alike; a crippled 400pt ship far away puts one
    side 100 VP behind. Last turn of the game. "brawl": the two gunships
    broadside to broadside at 20cm; "quiet": out of range of each other."""
    def scene(close):
        a = make_ship(id="a", player=1, x=50.0, y=50.0, heading=0.0, shields_max=1,
                      weapons=[dict(w) for w in GUNS], points_value=150)
        b = make_ship(id="b", player=2, x=50.0, y=70.0 if close else 115.0, heading=0.0,
                      shields_max=1, weapons=[dict(w) for w in GUNS], points_value=150)
        hurt = make_ship(id="h", player=1 if behind else 2, x=170.0, y=5.0, heading=0.0,
                         hits_remaining=4, points_value=400)
        return _state([a, b, hurt], {"turn_number": 5, "turn_limit": 5,
                                     "table_width": 180.0, "table_height": 120.0})
    return scene(True), scene(False)


def test_expert_leaf_takes_the_brawl_only_when_behind_at_the_end():
    brawl, quiet = _brawl_states(behind=True)
    assert _evaluate(brawl, 1) > _evaluate(quiet, 1)
    brawl, quiet = _brawl_states(behind=False)
    assert _evaluate(quiet, 1) > _evaluate(brawl, 1)
    # without a turn limit the leaf stays expected VP (the two are about even)
    brawl, quiet = _brawl_states(behind=True)
    brawl.turn_limit = quiet.turn_limit = None
    assert abs(_evaluate(brawl, 1) - _evaluate(quiet, 1)) < 0.02
