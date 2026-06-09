"""BFG:XR scenario / game-end rules.

Pure game logic — no Tkinter. The game panel calls these and renders
dialogs from the returned results.
"""
import math
from typing import Optional

from .models import Ship
from .game_state import GameState
from .victory_points import calculate_victory_points

ARTEFACT_PICKUP_RADIUS_CM = 5.0


def ships_alive(gs: GameState, player: int) -> bool:
    return any(
        s for s in gs.get_ships()
        if s.player == player and not s.is_destroyed and not s.is_disengaged
    )


def vp_winner(gs: GameState) -> Optional[int]:
    """Player with the higher VP total, or None on a tie."""
    vp = calculate_victory_points(gs)
    if vp["player1"] > vp["player2"]:
        return 1
    if vp["player2"] > vp["player1"]:
        return 2
    return None


def check_game_over(gs: GameState) -> Optional[dict]:
    """
    Check all game-end conditions (turn limit, fleet destruction, scenario
    objectives). Returns {'winner': int|None, 'reason': str, 'detail': str}
    if the game is over, else None.
    """
    # Turn limit
    if gs.turn_limit and gs.turn_number > gs.turn_limit:
        return {"winner": vp_winner(gs), "reason": "turn_limit", "detail": ""}

    # All ships gone
    if not ships_alive(gs, 1):
        return {"winner": 2, "reason": "no_ships", "detail": ""}
    if not ships_alive(gs, 2):
        return {"winner": 1, "reason": "no_ships", "detail": ""}

    return check_scenario_end(gs)


def check_scenario_end(gs: GameState) -> Optional[dict]:
    """Scenario-specific win conditions. Same return contract as check_game_over."""
    if gs.scenario_mode == "kill_admiral":
        for ship in gs.get_ships():
            if ship.is_flagship and ship.is_destroyed:
                return {"winner": 3 - ship.player,
                        "reason": "admiral_killed", "detail": ship.name}

    elif gs.scenario_mode in ("destroy_ship", "protect_ship"):
        if gs.objective_ship_id:
            target = gs.get_ship_by_id(gs.objective_ship_id)
            if target and target.is_destroyed:
                return {"winner": gs.scenario_attacker,
                        "reason": "objective_destroyed", "detail": target.name}

    elif gs.scenario_mode == "capture_artefact":
        if gs.artefact_carrier_id:
            carrier = gs.get_ship_by_id(gs.artefact_carrier_id)
            if carrier:
                if carrier.is_disengaged and gs.artefact_owner == gs.scenario_attacker:
                    return {"winner": gs.scenario_attacker,
                            "reason": "artefact_escaped", "detail": ""}
                if carrier.is_destroyed:
                    return {"winner": 3 - gs.scenario_attacker,
                            "reason": "artefact_lost", "detail": ""}

    return None


def check_artefact_pickup(gs: GameState) -> Optional[Ship]:
    """
    After movement: if an attacker ship reached the uncarried artefact token,
    mark it as the carrier and return the ship. Otherwise return None.
    """
    if gs.scenario_mode != "capture_artefact":
        return None
    if gs.artefact_token_pos is None or gs.artefact_carrier_id is not None:
        return None

    tx, ty = gs.artefact_token_pos
    for ship in gs.get_ships():
        if ship.is_destroyed or ship.is_disengaged:
            continue
        if ship.player == gs.scenario_attacker:
            dist = math.sqrt((ship.x - tx) ** 2 + (ship.y - ty) ** 2)
            if dist <= ARTEFACT_PICKUP_RADIUS_CM:
                gs.artefact_carrier_id = ship.id
                gs.artefact_owner = ship.player
                gs.artefact_token_pos = None
                gs.add_log(f"[ARTEFACT] {ship.name} picks up the artefact!")
                return ship
    return None
