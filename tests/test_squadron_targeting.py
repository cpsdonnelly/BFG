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

    def test_rolls_dice_and_reports_armour_without_allocating(self):
        attacker, t1, t2, gs = self._pair(armor_a=4, armor_b=5)
        weapon = self._make_weapon(strength=6)
        dice = DiceStub([5, 5, 5, 5, 5, 5])
        result = resolve_batteries_vs_squadron(
            attacker, weapon, "capital", "abeam", [t1, t2], dice, [])
        assert result.dice_rolled and all(d == 5 for d in result.dice_rolled)
        assert result.armors == {"t1": 4, "t2": 5}
        assert "att" in result.description

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



class TestAllocateSquadronHits:
    """Core rules s.5 Shooting at Squadrons: nearest eligible ship until it is
    destroyed (critical damage included), then the next takes what is left."""

    def _apply(self, gs, dice):
        from src.combat import apply_damage

        def apply(ship, n):
            r = apply_damage(gs.get_ship_by_id(ship.id), n, dice, gs)
            return r["unused_hits"], r["destroyed"]
        return apply

    def test_booklet_example_three_dauntless_take_thirteen_hits(self):
        from src.combat import allocate_squadron_hits
        ships = [make_ship(id=f"d{i}", player=2, hits_max=6, shields_max=1,
                           x=20.0 * i, y=50.0) for i in range(1, 4)]
        gs = make_gs(ships)
        damage_rolls = (
            [6, 8,      # D1 hit 1: crit check 6, crit 8 = Thrusters Damaged (+1)
             6, 6,      # D1 hit 2: crit check 6, crit 6 = Engine Room Damaged (+1)
             1]         # D1 hit 3: no crit; hit 4 destroys it -> 8 hits left
            + [1] * 5   # D2: shield + 5 hull hits with crit checks; 6th hull hit destroys it
        )
        dice = DiceStub(damage_rolls)
        applied = allocate_squadron_hits([5] * 13, ships, lambda s: 5,
                                         self._apply(gs, dice))
        assert dice._idx == len(damage_rolls)
        assert applied == {"d1": 5, "d2": 7, "d3": 1}
        assert [gs.get_ship_by_id(f"d{i}").hits_remaining for i in (1, 2, 3)] == [0, 0, 6]

    def test_nearest_ship_that_survives_keeps_every_hit(self):
        from src.combat import allocate_squadron_hits
        near = make_ship(id="n", player=2, hits_max=8, shields_max=0, x=20.0)
        far = make_ship(id="f", player=2, hits_max=8, shields_max=0, x=40.0)
        gs = make_gs([near, far])
        dice = DiceStub([1, 1])                  # two crit checks, no crits
        applied = allocate_squadron_hits([5, 5], [near, far], lambda s: 4,
                                         self._apply(gs, dice))
        assert applied == {"n": 2}
        assert gs.get_ship_by_id("f").hits_remaining == 8

    def test_no_die_beats_nearest_armour_so_nothing_reaches_the_next_ship(self):
        from src.combat import allocate_squadron_hits
        near = make_ship(id="n", player=2, armor_side="6+", x=20.0)
        far = make_ship(id="f", player=2, armor_side="4+", x=40.0)
        gs = make_gs([near, far])
        armour = {"n": 6, "f": 4}
        applied = allocate_squadron_hits([4, 5], [near, far], lambda s: armour[s.id],
                                         self._apply(gs, DiceStub([1])))
        assert applied == {}

    def test_dice_that_missed_a_destroyed_ship_can_hit_the_next(self):
        from src.combat import allocate_squadron_hits
        near = make_ship(id="n", player=2, ship_type="escort", hits_max=1,
                         shields_max=0, x=20.0)
        far = make_ship(id="f", player=2, ship_type="escort", hits_max=2,
                        shields_max=0, x=40.0)
        gs = make_gs([near, far])
        armour = {"n": 6, "f": 4}
        dice = DiceStub([1])                     # far: crit check on its first hit
        applied = allocate_squadron_hits([6, 4, 4], [near, far],
                                         lambda s: armour[s.id], self._apply(gs, dice))
        # The 6 destroys the 6+ escort; both 4s then hit the 4+ escort behind it
        assert applied == {"n": 1, "f": 2}
        assert dice._idx == 1
