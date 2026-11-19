"""Tyranids, slice 2a (CLAUDE.md To do 19): spore cysts and the spore cloud,
bio-plasma, bonded exo-plating, pyro-acid fires, the crit table (Proteus
thorax and spore cysts), boarding, raids and navigation."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.models import BlastMarker
from src.combat import resolve_lances, apply_damage, roll_critical_hit
from src.geometry import current_shields
from src.ordnance import turret_dice, turrets_blocked
from src.boarding import troop_rating
from src.hit_and_run import _raid_roll_modifier as raid_modifier
from src.tables import crit_table_for, TYRANID_CRITICAL_HITS

TYR = ["tyranid", "spore_cloud"]


def _tyr(**kw):
    base = dict(id="ty", player=2, x=0.0, y=40.0, heading=180.0, hits_max=6, turrets=2,
                shields_max=2, special_rules=list(TYR))
    base.update(kw)
    return make_ship(**base)


def test_spore_cloud_shields_follow_the_cysts():
    t = _tyr()
    assert current_shields(t, []) == 2
    t.hits_remaining = 3                                  # crippled: cysts halved
    assert t.effective_turrets == 1 and current_shields(t, []) == 1
    t.special_rules.append("spore_overdrive")
    assert t.effective_turrets == 2
    t.critical_damage = [{"crit_type": "spores_injured"}]
    assert t.effective_turrets == 0 and current_shields(t, []) == 0


def test_bio_plasma_ignores_shields_and_needs_six_beyond_15cm():
    gun = _tyr(id="g", player=1, x=0.0, y=0.0)
    far = make_ship(id="f", player=2, x=0.0, y=25.0, shields_max=2)
    w = {"name": "Spines", "weapon_type": "lance", "strength": 3, "range_cm": 30,
         "bio_plasma": True, "arcs": ["front"]}
    sr = resolve_lances(gun, far, w, DiceStub([5, 6, 4]))
    assert sr.hits == 1 and sr.bypass_hits == 1
    near = make_ship(id="n", player=2, x=0.0, y=10.0)
    assert resolve_lances(gun, near, w, DiceStub([5, 6, 4])).hits == 3


def test_bonded_exo_plating_saves_on_four_and_ignores_brace():
    k = make_ship(id="k", player=2, hits_max=2, special_rules=["tyranid", "bonded_exo_plating"],
                  turrets=0, shields_max=0)
    gs = make_gs([k])
    dice = DiceStub([4, 2, 1])                  # one saved, one through, crit check
    apply_damage(gs.get_ship_by_id("k"), 2, dice, gs, target_braced=True)
    assert dice._idx == 3 and gs.get_ship_by_id("k").hits_remaining == 1


def test_pyro_acid_crit_adds_a_fire():
    gun = _tyr(id="g", player=1, x=0.0, y=0.0,
               weapons=[{"name": "Pyro", "weapon_type": "battery", "strength": 4,
                         "range_cm": 30, "arcs": ["front"], "pyro_acid": True}])
    tgt = make_ship(id="t", player=2, x=0.0, y=20.0, hits_max=8, shields_max=0)
    gs = make_gs([gun, tgt])
    rolls = [6,           # crit check
             7]           # 2D6 = 7: Fire!
    dice = DiceStub(rolls)
    apply_damage(gs.get_ship_by_id("t"), 1, dice, gs, attacker_key="g", gunnery=True)
    t = gs.get_ship_by_id("t")
    assert dice._idx == len(rolls)
    assert [c["crit_type"] for c in t.critical_damage] == ["fire", "fire"]


def test_crit_table_proteus_thorax_and_cysts():
    p = _tyr(special_rules=TYR + ["extremely_ponderous"], turrets=5, hits_max=20,
             weapons=[{"name": "Keel Pyro-Acid Battery", "weapon_type": "battery",
                       "strength": 12, "range_cm": 45, "arcs": ["left", "front", "right"]},
                      {"name": "Dorsal Pyro-Acid Battery", "weapon_type": "battery",
                       "strength": 12, "range_cm": 45, "arcs": ["left", "front", "right"]}])
    assert crit_table_for(p) is TYRANID_CRITICAL_HITS
    gs = make_gs([p])
    s = gs.get_ship_by_id("ty")
    roll_critical_hit(s, DiceStub([6, 2]), gs)           # 6: thorax, D6 2: keel
    assert s.critical_damage[-1]["crit_type"] == "keel_armament"
    roll_critical_hit(s, DiceStub([2]), gs)              # 2: spore cysts injured, -1 only
    assert s.effective_turrets == 4


def test_spore_cysts_fire_at_everything_and_blast_markers_need_sixes():
    t = _tyr(turrets_used_vs="craft")
    assert not turrets_blocked(t, "torp")
    gs = make_gs([t])
    gs.add_blast_marker(BlastMarker(id="b", x=t.x + 1.0, y=t.y))
    rolls = turret_dice(DiceStub([5, 5]), gs.get_ship_by_id("ty"), 2, 4, "x", gs)
    assert sorted(rolls) == [1, 5]


def test_boarding_raids_and_navigation():
    t = _tyr()
    assert troop_rating(t) == 12
    other = make_ship(id="o", player=1)
    assert raid_modifier(["tyranid"], other) == 1
    assert raid_modifier([], t) == -1
