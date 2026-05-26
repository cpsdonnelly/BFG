"""Tests for effective_battery_firepower and resolve_combined_batteries."""
import pytest
from src.combat import (effective_battery_firepower, resolve_combined_batteries,
                        resolve_batteries)
from src.models import SpecialOrder
from src.tables import lookup_gunnery_dice, get_gunnery_column

from tests.conftest import make_ship, make_gs, DiceStub


# ---------------------------------------------------------------------------
# effective_battery_firepower
# ---------------------------------------------------------------------------

def _weapon(strength: int) -> dict:
    return {"name": "Weapon Battery", "weapon_type": "battery",
            "strength": strength, "arcs": ["front"]}


class TestEffectiveBatteryFirepower:
    def test_full_health_no_order_unchanged(self):
        s = make_ship(hits_remaining=8, hits_max=8)
        assert effective_battery_firepower(s, _weapon(6)) == 6

    def test_crippled_halves_round_up(self):
        s = make_ship(hits_remaining=4, hits_max=8)  # ≤ half → crippled
        assert effective_battery_firepower(s, _weapon(6)) == 3
        assert effective_battery_firepower(s, _weapon(5)) == 3  # 5//2 rounds up

    def test_all_ahead_full_halves(self):
        s = make_ship(special_order=SpecialOrder.ALL_AHEAD_FULL.value)
        assert effective_battery_firepower(s, _weapon(6)) == 3

    def test_burn_retros_halves(self):
        s = make_ship(special_order=SpecialOrder.BURN_RETROS.value)
        assert effective_battery_firepower(s, _weapon(6)) == 3

    def test_come_to_new_heading_halves(self):
        s = make_ship(special_order=SpecialOrder.COME_TO_NEW_HEADING.value)
        assert effective_battery_firepower(s, _weapon(6)) == 3

    def test_brace_halves(self):
        s = make_ship(special_order=SpecialOrder.BRACE_FOR_IMPACT.value)
        assert effective_battery_firepower(s, _weapon(6)) == 3

    def test_crippled_and_aaf_stacks(self):
        # Crippled: 6→3, then AAF: 3→2 (ceil)
        s = make_ship(hits_remaining=4, hits_max=8,
                      special_order=SpecialOrder.ALL_AHEAD_FULL.value)
        assert effective_battery_firepower(s, _weapon(6)) == 2

    def test_refactored_resolve_batteries_unchanged(self):
        """resolve_batteries still gives same result after refactor."""
        # attacker at origin heading east; target 20cm ahead also heading east
        # → from target's perspective attacker is in REAR arc → "moving_away"
        # capital + moving_away → col 3, FP4 → GUNNERY_TABLE[4][2] = 2 dice
        attacker = make_ship(id="a", x=0.0, y=0.0, heading=0.0,
                             hits_remaining=8, hits_max=8)
        target = make_ship(id="t", x=20.0, y=0.0, heading=0.0,
                           ship_type="cruiser",
                           armor_prow="6+", armor_side="5+")
        weapon = _weapon(4)
        dice = DiceStub([6] * 10)  # all hits
        bms = []
        sr = resolve_batteries(attacker, target, weapon, dice, bms)
        # FP 4, moving_away capital = col 3, no shifts → GUNNERY_TABLE[4][2] = 2 dice
        assert sr.hits == 2


# ---------------------------------------------------------------------------
# resolve_combined_batteries
# ---------------------------------------------------------------------------

class TestResolveCombinedBatteries:
    def _make_pair(self, fp1=4, fp2=4, x_offset=5.0):
        """Two ships heading east within 30 cm, targeting a capital ship presenting
        its side (abeam).  Target heading=90° (north); attackers to the west →
        LEFT arc of target → abeam.  capital + abeam → col 4 (no >30cm shift):
        FP4→1 die, FP8→3 dice  (combined > 2×individual).
        """
        a1 = make_ship(id="a1", name="Ship One", x=0.0, y=0.0, heading=0.0,
                       hits_remaining=8, hits_max=8)
        a2 = make_ship(id="a2", name="Ship Two", x=x_offset, y=0.0, heading=0.0,
                       hits_remaining=8, hits_max=8)
        # Target ≤30 cm away so no distance shift; heading north so LEFT arc → abeam
        target = make_ship(id="t", name="Target", x=25.0, y=0.0, heading=90.0,
                           ship_type="cruiser", armor_prow="6+", armor_side="5+")
        w1 = _weapon(fp1)
        w2 = _weapon(fp2)
        return a1, a2, target, w1, w2

    def test_returns_single_shot_result(self):
        a1, a2, target, w1, w2 = self._make_pair()
        dice = DiceStub([6] * 20)
        sr = resolve_combined_batteries(a1, [(a1, w1), (a2, w2)], target,
                                        dice, [])
        assert sr.weapon_type == "battery"
        assert sr.hits >= 0

    def test_firepower_pooled_correctly(self):
        """Pooled FP 4+4=8 at col 4 (abeam capital) gives 3 dice;
        two separate FP-4 shots at same column give 1 die each = 2 dice total.
        Combined fire is demonstrably better here."""
        a1, a2, target, w1, w2 = self._make_pair()
        # target orientation: abeam → col 4 for capital
        col = get_gunnery_column("capital", "abeam")
        individual_dice = lookup_gunnery_dice(4, col, 0)  # 1 die each
        combined_dice = lookup_gunnery_dice(8, col, 0)    # 3 dice

        assert combined_dice > 2 * individual_dice  # combined is better

        # verify the resolver actually rolls combined_dice
        dice = DiceStub([1] * 20)  # all miss
        sr = resolve_combined_batteries(a1, [(a1, w1), (a2, w2)], target,
                                        dice, [])
        assert len(sr.dice_rolled) == combined_dice

    def test_all_hits_when_dice_are_all_max(self):
        a1, a2, target, w1, w2 = self._make_pair()
        col = get_gunnery_column("capital", "abeam")
        n_dice = lookup_gunnery_dice(8, col, 0)
        dice = DiceStub([6] * n_dice)
        sr = resolve_combined_batteries(a1, [(a1, w1), (a2, w2)], target,
                                        dice, [])
        assert sr.hits == n_dice

    def test_no_hits_when_dice_are_ones(self):
        a1, a2, target, w1, w2 = self._make_pair()
        dice = DiceStub([1] * 20)
        sr = resolve_combined_batteries(a1, [(a1, w1), (a2, w2)], target,
                                        dice, [])
        assert sr.hits == 0

    def test_zero_total_fp_returns_empty(self):
        a1, a2, target, w1, w2 = self._make_pair()
        # cripple both ships to halve their FP (but FP=1 crippled still gives 1)
        # use FP=0 weapons instead
        w_zero = _weapon(0)
        dice = DiceStub([6] * 20)
        sr = resolve_combined_batteries(a1, [(a1, w_zero), (a2, w_zero)], target,
                                        dice, [])
        assert sr.hits == 0
        assert "no firepower" in sr.description

    def test_contributor_names_in_description(self):
        a1, a2, target, w1, w2 = self._make_pair()
        dice = DiceStub([1] * 20)
        sr = resolve_combined_batteries(a1, [(a1, w1), (a2, w2)], target,
                                        dice, [])
        assert "Ship One" in sr.description
        assert "Ship Two" in sr.description

    def test_single_contributor(self):
        a1, a2, target, w1, w2 = self._make_pair()
        dice = DiceStub([6] * 20)
        col = get_gunnery_column("capital", "abeam")
        expected_dice = lookup_gunnery_dice(4, col, 0)
        sr = resolve_combined_batteries(a1, [(a1, w1)], target, dice, [])
        assert len(sr.dice_rolled) == expected_dice

    def test_lock_on_rerolls_misses(self):
        a1, a2, target, w1, w2 = self._make_pair()
        # First roll: all 1s (misses). Reroll: all 6s (hits).
        col = get_gunnery_column("capital", "abeam")
        n_dice = lookup_gunnery_dice(8, col, 0)
        dice = DiceStub([1] * n_dice + [6] * n_dice)
        sr = resolve_combined_batteries(a1, [(a1, w1), (a2, w2)], target,
                                        dice, [], lock_on=True)
        assert sr.hits == n_dice  # all misses were re-rolled to hits
