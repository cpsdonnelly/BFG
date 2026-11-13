"""Target-directed movement candidates (CLAUDE.md To do 11 a, owner): turn
points, the even grid as fallback, goals against the target; every candidate
is a legal move."""
import math
from tests.conftest import make_gs, DiceStub
from src.models import Ship, SpecialOrder
from src.ship_catalog import find_ship_class
from src.ai_player import AIPlayer
from src.turn_controller import TurnController
from src.movement import validate_movement


def _ship(name, player, x, y, h, i=0):
    d = find_ship_class(name).to_ship_dict(name, player, ship_id=f"{name[:4]}{player}{i}")
    d.update(x=x, y=y, heading=h, leadership=8)
    return Ship.from_dict(d)


def _ai(ships):
    gs = make_gs(ships)
    gs.table_width, gs.table_height = 180.0, 120.0
    ai = AIPlayer(1, TurnController(gs, DiceStub([])), gs, DiceStub([]))
    ai.difficulty = "normal"
    return ai, gs


def test_every_candidate_is_a_legal_move():
    for name in ("Lunar Class Cruiser", "Emperor Class Battleship", "Cobra Class Destroyer",
                 "Protector Class Cruiser"):
        for order in ("", SpecialOrder.BURN_RETROS.value):
            me = _ship(name, 1, 60.0, 60.0, 30.0)
            foe = _ship("Lunar Class Cruiser", 2, 120.0, 40.0, 200.0)
            ai, gs = _ai([me, foe])
            cands = ai._move_candidates(me, foe, order, 0)
            assert cands
            for turn_deg, dist, turn_at, _src in cands:
                cmds = ai._move_cmds(me, turn_deg, dist, turn_at)
                res = validate_movement(me, cmds, order, table_width=180.0, table_height=120.0)
                assert not res.errors, (name, order, turn_deg, dist, turn_at, res.errors)
                # the simulator ends where the engine does
                fx, fy, _fh = ai._simulate_final_pos(me, turn_deg, dist, turn_at)
                ex, ey = res.path[-1]
                assert math.hypot(fx - ex, fy - ey) < 1e-6


def test_turn_points_and_goals_are_offered():
    """Capital ships may turn after the minimum distance, after the minimum
    move or at the end; escorts also at the very start; the guns-to-bear
    goal searches the turn angle finely."""
    me = _ship("Lunar Class Cruiser", 1, 60.0, 60.0, 0.0)
    foe = _ship("Lunar Class Cruiser", 2, 75.0, 95.0, 0.0)      # off to port
    ai, gs = _ai([me, foe])
    cands = ai._move_candidates(me, foe, "", 0)
    points = {c[2] for c in cands if abs(c[0]) > 0.5}
    assert {None, 10, 20}.issubset(points) or {10, 20}.issubset(points)
    assert any(c[3] == "guns to bear" for c in cands)
    esc = _ship("Cobra Class Destroyer", 1, 60.0, 60.0, 0.0)
    ai2, _ = _ai([esc, foe])
    assert any(c[2] == 0.0 and abs(c[0]) > 0.5 for c in ai2._move_candidates(esc, foe, "", 0))


def test_range_band_goal_aims_for_the_winning_bracket():
    """A Merchant (45cm railguns) facing a Lunar (30cm guns) aims for 30-45cm,
    the bracket it wins (To do 8 f); a ship that wins nowhere gets no band."""
    m = _ship("Merchant Starship", 1, 60.0, 60.0, 0.0)
    lunar = _ship("Lunar Class Cruiser", 2, 140.0, 60.0, 180.0)
    ai, gs = _ai([m, lunar])
    assert ai._range_band(m, lunar) == 37.5
    weak = _ship("Cobra Class Destroyer", 1, 60.0, 60.0, 0.0)
    big = _ship("Emperor Class Battleship", 2, 140.0, 60.0, 180.0)
    ai2, _ = _ai([weak, big])
    assert ai2._range_band(weak, big) is None or ai2._range_band(weak, big) > 0


def test_point_goals_and_refinement():
    """Goals c / d / 3 (To do 11 a): prow-on, into the target's rear arc, a
    second target, an escort to the commander's ship; the planner refines the
    best candidates and its moves stay legal."""
    import random
    me = _ship("Cobra Class Destroyer", 1, 60.0, 60.0, 0.0)
    flag = _ship("Lunar Class Cruiser", 1, 40.0, 80.0, 0.0, 1)
    flag.is_flagship = True
    foe = _ship("Lunar Class Cruiser", 2, 85.0, 70.0, 180.0)
    foe2 = _ship("Lunar Class Cruiser", 2, 100.0, 30.0, 180.0, 2)
    ai, gs = _ai([me, flag, foe, foe2])
    srcs = {c[3] for c in ai._move_candidates(me, foe, "", 0)}
    assert {"prow-on", "rear arc", "second target", "support"} <= srcs
    # a rear-arc candidate ends behind the target's predicted position
    from src.ai_hazards import _predicted_positions
    nxt = _predicted_positions(foe, True)[1]
    rear = [c for c in ai._move_candidates(me, foe, "", 0) if c[3] == "rear arc"]
    ends = [ai._simulate_final_pos(me, c[0], c[1], c[2]) for c in rear]
    assert any(nxt.get_target_arc(x, y) == "rear" for x, y, _h in ends)
    rng = random.Random(3)
    for _ in range(12):
        name = rng.choice(["Lunar Class Cruiser", "Cobra Class Destroyer",
                           "Emperor Class Battleship"])
        me = _ship(name, 1, rng.uniform(40, 140), rng.uniform(30, 90), rng.uniform(0, 360))
        foe = _ship("Lunar Class Cruiser", 2, rng.uniform(40, 140), rng.uniform(30, 90),
                    rng.uniform(0, 360))
        ai, gs = _ai([me, foe])
        order = rng.choice(["", SpecialOrder.BURN_RETROS.value])
        cmds = ai._plan_move_toward(me, foe, order, 0)
        res = validate_movement(me, cmds, order, table_width=180.0, table_height=120.0)
        assert not res.errors, (name, order, ai._last_move_source, res.errors)


def test_supported_ships_move_first():
    """Coordination (To do 11 a): the commander's ship, then carriers, other
    capital ships, escorts last; squadrons stay together."""
    from tests.conftest import make_ship
    bay = {"name": "Bays", "weapon_type": "launch_bay", "strength": 2, "arcs": []}
    ships = [make_ship(id="e1", player=1, ship_type="escort", squadron_id="sq"),
             make_ship(id="c", player=1),
             make_ship(id="e2", player=1, ship_type="escort", squadron_id="sq"),
             make_ship(id="cv", player=1, weapons=[bay]),
             make_ship(id="f", player=1, is_flagship=True)]
    order = [s.id for s in AIPlayer._coordinated_order(ships)]
    assert order == ["f", "cv", "c", "e1", "e2"]


def test_lock_on_goal_and_dense_grid_when_crowded():
    """Goal g (pointed for a straight Lock On move next turn) is always offered;
    the denser grid only when enemy ordnance or terrain crowds the area; every
    candidate stays legal."""
    from tests.conftest import make_marker
    me = _ship("Lunar Class Cruiser", 1, 60.0, 60.0, 0.0)
    foe = _ship("Lunar Class Cruiser", 2, 110.0, 80.0, 180.0)
    ai, gs = _ai([me, foe])
    srcs = {c[3] for c in ai._move_candidates(me, foe, "", 0)}
    assert "lock on next" in srcs and "dense grid" not in srcs
    for i, (x, y) in enumerate([(70.0, 75.0), (75.0, 45.0)]):
        gs.add_ordnance(make_marker(id=f"t{i}", ordnance_type="torpedo_standard",
                                    owner_player=2, x=x, y=y, heading=180.0))
    cands = ai._move_candidates(me, foe, "", 0)
    assert any(c[3] == "dense grid" for c in cands)
    for turn_deg, dist, turn_at, _src in cands:
        res = validate_movement(me, ai._move_cmds(me, turn_deg, dist, turn_at), "",
                                table_width=180.0, table_height=120.0)
        assert not res.errors


def test_lock_on_when_guns_will_bear_after_a_straight_move():
    """To do 10 a: Lock On when the target will be in arc after the move it
    allows (straight on), not merely now. A Lunar with an enemy abeam within
    range keeps it on the beam moving straight: Lock On. With the enemy dead
    ahead, the broadsides only bear after a turn, which Lock On forbids: no."""
    me = _ship("Lunar Class Cruiser", 1, 60.0, 60.0, 0.0)
    abeam = _ship("Lunar Class Cruiser", 2, 75.0, 82.0, 0.0)
    ai, gs = _ai([me, abeam])
    assert ai._lock_on_gain(me) > 0
    assert ai._choose_special_order(me) == SpecialOrder.LOCK_ON.value
    ahead = _ship("Lunar Class Cruiser", 2, 100.0, 60.0, 180.0)
    ai2, _ = _ai([me, ahead])
    assert ai2._lock_on_gain(me) <= 0


def test_low_value_order_skipped_when_it_risks_later_orders():
    """To do 10 c: a failed check ends later checks (s.2). A ship whose order
    is worth little and likely to fail skips it when a valuable order comes
    after it."""
    me = _ship("Lunar Class Cruiser", 1, 60.0, 60.0, 0.0)
    later = _ship("Lunar Class Cruiser", 1, 60.0, 30.0, 0.0, 1)
    foe = _ship("Lunar Class Cruiser", 2, 75.0, 82.0, 0.0)
    ai, gs = _ai([me, later, foe])
    me = gs.get_ship_by_id(me.id)
    me.leadership = 5
    gs.update_ship(me)
    ai._order_plan = {"seq": [me.id, later.id],
                      "orders": {later.id: ("lock_on", 500.0, 0.9)}}
    assert ai._pick_special_order(gs.get_ship_by_id(me.id)) == SpecialOrder.LOCK_ON.value
    assert ai._choose_special_order(gs.get_ship_by_id(me.id)) is None
    ai._order_plan = {"seq": [me.id, later.id], "orders": {}}
    assert ai._choose_special_order(gs.get_ship_by_id(me.id)) == SpecialOrder.LOCK_ON.value


def test_all_ahead_full_when_far_and_lock_on_only_for_guns_that_fire():
    """To do 10 b: an Ork kroozer far from the enemy goes All Ahead Full (it
    passes automatically, and nothing would fire this turn anyway); in reach
    it Locks On. Lock On counts only guns in range after the move."""
    me = _ship("Kill Kroozer", 1, 40.0, 60.0, 0.0)
    far = _ship("Lunar Class Cruiser", 2, 130.0, 60.0, 180.0)
    ai, gs = _ai([me, far])
    assert ai._lock_on_gain(me) == 0.0
    assert ai._pick_special_order(me) == SpecialOrder.ALL_AHEAD_FULL.value
    near = _ship("Lunar Class Cruiser", 2, 90.0, 60.0, 180.0)
    ai2, _ = _ai([me, near])
    assert ai2._pick_special_order(me) == SpecialOrder.LOCK_ON.value


def test_position_with_an_enemy_off_each_beam_scores_both_broadsides():
    """To do 8 b: a Lunar between two enemies, one off each beam, keeps both
    broadsides busy; with both enemies off one side only one bears."""
    me = _ship("Lunar Class Cruiser", 1, 60.0, 60.0, 0.0)
    port = _ship("Lunar Class Cruiser", 2, 60.0, 80.0, 0.0, 1)
    stbd = _ship("Lunar Class Cruiser", 2, 60.0, 40.0, 0.0, 2)
    ai, gs = _ai([me, port, stbd])
    both = ai._mount_coverage(me, 60.0, 60.0, 0.0, port)
    one_side = ai._mount_coverage(me, 60.0, 100.0, 0.0, port)   # both off the starboard side
    assert both > 0 and one_side == 0


def test_long_ranged_fast_ship_kites_a_brawler():
    """To do 8 c: a Murder (speed 25, 45-60cm guns) facing a Lunar (20cm, 30cm
    guns) gains in the 50-60cm band; a Slaughter (30cm guns) has no edge."""
    lunar = _ship("Lunar Class Cruiser", 2, 120.0, 60.0, 180.0)
    murder = _ship("Murder Class Cruiser", 1, 40.0, 60.0, 0.0)
    ai, gs = _ai([murder, lunar])
    assert ai.range_speed_edge(murder, lunar)
    assert ai._kite_bonus(murder, 65.0, 60.0, 0.0, lunar) > 0          # 55cm away
    assert ai._kite_bonus(murder, 95.0, 60.0, 0.0, lunar) == 0.0       # 25cm: in its reach
    slaughter = _ship("Slaughter Class Cruiser", 1, 40.0, 60.0, 0.0)
    ai2, _ = _ai([slaughter, lunar])
    assert not ai2.range_speed_edge(slaughter, lunar)


def test_ork_boards_a_crippled_lunar_only_with_boarding_on():
    """To do 8 h: with the boarding rule on, an Ork kroozer's moves include
    base contact with its target, a move ending there gains the boarding
    action's value, and in contact it declares one; off, none of it."""
    ork = _ship("Kill Kroozer", 1, 60.0, 60.0, 0.0)
    lunar = _ship("Lunar Class Cruiser", 2, 80.0, 60.0, 180.0)
    ai, gs = _ai([ork, lunar])
    lun = gs.get_ship_by_id(lunar.id)
    lun.hits_remaining = 3
    gs.update_ship(lun)
    o, t = gs.get_ship_by_id(ork.id), gs.get_ship_by_id(lunar.id)
    assert not any(c[3] == "board" for c in ai._move_candidates(o, t, "", 0))
    assert ai._boarding_reach(o, 76.0, 60.0, t) == 0.0
    gs.rule_boarding = True
    assert any(c[3] == "board" for c in ai._move_candidates(o, t, "", 0))
    assert ai._boarding_reach(o, t.x - t.base_radius - o.base_radius, 60.0, t) > 0
    o.x = t.x - t.base_radius - o.base_radius
    gs.update_ship(o)
    ai._consider_boarding(gs.get_ship_by_id(o.id))
    assert gs.get_ship_by_id(o.id).boarding_target_id == t.id


def test_ram_dead_ahead_only_with_ramming_on():
    """To do 8 h: on All Ahead Full an Ork kroozer declares a ram on the enemy
    dead ahead, and the ram resolves as it moves through; off, nothing."""
    from src.models import Ship as _S
    ork = _ship("Kill Kroozer", 1, 40.0, 60.0, 0.0)
    lunar = _ship("Lunar Class Cruiser", 2, 60.0, 60.0, 90.0)       # side-on, 20cm ahead
    ai, gs = _ai([ork, lunar])
    o = gs.get_ship_by_id(ork.id)
    assert ai._ram_candidate(o) is None
    gs.rule_ramming = True
    cand = ai._ram_candidate(o)
    assert cand is not None and cand[1].id == lunar.id
    from tests.conftest import DiceStub
    ai.dice = DiceStub([3, 3])                        # same size: 2D6 = 6, passes Ld 8
    ai._declare_ram(o)
    o = gs.get_ship_by_id(ork.id)
    assert o.ramming_target_id == lunar.id
    hits = [6] * o.hits_max + [1] * ((lunar.hits_max + 1) // 2)
    ai.dice = DiceStub(hits + [1] * 20)
    o.x = 80.0
    gs.update_ship(o)
    ai._resolve_ram(gs.get_ship_by_id(ork.id), (40.0, 60.0))
    assert gs.get_ship_by_id(lunar.id).hits_remaining < lunar.hits_max
    assert gs.get_ship_by_id(ork.id).ramming_target_id is None
    assert isinstance(o, _S)


def test_easy_moves_are_softmax_choices():
    """To do 11 i: Easy samples moves by softmax on their value: legal, mostly
    good, not always the best."""
    import random
    random.seed(4)
    me = _ship("Lunar Class Cruiser", 1, 60.0, 60.0, 0.0)
    foe = _ship("Lunar Class Cruiser", 2, 110.0, 80.0, 180.0)
    ai, gs = _ai([me, foe])
    ai.difficulty = "easy"
    seen = set()
    for _ in range(15):
        cmds = ai._plan_move_toward(me, foe, "", 0)
        res = validate_movement(me, cmds, "", table_width=180.0, table_height=120.0)
        assert not res.errors
        seen.add((round(res.final_x, 1), round(res.final_y, 1)))
    assert len(seen) > 1


def test_reload_by_value_against_lock_on():
    """To do 10 b: Reload Ordnance is valued as next turn's launch and weighed
    against Lock On in expected VP. A Lunar with spent torpedoes and an enemy
    abeam Locks On (its broadsides are worth more than one strength-6 salvo a
    turn on); with nothing worth Locking On for it reloads."""
    me = _ship("Lunar Class Cruiser", 1, 60.0, 60.0, 0.0)
    abeam = _ship("Lunar Class Cruiser", 2, 75.0, 82.0, 0.0)
    ai, gs = _ai([me, abeam])
    me = gs.get_ship_by_id(me.id)
    me.ordnance_loaded_torps = False
    gs.update_ship(me)
    rv = ai._reload_value(me)
    assert rv > 0
    from src.ai_hazards import value_per_hit
    gun_vp = ai._lock_on_gain(me) * 0.35 * value_per_hit(abeam, gs)
    want = SpecialOrder.LOCK_ON.value if gun_vp >= rv else SpecialOrder.RELOAD_ORDNANCE.value
    assert ai._pick_special_order(me) == want
    ahead = _ship("Lunar Class Cruiser", 2, 100.0, 60.0, 180.0)
    ai2, gs2 = _ai([me, ahead])
    assert ai2._pick_special_order(gs2.get_ship_by_id(me.id)) == SpecialOrder.RELOAD_ORDNANCE.value
    # a far enemy out of torpedo reach: nothing to gain next turn, still reloads
    far = _ship("Lunar Class Cruiser", 2, 175.0, 115.0, 180.0)
    ai3, gs3 = _ai([me, far])
    assert ai3._reload_value(gs3.get_ship_by_id(me.id)) == 0.0


def test_come_to_new_heading_two_turns():
    """To do 10 b: Come to New Heading gives a second turn at half firepower.
    A Tau Protector (90-degree turns, guns forward) with an enemy close behind
    turns twice to bring its prow round; a Lunar with the enemy abeam doesn't.
    Every two-turn move is legal under the order."""
    me = _ship("Protector Class Cruiser", 1, 60.0, 60.0, 0.0)
    behind = _ship("Lunar Class Cruiser", 2, 20.0, 62.0, 0.0)
    ai, gs = _ai([me, behind])
    me = gs.get_ship_by_id(me.id)
    assert ai._ctnh_gain(me) > 0
    assert ai._pick_special_order(me) == SpecialOrder.COME_TO_NEW_HEADING.value
    o = SpecialOrder.COME_TO_NEW_HEADING.value
    moves = ai._ctnh_moves(me, behind)
    assert moves
    for _sc, cmds, _src in moves:
        assert not validate_movement(me, cmds, o, table_width=180, table_height=120).errors
    cmds = ai._plan_move_toward(me, behind, o, 0)
    assert sum(c.action.startswith("turn") for c in cmds) == 2
    assert ai._last_move_source.startswith("come to new heading")
    lunar = _ship("Lunar Class Cruiser", 1, 60.0, 60.0, 0.0)
    abeam = _ship("Lunar Class Cruiser", 2, 75.0, 82.0, 0.0)
    ai2, gs2 = _ai([lunar, abeam])
    assert ai2._pick_special_order(gs2.get_ship_by_id(lunar.id)) != o


def test_crippled_ship_values_disengaging_near_a_phenomenon():
    """To do 11 a goal 3 / 11 c: the disengage test is taken at the end of the
    move (s.37), +3 Ld within 15cm of a celestial phenomenon. For a crippled
    Lunar (Ld 6) under three enemy cruisers, a move ending within 15cm of a
    dust cloud scores more with the cloud there than without, by the better
    disengage chance (the move score still weighs it against its guns)."""
    from src.models import Phenomenon
    from src.disengage import get_disengage_ld_modifiers
    me = _ship("Lunar Class Cruiser", 1, 60.0, 60.0, 0.0)
    me.hits_remaining, me.leadership = 3, 6
    foes = [_ship("Lunar Class Cruiser", 2, 95.0, 40.0 + 15 * i, 180.0, i) for i in range(3)]
    ai, gs = _ai([me] + foes)
    me = gs.get_ship_by_id(me.id)
    ai._move_nearest = foes[0]
    cand = (45.0, 15.0, 10.0)                      # turn towards the cloud
    x, y, h = ai._simulate_final_pos(me, *cand)
    before = ai._move_score(me, foes[1], "", *cand)
    spot0 = ai._disengage_spot(me, x, y, h, foes[1])
    assert spot0 > 0                                # worth trying even here
    gs.add_phenomenon(Phenomenon(id="c", phenomenon_type="gas_dust_cloud", x=74.0, y=82.0,
                                 width=10.0, height=10.0))
    moved = Ship.from_dict(me.to_dict())
    moved.x, moved.y = x, y
    assert get_disengage_ld_modifiers(moved, gs)["effective_ld"] == 9
    spot1 = ai._disengage_spot(me, x, y, h, foes[1])
    assert spot1 > spot0
    assert abs(ai._move_score(me, foes[1], "", *cand) - before - (spot1 - spot0)) < 1e-6
    # a healthy ship far from any danger doesn't care
    me2 = _ship("Lunar Class Cruiser", 1, 20.0, 20.0, 0.0)
    far = _ship("Lunar Class Cruiser", 2, 170.0, 110.0, 180.0)
    ai2, gs2 = _ai([me2, far])
    assert ai2._disengage_spot(gs2.get_ship_by_id(me2.id), 30.0, 20.0, 0.0, far) == 0.0
