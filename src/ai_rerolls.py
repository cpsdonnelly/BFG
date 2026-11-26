"""AI re-roll spending by importance (owner guidance on AI play).

A fleet commander's re-rolls are few, so the AI holds them for tests that
matter. Each failed test is scored by the victory points it swings; a re-roll
is spent when the score clears a bar that rises as re-rolls run out (the last
one only on the biggest swings), and every re-roll left is spent once the
commander's ship is about to be lost (re-rolls go with it: booklet update 33).

Scores, all in expected VP: what passing the test gains over failing it,
computed for each test (see `importance`; owner: no rules of thumb).
"""
import math
from typing import Optional


from .models import Ship

# Spend when importance (VP) >= bar[re-rolls left], the last one hardest
_BAR = {1: 45.0, 2: 25.0, 3: 15.0}


BAR_REFERENCE_POINTS = 1500.0   # the fleet size the bars were set for (judgement)


def _bar(left: int, gs=None) -> float:
    """The importance a failed test needs before spending one of `left`
    re-rolls, scale-free (To do 11 f): the VP bars set for a 1500pt game,
    scaled by the points on the table (both fleets, halved: one fleet's
    worth), never below a quarter of them."""
    base = _BAR.get(left, 10.0)
    if gs is None:
        return base
    pts = sum(s.points_value or 0 for s in gs.get_ships()) / 2.0
    if pts <= 0:
        return base
    return base * max(0.25, pts / BAR_REFERENCE_POINTS)


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
                from .ai_hazards import BATTERY_HITS_PER_FP, lance_p
                threat += (w.get("strength") or 0) * (lance_p(w) if w.get("weapon_type") == "lance"
                                                      else BATTERY_HITS_PER_FP)
    return threat >= flag.hits_remaining


def firepower_outcomes(ship: Ship, gs, halve: bool = False):
    """The ship's direct fire at its best target next shooting phase as a
    gamble: (expected VP, [(chance, VP)]), exact (owner: the real Gunnery
    table, not a rule of thumb): every battery / lance mount that bears on
    the target (`ai_hazards._mount_bears`: in arc and reach after its move, or
    after a turn at 0.75), each by its exact hit distribution
    (`weapon_hit_pmf`: the Gunnery table's dice, each faction's lance rules,
    saves), convolved and taken past the target's shields
    (`volley_hull_pmf`), each count of hull hits valued by `hits_vp` (destroyed,
    crippled, its fire removed). `halve`: every weapon at half strength (the
    s.7 orders that halve batteries and lances), for an order's cost."""
    from .ai_hazards import _mount_bears, volley_hull_pmf, hits_vp
    from .geometry import current_shields
    best = (0.0, [(1.0, 0.0)])
    bm = gs.get_blast_markers()
    for e in gs.get_ships():
        if (e.player == ship.player or e.is_destroyed or e.is_disengaged
                or e.status in ("drifting_hulk", "burning_hulk")):
            continue
        mounts = []
        for w in ship.weapons:
            if w.get("weapon_type") not in ("battery", "lance"):
                continue
            wt = _mount_bears(ship, w, e)
            if wt:
                mounts.append((ship, w, float(wt), halve))
        if not mounts:
            continue
        pmf = volley_hull_pmf(mounts, e, current_shields(e, bm))
        outs = [(q, hits_vp(e, gs, k)) for k, q in enumerate(pmf) if q > 1e-9]
        ev = sum(q * v for q, v in outs)
        if ev > best[0]:
            best = (ev, outs)
    return best


def firepower_swing(ship: Ship, gs) -> float:
    """Expected VP the ship's direct fire can take off its best target in reach
    (P(kill) x value + P(cripple) x a quarter of it)."""
    return firepower_outcomes(ship, gs)[0]


def _closest_target(ship: Ship, gs):
    """The enemy target priority forces (s.13): the closest enemy ship."""
    es = [e for e in gs.get_ships() if e.player != ship.player and not e.is_destroyed
          and not e.is_disengaged and e.status == "active"]
    return min(es, key=lambda e: (math.hypot(e.x - ship.x, e.y - ship.y), e.id), default=None)


def _target_ev(ship: Ship, gs, e: Ship) -> float:
    """Expected VP of the ship's guns at one target (firepower_outcomes' terms)."""
    from .ai_hazards import _mount_bears, volley_hull_pmf, hits_vp
    from .geometry import current_shields
    mounts = [(ship, w, 1.0, False) for w in ship.weapons
              if w.get("weapon_type") in ("battery", "lance") and _mount_bears(ship, w, e)]
    if not mounts:
        return 0.0
    pmf = volley_hull_pmf(mounts, e, current_shields(e, gs.get_blast_markers()))
    return sum(q * hits_vp(e, gs, k) for k, q in enumerate(pmf))


def _guided_value(marker, gs) -> float:
    """What passing a guided salvo's Leadership test is worth: its best plan
    turning now less its best plan held straight this move (approach_plan,
    each later turn at the guided test's odds), over the enemy ships."""
    from .ai_hazards import approach_plan, guided_turn_chance
    p_turn = guided_turn_chance(marker, gs)
    best = 0.0
    for e in gs.get_ships():
        if e.player == marker.owner_player or e.is_destroyed or e.is_disengaged:
            continue
        kw = dict(arc_half=45.0, p_turn=p_turn, our_phase=gs.active_player == marker.owner_player)
        on = approach_plan(marker.x, marker.y, marker.heading, marker.speed or 30, e, gs,
                           marker.owner_player, marker.strength, turn_now=True, **kw)
        off = approach_plan(marker.x, marker.y, marker.heading, marker.speed or 30, e, gs,
                            marker.owner_player, marker.strength, turn_now=False, **kw)
        gain = (on or {}).get("value", 0.0) - (off or {}).get("value", 0.0)
        best = max(best, gain)
    return best


def importance(ship: Ship, label: str, gs, context: Optional[dict] = None) -> float:
    """VP a passed re-roll of this failed test is worth (owner: computed, not
    rules of thumb): what passing gains over failing, for each test.
    - Brace for Impact: the brace's own price given it passes
      (`ai_player.brace_value`: the 4+ saves on the hits it faces this turn
      against half its fire, by certainty equivalent), on the attack in hand
      (`expected_hits`) or the enemy's next turn of fire on it;
    - warp rift navigation: the ship lost (`ai_hazards.lost_ship_vp`);
    - asteroid navigation: the D6 damage less shields, each count valued
      exactly (`hits_vp`);
    - disengaging: `disengage_gain` at a certain pass with no guns given up
      (a failed test forbids firing too);
    - target priority: its guns at the best target less at the closest one,
      each by its exact hit distribution (`firepower_outcomes`' terms);
    - special orders: the order's value (`order_vp`, from the AI's order plan;
      otherwise the AI's own `_order_value`);
    - guided torpedoes: the salvo's plan turning now less held straight.
    Plus the later orders a failed movement-phase check would block (s.2,
    `blocked_orders_vp`)."""
    from .ai_hazards import lost_ship_vp, hits_vp, disengage_gain
    label = (label or "").lower()
    context = context or {}
    if "brace" in label:
        from .ai_hazards import incoming_hits
        from .ai_player import brace_value
        hits = context.get("expected_hits")
        if hits is None:
            hits = incoming_hits(ship, gs)
        score = max(0.0, brace_value(gs, ship, hits, context.get("attacker"), p_pass=1.0))
    elif "warp rift" in label:
        score = lost_ship_vp(ship, gs)
    elif "asteroid" in label:
        from .geometry import current_shields
        sh = current_shields(ship, gs.get_blast_markers())
        score = sum(hits_vp(ship, gs, max(0, r - sh)) for r in range(1, 7)) / 6.0
    elif "disengage" in label:
        score = max(0.0, disengage_gain(ship, gs, 12, 0.0))
    elif "target priority" in label:
        closest = _closest_target(ship, gs)
        best = firepower_outcomes(ship, gs)[0]
        score = max(0.0, best - (_target_ev(ship, gs, closest) if closest else 0.0))
    elif "guided" in label:
        m = context.get("marker")
        score = _guided_value(m, gs) if m is not None else context.get("salvo_vp", 0.0)
    else:                                          # special orders
        score = context.get("order_vp")
        if score is None:
            score = _order_vp(ship, label, gs, context.get("tc"))
    # To do 10 d: a failed movement-phase command check also ends every later
    # check this turn (s.2), so its re-roll is worth the orders it unblocks
    score += context.get("blocked_orders_vp", 0.0)
    return score


def _order_vp(ship: Ship, label: str, gs, tc=None) -> float:
    """The order's gain if it passes, by the AI's own valuation
    (`AIPlayer._order_value`), for a test with no order plan at hand (a
    human's prompt)."""
    from .models import SpecialOrder
    order = next((o.value for o in SpecialOrder if o.value == label
                  or o.value.replace("_", " ") == label), None)
    if order is None:
        return 0.0
    if tc is None:
        return 0.0
    from .ai_player import AIPlayer
    from .dice import DiceRoller
    ai = AIPlayer(ship.player, tc, gs, DiceRoller(mode="auto"))
    return max(0.0, ai._order_value(ship, order)[1])


def spend_bar(ship: Ship, gs, left: int) -> float:
    """The importance a failed test needs before one of `left` re-rolls is
    spent on it (`should_reroll`), which is also what the AI holds a re-roll
    to be worth when it keeps one for later: 0 when the commander's ship is
    about to be lost (the re-rolls go with it), and on the last game turn the
    lowest bar (left-over re-rolls are worth nothing after it)."""
    if commander_in_danger(gs, ship.player):
        return 0.0                                 # use them before they're lost
    bar = _bar(left, gs)
    limit = getattr(gs, "turn_limit", None)
    if limit and gs.turn_number >= limit:
        # The last game turn (owner: play to the turn limit): re-rolls left
        # over are worth nothing after it, so the bars that save them for
        # later turns drop to the lowest (some tests may still come this turn)
        bar = min(bar, _bar(len(_BAR) + 1, gs))
    return bar


def should_reroll(ship: Ship, label: str, gs, left: int, context: Optional[dict] = None) -> bool:
    """Spend one of `left` re-rolls on this failed test?"""
    if left <= 0:
        return False
    bar = spend_bar(ship, gs, left)
    if bar <= 0:
        return True
    return importance(ship, label, gs, context) >= bar


def rerolls_left(gs, ship: Ship) -> int:
    """Re-rolls this ship could use on a failed test now, by the turn
    controller's own rule (`TurnController.get_fleet_rerolls`: a secondary
    commander's own, the fleet commander's unless a radiation burst or
    Signaling Problems blocks them, Demiurg War Host re-rolls), read from the
    game state alone."""
    from .turn_controller import TurnController
    reader = TurnController.__new__(TurnController)   # no __init__: reads gs only
    reader.gs = gs
    try:
        return reader.get_fleet_rerolls(ship.player, ship)
    except Exception:
        return 0


def with_reroll(ship: Ship, gs, p: float, gain: float,
                extra: float = 0.0) -> float:
    """Expected VP of trying a test worth `gain` if passed, at pass chance
    `p`, counting a commander re-roll (owner, To do 33): a failed test is
    re-rolled when the AI would spend one on it (`should_reroll`: `gain` plus
    `extra`, the later orders a failure would block, against the bar), which
    passes at `p` again (one re-roll per test, s.5) and unblocks the later
    orders too, so p x g + (1 - p) x (p x (g + extra) - the re-roll's worth),
    the re-roll's worth being its bar (what the AI holds a kept re-roll to be
    worth); never less than without it."""
    base = p * gain
    if gain <= 0 or p <= 0.0 or p >= 1.0:
        return base
    left = rerolls_left(gs, ship)
    if left <= 0:
        return base
    bar = spend_bar(ship, gs, left)
    if gain + extra < bar:
        return base                     # the AI wouldn't spend one on it
    return base + (1.0 - p) * max(0.0, p * (gain + extra) - bar)
