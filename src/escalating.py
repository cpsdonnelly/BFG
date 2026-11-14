"""Escalating Engagement (XR p.107): divisions behind contact markers.

Each player splits the fleet into up to five divisions, one per contact
marker. One division per player starts on the table, deployed within 10cm of
its marker; in the end phase of each of its turns a player puts another
marker on a randomly rolled table edge, and at the start of each of its turns
it rolls for every marker on an edge: on a success the division moves on
within 10cm of the marker, otherwise the marker may slide along the edge.

State in `gs.scenario_state`:
  "divisions": {"1": [[unit keys], ...], "2": [...]}
  "start": {"1": [x, y], "2": [x, y]}      the starting markers
  "start_div": {"1": i, "2": j}
  "waiting": {"1": [i, ...], "2": [...]}   divisions not yet on an edge
  "edge_markers": [{"player": p, "div": i, "edge": e, "x": x, "y": y}]
Reserve ships are held off the table as in the other reinforcement scenarios
(`scenarios._to_reserve`).
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

MAX_DIVISIONS = 5
START_EDGE_GAP = 30.0       # starting markers at least 30cm from every edge
START_MARKER_GAP = 60.0     # ... and 60cm from the enemy's
DEPLOY_RADIUS = 10.0        # divisions deploy / arrive within 10cm of their marker
EDGE_ENEMY_GAP = 60.0       # an edge marker not within 60cm of enemy ships
EDGE_FRIEND_RANGE = 30.0    # friendly ships within 30cm of the edge pull the marker
ARRIVAL_FRIEND_BONUS = 2    # +2 with friendly ships within 30cm of the marker
EDGE_BY_D6 = {1: "left", 2: "top", 3: "top", 4: "bottom", 5: "bottom", 6: "right"}


def active(gs) -> bool:
    return getattr(gs, "scenario_mode", "") == "escalating_engagement"


def _key(sd: Dict) -> str:
    return sd["squadron_id"] if (sd.get("ship_type") == "escort" and sd.get("squadron_id")) \
        else sd["id"]


def _units(gs, player: int) -> Dict[str, int]:
    units: Dict[str, int] = {}
    for sd in gs.ships:
        if sd["player"] == player and "immobile" not in sd.get("special_rules", []):
            units[_key(sd)] = units.get(_key(sd), 0) + sd.get("points_value", 0)
    return units


def auto_divisions(gs, player: int) -> List[List[str]]:
    """Split a fleet into divisions (judgement): the units dearest first,
    each to the division with the fewest points so far, as many divisions as
    there are units up to five (each division needs a ship or squadron)."""
    units = _units(gs, player)
    n = min(MAX_DIVISIONS, len(units))
    divs: List[List[str]] = [[] for _ in range(n)]
    pts = [0] * n
    for k, v in sorted(units.items(), key=lambda kv: (-kv[1], kv[0])):
        i = pts.index(min(pts))
        divs[i].append(k)
        pts[i] += v
    return divs


def _pick(dice, n: int, label: str) -> int:
    """A random division index 0..n-1 by D6 (re-rolled above n)."""
    if n <= 1:
        return 0
    while True:
        r = dice.roll_d6(1, label)[0]
        if r <= n:
            return r - 1


def _start_spots(gs, player: int, other: Optional[Tuple[float, float]]):
    """Legal starting-marker spots (a 5cm grid) for a player: 30cm from every
    edge and 60cm from the enemy's marker. Player 1 prefers the lower half,
    player 2 the upper (judgement: the fleets arrive from opposite sides)."""
    w, h = gs.table_width, gs.table_height
    spots = []
    y = START_EDGE_GAP
    while y <= h - START_EDGE_GAP + 1e-9:
        x = START_EDGE_GAP
        while x <= w - START_EDGE_GAP + 1e-9:
            if other is None or math.hypot(x - other[0], y - other[1]) >= START_MARKER_GAP:
                spots.append((x, y))
            x += 5.0
        y += 5.0
    if not spots:
        return []
    want = [(x, y) for x, y in spots if (y <= h / 2.0) == (player == 1)]
    return want or spots


def setup(gs, dice) -> None:
    """Before deployment: divisions (kept if already chosen), each player's
    random starting division, the roll-off for who places its marker first
    (the winner places second, judgement: it sees the other marker) and both
    markers (a D6 picks a spot along the player's half, reading: the placing
    is automatic for now); the other divisions wait off the table."""
    from .scenarios import _to_reserve
    st = dict(gs.scenario_state or {})
    divs = st.get("divisions") or {str(p): auto_divisions(gs, p) for p in (1, 2)}
    start_div, start = {}, {}
    for p in (1, 2):
        start_div[str(p)] = _pick(dice, len(divs[str(p)]),
                                  f"Escalating Engagement: player {p}'s starting division")
    a = dice.roll_d6(1, "Escalating Engagement: player 1 marker roll-off")[0]
    b = dice.roll_d6(1, "Escalating Engagement: player 2 marker roll-off")[0]
    while a == b:
        a = dice.roll_d6(1, "Escalating Engagement: player 1 marker roll-off")[0]
        b = dice.roll_d6(1, "Escalating Engagement: player 2 marker roll-off")[0]
    second = 1 if a > b else 2
    order = (3 - second, second)
    for p in order:
        other = start.get(str(3 - p))
        spots = _start_spots(gs, p, tuple(other) if other else None)
        if not spots:
            spots = [(gs.table_width / 2.0, gs.table_height / 2.0)]
        xs = sorted({x for x, _ in spots})
        r = dice.roll_d6(1, f"Escalating Engagement: player {p}'s marker spot")[0]
        x_pick = xs[min(len(xs) - 1, int((r - 0.5) / 6.0 * len(xs)))]
        col = [s for s in spots if s[0] == x_pick]
        # the middle of the player's own band at that x
        spot = col[len(col) // 2]
        start[str(p)] = [round(spot[0], 3), round(spot[1], 3)]
    waiting = {}
    for p in (1, 2):
        keep = set(divs[str(p)][start_div[str(p)]])
        for sd in gs.ships:
            if sd["player"] == p and _key(sd) not in keep \
                    and "immobile" not in sd.get("special_rules", []):
                _to_reserve(sd)
        waiting[str(p)] = [i for i in range(len(divs[str(p)])) if i != start_div[str(p)]]
    st.update({"divisions": divs, "start": start, "start_div": start_div,
               "waiting": waiting, "edge_markers": [], "first_marker": order[0]})
    gs.scenario_state = st
    gs.add_log(f"[Escalating Engagement] starting markers: player 1 at "
               f"({start['1'][0]:g}, {start['1'][1]:g}), player 2 at "
               f"({start['2'][0]:g}, {start['2'][1]:g}); player {order[0]} placed first")


def start_marker(gs, player: int) -> Optional[Tuple[float, float]]:
    m = (gs.scenario_state or {}).get("start", {}).get(str(player))
    return (m[0], m[1]) if m else None


def placement_errors(gs, group, positions) -> List[str]:
    """The starting division deploys within 10cm of its marker (reading: the
    ship's centre)."""
    if not group:
        return []
    m = start_marker(gs, group[0].player)
    if m is None:
        return []
    return [f"Escalating Engagement: {s.name} must be within {DEPLOY_RADIUS:g}cm of its "
            f"contact marker" for s, (x, y) in zip(group, positions)
            if math.hypot(x - m[0], y - m[1]) > DEPLOY_RADIUS + 1e-6]


def zone_rects(gs) -> Dict[int, List[Tuple[float, float, float, float]]]:
    """Each player's deployment rect (left, right, top, bottom distances) round
    its starting marker; placement_errors keeps ships within the 10cm circle."""
    w, h = gs.table_width, gs.table_height
    out = {}
    for p in (1, 2):
        m = start_marker(gs, p)
        if m is None:
            return {}
        x0, x1 = max(0.0, m[0] - DEPLOY_RADIUS), min(w, m[0] + DEPLOY_RADIUS)
        y0, y1 = max(0.0, m[1] - DEPLOY_RADIUS), min(h, m[1] + DEPLOY_RADIUS)
        out[p] = [(x0, w - x1, h - y1, y0)]
    return out


def auto_positions(gs, group, placed) -> Optional[List[Tuple[float, float]]]:
    """Place a starting unit round its marker: rings of 4cm spacing."""
    if not group:
        return None
    m = start_marker(gs, group[0].player)
    if m is None:
        return None
    taken = [(s.x, s.y) for s in placed]
    out: List[Tuple[float, float]] = []
    for ring in (0.0, 4.0, 8.0):
        n = 1 if ring == 0 else int(2 * math.pi * ring / 4.0)
        for k in range(n):
            a = 2 * math.pi * k / n
            pt = (m[0] + ring * math.cos(a), m[1] + ring * math.sin(a))
            if all(math.hypot(pt[0] - x, pt[1] - y) >= 3.9 for x, y in taken + out):
                out.append(pt)
                if len(out) == len(group):
                    return out
    return out + [m] * (len(group) - len(out))


# --- edge markers -----------------------------------------------------------------

def _edge_point(gs, edge: str, t: float) -> Tuple[float, float]:
    w, h = gs.table_width, gs.table_height
    return {"left": (0.0, t), "right": (w, t), "top": (t, h), "bottom": (t, 0.0)}[edge]


def _edge_len(gs, edge: str) -> float:
    return gs.table_height if edge in ("left", "right") else gs.table_width


def _dist_to_edge(gs, edge: str, x: float, y: float) -> float:
    return {"left": x, "right": gs.table_width - x, "bottom": y,
            "top": gs.table_height - y}[edge]


def _on_table(gs, player: Optional[int] = None, enemy_of: Optional[int] = None):
    return [s for s in gs.get_ships() if not s.is_destroyed and not s.is_disengaged
            and (player is None or s.player == player)
            and (enemy_of is None or s.player != enemy_of)]


def edge_spot(gs, player: int, edge: str) -> Optional[Tuple[float, float]]:
    """A legal spot on `edge` for a new contact marker: not within 60cm of any
    enemy ship; with friendly ships within 30cm of that edge, within 30cm of
    at least one of them. Among legal spots (every 5cm), the one nearest our
    ships (judgement), else the middle of the edge. None when no spot is legal
    (reading: the marker waits for the next end phase)."""
    enemies = _on_table(gs, enemy_of=player)
    friends = _on_table(gs, player=player)
    near = [s for s in friends if _dist_to_edge(gs, edge, s.x, s.y) <= EDGE_FRIEND_RANGE]
    length = _edge_len(gs, edge)
    legal = []
    t = 0.0
    while t <= length + 1e-9:
        x, y = _edge_point(gs, edge, t)
        if all(math.hypot(x - e.x, y - e.y) > EDGE_ENEMY_GAP for e in enemies) and (
                not near or any(math.hypot(x - f.x, y - f.y) <= EDGE_FRIEND_RANGE
                                for f in near)):
            legal.append((x, y))
        t += 5.0
    if not legal:
        return None
    if friends:
        cx = sum(s.x for s in friends) / len(friends)
        cy = sum(s.y for s in friends) / len(friends)
        return min(legal, key=lambda p: math.hypot(p[0] - cx, p[1] - cy))
    mid = _edge_point(gs, edge, length / 2.0)
    return min(legal, key=lambda p: math.hypot(p[0] - mid[0], p[1] - mid[1]))


def end_of_turn(gs, player: int, dice) -> None:
    """In the end phase of each of its turns a player places another contact
    marker, chosen at random, on a randomly rolled table edge (D6: 1 left,
    2-3 top, 4-5 bottom, 6 right, as the diagram draws them)."""
    if not active(gs) or dice is None:
        return
    st = dict(gs.scenario_state or {})
    waiting = dict(st.get("waiting", {}))
    left = list(waiting.get(str(player), []))
    if not left:
        return
    i = left[_pick(dice, len(left), f"Escalating Engagement: player {player}'s next marker")]
    edge = EDGE_BY_D6[dice.roll_d6(1, f"Escalating Engagement: player {player}'s marker "
                                      f"edge (1 left, 2-3 top, 4-5 bottom, 6 right)")[0]]
    spot = edge_spot(gs, player, edge)
    if spot is None:
        gs.add_log(f"[Escalating Engagement] player {player} can't place a contact marker on "
                   f"the {edge} edge this turn")
        return
    left.remove(i)
    waiting[str(player)] = left
    markers = list(st.get("edge_markers", []))
    markers.append({"player": player, "div": i, "edge": edge,
                    "x": round(spot[0], 3), "y": round(spot[1], 3)})
    st["waiting"], st["edge_markers"] = waiting, markers
    gs.scenario_state = st
    gs.add_log(f"[Escalating Engagement] player {player} places a contact marker on the "
               f"{edge} edge at ({spot[0]:g}, {spot[1]:g})")


def division_ships(gs, player: int, div: int):
    keys = set((gs.scenario_state or {}).get("divisions", {}).get(str(player), [])[div])
    return [s for s in gs.get_ships() if s.player == player and _key_ship(s) in keys
            and not s.is_destroyed]


def _key_ship(s) -> str:
    return s.squadron_id if (s.ship_type == "escort" and s.squadron_id) else s.id


def arrival_need(ships) -> int:
    slowest = min((s.speed for s in ships), default=0)
    return 5 if slowest <= 20 else (4 if slowest < 30 else 3)


def place_division(gs, ships, edge: str, x: float, y: float) -> None:
    """The division moves onto the table from the marker's edge within 10cm of
    the marker (reading: as the other reinforcements, it is placed touching
    the edge, facing in, and moves normally that turn); rows step inwards
    when 4cm spacing along the 20cm of edge runs out."""
    along = y if edge in ("left", "right") else x
    length = _edge_len(gs, edge)
    lo, hi = max(2.0, along - DEPLOY_RADIUS), min(length - 2.0, along + DEPLOY_RADIUS)
    per_row = max(1, int((hi - lo) // 4.0) + 1)
    facing = {"left": 0.0, "right": 180.0, "top": 270.0, "bottom": 90.0}[edge]
    w, h = gs.table_width, gs.table_height
    for n, s in enumerate(ships):
        row, col = divmod(n, per_row)
        t = lo + 4.0 * col
        depth = s.base_radius + 0.1 + 4.0 * row
        px, py = {"left": (depth, t), "right": (w - depth, t),
                  "bottom": (t, depth), "top": (t, h - depth)}[edge]
        s.x, s.y, s.heading = px, py, facing
        s.status = "active"
        s.is_disengaged = False
        gs.update_ship(s)


def turn_start(gs, player: int, dice) -> None:
    """At the start of a player's turn: a D6 for each of its markers on an
    edge (5+ / 4+ / 3+ by the division's slowest speed, +2 with friendly ships
    within 30cm of the marker; the player always tries, judgement). Arrived
    divisions come on and the marker is removed; otherwise the marker may move
    along its edge up to the slowest speed (towards our ships, judgement)."""
    if not active(gs) or dice is None:
        return
    st = dict(gs.scenario_state or {})
    keep = []
    for m in st.get("edge_markers", []):
        if m["player"] != player:
            keep.append(m)
            continue
        ships = division_ships(gs, player, m["div"])
        if not ships:
            continue
        need = arrival_need(ships)
        friends = _on_table(gs, player=player)
        bonus = ARRIVAL_FRIEND_BONUS if any(
            math.hypot(f.x - m["x"], f.y - m["y"]) <= EDGE_FRIEND_RANGE for f in friends) else 0
        r = dice.roll_d6(1, f"Escalating Engagement: division arrives on {need}+"
                            f"{' (+2)' if bonus else ''}")[0]
        if r + bonus >= need:
            place_division(gs, ships, m["edge"], m["x"], m["y"])
            gs.add_log(f"[Escalating Engagement] arriving from the {m['edge']} edge: "
                       f"{', '.join(s.name for s in ships)}")
            continue
        slide = min(s.speed for s in ships)
        if friends:
            cx = sum(s.x for s in friends) / len(friends)
            cy = sum(s.y for s in friends) / len(friends)
            target = cy if m["edge"] in ("left", "right") else cx
            cur = m["y"] if m["edge"] in ("left", "right") else m["x"]
            new = cur + max(-slide, min(slide, target - cur))
            new = max(0.0, min(_edge_len(gs, m["edge"]), new))
            m = dict(m)
            if m["edge"] in ("left", "right"):
                m["y"] = round(new, 3)
            else:
                m["x"] = round(new, 3)
        gs.add_log(f"[Escalating Engagement] player {player}'s division doesn't arrive "
                   f"(rolled {r})")
        keep.append(m)
    st["edge_markers"] = keep
    gs.scenario_state = st
