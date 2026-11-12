"""Strikes valued when they land (To do 2, HANDOFF "Ordnance strike planning"):
arrival phase, which turn the wave lands in (the raid's repair window), enemy
guns on the way (one 6 removes the whole wave, s.25 / s.30) and reactive CAP."""
from tests.conftest import make_ship, make_gs
from src.ai_hazards import strike_timeline

GUNS = [{"name": "Port Battery", "weapon_type": "battery", "range_cm": 30, "strength": 8,
         "arcs": ["left"]},
        {"name": "Starboard Battery", "weapon_type": "battery", "range_cm": 30, "strength": 8,
         "arcs": ["right"]}]


def test_arrival_phase_and_landing_turn():
    t = make_ship(id="t", player=2, x=25.0, y=0.0, heading=90.0, speed=0)
    gs = make_gs([t])
    now = strike_timeline(0.0, 0.0, 30.0, t, gs, 1)
    assert now["phase"] == 0 and now["end_phases"] == 1      # lands in our own phase
    far = make_ship(id="t", player=2, x=50.0, y=0.0, heading=90.0, speed=0)
    later = strike_timeline(0.0, 0.0, 30.0, far, make_gs([far]), 1)
    assert later["phase"] == 1 and later["end_phases"] == 2  # in the enemy's phase,
    #                                                          after it has fired
    assert strike_timeline(0.0, 0.0, 30.0, far, make_gs([far]), 1, max_phases=1) is None


def test_enemy_guns_on_the_way_cost_survival():
    """A wave waiting where an enemy broadside reaches it in the enemy's
    shooting phase may lose everything to one 6."""
    t = make_ship(id="t", player=2, x=50.0, y=0.0, heading=90.0, speed=0)
    gunship = make_ship(id="g", player=2, x=30.0, y=20.0, heading=0.0, speed=0,
                        weapons=[dict(w) for w in GUNS])
    safe = strike_timeline(0.0, 0.0, 30.0, t, make_gs([t]), 1)
    risky = strike_timeline(0.0, 0.0, 30.0, t, make_gs([t, gunship]), 1)
    assert safe["survival"] == 1.0 and 0.0 < risky["survival"] < 1.0


def test_reactive_cap_from_a_loaded_target_carrier():
    bay = {"name": "Launch Bays", "weapon_type": "launch_bay", "range_cm": 30, "strength": 2,
           "arcs": [], "craft_types": ["fury_fighter", "starhawk_bomber"],
           "craft_speeds": {"fury_fighter": 30, "starhawk_bomber": 20}}
    t = make_ship(id="t", player=2, x=50.0, y=0.0, heading=90.0, speed=0, weapons=[bay])
    assert strike_timeline(0.0, 0.0, 30.0, t, make_gs([t]), 1)["reactive_cap"] == 2
    t.ordnance_loaded_craft = False
    assert strike_timeline(0.0, 0.0, 30.0, t, make_gs([t]), 1)["reactive_cap"] == 0
    # landing in our own phase, before the enemy has an ordnance phase: no reaction
    near = make_ship(id="t", player=2, x=25.0, y=0.0, heading=90.0, speed=0, weapons=[bay])
    assert strike_timeline(0.0, 0.0, 30.0, near, make_gs([near]), 1)["reactive_cap"] == 0
