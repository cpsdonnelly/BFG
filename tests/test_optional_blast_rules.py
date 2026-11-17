"""Optional Modern / Remastered blast marker rules (core s.11)."""
import pytest
from tests.conftest import make_gs, make_ship, DiceStub
from src.models import BlastMarker
from src.optional_rules import set_blast_rules, in_blast_contact
from src.combat import get_column_shifts


@pytest.fixture(autouse=True)
def reset_mode():
    yield
    set_blast_rules("standard")


def setup():
    firer = make_ship(id="f", player=1, x=0.0, y=0.0)
    target = make_ship(id="t", player=2, x=25.0, y=0.0)
    # a marker touching the target's far side, off the line of fire
    bm = BlastMarker(id="b", x=25.0, y=2.5)
    return firer, target, [bm]


def test_standard_marker_off_the_line_no_shift():
    f, t, bms = setup()
    base = get_column_shifts(f, t, [])
    assert get_column_shifts(f, t, bms) == base


def test_modern_target_in_contact_counts_as_behind_blasts():
    f, t, bms = setup()
    base = get_column_shifts(f, t, [])
    set_blast_rules("modern")
    assert in_blast_contact(t, bms)
    assert get_column_shifts(f, t, bms) == base + 1


def test_remastered_firer_in_contact_shifts_and_overlap_counts():
    f, t, _ = setup()
    bms = [BlastMarker(id="b", x=0.0, y=2.5)]          # touching the firer only
    base = get_column_shifts(f, t, [])
    set_blast_rules("modern")
    assert get_column_shifts(f, t, bms) == base
    set_blast_rules("remastered")
    assert get_column_shifts(f, t, bms) == base + 1
    over = make_ship(id="o", player=1, x=2.5, y=-1.0)   # overlaps the firer, not the marker
    far = make_ship(id="x", player=1, x=5.0, y=-1.5)    # overlaps 'over' only (no cascade)
    assert in_blast_contact(over, bms, [f, over, far])
    assert not in_blast_contact(far, bms, [f, far, over])


def test_overlapping_bases_cover_shields_too():
    from src.optional_rules import set_ship_source
    from src.geometry import current_shields
    a = make_ship(id="a", x=0.0, y=0.0, shields_max=2)
    b = make_ship(id="b", x=2.5, y=0.0, shields_max=2)          # overlaps a, no marker of its own
    bms = [BlastMarker(id="m", x=-2.5, y=0.0)]                    # touches a only
    set_ship_source(lambda: [a, b])
    try:
        assert current_shields(b, bms) == 2                        # standard: not in contact
        set_blast_rules("modern")
        assert current_shields(b, bms) == 1                        # overlapping a: in contact
    finally:
        set_ship_source(None)


def _ring(spill):
    import math
    from src.combat import _place_shield_impacts
    from src.geometry import BLAST_MARKER_RADIUS_CM
    t = make_ship(id="t", x=50.0, y=50.0)
    d = t.base_radius * 2 + 1.2
    ring = [make_ship(id=f"o{k}", x=50.0 + d * math.cos(k * math.pi / 2),
                      y=50.0 + d * math.sin(k * math.pi / 2)) for k in range(4)]
    gs = make_gs([t] + ring)
    gs.rule_remastered_spillover = spill
    _place_shield_impacts(t, 10, gs, (0.0, 50.0), attacker_key="att")
    hit = {o.id for o in ring for b in gs.get_blast_markers()
           if math.hypot(b.x - o.x, b.y - o.y) <= o.base_radius + BLAST_MARKER_RADIUS_CM}
    return hit


def test_remastered_spillover_limit_one_other_ship():
    assert len(_ring(False)) > 1
    assert len(_ring(True)) <= 1
