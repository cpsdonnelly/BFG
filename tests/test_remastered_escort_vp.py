"""Remastered escort squadron VP (p.121), an option beside the Remastered
toggles (To do 9); XR stays the default."""
from tests.conftest import make_ship, make_gs
from src.victory_points import calculate_victory_points


def _sq(remastered, dead=2, gone=0, n=4):
    ships = []
    for i in range(n):
        st = "destroyed" if i < dead else ("disengaged" if i < dead + gone else "active")
        ships.append(make_ship(id=f"e{i}", player=1, ship_type="escort", squadron_id="sq",
                               hits_max=1, hits_remaining=0 if i < dead else 1,
                               points_value=40, status=st,
                               is_disengaged=(st == "disengaged")))
    ships.append(make_ship(id="foe", player=2, x=100.0, points_value=200))
    gs = make_gs(ships)
    gs.rule_remastered_escort_vp = remastered
    return calculate_victory_points(gs)[2]["total"] - calculate_victory_points(gs)[2].get(
        "holding_field", 0)


def test_on_the_table_half_lost():
    assert _sq(False) == 40          # XR: 25% of 160
    assert _sq(True) == 0            # Remastered: nothing unless all destroyed


def test_disengaged_and_destroyed():
    assert _sq(True, dead=2, gone=2) == 40     # crippled, then disengaged: 25%
    assert _sq(True, dead=1, gone=3) == 16     # not crippled: 10%
    assert _sq(True, dead=4) == 160 and _sq(False, dead=4) == 160


def test_ai_keeps_a_crippled_squadron_on_the_table():
    """In Remastered mode leaving concedes 25% of the squadron, staying only
    risks it if every survivor dies, so a crippled squadron under light fire
    stays: leaving is worth much less than in XR."""
    from src.ai_hazards import disengage_gain
    gun = {"name": "Guns", "weapon_type": "battery", "range_cm": 30, "strength": 4,
           "arcs": ["left", "right", "front"]}

    def gain(rem):
        ships = [make_ship(id=f"e{i}", player=1, ship_type="escort", squadron_id="sq",
                           hits_max=1, hits_remaining=0 if i < 2 else 1, points_value=40,
                           status="destroyed" if i < 2 else "active", x=0.0, y=5.0 * i)
                 for i in range(4)]
        ships.append(make_ship(id="foe", player=2, x=20.0, y=10.0, heading=90.0,
                               weapons=[gun], points_value=200))
        gs = make_gs(ships)
        gs.rule_remastered_escort_vp = rem
        return disengage_gain(gs.get_ship_by_id("e2"), gs, 8, 0.0)
    assert gain(True) < 0 and gain(True) < gain(False) - 10.0
