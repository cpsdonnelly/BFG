"""Destroy the Docks (XR p.99): a raid on the orbital docks round a large
planet; the defender's fleet arrives at random from the top edge.

Diagram (transcribed edge-relative): a large planet at the centre with its
30cm gravity well; the attacker's two forces within 10cm of the left and
right (short) edges; the defender's reinforcements from the top edge.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

PLANET_R = 8.0               # a large planet (the Planet Strike size)
ATTACKER_EDGE = 10.0         # each attacking force within 10cm of a short edge
ORBITAL_MINES = 8
MINE_VP = 5                  # orbital mines give their 5pts when removed (Support Assets)
REINFORCEMENT_SHARE = 0.25   # the attacker must destroy 25% of the reinforcements
FREE_ASSETS = (("Space Station", 2, "station"), ("Orbital Dock", 1, "dock"),
               ("Defence Monitor", 1, "monitor"), ("System Escort", 2, "escort"))
# The eight satellites, four inner and four outer (judgement: the defender's
# choice in any mix; two weapons platforms, a laser and a torpedo launcher each)
SATELLITES = ("Orbital Weapons Platform", "Orbital Weapons Platform",
              "Orbital Defence Laser Platform", "Orbital Torpedo Launcher")


def active(gs) -> bool:
    return getattr(gs, "scenario_mode", "") == "destroy_docks"


def planet(gs):
    return next((p for p in gs.get_phenomena() if p.id == "docks_planet"), None)


def in_well(gs, x: float, y: float) -> bool:
    pl = planet(gs)
    return pl is not None and math.hypot(x - pl.x, y - pl.y) <= pl.gravity_well_radius


def _key(sd: Dict) -> str:
    return sd["squadron_id"] if (sd.get("ship_type") == "escort" and sd.get("squadron_id")) \
        else sd["id"]


def _add(gs, name: str, player: int, sid: str, squadron: str = ""):
    from .ship_catalog import find_ship_class
    from .models import Ship
    entry = find_ship_class(name)
    if entry is None:
        return None
    d = entry.to_ship_dict(name, player, ship_id=sid)
    d.update(x=0.0, y=0.0, heading=90.0, squadron_id=squadron)
    s = Ship.from_dict(d)
    gs.add_ship(s)
    return s


def setup(gs, dice) -> None:
    """Battlezone: no other phenomena; a large planet at the centre; an
    asteroid field from each player outside the gravity well (judgement: the
    attacker's across the reinforcement approach above the planet, the
    defender's between the left force and the planet). The defender's free
    assets are added (free; reading: they score their normal VP)
    and its own fleet held in reserve; the attacker's ships split into two
    forces as equal in points as possible (dearest first to the smaller)."""
    from .models import Phenomenon
    from .scenarios import _to_reserve, defender
    w, h = gs.table_width, gs.table_height
    gs.phenomena = []
    gs.add_phenomenon(Phenomenon(id="docks_planet", phenomenon_type="planet_large",
                                 x=w / 2.0, y=h / 2.0, width=2 * PLANET_R,
                                 height=2 * PLANET_R, radius=PLANET_R))
    pl = planet(gs)
    well = pl.gravity_well_radius
    for i, (ax, ay) in enumerate(((w / 2.0, min(h - 8.0, h / 2.0 + well + 9.0)),
                                  (max(8.0, w / 2.0 - well - 9.0), h / 2.0))):
        gs.add_phenomenon(Phenomenon(id=f"docks_asteroids_{i}",
                                     phenomenon_type="asteroid_field", x=ax, y=ay,
                                     width=15.0, height=15.0, radius=0))
    dfn = defender(gs)
    fleet_keys = sorted({_key(sd) for sd in gs.ships if sd["player"] == dfn})
    for sd in gs.ships:
        if sd["player"] == dfn and "immobile" not in sd.get("special_rules", []):
            _to_reserve(sd)
    roles: Dict[str, List[str]] = {"station": [], "dock": [], "monitor": [], "escort": [],
                                   "inner": [], "outer": [], "fleet": fleet_keys}
    n = 0
    for name, count, role in FREE_ASSETS:
        for k in range(count):
            s = _add(gs, name, dfn, f"docks_{role}_{k}",
                     squadron="docks_system_escorts" if role == "escort" else "")
            if s is not None:
                roles[role].append(s.id)
                n += 1
    for group in ("inner", "outer"):
        for k, name in enumerate(SATELLITES):
            s = _add(gs, name, dfn, f"docks_{group}_{k}")
            if s is not None:
                roles[group].append(s.id)
    # the attacker's two forces
    units: Dict[str, int] = {}
    for sd in gs.ships:
        if sd["player"] == gs.scenario_attacker:
            units[_key(sd)] = units.get(_key(sd), 0) + sd.get("points_value", 0)
    forces = {"left": [], "right": []}
    pts = {"left": 0, "right": 0}
    for k, v in sorted(units.items(), key=lambda kv: (-kv[1], kv[0])):
        side = "left" if pts["left"] <= pts["right"] else "right"
        forces[side].append(k)
        pts[side] += v
    # the fleet commander's free re-roll (on its flagship, reading)
    flag = next((sd for sd in gs.ships if sd["player"] == dfn and sd.get("is_flagship")), None)
    if flag is not None:
        flag["rerolls_remaining"] = flag.get("rerolls_remaining", 0) + 1
    gs.scenario_state = {"roles": roles, "forces": forces, "fails": {},
                         "mines_laid": 0,
                         "reinforcement_points": sum(
                             sd.get("points_value", 0) for sd in gs.ships
                             if sd["player"] == dfn and _key(sd) in fleet_keys)}
    gs.add_log(f"[Destroy the Docks] a large planet at the centre; the defender's free assets "
               f"({n} ships, 8 satellites) set up, its fleet in reserve; the attacker's forces "
               f"{pts['left']} / {pts['right']} pts")


def role_of(gs, ship) -> Optional[str]:
    roles = (gs.scenario_state or {}).get("roles", {})
    for r, ids in roles.items():
        if r != "fleet" and ship.id in ids:
            return r
    return None


def force_of(gs, ship) -> Optional[str]:
    forces = (gs.scenario_state or {}).get("forces", {})
    k = ship.squadron_id if (ship.ship_type == "escort" and ship.squadron_id) else ship.id
    return next((f for f, ks in forces.items() if k in ks), None)


def zone_rects(gs) -> Dict[int, List[Tuple[float, float, float, float]]]:
    """(left, right, top, bottom) distances: the attacker's two 10cm strips;
    the defender's gravity well (its bounding square) and, for the outer
    platforms, the whole table (placement_errors tells them apart)."""
    w, h = gs.table_width, gs.table_height
    pl = planet(gs)
    well = pl.gravity_well_radius if pl else 38.0
    px, py = (pl.x, pl.y) if pl else (w / 2.0, h / 2.0)
    att = gs.scenario_attacker
    return {att: [(0, w - ATTACKER_EDGE, 0, 0), (w - ATTACKER_EDGE, 0, 0, 0)],
            3 - att: [(max(0.0, px - well), max(0.0, w - px - well),
                       max(0.0, h - py - well), max(0.0, py - well)), (0, 0, 0, 0)]}


def placement_errors(gs, group, positions) -> List[str]:
    errs: List[str] = []
    if not group:
        return errs
    w = gs.table_width
    for s, (x, y) in zip(group, positions):
        if s.player == gs.scenario_attacker:
            side = force_of(gs, s)
            if side == "left" and x > ATTACKER_EDGE or side == "right" and x < w - ATTACKER_EDGE:
                errs.append(f"Destroy the Docks: {s.name} belongs to the {side} force")
            continue
        if role_of(gs, s) == "outer":
            continue
        if not in_well(gs, x, y):
            errs.append(f"Destroy the Docks: {s.name} sets up in the planet's gravity well")
    return errs


def auto_positions(gs, group, placed) -> Optional[List[Tuple[float, float]]]:
    """Defenders round the planet (a ring inside the well per role), outer
    platforms on a wider ring; attacking forces along their edge."""
    if not group:
        return None
    s0 = group[0]
    w, h = gs.table_width, gs.table_height
    if s0.player == gs.scenario_attacker:
        side = force_of(gs, s0) or "left"
        k = sum(1 for p in placed if p.player == s0.player and force_of(gs, p) == side)
        x = 5.0 if side == "left" else w - 5.0
        return [(x, h / 2.0 + (-1) ** (k + i) * 8.0 * ((k + i + 1) // 2))
                for i in range(len(group))]
    pl = planet(gs)
    if pl is None:
        return None
    role = role_of(gs, s0) or "fleet"
    ring = {"station": 13.0, "dock": 13.0, "inner": 22.0, "monitor": 30.0,
            "escort": 30.0, "outer": 55.0}.get(role, 30.0)
    k = sum(1 for p in placed if p.player == s0.player and (role_of(gs, p) or "fleet") == role)
    off = {"station": 0.0, "dock": 180.0, "inner": 45.0, "monitor": 0.0, "escort": 90.0,
           "outer": 22.5}.get(role, 0.0)
    step = {"station": 120.0, "dock": 0.0, "inner": 90.0, "escort": 12.0,
            "outer": 90.0}.get(role, 20.0)
    out = []
    for i in range(len(group)):
        a = math.radians(off + step * (k + i))
        x = pl.x + ring * math.cos(a)
        y = pl.y + ring * math.sin(a)
        out.append((max(3.0, min(w - 3.0, x)), max(3.0, min(h - 3.0, y))))
    return out


def lay_orbital_mines(gs) -> None:
    """The eight orbital mines: mine markers in the gravity well, active at
    once (the enemy is on the table). Placed on a ring 20cm out (judgement),
    once, after deployment."""
    st = dict(gs.scenario_state or {})
    if not active(gs) or st.get("mines_laid"):
        return
    from .models import OrdnanceMarker, OrdnanceType
    pl = planet(gs)
    if pl is None:
        return
    from .scenarios import defender
    for i in range(ORBITAL_MINES):
        a = math.radians(22.5 + 45.0 * i)
        gs.add_ordnance(OrdnanceMarker(
            id=f"orbital_mine_{i}", ordnance_type=OrdnanceType.MINE_FIELD.value,
            owner_player=defender(gs), launched_by="", x=pl.x + 20.0 * math.cos(a),
            y=pl.y + 20.0 * math.sin(a), heading=0.0, strength=1, speed=10,
            launched_turn=0))
    st["mines_laid"] = ORBITAL_MINES
    gs.scenario_state = st
    gs.add_log("[Destroy the Docks] 8 orbital mines laid in the gravity well")


def mines_removed(gs) -> int:
    st = gs.scenario_state or {}
    left = sum(1 for m in gs.get_ordnance() if str(m.id).startswith("orbital_mine_"))
    return max(0, st.get("mines_laid", 0) - left)


def arrival_need(ships, fails: int) -> int:
    """5+ / 4+ / 3+ by the slowest speed, +1 for every two turns failed."""
    slowest = min((s.speed for s in ships), default=0)
    need = 5 if slowest <= 20 else (4 if slowest < 30 else 3)
    return need - fails // 2


def arrivals(gs, player: int, dice) -> List[str]:
    """At the start of the defender's turn a D6 for each ship and squadron in
    reserve; arrivals come on from the top edge."""
    from .scenarios import reserve_units, place_arrival
    if dice is None:
        return []
    st = dict(gs.scenario_state or {})
    fails = dict(st.get("fails", {}))
    came = []
    for i, (k, ships) in enumerate(sorted(reserve_units(gs, player).items())):
        need = arrival_need(ships, fails.get(k, 0))
        r = dice.roll_d6(1, f"Destroy the Docks: {ships[0].name} arrives on {need}+")[0]
        if r >= need:
            place_arrival(gs, ships, i)
            came.append(", ".join(s.name for s in ships))
            gs.add_log(f"[Reinforcements] arriving from the top edge: {came[-1]}")
        else:
            fails[k] = fails.get(k, 0) + 1
    st["fails"] = fails
    gs.scenario_state = st
    return came


def reinforcements_destroyed(gs) -> int:
    st = gs.scenario_state or {}
    keys = set(st.get("roles", {}).get("fleet", []))
    return sum(s.points_value for s in gs.get_ships()
               if (s.squadron_id if (s.ship_type == "escort" and s.squadron_id) else s.id) in keys
               and s.is_destroyed)


def targets(gs) -> List[str]:
    """The ships the attacker must destroy: both stations, the dock and the
    inner platforms."""
    roles = (gs.scenario_state or {}).get("roles", {})
    return list(roles.get("station", [])) + list(roles.get("dock", [])) + \
        list(roles.get("inner", []))


def attacker_won(gs) -> bool:
    st = gs.scenario_state or {}
    for sid in targets(gs):
        s = gs.get_ship_by_id(sid)
        if s is not None and not s.is_destroyed:
            return False
    return reinforcements_destroyed(gs) >= REINFORCEMENT_SHARE * st.get(
        "reinforcement_points", 0)


def winner(gs) -> int:
    from .scenarios import defender
    return gs.scenario_attacker if attacker_won(gs) else defender(gs)


def force_errors(gs) -> List[str]:
    from .scenarios import defender
    bb = [s.name for s in gs.get_ships() if s.player == defender(gs)
          and s.ship_type == "battleship"]
    return [f"Destroy the Docks: the defender can't include battleships ({', '.join(bb)})"] \
        if bb else []


TARGET_WEIGHT = 0.5      # judgement: winning ~ half the points on the table


def target_bonus_vp(gs, ship) -> float:
    """AI: each objective ship's share of winning (judgement)."""
    if not active(gs) or ship.id not in targets(gs):
        return 0.0
    from .scenarios import table_points
    return TARGET_WEIGHT * table_points(gs) / max(1, len(targets(gs)))
