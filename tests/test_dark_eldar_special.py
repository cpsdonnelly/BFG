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
    gs.slave_hook = lambda p, t, what, best: True
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
    gs.slave_hook = lambda p, tg, what, best: True
    m = OrdnanceMarker(id="i", ordnance_type=OrdnanceType.ASSAULT_BOAT.value, owner_player=2,
                       launched_by="d", x=0.0, y=3.0, special_rules=["dark_eldar", "impaler"])
    out = resolve_impaler(m, gs.get_ship_by_id("t"), False, DiceStub([4]), gs)
    assert out.get("slaves") and gs.slave_vp == {"2": 20}


def test_impaler_damage_and_crit():
    t = make_ship(id="t", player=1, x=0.0, y=0.0, hits_max=8, armor_prow="5+",
                  armor_side="5+", armor_rear="5+")
    gs = make_gs([t])
    gs.slave_hook = lambda p, tg, what, best: False
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


def _crippled(**kw):
    s = make_ship(id="t", player=1, hits_max=8, **kw)
    s.hits_remaining = 4                              # crippled
    return s


def test_pain_frenzy_rerolls_a_raid_only_against_crippled_ships():
    from src.hit_and_run import resolve_raids
    from src.dark_eldar import pain_frenzy_applies
    t = _crippled()
    gs = make_gs([t])
    assert pain_frenzy_applies(DE, t)
    assert not pain_frenzy_applies(DE, make_ship(hits_max=8))
    assert pain_frenzy_applies(DE + ["wych_cult"], make_ship(hits_max=8))    # Wych Cult
    gs.slave_hook = lambda *a: False                  # raid, not slaves
    asked = []
    gs.raid_reroll_hook = lambda *a: asked.append(a) or True   # the player re-rolls
    dice = DiceStub([1, 5] + [1] * 10)                 # first result, then the re-roll
    resolve_raids(1, gs.get_ship_by_id("t"), False, dice, gs, attacker_rules=DE)
    assert asked and dice._idx >= 2
    asked.clear()
    gs2 = make_gs([make_ship(id="u", player=1, hits_max=8)])
    gs2.slave_hook = lambda *a: False
    gs2.raid_reroll_hook = lambda *a: asked.append(a) or True
    resolve_raids(1, gs2.get_ship_by_id("u"), False, DiceStub([1] * 10), gs2, attacker_rules=DE)
    assert not asked                                   # not crippled: no re-roll offered


def test_pain_frenzy_rerolls_a_boarding_crit_on_a_crippled_ship():
    from src.boarding import _boarding_crit_check
    t = _crippled()
    gs = make_gs([t])
    de = make_ship(id="d", player=2, special_rules=list(DE))
    asked = []
    gs.raid_reroll_hook = lambda *a: asked.append(a) or True
    dice = DiceStub([3, 6, 1, 1, 1, 1])      # auto crit: 3, re-rolled to 6
    _boarding_crit_check(gs.get_ship_by_id("t"), 0, dice, gs, inflicted_by=[de])
    assert asked and dice._idx >= 2
    asked.clear()
    u = make_ship(id="u", player=1, hits_max=8)
    gs2 = make_gs([u])
    gs2.raid_reroll_hook = lambda *a: asked.append(a) or True
    _boarding_crit_check(gs2.get_ship_by_id("u"), 0, DiceStub([3, 1, 1, 1]), gs2,
                         inflicted_by=[de])     # not crippled: no re-roll offered
    assert not asked


def test_pain_frenzy_impaler_crit_reroll_choice():
    from src.dark_eldar import frenzy_crit_reroll
    t = _crippled()
    assert frenzy_crit_reroll(t, 7, {"extra_damage": 0})          # no extra damage: re-roll
    assert not frenzy_crit_reroll(t, 12, {"extra_damage": "D6"})  # bulkhead collapse: keep


def test_incubi_choose_the_better_of_two_or_both_against_crippled():
    from src.hit_and_run import resolve_raids
    t = make_ship(id="t", player=1, hits_max=8)
    gs = make_gs([t])
    gs.slave_hook = lambda *a: False
    dice = DiceStub([1, 6] + [1] * 10)     # 2D6, keep one; then the crit rolls
    r = resolve_raids(1, gs.get_ship_by_id("t"), False, dice, gs,
                      attacker_rules=DE + ["incubi"])
    assert r["raid_rolls"] == [6]
    c = _crippled()
    gs2 = make_gs([c])
    gs2.slave_hook = lambda *a: False
    r2 = resolve_raids(1, gs2.get_ship_by_id("t"), False, DiceStub([3, 4] + [1] * 10), gs2,
                       attacker_rules=DE + ["incubi"])
    assert len(r2["raid_rolls"]) == 2         # both results apply


def test_superstructure_damaged_costs_hits_when_turning():
    from src.dark_eldar import superstructure_strain
    from src.movement import MoveCommand
    s = make_ship(id="d", player=1, hits_max=6, special_rules=list(DE))
    s.critical_damage = [{"crit_type": "de_superstructure", "repairable": True}]
    gs = make_gs([s])
    cmds = [MoveCommand("forward", 10), MoveCommand("turn_left", 45),
            MoveCommand("forward", 5), MoveCommand("turn_right", 30)]
    dice = DiceStub([2, 5, 1, 1, 1])         # two turns: 2 (damage), 5; then crit checks
    assert superstructure_strain(gs, dice, "d", cmds) == 1
    assert gs.get_ship_by_id("d").hits_remaining == 5
