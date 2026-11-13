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
    "line_breaker": {
        "name": "Line Breaker (XR p.118)",
        "first_turn": "attacker",
        "end": "fleet_gone_or_breakthrough",
        "victory": "line_breaker",
    },
    "space_assault": {
        "name": "Space Assault (XR p.121)",
        "first_turn": "attacker",
        "end": "fleet_gone",
        "victory": "vp",
    },
    "convoy_matched": {
        "name": "Convoy (XR p.120, matched play)",
        "first_turn": "defender",
        "end": "fleet_gone_or_no_cargo",
        "victory": "vp",
    },
    "planet_strike": {
        "name": "Planet Strike (XR p.124)",
        "first_turn": "attacker",
        "end": "fleet_gone",
        "victory": "planet_strike",
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


# --- Attack ratings (p.78) --------------------------------------------------------
# Faction -> attack rating (the booklet's table and faction fleet lists).
# Readings (no fleet list recorded on the ships): Eldar 3 (Craftworld; Corsair
# lists are 4), Necrons 4 (Harvest; Dynasty 3), Space Marines 3 (Dominion with
# allies of convenience 2).
ATTACK_RATINGS = {
    "imperial_navy_gothic": 2, "chaos": 2, "adeptus_mechanicus": 2, "tau_kororvesh": 2,
    "space_marines": 3, "orks": 3, "eldar": 3, "necrons": 4,
}


def attack_rating(gs, player: int) -> int:
    """A fleet's attack rating: its main faction's (by points). Inquisition
    fleets: a Grey Knights banisher fleet 3, 2 when more than half its ships
    aren't Grey Knights (p.84); a Rogue Trader or Inquisition detachment
    doesn't change the fleet it joins; support assets don't count. Reading: a
    fleet of Rogue Traders alone has 2."""
    ships = [s for s in gs.get_ships() if s.player == player]
    pts: Dict[str, int] = {}
    for s in ships:
        if s.faction != "support_assets":
            pts[s.faction] = pts.get(s.faction, 0) + (s.points_value or 0)
    main = [f for f in pts if f not in ("rogue_traders", "inquisition_grey_knights")]
    if main:
        return ATTACK_RATINGS.get(max(main, key=pts.get), 2)
    if "inquisition_grey_knights" in pts:
        inq = [s for s in ships if s.faction == "inquisition_grey_knights"]
        gk = sum(1 for s in inq if "knights_of_titan" in s.special_rules)
        return 3 if gk * 2 >= len([s for s in ships if s.faction != "support_assets"]) else 2
    return 2


def roll_attack_ratings(gs, dice) -> int:
    """Each player rolls D6s equal to the fleet's attack rating; the best die
    wins, ties compare the next highest and so on, and a player who runs out
    of dice loses; a complete tie is rolled again. Returns the attacker."""
    r = {p: attack_rating(gs, p) for p in (1, 2)}
    while True:
        rolls = {p: sorted(dice.roll_d6(r[p], f"Player {p} attack rating ({r[p]}D6)"),
                           reverse=True) for p in (1, 2)}
        for a, b in zip(rolls[1], rolls[2]):
            if a != b:
                win = 1 if a > b else 2
                break
        else:
            if len(rolls[1]) == len(rolls[2]):
                continue                         # still tied: roll again
            win = 1 if len(rolls[1]) > len(rolls[2]) else 2
        gs.add_log(f"[Scenario] attack ratings: player 1 {rolls[1]}, player 2 "
                   f"{rolls[2]}: player {win} attacks")
        return win


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
    elif mode == "convoy_matched":
        gs.scenario_state = {"had_cargo": cargo_on_table(gs, defender(gs)) > 0}
    elif mode == "planet_strike":
        # A large planet centred between the long edges, its far side exactly
        # 45cm from the defender's short edge (the right one); no other planets
        # (reading: planets already placed are removed)
        from .models import Phenomenon
        r = 8.0
        gs.phenomena = [p for p in gs.phenomena if "planet" not in p.get("phenomenon_type", "")]
        gs.add_phenomenon(Phenomenon(id="strike_planet", phenomenon_type="planet_large",
                                     x=gs.table_width - 45.0 + r, y=gs.table_height / 2.0,
                                     width=2 * r, height=2 * r, radius=r))
        gs.scenario_state = {"bombardment": 0}
        gs.add_log("[Planet Strike] a large planet 45cm from the defender's short edge")
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
    if getattr(gs, "scenario_mode", "") == "space_assault":
        st = space_station(gs)
        if st is not None:
            # exactly 30cm from the defender's edge, equidistant from the short edges
            return {st.id: (gs.table_width / 2.0, 30.0, 90.0)}
    return {}


PLATFORMS = ("Orbital Weapons Platform", "Orbital Defence Laser Platform",
             "Orbital Torpedo Launcher")


def is_platform(ship) -> bool:
    """Line Breaker's defence platforms (Support Assets)."""
    return any(ship.ship_class.startswith(p) for p in PLATFORMS)


def transport(ship, building: bool = False) -> float:
    """A convoy ship's transport capacity (Support Assets p.64): halved while
    crippled for ships larger than an escort; escort carriers and Q-ships
    count only when assembling the fleet (`building`)."""
    cap = next((float(r.split(":")[1]) for r in ship.special_rules
                if r.startswith("transport:")), 0.0)
    if building:
        return cap
    if "transport_build_only" in ship.special_rules:
        return 0.0
    if ship.ship_type != "escort" and ship.damage_crippled:
        cap /= 2.0
    return cap


def is_convoy(ship) -> bool:
    return any(r.startswith("transport:") for r in ship.special_rules)


def cargo_on_table(gs, player: int) -> float:
    return sum(transport(s) for s in gs.get_ships() if s.player == player and is_convoy(s)
               and not s.is_destroyed and not s.is_disengaged)


def scores_normally(gs, ship) -> bool:
    """False for ships the scenario scores itself (vp_bonus): Convoy's convoy
    ships."""
    return not (getattr(gs, "scenario_mode", "") == "convoy_matched" and is_convoy(ship)
                and ship.player == defender(gs))


def strike_planet(gs):
    return next((p for p in gs.get_phenomena() if p.id == "strike_planet"), None)


def in_planet_contact(gs, ship) -> bool:
    """Base contact with Planet Strike's planet marker."""
    pl = strike_planet(gs)
    if pl is None:
        return False
    margin = getattr(gs, "contact_margin_cm", 0.2)
    return ((ship.x - pl.x) ** 2 + (ship.y - pl.y) ** 2
            <= (pl.radius + ship.base_radius + margin) ** 2)


def bombardment_points(gs, ship) -> float:
    """What a ship scores for holding position over the planet: its remaining
    hits plus its total transport capacity."""
    return ship.hits_remaining + transport(ship)


# Planet Strike's table: bombardment points -> the D6 the attacker needs
# (None: the defender wins automatically, 1: the attacker wins automatically)
STRIKE_TABLE = ((5, None), (10, 6), (15, 5), (20, 4), (25, 3), (30, 2))


def strike_need(points_: float) -> Optional[int]:
    for top, need in STRIKE_TABLE:
        if points_ <= top:
            return need
    return 1


def space_station(gs):
    return next((s for s in gs.get_ships() if s.player == defender(gs)
                 and s.ship_class.startswith("Space Station")), None)


def force_errors(gs) -> List[str]:
    """The scenario's force requirements (checked at set-up, warnings only):
    Line Breaker one defence platform per 200pts or portion thereof of the
    defender's fleet; Space Assault a single space station."""
    mode = getattr(gs, "scenario_mode", "")
    ships = [s for s in gs.get_ships() if s.player == defender(gs)]
    if mode == "line_breaker":
        pts = sum(s.points_value for s in ships)
        need = -(-pts // 200)
        have = sum(1 for s in ships if is_platform(s))
        if have < need:
            return [f"Line Breaker: the defender needs {need} defence platforms "
                    f"({pts}pts), has {have}"]
    if mode == "planet_strike":
        att = [s for s in gs.get_ships() if s.player == gs.scenario_attacker]
        pts = sum(s.points_value for s in att if not is_convoy(s))
        need = -(-pts // 100)
        have = sum(transport(s, building=True) for s in att if is_convoy(s))
        if have < need:
            return [f"Planet Strike: the attacker needs {need} transport capacity "
                    f"({pts}pts), has {have:g}"]
        return []
    if mode == "convoy_matched":
        convoy = [s for s in ships if is_convoy(s)]
        pts = sum(s.points_value for s in ships if not is_convoy(s))
        need = -(-pts // 100)
        have = sum(transport(s, building=True) for s in convoy)
        errs = []
        if abs(have - need) > 1e-9:
            errs.append(f"Convoy: the defender needs exactly {need} transport capacity "
                        f"({pts}pts), has {have:g}")
        if not any(transport(s) > 0 for s in convoy):
            errs.append("Convoy: at least one convoy ship whose capacity counts in the game")
        return errs
    if mode == "space_assault":
        n = sum(1 for s in ships if s.ship_class.startswith("Space Station"))
        if n != 1:
            return [f"Space Assault: the defender must include a single space station ({n})"]
    return []


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
    elif mode == "line_breaker":
        # The defender's long edge is the bottom one (y = 0): its fleet within
        # 60cm of it, its platforms more than 30cm from every edge
        # (placement_errors tells them apart); the attacker within 15cm of the top
        rects = {3 - att_p: [(0, 0, h - 60, 0), (30, 30, 30, 30)],
                 att_p: [(0, 0, 0, h - 15)]}
    elif mode == "space_assault":
        # Defender within 30cm of the bottom edge (the station is placed by the
        # scenario, 30cm in and centred); attacker within 30cm of the top
        rects = {3 - att_p: [(0, 0, h - 30, 0)], att_p: [(0, 0, 0, h - 30)]}
    elif mode == "planet_strike":
        # Attacker within 30cm of the left short edge; defender within 45cm of
        # the right one, where the planet is (its defences in the gravity well,
        # the extra rect, placement_errors tells them apart)
        pl = strike_planet(gs)
        well = pl.gravity_well_radius if pl else 38.0
        px, py = (pl.x, pl.y) if pl else (w - 37.0, h / 2.0)
        rects = {att_p: [(0, w - 30, 0, 0)],
                 3 - att_p: [(w - 45, 0, 0, 0),
                             (max(0.0, px - well), max(0.0, w - px - well),
                              max(0.0, h - py - well), max(0.0, py - well))]}
    elif mode == "convoy_matched":
        # Defender (and its convoy) within 30cm of the bottom edge; attacker
        # between 15 and 45cm of the top edge
        rects = {3 - att_p: [(0, 0, h - 30, 0)], att_p: [(0, 0, 15, h - 45)]}
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
    mode = getattr(gs, "scenario_mode", "")
    if mode == "line_breaker" and group and group[0].player == defender(gs):
        w, h = gs.table_width, gs.table_height
        for s_, (x, y) in zip(group, positions):
            if is_platform(s_):
                if min(x, y, w - x, h - y) <= 30.0:
                    errs.append(f"Line Breaker: {s_.name} more than 30cm from every edge")
                for o in placed:
                    if is_platform(o) and (o.x - x) ** 2 + (o.y - y) ** 2 <= 15.0 ** 2:
                        errs.append(f"Line Breaker: platforms more than 15cm apart ({o.name})")
                if any(_in_phenomenon(x, y, p) for p in gs.get_phenomena()):
                    errs.append(f"Line Breaker: {s_.name} not within a celestial phenomenon")
            elif y > 60.0:
                errs.append(f"Line Breaker: {s_.name} within 60cm of the defender's edge")
        return errs
    if mode == "planet_strike" and group and group[0].player == defender(gs):
        pl = strike_planet(gs)
        for s_, (x, y) in zip(group, positions):
            if "immobile" in s_.special_rules:
                if pl and (x - pl.x) ** 2 + (y - pl.y) ** 2 > pl.gravity_well_radius ** 2:
                    errs.append(f"Planet Strike: {s_.name} within the planet's gravity well")
            elif x < gs.table_width - 45.0:
                errs.append(f"Planet Strike: {s_.name} within 45cm of the defender's edge")
        return errs
    if mode != "ambush" or not group:
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


def _in_phenomenon(x: float, y: float, p) -> bool:
    """A point inside a celestial phenomenon's area (planets by radius, the
    rest by their rectangle, as the map editor draws them)."""
    if "planet" in p.phenomenon_type and p.radius > 0:
        return (x - p.x) ** 2 + (y - p.y) ** 2 <= p.radius ** 2
    return abs(x - p.x) <= p.width / 2 and abs(y - p.y) <= p.height / 2


def auto_positions(gs, group, zone, placed, index: int):
    """Scenario-aware automatic placement, or None for the default: Warp
    Storm alternates its divisions' corners; Ambush spaces the defender's
    groups 25cm apart."""
    mode = getattr(gs, "scenario_mode", "")
    if mode == "line_breaker" and group and group[0].player == defender(gs):
        rects = zone.rects()
        r = rects[1] if is_platform(group[0]) else rects[0]
        others = [s for s in placed if s.player == defender(gs)]
        y = r.y_min + (2.0 if is_platform(group[0]) else 5.0)
        while y <= r.y_max:
            x = r.x_min + 5.0
            while x <= r.x_max:
                pts = [(x + 4.0 * i, y) for i in range(len(group))]
                if not placement_errors(gs, group, pts, [90.0] * len(group), others) and all(
                        (px - s.x) ** 2 + (py - s.y) ** 2 >= 6.0 ** 2
                        for px, py in pts for s in others):
                    return pts
                x += 16.0
            y += 8.0
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


def exit_edge(gs, ship) -> str:
    """The table edge a ship has moved off (the one it is furthest past)."""
    r = ship.base_radius
    over = {"left": r - ship.x, "right": ship.x + r - gs.table_width,
            "bottom": r - ship.y, "top": ship.y + r - gs.table_height}
    return max(over, key=over.get)


def record_exit(gs, ship) -> None:
    """A ship moved off the table: remember the edge (Line Breaker's
    breakthrough is a capital ship off the defender's long edge)."""
    if not is_booklet_scenario(gs):
        return
    st = dict(gs.scenario_state or {})
    exits = dict(st.get("exits", {}))
    exits[ship.id] = exit_edge(gs, ship)
    st["exits"] = exits
    gs.scenario_state = st


def line_breaker_won(gs) -> bool:
    """The attacker has destroyed every defence platform and moved at least
    one capital ship off the defender's long edge (the bottom one)."""
    plats = [s for s in gs.get_ships() if s.player == defender(gs) and is_platform(s)]
    if any(not s.is_destroyed for s in plats):
        return False
    exits = (gs.scenario_state or {}).get("exits", {})
    return any(edge == "bottom" and (s := gs.get_ship_by_id(sid)) is not None
               and s.player == gs.scenario_attacker and s.ship_type != "escort"
               for sid, edge in exits.items())


def vp_bonus(gs, result: Dict) -> None:
    """Scenario victory points added to calculate_victory_points' result.
    Rescue: the attacker +100% of the defending flagship's cost if it is
    destroyed at the end of the game. Space Assault: 250 to the attacker if
    the space station is destroyed, else 250 to the defender."""
    if getattr(gs, "scenario_mode", "") == "convoy_matched":
        # Each convoy ship moving off the attacker's long edge (the top) gives
        # the defender 100 VP instead of counting for the attacker; leaving
        # any other way counts as destroyed and gives the attacker +50.
        # Reading: convoy ships are scored one by one, not as squadrons
        exits = (gs.scenario_state or {}).get("exits", {})
        att, dfn = gs.scenario_attacker, defender(gs)
        for c in gs.get_ships():
            if c.player != dfn or not is_convoy(c):
                continue
            pts = c.points_value
            if c.is_disengaged and exits.get(c.id) == "top":
                vp, who, why = 100, dfn, "escaped"
            elif c.is_disengaged:
                vp, who, why = pts + 50, att, "left the board (destroyed)"
            elif c.is_destroyed:
                vp, who, why = pts, att, "destroyed"
            elif c.damage_crippled:
                vp, who, why = max(1, pts // 4) if pts else 0, att, "crippled"
            else:
                continue
            if vp:
                result[who]["scenario"] = result[who].get("scenario", 0) + vp
                result[who]["details"].append(f"Convoy: {c.name} {why}: +{vp} VP")
        return
    if getattr(gs, "scenario_mode", "") == "space_assault":
        st = space_station(gs)
        if st is None:
            return
        p = gs.scenario_attacker if st.is_destroyed else defender(gs)
        result[p]["scenario"] = result[p].get("scenario", 0) + 250
        result[p]["details"].append(f"Space Assault: station "
                                    f"{'destroyed' if st.is_destroyed else 'survives'}: +250 VP")
        return
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
    flagship: +100% of its cost; Space Assault's station: the 250 the attacker
    gains and the 250 the defender loses). Line Breaker's platforms: the
    attacker can only win with them all destroyed (judgement: each worth the
    defender's points / platforms). Used by the AI's damage and disengage
    values."""
    mode = getattr(gs, "scenario_mode", "")
    if mode == "convoy_matched" and is_convoy(ship) and ship.player == defender(gs):
        return 100.0        # a convoy ship escaping would give the defender 100
    if mode == "space_assault" and ship.ship_class.startswith("Space Station") \
            and ship.player == defender(gs):
        return 500.0
    if mode == "line_breaker" and is_platform(ship) and ship.player == defender(gs):
        ds = [s for s in gs.get_ships() if s.player == defender(gs)]
        n = max(1, sum(1 for s in ds if is_platform(s)))
        return sum(s.points_value for s in ds) / n
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
    if getattr(gs, "scenario_mode", "") == "planet_strike":
        # Planet Strike: the attacker holding the field wins; otherwise a D6
        # on the bombardment table decides the invasion
        st = dict(gs.scenario_state or {})
        if st.get("strike_winner"):
            return False
        from .victory_points import _holds_field
        pts = st.get("bombardment", 0)
        need = strike_need(pts)
        if _holds_field(gs.scenario_attacker, gs.get_ships()):
            win = gs.scenario_attacker
        elif need is None:
            win = defender(gs)
        elif need == 1:
            win = gs.scenario_attacker
        else:
            roll = dice.roll_d6(1, f"Planet Strike invasion ({pts:g} bombardment points: "
                                   f"{need}+)")[0]
            win = gs.scenario_attacker if roll >= need else defender(gs)
            gs.add_log(f"[Planet Strike] invasion roll {roll} (needs {need}+)")
        st["strike_winner"] = win
        gs.scenario_state = st
        gs.add_log(f"[Planet Strike] player {win} wins ({pts:g} bombardment points)")
        return True
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
    if getattr(gs, "scenario_mode", "") == "planet_strike":
        if player != gs.scenario_attacker:
            return 0
        got = 0.0
        for sh in gs.get_ships():
            if (sh.player == player and not sh.is_destroyed and not sh.is_disengaged
                    and (sh.distance_moved_this_turn or 0.0) <= 1e-9
                    and in_planet_contact(gs, sh)):
                got += bombardment_points(gs, sh)
        if got:
            st = dict(gs.scenario_state or {})
            st["bombardment"] = st.get("bombardment", 0) + got
            gs.scenario_state = st
            gs.add_log(f"[Planet Strike] bombardment +{got:g}: {st['bombardment']:g} points")
        return got
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
    if mode == "convoy_matched":
        st = gs.scenario_state or {}
        if st.get("had_cargo") and cargo_on_table(gs, defender(gs)) <= 0:
            from .scenario import vp_winner
            return {"winner": vp_winner(gs), "reason": "convoy_gone",
                    "detail": "no transport capacity left on the table"}
    if mode == "line_breaker" and line_breaker_won(gs):
        return {"winner": gs.scenario_attacker, "reason": "breakthrough",
                "detail": "the line is broken"}
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


# --- AI: scenario points as VP ---------------------------------------------------
OBJECTIVE_POINT_WEIGHT = 0.5    # judgement: 10 Domination points ~ half the points on the table
BOMBARD_WEIGHT = 0.5            # judgement: winning Planet Strike ~ half the points on the table


def table_points(gs) -> float:
    return float(sum(s.points_value for s in gs.get_ships()) or 1000)


def domination_point_vp(total: float) -> float:
    """A Domination objective point in VP: a tenth of the game (judgement)."""
    return OBJECTIVE_POINT_WEIGHT * total / (2.0 * DOMINATION_TARGET)


def bombard_point_vp(total: float) -> float:
    """A Planet Strike bombardment point in VP: about a 25th of the game,
    the table running from 6 (6+) to 31 (automatic) (judgement)."""
    return BOMBARD_WEIGHT * total / 25.0


def scenario_margin_vp(gs, player: int) -> float:
    """The scenario points banked so far, as VP for `player` (To do 2: the
    margin the AI plays for counts them): Domination's objective points,
    Planet Strike's bombardment points (the attacker's)."""
    mode = getattr(gs, "scenario_mode", "")
    if mode == "domination":
        pts = points(gs)
        return (pts[player] - pts[3 - player]) * domination_point_vp(table_points(gs))
    if mode == "planet_strike":
        b = (gs.scenario_state or {}).get("bombardment", 0)
        sign = 1 if player == gs.scenario_attacker else -1
        return sign * b * bombard_point_vp(table_points(gs))
    return 0.0


def sim_scenario(gs) -> Dict:
    """What the expert search's leaf needs about the scenario (lookahead_ai):
    Domination's markers, points and point value; Planet Strike's planet,
    bombardment and point value."""
    mode = getattr(gs, "scenario_mode", "")
    if mode == "domination":
        return {"mode": mode, "objectives": objectives(gs), "points": points(gs),
                "point_vp": domination_point_vp(table_points(gs))}
    if mode == "planet_strike":
        pl = strike_planet(gs)
        return {"mode": mode, "attacker": gs.scenario_attacker,
                "bombard": (gs.scenario_state or {}).get("bombardment", 0),
                "planet": (pl.x, pl.y, pl.radius) if pl else None,
                "point_vp": bombard_point_vp(table_points(gs))}
    return {}


def winner_at_end(gs, vp_winner_fn) -> Optional[int]:
    """Who wins when the game ends for any reason (fleet gone, turn limit):
    Domination by objective points, the others by VP."""
    sc = SCENARIOS.get(getattr(gs, "scenario_mode", ""))
    if sc and sc["victory"] == "objective_points":
        return points_winner(gs)
    if sc and sc["victory"] == "line_breaker":
        return gs.scenario_attacker if line_breaker_won(gs) else defender(gs)
    if sc and sc["victory"] == "planet_strike":
        st = gs.scenario_state or {}
        if st.get("strike_winner"):
            return st["strike_winner"]
        from .victory_points import _holds_field
        if _holds_field(gs.scenario_attacker, gs.get_ships()):
            return gs.scenario_attacker
        need = strike_need(st.get("bombardment", 0))
        if need is None:
            return defender(gs)
        if need == 1:
            return gs.scenario_attacker
        return None                       # decided by end_of_game's roll
    return vp_winner_fn(gs)
