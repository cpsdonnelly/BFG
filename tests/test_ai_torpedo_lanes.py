"""AI torpedo launch lanes (To do 1): the AI aims down the clearest lane that
still meets its target and never fires through its own ships (standard
torpedoes attack the first ship they contact, friend or foe, s.15)."""
import math

from tests.conftest import make_ship, make_gs, DiceStub
from src.models import Ship, BlastMarker
from src.ship_catalog import find_ship_class
from src.ai_player import AIPlayer
from src.turn_controller import TurnController


def _setup(friend_at=None, blast_at=None, friend=None, enemy=None):
    d = find_ship_class("Dictator Class Cruiser").to_ship_dict("D", 1, ship_id="d")
    d.update(x=0.0, y=0.0, heading=0.0, leadership=8, ordnance_loaded_craft=False)
    ships = [Ship.from_dict(d),
             make_ship(**{"id": "e", "player": 2, "x": 40.0, "y": 0.0, "heading": 180.0,
                          "speed": 0, "points_value": 150, **(enemy or {})})]
    if friend_at:
        ships.append(make_ship(**{"id": "f", "player": 1, "x": friend_at[0],
                                  "y": friend_at[1], "heading": 0.0, "points_value": 100,
                                  **(friend or {})}))
    gs = make_gs(ships)
    gs.current_phase = "ordnance"
    if blast_at:
        gs.add_blast_marker(BlastMarker(id="bm", x=blast_at[0], y=blast_at[1]))
    dice = DiceStub([])
    ai = AIPlayer(1, TurnController(gs, dice), gs, dice)
    ai.difficulty = "normal"
    return gs, ai, dice


def _torps(gs):
    return [o for o in gs.ordnance if o["owner_player"] == 1 and "torpedo" in o["ordnance_type"]]


def test_no_torpedoes_through_a_friendly_ship():
    gs, ai, dice = _setup(friend_at=(20.0, 0.0))
    ai.run_ordnance_phase()
    assert dice._idx == 0
    assert _torps(gs) == []
    # Clear lane: it fires
    gs, ai, dice = _setup()
    ai.run_ordnance_phase()
    assert len(_torps(gs)) == 1


def test_friend_in_base_contact_is_passed_through():
    """s.15-16: a launcher fires 'through' a friendly ship in base contact."""
    gs, ai, dice = _setup(friend_at=(3.0, 0.0))
    ai.run_ordnance_phase()
    assert len(_torps(gs)) == 1


def test_aim_moves_off_a_blast_marker_on_the_centre_line():
    gs, ai, _dice = _setup()
    ship, tgt = gs.get_ship_by_id("d"), gs.get_ship_by_id("e")
    weapon = next(w for w in ship.weapons if w.get("weapon_type") == "torpedo")
    h_clear = ai._torpedo_aim_heading(ship, weapon, tgt)
    # 2.5cm off the centre line: the marker's edge (1.25cm) clips it head-on
    gs, ai, _dice = _setup(blast_at=(20.0, -2.5))
    ship, tgt = gs.get_ship_by_id("d"), gs.get_ship_by_id("e")
    h, value, on_target, lost = ai._torp_lane(ship, weapon, tgt, 0.0, 40.0)
    assert abs(h_clear) < 1e-6 or abs(h_clear - 360) < 1e-6
    assert value > 0 and on_target > 0 and lost == 0
    assert 0 < h < 10                               # turned a little to port of the marker
    from src.ai_hazards import ordnance_path_survival, torpedo_path_survival
    assert ordnance_path_survival(0.0, 0.0, 70.0, 0.0, gs, "torpedo") == 1.0  # centre misses
    assert torpedo_path_survival(0.0, 0.0, 70.0, 0.0, gs) < 1.0   # but the marker's edge hits
    # The heading still meets the target's base (s.15)
    from src.geometry import torpedo_first_contact
    ex, ey = 40.0 * math.cos(math.radians(h)), 40.0 * math.sin(math.radians(h))
    assert torpedo_first_contact(tgt.x, tgt.y, tgt.base_radius, 0.0, 0.0, ex, ey, h)


def test_friendly_fire_is_negative_vp():
    """Owner: damage to a friendly ship is negative VP, weighed against what
    the salvo still does to the enemy (s.15: it attacks every ship it contacts
    and carries on with its strength reduced by its hits)."""
    gs, ai, _dice = _setup(friend_at=(20.0, 0.0))
    ship, tgt = gs.get_ship_by_id("d"), gs.get_ship_by_id("e")
    weapon = next(w for w in ship.weapons if w.get("weapon_type") == "torpedo")
    clear = _setup()[1]._torp_lane(ship, weapon, tgt, 0.0, 40.0)
    h, value, on_target, lost = ai._torp_lane(ship, weapon, tgt, 0.0, 40.0)
    assert lost > 0 and on_target < clear[2]       # our ship soaks hits first
    assert value < clear[1]
    # A tough, cheap friend in the way of a nearly dead, valuable enemy: the
    # salvo is still worth firing, at the cost of the friendly damage
    gs, ai, dice = _setup(friend_at=(20.0, 0.0),
                          friend={"armor_prow": "6+", "armor_side": "6+", "armor_rear": "6+",
                                  "points_value": 30},
                          enemy={"hits_remaining": 1, "points_value": 300, "turrets": 0})
    ship, tgt = gs.get_ship_by_id("d"), gs.get_ship_by_id("e")
    h, value, on_target, lost = ai._torp_lane(ship, weapon, tgt, 0.0, 40.0)
    assert lost > 0 and value > 0
    ai.run_ordnance_phase()
    assert dice._idx == 0
    assert len(_torps(gs)) == 1


def test_move_score_counts_loaded_torpedoes_in_arc():
    """Torpedoes launch from where the ship ends its move: an end position with
    the target ahead and in torpedo reach scores the launcher; unloaded, or
    with the target abeam, it doesn't."""
    from src.ai_player import AIPlayer
    torp = {"name": "Prow Torpedoes", "weapon_type": "torpedo", "range_cm": 30,
            "strength": 6, "arcs": ["front"], "torpedo_type": "standard", "torpedo_speed": 30}
    me = make_ship(id="me", player=1, x=0.0, y=0.0, weapons=[dict(torp)])
    me.ordnance_loaded_torps = True
    tgt = make_ship(id="t", player=2, x=40.0, y=0.0)
    gs = make_gs([me, tgt])
    dice = DiceStub([])
    ai = AIPlayer(1, TurnController(gs, dice), gs, dice)
    ahead = ai._arc_score(me, 0.0, 0.0, 0.0, tgt)           # 40cm: within two moves
    abeam = ai._arc_score(me, 0.0, 0.0, 90.0, tgt)
    near = ai._arc_score(me, 15.0, 0.0, 0.0, tgt)           # 25cm: within one move
    assert (abeam, ahead, near) == (0.0, 3.0, 6.0)
    me.ordnance_loaded_torps = False
    assert ai._arc_score(me, 15.0, 0.0, 0.0, tgt) == 0.0
