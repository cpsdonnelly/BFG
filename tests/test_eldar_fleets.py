"""Eldar fleet building (MMS v2.0, 09_eldar.md): the Corsair and Craftworld
fleet lists, their commanders and upgrades, and the effects in play
(Gryphon Knights, Aspect Warriors, the +1 boarding bodyguards)."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.ship_catalog import get_ship_class
from src.fleet_lists import fleet_list_errors
from src.boarding import _crew_damage_bonus
from src.hit_and_run import _raid_roll_modifier
from src.turn_controller import TurnController


def _e(name):
    return get_ship_class("eldar", name)


def _row(name, ups=(), key="eldar_corsair"):
    return {"entry": _e(name), "upgrades": list(ups), "list": key}


def test_the_owners_corsair_fleet_is_valid():
    rows = ([_row("Eclipse Class Cruiser", ["Shadow Prince (Ld 9)"])]
            + [_row("Hemlock Class Destroyer")] * 4 + [_row("Nightshade Class Destroyer")] * 5
            + [_row("Aconite Class Frigate")] * 4)
    assert fleet_list_errors("eldar_corsair", rows, 1000) == []
    d = _e("Eclipse Class Cruiser").to_ship_dict(name="e", player=1,
                                                 upgrades=["Shadow Prince (Ld 9)"])
    assert d["leadership"] == 9 and d["rerolls_remaining"] == 1 and d["points_value"] == 310
    # over 750 points without a Lord
    assert any("fleet commander" in e for e in fleet_list_errors("eldar_corsair", rows[1:], 760))


def test_list_limits_and_list_only_options():
    assert any("Hero" in e for e in fleet_list_errors(
        "eldar_corsair", [_row("Void Dragon Class Grand Cruiser", ["Dragon Prince (Ld 10)"])], 420))
    assert fleet_list_errors("eldar_corsair", [_row("Void Dragon Class Grand Cruiser", [
        "Dragon Prince (Ld 10)", "Dragon Prince: Hero"])], 470) == []
    # a Supernova needs two cruisers
    assert any("Supernova" in e for e in fleet_list_errors(
        "eldar_corsair", [_row("Supernova Class Grand Cruiser"), _row("Eclipse Class Cruiser")], 530))
    # over 2000 points a Dragon Prince is needed
    big = [_row("Eclipse Class Cruiser", ["Shadow Prince (Ld 9)"])] + [_row("Eclipse Class Cruiser")] * 7
    assert any("Dragon Prince" in e for e in fleet_list_errors("eldar_corsair", big, 2130))
    # Craftworld options aren't Corsair ones
    errs = fleet_list_errors("eldar_corsair", [_row("Eclipse Class Cruiser", ["Admiral (Ld 9)"])], 310)
    assert any("isn't available" in e for e in errs)
    names = [u.name for u in _e("Wyrm Class Battleship").upgrades_available]
    assert "Aspect Warriors" in names
    assert "Aspect Warriors" not in [u.name for u in _e("Eclipse Class Cruiser").upgrades_available]


def test_bodyguard_aspect_warriors_and_gryphon_knights():
    assert _crew_damage_bonus(make_ship(special_rules=["eldar_bodyguard", "aspect_warriors"])) == 2
    assert _raid_roll_modifier(["aspect_warriors"], make_ship()) == 1
    a = make_ship(id="a", player=1, leadership=10)
    b = make_ship(id="b", player=1, leadership=10, special_rules=["gryphon_knight"])
    gs = make_gs([a, b])
    gs.active_player = 1
    tc = TurnController(gs, DiceStub([12]))
    tc.command_check_failed = True
    assert not tc.can_issue_special_order(gs.get_ship_by_id("a"))
    assert tc.can_issue_special_order(gs.get_ship_by_id("b"))
