"""More secondary commanders (To do 4): Grey Knights Grand Master and Elite
Daemonhunters (Banisher Fleet), Elite Captains (Inquisitorial Fleet
Detachment), Rogue Trader Bond-Captains (Fleet Detachment)."""
from src.ship_catalog import find_ship_class
from src.booklet_options import (fleet_option_errors, GK_GRAND_MASTER, GK_BROTHER_CAPTAIN,
                                 INQ_ELITE_DH, INQ_ELITE_CAPTAIN)
from src.fleet_lists import option_allowed


def test_inquisition_commanders():
    gk = find_ship_class("Grey Knights Strike Cruiser")
    d = gk.to_ship_dict("G", 1, upgrades=[GK_GRAND_MASTER, "Inquisitor Lord: 2 extra re-rolls"])
    assert d["leadership"] == 10 and d["rerolls_remaining"] == 3
    d = gk.to_ship_dict("G", 1, upgrades=[GK_BROTHER_CAPTAIN])
    assert d["leadership"] == 9 and d["own_rerolls"] == 1
    ic = find_ship_class("Inquisitorial Cruiser")
    d = ic.to_ship_dict("I", 1, upgrades=[INQ_ELITE_CAPTAIN, "Elite Captain: re-roll"])
    assert "ld_bonus:1:9" in d["special_rules"] and d["own_rerolls"] == 1
    # 0-3 Elite Daemonhunters of either kind
    rows = [(gk, [GK_BROTHER_CAPTAIN])] * 2 + [(ic, [INQ_ELITE_DH])] * 2
    assert fleet_option_errors(rows)
    assert not fleet_option_errors(rows[:3])
    # list gating: Daemonhunters in the Banisher fleet, Elite Captains in the detachment
    assert option_allowed(INQ_ELITE_DH, ["inq_banisher"])
    assert not option_allowed(INQ_ELITE_DH, ["inq_detachment"])
    assert option_allowed(INQ_ELITE_CAPTAIN, ["navy_gothic", "inq_detachment"])
    assert not option_allowed(INQ_ELITE_CAPTAIN, ["inq_banisher"])


def test_bond_captains_in_the_rogue_trader_detachment():
    e = next(x for x in [find_ship_class("Rogue Trader Escort Carrier")] if x)
    names = [u.name for u in e.upgrades_available]
    assert "Bond-Captain (+1 Ld, max 8)" in names or not any(
        "Lord Captain" in n for n in names)         # escorts carry no commanders
    assert option_allowed("Bond-Captain (+1 Ld, max 8)", ["navy_gothic", "rt_detachment"])
    assert not option_allowed("Bond-Captain (+1 Ld, max 8)", ["rt_expedition"])
