"""Faction lance rules in the AI's expected hits (owner, To do 30):
combat.lance_expected mirrors combat.resolve_lances."""
from tests.conftest import make_ship
from src.combat import lance_die_hits, lance_expected, resolve_lances
from src.dice import DiceRoller, start_game_dice

L = {"name": "Prow Lance", "weapon_type": "lance", "range_cm": 30, "strength": 4,
     "arcs": ["front"]}


def test_per_die_values():
    assert lance_die_hits(L) == 0.5
    assert lance_die_hits({**L, "hits_on": 5}) == 2 / 6                 # Ork zzapp gunz
    assert abs(lance_die_hits({**L, "de_phantom": True}) - 5 / 6) < 1e-12   # 1 on 4, 2 on 5+
    assert abs(lance_die_hits({**L, "phantom": True}) - 4 / 6) < 1e-12      # 1 on 4-5, 2 on 6
    assert abs(lance_die_hits({**L, "pulsar": True}) - 0.875) < 1e-12       # + follow-ups


def test_bio_plasma_and_particle_whips_bypass_shields():
    a = make_ship(id="a", player=1, x=0.0, y=0.0)
    near, far = make_ship(id="n", player=2, x=10.0, y=0.0), make_ship(id="f", player=2, x=25.0, y=0.0)
    bio = {**L, "bio_plasma": True}
    assert lance_expected(a, bio, near) == (2.0, 2.0)                    # 4+, all past shields
    assert abs(lance_expected(a, bio, far)[0] - 4 / 6) < 1e-12           # only a 6 beyond 15cm
    whip = {**L, "particle_whip": True}
    h, b = lance_expected(a, whip, far)
    assert h == 2.0 and abs(b - 4 / 6) < 1e-12                           # the 6s go past


def test_matches_the_engine_on_average():
    """Many real rolls of resolve_lances average to lance_expected."""
    start_game_dice(7)
    dice = DiceRoller(mode="auto")
    a = make_ship(id="a", player=1, x=0.0, y=0.0)
    for extra, tgt_rules in (({"pulsar": True}, ["holofield"]), ({"phantom": True}, []),
                             ({"de_phantom": True}, ["shadowfield"]), ({}, [])):
        w = {**L, **extra}
        t = make_ship(id="t", player=2, x=40.0, y=0.0, special_rules=list(tgt_rules))
        n = 4000
        mean = sum(resolve_lances(a, t, w, dice).hits for _ in range(n)) / n
        assert abs(mean - lance_expected(a, w, t)[0]) < 0.08, (extra, tgt_rules, mean)
