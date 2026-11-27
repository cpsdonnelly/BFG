"""Strategy candidates for every ship (owner, To do 34: "a list of strategies
all ships try out and then evaluate").

A strategy is a plan over a few game turns with a destination relative to an
enemy (or a friend, or the table): flank left / right into its rear arc, hold
the range band where our guns beat its, kite out of its reach, close in, come
prow-on, screen a friend, or run for the nearest edge when crippled. Each one
gives this turn's first move towards its waypoint (`AIPlayer._head_for`); the
expert search (`lookahead_ai`) then follows the plan for its turns in the sim
(`plan_waypoint`, the target's own moves and the enemy's replies included) and
the strategy is judged by where that leaves the game, like any other line. So a
first move that looks poor on its own (swinging wide now to be behind the enemy
next turn) is tried and valued by what it leads to. Candidates propose, the
search's values decide (owner: not hard rules, it depends on the matchup).

Waypoints:
- "rel_heading": `dist` from the target at `angle` from its heading (a flank:
  its rear arc, 180 +- 45 degrees), recomputed from where the target is each
  turn;
- "rel_bearing": `dist` from the target along the bearing from it to the ship
  (hold a range band, kite, close in);
- "fixed": a point (a table edge, a friend's screen).
"""
import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

PLAN_TURNS = 2          # game turns a strategy is followed in the search (judgement)


@dataclass
class Strategy:
    name: str
    kind: str                 # "rel_heading", "rel_bearing" or "fixed"
    target_id: str = ""
    angle: float = 0.0        # rel_heading: degrees from the target's heading
    dist: float = 0.0         # from the target
    x: float = 0.0            # fixed
    y: float = 0.0
    turns: int = PLAN_TURNS


def plan_waypoint(plan: Strategy, ship, ships) -> Optional[Tuple[float, float]]:
    """Where `ship` should head this turn under `plan`, from the ships as they
    stand (`ships`: real or sim ships with x, y, heading, id). None when the
    target is gone."""
    if plan.kind == "fixed":
        return plan.x, plan.y
    t = next((s for s in ships if getattr(s, "id", None) == plan.target_id), None)
    if t is None or not _alive(t):
        return None
    if plan.kind == "rel_heading":
        a = math.radians((t.heading or 0) + plan.angle)
    else:
        a = math.atan2(ship.y - t.y, ship.x - t.x)
    return t.x + plan.dist * math.cos(a), t.y + plan.dist * math.sin(a)


def _alive(s) -> bool:
    alive = getattr(s, "is_alive", None)
    if alive is not None:
        return bool(alive)
    return not (s.is_destroyed or s.is_disengaged)


def _gun_reach(ship) -> float:
    """The longest battery / lance range the ship carries (0 without guns)."""
    return max((w.get("range_cm") or 0 for w in ship.weapons
                if w.get("weapon_type") in ("battery", "lance")), default=0.0)


def strategies_for(ai, ship, enemy) -> List[Strategy]:
    """The strategies this ship's weapons, speed and state allow against
    `enemy` (the target its move plans against): flank left / right (any ship
    with guns or ordnance: get behind it at the range band, or 15cm without
    one), hold the band, kite (only with a range-and-speed edge,
    `AIPlayer.range_speed_edge`), close in (boarding / ramming on, or our best
    bracket under 15cm), screen the commander's ship or a carrier (escorts),
    and the nearest table edge for a crippled ship."""
    out: List[Strategy] = []
    if enemy is None:
        return out
    reach = _gun_reach(ship)
    band = None
    try:
        band = ai._range_band(ship, enemy)
    except Exception:
        band = None
    behind = band if band else (min(reach * 0.75, 25.0) if reach else 15.0)
    behind = max(10.0, min(30.0, behind))
    for side, sign in (("flank_left", 1.0), ("flank_right", -1.0)):
        out.append(Strategy(side, "rel_heading", enemy.id, 180.0 + sign * 45.0, behind))
    if band:
        out.append(Strategy("hold_band", "rel_bearing", enemy.id, dist=band))
    try:
        edge = ai.range_speed_edge(ship, enemy)
    except Exception:
        edge = False
    if edge:
        e_reach = _gun_reach(enemy) + (enemy.speed or 0)
        if reach > e_reach:
            out.append(Strategy("kite", "rel_bearing", enemy.id, dist=(e_reach + reach) / 2.0))
    gs = ai.gs
    if (getattr(gs, "rule_boarding", False) or getattr(gs, "rule_ramming", False)
            or (band is not None and band < 15.0)):
        out.append(Strategy("close", "rel_bearing", enemy.id, dist=ship.base_radius
                            + enemy.base_radius))
    if ship.ship_type == "escort":
        friend = next((f for f in gs.get_ships() if f.player == ship.player and f.id != ship.id
                       and not f.is_destroyed and not f.is_disengaged
                       and (f.is_flagship or any(w.get("weapon_type") == "launch_bay"
                                                 for w in f.weapons))), None)
        if friend is not None:
            a = math.atan2(enemy.y - friend.y, enemy.x - friend.x)
            out.append(Strategy("screen", "fixed", x=friend.x + 8.0 * math.cos(a),
                                y=friend.y + 8.0 * math.sin(a)))
    if ship.is_crippled:
        w, h = getattr(gs, "table_width", 120.0), getattr(gs, "table_height", 90.0)
        edges = [(0.0, ship.y), (w, ship.y), (ship.x, 0.0), (ship.x, h)]
        ex, ey = min(edges, key=lambda p: math.hypot(p[0] - ship.x, p[1] - ship.y))
        out.append(Strategy("to_edge", "fixed", x=ex, y=ey))
    return out


def head_for_move(ship, gx: float, gy: float, speed: float, turn_angle: float,
                  turn_dist: float) -> Tuple[float, float]:
    """The sim's move towards (gx, gy): straight for the turning distance, a turn
    towards it clamped to the turn angle, then on for what is left (full speed
    unless the point is nearer). Returns (turn_deg, dist)."""
    r = math.radians
    p = min(turn_dist, speed)
    px = ship.x + p * math.cos(r(ship.heading))
    py = ship.y + p * math.sin(r(ship.heading))
    want = math.degrees(math.atan2(gy - py, gx - px))
    turn = (want - ship.heading + 180.0) % 360.0 - 180.0
    turn = max(-turn_angle, min(turn_angle, turn))
    rest = math.hypot(gx - px, gy - py)
    dist = max(min(speed, p + rest), min(speed, turn_dist + 1.0) if abs(turn) > 0.5 else 1.0)
    return turn, dist
