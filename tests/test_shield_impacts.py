"""Shield impacts (s.11): markers touch the base, as close as possible to the
origin of the attack, fanned out without overlapping; no fixed limit."""
import math
from tests.conftest import make_ship, make_gs, DiceStub
from src.combat import apply_damage, SHIELD_IMPACT_SPACING_CM
from src.geometry import count_blast_markers_touching


def _target(**kw):
    base = dict(id="t", player=2, x=50.0, y=50.0, heading=90.0, shields_max=6, hits_max=12)
    base.update(kw)
    return make_ship(**base)


def test_markers_face_the_attacker_and_touch_the_base():
    t = _target(shields_max=2)
    gs = make_gs([t])
    apply_damage(t, 1, DiceStub([1]), gs, origin=(80.0, 50.0))     # attack from the east
    bms = gs.get_blast_markers()
    assert len(bms) == 1 and bms[0].x > t.x and abs(bms[0].y - t.y) < 0.01
    assert count_blast_markers_touching(t, bms) == 1


def test_several_impacts_fan_out_without_overlap_and_no_cap():
    t = _target()                       # small base, 6 shields
    gs = make_gs([t])
    apply_damage(t, 6, DiceStub([1]), gs, origin=(50.0, 90.0))     # from the north
    bms = gs.get_blast_markers()
    assert len(bms) == 6                # no 3-per-turn cap
    for i, a in enumerate(bms):
        for b in bms[i + 1:]:
            assert math.hypot(a.x - b.x, a.y - b.y) >= SHIELD_IMPACT_SPACING_CM - 1e-3
    assert count_blast_markers_touching(t, bms) == 6
    assert abs(bms[0].x - t.x) < 0.01 and bms[0].y > t.y      # first one due north
    north = sum(1 for b in bms if b.y > t.y - 0.5)
    assert north >= 5                   # fanned round from the attacker's side


def test_avoids_touching_a_nearby_ship_not_in_contact():
    t = _target(shields_max=1)
    near = make_ship(id="n", player=2, x=54.5, y=50.0)   # close, not in base contact
    gs = make_gs([t, near])
    apply_damage(t, 1, DiceStub([1]), gs, origin=(80.0, 50.0))
    bm = gs.get_blast_markers()[0]
    assert count_blast_markers_touching(gs.get_ship_by_id("n"), [bm]) == 0
