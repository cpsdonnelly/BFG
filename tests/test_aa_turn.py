"""AA turn driver (To do 13): a round runs Command, Ordnance A, Shooting,
Movement, Ordnance B, End with both fleets, units activating one at a time."""
import random

from tests.conftest import make_ship, make_gs, DiceStub
from src.aa_turn import AATurn, config_from
from src.turn_controller import TurnController

GUN = {"name": "Battery", "weapon_type": "battery", "range_cm": 30, "strength": 4,
       "arcs": ["left", "right"]}


def _game(settings=None):
    ships = [make_ship(id=f"a{i}", player=1, x=20.0, y=20.0 + 10 * i, weapons=[dict(GUN)],
                       leadership=8) for i in range(2)]
    ships += [make_ship(id=f"b{i}", player=2, x=100.0, y=20.0 + 10 * i, weapons=[dict(GUN)],
                        leadership=7) for i in range(3)]
    ships.append(make_ship(id="b_unarmed", player=2, x=110.0, y=60.0, weapons=[]))
    gs = make_gs(ships)
    gs.aa_settings = dict(settings or {})
    tc = TurnController(gs, DiceStub([]))
    return gs, tc, AATurn(tc, rng=random.Random(5))


def _run_phase(aa, gs):
    seen = []
    while True:
        nxt = aa.next_activation()
        if nxt is None:
            return seen
        p, key = nxt
        assert gs.active_player == p
        key = key or aa.remaining_units(p)[0].key
        aa.activated(p, key)
        seen.append((p, key))


def test_a_round_runs_every_phase_and_unit():
    gs, tc, aa = _game()
    aa.start_game()
    assert gs.turn_system == "aa" and aa.round == 1
    phases = []
    for _ in range(6):
        phases.append(aa.phase)
        if aa.phase in ("shooting", "movement"):
            seen = _run_phase(aa, gs)
            n = 5 if aa.phase == "shooting" else 6        # the unarmed ship can't shoot
            assert len(seen) == n and len(set(seen)) == n
            assert {p for p, _k in seen} == {1, 2}
        else:
            assert aa.next_activation() is None
        aa.advance()
    assert phases == ["command", "ordnance_a", "shooting", "movement", "ordnance_b", "end"]
    assert aa.round == 2 and aa.phase == "command"


def test_settings_reach_the_driver():
    gs, tc, aa = _game({"order_mode": "fixed_initiative", "phase_order": "move_first"})
    cfg = config_from(gs)
    assert cfg.activation.order_mode == "fixed_initiative" and cfg.phase_order == "move_first"
    aa.start_game()
    aa.advance(); aa.advance()
    assert aa.phase == "movement"
    nxt = aa.next_activation()
    assert nxt[1] is not None                   # System 1 names the unit


def test_orders_and_brace_cleared_at_the_new_round():
    gs, tc, aa = _game()
    aa.start_game()
    for sid, order in (("a0", "lock_on"), ("b0", "brace_for_impact")):
        s = gs.get_ship_by_id(sid)
        s.special_order = order
        gs.update_ship(s)
    for _ in range(6):
        if aa.phase in ("shooting", "movement"):
            _run_phase(aa, gs)
        aa.advance()
    assert gs.get_ship_by_id("a0").special_order == "none"
    assert gs.get_ship_by_id("b0").special_order == "none"


def test_ordnance_cadence_and_launch_phase():
    gs, tc, aa = _game()
    aa.start_game()
    new = {"id": "n", "aa_round_placed": 1}
    old = {"id": "o", "aa_round_placed": 0}
    assert aa.may_move_ordnance(new)
    aa.record_ordnance_move(new, 1)
    assert not aa.may_move_ordnance(new)          # one move on its first round
    for _ in range(2):
        assert aa.may_move_ordnance(old)
        aa.record_ordnance_move(old, 1)
    assert not aa.may_move_ordnance(old)          # two a round afterwards
    while aa.phase != "ordnance_b":
        if aa.phase in ("shooting", "movement"):
            _run_phase(aa, gs)
        assert not aa.launch_allowed()
        aa.advance()
    assert aa.launch_allowed()


def test_boarding_locks_both_ships_in_aa():
    """AA notes: boarding locks both ships on declaration (no move, fire or
    launch this round) and resolves in the end phase; IGOUGO marks only the
    boarder. Locks clear at the next round."""
    from src.aa_turn import lock_boarding, is_locked
    gs, tc, aa = _game()
    lock_boarding(gs, "a0", "b0")
    assert not is_locked(gs.get_ship_by_id("b0"))          # IGOUGO: unchanged
    aa.start_game()
    a = gs.get_ship_by_id("a0")
    a.has_boarded, a.boarding_target_id = True, "b0"
    gs.update_ship(a)
    lock_boarding(gs, "a0", "b0")
    assert is_locked(gs.get_ship_by_id("a0")) and is_locked(gs.get_ship_by_id("b0"))
    for _ in range(6):
        if aa.phase in ("shooting", "movement"):
            _run_phase(aa, gs)
        aa.advance()
    assert not is_locked(gs.get_ship_by_id("b0"))


def test_system1_forcing_spends_a_reroll_and_dice_off():
    """System 1's optional forcing (ABFG): a re-roll makes one ship, friendly or
    enemy, activate first; both forcing -> 2D6 + the fleet's best Ld."""
    gs, tc, aa = _game({"order_mode": "fixed_initiative", "allow_forcing": True})
    for sid in ("a0", "b0"):
        s = gs.get_ship_by_id(sid)
        s.is_flagship, s.rerolls_remaining = True, 1
        gs.update_ship(s)
    aa.start_game()
    aa.advance(); aa.advance()                           # shooting
    assert aa.phase == "shooting"
    # player 1 (Ld 8) and player 2 (Ld 7) both force; 2D6 rolls 6 v 9: 14 v 16
    winner = aa.force_first({1: "a1", 2: "b2"}, DiceStub([6, 9]))
    assert winner == 2 and aa.next_activation() == (2, "b2")
    assert gs.get_ship_by_id("a0").rerolls_remaining == 0      # both paid
    assert gs.get_ship_by_id("b0").rerolls_remaining == 0
    # nobody can pay any more: no forcing
    assert aa.force_first({1: "a0"}, DiceStub([])) is None


def test_rams_lock_both_ships_and_resolve_in_the_end_phase():
    from src.aa_turn import defer_ram, resolve_pending_rams, is_locked
    gs, tc, aa = _game()
    assert defer_ram(gs, "a0", "b0") is False                # IGOUGO: resolve now
    aa.start_game()
    assert defer_ram(gs, "a0", "b0") is True
    assert is_locked(gs.get_ship_by_id("a0")) and is_locked(gs.get_ship_by_id("b0"))
    aa.advance()                                             # pending survives the phases
    assert gs.aa_state["pending_rams"] == [["a0", "b0"]]
    from src.dice import DiceRoller
    hit = []
    out = resolve_pending_rams(gs, DiceRoller(mode="auto"), on_hit=lambda s: hit.append(s.id))
    assert len(out) == 1 and gs.aa_state["pending_rams"] == []
    assert sorted(hit) == ["a0", "b0"]                       # destruction checks for both
