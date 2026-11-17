"""Owner: with the hit-and-run toggle off, assault boats, boarding torpedoes and
teleport attacks are disabled for the players too (they are all raids, s.31)."""
from tests.conftest import make_ship, make_gs
from src.ordnance import craft_type_allowed, launch_torpedoes, torpedo_kind_options
from src.hit_and_run import check_teleport_eligibility

BAY = {"name": "Launch Bays", "weapon_type": "launch_bay", "strength": 2,
       "craft_types": ["fury_fighter", "shark_assault_boat", "thunderhawk"]}
TUBES = {"name": "Prow Torpedoes", "weapon_type": "torpedo", "strength": 6, "range_cm": 30,
         "arcs": ["front"], "boarding_torpedoes": True, "torpedo_speed": 30}


def test_assault_boats_off_multi_role_still_launch():
    gs = make_gs([])
    assert not craft_type_allowed("shark_assault_boat", [BAY], gs)
    assert craft_type_allowed("fury_fighter", [BAY], gs)
    assert craft_type_allowed("thunderhawk", [BAY], gs)      # fighter / bomber still
    gs.rule_hit_and_run = True
    assert craft_type_allowed("shark_assault_boat", [BAY], gs)


def test_no_boarding_torpedoes_when_raids_are_off():
    ship = make_ship(id="s", player=1, x=0.0, y=0.0, weapons=[dict(TUBES)])
    gs = make_gs([ship])
    assert [k for k, _ in torpedo_kind_options(ship, TUBES, gs.rule_hit_and_run)] == ["standard"]
    m = launch_torpedoes(ship, TUBES, gs, boarding=True)
    assert m.ordnance_type == "torpedo_standard"
    gs.rule_hit_and_run = True
    assert launch_torpedoes(ship, TUBES, gs, boarding=True).ordnance_type == "torpedo_boarding"


def test_no_teleports_when_raids_are_off():
    a = make_ship(id="a", player=1, x=0.0, y=0.0, hits_max=8)
    t = make_ship(id="t", player=2, x=5.0, y=0.0, hits_max=6, shields_max=0)
    gs = make_gs([a, t])
    gs.rule_teleport = True
    ok, why = check_teleport_eligibility(a, t, gs)
    assert not ok and "hit-and-run" in why
    gs.rule_hit_and_run = True
    assert check_teleport_eligibility(a, t, gs)[0]
