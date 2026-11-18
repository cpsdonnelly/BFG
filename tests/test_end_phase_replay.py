"""To do 18: the end phase's decisions (teleports, braces against raids,
repairs) are each player's recorded choices (end_choice events), made by
the AI, a human or a replay through one path (GameFlow._end_choice)."""
from src import recorder
from src.dice import DiceRoller, DiceSource, set_source, current_source
from src.game_state import GameState
from src.headless_game import HeadlessGame
from src.models import Ship
from src.ship_catalog import find_ship_class
from src.turn_controller import TurnController

CRITS = [{"crit_type": "port_armament", "description": "Port Armament Damaged",
          "repairable": True},
         {"crit_type": "engine_room", "description": "Engine Room Damaged",
          "repairable": True}]


def _game(source, replay=None):
    set_source(source)
    recorder.start_recording()
    gs = GameState(game_name="end", game_seed=5)
    gs.table_width, gs.table_height, gs.dice_mode = 120.0, 90.0, "auto"
    for p, x in ((1, 30.0), (2, 90.0)):
        d = find_ship_class("Lunar Class Cruiser").to_ship_dict(
            "Lunar Class Cruiser", p, ship_id=f"s{p}")
        d.update(x=x, y=45.0, heading=0.0, leadership=8, name=f"Ship{p}",
                 critical_damage=[dict(c) for c in CRITS] if p == 2 else [])
        gs.add_ship(Ship.from_dict(d))
    gs.current_phase, gs.active_player, gs.turn_number = "end", 1, 2
    tc = TurnController(gs, DiceRoller(mode="auto"), save_dir=None)
    recorder.set_current_gs(gs)
    if replay is None:
        return gs, HeadlessGame(tc)
    return gs, HeadlessGame(tc, replay_events=replay, replay_phases=("end",))


def test_a_replayed_end_phase_takes_the_recorded_repair_choice(monkeypatch):
    from src.ai_player import AIPlayer
    try:
        # a seed where the damaged Lunar rolls exactly one 6: a real choice
        for seed in range(60):
            gs, game = _game(DiceSource(seed, record=True))
            monkeypatch.setattr(AIPlayer, "auto_repair_choices",
                                staticmethod(lambda rep, n: rep[-n:]))  # not the default
            game._resolve_end_phase()
            evs = [e for e in recorder.events() if e["kind"] == "end_choice"]
            if evs and len(evs[0]["answer"]) == 1:
                break
        monkeypatch.undo()
        assert evs[0]["what"] == "repair" and evs[0]["seat"] and evs[0]["by"] == 2
        left = [c["description"] for c in gs.get_ship_by_id("s2").critical_damage]
        assert left == ["Port Armament Damaged"]          # the second was repaired
        record, events = current_source().record, list(recorder.events())
        gs2, game2 = _game(DiceSource(0, replay=[list(e) for e in record]), replay=events)
        game2._resolve_end_phase()
        assert [c["description"] for c in gs2.get_ship_by_id("s2").critical_damage] == left
        # without the record the AI's own choice repairs the first one
        gs3, game3 = _game(DiceSource(0, replay=[list(e) for e in record]))
        game3._resolve_end_phase()
        assert [c["description"] for c in gs3.get_ship_by_id("s2").critical_damage] \
            == ["Engine Room Damaged"]
    finally:
        set_source(DiceSource())
        recorder.stop_recording()


def test_damage_control_rolls_for_the_active_players_ships_first():
    """s.36: "the player whose turn it is rolls for his or her ships first"."""
    try:
        gs, game = _game(DiceSource(3, record=True))
        gs.active_player = 2
        sh = gs.get_ship_by_id("s1")
        sh.critical_damage = [dict(CRITS[0])]
        gs.update_ship(sh)
        game._resolve_end_phase()
        who = [("Ship2" if "Ship2" in str(r) else "Ship1")
               for r in current_source().record if "damage control" in str(r)]
        assert who == ["Ship2", "Ship1"]
    finally:
        set_source(DiceSource())
        recorder.stop_recording()
