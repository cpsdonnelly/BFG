"""Tests for src/squadron.py and TurnController.issue_squadron_order."""
import pytest
from src.squadron import get_squadrons, check_squadron_coherency, COHERENCY_RANGE
from src.turn_controller import TurnController
from src.models import SpecialOrder

from tests.conftest import make_ship, make_gs, DiceStub


# ---------------------------------------------------------------------------
# get_squadrons
# ---------------------------------------------------------------------------

class TestGetSquadrons:
    def test_groups_by_squadron_id(self):
        s1 = make_ship(id="s1", player=1, squadron_id="sq1")
        s2 = make_ship(id="s2", player=1, squadron_id="sq1")
        gs = make_gs([s1, s2])
        result = get_squadrons(gs, 1)
        assert "sq1" in result
        assert {s.id for s in result["sq1"]} == {"s1", "s2"}

    def test_excludes_empty_squadron_id(self):
        s = make_ship(id="s1", player=1, squadron_id="")
        gs = make_gs([s])
        result = get_squadrons(gs, 1)
        assert result == {}

    def test_excludes_destroyed_ship(self):
        s1 = make_ship(id="s1", player=1, squadron_id="sq1", hits_remaining=0)
        s2 = make_ship(id="s2", player=1, squadron_id="sq1")
        gs = make_gs([s1, s2])
        result = get_squadrons(gs, 1)
        ids = {s.id for s in result.get("sq1", [])}
        assert "s1" not in ids
        assert "s2" in ids

    def test_excludes_disengaged_ship(self):
        s1 = make_ship(id="s1", player=1, squadron_id="sq1", is_disengaged=True)
        s2 = make_ship(id="s2", player=1, squadron_id="sq1")
        gs = make_gs([s1, s2])
        result = get_squadrons(gs, 1)
        ids = {s.id for s in result.get("sq1", [])}
        assert "s1" not in ids

    def test_excludes_other_player(self):
        s1 = make_ship(id="s1", player=1, squadron_id="sq1")
        s2 = make_ship(id="s2", player=2, squadron_id="sq1")
        gs = make_gs([s1, s2])
        result = get_squadrons(gs, 1)
        ids = {s.id for s in result.get("sq1", [])}
        assert "s2" not in ids
        assert "s1" in ids

    def test_multiple_squadrons(self):
        s1 = make_ship(id="s1", player=1, squadron_id="sq1")
        s2 = make_ship(id="s2", player=1, squadron_id="sq2")
        gs = make_gs([s1, s2])
        result = get_squadrons(gs, 1)
        assert "sq1" in result
        assert "sq2" in result


# ---------------------------------------------------------------------------
# check_squadron_coherency
# ---------------------------------------------------------------------------

class TestCheckSquadronCoherency:
    def test_in_range_no_violation(self):
        # 10 cm apart — within 15 cm coherency
        s1 = make_ship(id="s1", player=1, squadron_id="sq1", x=0.0, y=0.0)
        s2 = make_ship(id="s2", player=1, squadron_id="sq1", x=10.0, y=0.0)
        gs = make_gs([s1, s2])
        assert check_squadron_coherency(gs, 1) == []

    def test_exactly_at_coherency_range_ok(self):
        s1 = make_ship(id="s1", player=1, squadron_id="sq1", x=0.0, y=0.0)
        s2 = make_ship(id="s2", player=1, squadron_id="sq1",
                       x=COHERENCY_RANGE, y=0.0)
        gs = make_gs([s1, s2])
        assert check_squadron_coherency(gs, 1) == []

    def test_out_of_range_violation(self):
        s1 = make_ship(id="s1", player=1, squadron_id="sq1", x=0.0, y=0.0)
        s2 = make_ship(id="s2", player=1, squadron_id="sq1",
                       x=COHERENCY_RANGE + 1, y=0.0)
        gs = make_gs([s1, s2])
        violations = check_squadron_coherency(gs, 1)
        assert len(violations) == 2  # both ships are out of range of each other

    def test_three_ships_one_outlier(self):
        # s1 and s2 within range; s3 far from both
        s1 = make_ship(id="s1", player=1, squadron_id="sq1", x=0.0, y=0.0)
        s2 = make_ship(id="s2", player=1, squadron_id="sq1", x=5.0, y=0.0)
        s3 = make_ship(id="s3", player=1, squadron_id="sq1", x=100.0, y=0.0)
        gs = make_gs([s1, s2, s3])
        violations = check_squadron_coherency(gs, 1)
        # Only s3 violates (it is >15cm from both s1 and s2)
        assert len(violations) == 1
        assert "s3" in violations[0] or "Test Ship" in violations[0]

    def test_single_member_no_check(self):
        s = make_ship(id="s1", player=1, squadron_id="sq1")
        gs = make_gs([s])
        assert check_squadron_coherency(gs, 1) == []

    def test_no_violation_different_squadrons(self):
        # Two separate squadrons, each in-range internally
        s1 = make_ship(id="s1", player=1, squadron_id="sq1", x=0.0, y=0.0)
        s2 = make_ship(id="s2", player=1, squadron_id="sq1", x=5.0, y=0.0)
        s3 = make_ship(id="s3", player=1, squadron_id="sq2", x=200.0, y=0.0)
        s4 = make_ship(id="s4", player=1, squadron_id="sq2", x=205.0, y=0.0)
        gs = make_gs([s1, s2, s3, s4])
        assert check_squadron_coherency(gs, 1) == []


# ---------------------------------------------------------------------------
# TurnController.issue_squadron_order
# ---------------------------------------------------------------------------

def _make_tc(ships, dice_results):
    gs = make_gs(ships)
    gs.active_player = 1
    return TurnController(gs, DiceStub(dice_results))


class TestIssueSquadronOrder:
    def test_pass_applies_to_all_members(self):
        # roll_2d6 returns 4 → pass vs Ld 7
        s1 = make_ship(id="s1", player=1, leadership=7)
        s2 = make_ship(id="s2", player=1, leadership=6)
        tc = _make_tc([s1, s2], [4])
        result = tc.issue_squadron_order([s1, s2], SpecialOrder.LOCK_ON.value)
        assert result["success"] is True
        assert set(result["ships_affected"]) == {"Test Ship", "Test Ship"}
        # Fresh ships from gs should have the order
        for sid in ("s1", "s2"):
            fresh = tc.gs.get_ship_by_id(sid)
            assert fresh.special_order == SpecialOrder.LOCK_ON.value

    def test_fail_sets_command_check_failed(self):
        # roll 12 → fail vs Ld 7
        s1 = make_ship(id="s1", player=1, leadership=7)
        s2 = make_ship(id="s2", player=1, leadership=6)
        tc = _make_tc([s1, s2], [12])
        result = tc.issue_squadron_order([s1, s2], SpecialOrder.LOCK_ON.value)
        assert result["success"] is False
        assert tc.command_check_failed is True
        for sid in ("s1", "s2"):
            fresh = tc.gs.get_ship_by_id(sid)
            assert fresh.special_order == "none"

    def test_leader_is_highest_leadership(self):
        s1 = make_ship(id="s1", name="High", player=1, leadership=9)
        s2 = make_ship(id="s2", name="Low", player=1, leadership=5)
        tc = _make_tc([s1, s2], [4])
        result = tc.issue_squadron_order([s1, s2], SpecialOrder.LOCK_ON.value)
        assert result["leader"] == "High"

    def test_braced_member_skipped(self):
        s1 = make_ship(id="s1", player=1, leadership=7)
        s2 = make_ship(id="s2", player=1, leadership=6,
                       special_order=SpecialOrder.BRACE_FOR_IMPACT.value)
        tc = _make_tc([s1, s2], [4])
        result = tc.issue_squadron_order([s1, s2], SpecialOrder.LOCK_ON.value)
        assert result["success"] is True
        assert tc.gs.get_ship_by_id("s1").special_order == SpecialOrder.LOCK_ON.value
        assert (tc.gs.get_ship_by_id("s2").special_order ==
                SpecialOrder.BRACE_FOR_IMPACT.value)

    def test_ponderous_ctnh_blocked(self):
        s1 = make_ship(id="s1", player=1, leadership=7,
                       special_rules=["ponderous"])
        s2 = make_ship(id="s2", player=1, leadership=6)
        tc = _make_tc([s1, s2], [4])
        result = tc.issue_squadron_order(
            [s1, s2], SpecialOrder.COME_TO_NEW_HEADING.value)
        assert result["success"] is False
        assert "ponderous" in result["error"].lower() or "CtNH" in result["error"]
        assert not tc.command_check_failed  # no roll was made

    def test_already_failed_blocked(self):
        s1 = make_ship(id="s1", player=1, leadership=7)
        s2 = make_ship(id="s2", player=1, leadership=6)
        tc = _make_tc([s1, s2], [4])
        tc.command_check_failed = True
        result = tc.issue_squadron_order([s1, s2], SpecialOrder.LOCK_ON.value)
        assert result["success"] is False
        assert "already failed" in result["error"].lower()
