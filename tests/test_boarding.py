"""Tests for src/boarding.py boarding action resolution."""
import pytest
from src.boarding import (
    troop_rating, resolve_boarding, ships_in_base_contact,
    _apply_boarding_damage, _distribute_boarding_damage, _troop_advantage_bonus,
    contiguous_contact_groups, _crew_damage_bonus,
)
from src.tables import BOARDING_RESULTS

from tests.conftest import make_ship, make_gs, DiceStub


# ---------------------------------------------------------------------------
# troop_rating
# ---------------------------------------------------------------------------

class TestTroopRating:
    def test_full_health_includes_turrets(self):
        s = make_ship(hits_remaining=8, turrets=2)
        assert troop_rating(s) == 10  # 8 + 2

    def test_grappled_excludes_turrets(self):
        s = make_ship(hits_remaining=8, turrets=2)
        assert troop_rating(s, grappled=True) == 8

    def test_damaged_ship(self):
        s = make_ship(hits_remaining=4, turrets=3)
        assert troop_rating(s) == 7
        assert troop_rating(s, grappled=True) == 4

    def test_zero_hits_remaining(self):
        s = make_ship(hits_remaining=0, turrets=2)
        assert troop_rating(s) == 0  # max(0, ...)


# ---------------------------------------------------------------------------
# _troop_advantage_bonus
# ---------------------------------------------------------------------------

class TestTroopAdvantageBonus:
    def test_equal_rating_no_bonus(self):
        assert _troop_advantage_bonus(5, 5) == 0

    def test_higher_by_one_plus_one(self):
        assert _troop_advantage_bonus(6, 5) == 1

    def test_double_plus_two(self):
        assert _troop_advantage_bonus(10, 5) == 2

    def test_triple_plus_three(self):
        assert _troop_advantage_bonus(15, 5) == 3

    def test_quadruple_plus_four(self):
        assert _troop_advantage_bonus(20, 5) == 4

    def test_lower_rating_no_bonus(self):
        assert _troop_advantage_bonus(3, 5) == 0


# ---------------------------------------------------------------------------
# BOARDING_RESULTS table
# ---------------------------------------------------------------------------

class TestBoardingResultsTable:
    def test_diff_one_both_crit_on_five(self):
        row = BOARDING_RESULTS[1]
        assert row["winner_crit"] == 5
        assert row["loser_crit"] == 5

    def test_diff_five_winner_no_crit_loser_auto(self):
        row = BOARDING_RESULTS[5]
        assert row["winner_crit"] is None
        assert row["loser_crit"] == 0


# ---------------------------------------------------------------------------
# _apply_boarding_damage
# ---------------------------------------------------------------------------

class TestApplyBoardingDamage:
    def test_damage_applied_to_hull(self):
        ship = make_ship(id="s", hits_remaining=8)
        gs = make_gs([ship])
        _apply_boarding_damage(ship, 3, gs)
        fresh = gs.get_ship_by_id("s")
        assert fresh.hits_remaining == 5

    def test_reduced_to_zero_becomes_drifting_hulk(self):
        ship = make_ship(id="s", hits_remaining=3)
        gs = make_gs([ship])
        _apply_boarding_damage(ship, 3, gs)
        fresh = gs.get_ship_by_id("s")
        assert fresh.hits_remaining == 0
        assert fresh.status == "drifting_hulk"

    def test_excess_damage_does_not_go_negative(self):
        ship = make_ship(id="s", hits_remaining=2)
        gs = make_gs([ship])
        _apply_boarding_damage(ship, 10, gs)
        fresh = gs.get_ship_by_id("s")
        assert fresh.hits_remaining == 0


# ---------------------------------------------------------------------------
# _distribute_boarding_damage
# ---------------------------------------------------------------------------

class TestDistributeBoardingDamage:
    def test_single_attacker_takes_all(self):
        s = make_ship(id="s", hits_remaining=8)
        gs = make_gs([s])
        _distribute_boarding_damage([s], 3, gs)
        assert gs.get_ship_by_id("s").hits_remaining == 5

    def test_two_attackers_even_split(self):
        s1 = make_ship(id="s1", hits_remaining=8)
        s2 = make_ship(id="s2", hits_remaining=8)
        gs = make_gs([s1, s2])
        _distribute_boarding_damage([s1, s2], 4, gs)
        assert gs.get_ship_by_id("s1").hits_remaining == 6
        assert gs.get_ship_by_id("s2").hits_remaining == 6

    def test_odd_damage_remainder_goes_to_first(self):
        s1 = make_ship(id="s1", hits_remaining=8)
        s2 = make_ship(id="s2", hits_remaining=8)
        gs = make_gs([s1, s2])
        _distribute_boarding_damage([s1, s2], 3, gs)
        # 3 // 2 = 1 each, remainder 1 goes to s1
        assert gs.get_ship_by_id("s1").hits_remaining == 6
        assert gs.get_ship_by_id("s2").hits_remaining == 7


# ---------------------------------------------------------------------------
# ships_in_base_contact
# ---------------------------------------------------------------------------

class TestShipsInBaseContact:
    def test_overlapping_ships_in_contact(self):
        # Small base radius ~1.6cm; ships at same position
        a = make_ship(id="a", x=0.0, y=0.0)
        b = make_ship(id="b", x=1.0, y=0.0)
        assert ships_in_base_contact(a, b)

    def test_far_ships_not_in_contact(self):
        a = make_ship(id="a", x=0.0, y=0.0)
        b = make_ship(id="b", x=50.0, y=0.0)
        assert not ships_in_base_contact(a, b)


# ---------------------------------------------------------------------------
# contiguous_contact_groups
# ---------------------------------------------------------------------------

class TestContiguousContactGroups:
    def test_empty_input(self):
        assert contiguous_contact_groups([]) == []

    def test_single_ship_is_its_own_group(self):
        a = make_ship(id="a", x=0.0, y=0.0)
        groups = contiguous_contact_groups([a])
        assert len(groups) == 1
        assert [s.id for s in groups[0]] == ["a"]

    def test_two_touching_ships_one_group(self):
        a = make_ship(id="a", x=0.0, y=0.0)
        b = make_ship(id="b", x=1.0, y=0.0)
        groups = contiguous_contact_groups([a, b])
        assert len(groups) == 1
        assert {s.id for s in groups[0]} == {"a", "b"}

    def test_two_far_ships_two_groups(self):
        a = make_ship(id="a", x=0.0, y=0.0)
        b = make_ship(id="b", x=50.0, y=0.0)
        groups = contiguous_contact_groups([a, b])
        assert len(groups) == 2

    def test_chain_is_transitively_connected(self):
        # Contact threshold for two small ships = 1.6 + 1.6 + 1.0 margin = 4.2cm.
        # Space ships 4cm apart: a—b and b—c touch (4 ≤ 4.2) but a—c do NOT
        # (8 > 4.2). The transitive closure must still link all three.
        a = make_ship(id="a", x=0.0, y=0.0)
        b = make_ship(id="b", x=4.0, y=0.0)
        c = make_ship(id="c", x=8.0, y=0.0)
        assert not ships_in_base_contact(a, c)  # premise: a,c not directly touching
        groups = contiguous_contact_groups([a, b, c])
        assert len(groups) == 1
        assert {s.id for s in groups[0]} == {"a", "b", "c"}

    def test_two_separate_clusters(self):
        # Cluster 1: a,b touching near origin. Cluster 2: c,d touching far away.
        a = make_ship(id="a", x=0.0, y=0.0)
        b = make_ship(id="b", x=1.0, y=0.0)
        c = make_ship(id="c", x=80.0, y=0.0)
        d = make_ship(id="d", x=81.0, y=0.0)
        groups = contiguous_contact_groups([a, b, c, d])
        assert len(groups) == 2
        clusters = sorted(({s.id for s in g} for g in groups), key=lambda x: sorted(x))
        assert {"a", "b"} in clusters
        assert {"c", "d"} in clusters

    def test_order_preserved_within_group(self):
        a = make_ship(id="a", x=0.0, y=0.0)
        b = make_ship(id="b", x=4.0, y=0.0)
        c = make_ship(id="c", x=8.0, y=0.0)
        groups = contiguous_contact_groups([a, b, c])
        assert [s.id for s in groups[0]] == ["a", "b", "c"]

    def test_every_ship_appears_exactly_once(self):
        ships = [make_ship(id=str(i), x=float(i) * 40, y=0.0) for i in range(5)]
        groups = contiguous_contact_groups(ships)
        all_ids = [s.id for g in groups for s in g]
        assert sorted(all_ids) == sorted(s.id for s in ships)
        assert len(all_ids) == len(set(all_ids))


# ---------------------------------------------------------------------------
# resolve_boarding
# ---------------------------------------------------------------------------

class TestResolveBoarding:
    def _pair(self, a_hits=8, d_hits=8):
        attacker = make_ship(id="a", name="Attacker", hits_remaining=a_hits,
                             hits_max=a_hits, turrets=2, player=1)
        target = make_ship(id="t", name="Target", hits_remaining=d_hits,
                           hits_max=d_hits, turrets=2, player=2)
        gs = make_gs([attacker, target])
        return attacker, target, gs

    def test_attacker_wins_target_takes_damage(self):
        attacker, target, gs = self._pair()
        # attacker rolls 6 (total ~6+0+1=7), defender rolls 1 (total ~1+0+0=1) → diff 6
        # Both have equal troop rating initially (no bonus), no mods
        dice = DiceStub([6, 1] + [1] * 20)  # a_roll=6, d_roll=1, then crit checks
        result = resolve_boarding([attacker], target, dice, gs)
        assert result["winner"] == "attacker"
        assert result["damage"] > 0
        fresh_t = gs.get_ship_by_id("t")
        assert fresh_t.hits_remaining < 8

    def test_defender_wins_attacker_takes_damage(self):
        attacker, target, gs = self._pair()
        # attacker rolls 1, defender rolls 6 → defender wins
        dice = DiceStub([1, 6] + [1] * 20)
        result = resolve_boarding([attacker], target, dice, gs)
        assert result["winner"] == "defender"
        assert result["damage"] > 0
        fresh_a = gs.get_ship_by_id("a")
        assert fresh_a.hits_remaining < 8

    def test_draw_sets_grapple_flag(self):
        attacker, target, gs = self._pair()
        # Equal rolls, equal troop ratings → draw
        dice = DiceStub([3, 3] + [1] * 20)
        result = resolve_boarding([attacker], target, dice, gs)
        assert result["grapple"] is True
        assert result["damage"] == 0
        # resolve_boarding returns the flag; the UI panel applies gs state
        assert result["winner"] == "draw"

    def test_loser_reduced_to_zero_becomes_drifting_hulk(self):
        attacker, target, gs = self._pair(d_hits=2)
        # attacker rolls max, defender rolls 1 → attacker wins by large margin → target at 0
        dice = DiceStub([6, 1] + [1] * 20)
        result = resolve_boarding([attacker], target, dice, gs)
        fresh_t = gs.get_ship_by_id("t")
        assert fresh_t.status == "drifting_hulk"

    def test_multi_ship_combined_troop_rating(self):
        # Two small attackers vs one target — combined troop rating should beat individual
        # hits_max=4 so they are NOT crippled (hits_remaining == hits_max)
        a1 = make_ship(id="a1", name="A1", hits_remaining=4, hits_max=4, turrets=1, player=1)
        a2 = make_ship(id="a2", name="A2", hits_remaining=4, hits_max=4, turrets=1, player=1)
        target = make_ship(id="t", name="Target", hits_remaining=6, hits_max=8, turrets=2, player=2)
        gs = make_gs([a1, a2, target])
        # Combined attacker rating = (4+1) + (4+1) = 10; target = 6+2 = 8 → attacker +1 bonus
        # Roll: a=1, d=1 → a_total=1+0+1=2; d_total=1+0+0=1 → attacker wins
        dice = DiceStub([1, 1] + [1] * 20)
        result = resolve_boarding([a1, a2], target, dice, gs)
        assert result["winner"] == "attacker"

    def test_result_has_required_keys(self):
        attacker, target, gs = self._pair()
        dice = DiceStub([1] * 20)
        result = resolve_boarding([attacker], target, dice, gs)
        for key in ("attacker_roll", "defender_roll", "winner", "damage",
                    "loser_ships", "attacker_crits", "defender_crits", "grapple"):
            assert key in result

    def test_crippled_defender_gives_attacker_bonus(self):
        # Crippled defender: +2 to attacker's modifier
        attacker = make_ship(id="a", hits_remaining=8, turrets=2, player=1)
        target = make_ship(id="t", hits_remaining=3, hits_max=8,  # ≤ half → crippled
                           turrets=2, player=2)
        gs = make_gs([attacker, target])
        # Tie roll, but attacker gets +2 from target being crippled
        dice = DiceStub([3, 3] + [1] * 20)
        result = resolve_boarding([attacker], target, dice, gs)
        # attacker: 3+2(crippled mod)=5; defender: 3+0=3 → attacker wins
        assert result["winner"] == "attacker"


class TestCrewDamageBonus:
    def test_default_no_special_rules_is_zero(self):
        s = make_ship(special_rules=[])
        assert _crew_damage_bonus(s) == 0

    def test_unrelated_special_rule_is_zero(self):
        s = make_ship(special_rules=["targeting_matrix"])
        assert _crew_damage_bonus(s) == 0

    def test_space_marine_crew_gets_plus_two(self):
        s = make_ship(special_rules=["space_marine_crew"])
        assert _crew_damage_bonus(s) == 2

    def test_space_marine_bonus_applied_in_boarding(self):
        # Equal troop ratings and equal rolls; only the +2 marine crew bonus differs.
        attacker = make_ship(id="a", name="Marine", hits_remaining=8, hits_max=8,
                             turrets=2, player=1, special_rules=["space_marine_crew"])
        target = make_ship(id="t", name="Target", hits_remaining=8, hits_max=8,
                           turrets=2, player=2)
        gs = make_gs([attacker, target])
        dice = DiceStub([3, 3] + [1] * 20)  # tie roll
        result = resolve_boarding([attacker], target, dice, gs)
        # attacker: 3 + 2(crew) = 5; defender: 3 → attacker wins by 2
        assert result["winner"] == "attacker"
        assert result["damage"] == 2
