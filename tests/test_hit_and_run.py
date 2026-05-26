"""Tests for src/hit_and_run.py."""
import pytest
from src.hit_and_run import (
    check_teleport_eligibility,
    resolve_raids,
    resolve_hit_and_run,
    resolve_teleport_attack,
    _apply_raid_crit,
)
from src.models import OrdnanceMarker

from tests.conftest import make_ship, make_gs, DiceStub


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _no_brace(ship, msg):
    return (False, False)

def _brace_pass(ship, msg):
    return (True, True)

def _brace_fail(ship, msg):
    return (True, False)

def _assault_marker():
    return OrdnanceMarker(
        id="ab1", ordnance_type="assault_boat",
        owner_player=1, launched_by="a1",
        x=5.0, y=0.0,
    )


# ---------------------------------------------------------------------------
# check_teleport_eligibility
# ---------------------------------------------------------------------------

class TestCheckTeleportEligibility:
    def _pair(self, **a_overrides):
        """Attacker and target that pass all eligibility checks by default."""
        defaults = dict(id="a", x=0.0, y=0.0, hits_max=8,
                        ship_type="cruiser", shields_max=2)
        defaults.update(a_overrides)
        attacker = make_ship(**defaults)
        # Target: no shields, slightly fewer hits, within 10 cm
        target = make_ship(
            id="t", x=5.0, y=0.0, player=2,
            hits_max=6, hits_remaining=5,
            shields_max=0,
        )
        gs = make_gs([attacker, target])
        return attacker, target, gs

    def test_crippled_ineligible(self):
        attacker, target, gs = self._pair(hits_remaining=4, hits_max=8)
        ok, reason = check_teleport_eligibility(attacker, target, gs)
        assert not ok
        assert "crippled" in reason.lower()

    def test_disallowed_special_order_ineligible(self):
        attacker, target, gs = self._pair(special_order="all_ahead_full")
        ok, reason = check_teleport_eligibility(attacker, target, gs)
        assert not ok
        assert "all_ahead_full" in reason

    def test_tau_ineligible(self):
        attacker, target, gs = self._pair(faction="tau_kororvesh")
        ok, reason = check_teleport_eligibility(attacker, target, gs)
        assert not ok
        assert "tau" in reason.lower()

    def test_small_escort_ineligible(self):
        attacker, target, gs = self._pair(ship_type="escort", hits_max=2)
        ok, reason = check_teleport_eligibility(attacker, target, gs)
        assert not ok
        assert "small" in reason.lower() or "too small" in reason.lower()

    def test_out_of_range_ineligible(self):
        attacker, target, gs = self._pair()
        target.x = 50.0  # 50 cm away, max is 10
        ok, reason = check_teleport_eligibility(attacker, target, gs)
        assert not ok
        assert "away" in reason.lower() or "cm" in reason.lower()

    def test_target_has_shields_ineligible(self):
        attacker = make_ship(id="a", x=0.0, y=0.0)
        target = make_ship(id="t", x=5.0, y=0.0, player=2,
                           hits_max=6, hits_remaining=5, shields_max=2)
        gs = make_gs([attacker, target])
        ok, reason = check_teleport_eligibility(attacker, target, gs)
        assert not ok
        assert "shield" in reason.lower()

    def test_target_more_hits_ineligible(self):
        attacker = make_ship(id="a", x=0.0, y=0.0, hits_max=4, hits_remaining=4)
        target = make_ship(id="t", x=5.0, y=0.0, player=2,
                           hits_max=8, hits_remaining=8, shields_max=0)
        gs = make_gs([attacker, target])
        ok, reason = check_teleport_eligibility(attacker, target, gs)
        assert not ok
        assert "hits" in reason.lower()

    def test_all_conditions_pass(self):
        attacker, target, gs = self._pair()
        ok, reason = check_teleport_eligibility(attacker, target, gs)
        assert ok
        assert reason == ""

    def test_lock_on_order_allowed(self):
        attacker, target, gs = self._pair(special_order="lock_on")
        ok, _ = check_teleport_eligibility(attacker, target, gs)
        assert ok

    def test_reload_ordnance_order_allowed(self):
        attacker, target, gs = self._pair(special_order="reload_ordnance")
        ok, _ = check_teleport_eligibility(attacker, target, gs)
        assert ok


# ---------------------------------------------------------------------------
# resolve_raids
# ---------------------------------------------------------------------------

class TestResolveRaids:
    def _gs(self, target):
        return make_gs([target])

    def test_roll_one_is_failure(self):
        target = make_ship(id="t", player=2)
        gs = self._gs(target)
        dice = DiceStub([1])
        summary = resolve_raids(1, target, False, dice, gs)
        assert summary["failures"] == 1
        assert summary["crits_applied"] == []
        assert summary["repelled"] == 0

    def test_roll_six_applies_engine_room_crit(self):
        # Roll 6 = Engine Room Damaged (extra_damage=1, no cascade)
        target = make_ship(id="t", player=2, hits_max=8)
        gs = self._gs(target)
        dice = DiceStub([6])
        summary = resolve_raids(1, target, False, dice, gs)
        assert len(summary["crits_applied"]) == 1
        assert summary["crits_applied"][0]["crit_type"] == "engine_room"
        # Engine room: extra_damage=1
        fresh = gs.get_ship_by_id("t")
        assert fresh.hits_remaining == 7

    def test_brace_repel_roll_four_plus_repels(self):
        target = make_ship(id="t", player=2)
        gs = self._gs(target)
        # Raid roll=6 (success), then repel roll=5 (≥4 → repelled)
        dice = DiceStub([6, 5])
        summary = resolve_raids(1, target, brace_passed=True, dice=dice, gs=gs)
        assert summary["repelled"] == 1
        assert summary["crits_applied"] == []

    def test_brace_repel_roll_under_four_does_not_repel(self):
        target = make_ship(id="t", player=2)
        gs = self._gs(target)
        # Raid roll=6, repel roll=3 (<4 → not repelled)
        dice = DiceStub([6, 3])
        summary = resolve_raids(1, target, brace_passed=True, dice=dice, gs=gs)
        assert summary["repelled"] == 0
        assert len(summary["crits_applied"]) == 1

    def test_multiple_raids_one_failure_one_hit(self):
        target = make_ship(id="t", player=2)
        gs = self._gs(target)
        dice = DiceStub([1, 6])
        summary = resolve_raids(2, target, False, dice, gs)
        assert summary["failures"] == 1
        assert len(summary["crits_applied"]) == 1

    def test_no_brace_two_hits_two_crits(self):
        target = make_ship(id="t", player=2, hits_max=8)
        gs = self._gs(target)
        dice = DiceStub([6, 6])
        summary = resolve_raids(2, target, False, dice, gs)
        # Each roll=6 → Engine Room Damaged.  Second will cascade past engine_room
        # (unrepairable=False so no cascade due to that) — actually engine_room IS
        # repairable, so both apply independently.
        assert len(summary["crits_applied"]) == 2

    def test_raid_events_logged(self):
        target = make_ship(id="t", player=2)
        gs = self._gs(target)
        dice = DiceStub([1])
        resolve_raids(1, target, False, dice, gs, source_name="MyBoats")
        # A failure log line should have been written for the roll of 1
        assert any("FAILURE" in entry for entry in gs.log)


# ---------------------------------------------------------------------------
# resolve_hit_and_run
# ---------------------------------------------------------------------------

class TestResolveHitAndRun:
    def test_no_brace_crit_applied(self):
        target = make_ship(id="t", player=2, hits_max=8)
        gs = make_gs([target])
        marker = _assault_marker()
        dice = DiceStub([6])
        result = resolve_hit_and_run(marker, target, dice, gs, _no_brace)
        assert result["brace_wanted"] is False
        assert result["brace_passed"] is False
        assert len(result["crits_applied"]) == 1

    def test_brace_pass_repels_raid(self):
        target = make_ship(id="t", player=2)
        gs = make_gs([target])
        marker = _assault_marker()
        # raid roll=6, repel roll=5 → repelled
        dice = DiceStub([6, 5])
        result = resolve_hit_and_run(marker, target, dice, gs, _brace_pass)
        assert result["brace_wanted"] is True
        assert result["brace_passed"] is True
        assert result["repelled"] == 1
        assert result["crits_applied"] == []

    def test_brace_fail_no_repel_crit_applied(self):
        target = make_ship(id="t", player=2, hits_max=8)
        gs = make_gs([target])
        marker = _assault_marker()
        dice = DiceStub([6])
        result = resolve_hit_and_run(marker, target, dice, gs, _brace_fail)
        assert result["brace_wanted"] is True
        assert result["brace_passed"] is False
        assert len(result["crits_applied"]) == 1

    def test_result_has_required_keys(self):
        target = make_ship(id="t", player=2)
        gs = make_gs([target])
        marker = _assault_marker()
        dice = DiceStub([1])
        result = resolve_hit_and_run(marker, target, dice, gs, _no_brace)
        for key in ("brace_wanted", "brace_passed", "raid_rolls", "crits_applied",
                    "failures", "repelled"):
            assert key in result

    def test_roll_one_no_crit(self):
        target = make_ship(id="t", player=2)
        gs = make_gs([target])
        marker = _assault_marker()
        dice = DiceStub([1])
        result = resolve_hit_and_run(marker, target, dice, gs, _no_brace)
        assert result["crits_applied"] == []
        assert result["failures"] == 1


# ---------------------------------------------------------------------------
# resolve_teleport_attack
# ---------------------------------------------------------------------------

class TestResolveTeleportAttack:
    def test_no_brace_crit_applied(self):
        attacker = make_ship(id="a", x=0.0, y=0.0, player=1)
        target = make_ship(id="t", x=5.0, y=0.0, player=2, hits_max=8)
        gs = make_gs([attacker, target])
        dice = DiceStub([6])
        result = resolve_teleport_attack(attacker, target, dice, gs, _no_brace)
        assert len(result["crits_applied"]) == 1

    def test_brace_pass_repels(self):
        attacker = make_ship(id="a", x=0.0, y=0.0, player=1)
        target = make_ship(id="t", x=5.0, y=0.0, player=2)
        gs = make_gs([attacker, target])
        dice = DiceStub([6, 5])
        result = resolve_teleport_attack(attacker, target, dice, gs, _brace_pass)
        assert result["repelled"] == 1
        assert result["crits_applied"] == []

    def test_attacker_name_in_log(self):
        attacker = make_ship(id="a", name="The Terror", x=0.0, y=0.0, player=1)
        target = make_ship(id="t", x=5.0, y=0.0, player=2)
        gs = make_gs([attacker, target])
        dice = DiceStub([1])
        resolve_teleport_attack(attacker, target, dice, gs, _no_brace)
        assert any("The Terror" in entry for entry in gs.log)

    def test_result_has_required_keys(self):
        attacker = make_ship(id="a", x=0.0, y=0.0, player=1)
        target = make_ship(id="t", x=5.0, y=0.0, player=2)
        gs = make_gs([attacker, target])
        dice = DiceStub([1])
        result = resolve_teleport_attack(attacker, target, dice, gs, _no_brace)
        for key in ("brace_wanted", "brace_passed", "raid_rolls", "crits_applied"):
            assert key in result

    def test_roll_one_no_crit(self):
        attacker = make_ship(id="a", x=0.0, y=0.0, player=1)
        target = make_ship(id="t", x=5.0, y=0.0, player=2)
        gs = make_gs([attacker, target])
        dice = DiceStub([1])
        result = resolve_teleport_attack(attacker, target, dice, gs, _no_brace)
        assert result["failures"] == 1
        assert result["crits_applied"] == []
