"""Mark of Chaos Undivided and Stormbird gunships (07_chaos.md, To do 4)."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.ship_catalog import find_ship_class
from src.booklet_options import ship_option_errors, STORMBIRDS, CSM_CREW
from src import chaos_undivided as cu


def test_undivided_lends_the_marked_ship_leadership_for_the_turn():
    lord = make_ship(id="l", player=1, leadership=9, special_rules=["mark:undivided"])
    low = make_ship(id="a", player=1, leadership=6)
    high = make_ship(id="b", player=1, leadership=10)
    gs = make_gs([lord, low, high])
    assert cu.can_use(gs, 1)
    assert cu.activate(gs, 1) == 9
    assert gs.get_ship_by_id("a").leadership == 9 and gs.get_ship_by_id("b").leadership == 10
    assert not cu.can_use(gs, 1)                     # once per game
    # a Bridge Smashed meanwhile is kept when the boost ends
    a = gs.get_ship_by_id("a")
    a.leadership -= 3
    gs.update_ship(a)
    cu.end_turn(gs, 1)
    assert gs.get_ship_by_id("a").leadership == 3


def test_command_check_offers_it():
    from src.movement import do_command_check
    lord = make_ship(id="l", player=1, leadership=9, special_rules=["mark:undivided"])
    low = make_ship(id="a", player=1, leadership=6)
    gs = make_gs([lord, low])
    asked = []
    gs.undivided_hook = lambda ship, lead, label: asked.append(label) or True
    dice = DiceStub([9])
    res = do_command_check(gs.get_ship_by_id("a"), "lock_on", dice, gs=gs)
    assert asked == ["lock_on"] and res["needed"] == 9 and res["passed"]
    assert dice._idx == 1


def test_options():
    names = [u.name for u in find_ship_class("Devastation Cruiser").upgrades_available]
    assert "Mark of Chaos Undivided" in names and STORMBIRDS in names
    dev = find_ship_class("Devastation Cruiser")
    assert ship_option_errors(dev, ["Mark of Chaos Undivided"])        # needs a Lord
    assert not ship_option_errors(dev, ["Chaos Lord (Ld 8)", "Mark of Chaos Undivided"])
    assert ship_option_errors(dev, [STORMBIRDS])                        # needs a CSM crew
    d = dev.to_ship_dict("D", 1, upgrades=[CSM_CREW, STORMBIRDS])
    bays = [w for w in d["weapons"] if w["weapon_type"] == "launch_bay"]
    assert [w["strength"] for w in bays] == [1, 1]
    assert all(w["craft_types"] == ["stormbird"] for w in bays)
    # not with torpedo bombers
    assert ship_option_errors(dev, [CSM_CREW, STORMBIRDS, "Attack craft: torpedo bombers"])
