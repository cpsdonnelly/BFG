"""Space Marine (and Grey Knights) faction rules, Bombardment Cannons."""
import pytest
from tests.conftest import make_ship, make_gs, DiceStub
from src.ship_catalog import find_ship_class
from src.combat import resolve_batteries, apply_damage
from src.movement import aaf_bonus_dice, resolve_aaf_speed, do_command_check
from src.hit_and_run import check_teleport_eligibility, _raid_roll_modifier
from src.boarding import resolve_boarding
from src.victory_points import calculate_victory_points


def test_catalog_faction_rules():
    sc = find_ship_class("Strike Cruiser")
    assert sc.playable and {"space_marine_crew", "teleport_assault"} <= set(sc.special_rules)
    assert sc.leadership_table == "Astartes"
    rsv = find_ship_class("Sword Rapid Strike Vessel")      # "no Space Marine rules apply"
    assert "space_marine_crew" not in rsv.special_rules and rsv.leadership_table == "Default"
    gk = find_ship_class("Grey Knights Strike Cruiser")
    assert {"space_marine_crew", "knights_of_titan", "improved_thrusters"} <= set(gk.special_rules)
    assert gk.leadership_table == "Astartes"                 # all Space Marine rules
    emperor = find_ship_class("Emperor Battle Barge")
    assert {"ponderous", "venerable"} <= set(emperor.special_rules)
    assert "improved_thrusters" in find_ship_class("Vanguard Cruiser").special_rules
    assert "improved_thrusters" not in find_ship_class("Exorcist Grand Cruiser").special_rules  # +5pts refit
    assert "ere_we_go" in find_ship_class("Kill Kroozer").special_rules


def test_catalog_bombardment_cannons_and_killkannons():
    sc = find_ship_class("Strike Cruiser")
    bc = next(w for w in sc.weapons if "Bombardment" in w["name"])
    assert (bc["weapon_type"], bc["hits_on"], bc["crit_on"]) == ("battery", 4, 4)
    dd = find_ship_class("Dethdeala (0-1)")
    assert dd.playable and any(w.get("hits_on") == 4 for w in dd.weapons)


BC = {"name": "Prow Bombardment Cannon", "weapon_type": "battery", "strength": 3,
      "range_cm": 30, "arcs": ["front"], "hits_on": 4, "crit_on": 4}


def test_bombardment_cannon_hits_on_4_regardless_of_armour():
    attacker = make_ship(id="a", player=1, x=0.0, y=0.0, heading=0.0, weapons=[BC])
    target = make_ship(id="t", player=2, x=20.0, y=0.0, heading=180.0,
                       armor_prow="6+", armor_side="6+")       # closing, prow 6+
    from src.tables import lookup_gunnery_dice, get_gunnery_column
    n = lookup_gunnery_dice(3, get_gunnery_column("capital", "closing"), 0)
    rolls = [4] * n
    dice = DiceStub(rolls)
    r = resolve_batteries(attacker, target, BC, dice, [])
    assert dice._idx == n and r.hits == n


def test_crits_on_4_plus():
    t = make_ship(id="t", player=2, hits_max=8, shields_max=0)
    gs = make_gs([t])
    rolls = [4,          # crit check 4+: crit
             6]          # 2D6 crit table: 6 (Engine Room in this table? any result)
    dice = DiceStub(rolls + [1] * 4)
    r = apply_damage(t, 1, dice, gs, crit_on=4)
    assert len(r["crits"]) == 1
    t2 = make_ship(id="t2", player=2, hits_max=8, shields_max=0)
    gs2 = make_gs([t2])
    dice = DiceStub([4])
    assert apply_damage(t2, 1, dice, gs2)["crits"] == [] and dice._idx == 1


def test_all_ahead_full_dice():
    assert aaf_bonus_dice(make_ship()) == 4
    assert aaf_bonus_dice(make_ship(special_rules=["improved_thrusters"])) == 5
    ork = make_ship(special_rules=["ere_we_go"])
    assert aaf_bonus_dice(ork) == 3
    rolls = [1, 2, 3]
    dice = DiceStub(rolls)
    assert resolve_aaf_speed(ork, dice) == 6 and dice._idx == 3


def test_orks_auto_pass_all_ahead_full():
    ork = make_ship(special_rules=["ere_we_go"], leadership=5)
    dice = DiceStub([12])
    assert do_command_check(ork, "all_ahead_full", dice)["passed"] and dice._idx == 0
    assert not do_command_check(ork, "lock_on", DiceStub([12]))["passed"]


def test_teleport_assault_bigger_targets():
    sm = make_ship(id="a", player=1, hits_max=6, x=0.0, y=0.0,
                   special_rules=["space_marine_crew", "teleport_assault"])
    big = make_ship(id="t", player=2, hits_max=12, shields_max=0, x=8.0, y=0.0)
    gs = make_gs([sm, big])
    assert check_teleport_eligibility(sm, big, gs)[0]
    plain = make_ship(id="b", player=1, hits_max=6, x=0.0, y=0.0)
    assert not check_teleport_eligibility(plain, big, gs)[0]


def test_space_marine_raid_modifiers():
    sm_target = make_ship(special_rules=["space_marine_crew"])
    assert _raid_roll_modifier(["space_marine_crew"], make_ship()) == 1
    assert _raid_roll_modifier([], sm_target) == -1


def test_knights_of_titan_rerolls_a_lost_boarding_action():
    gk = make_ship(id="a", player=1, hits_max=8, turrets=2, special_rules=["knights_of_titan"])
    enemy = make_ship(id="t", player=2, hits_max=8, turrets=2)
    gs = make_gs([gk, enemy])
    rolls = [1, 4,       # 1 vs 4: Grey Knights lose -> re-roll
             6, 2,       # 6 vs 2: attackers win by 4
             1,          # winner crit check (6+): no
             1]          # loser crit check (2+): no
    dice = DiceStub(rolls)
    r = resolve_boarding([gk], enemy, dice, gs)
    assert dice._idx == len(rolls)
    assert r["winner"] == "attacker" and r["damage"] == 4


def test_venerable_battle_barge_vp():
    destroyed = make_ship(id="v1", player=1, points_value=400, hits_max=12,
                          hits_remaining=0, status="destroyed", special_rules=["venerable"])
    crippled = make_ship(id="v2", player=1, points_value=400, hits_max=12,
                         hits_remaining=6, special_rules=["venerable"])
    gs = make_gs([destroyed, crippled])
    vp = calculate_victory_points(gs)
    assert vp[2]["destroyed"] == 500 and vp[2]["crippled"] == 200


# ── Fleet options: refits, Master of the Fleet, honour guards ───────────────
from src.booklet_options import ship_option_errors, fleet_option_errors
from src.hit_and_run import teleport_range, resolve_teleport_attack


def _names(entry):
    return [u.name for u in entry.upgrades_available]


def test_strike_cruiser_options_and_costs():
    sc = find_ship_class("Strike Cruiser")
    costs = {u.name: u.points_cost for u in sc.upgrades_available}
    assert costs["Secondary Shield (+1 Shield)"] == 15
    # Tactical Flexibility: -10 on each variant refit (min 0)
    assert costs["Variant: prow Bombardment Cannon"] == 0
    assert costs["Variant: prow torpedoes"] == 0
    assert costs["Variant: macrobatteries to launch bays"] == 10
    assert "Secondary Shield (+1 Shield)" in _names(find_ship_class("Vanguard Cruiser"))
    assert _names(find_ship_class("Sword Rapid Strike Vessel")) == []


def test_variant_swaps_weapons():
    sc = find_ship_class("Strike Cruiser")
    d = sc.to_ship_dict("Spear", 1, upgrades=["Variant: prow torpedoes",
                                              "Variant: macrobatteries to launch bays",
                                              "Secondary Shield (+1 Shield)"])
    names = sorted(w["name"] for w in d["weapons"])
    assert names == ["Port Launch Bays", "Prow Bombardment Cannon", "Prow Torps",
                     "Starboard Launch Bays"]
    torps = next(w for w in d["weapons"] if w["name"] == "Prow Torps")
    assert torps["strength"] == 6 and torps["boarding_torpedoes"]
    assert d["shields_max"] == sc.shields_max + 1
    assert d["points_value"] == 145 + 0 + 10 + 15


def test_option_groups_and_requirements():
    sc = find_ship_class("Strike Cruiser")
    assert ship_option_errors(sc, ["Variant: prow torpedoes",
                                   "Variant: prow Bombardment Cannon"])
    bb = find_ship_class("Space Marine Battle Barge")
    assert ship_option_errors(bb, ["Master of the Fleet: 2 re-rolls"])        # needs MoF
    assert not ship_option_errors(bb, ["Master of the Fleet (Ld 10)",
                                       "Master of the Fleet: 2 re-rolls"])
    assert ship_option_errors(bb, ["Master of the Fleet (Ld 10)",
                                   "Master of the Fleet: 1 re-roll",
                                   "Master of the Fleet: 3 re-rolls"])


def test_fleet_limits():
    sc = find_ship_class("Strike Cruiser")
    bb = find_ship_class("Space Marine Battle Barge")
    var = ["Variant: prow torpedoes"]
    mof = ["Master of the Fleet (Ld 10)"]
    assert not fleet_option_errors([(bb, mof), (sc, var), (sc, [])], 800)
    assert fleet_option_errors([(bb, mof), (sc, var), (sc, var)], 800)       # 2 of 2
    assert fleet_option_errors([(bb, mof), (bb, mof)], 900)                 # two MoF
    assert any("Master of the Fleet" in e for e in fleet_option_errors([(bb, []), (sc, [])], 800))
    assert not fleet_option_errors([(bb, []), (sc, [])], 700)


def test_master_of_the_fleet_ship():
    bb = find_ship_class("Space Marine Battle Barge")
    d = bb.to_ship_dict("Hammer", 1, upgrades=["Master of the Fleet (Ld 10)",
                                               "Master of the Fleet: 2 re-rolls",
                                               "Master of the Fleet: Terminator honour guard"])
    assert d["leadership"] == 10 and d["leadership_table"] == ""     # not rolled
    assert d["rerolls_remaining"] == 2 and d["is_flagship"]
    assert "terminator_honour_guard" in d["special_rules"]
    assert d["points_value"] == 425 + 50 + 50 + 25


def test_terminator_honour_guard_teleport():
    hg = make_ship(id="a", player=1, hits_max=12, x=0.0, y=0.0,
                   special_rules=["space_marine_crew", "teleport_assault",
                                  "terminator_honour_guard"])
    target = make_ship(id="t", player=2, hits_max=8, shields_max=0, x=18.0, y=0.0)
    gs = make_gs([hg, target])
    assert teleport_range(hg) == 20 and check_teleport_eligibility(hg, target, gs)[0]
    rolls = [2, 5, 4,      # 3D6: best two are 5 and 4
             ]
    dice = DiceStub(rolls + [1] * 6)
    r = resolve_teleport_attack(hg, target, dice, gs, lambda *a: (False, False))
    assert r["raid_rolls"] == [5, 4]
    assert len(r["crits_applied"]) == 2          # 5+1 and 4+1 Space Marine bonus


def test_escort_squadron_totals_firepower_before_halving():
    # s.8: two braced FP3 escorts fire FP3 (6 halved), not 2 + 2 = 4
    from src.combat import resolve_combined_batteries
    from src.tables import lookup_gunnery_dice, get_gunnery_column
    gun = {"name": "Battery", "weapon_type": "battery", "strength": 3, "range_cm": 30,
           "arcs": ["front"]}
    escorts = [make_ship(id=f"e{i}", ship_type="escort", x=0.0, y=float(i), heading=0.0,
                         special_order="brace_for_impact", weapons=[gun]) for i in range(2)]
    target = make_ship(id="t", player=2, x=20.0, y=0.5, heading=180.0)     # closing
    col = get_gunnery_column("capital", escorts[0].get_target_orientation(target))
    n = lookup_gunnery_dice(3, col, 0)
    assert n != lookup_gunnery_dice(4, col, 0)
    dice = DiceStub([1] * n)
    resolve_combined_batteries(escorts[0], [(e, gun) for e in escorts], target, dice, [])
    assert dice._idx == n
