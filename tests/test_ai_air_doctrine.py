"""Owner: carrier doctrine. With more launch capacity than the enemy, the AI
should prioritise taking down the enemy's carriers (air supremacy); with less,
it should protect its carriers and fly more interception."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.ship_catalog import find_ship_class
from src.models import Ship
from src.ai_hazards import bay_threat_vp, added_vp, air_balance

GUNS = [{"name": "Port Battery", "weapon_type": "battery", "range_cm": 30, "strength": 6,
         "arcs": ["left"]},
        {"name": "Starboard Battery", "weapon_type": "battery", "range_cm": 30, "strength": 6,
         "arcs": ["right"]}]


def _carrier(sid, player, x, y=0.0, heading=0.0):
    d = find_ship_class("Dictator Class Cruiser").to_ship_dict(sid, player, ship_id=sid)
    d.update(x=x, y=y, heading=heading, leadership=8)
    return Ship.from_dict(d)


def _gun_cruiser(sid, player, x, y=0.0, pts=None):
    return make_ship(id=sid, player=player, x=x, y=y, heading=180.0, weapons=[dict(w) for w in GUNS],
                     points_value=pts or 220, hits_max=8, armor_prow="5+", armor_side="5+")


def test_enemy_carrier_worth_more_to_kill_the_more_we_launch():
    """Its fighters deny our strikes (one squadron each, up to our capacity), so
    killing it is worth more to a carrier-heavy fleet."""
    enemy_cv = _carrier("ecv", 2, 40.0, heading=180.0)
    gun_only = [_gun_cruiser("g1", 1, 0.0)]
    carriers = [_carrier(f"c{i}", 1, 0.0, 10.0 * i) for i in range(2)]   # 8 squadrons
    gs_guns = make_gs(gun_only + [enemy_cv])
    gs_cv = make_gs(carriers + [enemy_cv])
    assert air_balance(gs_cv, 1) == (8, 4)
    assert bay_threat_vp(enemy_cv, gs_cv) > bay_threat_vp(enemy_cv, gs_guns) > 0
    assert bay_threat_vp(_gun_cruiser("x", 2, 40.0), gs_cv) == 0.0


def test_air_supremacy_puts_guns_on_the_enemy_carrier():
    """Two enemies of equal points and toughness, one a carrier: our carrier-heavy
    fleet values hits on the carrier more (damage_vp counts the threat removed)."""
    enemy_cv = _carrier("ecv", 2, 40.0, heading=180.0)
    twin = _gun_cruiser("eg", 2, 40.0, 20.0, pts=enemy_cv.points_value)
    twin = Ship.from_dict({**twin.to_dict(), "hits_max": enemy_cv.hits_max,
                           "hits_remaining": enemy_cv.hits_remaining,
                           "shields_max": enemy_cv.shields_max,
                           "armor_prow": enemy_cv.armor_prow, "armor_side": enemy_cv.armor_side,
                           "armor_rear": enemy_cv.armor_rear, "weapons": []})
    gs = make_gs([_carrier("c0", 1, 0.0), _carrier("c1", 1, 0.0, 10.0), enemy_cv, twin])
    hits = enemy_cv.hits_max          # enough to kill either
    assert added_vp(enemy_cv, gs, 0.0, hits) > added_vp(twin, gs, 0.0, hits)


def test_out_carriered_the_ai_protects_its_carrier_and_flies_more_cap():
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    mine = _carrier("c0", 1, 0.0)
    rivals = [_carrier(f"e{i}", 2, 45.0, 15.0 * i, heading=180.0) for i in range(3)]
    gs_weak = make_gs([mine] + rivals)             # 4 vs 12 squadrons
    gs_even = make_gs([mine, rivals[0]])           # 4 vs 4
    tgt = rivals[0]

    def ai_for(gs):
        dice = DiceStub([])
        a = AIPlayer(1, TurnController(gs, dice), gs, dice)
        a.difficulty = "normal"
        return a
    weak, even = ai_for(gs_weak), ai_for(gs_even)
    assert weak._anticipated_weight() > even._anticipated_weight()
    inside = weak._carrier_exposure(mine, 10.0, 0.0, tgt)
    outside = weak._carrier_exposure(mine, -80.0, 0.0, tgt)
    assert inside > even._carrier_exposure(mine, 10.0, 0.0, tgt) > 0 and outside == 0.0
    # gun ships carry no carrier-protection term
    assert weak._carrier_exposure(_gun_cruiser("g", 1, 0.0), 10.0, 0.0, tgt) == 0.0
