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
    "ambush": {
        "name": "Ambush (XR p.119)",
        "first_turn": "attacker",
        "end": "fleet_gone",
        "victory": "vp",
    },
    "rescue": {
        "name": "Rescue (XR p.122)",
        "first_turn": "defender",
        "end": "fleet_gone",
        "victory": "vp",
    },
    "warp_storm": {
        "name": "Warp Storm (XR p.123)",
        "first_turn": "attacker",
        "end": "fleet_gone",
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
    if sc and sc.get("first_turn") == "defender":
        return 3 - gs.scenario_attacker
    return None


def defender(gs) -> int:
    return 3 - gs.scenario_attacker


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
    elif mode == "ambush":
        # The defender is caught unawares: no ordnance loaded (as if expended),
        # Reload Ordnance needed before launching or firing any
        for sd in gs.ships:
            if sd["player"] == defender(gs):
                sd["ordnance_loaded_torps"] = False
                sd["ordnance_loaded_craft"] = False
                sd["ordnance_loaded_mines"] = False
        gs.scenario_state = {"ambush": True}
        gs.add_log("[Ambush] the defender starts with no ordnance loaded")
    elif mode == "rescue":
        flag = rescue_flagship(gs)
        gs.scenario_state = {"flagship": flag.id if flag else None}
        if flag is not None:
            gs.add_log(f"[Rescue] the defending flagship is {flag.name}")
    elif mode in SCENARIOS:
        gs.scenario_state = {"started": True}


def rescue_flagship(gs):
    """Rescue: the defender's fleet commander's capital ship. Reading: without
    a flagship marked, the defender's most expensive capital ship."""
    sid = (gs.scenario_state or {}).get("flagship")
    if sid:
        return gs.get_ship_by_id(sid)
    caps = [s for s in gs.get_ships() if s.player == defender(gs)
            and s.ship_type != "escort" and not s.is_destroyed]
    flag = next((s for s in caps if s.is_flagship), None)
    return flag or max(caps, key=lambda s: s.points_value, default=None)


def fixed_placements(gs) -> Dict[str, Tuple[float, float, float]]:
    """Ships the scenario places itself (not deployed by the player): Rescue's
    flagship at the exact centre, pointing at the defender's short edge (the
    left edge, x = 0, here)."""
    if getattr(gs, "scenario_mode", "") == "rescue":
        flag = rescue_flagship(gs)
        if flag is not None:
            return {flag.id: (gs.table_width / 2.0, gs.table_height / 2.0, 180.0)}
    return {}


def deployment_zones(gs) -> Optional[List[DeploymentZone]]:
    """The scenario's deployment zones (each player's first rect carries any
    others in `extra`), or None for the default 30cm zones."""
    mode = getattr(gs, "scenario_mode", "standard")
    w, h = gs.table_width, gs.table_height
    att_p = gs.scenario_attacker
    if mode == "confrontation":
        # Attacker within 30cm of a long table edge, defender the opposite one
        rects = {att_p: [(0, 0, 0, h - 30)], 3 - att_p: [(0, 0, h - 30, 0)]}
    elif mode == "ambush":
        # Defender more than 30cm from every edge; attacker within 30cm of any
        rects = {3 - att_p: [(30, 30, 30, 30)],
                 att_p: [(0, 0, h - 30, 0), (0, 0, 0, h - 30), (0, w - 30, 0, 0),
                         (w - 30, 0, 0, 0)]}
    elif mode == "rescue":
        # The defender's short edge is the left one (x = 0), the attacker's the right
        rects = {3 - att_p: [(0, w - 30, 0, 0)], att_p: [(w - 30, 0, 0, 0)]}
    elif mode == "warp_storm":
        # Two divisions each in opposite corners (30cm squares): attacker
        # bottom-left and top-right, defender top-left and bottom-right
        rects = {att_p: [(0, w - 30, h - 30, 0), (w - 30, 0, 0, h - 30)],
                 3 - att_p: [(0, w - 30, 0, h - 30), (w - 30, 0, h - 30, 0)]}
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


def placement_errors(gs, group, positions, headings, placed) -> List[str]:
    """Scenario deployment rules beyond the zone (DeploymentState's
    extra_check). Ambush: every defending ship and squadron faces the same
    direction and is at least 20cm from any other ship or squadron (its own
    squadron excepted)."""
    errs: List[str] = []
    if getattr(gs, "scenario_mode", "") != "ambush" or not group:
        return errs
    if group[0].player != defender(gs):
        return errs
    others = [s for s in placed if s.player == defender(gs)
              and not (group[0].squadron_id and s.squadron_id == group[0].squadron_id)]
    for s in others:
        for h in headings:
            if abs((h - s.heading + 180.0) % 360.0 - 180.0) > 1e-6:
                errs.append(f"Ambush: every defending ship faces the same direction "
                            f"({s.name} faces {s.heading:g})")
                break
        for (x, y) in positions:
            if (x - s.x) ** 2 + (y - s.y) ** 2 < 20.0 ** 2:
                errs.append(f"Ambush: at least 20cm from {s.name}")
                break
    return errs


def auto_positions(gs, group, zone, placed, index: int):
    """Scenario-aware automatic placement, or None for the default: Warp
    Storm alternates its divisions' corners; Ambush spaces the defender's
    groups 25cm apart."""
    mode = getattr(gs, "scenario_mode", "")
    if mode == "warp_storm":
        r = zone.rects()[index % len(zone.rects())]
        cx, cy = (r.x_min + r.x_max) / 2, (r.y_min + r.y_max) / 2
        return [(cx + 5.0 * (i % 3) - 5.0, cy + 5.0 * (i // 3)) for i in range(len(group))]
    if mode == "ambush" and group and group[0].player == defender(gs):
        others = [s for s in placed if s.player == defender(gs)]
        y = zone.y_min + 5.0
        while y <= zone.y_max:
            x = zone.x_min + 5.0
            while x <= zone.x_max:
                pts = [(x + 4.0 * i, y) for i in range(len(group))]
                if all(zone.contains(px, py) for px, py in pts) and all(
                        (px - s.x) ** 2 + (py - s.y) ** 2 >= 21.0 ** 2
                        for px, py in pts for s in others):
                    return pts
                x += 25.0
            y += 25.0
    return None


def division_errors(gs, player: int) -> List[str]:
    """Warp Storm: the two divisions (one per corner) as close to the same
    number of capital ships and escort squadrons as possible (a difference of
    at most one of each, reading)."""
    if getattr(gs, "scenario_mode", "") != "warp_storm":
        return []
    zone = next((z for z in deployment_zones(gs) if z.player == player), None)
    if zone is None:
        return []
    caps, sqs = [0, 0], [set(), set()]
    for s in gs.get_ships():
        if s.player != player:
            continue
        i = next((k for k, r in enumerate(zone.rects())
                  if r.x_min <= s.x <= r.x_max and r.y_min <= s.y <= r.y_max), None)
        if i is None:
            continue
        if s.ship_type == "escort" and s.squadron_id:
            sqs[i].add(s.squadron_id)
        else:
            caps[i] += 1
    errs = []
    if abs(caps[0] - caps[1]) > 1:
        errs.append(f"capital ships {caps[0]} v {caps[1]}")
    if abs(len(sqs[0]) - len(sqs[1])) > 1:
        errs.append(f"escort squadrons {len(sqs[0])} v {len(sqs[1])}")
    return errs


# --- Special rules during the game -------------------------------------------

def _in_defenders_first_turn(gs) -> bool:
    """Up to the end of the defender's first turn. Reading: the attacker's
    turn before it counts too (the defender is caught unawares; a Brace in
    the attacker's first turn would last into the defender's turn)."""
    first = 1 if getattr(gs, "turn_system", "igougo") == "aa" or \
        gs.first_player == defender(gs) else 2
    return gs.turn_number <= first


def orders_forbidden(gs, ship) -> Optional[str]:
    """Why `ship` may not go on special orders now (Brace included), or None.
    Ambush: no defending ship during the defender's first turn. Rescue: the
    defending flagship during the defender's first turn."""
    mode = getattr(gs, "scenario_mode", "")
    if ship.player != defender(gs) or not _in_defenders_first_turn(gs):
        return None
    if mode == "ambush":
        return "Ambush: the defender is caught unawares (no special orders in its first turn)"
    if mode == "rescue" and ship.id == (gs.scenario_state or {}).get("flagship"):
        return "Rescue: the sabotaged flagship takes no special orders in its first turn"
    return None


def disengage_forbidden(gs, ship) -> Optional[str]:
    """Why `ship` may not take a disengage test, or None. Ambush: no defending
    ship in the defender's first turn. Rescue: the flagship may only
    disengage by moving off the defender's short edge (reading: no Leadership
    test to disengage)."""
    mode = getattr(gs, "scenario_mode", "")
    if mode == "ambush" and ship.player == defender(gs) and _in_defenders_first_turn(gs):
        return "Ambush: the defender may not disengage in its first turn"
    if mode == "rescue" and ship.id == (gs.scenario_state or {}).get("flagship"):
        return "Rescue: the flagship can only disengage off the defender's short edge"
    return None


def off_table_destroyed(gs, ship) -> bool:
    """Rescue: the flagship moving off any edge but the defender's short edge
    (the left edge, x = 0) is destroyed instead of disengaging."""
    if getattr(gs, "scenario_mode", "") != "rescue":
        return False
    if ship.id != (gs.scenario_state or {}).get("flagship"):
        return False
    r = ship.base_radius
    over = {"left": r - ship.x, "right": ship.x + r - gs.table_width,
            "bottom": r - ship.y, "top": ship.y + r - gs.table_height}
    return max(over, key=over.get) != "left"


def vp_bonus(gs, result: Dict) -> None:
    """Scenario victory points added to calculate_victory_points' result.
    Rescue: the attacker +100% of the defending flagship's cost if it is
    destroyed at the end of the game."""
    if getattr(gs, "scenario_mode", "") != "rescue":
        return
    sid = (gs.scenario_state or {}).get("flagship")
    flag = gs.get_ship_by_id(sid) if sid else None
    if flag is not None and flag.is_destroyed:
        att = gs.scenario_attacker
        result[att]["scenario"] = result[att].get("scenario", 0) + flag.points_value
        result[att]["details"].append(f"Rescue: {flag.name} destroyed: +{flag.points_value} VP")


def kill_bonus_vp(gs, ship) -> float:
    """Extra VP the scenario gives the enemy for destroying `ship` (Rescue's
    flagship: +100% of its cost). Used by the AI's damage and disengage values."""
    if (getattr(gs, "scenario_mode", "") == "rescue"
            and ship.id == (gs.scenario_state or {}).get("flagship")):
        return float(ship.points_value or 0)
    return 0.0


def warp_loss_chance(gs, ship) -> float:
    """Warp Storm: the chance a ship that disengages is lost in the warp at
    the end of the game (2D6 over its Ld). 0 in other scenarios."""
    if getattr(gs, "scenario_mode", "") != "warp_storm":
        return 0.0
    ld = ship.leadership
    ways = sum(1 for a in range(1, 7) for b in range(1, 7) if a + b > ld)
    return ways / 36.0


def end_of_game(gs, dice) -> bool:
    """Rolls the scenario makes when the game ends, once. Warp Storm: each
    ship or squadron that disengaged takes a Leadership test (2D6 against its
    Ld; a squadron once); those that fail are lost in the warp and count as
    destroyed. Returns True when anything changed."""
    if getattr(gs, "scenario_mode", "") != "warp_storm":
        return False
    st = dict(gs.scenario_state or {})
    if st.get("ended"):
        return False
    st["ended"] = True
    gs.scenario_state = st
    changed = False
    groups: Dict[str, list] = {}
    for s in gs.get_ships():
        if s.is_disengaged and not s.is_destroyed:
            key = s.squadron_id if (s.ship_type == "escort" and s.squadron_id) else s.id
            groups.setdefault(key, []).append(s)
    for members in groups.values():
        ld = max(m.leadership for m in members)
        roll = dice.roll_2d6(f"Warp Storm: {members[0].name} returns through the warp (Ld {ld})")
        if roll > ld:
            for m in members:
                m.is_disengaged = False
                m.status = "destroyed"
                m.hits_remaining = 0
                gs.update_ship(m)
            gs.add_log(f"[Warp Storm] {members[0].name} is lost in the warp (rolled {roll} "
                       f"v Ld {ld}): destroyed")
            changed = True
        else:
            gs.add_log(f"[Warp Storm] {members[0].name} escapes the warp (rolled {roll} v Ld {ld})")
    return changed


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
