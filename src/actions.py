"""The action layer (To do 18 item 7, To do 17): each kind of player action is
one engine function, called by the window, the AI and a replay alike, which
records one "act" event with what it needs to be done again exactly. A
replay calls the same function with the recorded inputs (dice from the roll
record, questions from ReplayPrompter), so a game with human players replays
like an AI's.

Built so far: moves (apply_move: the AI's and every human move path)."""
from . import recorder
from .movement import (MovementResult, MoveCommand, execute_movement,
                       record_staged_move)


def _result_data(result: MovementResult) -> dict:
    return {k: v for k, v in vars(result).items()}


def result_from(data: dict) -> MovementResult:
    """A recorded movement result, as it was applied."""
    r = MovementResult()
    for k, v in data.items():
        if k == "path":
            v = [tuple(p) for p in v]
        setattr(r, k, v)
    return r


def apply_move(gs, dice, ship, result: MovementResult, commands, on_aaf: bool,
               contacts=None, log=None):
    """Make a validated move: the ship moves (execute_movement), the ordnance
    it ran into attacks it (`contacts`, s.15; the AI's are resolved after its
    whole phase for now), the asteroid / warp rift / cloud tests it ran into
    (s.39), and its movement this phase is counted (staged moves).
    Returns the ship as it ends."""
    recorder.event(gs, "act_move", ship=ship.id, result=_result_data(result),
                   commands=[[c.action, c.value] for c in commands or []], on_aaf=on_aaf)
    execute_movement(ship, result, gs, dice)
    if contacts is not None:
        contacts()
    from .terrain_effects import resolve_post_move_terrain
    if log is None:
        resolve_post_move_terrain(gs, ship.id, dice, on_aaf)
    else:
        resolve_post_move_terrain(gs, ship.id, dice, on_aaf, log=log)
    return record_staged_move(gs, ship.id, result, list(commands or []))


def commands_from(data) -> list:
    return [MoveCommand(a, v) for a, v in data]
