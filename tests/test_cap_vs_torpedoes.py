"""Owner: a CAP fighter removes a whole torpedo salvo but only one squadron
of a wave, so craft go in first ahead of a big salvo, and a small salvo can
draw the CAP off a wave (s.19, s.26)."""
from tests.conftest import make_gunship, make_ship, make_gs, make_marker, DiceStub
from src.ai_player import AIPlayer
from src.turn_controller import TurnController
from src.fleet_loader import load_fleet_file, fleet_to_ships


def _setup(cap=1):
    gothic = fleet_to_ships(load_fleet_file("data/fleets/owner_gothic_1000.json"), 2)
    lunar = next(s for s in gothic if "Lunar" in s.ship_class)
    lunar.x, lunar.y, lunar.leadership = 50.0, 50.0, 8
    me = make_ship(id="me", player=1, x=50.0, y=20.0, heading=90.0)
    # our guns within reach of the Lunar: hull hits short of a kill are worth
    # the chance they are finished later (ai_hazards.hits_vp)
    gs = make_gs([me, lunar, make_gunship(player=1, x=20.0, y=50.0)])
    for i in range(cap):
        gs.add_ordnance(make_marker(id=f"cap{i}", ordnance_type="fighter", owner_player=2,
                                    x=50.0, y=50.0, cap_ship_id=lunar.id, strength=1))
    return gs, gs.get_ship_by_id(lunar.id)


def test_salvo_into_cap_is_worth_nothing_until_craft_strip_it():
    gs, lunar = _setup(cap=1)
    ai = AIPlayer(1, TurnController(gs, DiceStub([])), gs, DiceStub([]))
    assert ai._torp_cap_factor(lunar, 0) == 0.0
    ai._ord_arrivals = {lunar.id: {"craft": [(0, 0, 1, 0, 0)]}}
    assert ai._torp_cap_factor(lunar, 0) == 1.0            # one bomber spends the CAP
    gs2, lunar2 = _setup(cap=0)
    ai2 = AIPlayer(1, TurnController(gs2, DiceStub([])), gs2, DiceStub([]))
    assert ai2._torp_cap_factor(lunar2, 0) == 1.0          # no CAP at all


def test_contact_order_big_salvo_craft_first_small_salvo_torpedoes_first():
    from src.formations import contact_order_values
    gs, lunar = _setup(cap=1)
    imp = [make_marker(id=f"i{i}", ordnance_type="assault_boat", owner_player=1,
                       x=50.0, y=48.0, strength=1, special_rules=["dark_eldar", "impaler"],
                       resilient_save=4) for i in range(2)]
    big = make_marker(id="t6", owner_player=1, x=50.0, y=47.0, strength=6)
    small = make_marker(id="t1", owner_player=1, x=50.0, y=47.0, strength=1)
    v_big = contact_order_values(lunar, [imp], [big], gs)
    assert v_big["craft"] > v_big["torpedoes"]            # let the wave soak the CAP
    v_small = contact_order_values(lunar, [imp], [small], gs)
    assert v_small["torpedoes"] > v_small["craft"]        # the salvo draws the CAP off
