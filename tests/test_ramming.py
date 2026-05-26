"""Tests for ramming mechanics: ram_ld_dice and resolve_ram."""
import pytest
from src.combat import ram_ld_dice, resolve_ram
from src.models import Arc

from tests.conftest import make_ship, make_gs, DiceStub


# ---------------------------------------------------------------------------
# ram_ld_dice — leadership test dice count
# ---------------------------------------------------------------------------

class TestRamLdDice:
    def test_same_type_two_dice(self):
        assert ram_ld_dice("cruiser", "cruiser") == 2

    def test_target_larger_one_die(self):
        # Escort ramming a cruiser → cruiser is larger → 1D6 (easier)
        assert ram_ld_dice("escort", "cruiser") == 1
        assert ram_ld_dice("escort", "battleship") == 1
        assert ram_ld_dice("cruiser", "battleship") == 1
        assert ram_ld_dice("cruiser", "defense") == 1

    def test_target_smaller_three_dice(self):
        # Battleship ramming an escort → escort is smaller → 3D6 (harder)
        assert ram_ld_dice("battleship", "escort") == 3
        assert ram_ld_dice("cruiser", "escort") == 3
        assert ram_ld_dice("battleship", "cruiser") == 3

    def test_defence_is_largest(self):
        # Any type ramming a defence → 1D6
        assert ram_ld_dice("battleship", "defense") == 1
        assert ram_ld_dice("cruiser", "defense") == 1
        assert ram_ld_dice("escort", "defense") == 1

    def test_battleship_vs_battleship(self):
        assert ram_ld_dice("battleship", "battleship") == 2

    def test_escort_vs_escort(self):
        assert ram_ld_dice("escort", "escort") == 2


# ---------------------------------------------------------------------------
# resolve_ram — damage calculation
# ---------------------------------------------------------------------------

class TestResolveRam:
    def _pair(self, rammer_heading=0.0, target_heading=180.0,
              rammer_type="cruiser", target_type="cruiser",
              rammer_hits_max=8, target_hits_max=8):
        """Rammer at (0,0) heading east; target at (10,0) heading west → front-to-front."""
        rammer = make_ship(id="r", x=0.0, y=0.0, heading=rammer_heading,
                           ship_type=rammer_type, hits_max=rammer_hits_max,
                           hits_remaining=rammer_hits_max,
                           armor_prow="6+", armor_side="5+")
        target = make_ship(id="t", x=10.0, y=0.0, heading=target_heading,
                           ship_type=target_type, hits_max=target_hits_max,
                           hits_remaining=target_hits_max,
                           armor_prow="6+", armor_side="5+")
        gs = make_gs([rammer, target])
        return rammer, target, gs

    def test_both_ships_take_damage_on_all_hits(self):
        rammer, target, gs = self._pair()
        # rammer.hits_max=8 dice vs prow (6+) → all 6s = 8 hits
        # target.hits_max=8 dice vs rammer prow (6+) → all 6s = 8 hits
        dice = DiceStub([6] * 32)
        result = resolve_ram(rammer, target, dice, gs)
        assert result["target_hits"] == 8
        assert result["rammer_hits"] == 8
        fresh_t = gs.get_ship_by_id("t")
        fresh_r = gs.get_ship_by_id("r")
        assert fresh_t.hits_remaining == 0
        assert fresh_r.hits_remaining == 0

    def test_all_ones_no_hits(self):
        rammer, target, gs = self._pair()
        dice = DiceStub([1] * 32)
        result = resolve_ram(rammer, target, dice, gs)
        assert result["target_hits"] == 0
        assert result["rammer_hits"] == 0
        assert gs.get_ship_by_id("t").hits_remaining == 8
        assert gs.get_ship_by_id("r").hits_remaining == 8

    def test_shields_ignored_on_target(self):
        rammer = make_ship(id="r", x=0.0, y=0.0, heading=0.0,
                           hits_max=4, hits_remaining=4,
                           armor_prow="6+", armor_side="5+")
        target = make_ship(id="t", x=10.0, y=0.0, heading=180.0,
                           hits_max=8, hits_remaining=8, shields_max=3,
                           armor_prow="6+")
        gs = make_gs([rammer, target])
        # 4 dice all 6s → 4 raw hits; shields (3) should NOT absorb any
        # Use 1s for crit checks and counter rolls to keep hits clean
        dice = DiceStub([6, 6, 6, 6] + [1] * 40)
        result = resolve_ram(rammer, target, dice, gs)
        # The 4 raw hits went straight to hull (shields bypassed)
        assert result["target_hits"] == 4

    def test_front_to_front_full_counter_dice(self):
        # Rammer at (0,0) heading east; target heading west → front-to-front
        rammer, target, gs = self._pair(rammer_heading=0.0, target_heading=180.0,
                                         target_hits_max=6)
        dice = DiceStub([6] * 40)
        result = resolve_ram(rammer, target, dice, gs)
        assert result["front_to_front"] is True
        # Counter dice = target.hits_max (full 6 dice, not halved)
        assert len(result["rammer_rolls"]) == 6

    def test_not_front_to_front_halves_counter_dice(self):
        # Rammer approaches from behind target (target heading east too)
        # Both heading east → rammer is in target's REAR, not FRONT
        rammer, target, gs = self._pair(rammer_heading=0.0, target_heading=0.0,
                                         target_hits_max=6)
        dice = DiceStub([6] * 40)
        result = resolve_ram(rammer, target, dice, gs)
        assert result["front_to_front"] is False
        # Counter dice = ceil(6/2) = 3
        assert len(result["rammer_rolls"]) == 3

    def test_defence_target_always_full_counter_dice(self):
        # Even if not front-to-front, defence always returns full dice
        rammer, target, gs = self._pair(rammer_heading=0.0, target_heading=0.0,
                                         target_type="defense", target_hits_max=6)
        dice = DiceStub([6] * 40)
        result = resolve_ram(rammer, target, dice, gs)
        assert len(result["rammer_rolls"]) == 6  # full, not halved

    def test_target_facing_prow_when_rammer_ahead(self):
        # Rammer at (0,0) heading east; target at (10,0) heading east too
        # Rammer approaches from target's rear → target's REAR arc → side armor
        rammer, target, gs = self._pair(rammer_heading=0.0, target_heading=0.0)
        dice = DiceStub([1] * 40)
        result = resolve_ram(rammer, target, dice, gs)
        # Rammer is in target's REAR arc (rammer behind target) → side armor used
        assert result["target_facing"] == "side"

    def test_target_facing_side_when_rammer_behind(self):
        # Rammer at (0,0) heading east; target at (10,0) heading west
        # Rammer approaches target's front → prow armor
        rammer, target, gs = self._pair(rammer_heading=0.0, target_heading=180.0)
        dice = DiceStub([1] * 40)
        result = resolve_ram(rammer, target, dice, gs)
        assert result["target_facing"] == "prow"

    def test_result_dict_has_required_keys(self):
        rammer, target, gs = self._pair()
        dice = DiceStub([1] * 40)
        result = resolve_ram(rammer, target, dice, gs)
        for key in ("target_facing", "front_to_front", "target_rolls",
                    "target_hits", "rammer_rolls", "rammer_hits"):
            assert key in result

    def test_escort_rammer_fewer_dice(self):
        # Escort hits_max=2 → only 2 dice on target
        rammer = make_ship(id="r", x=0.0, y=0.0, heading=0.0,
                           ship_type="escort", hits_max=2, hits_remaining=2,
                           armor_prow="6+")
        target = make_ship(id="t", x=10.0, y=0.0, heading=180.0,
                           hits_max=8, hits_remaining=8, armor_prow="6+")
        gs = make_gs([rammer, target])
        dice = DiceStub([6] * 40)
        result = resolve_ram(rammer, target, dice, gs)
        assert len(result["target_rolls"]) == 2
