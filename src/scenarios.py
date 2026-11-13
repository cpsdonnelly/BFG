"""Booklet scenarios (bfgxr/rules/12_scenarios.md; CLAUDE.md To do 7), pure
logic. First slice: the scenario registry (set-up zones, first turn, game end,
victory) with the matched-play Confrontation and Domination (XR p.117,
p.125-126). The older generic modes (kill the admiral, destroy / protect a
ship, capture the artefact) stay in `scenario.py`; `GameState.scenario_mode`
names either kind.

Coordinates: the engine's frame (x right, y up, player 1's default edge at
y = 0). The booklet's deployment diagrams are drawn with their top edge at
y = table height. Domination's diagrams are for a 180 x 120cm table; every
position here is measured from a table edge or the centre, as the diagrams
dimension it, so a different table size keeps the same distances.

Readings to confirm with the owner are marked "reading"."""
from typing import Dict, List, Optional, Tuple

from .deployment import DeploymentZone

CONTROL_RANGE = 15.0        # Domination: within 15cm of the marker centre (to the stem)
DOMINATION_TARGET = 10      # ...the game ends when a player has 10 objective points

# key -> booklet facts the engine plays
SCENARIOS: Dict[str, Dict] = {
    "confrontation": {
        "name": "Confrontation (XR p.117)",
        "first_turn": "attacker",
        "end": "fleet_gone",            # one fleet disengages or is destroyed
        "victory": "vp",
    },
    "domination": {
        "name": "Domination (XR p.125-126)",
        "first_turn": "attacker",
        "end": "fleet_gone_or_points",
        "victory": "objective_points",
    },
}


def is_booklet_scenario(gs) -> bool:
    return getattr(gs, "scenario_mode", "standard") in SCENARIOS


def first_player(gs) -> Optional[int]:
    """The player the scenario says takes the first turn (None: roll off, s.2)."""
    sc = SCENARIOS.get(getattr(gs, "scenario_mode", ""))
    if sc and sc.get("first_turn") == "attacker":
        return gs.scenario_attacker
    return None


# --- Deployment zones and objective markers -------------------------------------

def _rect(player, w, h, left, right, top, bottom, label) -> DeploymentZone:
    """A zone given as distances in from the left / right edges and down from
    the top edge (diagram frame); converted to engine x / y."""
    return DeploymentZone(player=player, x_min=left, x_max=w - right,
                          y_min=bottom, y_max=h - top, label=label)


def _domination_layout(n: int, w: float, h: float):
    """Deployment n (D6) as (attacker zone rects, defender zone rects,
    objectives), from the six diagrams. Rect args: (left, right, top, bottom)
    insets from the edges; objectives (x, y) in the engine frame."""
    cx, cy = w / 2.0, h / 2.0
    top = lambda d: h - d              # noqa: E731  y of a point d below the top edge
    bot = lambda d: d                  # noqa: E731
    if n == 1:
        att = [(0, 0, 0, h - 30)]
        dfn = [(0, 0, h - 30, 0)]
        obj = [(30, cy), (cx, cy), (w - 30, cy)]
    elif n == 2:
        att = [(0, 60, 0, h - 30)]
        dfn = [(60, 0, h - 30, 0)]
        obj = [(w - 30, top(30)), (cx, cy), (30, bot(30))]
    elif n == 3:
        # L-shapes: attacker bottom-left (45 wide x 30 deep, plus 30 wide up
        # to 45 from the bottom); defender the mirror image top-right
        att = [(0, w - 45, h - 30, 0), (0, w - 30, h - 45, 0)]
        dfn = [(w - 45, 0, 0, h - 30), (w - 30, 0, 0, h - 45)]
        obj = [(30, top(30)), (cx, top(30)), (cx, bot(30)), (w - 30, bot(30))]
    elif n == 4:
        att = [(0, 0, 0, h - 30)]
        dfn = [(0, 0, h - 30, 0)]
        obj = [(45, cy), (w - 45, cy), (cx, top(45)), (cx, bot(45))]
    elif n == 5:
        att = [(0, w - 45, 0, 0)]
        dfn = [(w - 45, 0, 0, 0)]
        obj = [(cx, top(30)), (w - 60, top(30)), (60, bot(30)), (cx, bot(30))]
    elif n == 6:
        att = [(0, w - 45, 0, 0)]
        dfn = [(w - 45, 0, 0, 0)]
        obj = [(cx, top(15)), (cx, cy), (cx, bot(15))]
    else:
        raise ValueError(f"Domination deployment {n} (D6)")
    return att, dfn, obj


def setup_scenario(gs, dice=None, layout: Optional[int] = None) -> None:
    """Before deployment: roll what the scenario needs (Domination: the D6
    deployment diagram) and store it in `gs.scenario_state`."""
    mode = getattr(gs, "scenario_mode", "standard")
    if mode == "domination":
        if layout is None:
            if dice is None:
                from .dice import DiceRoller
                dice = DiceRoller(mode="auto")
            layout = dice.roll_d6(1, "Domination deployment (D6)")[0]
        _, _, obj = _domination_layout(layout, gs.table_width, gs.table_height)
        gs.scenario_state = {"layout": layout,
                             "objectives": [[round(x, 3), round(y, 3)] for x, y in obj],
                             "points": {"1": 0, "2": 0}}
        gs.add_log(f"[Domination] deployment {layout}: {len(obj)} objective markers")
    elif mode in SCENARIOS:
        gs.scenario_state = {}


def deployment_zones(gs) -> Optional[List[DeploymentZone]]:
    """The scenario's deployment zones (each player's first rect carries any
    others in `extra`), or None for the default 30cm zones."""
    mode = getattr(gs, "scenario_mode", "standard")
    w, h = gs.table_width, gs.table_height
    att_p = gs.scenario_attacker
    if mode == "confrontation":
        # Attacker within 30cm of a long table edge, defender the opposite one
        rects = {att_p: [(0, 0, 0, h - 30)], 3 - att_p: [(0, 0, h - 30, 0)]}
    elif mode == "domination":
        layout = (gs.scenario_state or {}).get("layout")
        if not layout:
            return None
        att, dfn, _ = _domination_layout(layout, w, h)
        rects = {att_p: att, 3 - att_p: dfn}
    else:
        return None
    zones = []
    for p in (1, 2):
        role = "Attacker" if p == att_p else "Defender"
        rs = [_rect(p, w, h, *r, label=f"Player {p} ({role})") for r in rects[p]]
        main = rs[0]
        main.extra = rs[1:]
        zones.append(main)
    return zones


# --- Domination: control and scoring --------------------------------------------

def objectives(gs) -> List[Tuple[float, float]]:
    return [tuple(o) for o in (gs.scenario_state or {}).get("objectives", [])]


def _counts_for_control(ship) -> bool:
    """A ship that can hold a marker: on the table and operational (reading:
    hulks, destroyed and disengaged ships don't count)."""
    return not (ship.is_destroyed or ship.is_disengaged or getattr(ship, "is_hulk", False))


def controller(gs, marker: Tuple[float, float], ships=None) -> Optional[int]:
    """The player controlling a marker: at least one ship within 15cm of it
    (marker centre to the ship's stem) and no enemy ship (p.126)."""
    ships = gs.get_ships() if ships is None else ships
    mx, my = marker
    near = {s.player for s in ships if _counts_for_control(s)
            and (s.x - mx) ** 2 + (s.y - my) ** 2 <= CONTROL_RANGE ** 2}
    return next(iter(near)) if len(near) == 1 else None


def controlled(gs, player: int, ships=None) -> int:
    return sum(1 for m in objectives(gs) if controller(gs, m, ships) == player)


def points(gs) -> Dict[int, int]:
    pts = (gs.scenario_state or {}).get("points", {})
    return {1: int(pts.get("1", 0)), 2: int(pts.get("2", 0))}


def score_end_of_turn(gs, player: int) -> int:
    """At the end of each player's own turn that player scores 1 objective
    point per marker controlled. Returns the points scored. Called from
    TurnController.end_phase; alternate activation calls that for each player
    in the round's end phase, so both score once a round (reading, outside the
    booklet)."""
    if getattr(gs, "scenario_mode", "") != "domination":
        return 0
    n = controlled(gs, player)
    st = dict(gs.scenario_state or {})
    pts = dict(st.get("points", {"1": 0, "2": 0}))
    pts[str(player)] = int(pts.get(str(player), 0)) + n
    st["points"] = pts
    gs.scenario_state = st
    gs.add_log(f"[Domination] player {player} controls {n} objective(s): "
               f"{pts['1']} - {pts['2']} points")
    return n


def check_end(gs) -> Optional[dict]:
    """Booklet scenario game-end and victory (scenario.check_game_over's
    contract). Fleet-gone checks stay in check_game_over."""
    mode = getattr(gs, "scenario_mode", "")
    if mode == "domination":
        pts = points(gs)
        if max(pts.values()) >= DOMINATION_TARGET:
            return {"winner": points_winner(gs), "reason": "objective_points",
                    "detail": f"{pts[1]} - {pts[2]}"}
    return None


def points_winner(gs) -> Optional[int]:
    pts = points(gs)
    if pts[1] == pts[2]:
        return None
    return 1 if pts[1] > pts[2] else 2


def winner_at_end(gs, vp_winner_fn) -> Optional[int]:
    """Who wins when the game ends for any reason (fleet gone, turn limit):
    Domination by objective points, the others by VP."""
    sc = SCENARIOS.get(getattr(gs, "scenario_mode", ""))
    if sc and sc["victory"] == "objective_points":
        return points_winner(gs)
    return vp_winner_fn(gs)
