"""First turn (core rules, "First turn", s.2): both players roll a D6 (re-rolling
ties) and the higher may move first or second. Scenarios that fix it aren't
built yet (To do 7).

The AI's choice (To do 11 e, judgement): move first when its guns can reach the
enemy this turn (gun reach + speed covers the gap between the fleets), so it
shoots first; otherwise second, letting the enemy close into its reach."""
import math
from typing import Tuple


def _reach(s) -> float:
    guns = [w.get("range_cm") or 0 for w in s.weapons
            if w.get("weapon_type") in ("battery", "lance", "nova_cannon")]
    return (max(guns) if guns else 0.0) + (s.speed or 0)


def ai_moves_first(gs, player: int) -> bool:
    mine = [s for s in gs.get_ships() if s.player == player and not s.is_destroyed]
    theirs = [s for s in gs.get_ships() if s.player != player and not s.is_destroyed]
    if not mine or not theirs:
        return True
    gap = min(math.hypot(a.x - b.x, a.y - b.y) for a in mine for b in theirs)
    return max(_reach(s) for s in mine) >= gap


def roll_off(dice, dice2=None) -> Tuple[int, Tuple[int, int]]:
    """(winner, (player 1's roll, player 2's roll)); ties are re-rolled.
    dice2: player 2's roller if different (an AI player rolls automatically)."""
    dice2 = dice2 or dice
    while True:
        a = dice.roll_d6(1, "First turn roll-off: player 1")[0]
        b = dice2.roll_d6(1, "First turn roll-off: player 2")[0]
        if a != b:
            return (1 if a > b else 2), (a, b)
