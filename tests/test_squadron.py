"""Tests for src/squadron.py and TurnController.issue_squadron_order."""
import pytest
from src.squadron import (get_squadrons, check_squadron_coherency,
                           partition_by_coherency, get_coherency_components,
                           COHERENCY_RANGE)
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


# ---------------------------------------------------------------------------
# partition_by_coherency
# ---------------------------------------------------------------------------

class TestPartitionByCoherency:
    def test_single_ship_always_in(self):
        s = make_ship(id="s1", player=1, x=0.0, y=0.0)
        in_coh, out_coh = partition_by_coherency([s])
        assert in_coh == [s]
        assert out_coh == []

    def test_empty_list(self):
        assert partition_by_coherency([]) == ([], [])

    def test_both_in_range(self):
        s1 = make_ship(id="s1", player=1, x=0.0, y=0.0)
        s2 = make_ship(id="s2", player=1, x=10.0, y=0.0)
        in_coh, out_coh = partition_by_coherency([s1, s2])
        assert set(s.id for s in in_coh) == {"s1", "s2"}
        assert out_coh == []

    def test_exactly_at_coherency_range(self):
        s1 = make_ship(id="s1", player=1, x=0.0, y=0.0)
        s2 = make_ship(id="s2", player=1, x=COHERENCY_RANGE, y=0.0)
        in_coh, out_coh = partition_by_coherency([s1, s2])
        assert len(in_coh) == 2
        assert out_coh == []

    def test_one_out_of_range(self):
        s1 = make_ship(id="s1", player=1, x=0.0, y=0.0)
        s2 = make_ship(id="s2", player=1, x=5.0, y=0.0)
        s3 = make_ship(id="s3", player=1, x=100.0, y=0.0)
        in_coh, out_coh = partition_by_coherency([s1, s2, s3])
        assert set(s.id for s in in_coh) == {"s1", "s2"}
        assert [s.id for s in out_coh] == ["s3"]

    def test_all_out_of_range(self):
        s1 = make_ship(id="s1", player=1, x=0.0, y=0.0)
        s2 = make_ship(id="s2", player=1, x=100.0, y=0.0)
        in_coh, out_coh = partition_by_coherency([s1, s2])
        # Neither is within 15 cm of the other
        assert in_coh == []
        assert set(s.id for s in out_coh) == {"s1", "s2"}


# ---------------------------------------------------------------------------
# Coherency enforcement inside issue_squadron_order
# ---------------------------------------------------------------------------

class TestSquadronOrderCoherencyEnforcement:
    def test_out_of_coherency_ship_excluded(self):
        # s3 is far away — should be excluded from the squadron order
        s1 = make_ship(id="s1", name="Alpha", player=1, leadership=7, x=0.0, y=0.0)
        s2 = make_ship(id="s2", name="Beta",  player=1, leadership=6, x=5.0, y=0.0)
        s3 = make_ship(id="s3", name="Stray", player=1, leadership=8, x=200.0, y=0.0)
        tc = _make_tc([s1, s2, s3], [4])
        result = tc.issue_squadron_order(
            [s1, s2, s3], SpecialOrder.LOCK_ON.value)
        assert result["success"] is True
        # s3 should NOT be in ships_affected
        assert "Stray" not in result["ships_affected"]
        assert "Alpha" in result["ships_affected"] or "Beta" in result["ships_affected"]
        # s3 should NOT have the order
        assert tc.gs.get_ship_by_id("s3").special_order == "none"

    def test_out_of_coherency_ship_cannot_use_high_ld_leader(self):
        # s1 has Ld 9 but is 200 cm away — in-coherency ships roll with s2 Ld 7
        s1 = make_ship(id="s1", name="Leader", player=1, leadership=9, x=200.0, y=0.0)
        s2 = make_ship(id="s2", name="Close",  player=1, leadership=7, x=0.0,   y=0.0)
        s3 = make_ship(id="s3", name="Near",   player=1, leadership=6, x=5.0,   y=0.0)
        tc = _make_tc([s1, s2, s3], [4])
        result = tc.issue_squadron_order(
            [s1, s2, s3], SpecialOrder.LOCK_ON.value)
        assert result["success"] is True
        # Leader used for the roll should be the highest-Ld in-coherency ship
        assert result["leader"] == "Close"

    def test_all_out_of_coherency_returns_failure(self):
        s1 = make_ship(id="s1", player=1, leadership=7, x=0.0,   y=0.0)
        s2 = make_ship(id="s2", player=1, leadership=6, x=200.0, y=0.0)
        tc = _make_tc([s1, s2], [4])
        result = tc.issue_squadron_order([s1, s2], SpecialOrder.LOCK_ON.value)
        assert result["success"] is False
        assert "coherency" in result["error"].lower()


# ---------------------------------------------------------------------------
# get_coherency_components  (connected-component chain rule)
# ---------------------------------------------------------------------------

class TestGetCoherencyComponents:
    def test_single_ship_returns_one_group(self):
        s = make_ship(id="s1", player=1, x=0.0, y=0.0)
        groups, isolated = get_coherency_components([s])
        assert len(groups) == 1
        assert groups[0] == [s]
        assert isolated == []

    def test_empty_returns_empty(self):
        groups, isolated = get_coherency_components([])
        assert groups == []
        assert isolated == []

    def test_two_ships_in_range(self):
        s1 = make_ship(id="s1", player=1, x=0.0, y=0.0)
        s2 = make_ship(id="s2", player=1, x=10.0, y=0.0)
        groups, isolated = get_coherency_components([s1, s2])
        assert len(groups) == 1
        assert {s.id for s in groups[0]} == {"s1", "s2"}
        assert isolated == []

    def test_two_ships_out_of_range(self):
        s1 = make_ship(id="s1", player=1, x=0.0, y=0.0)
        s2 = make_ship(id="s2", player=1, x=200.0, y=0.0)
        groups, isolated = get_coherency_components([s1, s2])
        assert groups == []
        assert {s.id for s in isolated} == {"s1", "s2"}

    def test_chain_of_four(self):
        # 0, 10, 20, 30 cm — each 10 cm from the next; all connected via chain
        s1 = make_ship(id="s1", player=1, x=0.0,  y=0.0)
        s2 = make_ship(id="s2", player=1, x=10.0, y=0.0)
        s3 = make_ship(id="s3", player=1, x=20.0, y=0.0)
        s4 = make_ship(id="s4", player=1, x=30.0, y=0.0)
        groups, isolated = get_coherency_components([s1, s2, s3, s4])
        assert len(groups) == 1
        assert {s.id for s in groups[0]} == {"s1", "s2", "s3", "s4"}
        assert isolated == []

    def test_broken_chain_two_groups(self):
        # Positions: 0, 10, 26, 36 — gap between s2 (10) and s3 (26) is 16 cm > 15
        s1 = make_ship(id="s1", player=1, x=0.0,  y=0.0, leadership=7)
        s2 = make_ship(id="s2", player=1, x=10.0, y=0.0, leadership=6)
        s3 = make_ship(id="s3", player=1, x=26.0, y=0.0, leadership=7)
        s4 = make_ship(id="s4", player=1, x=36.0, y=0.0, leadership=6)
        groups, isolated = get_coherency_components([s1, s2, s3, s4])
        assert len(groups) == 2
        # Both groups have size 2; sort is stable on size, tiebreak by max Ld
        assert isolated == []
        group_ids = [{s.id for s in g} for g in groups]
        assert {"s1", "s2"} in group_ids
        assert {"s3", "s4"} in group_ids

    def test_isolated_plus_pair(self):
        isolated_ship = make_ship(id="iso", player=1, x=200.0, y=0.0)
        s1 = make_ship(id="s1", player=1, x=0.0,  y=0.0)
        s2 = make_ship(id="s2", player=1, x=10.0, y=0.0)
        groups, isolated = get_coherency_components([isolated_ship, s1, s2])
        assert len(groups) == 1
        assert {s.id for s in groups[0]} == {"s1", "s2"}
        assert len(isolated) == 1
        assert isolated[0].id == "iso"


# ---------------------------------------------------------------------------
# partition_by_coherency — chain/broken-chain cases
# ---------------------------------------------------------------------------

class TestPartitionByCoherencyChain:
    def test_chain_of_four_all_in(self):
        s1 = make_ship(id="s1", player=1, x=0.0,  y=0.0)
        s2 = make_ship(id="s2", player=1, x=10.0, y=0.0)
        s3 = make_ship(id="s3", player=1, x=20.0, y=0.0)
        s4 = make_ship(id="s4", player=1, x=30.0, y=0.0)
        in_coh, out_coh = partition_by_coherency([s1, s2, s3, s4])
        assert {s.id for s in in_coh} == {"s1", "s2", "s3", "s4"}
        assert out_coh == []

    def test_broken_chain_larger_group_wins(self):
        # 3-ship group at 0/10/20, 2-ship group at 100/110
        s1 = make_ship(id="s1", player=1, x=0.0,   y=0.0)
        s2 = make_ship(id="s2", player=1, x=10.0,  y=0.0)
        s3 = make_ship(id="s3", player=1, x=20.0,  y=0.0)
        s4 = make_ship(id="s4", player=1, x=100.0, y=0.0)
        s5 = make_ship(id="s5", player=1, x=110.0, y=0.0)
        in_coh, out_coh = partition_by_coherency([s1, s2, s3, s4, s5])
        assert {s.id for s in in_coh} == {"s1", "s2", "s3"}
        assert {s.id for s in out_coh} == {"s4", "s5"}

    def test_broken_chain_dangling_ship_excluded(self):
        # 0, 10, 26, 36 — two equal-size groups; each pair is in_coh / out_coh
        s1 = make_ship(id="s1", player=1, x=0.0,  y=0.0)
        s2 = make_ship(id="s2", player=1, x=10.0, y=0.0)
        s3 = make_ship(id="s3", player=1, x=26.0, y=0.0)
        s4 = make_ship(id="s4", player=1, x=36.0, y=0.0)
        in_coh, out_coh = partition_by_coherency([s1, s2, s3, s4])
        # Exactly one group in, one out (groups of equal size)
        assert len(in_coh) == 2
        assert len(out_coh) == 2
        # The two groups must be the two pairs
        in_ids  = {s.id for s in in_coh}
        out_ids = {s.id for s in out_coh}
        assert in_ids in ({"s1", "s2"}, {"s3", "s4"})
        assert out_ids in ({"s1", "s2"}, {"s3", "s4"})
        assert in_ids != out_ids
