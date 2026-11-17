"""s.40: Fighting Sunward, Solar Flares, Radiation Bursts (To do 6)."""
from tests.conftest import make_ship, make_gs, DiceStub
from src import celestial
from src.optional_rules import set_sunward
from src.combat import get_column_shifts


def test_fighting_sunward_doubles_the_range_shifts():
    a = make_ship(id="a", player=1, x=50.0, y=10.0)
    north = make_ship(id="n", player=2, x=50.0, y=50.0)      # 40cm towards the north edge
    south_gs = make_ship(id="s", player=2, x=50.0, y=-30.0)
    assert celestial.is_sunward(a, north, "north") and not celestial.is_sunward(a, south_gs, "north")
    try:
        set_sunward(True, "north")
        assert get_column_shifts(a, north, []) == 2
        assert get_column_shifts(a, south_gs, []) == 1
        close = make_ship(id="c", player=2, x=50.0, y=20.0)
        assert get_column_shifts(a, close, []) == -2
        set_sunward(False)
        assert get_column_shifts(a, north, []) == 1
    finally:
        set_sunward(False)


def test_solar_flare_once_per_game():
    lit = make_ship(id="l", player=1, shields_max=0, hits_max=8, hits_remaining=8)
    sh = make_ship(id="s", player=2, x=40.0, shields_max=2, hits_max=8, hits_remaining=8)
    gs = make_gs([lit, sh])
    gs.rule_solar_flares = True
    from src.models import OrdnanceMarker
    gs.add_ordnance(OrdnanceMarker(id="o", ordnance_type="torpedo_standard", owner_player=1,
                                   launched_by="l", x=10.0, y=10.0))
    # flare roll 6; the unshielded ship takes a hit and rolls for a crit (3: none);
    # the ordnance roll 5 removes the marker
    dice = DiceStub([6, 3, 5])
    celestial.start_of_turn(gs, dice)
    assert dice._idx == 3
    assert gs.get_ship_by_id("l").hits_remaining == 7
    assert gs.get_ship_by_id("s").hits_remaining == 8 and len(gs.blast_markers) == 2
    assert not gs.ordnance and gs.solar_flare_done
    dice2 = DiceStub([])
    celestial.start_of_turn(gs, dice2)          # once per game: no more rolls
    assert dice2._idx == 0


def test_radiation_burst_cuts_ld_for_the_turn_and_limits_rerolls():
    from src.turn_controller import TurnController
    from src.disengage import get_disengage_ld_modifiers
    flag = make_ship(id="f", player=1, leadership=9, is_flagship=True, rerolls_remaining=2)
    other = make_ship(id="o", player=1, x=60.0, leadership=8)
    gs = make_gs([flag, other])
    gs.rule_radiation_bursts = True
    tc = TurnController(gs, DiceStub([]))
    dice = DiceStub([5, 3])
    celestial.start_of_turn(gs, dice)
    assert gs.get_ship_by_id("o").leadership == 5 and celestial.radiation_active(gs)
    assert tc.get_fleet_rerolls(1, gs.get_ship_by_id("o")) == 0
    assert tc.get_fleet_rerolls(1, gs.get_ship_by_id("f")) == 2
    mods = get_disengage_ld_modifiers(gs.get_ship_by_id("o"), gs)
    assert any("radiation" in m for m in mods["modifiers"])
    celestial.end_of_turn(gs, gs.active_player)
    assert gs.get_ship_by_id("o").leadership == 8
