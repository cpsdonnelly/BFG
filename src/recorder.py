"""Decision events (To do 17): what each player decided, recorded where the
engine acts on it, so a human's choices and the AI's are logged the same
way. Each event carries the turn, phase, active player and the dice
position (how many rolls the game's DiceSource had recorded when it
happened), which ties it to the roll record; with the start state, the
seed and the rolls, the events are the game.

Kinds (data keys): move (ship, from, path, to, heading, distance, turns),
order (ships, order, passed), fire (ship, target, weapon, kind, hits),
launch (ship, weapon, kind, markers), brace (ship, passed), reroll (player,
ship), board (attackers, target), teleport (ship, target), ram (ship,
target), disengage (ship, passed), prompt (title, answer, best) for every
"Auto (best)" prompt a player answered.

Off unless a game starts it (start_recording); the AI's planning never
calls these entry points, so it records nothing."""
import os
from typing import Dict, List, Optional

_EVENTS: Optional[List[Dict]] = None


def start_recording(events: List[Dict] = None) -> List[Dict]:
    """Record this game's events (a new game, or a loaded game's own)."""
    global _EVENTS
    _EVENTS = list(events or [])
    return _EVENTS


def stop_recording() -> None:
    global _EVENTS
    _EVENTS = None


def events() -> Optional[List[Dict]]:
    return _EVENTS


def recording() -> bool:
    return _EVENTS is not None


def _jsonable(v):
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if v is None or isinstance(v, (bool, int, float, str)):   # floats exact: moves replay
        return v
    return str(v)


def event(gs, kind: str, **data) -> None:
    """Record one decision (no-op unless recording)."""
    if _EVENTS is None:
        return
    from .dice import current_source
    rec = current_source().record
    _EVENTS.append({
        "n": len(_EVENTS), "kind": kind,
        "turn": getattr(gs, "turn_number", 0), "phase": getattr(gs, "current_phase", ""),
        "player": getattr(gs, "active_player", 0),
        "roll": len(rec) if rec is not None else None,
        **{k: _jsonable(v) for k, v in data.items()},
    })


def weapon_label(ship, weapon) -> str:
    """A weapon as '<index>:<name>' on its ship (index in ship.weapons)."""
    try:
        idx = next(i for i, w in enumerate(ship.weapons) if w is weapon)
    except StopIteration:
        idx = next((i for i, w in enumerate(ship.weapons) if w == weapon), -1)
    return f"{idx}:{weapon.get('name', weapon.get('weapon_type', ''))}"


STRICT = os.environ.get("BFG_RECORD_STRICT") == "1"   # tests: a broken extractor fails


def logged(kind: str, extract):
    """Decorator: after the call, record `kind` with extract(result, A) ->
    (gs, data), or None to skip; A is the call's arguments by parameter name
    (defaults filled in), so keyword and positional calls record alike.
    Outside tests a recording failure never stops the game."""
    import functools
    import inspect

    def deco(fn):
        sig = inspect.signature(fn)

        @functools.wraps(fn)
        def wrapper(*a, **k):
            res = fn(*a, **k)
            if _EVENTS is not None:
                try:
                    ba = sig.bind(*a, **k)
                    ba.apply_defaults()
                    out = extract(res, ba.arguments)
                except Exception:            # noqa: BLE001 (never break play for a log)
                    if STRICT:
                        raise
                    out = None
                if out:
                    event(out[0], kind, **out[1])
            return res
        return wrapper
    return deco


def _id(s):
    return getattr(s, "id", None)


_GS = None


def set_current_gs(gs) -> None:
    """The game being recorded, for entry points that aren't given it."""
    global _GS
    _GS = gs


def current_gs():
    return _GS
