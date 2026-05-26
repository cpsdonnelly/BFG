"""Tests for resolve_batteries_vs_squadron and supporting helpers."""
import pytest
from src.combat import (
    resolve_batteries_vs_squadron, eligible_orientations, ORIENTATION_DIFFICULTY,
)
from tests.conftest import make_ship, make_gs, DiceStub


# ---------------------------------------------------------------------------
# eligible_orientations
# ---------------------------------------------------------------------------

class TestEligibleOrientations:
    def test_closing_only_includes_closing(self):
        result = eligible_orientations("closing")
        assert result == ["closing"]

    def test_moving_away_includes_closing_and_moving_away(self):
        result = eligible_orientations("moving_away")
        assert "closing" in result
        assert "moving_away" in result
        assert "abeam" not in result

    def test_abeam_includes_all(self):
        result = eligible_orientations("abeam")
        assert set(result) == {"closing", "moving_away", "abeam"}

    def test_unknown_orientation_defaults_to_abeam(self):
        result = eligible_orientations("unknown")
        assert set(result) == {"closing", "moving_away", "abeam"}


# ---------------------------------------------------------------------------
# resolve_batteries_vs_squadron — basic hit allocation
# ---------------------------------------------------------------------------

class TestResolveBatteriesVsSquadron:
    """
    Tests pass `eligible_ships` directly (pre-filtered) and the `target_type`
    argument explicitly, bypassing the UI dialog filtering logic.
    The default make_ship has ship_type="cruiser" which falls to gunnery col2
    (fallback capital column) — FP6 at mid-range (no shifts) gives 2+ dice.
    """

    def _make_weapon(self, strength=6, range_cm=30, arcs=None):
        return {
            "name": "Broadside Batteries",
            "weapon_type": "battery",
            "strength": strength,
            "range_cm": range_cm,
            "arcs": arcs or ["left", "right"],
        }

    def _pair(self, armor_a=4, armor_b=5):
        """Two targets at mid-range (20cm) — no range column shift."""
        attacker = make_ship(id="att", x=0.0, y=0.0, heading=0, player=1)
        t1 = make_ship(id="t1", name="T1", x=20.0, y=0.0,
                       armor_side=f"{armor_a}+", player=2)
        t2 = make_ship(id="t2", name="T2", x=25.0, y=0.0,
                       armor_side=f"{armor_b}+", player=2)
        gs = make_gs([attacker, t1, t2])
        return attacker, t1, t2, gs

    def test_no_eligible_ships_returns_zero(self):
        attacker = make_ship(id="att", x=0.0, y=0.0, player=1)
        weapon = self._make_weapon()
        dice = DiceStub([6] * 10)
        result = resolve_batteries_vs_squadron(
            attacker, weapon, "capital", "closing", [], dice, [])
        assert result.hits == 0
        assert result.description == "no eligible targets"

    def test_all_dice_miss_armor(self):
        attacker, t1, t2, gs = self._pair(armor_a=5, armor_b=6)
        weapon = self._make_weapon(strength=6)
        # Supply enough dice but all below armor thresholds
        dice = DiceStub([4, 4, 4, 4, 4, 4, 4, 4])
        result = resolve_batteries_vs_squadron(
            attacker, weapon, "capital", "abeam", [t1, t2],
            dice, [])
        assert result.hits == 0
        assert result.hits_by_ship == {}

    def test_hits_allocated_to_nearest_eligible(self):
        # t1 nearest (armor 4+), t2 farther (armor 5+).
        # FP6 capital abeam → col4 → 2+ dice at 20cm.  Supply 4 dice, all hit t1.
        attacker, t1, t2, gs = self._pair(armor_a=4, armor_b=5)
        weapon = self._make_weapon(strength=6)
        dice = DiceStub([5, 5, 5, 5, 5, 5])
        result = resolve_batteries_vs_squadron(
            attacker, weapon, "capital", "abeam", [t1, t2],
            dice, [])
        assert result.hits > 0
        # Every hit goes to nearest ship (t1)
        assert result.hits_by_ship.get(t1.id, 0) == result.hits
        assert result.hits_by_ship.get(t2.id, 0) == 0

    def test_die_skips_to_farther_ship_when_nearest_too_tough(self):
        # t1 armor=6+ (can't be hit by die≤5), t2 armor=4+, t1 is nearest.
        # Any die 4 or 5: t1 fails, t2 passes → hit goes to t2.
        attacker = make_ship(id="att", x=0.0, y=0.0, heading=0, player=1)
        t1 = make_ship(id="t1", name="Tough", x=20.0, y=0.0,
                       armor_side="6+", player=2)
        t2 = make_ship(id="t2", name="Weak", x=25.0, y=0.0,
                       armor_side="4+", player=2)
        # Pass a known single die via a tiny weapon; use capital target_type (col2 fallback)
        # to get at least 1 die. FP3 capital closing → col2 → 2 dice at 20cm.
        weapon = self._make_weapon(strength=3)
        dice = DiceStub([4, 4, 4, 4])  # supply extra; code takes what it needs
        result = resolve_batteries_vs_squadron(
            attacker, weapon, "capital", "closing", [t1, t2],
            dice, [])
        # die=4 → t1 (armor 6) fails, t2 (armor 4) passes → hit on t2
        assert result.hits_by_ship.get(t2.id, 0) > 0
        assert result.hits_by_ship.get(t1.id, 0) == 0

    def test_mixed_armor_lowest_die_hits_weaker_not_tougher(self):
        # sorted dice [4, 6]: die=4 hits t1 (armor 4+) not t2 (armor 5+)
        # confirms sorting + allocation works correctly
        attacker, t1, t2, gs = self._pair(armor_a=4, armor_b=5)
        weapon = self._make_weapon(strength=3)
        # Provide die=4 then die=6; sorted order [4,6] so first die=4 goes to t1
        dice = DiceStub([6, 4, 6, 6])
        result = resolve_batteries_vs_squadron(
            attacker, weapon, "capital", "closing", [t1, t2],
            dice, [])
        # At minimum die=4 should hit t1 (armor 4+) rather than t2 (armor 5+)
        assert result.hits_by_ship.get(t1.id, 0) > 0

    def test_hits_by_ship_populated_for_each_hit_ship(self):
        attacker, t1, t2, gs = self._pair(armor_a=3, armor_b=3)
        weapon = self._make_weapon(strength=6)
        dice = DiceStub([6, 6, 6, 6, 6, 6])
        result = resolve_batteries_vs_squadron(
            attacker, weapon, "capital", "abeam", [t1, t2],
            dice, [])
        assert result.hits > 0
        assert t1.id in result.hits_by_ship

    def test_description_contains_attacker_and_hit_ship_name(self):
        attacker, t1, t2, gs = self._pair(armor_a=4, armor_b=4)
        weapon = self._make_weapon(strength=6)
        dice = DiceStub([5, 5, 5, 5, 5, 5])
        result = resolve_batteries_vs_squadron(
            attacker, weapon, "capital", "abeam", [t1, t2],
            dice, [])
        assert "T1" in result.description or "T2" in result.description

    def test_zero_firepower_returns_no_firepower(self):
        attacker = make_ship(id="att", x=0.0, y=0.0, player=1)
        weapon = self._make_weapon(strength=0)
        t1 = make_ship(id="t1", x=20.0, y=0.0, player=2)
        dice = DiceStub([6] * 10)
        result = resolve_batteries_vs_squadron(
            attacker, weapon, "capital", "abeam", [t1],
            dice, [])
        assert result.hits == 0
        assert "no firepower" in result.description


# ---------------------------------------------------------------------------
# resolve_batteries_vs_squadron — gunnery column selection
# ---------------------------------------------------------------------------

class TestGunneryColumnSelection:
    def _weapon(self, strength=6):
        return {
            "name": "Broadsides",
            "weapon_type": "battery",
            "strength": strength,
            "range_cm": 30,
            "arcs": ["left", "right"],
        }

    def test_closing_capital_uses_best_column(self):
        # "closing" capital → col 2, more dice than "abeam" col 4
        attacker = make_ship(id="att", x=0.0, y=0.0, player=1)
        t1 = make_ship(id="t1", x=10.0, y=0.0, armor_side="4+",
                       ship_type="cruiser", player=2)
        weapon = self._weapon(strength=6)
        # Closing should yield more dice → more likely to hit with all-5 dice
        dice_closing = DiceStub([5] * 30)
        r_closing = resolve_batteries_vs_squadron(
            attacker, weapon, "cruiser", "closing", [t1], dice_closing, [])
        dice_abeam = DiceStub([5] * 30)
        r_abeam = resolve_batteries_vs_squadron(
            attacker, weapon, "cruiser", "abeam", [t1], dice_abeam, [])
        # Closing (col2) uses more dice than abeam (col4) for same FP
        assert len(r_closing.dice_rolled) >= len(r_abeam.dice_rolled)
