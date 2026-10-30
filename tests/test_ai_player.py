"""Tests for AI decisions that read live ship state."""
from src.ai_player import ai_should_brace
from src.lookahead_ai import SimShip
from src.models import BlastMarker
from tests.conftest import make_ship, make_gs


def test_brace_decision_absorbs_hits_with_shields():
    target = make_ship(id="t", player=2, shields_max=2, hits_max=8)
    gs = make_gs([target])
    # 2 hits fully absorbed by 2 shields, no other enemies -> no hull damage
    assert ai_should_brace(gs, target, incoming_hits=2) is False


def test_brace_decision_counts_blast_markers_against_shields():
    target = make_ship(id="t", player=2, shields_max=2, hits_max=8)
    gs = make_gs([target])
    gs.add_blast_marker(BlastMarker(id="bm1", x=0.0, y=0.0))
    gs.add_blast_marker(BlastMarker(id="bm2", x=0.0, y=0.0, heading=60.0))
    # Both shields knocked down -> 2 hull hits >= 8/4 threshold -> brace
    assert ai_should_brace(gs, target, incoming_hits=2) is True


def test_lookahead_sim_ship_uses_effective_shields():
    crippled = make_ship(shields_max=3, hits_max=8, hits_remaining=4)
    sim = SimShip.from_ship(crippled)
    assert sim.shields_remaining == crippled.effective_shields == 2
