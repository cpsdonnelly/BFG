"""To do 18 item 7: the action layer. One move function for the AI and every
human move path: the move, the ordnance it touched, the terrain tests it ran
into, its staged-move count, and an exact record of it."""
from src import recorder
from src.actions import apply_move, result_from
from src.movement import MoveCommand, validate_movement
from tests.conftest import DiceStub, make_gs, make_phenomenon, make_ship


def test_apply_move_runs_terrain_tests_and_records_the_move():
    ship = make_ship(id="a", x=20.0, y=50.0, heading=0.0, speed=20, leadership=8)
    gs = make_gs([ship])
    gs.add_phenomenon(make_phenomenon("asteroid_field", x=35.0, y=50.0,
                                      width=10.0, height=10.0, radius=0))
    cmds = [MoveCommand("forward", 20.0)]
    r = validate_movement(ship, cmds, "", 0, [], 180, 120)
    assert r.valid
    recorder.start_recording()
    dice = DiceStub([3, 3])                 # the asteroid navigation test, 2D6 = 6 vs Ld 8
    out = apply_move(gs, dice, gs.get_ship_by_id("a"), r, cmds, False)
    assert dice._idx == 2                   # the test was taken
    assert out.distance_moved_this_turn == 20.0
    assert "in_asteroid_field" not in out.special_rules    # resolved and cleared
    ev = [e for e in recorder.events() if e["kind"] == "act_move"][0]
    again = result_from(ev["result"])
    assert (again.final_x, again.final_y, again.path) == (r.final_x, r.final_y,
                                                          [tuple(p) for p in r.path])
    recorder.stop_recording()


def test_ram_and_boarding_declarations_replay(tmp_path):
    from src.actions import declare_ram, declare_boarding, replay_event
    from src.dice import DiceRoller, DiceSource, set_source
    from src.turn_controller import TurnController
    import copy

    def setup():
        a = make_ship(id="a", x=20.0, y=50.0, heading=0.0, leadership=8)
        b = make_ship(id="b", player=2, x=30.0, y=50.0, heading=180.0)
        return make_gs([a, b])
    gs = setup()
    start = copy.deepcopy(gs.ships)
    set_source(DiceSource(5, record=True))
    recorder.start_recording()
    dice = DiceRoller(mode="auto")
    passed = declare_ram(gs, dice, "a", "b")
    declare_boarding(gs, "a", "b")
    evs = [e for e in recorder.events() if e["depth"] == 0]
    assert [e["kind"] for e in evs] == ["declare_ram", "declare_boarding"]
    from src.dice import current_source
    rec = current_source().record
    after = copy.deepcopy(gs.ships)

    gs2 = setup()
    gs2.ships = start
    set_source(DiceSource(0, replay=[list(e) for e in rec]))
    tc = TurnController(gs2, DiceRoller(mode="auto"), save_dir=str(tmp_path))
    for e in evs:
        replay_event(gs2, tc, DiceRoller(mode="auto"), e)
    assert gs2.ships == after
    assert gs2.get_ship_by_id("a").ramming_target_id == ("b" if passed else None)
    recorder.stop_recording()
    set_source(DiceSource())


def test_a_fire_dialog_volley_is_one_action_that_replays():
    """To do 17 / 18: the Fire dialog's volley runs without a window
    (fire_volley.FireVolley) as one recorded action (actions.fire_volley);
    the same orders and the recorded dice give the same result."""
    import json
    from src import recorder, actions
    from src.dice import DiceRoller, DiceSource, set_source, current_source
    from src.game_state import GameState
    from src.headless_game import HeadlessContext
    from src.combat_panel import CombatPanel
    from src.models import Ship
    from src.ship_catalog import find_ship_class
    from src.turn_controller import TurnController

    def setup():
        gs = GameState(game_name="volley", game_seed=3)
        gs.ai_player = 2
        for p, n, x, h in ((1, "Lunar Class Cruiser", 40.0, 0.0),
                           (2, "Murder Class Cruiser", 40.0, 180.0)):
            d = find_ship_class(n).to_ship_dict(n, p, ship_id=f"p{p}")
            d.update(x=x if p == 1 else 40.0, y=30.0 if p == 1 else 50.0,
                     heading=90.0 if p == 1 else 270.0, leadership=8)
            gs.add_ship(Ship.from_dict(d))
        gs.current_phase, gs.active_player = "shooting", 1
        tc = TurnController(gs, DiceRoller(mode="auto"), save_dir=None)
        recorder.set_current_gs(gs)
        return gs, CombatPanel(HeadlessContext(tc, gs, tc.dice))

    def state(gs):
        return json.dumps({"ships": gs.ships, "bm": gs.blast_markers}, sort_keys=True,
                          default=str)

    set_source(DiceSource(5, record=True))
    recorder.start_recording()
    gs, panel = setup()
    lunar = gs.get_ship_by_id("p1")
    orders = [[i, "p2", None] for i, w in enumerate(lunar.weapons)
              if w.get("weapon_type") in ("battery", "lance")]
    actions.fire_volley(panel, "p1", orders)
    s1, record, evs = state(gs), current_source().record, recorder.events()
    assert any(e["kind"] == "fire" for e in evs)          # it rolled
    top = [e for e in evs if e["depth"] == 0]
    assert [e["kind"] for e in top if e["kind"] != "prompt"] == ["act_volley_fire"]

    set_source(DiceSource(0, replay=[list(e) for e in record]))
    recorder.start_recording()
    gs2, panel2 = setup()
    for e in top:
        if e["kind"] != "prompt":
            actions.replay_event(gs2, panel2.ctx.tc, panel2.ctx.dice, e, panel=panel2)
    set_source(DiceSource())                 # back to plain dice for later tests
    recorder.stop_recording()
    assert state(gs2) == s1


def test_a_nova_cannon_miss_places_a_blast_marker():
    """s.14: if no ships were hit, a blast marker under the centre of the
    template (the AI's path used to drop it; the Fire dialog placed it)."""
    from src import actions
    from tests.conftest import make_gs, make_ship, DiceStub
    nova = dict(name="Nova Cannon", weapon_type="nova_cannon", strength=1, range=150,
                arcs=["front"])
    a = make_ship(id="a", x=0.0, y=0.0, heading=0.0, weapons=[nova])
    t = make_ship(id="t", player=2, x=60.0, y=0.0)
    gs = make_gs([a, t])
    import src.combat as combat
    real = combat.resolve_nova_cannon
    combat.resolve_nova_cannon = lambda *a_, **k: {"template_x": 90.0, "template_y": 40.0,
                                                   "ship_hits": {}, "blast_markers": [(90.0, 40.0)]}
    try:
        actions.fire_nova_cannon(gs, DiceStub([]), "a", 60.0, 0.0)
    finally:
        combat.resolve_nova_cannon = real
    assert [(m.x, m.y) for m in gs.get_blast_markers()] == [(90.0, 40.0)]


def test_fire_at_squadron_action_replays():
    """The "Fire at Squadron" dialog's shot as one recorded action
    (actions.fire_at_squadron_ships): the same orders and dice, the same result."""
    import json
    from src import recorder, actions
    from src.dice import DiceRoller, DiceSource, set_source, current_source
    from src.game_state import GameState
    from src.headless_game import HeadlessContext
    from src.combat_panel import CombatPanel
    from src.models import Ship
    from src.ship_catalog import find_ship_class
    from src.turn_controller import TurnController

    def setup():
        gs = GameState(game_name="sq", game_seed=4)
        gs.ai_player = 2
        d = find_ship_class("Lunar Class Cruiser").to_ship_dict("Lunar Class Cruiser", 1,
                                                               ship_id="att")
        d.update(x=40.0, y=30.0, heading=0.0, leadership=8)
        gs.add_ship(Ship.from_dict(d))
        for i in range(3):
            n = "Sword Class Frigate"
            e = find_ship_class(n).to_ship_dict(n, 2, ship_id=f"e{i}")
            e.update(x=34.0 + 6 * i, y=48.0, heading=270.0, leadership=7, squadron_id="sq")
            gs.add_ship(Ship.from_dict(e))
        gs.current_phase, gs.active_player = "shooting", 1
        tc = TurnController(gs, DiceRoller(mode="auto"), save_dir=None)
        recorder.set_current_gs(gs)
        return gs, CombatPanel(HeadlessContext(tc, gs, tc.dice))

    def state(gs):
        return json.dumps({"ships": gs.ships, "bm": gs.blast_markers}, sort_keys=True,
                          default=str)

    set_source(DiceSource(9, record=True))
    recorder.start_recording()
    gs, panel = setup()
    att = gs.get_ship_by_id("att")
    from src.combat import check_weapon_in_arc
    e1 = gs.get_ship_by_id("e1")
    w_idx = next(i for i, w in enumerate(att.weapons) if w.get("weapon_type") == "battery"
                 and check_weapon_in_arc(att, w, e1.x, e1.y))
    res = actions.fire_at_squadron_ships(panel, "att", ["e0", "e1", "e2"], "sq", "abeam", w_idx)
    s1, record, evs = state(gs), current_source().record, recorder.events()
    top = [e for e in evs if e["depth"] == 0 and e["kind"] != "prompt"]
    set_source(DiceSource(0, replay=[list(e) for e in record]))
    recorder.start_recording()
    gs2, panel2 = setup()
    for e in top:
        actions.replay_event(gs2, panel2.ctx.tc, panel2.ctx.dice, e, panel=panel2)
    set_source(DiceSource())
    recorder.stop_recording()
    assert "hits" in res and [e["kind"] for e in top] == ["act_fire_squadron"]
    assert state(gs2) == s1


def test_human_launches_are_actions_that_replay():
    """The launch dialog's torpedo salvo (split in two) and bay launch (a
    wave) as recorded actions: replayed from the record, the same markers."""
    import json
    from src import recorder, actions
    from src.dice import DiceSource, set_source, current_source
    from src.game_state import GameState
    from src.models import Ship
    from src.ship_catalog import find_ship_class

    def setup():
        gs = GameState(game_name="launch", game_seed=6)
        for p, n, sid in ((1, "Dictator Class Cruiser", "dic"), (1, "Lunar Class Cruiser", "lun")):
            d = find_ship_class(n).to_ship_dict(n, p, ship_id=sid)
            d.update(x=30.0 if sid == "dic" else 60.0, y=30.0, heading=0.0, leadership=8)
            gs.add_ship(Ship.from_dict(d))
        gs.current_phase, gs.active_player = "ordnance", 1
        recorder.set_current_gs(gs)
        return gs

    set_source(DiceSource(6, record=True))
    recorder.start_recording()
    gs = setup()
    lun, dic = gs.get_ship_by_id("lun"), gs.get_ship_by_id("dic")
    t_idx = next(i for i, w in enumerate(lun.weapons) if w.get("weapon_type") == "torpedo")
    torps = actions.launch_torpedo_volley(gs, None, "lun", t_idx, 0.0, 3, 20.0, "standard",
                                          lun.weapons[t_idx]["strength"])
    bays = [i for i, w in enumerate(dic.weapons) if w.get("weapon_type") == "launch_bay"]
    kinds = sorted({ct for i in bays for ct in dic.weapons[i].get("craft_types", [])})
    craft = actions.launch_bays(gs, current_source_dice(), "dic", bays, 0.0,
                                [[kinds[0], "2"]], False, "dic", "", {"lone": "0", "cap": "0"},
                                None, True, "close", 8)
    state = json.dumps(gs.ordnance, sort_keys=True, default=str)
    record, evs = current_source().record, recorder.events()
    assert len(torps["markers"]) == 1 and len(craft["launched"]) == 2   # Str 6: no split (s.16)
    set_source(DiceSource(0, replay=[list(e) for e in record]))
    recorder.start_recording()
    gs2 = setup()
    for e in evs:
        if e["depth"] == 0:
            actions.replay_event(gs2, None, current_source_dice(), e)
    set_source(DiceSource())
    recorder.stop_recording()
    assert json.dumps(gs2.ordnance, sort_keys=True, default=str) == state


def current_source_dice():
    from src.dice import DiceRoller
    return DiceRoller(mode="auto")


def test_ai_resolves_ordnance_contacts_as_each_ship_moves():
    """s.15: ordnance a ship moves into attacks it as it moves. The AI uses the
    game flow's resolver after each ship's move, as a human's moves do (it used
    to wait for the end of its whole movement phase)."""
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    from tests.conftest import make_ship, make_gs, DiceStub
    ships = [make_ship(id=f"a{i}", player=1, x=20.0, y=20.0 + 20 * i) for i in range(2)]
    gs = make_gs(ships + [make_ship(id="e", player=2, x=100.0, y=60.0)])
    gs.current_phase, gs.active_player = "movement", 1
    dice = DiceStub([4])
    ai = AIPlayer(1, TurnController(gs, dice), gs, dice)
    calls = []
    ai.contacts_fn = lambda: calls.append(1)
    ai.run_movement_phase()
    assert len(calls) == 2              # once after each of the two moves


def test_ai_later_squadron_volley_sees_earlier_volleys_blast_markers(monkeypatch):
    """s.11: blast markers come into effect at once. Two AI squadrons fire in
    turn: the second plans with the marker the first volley placed."""
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    from src.models import BlastMarker
    from src import actions, combat
    from tests.conftest import make_ship, make_gs, DiceStub
    gun = {"name": "Prow Battery", "weapon_type": "battery", "range_cm": 30, "strength": 4,
           "arcs": ["front"]}
    ours = [make_ship(id=f"s{i}", player=1, ship_type="escort", x=0.0, y=-3.0 + 2 * i,
                      heading=0.0, squadron_id="A" if i < 2 else "B", weapons=[dict(gun)])
            for i in range(4)]
    gs = make_gs(ours + [make_ship(id="t", player=2, x=20.0, y=0.0)])
    gs.current_phase, gs.active_player = "shooting", 1
    seen = []
    real_plan = combat.plan_squadron_volley

    def spy(pairs, group, bms, *a, **k):
        seen.append(len(bms))
        return real_plan(pairs, group, bms, *a, **k)
    monkeypatch.setattr(combat, "plan_squadron_volley", spy)

    def fire(gs_, dice, lead, *a, **k):                  # each volley leaves a marker
        gs_.add_blast_marker(BlastMarker(id=f"bm{len(gs_.blast_markers)}", x=19.0, y=0.0))
    monkeypatch.setattr(actions, "fire_squadron_volley", fire)
    ai = AIPlayer(1, TurnController(gs, DiceStub([])), gs, DiceStub([]))
    ai._committed, ai._volley_fired = {}, set()
    ai._squadron_volleys()
    assert len(gs.blast_markers) == 2 and seen and seen[-1] == 1
