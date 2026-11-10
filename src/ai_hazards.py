"""AI hazard assessment: what a move risks, in expected victory points.

Owner guidance: the AI avoids asteroid fields, dust clouds, blast markers and
incoming torpedoes and mines, each with a threat level (one mine is more
dangerous than one torpedo salvo). Threats come from the rules, not invented
weights, so they compare with each other and with the damage a move lets the
ship deal:

- mines (s.17): 8D6 against Armour, ignoring shields; a mine moves exactly 10cm
  straight at the nearest enemy vessel in every ordnance phase;
- torpedoes (s.16): their strength in dice against Armour, ignoring shields,
  along their next move; turrets shoot some down first (4+ each);
- attack craft (s.18-24): bombers make D6 attacks less turrets, assault boats
  raids;
- asteroid fields: a failed Leadership test does D6 damage that shields stop
  (escorts re-roll); warp rifts: a failed 3D6 test loses the ship;
- dust clouds: -5cm, and 1/6 damage only to shieldless ships;
- blast markers: -5cm, a shield down for each touching at the end of the move,
  1/6 damage to a shieldless ship moving through.

Everything is pure logic (no Tk), so the expert AI's worker thread may use it.
"""
import math
from itertools import product
from typing import Dict, List, Sequence, Tuple

from .models import OrdnanceMarker, Ship

Point = Tuple[float, float]


# ── Probabilities ────────────────────────────────────────────────────────────

def p_sum_at_most(n_dice: int, target: int) -> float:
    """P(sum of n D6 <= target)."""
    if target < n_dice:
        return 0.0
    if target >= 6 * n_dice:
        return 1.0
    hits = sum(1 for r in product(range(1, 7), repeat=n_dice) if sum(r) <= target)
    return hits / 6 ** n_dice


def p_hit(armour: int) -> float:
    """One die against Armour N+ (a 6 always hits)."""
    return max(1, 7 - armour) / 6.0


# ── Values ───────────────────────────────────────────────────────────────────

def ship_value(ship: Ship, gs) -> float:
    """Victory points the ship is worth to its opponent if destroyed (s.38):
    its points (commander and options included), x1.25 for venerable ships;
    the flagship counts double while its fleet still has commander re-rolls
    to lose (owner guidance: protect the commander's ship)."""
    v = float(ship.points_value or 0) * (1.25 if "venerable" in ship.special_rules else 1.0)
    if ship.is_flagship and ship.rerolls_remaining > 0:
        v *= 2.0
    return v


def value_per_hit(ship: Ship, gs) -> float:
    return ship_value(ship, gs) / max(1, ship.hits_max)


# ── Geometry ─────────────────────────────────────────────────────────────────

def _seg_dist(px, py, ax, ay, bx, by) -> float:
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _dense(path: Sequence[Point], step: float = 1.0) -> List[Point]:
    pts: List[Point] = [path[0]]
    for (x1, y1), (x2, y2) in zip(path, path[1:]):
        n = max(1, int(math.hypot(x2 - x1, y2 - y1) / step))
        pts += [(x1 + (x2 - x1) * k / n, y1 + (y2 - y1) * k / n) for k in range(1, n + 1)]
    return pts


def _in_rect(x, y, p, pad) -> bool:
    return abs(x - p.x) <= p.width / 2 + pad and abs(y - p.y) <= p.height / 2 + pad


def _touches_phenomenon(x, y, r, p) -> bool:
    if "planet" in p.phenomenon_type and p.radius > 0:
        return math.hypot(x - p.x, y - p.y) <= p.radius + r
    return _in_rect(x, y, p, r)


# ── Threats ──────────────────────────────────────────────────────────────────

def _turret_kills(ship: Ship) -> float:
    return ship.effective_turrets * 0.5             # each turret hits on 4+


def ordnance_threat(ship: Ship, end: Point, path: Sequence[Point], gs) -> Tuple[float, List[str]]:
    """Expected hits from enemy ordnance on a ship that moves along `path` to
    `end`: what it runs into on the way (attacks at once), and what can reach
    it before its next move (the enemy's ordnance phase; mines also move in
    ours). Returns (expected hits, reasons)."""
    r = ship.base_radius
    hits, why = 0.0, []
    pts = _dense(path)
    my_ships = [s for s in gs.get_ships() if s.player == ship.player
                and not s.is_destroyed and not s.is_disengaged and s.id != ship.id]
    for o in gs.ordnance:
        m = OrdnanceMarker.from_dict(o)
        if m.owner_player == ship.player or m.cap_ship_id:
            continue
        otype = m.ordnance_type
        armour = ship.armor_vs(m.x, m.y)
        ph = p_hit(armour)
        on_path = any(math.hypot(px - m.x, py - m.y) <= r + 1.5 for px, py in pts)
        if otype == "mine_field":
            continue
        if "mine" in otype:
            # 10cm straight at the nearest enemy vessel, in our ordnance phase
            # and the enemy's: reach 20cm if this ship is the nearest
            d_end = math.hypot(end[0] - m.x, end[1] - m.y) - r
            nearest = all(math.hypot(s.x - m.x, s.y - m.y) - s.base_radius >= d_end
                          for s in my_ships)
            if on_path or (d_end <= 20.0 and nearest):
                h = 8 * ph
                hits += h
                why.append(f"mine ({h:.1f} hits)")
            continue
        if "torpedo" in otype and otype != "torpedo_bomber":
            strength = max(0.0, m.strength - _turret_kills(ship))
            if strength <= 0:
                continue
            rad = math.radians(m.heading)
            ex, ey = m.x + m.speed * math.cos(rad), m.y + m.speed * math.sin(rad)
            in_line = _seg_dist(end[0], end[1], m.x, m.y, ex, ey) <= r + 1.0
            if on_path or in_line:
                h = strength * ph
                if "boarding" in otype:
                    h *= 0.5                         # raids, not hull damage
                hits += h
                why.append(f"torpedoes S{m.strength} ({h:.1f} hits)")
            continue
        # attack craft that may reach the ship before it moves again
        reach = (m.speed or 20) + r
        if on_path or math.hypot(end[0] - m.x, end[1] - m.y) <= reach:
            if "bomber" in otype or otype in ("manta", "thunderhawk", "fighta_bommer"):
                attacks = max(0.0, 3.5 - ship.effective_turrets)
                h = attacks * ph
            elif "assault" in otype or otype == "gun_cutter":
                h = 0.5 * max(0.0, 1 - 0.5 * ship.effective_turrets / 2)
            else:
                continue                             # fighters don't attack ships
            hits += h
            why.append(f"{otype} ({h:.1f} hits)")
    return hits, why


def terrain_threat(ship: Ship, end: Point, path: Sequence[Point], gs,
                   order: str = "") -> Tuple[float, float, List[str]]:
    """(expected hits, chance of losing the ship, reasons) from celestial
    phenomena and blast markers along the move."""
    r = ship.base_radius
    pts = _dense(path)
    hits, lose, why = 0.0, 0.0, []
    ld = max(0, ship.leadership)
    n_dice = 3 if order == "all_ahead_full" else 2
    shields = ship.effective_shields
    for p in gs.get_phenomena():
        if not any(_touches_phenomenon(x, y, r, p) for x, y in pts):
            continue
        t = p.phenomenon_type
        if t == "asteroid_field":
            fail = 1.0 - p_sum_at_most(n_dice, ld)
            if ship.ship_type == "escort":
                fail *= fail                         # escorts re-roll
            h = fail * max(0.0, 3.5 - shields)
            hits += h
            why.append(f"asteroid field ({fail:.0%} fail)")
        elif t == "warp_rift":
            fail = 1.0 - p_sum_at_most(3, ld)
            lose = max(lose, fail)
            why.append(f"warp rift ({fail:.0%} lost)")
        elif t == "gas_dust_cloud" and "demiurg_commerce" not in ship.special_rules:
            if shields == 0:
                hits += 1 / 6
            why.append("dust cloud")
    bms = gs.get_blast_markers()
    if bms and "demiurg_commerce" not in ship.special_rules:
        from .geometry import BLAST_MARKER_RADIUS_CM
        reach = r + BLAST_MARKER_RADIUS_CM
        crossed = [b for b in bms if any(math.hypot(b.x - x, b.y - y) <= reach for x, y in pts)]
        if crossed:
            if shields == 0:
                hits += 1 / 6
            why.append(f"blast markers ({len(crossed)})")
    return hits, lose, why


def blast_markers_at(ship: Ship, end: Point, gs) -> int:
    from .geometry import BLAST_MARKER_RADIUS_CM
    reach = ship.base_radius + BLAST_MARKER_RADIUS_CM
    return sum(1 for b in gs.get_blast_markers() if math.hypot(b.x - end[0], b.y - end[1]) <= reach)


def move_hazard_vp(ship: Ship, end: Point, path: Sequence[Point], gs,
                   order: str = "") -> Dict:
    """Expected VP a move risks: hits x the ship's VP per hit (a cripple and a
    kill are where those hits matter most), plus a chance of losing the whole
    ship, plus the value of shields knocked down by blast markers it ends on
    (each stops roughly one hit of the enemy's fire). Returns {"vp", "why"}."""
    oh, ow = ordnance_threat(ship, end, path, gs)
    th, lose, tw = terrain_threat(ship, end, path, gs, order)
    vph = value_per_hit(ship, gs)
    hits = oh + th
    # Hits that cripple or kill are worth more than the first ones
    remaining = max(1, ship.hits_remaining)
    weight = 1.0 + (0.5 if hits >= remaining - ship.hits_max / 2 else 0.0) \
        + (1.0 if hits >= remaining * 0.75 else 0.0)
    vp = hits * vph * weight + lose * ship_value(ship, gs)
    if "demiurg_commerce" not in ship.special_rules:
        down = min(ship.effective_shields, blast_markers_at(ship, end, gs))
        vp += down * 0.5 * vph
    return {"vp": vp, "why": ow + tw}
