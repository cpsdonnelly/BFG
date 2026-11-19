"""Dark Eldar, slice 3 (CLAUDE.md To do 19): slave-taking, Insatiable Greed,
Impalers, Pain Frenzy; and the spectator mode's per-player AI difficulty."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.models import OrdnanceMarker, OrdnanceType
from src.dark_eldar import take_slaves, resolve_impaler, boarding_slave_vp
from src.victory_points import calculate_victory_points
from src.hit_and_run import _raid_roll_modifier

DE = ["dark_eldar", "shadowfield"]


def test_slave_taking_raid_scores_five_unless_braced_save():
    gs = make_gs([make_ship(id="t", player=1)])
    gs.slave_hook = lambda p, t, what: True
    t = gs.get_ship_by_id("t")
    assert take_slaves(gs, DE, t, False, DiceStub([]), 5)
    assert gs.slave_vp == {"2": 5}
    dice = DiceStub([4])                      # braced: saved, no VP
    assert take_slaves(gs, DE, t, True, dice, 5) and dice._idx == 1
    assert gs.slave_vp == {"2": 5}
    assert calculate_victory_points(gs)[2]["total"] >= 5
    assert not take_slaves(gs, ["chaos"], t, False, DiceStub([]), 5)


def test_boarding_slaves_per_hit_and_bridge_smashed():
    gs = make_gs([])
    de, t = make_ship(id="d", player=2, special_rules=DE), make_ship(id="t", player=1)
    boarding_slave_vp(gs, [de], t, {"winner": "attacker", "damage": 3,
                                    "defender_crits": [{"crit_type": "bridge_smashed"}]})
    assert gs.slave_vp == {"2": 115}


def test_impaler_slaves_roll_d6_x5():
    t = make_ship(id="t", player=1, x=0.0, y=0.0)
    gs = make_gs([t])
    gs.slave_hook = lambda p, tg, what: True
    m = OrdnanceMarker(id="i", ordnance_type=OrdnanceType.ASSAULT_BOAT.value, owner_player=2,
                       launched_by="d", x=0.0, y=3.0, special_rules=["dark_eldar", "impaler"])
    out = resolve_impaler(m, gs.get_ship_by_id("t"), False, DiceStub([4]), gs)
    assert out.get("slaves") and gs.slave_vp == {"2": 20}


def test_impaler_damage_and_crit():
    t = make_ship(id="t", player=1, x=0.0, y=0.0, hits_max=8, armor_prow="5+",
                  armor_side="5+", armor_rear="5+")
    gs = make_gs([t])
    gs.slave_hook = lambda p, tg, what: False
    m = OrdnanceMarker(id="i", ordnance_type=OrdnanceType.ASSAULT_BOAT.value, owner_player=2,
                       launched_by="d", x=0.0, y=3.0, special_rules=["dark_eldar", "impaler"])
    rolls = [5,          # Impaler D6: >= 5+ Armour, 1 damage
             3, 3,       # the damage's crit check (no crit on 3)
             4, 3]       # the critical hit: 2D6 = 7
    dice = DiceStub(rolls)
    out = resolve_impaler(m, gs.get_ship_by_id("t"), False, dice, gs)
    fresh = gs.get_ship_by_id("t")
    assert out["damage"] == 1 and fresh.hits_remaining <= 7 and fresh.critical_damage


def test_pain_frenzy_and_incubi_raid_modifiers():
    assert _raid_roll_modifier(["dark_eldar"], make_ship()) == 1
    assert _raid_roll_modifier([], make_ship(special_rules=["incubi"])) == -1


def test_insatiable_greed_counts_disengaged_as_destroyed():
    de = make_ship(id="d", player=2, special_rules=list(DE), points_value=100, status="disengaged",
                   is_disengaged=True)
    foe = make_ship(id="f", player=1, points_value=100)
    vp = calculate_victory_points(make_gs([de, foe]))
    assert vp[1]["destroyed"] == 100 and vp[1]["disengaged"] == 0


def test_spectator_difficulty_per_player():
    gs = make_gs([])
    gs.ai_spectator, gs.ai_difficulty, gs.ai_difficulty_p1 = True, "normal", "easy"
    assert gs.difficulty_for(1) == "easy" and gs.difficulty_for(2) == "normal"
    gs.ai_spectator = False
    assert gs.difficulty_for(1) == "normal"
