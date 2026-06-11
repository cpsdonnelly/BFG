"""Pyodide entry points callable from the JS Web Worker.

JS calls these functions via pyodide.runPython() / pyodide.globals.get().
All heavy game logic lives in WebGameContext; this module is just the boundary.
"""
import json
import os

from . import web_ui_stub as _ui

_ctx = None


def init(sab_int32) -> None:
    """Called once after Pyodide boots.  Receives the SharedArrayBuffer view."""
    _ui._sab = sab_int32
    os.makedirs("/saves/bfg_web", exist_ok=True)

    global _ctx
    from .web_game_context import WebGameContext
    _ctx = WebGameContext()


def start_game(config_json: str) -> str:
    """Load a game config and start the game.  Returns updated state JSON."""
    config = json.loads(config_json)
    _ctx.dispatch({"name": "start_game", "data": config})
    return get_state()


def perform_action(action_json: str) -> str:
    """Dispatch one game action.  Returns updated state JSON."""
    action = json.loads(action_json)
    _ctx.dispatch(action)
    return get_state()


def get_state() -> str:
    """Return the current full game state as a JSON string."""
    return json.dumps(_ctx._state_snapshot())
