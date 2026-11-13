"""Demiurg War Host (bfgxr/rules/11_tau-allies.md, Xenos p.101; CHANGES updates 22-23)."""
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


# ── Demiurg ship rules (Xenos p.91-94) ────────────────────────────────────────

def test_absorber_fields_collect_markers_and_are_never_slowed():
    from src.models import BlastMarker
    from src.movement import blast_markers_to_slow, collect_blast_markers
    d = make_ship(id="d", x=0.0, y=0.0, special_rules=["demiurg_commerce"])
    gs = make_gs([d])
    gs.add_blast_marker(BlastMarker(id="a", x=1.0, y=0.0))
    gs.add_blast_marker(BlastMarker(id="b", x=10.0, y=0.0))
    gs.add_blast_marker(BlastMarker(id="c", x=40.0, y=0.0))
    assert collect_blast_markers(d, gs, [(0.0, 0.0), (12.0, 0.0)]) == 2
    assert d.collected_blast_markers == 2 and [b["id"] for b in gs.blast_markers] == ["c"]
    assert blast_markers_to_slow(d) > 100
    other = make_ship(id="o")
    assert collect_blast_markers(other, gs, [(0.0, 0.0), (45.0, 0.0)]) == 0


def test_cutting_beam_firepower_and_range():
    from src.combat import cutting_beam_firepower
    from src.chapter_tactics import weapon_range
    d = make_ship(special_rules=["demiurg_commerce"], collected_blast_markers=3)
    beam = {"name": "Prow Cutting Beam", "weapon_type": "lance", "range_cm": 15, "strength": 1,
            "cutting_beam": True}
    assert cutting_beam_firepower(d, 10) == 4 and cutting_beam_firepower(d, 25) == 2
    assert weapon_range(d, beam) == 30
    d.collected_blast_markers = 12
    assert cutting_beam_firepower(d, 10) == 8
    d.collected_blast_markers = 1
    assert weapon_range(d, beam) == 15


def test_bastion_modular_bays_launch_one_or_the_other():
    from src.ship_catalog import find_ship_class
    from src.models import Ship
    d = find_ship_class(BASTION).to_ship_dict(name="b", player=1)
    d.update(id="b", x=0.0, y=0.0, heading=0.0)
    s = Ship.from_dict(d)
    assert s.ordnance_loaded_torps and s.ordnance_loaded_craft
    s.mark_launched("craft")
    assert not s.ordnance_loaded_torps and not s.ordnance_loaded_craft
    plain = make_ship()
    plain.mark_launched("craft")
    assert plain.ordnance_loaded_torps and not plain.ordnance_loaded_craft


def test_demiurg_immune_to_dust_clouds_and_higher_vp_against_orks():
    from src.terrain_effects import resolve_gas_dust_contact
    from src.victory_points import calculate_victory_points
    from tests.conftest import DiceStub
    d = make_ship(id="d", player=1, shields_max=0, special_rules=["demiurg_commerce"])
    dice = DiceStub([])
    assert resolve_gas_dust_contact(d, dice, make_gs([d])) == {"speed_penalty": 0, "damage": 0}
    dead = make_ship(id="c", player=1, ship_class="Citadel Commerce Vessel", points_value=185,
                     hits_remaining=0, status="destroyed",
                     special_rules=["demiurg_commerce", "demiurg_vp:200"])
    tau = make_ship(id="t", player=1)
    ork = make_ship(id="k", player=2, faction="orks")
    imp = make_ship(id="i", player=2)
    assert calculate_victory_points(make_gs([dead, tau, ork]))[2]["destroyed"] == 200
    assert calculate_victory_points(make_gs([dead, tau, imp]))[2]["destroyed"] == 185
    assert calculate_victory_points(make_gs([dead, imp]))[2]["destroyed"] == 200   # all Demiurg


def test_demiurg_hired_reserves():
    from src.fleet_lists import LISTS
    assert "demiurg_hired" in LISTS["navy_gothic"]["reserves"]
    assert "demiurg_hired" not in LISTS["navy_bakka"]["reserves"]
    assert "demiurg_hired" not in LISTS["orks_green_tide"]["reserves"]
    own = rows(*["Gothic Cruiser"] * 3, list_key="navy_gothic")
    hired = rows(CITADEL, list_key="reserve:demiurg_hired")
    assert not has(fleet_list_errors("navy_gothic", own + hired, 800), "Reserves")
    hired += rows(BASTION, list_key="reserve:demiurg_hired")
    assert has(fleet_list_errors("navy_gothic", own + hired, 1100), "Reserves")
