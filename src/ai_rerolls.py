"""AI re-roll spending by importance (owner guidance on AI play).

A fleet commander's re-rolls are few, so the AI holds them for tests that
matter. Each failed test is scored by the victory points it swings; a re-roll
is spent when the score clears a bar that rises as re-rolls run out (the last
one only on the biggest swings), and every re-roll left is spent once the
commander's ship is about to be lost (re-rolls go with it: booklet update 33).

Scores, all in expected VP (ai_hazards.ship_value / value_per_hit):
- Brace for Impact: about half the damage of the attack it faces is saved;
  more when the ship is close to crippled or destroyed;
- target priority / Lock On: what the ship's guns can take off the best
  target in reach (finishing or crippling it counts most);
- navigation: a warp rift risks the whole ship, an asteroid field D6 damage;
- disengaging: a crippled ship that gets away is worth most of its VP;
- other special orders: 5% of the ship's value;
- guided torpedoes: the salvo's expected hits on its target.
The flagship's own tests count 1.5x.
"""
import math
from typing import Optional

from .ai_hazards import p_hit, ship_value, value_per_hit
from .models import Ship

# Spend when importance (VP) >= bar[re-rolls left], the last one hardest
_BAR = {1: 45.0, 2: 25.0, 3: 15.0}


def _bar(left: int) -> float:
    return _BAR.get(left, 10.0)


def commander_in_danger(gs, player: int) -> bool:
    """The commander's ship is about to be lost: 2 hits or fewer left, or
    crippled with more enemy firepower in reach than it has hits."""
    flag = next((s for s in gs.get_ships() if s.player == player and s.is_flagship
                 and not s.is_destroyed), None)
    if flag is None:
        return False
    if flag.hits_remaining <= 2:
        return True
    if not flag.is_crippled:
        return False
    threat = 0.0
    for e in gs.get_ships():
        if e.player == player or e.is_destroyed or e.is_disengaged:
            continue
        d = math.hypot(e.x - flag.x, e.y - flag.y)
        for w in e.weapons:
            if w.get("weapon_type") in ("battery", "lance") and d <= (w.get("range_cm") or 0):
                threat += (w.get("strength") or 0) * 0.35
    return threat >= flag.hits_remaining


def firepower_outcomes(ship: Ship, gs):
    """The ship's direct fire at its best target in reach as a gamble:
    (expected VP, [(chance, VP)]): it destroys it, cripples it or neither, plus
    a little per hit (firepower_swing is the expected VP)."""
    best = (0.0, [(1.0, 0.0)])
    for e in gs.get_ships():
        if e.player == ship.player or e.is_destroyed or e.is_disengaged:
            continue
        d = math.hypot(e.x - ship.x, e.y - ship.y)
        hits = 0.0
        for w in ship.weapons:
            if w.get("weapon_type") not in ("battery", "lance"):
                continue
            if d > (w.get("range_cm") or 0):
                continue
            ph = 0.5 if w["weapon_type"] == "lance" else p_hit(e.armor_vs(ship.x, ship.y))
            hits += (w.get("strength") or 0) * ph * (0.6 if w["weapon_type"] == "battery" else 1.0)
        hits = max(0.0, hits - (0 if e.is_crippled else e.effective_shields * 0.7))
        if hits <= 0:
            continue
        v = ship_value(e, gs)
        rem = max(1, e.hits_remaining)
        p_kill = min(1.0, hits / rem)
        to_cripple = rem - e.hits_max // 2
        p_cripple = 0.0 if e.is_crippled or to_cripple <= 0 else min(1.0, hits / to_cripple)
        per_hit = hits * value_per_hit(e, gs) * 0.2
        ev = p_kill * v + p_cripple * v * 0.25 + per_hit
        if ev > best[0]:
            pc = max(0.0, min(1.0 - p_kill, p_cripple - p_kill))
            outs = [(p_kill, v + per_hit), (pc, 0.25 * v + per_hit),
                    (max(0.0, 1.0 - p_kill - pc), per_hit)]
            best = (ev, outs)
    return best


def firepower_swing(ship: Ship, gs) -> float:
    """Expected VP the ship's direct fire can take off its best target in reach
    (P(kill) x value + P(cripple) x a quarter of it)."""
    return firepower_outcomes(ship, gs)[0]


def importance(ship: Ship, label: str, gs, context: Optional[dict] = None) -> float:
    """VP a re-roll of this failed test is likely to swing."""
    label = (label or "").lower()
    context = context or {}
    v = ship_value(ship, gs)
    vph = value_per_hit(ship, gs)
    if "brace" in label:
        expected = context.get("expected_hits", 2.0)
        saved = expected * 0.5
        score = saved * vph
        if saved >= ship.hits_remaining * 0.5 or ship.hits_remaining <= 3:
            score += v * 0.3                      # it may be the difference between losing it
    elif "warp rift" in label:
        score = v
    elif "asteroid" in label:
        score = max(0.0, 3.5 - ship.effective_shields) * vph
    elif "disengage" in label:
        score = v * (0.75 if ship.is_crippled else 0.4)
    elif "target priority" in label or "lock_on" in label or "lock on" in label:
        score = firepower_swing(ship, gs) * (0.5 if "lock" in label else 0.7)
    elif "guided" in label:
        score = context.get("salvo_hits", 2.0) * context.get("target_vph", 20.0)
    else:                                          # other special orders
        score = v * 0.05
    if ship.is_flagship:
        score *= 1.5
    return score


def should_reroll(ship: Ship, label: str, gs, left: int, context: Optional[dict] = None) -> bool:
    """Spend one of `left` re-rolls on this failed test?"""
    if left <= 0:
        return False
    if commander_in_danger(gs, ship.player):
        return True                                # use them before they're lost
    bar = _bar(left)
    limit = getattr(gs, "turn_limit", None)
    if limit and gs.turn_number >= limit:
        # The last game turn (owner: play to the turn limit): re-rolls left
        # over are worth nothing after it, so the bars that save them for
        # later turns drop to the lowest (some tests may still come this turn)
        bar = min(bar, _bar(len(_BAR) + 1))
    return importance(ship, label, gs, context) >= bar
