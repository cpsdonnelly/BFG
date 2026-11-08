"""Adeptus Mechanicus (bfgxr/rules/02_adeptus-mechanicus.md; CHANGES update 19)."""
from tests.conftest import make_gs, make_ship, DiceStub
from tests.test_fleet_lists import rows
from src.ship_catalog import find_ship_class
from src.booklet_options import ship_option_errors
from src.fleet_lists import fleet_list_errors

LUNAR = "Mechanicus Lunar Cruiser"


def build(upgrades):
    return find_ship_class(LUNAR).to_ship_dict(name="m", player=1, upgrades=upgrades)


def test_one_gift_per_capital_ship_and_none_for_escorts():
    e = find_ship_class(LUNAR)
    assert ship_option_errors(e, ["Gift: Advanced Engines", "Gift: Advanced Weapons"])
    assert not [u for u in find_ship_class("Mechanicus Sword Frigate").upgrades_available
                if u.name.startswith("Gift:")]


def test_gift_effects():
    base = build([])
    eng = build(["Gift: Advanced Engines"])
    assert eng["speed"] == base["speed"] + 5 and eng["points_value"] == base["points_value"] + 5
    w = build(["Gift: Advanced Weapons"])
    dorsal = lambda d: next(x["strength"] for x in d["weapons"] if x["name"].startswith("Dorsal Lance"))
    assert dorsal(w) == dorsal(base) + 1 and "targeting_matrix" in w["special_rules"]
    from src.movement import aaf_bonus_dice
    from src.models import Ship
    d = dict(eng, id="m", x=0.0, y=0.0, heading=0.0)
    assert aaf_bonus_dice(Ship.from_dict(d)) == 6


def test_emergency_energy_reserves_lose_a_quarter_when_crippled():
    s = make_ship(shields_max=2, turrets=3, speed=20, hits_max=8, hits_remaining=4,
                  special_rules=["emergency_energy_reserves"])
    assert s.effective_shields == 2 and s.effective_turrets == 3 and s.effective_speed == 15
    assert s.crippled_value(8) == 6
    plain = make_ship(shields_max=2, turrets=3, speed=20, hits_max=8, hits_remaining=4)
    assert plain.effective_shields == 1 and plain.effective_turrets == 2


def test_overloaded_shield_capacitors_discard_hits_on_6s():
    from src.combat import apply_damage
    t = make_ship(id="t", shields_max=2, hits_max=8, hits_remaining=8,
                  special_rules=["overloaded_shields"])
    gs = make_gs([t])
    dice = DiceStub([6, 3])                 # one 6: one of the 3 hits is discarded
    out = apply_damage(t, 3, dice, gs)
    assert dice._idx == 2 and out["capacitor_discards"] == 1 and out["shield_hits"] == 2
    assert out["hull_hits"] == 0


def test_advanced_shields_shift_right_while_shields_are_up():
    from src.combat import get_column_shifts
    a = make_ship(id="a", player=1, x=0.0, y=0.0)
    t = make_ship(id="t", player=2, x=20.0, y=0.0, shields_max=1, special_rules=["advanced_shields"])
    plain = make_ship(id="p", player=2, x=20.0, y=0.0, shields_max=1)
    assert get_column_shifts(a, t, []) == get_column_shifts(a, plain, []) + 1


def test_vault_of_technology_rolls_a_free_gift():
    from src.mechanicus import roll_vault_of_technology
    d = build(["Gift: Vault of Technology"])
    d.update(id="m", x=0.0, y=0.0, heading=0.0)
    from src.models import Ship
    gs = make_gs([Ship.from_dict(d)])
    dice = DiceStub([3])
    logs = roll_vault_of_technology(gs, dice)
    assert dice._idx == 1 and "Advanced Engines" in logs[0]
    assert "secondary_reactors" in gs.ships[0]["special_rules"]
    assert "vault_of_technology" not in gs.ships[0]["special_rules"]
    gs2 = make_gs([Ship.from_dict(d)])
    dice = DiceStub([6])
    roll_vault_of_technology(gs2, dice, choose_fn=lambda s: 1)
    assert dice._idx == 1 and "emergency_energy_reserves" in gs2.ships[0]["special_rules"]


def test_omnissiahs_victory_needs_1000_points():
    ov = "Ark Mechanicus Omnissiah's Victory (unique)"
    r = rows(ov, LUNAR, LUNAR, LUNAR, list_key="admech_explorator")
    assert any("Omnissiah" in e for e in fleet_list_errors("admech_explorator", r, 999))
    assert not any("Omnissiah" in e and "points" in e
                   for e in fleet_list_errors("admech_explorator", r, 1100))
