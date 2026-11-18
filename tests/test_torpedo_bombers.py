"""Torpedo bombers (s.21) and Tiger Sharks (owner ruling), To do 3."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.ship_catalog import find_ship_class
from src.models import Ship, OrdnanceMarker
from src.ordnance import (launch_attack_craft, torpedo_bomber_groups, fire_torpedo_bombers,
                          remove_spent_salvos, attacks_ships)


def _carrier(name, option, player=1, **kw):
    e = find_ship_class(name)
    d = e.to_ship_dict(name, player, ship_id="cv", upgrades=[option])
    d.update(kw)
    return Ship.from_dict(d)


def test_purchases_add_or_swap_the_craft():
    emp = _carrier("Emperor Battleship", "Attack craft: torpedo bombers")
    bays = [w for w in emp.weapons if w["weapon_type"] == "launch_bay"]
    assert all("torpedo_bomber" in w["craft_types"] for w in bays)
    pro = _carrier("Protector Cruiser", "Tiger Shark drone carriers")
    bay = next(w for w in pro.weapons if w["weapon_type"] == "launch_bay")
    assert "tiger_shark" in bay["craft_types"] and "manta" not in bay["craft_types"]


def test_salvo_replaces_squadrons_and_runs_out_of_fuel():
    emp = _carrier("Emperor Battleship", "Attack craft: torpedo bombers", x=0.0, y=0.0)
    gs = make_gs([emp])
    gs.turn_number = 1
    bay = next(w for w in emp.weapons if w["weapon_type"] == "launch_bay")
    ms = launch_attack_craft(gs.get_ship_by_id("cv"), bay, "torpedo_bomber", 2, gs)
    assert not attacks_ships(ms[0].ordnance_type)          # never attacks ships
    assert torpedo_bomber_groups(gs, 1) == []                # not in their launch turn
    from src.waves import form_wave
    form_wave(gs, [m.id for m in ms])
    gs.turn_number = 2
    groups = torpedo_bomber_groups(gs, 1)
    assert len(groups) == 1 and len(groups[0]) == 2          # the wave combines
    salvo = fire_torpedo_bombers(gs, [m.id for m in groups[0]], 90.0)
    assert salvo.strength == 4 and salvo.heading == 90.0
    assert [o["id"] for o in gs.ordnance] == [salvo.id]
    assert remove_spent_salvos(gs) == [salvo.id] and not gs.ordnance


def test_tiger_sharks_fire_tau_missiles():
    pro = _carrier("Protector Cruiser", "Tiger Shark drone carriers", x=0.0, y=0.0)
    gs = make_gs([pro])
    gs.turn_number = 1
    bay = next(w for w in pro.weapons if w["weapon_type"] == "launch_bay")
    m = launch_attack_craft(gs.get_ship_by_id("cv"), bay, "tiger_shark", 1, gs)[0]
    assert m.resilient_save == 4 and m.speed == 20
    gs.turn_number = 2
    salvo = fire_torpedo_bombers(gs, [m.id], 0.0)
    assert salvo.ordnance_type == "torpedo_guided" and salvo.strength == 2
    assert "limited_fuel" in salvo.special_rules


def test_ai_fires_its_torpedo_bombers_only_at_a_ship_in_reach():
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    for x, fired in ((25.0, True), (60.0, False)):
        foe = make_ship(id="e", player=2, x=x, y=0.0, points_value=200, turrets=1)
        tb = OrdnanceMarker(id="tb1", ordnance_type="torpedo_bomber", owner_player=1,
                            launched_by="cv", x=0.0, y=0.0, speed=20, launched_turn=1)
        gs = make_gs([make_ship(id="cv", player=1, x=-50.0), foe])
        gs.turn_number = 2
        gs.add_ordnance(tb)
        ai = AIPlayer(1, TurnController(gs, DiceStub([])), gs, DiceStub([]))
        ai._fire_torpedo_bombers()
        kinds = [o["ordnance_type"] for o in gs.ordnance]
        assert (kinds == ["torpedo_standard"]) == fired, (x, kinds)


def test_ai_strike_offers_torpedo_bombers():
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    emp = _carrier("Emperor Battleship", "Attack craft: torpedo bombers", x=0.0, y=0.0,
                   leadership=8)
    foe = make_ship(id="e", player=2, x=40.0, y=0.0, points_value=200, turrets=1)
    gs = make_gs([emp, foe])
    ai = AIPlayer(1, TurnController(gs, DiceStub([])), gs, DiceStub([]))
    ai._ord_committed = {}
    s = gs.get_ship_by_id("cv")
    opt = ai._strike_option(s, ["torpedo_bomber"], 4, [gs.get_ship_by_id("e")])
    assert opt and opt[1] == [("torpedo_bomber", 4)] and opt[0] > 0


def test_hazard_model_counts_a_salvo_not_bomber_attacks():
    from src.ai_hazards import marker_hits
    s = make_ship(id="s", player=1, x=0.0, y=0.0, turrets=2, armor_prow="6+", armor_side="5+")
    near = OrdnanceMarker(id="tb", ordnance_type="torpedo_bomber", owner_player=2,
                          launched_by="x", x=45.0, y=0.0, speed=20)
    far = OrdnanceMarker(id="tb2", ordnance_type="torpedo_bomber", owner_player=2,
                         launched_by="x", x=60.0, y=0.0, speed=20)
    h, why = marker_hits(s, near, (0.0, 0.0), [(0.0, 0.0)], [s])
    assert 0 < h <= 2 and "torpedo bombers" in why
    assert marker_hits(s, far, (0.0, 0.0), [(0.0, 0.0)], [s])[0] == 0.0


def _parked_game(friend_too=False, behind=True):
    """An Emperor's torpedo bomber wave (two squadrons) parked on an enemy
    Lunar that is behind the carrier (outside any torpedo arc it has); the
    salvo is placed there in the next ordnance phase."""
    from src.game_state import GameState
    from src.turn_controller import TurnController
    from src.dice import DiceRoller, DiceSource, set_source
    from src.headless_game import HeadlessGame
    from src import recorder
    set_source(DiceSource(3))
    gs = GameState(game_name="tb", game_seed=3)
    gs.table_width, gs.table_height, gs.dice_mode = 180.0, 120.0, "auto"
    gs.ai_spectator = True
    gs.add_ship(_carrier("Emperor Battleship", "Attack craft: torpedo bombers",
                         x=90.0, y=60.0, heading=0.0, leadership=8))
    foe = find_ship_class("Lunar Class Cruiser").to_ship_dict("Lunar Class Cruiser", 2,
                                                             ship_id="foe")
    foe.update(x=60.0 if behind else 120.0, y=60.0, heading=90.0, leadership=8)
    gs.add_ship(Ship.from_dict(foe))
    if friend_too:
        fr = find_ship_class("Lunar Class Cruiser").to_ship_dict("Lunar Class Cruiser", 1,
                                                                ship_id="friend")
        fr.update(x=60.0, y=60.0, heading=90.0, leadership=8)
        gs.add_ship(Ship.from_dict(fr))
    for i in range(2):
        gs.add_ordnance(OrdnanceMarker(
            id=f"tb{i}", ordnance_type="torpedo_bomber", owner_player=1, launched_by="cv",
            x=gs.get_ship_by_id("foe").x, y=60.0, speed=20, launched_turn=1,
            wave_id="w", wave_order=i))
    gs.current_phase, gs.active_player, gs.turn_number = "ordnance", 1, 3
    tc = TurnController(gs, DiceRoller(mode="auto"), save_dir=None)
    recorder.set_current_gs(gs)
    return gs, HeadlessGame(tc)


def test_placed_salvo_attacks_the_ship_it_is_placed_on_then_carries_on():
    """Owner ruling (s.21): a salvo placed overlapping a ship's base attacks at
    once (turrets first), whatever the carrier's arcs, then carries on at its
    reduced strength; it can't attack that ship again that turn."""
    from src.dice import DiceSource, set_source
    from src.ordnance import torpedo_may_attack
    try:
        gs, game = _parked_game()
        salvo = fire_torpedo_bombers(gs, ["tb0", "tb1"], 0.0)
        foe = gs.get_ship_by_id("foe")
        assert torpedo_may_attack(salvo, foe, gs)        # no launch arc for a placed salvo
        game.ordnance._resolve_ordnance_movement()
        foe = gs.get_ship_by_id("foe")
        assert any("Torpedoes contact Lunar" in line for line in game.ctx.lines)
        left = [o for o in gs.ordnance if o["id"] == salvo.id]
        if left:                                         # the misses carried on
            assert left[0]["strength"] < 4 and left[0]["x"] > 60.0 + 10
            assert left[0]["attacked_turns"]["foe"] == gs.turn_number
            assert not torpedo_may_attack(OrdnanceMarker.from_dict(left[0]), foe, gs)
    finally:
        set_source(DiceSource())


def test_placed_salvo_attacks_a_friendly_ship_it_is_placed_on():
    from src.dice import DiceSource, set_source
    try:
        gs, game = _parked_game(friend_too=True)
        fire_torpedo_bombers(gs, ["tb0", "tb1"], 0.0)
        game.ordnance._resolve_ordnance_movement()
        assert any("FRIENDLY FIRE" in line for line in game.ctx.lines)
    finally:
        set_source(DiceSource())


def test_ai_values_a_parked_wave_and_aims_its_carry_on():
    """The AI fires a wave parked on its target (certain contact) and points the
    salvo's carry-on away from its own ships; a friend under the wave counts
    against the shot."""
    from src.ai_hazards import torpedo_bomber_target, torpedo_bomber_heading, _bomber_salvo_value
    gs, _g = _parked_game()
    group = torpedo_bomber_groups(gs, 1)[0]
    v, e = torpedo_bomber_target(gs, group, 1)
    assert e.id == "foe" and v > 0
    # a friend 20cm along heading 0 from the parked wave: the carry-on avoids it
    fr = make_ship(id="f2", player=1, x=80.0, y=60.0, points_value=200)
    gs.add_ship(fr)
    h = torpedo_bomber_heading(gs, group, 1, gs.get_ship_by_id("foe"))
    assert _bomber_salvo_value(gs, group, 1, h) > _bomber_salvo_value(gs, group, 1, 0.0)
    gs2, _g2 = _parked_game(friend_too=True)
    v2, _e = torpedo_bomber_target(gs2, torpedo_bomber_groups(gs2, 1)[0], 1)
    assert v2 < v
