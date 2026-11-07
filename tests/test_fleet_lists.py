"""Fleet lists (core rules s.4 and the faction Fleet Composition sections)."""
from src.fleet_lists import (ALL_LISTS, LISTS, list_ships, list_cost, fleet_list_errors,
                             lists_for_faction, detachments_for, option_allowed)
from src.ship_catalog import find_ship_class


def rows(*names, list_key="", upgrades=None):
    out = []
    for n in names:
        e = find_ship_class(n)
        assert e is not None, n
        out.append({"entry": e, "upgrades": list(upgrades or []), "list": list_key})
    return out


def test_every_listed_ship_is_in_the_catalog():
    missing = [(fl["key"], c) for fl in ALL_LISTS for c in list_ships(fl)
               if find_ship_class(c) is None]
    assert missing == []


def test_list_costs_override_profile_costs():
    assert list_cost(LISTS["navy_bakka"], "Gothic Cruiser", 180) == 185
    assert list_cost(LISTS["navy_gothic"], "Gothic Cruiser", 180) == 180
    assert list_cost(None, "Gothic Cruiser", 180) == 180


def test_gothic_battleship_ratio_and_cruiser_cap():
    ok = rows("Emperor Battleship", "Gothic Cruiser", "Lunar Cruiser", "Tyrant Cruiser",
              list_key="navy_gothic")
    assert fleet_list_errors("navy_gothic", ok, 1500) == []
    bad = rows("Emperor Battleship", "Gothic Cruiser", "Lunar Cruiser", list_key="navy_gothic")
    errs = fleet_list_errors("navy_gothic", bad, 1500)
    assert len(errs) == 1 and "Battleships" in errs[0]
    many = rows(*["Lunar Cruiser"] * 13, list_key="navy_gothic")
    assert any("at most 12" in e for e in fleet_list_errors("navy_gothic", many, 3000))


def test_ship_not_in_the_list():
    r = rows("Siluria Light Cruiser", list_key="navy_gothic")
    assert any("isn't in" in e for e in fleet_list_errors("navy_gothic", r, 1000))


def test_battlecruisers_count_towards_battleships_but_need_cruisers():
    r = rows("Retribution Battleship", "Mars Battlecruiser", "Gothic Cruiser",
             "Lunar Cruiser", list_key="navy_gothic")
    assert fleet_list_errors("navy_gothic", r, 1500) == []      # 1 BC per 2 cruisers; BS per 3


def test_bakka_battleships_per_750_points_and_dauntless_cap():
    r = rows("Retribution Battleship", "Victory Battleship", list_key="navy_bakka")
    errs = fleet_list_errors("navy_bakka", r, 1000)
    assert any("per 750pts" in e for e in errs)
    assert not any("per 750pts" in e for e in fleet_list_errors("navy_bakka", r, 1500))
    d = rows(*["Dauntless Light Cruiser"] * 3, list_key="navy_bakka")
    assert any("Dauntless" in e and "at most 2" in e
               for e in fleet_list_errors("navy_bakka", d, 1500))


def test_armageddon_endurance_defiant_combined_per_500():
    r = rows("Endurance Light Cruiser", "Defiant Light Cruiser", "Endurance Light Cruiser",
             list_key="navy_armageddon")
    assert any("combined" in e for e in fleet_list_errors("navy_armageddon", r, 500))   # max 2
    assert not any("combined" in e for e in fleet_list_errors("navy_armageddon", r, 1000))


def test_bastion_grand_cruisers_dont_count_for_battleships():
    r = rows("Emperor Battleship", "Exorcist Grand Cruiser", "Gothic Cruiser",
             "Lunar Cruiser", list_key="navy_bastion")
    errs = fleet_list_errors("navy_bastion", r, 1500)
    assert any(e.startswith("Battleships") for e in errs)        # 2 cruisers + GC isn't 3


def test_reserves_one_per_three_of_the_same_type():
    own = rows("Gothic Cruiser", "Lunar Cruiser", "Tyrant Cruiser", list_key="navy_gothic")
    res = rows("Mechanicus Lunar Cruiser", list_key="reserve:admech_explorator")
    assert fleet_list_errors("navy_gothic", own + res, 1500) == []
    res2 = res + rows("Mechanicus Gothic Cruiser", list_key="reserve:admech_explorator")
    assert any("Reserves" in e for e in fleet_list_errors("navy_gothic", own + res2, 1500))


def test_crusade_needs_master_of_the_fleet_at_750():
    r = rows("Space Marine Battle Barge", list_key="sm_crusade")
    assert any("fleet commander" in e for e in fleet_list_errors("sm_crusade", r, 1000))
    r = rows("Space Marine Battle Barge", list_key="sm_crusade",
             upgrades=["Master of the Fleet (Ld 10)"])
    assert fleet_list_errors("sm_crusade", r, 1000) == []
    assert fleet_list_errors("sm_crusade", rows("Strike Cruiser", list_key="sm_crusade"),
                             500) == []


def test_lightning_thrusters_lets_dominion_take_vanguards():
    lt = ["Master of the Fleet (Ld 10)", "Chapter tactic: Lightning Thrusters"]
    barge = rows("Space Marine Battle Barge", list_key="sm_dominion", upgrades=lt)
    van = rows("Vanguard Cruiser", "Vanguard Cruiser", list_key="sm_dominion")
    assert fleet_list_errors("sm_dominion", barge + van, 1000) == []
    plain = rows("Space Marine Battle Barge", list_key="sm_dominion",
                 upgrades=["Master of the Fleet (Ld 10)"])
    assert any("Vanguard" in e for e in fleet_list_errors("sm_dominion", plain + van, 1000))
    five = rows(*["Vanguard Cruiser"] * 5, list_key="sm_dominion")
    assert any("Vanguard" in e for e in fleet_list_errors("sm_dominion", barge + five, 1500))


def test_dominion_reserves_per_strike_cruisers():
    own = rows("Strike Cruiser", "Strike Cruiser", list_key="sm_dominion")
    res = rows("Lunar Cruiser", list_key="reserve:navy_gothic")
    assert fleet_list_errors("sm_dominion", own + res, 500) == []
    res2 = res + rows("Gothic Cruiser", list_key="reserve:navy_gothic")
    assert any("Reserves" in e for e in fleet_list_errors("sm_dominion", own + res2, 500))


def test_inquisition_detachment_joins_navy_and_limits_cruisers():
    assert "inq_detachment" in [d["key"] for d in detachments_for("navy_gothic")]
    own = rows("Gothic Cruiser", "Lunar Cruiser", "Tyrant Cruiser", list_key="navy_gothic")
    inq = rows("Inquisitorial Cruiser", list_key="inq_detachment")
    assert fleet_list_errors("navy_gothic", own + inq, 1500, ["inq_detachment"]) == []
    inq2 = inq + rows("Inquisitorial Cruiser", list_key="inq_detachment")
    assert any("Inquisitorial Cruisers" in e
               for e in fleet_list_errors("navy_gothic", own + inq2, 1500, ["inq_detachment"]))


def test_inferno_torpedoes_only_with_the_detachment():
    assert not option_allowed("Inferno Torpedoes", ["inq_banisher"])
    assert option_allowed("Inferno Torpedoes", ["navy_gothic", "inq_detachment"])
    assert option_allowed("Inferno Torpedoes", [])                 # no fleet list
    assert option_allowed("Torpedoes: short burn (40cm; out of fuel on a 6)", ["navy_gothic"])


def test_every_faction_with_ships_has_a_list():
    for f in ("imperial_navy_gothic", "adeptus_mechanicus", "space_marines",
              "inquisition_grey_knights", "chaos", "orks", "tau_kororvesh"):
        assert lists_for_faction(f), f


def test_every_ratio_reserve_and_join_names_something_real():
    for fl in ALL_LISTS:
        names = {sec["name"] for sec in fl["sections"]}
        for sec in fl["sections"]:
            if sec.get("ratio") and sec["ratio"][1] != ["*cruisers"]:
                assert set(sec["ratio"][1]) <= names, (fl["key"], sec["name"])
        for k in fl.get("reserves", []) + fl.get("joins", []):
            assert k in LISTS, (fl["key"], k)


def test_ork_battleships_need_two_kroozers_each():
    r = rows("Gorbag's Revenge (0-1)", "Kill Kroozer", list_key="orks_green_tide")
    assert any("Battleships" in e for e in fleet_list_errors("orks_green_tide", r, 1500))
    r += rows("Terror Ship", list_key="orks_green_tide")
    assert not any("Battleships" in e for e in fleet_list_errors("orks_green_tide", r, 1500))


# ── Owner rulings (export 15) ────────────────────────────────────────────────

def test_points_limits_use_the_fleet_total_full_rounds_down_portion_rounds_up():
    from src.fleet_lists import _list_errors
    r = rows("Retribution Battleship", "Victory Battleship", list_key="navy_bakka")
    assert any("per 750pts" in e for e in fleet_list_errors("navy_bakka", r, 1499))   # 1
    assert not any("per 750pts" in e for e in fleet_list_errors("navy_bakka", r, 1500))
    # "(or portion thereof)": GK strike cruisers one per 500pts or part, so 2 at 501pts
    gk = rows("Grey Knights Strike Cruiser", "Grey Knights Strike Cruiser",
              list_key="inq_detachment")
    assert _list_errors(LISTS["inq_detachment"], gk, 501, gk) == []
    assert any("per 500pts" in e for e in _list_errors(LISTS["inq_detachment"], gk, 500, gk))


def test_space_marine_battle_barges_flagship_and_command_ships():
    mof = ["Master of the Fleet (Ld 10)"]
    for key in ("sm_crusade", "sm_dominion"):
        ven = rows("Emperor Battle Barge", list_key=key, upgrades=mof)
        assert "Emperor Battle Barge" in list_ships(LISTS[key])
        assert any("1000pts" in e for e in fleet_list_errors(key, ven, 999))
        assert fleet_list_errors(key, ven, 1000) == []
        two_flags = ven + rows("Ultima Battle Barge", list_key=key)
        assert any("Chapter Flagship" in e for e in fleet_list_errors(key, two_flags, 2000))
        three = rows(*["Space Marine Battle Barge"] * 3, list_key=key, upgrades=mof)
        assert fleet_list_errors(key, three, 3000) == []          # flagship + 2 command ships
        assert any("Chapter Flagship" in e or "Command" in e
                   for e in fleet_list_errors(key, ven + three, 4000))
        # one battle barge per 1000pts or portion thereof
        assert any("per 1000pts" in e for e in fleet_list_errors(
            key, rows(*["Space Marine Battle Barge"] * 2, list_key=key, upgrades=mof), 1000))


def test_chaos_battleships_count_cruisers_and_heavy_cruisers_not_light():
    r = rows("Despoiler Battleship", "Murder Cruiser", "Hades Heavy Cruiser", "Styx Heavy Cruiser",
             list_key="chaos_black_crusade")
    assert not any(e.startswith("Battleships") for e in
                   fleet_list_errors("chaos_black_crusade", r, 1500))
    lc = rows("Despoiler Battleship", "Murder Cruiser", "Fanatic Light Cruiser",
              "Fanatic Light Cruiser", list_key="chaos_black_crusade")
    assert any(e.startswith("Battleships") for e in
               fleet_list_errors("chaos_black_crusade", lc, 1500))
    hc = rows("Hades Heavy Cruiser", "Hades Heavy Cruiser", "Murder Cruiser", "Murder Cruiser",
              list_key="chaos_black_crusade")
    assert any(e.startswith("Heavy Cruisers") for e in      # heavy: per two cruisers only
               fleet_list_errors("chaos_black_crusade", hc, 1500))


def test_renegade_cruisers_count_for_chaos_ratios():
    r = rows("Desolator Battleship", "Murder Cruiser", "Carnage Cruiser", list_key="chaos_renegades")
    assert any(e.startswith("Battleships") for e in fleet_list_errors("chaos_renegades", r, 1500))
    r += rows("Lunar Cruiser", list_key="chaos_renegades")
    assert not any(e.startswith("Battleships") for e in
                   fleet_list_errors("chaos_renegades", r, 1500))
    both = rows("Lunar Cruiser", *["Sword Frigate"] * 6, list_key="chaos_renegades")
    assert fleet_list_errors("chaos_renegades", both, 750) == []      # six escorts and a cruiser


def test_rogue_trader_detachment_may_join_orks_and_god_fleets():
    joins = LISTS["rt_detachment"]["joins"]
    assert "orks_green_tide" in joins and "chaos_khorne" in joins
    assert "sm_crusade" not in joins and "inq_banisher" not in joins


def test_expedition_space_marine_support_bars_xenos():
    exp = rows("Dauntless Light Cruiser", "Dauntless Light Cruiser", "Dauntless Light Cruiser",
               list_key="rt_expedition")
    merc = rows("Kroot Warsphere", list_key="rt_expedition")
    sm = rows("Strike Cruiser", list_key="reserve:sm_dominion")
    assert not any("xenos" in e for e in fleet_list_errors("rt_expedition", exp + merc, 1000))
    errs = fleet_list_errors("rt_expedition", exp + merc + sm, 1000)
    assert any("xenos" in e for e in errs)
    navy = rows("Lunar Cruiser", list_key="reserve:navy_gothic")
    assert any("one supporting fleet" in e
               for e in fleet_list_errors("rt_expedition", exp + sm + navy, 1000))


def test_towed_escorts_need_hooks_and_rigs_need_four_dhows():
    from src.fleet_lists import towed_errors
    merchant = rows("Merchant Starship")
    assert towed_errors(merchant + rows("Orca Gunship", "Orca Gunship")) == []
    assert towed_errors(merchant + rows(*["Orca Gunship"] * 3))
    assert towed_errors(rows("Warden Gunship"))
    rig = rows("Nicassar Rig")
    assert any("four Dhows" in e for e in towed_errors(rig + rows("Nicassar Dhow")))
    assert towed_errors(rig + rows(*["Nicassar Dhow"] * 4)) == []
    assert towed_errors(rig + rows(*["Nicassar Dhow"] * 5))           # only four hooks


def test_never_more_strongholds_than_bastions():
    r = rows("Stronghold Commerce Vessel", list_key="tau_empire")
    assert any("Stronghold" in e for e in fleet_list_errors("tau_empire", r, 1000))
    r += rows("Bastion Commerce Vessel", list_key="tau_empire")
    assert not any("Never more" in e for e in fleet_list_errors("tau_empire", r, 1000))


def test_custodians_per_750_of_tau_vessels():
    allies = rows("Stronghold Commerce Vessel", "Bastion Commerce Vessel", "Bastion Commerce Vessel",
                  list_key="tau_empire")
    cust = rows("Custodian Battleship", list_key="tau_empire")
    pts = [dict(r, points=r["entry"].points_cost) for r in cust + allies]
    assert any("Battleships" in e for e in fleet_list_errors("tau_empire", pts, 1195))
    tau = [dict(r, points=r["entry"].points_cost)
           for r in rows("Protector Cruiser", "Protector Cruiser", "Hero Starship",
                         list_key="tau_empire")]
    assert not any("Battleships" in e for e in fleet_list_errors("tau_empire", pts + tau, 1735))


def test_demiurg_fixed_leadership_drops_with_damage():
    from tests.conftest import DiceStub, make_gs
    from src.combat import apply_damage
    from src.models import Ship
    e = find_ship_class("Citadel Commerce Vessel")
    d = e.to_ship_dict("C", 2)
    assert d["leadership"] == 9 and not d["leadership_table"]
    ship = Ship(**{**{k: v for k, v in d.items() if k in Ship.__dataclass_fields__},
                   "id": "c", "x": 50.0, "y": 50.0})
    gs = make_gs([ship])
    rolls = [1, 1, 1, 1, 1]
    dice = DiceStub(rolls)
    apply_damage(ship, 5, dice, gs, ignores_shields=True)
    assert dice._idx == len(rolls) and gs.get_ship_by_id("c").leadership == 5   # 9-5 -> 5 min
