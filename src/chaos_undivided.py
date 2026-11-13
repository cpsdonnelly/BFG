"""Mark of Chaos Undivided (bfgxr/rules/07_chaos.md, Marks of Chaos): on the
Chaos Warmaster's or Lord's ship; once per game, before a Leadership test or
command check, the whole fleet may use the marked ship's Leadership until the
end of the turn.

The boost raises each of the player's ships to the marked ship's Ld (never
lowers one) and is undone at the end of that player's turn, keeping any Ld
change that happened meanwhile (e.g. Bridge Smashed -3)."""
from typing import Optional

from .models import Ship


def undivided_leader(gs, player: int) -> Optional[Ship]:
    return next((s for s in gs.get_ships() if s.player == player
                 and "mark:undivided" in s.special_rules
                 and not s.is_destroyed and not s.is_disengaged), None)


def can_use(gs, player: int) -> bool:
    return player not in (gs.undivided_used or []) and undivided_leader(gs, player) is not None


def activate(gs, player: int) -> int:
    """Use the Mark now: every ship of the player takes the marked ship's Ld
    (if higher) until the end of the turn. Returns the Ld used."""
    lead = undivided_leader(gs, player)
    if lead is None or player in (gs.undivided_used or []):
        return 0
    ld = lead.leadership
    deltas = {}
    for s in gs.ships:
        if s["player"] == player and (s.get("leadership") or 0) < ld:
            deltas[s["id"]] = ld - (s.get("leadership") or 0)
            s["leadership"] = ld
    gs.undivided_used = list(gs.undivided_used or []) + [player]
    gs.undivided_boost = dict(gs.undivided_boost or {})
    gs.undivided_boost[str(player)] = {"turn": gs.turn_number, "deltas": deltas}
    gs.add_log(f"Mark of Chaos Undivided: player {player}'s fleet uses "
               f"{lead.name}'s Leadership {ld} until the end of the turn")
    return ld


def end_turn(gs, player: int) -> None:
    """End of the player's turn: the boost ends."""
    boost = (gs.undivided_boost or {}).pop(str(player), None)
    if not boost:
        return
    for s in gs.ships:
        d = boost["deltas"].get(s["id"])
        if d:
            s["leadership"] = max(1, (s.get("leadership") or 0) - d)


def offer(gs, ship: Ship, label: str) -> bool:
    """Before a Leadership test or command check: may the fleet use the Mark?
    Asks GameState.undivided_hook(ship, leader, label) (a human owner, or the
    AI's rule) when it would raise this ship's Ld. True if activated."""
    if not can_use(gs, ship.player):
        return False
    lead = undivided_leader(gs, ship.player)
    if lead.leadership <= ship.leadership:
        return False
    hook = getattr(gs, "undivided_hook", None)
    want = hook(ship, lead, label) if hook else ai_wants_undivided(gs, ship, lead, label)
    if want:
        activate(gs, ship.player)
        return True
    return False


def ai_wants_undivided(gs, ship: Ship, lead: Ship, label: str) -> bool:
    """The AI's choice (judgement): use it when the fleet gains at least one
    full point of Ld on average across its ships still to act, weighted by
    the pass chance it adds to this test (2D6 <= Ld) of at least 0.25."""
    from .ai_hazards import p_sum_at_most
    gain = p_sum_at_most(2, lead.leadership) - p_sum_at_most(2, ship.leadership)
    mine = [s for s in gs.get_ships() if s.player == ship.player
            and not s.is_destroyed and not s.is_disengaged]
    avg = sum(max(0, lead.leadership - s.leadership) for s in mine) / max(1, len(mine))
    return gain >= 0.25 or (gain > 0 and avg >= 1.0)
