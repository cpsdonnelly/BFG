"""Demiurg War Host (bfgxr/rules/09_tau-allies.md, Xenos p.101; CHANGES updates 22-23)."""
from tests.conftest import make_gs, make_ship
from tests.test_fleet_lists import rows
from src.fleet_lists import fleet_list_errors, option_allowed, reserve_allowed

WH = "tau_demiurg_war_host"
BASTION, CITADEL = "Bastion Commerce Vessel", "Citadel Commerce Vessel"


def has(errs, text):
    return any(text in e for e in errs)


def test_needs_more_demiurg_than_other_cruisers_and_no_commander():
    r = rows(BASTION, CITADEL, "Protector Cruiser", list_key=WH)
    errs = fleet_list_errors(WH, r, 1000)
    assert not has(errs, "more Demiurg") and not has(errs, "commander")
    r += rows("Hero Starship", list_key=WH)
    assert has(fleet_list_errors(WH, r, 1000), "more Demiurg")
    res = rows("Protector Cruiser", list_key="reserve:tau_empire")
    assert has(fleet_list_errors(WH, rows(BASTION, CITADEL, "Protector Cruiser",
                                          list_key=WH) + res, 1200), "more Demiurg")


def test_stronghold_per_two_cruisers_and_kroot_limit():
    r = rows("Stronghold Commerce Vessel", BASTION, list_key=WH)
    assert has(fleet_list_errors(WH, r, 700), "Battleships")
    r += rows(CITADEL, list_key=WH)
    assert not has(fleet_list_errors(WH, r, 800), "Battleships")
    k = rows(*["Kroot Warsphere"] * 2, list_key=WH)
    assert not has(fleet_list_errors(WH, r + k, 1300), "Kroot")      # 2 per 1300 (or part)
    assert has(fleet_list_errors(WH, r + k, 700), "Kroot")


def test_escort_squadrons_and_mixing():
    caps = rows(BASTION, BASTION, CITADEL, list_key=WH)
    esc = rows("Orca Gunship", "Castellan Escort", list_key=WH)
    for e in esc:
        e["squadron_id"] = "e"
    errs = fleet_list_errors(WH, caps + esc, 900)
    assert has(errs, "Orca Gunships may only be mixed with Defender") and not has(errs, "at most one per three")
    more = rows("Defender Starship", "Defender Starship", list_key=WH)
    for e in more:
        e["squadron_id"] = "f"
    assert has(fleet_list_errors(WH, caps + esc + more, 1000), "at most one per three")


def test_options_and_reserves():
    assert option_allowed("War Host re-rolls: 2", [WH])
    assert not option_allowed("War Host re-rolls: 2", ["tau_empire"])
    assert not option_allowed("Kor'O (Ld 9)", [WH])
    assert reserve_allowed(WH, "tau_empire", "Protector Cruiser")
    assert not reserve_allowed(WH, "tau_empire", "Hero Starship")
    assert has(fleet_list_errors(WH, rows(BASTION, CITADEL, list_key=WH)
                                 + rows("Hero Starship", list_key="reserve:tau_empire"), 800),
               "only Kor'or'vesh")


def test_war_host_rerolls_any_demiurg_vessel_never_lost():
    from src.turn_controller import TurnController
    from tests.conftest import DiceStub
    buyer = make_ship(id="b", player=1, special_rules=["demiurg_commerce"], war_host_rerolls=2,
                      hits_remaining=0, status="destroyed")
    other = make_ship(id="o", player=1, special_rules=["demiurg_commerce"])
    tau = make_ship(id="t", player=1)
    gs = make_gs([buyer, other, tau])
    tc = TurnController(gs, DiceStub([]))
    assert tc.get_fleet_rerolls(1, other) == 2 and tc.get_fleet_rerolls(1, tau) == 0
    assert tc.use_fleet_reroll(1, other) and tc.get_fleet_rerolls(1, other) == 1
    assert not tc.use_fleet_reroll(1, tau)
