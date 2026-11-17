"""AA phase scheduling (To do 13; docs/AA_ORDER_SYSTEMS_NOTES.md): all three
order systems through `aa_round.PhaseScheduler`, the open items as settings."""
import random
from types import SimpleNamespace

from src.activation import AAConfig, Unit, edge_share
from src.aa_round import (AARoundConfig, PhaseScheduler, ordnance_moves, ROUND_SHOOT_FIRST,
                          ROUND_MOVE_FIRST)


def _units(player, n, ld=8, hits=8):
    return [Unit(player, [f"p{player}u{i}"], ld, hits) for i in range(n)]


def _tracker(holder=None, gap=0.0):
    return SimpleNamespace(holder=holder, gap=gap)


def _cfg(mode):
    return AARoundConfig(activation=AAConfig(order_mode=mode))


def _play(s, pick_first=True):
    seq = []
    while True:
        nxt = s.next()
        if nxt is None:
            return seq
        p, key = nxt
        key = key or s.remaining(p)[0].key
        s.activated(p, key)
        seq.append((p, key))


def test_bag_every_unit_activates_once():
    s = PhaseScheduler("shooting", {1: _units(1, 3), 2: _units(2, 4)}, _tracker(),
                       _cfg("bag"), random.Random(1))
    seq = _play(s)
    assert len(seq) == 7 and len(set(seq)) == 7 and s.finished()


def test_adjusted_bag_choice_and_extra_dice():
    # gap 2.0: choice + ceil(5 / 3) = 2 extra dice for the edge holder (player 1)
    asked = []
    s = PhaseScheduler("shooting", {1: _units(1, 5), 2: _units(2, 6)}, _tracker(1, 2.0),
                       _cfg("bag_adjusted"), random.Random(2),
                       choose_first=lambda holder: asked.append(holder) or 1)
    assert asked == [1]
    assert s.bag.dice[1] == 5 + 2 - 1          # its chosen first activation spent a die
    assert s.next() == (1, None)
    seq = _play(s)
    assert seq[0][0] == 1 and len(seq) == 11
    # going second instead: the edge holder may hand the first activation over
    s2 = PhaseScheduler("movement", {1: _units(1, 5), 2: _units(2, 6)}, _tracker(1, 2.0),
                        _cfg("bag_adjusted"), random.Random(3), choose_first=lambda h: 2)
    assert s2.next() == (2, None)


def test_scheduler_monte_carlo_matches_edge_share():
    """The engine's bag, the edge holder never passing, against the notes'
    exact formula: 5 v 6, choice + 2 extra dice."""
    rng = random.Random(7)
    n, total = 4000, 0.0
    for _ in range(n):
        s = PhaseScheduler("shooting", {1: _units(1, 5), 2: _units(2, 6)}, _tracker(1, 2.0),
                           _cfg("bag_adjusted"), rng, choose_first=lambda h: h)
        seq = _play(s)
        pos = {k: i for i, (_p, k) in enumerate(seq)}
        first = sum(1 for a in s.eligible[1] for b in s.eligible[2] if pos[a.key] < pos[b.key])
        total += first / 30.0
    share = 2 * total / n - 1
    assert abs(share - edge_share(5, 6, k=2, choice=True)) < 0.03


def test_fixed_initiative_orders():
    fast = Unit(1, ["esc"], 8, 3)        # initiative 15
    slow = Unit(2, ["bb"], 8, 12)        # initiative 6
    mid = Unit(1, ["cr"], 9, 8)          # initiative 11
    elig = {1: [fast, mid], 2: [slow]}
    shoot = _play(PhaseScheduler("shooting", elig, _tracker(), _cfg("fixed_initiative"),
                                 random.Random(0)))
    move = _play(PhaseScheduler("movement", elig, _tracker(), _cfg("fixed_initiative"),
                                random.Random(0)))
    assert [k for _p, k in shoot] == ["esc", "cr", "bb"]
    assert [k for _p, k in move] == ["bb", "cr", "esc"]


def test_passing_only_with_spare_dice():
    """allow_pass: a side may decline a draw of its colour while it has more
    dice in the bag than units left; the unit then acts later."""
    declined = 0
    for seed in range(40):
        s = PhaseScheduler("movement", {1: _units(1, 2), 2: _units(2, 2)}, _tracker(1, 2.0),
                           _cfg("bag_adjusted"), random.Random(seed), choose_first=lambda h: 2)
        assert not s.can_decline(2)          # the chosen first activation isn't a draw
        while True:
            nxt = s.next()
            if nxt is None:
                break
            p, _k = nxt
            if p == 1 and s.can_decline(1):
                left = len(s.remaining(1))
                s.decline(1)
                declined += 1
                assert len(s.remaining(1)) == left
                continue
            s.activated(p, s.remaining(p)[0].key)
        assert s.finished()
    assert declined > 0
    off = PhaseScheduler("movement", {1: _units(1, 2), 2: _units(2, 2)}, _tracker(1, 2.0),
                         AARoundConfig(activation=AAConfig(allow_pass=False)), random.Random(0),
                         choose_first=lambda h: 1)
    off.activated(1, "p1u0")
    p, _k = off.next()
    assert not off.can_decline(p)


def test_round_settings():
    assert AARoundConfig().round_phases() == ROUND_SHOOT_FIRST
    assert AARoundConfig(phase_order="move_first").round_phases() == ROUND_MOVE_FIRST
    assert ordnance_moves(3, 3) == 1 and ordnance_moves(3, 4) == 2
    assert ordnance_moves(3, 3, AARoundConfig(first_turn_moves=2)) == 2
