"""AI hazard assessment: what a move risks, in expected victory points.

Owner guidance: the AI avoids asteroid fields, dust clouds, blast markers and
incoming torpedoes and mines, each with a threat level (one mine is more
dangerous than one torpedo salvo). Threats come from the rules, not invented
weights, so they compare with each other and with the damage a move lets the
ship deal:

- mines (s.17): 8D6 against Armour (4D6 if any turret scores 4+), ignoring shields; a mine moves exactly 10cm
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


def p_sum_at_least(n_dice: int, target: int) -> float:
    """P(sum of n D6 >= target)."""
    return 1.0 - p_sum_at_most(n_dice, target - 1)


def lance_p(w: dict) -> float:
    """A lance die's chance to hit: 4+ (Ork Zzapp Gunz 5+, `hits_on`)."""
    return (7 - (w.get("hits_on") or 4)) / 6.0


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

def mine_attack_dice(ship: Ship) -> float:
    """Expected dice a mine attacks a ship with (s.17): 8D6, or 4D6 if any of
    the ship's turrets scores 4+ (Orks 5+), as `ordnance.resolve_mine_contact`
    rolls it. Innate turrets only (massed turrets depend on who is in base
    contact when it lands)."""
    need = 5 if "ork_turrets" in ship.special_rules else 4
    t = max(0, ship.effective_turrets)
    p_any = 1.0 - (1.0 - (7 - need) / 6.0) ** t
    return 8.0 - 4.0 * p_any


def _turret_kills(ship: Ship) -> float:
    """Expected torpedoes a ship's turrets shoot down: 4+ each (Orks 5+)."""
    need = 5 if "ork_turrets" in ship.special_rules else 4
    return ship.effective_turrets * (7 - need) / 6.0


def marker_hits(ship: Ship, m: OrdnanceMarker, end: Point, pts: Sequence[Point],
                my_ships: Sequence[Ship], gs=None) -> Tuple[float, str]:
    """Expected hits one enemy marker does to a ship that ends at `end` having
    passed through `pts` (0 if it can't reach it). my_ships: the ship's other
    friends (a mine goes for the nearest enemy vessel)."""
    r = ship.base_radius
    otype = m.ordnance_type
    if m.cap_ship_id or otype == "mine_field":
        return 0.0, ""
    ph = p_hit(ship.armor_vs(m.x, m.y))
    on_path = any(math.hypot(px - m.x, py - m.y) <= r + 1.5 for px, py in pts)
    if "mine" in otype:
        # 10cm straight at the nearest enemy vessel, in our ordnance phase and
        # the enemy's: reach 20cm if this ship is the nearest
        d_end = math.hypot(end[0] - m.x, end[1] - m.y) - r
        nearest = all(math.hypot(s.x - m.x, s.y - m.y) - s.base_radius >= d_end
                      for s in my_ships if s.id != ship.id)
        if on_path or (d_end <= 20.0 and nearest):
            h = mine_attack_dice(ship) * ph
            return h, f"mine ({h:.1f} hits)"
        return 0.0, ""
    if "torpedo" in otype and otype != "torpedo_bomber":
        strength = max(0.0, m.strength - _turret_kills(ship))
        if strength <= 0:
            return 0.0, ""
        h = strength * ph * (0.5 if "boarding" in otype else 1.0)   # raids, not hull
        if otype == "torpedo_guided":
            h *= 5 / 6        # Tau missiles: each strength point lost on a 1 before moving
        heading, p_reach = _torpedo_heading(m, ship, end, my_ships, gs)
        rad = math.radians(heading)
        reach = torpedo_reach(m)
        ex, ey = m.x + reach * math.cos(rad), m.y + reach * math.sin(rad)
        # contact: the ship's base (large bases are easier to hit) plus the
        # marker's half width
        if on_path or _seg_dist(end[0], end[1], m.x, m.y, ex, ey) <= r + TORP_CONTACT_HALF_W:
            return h, f"torpedoes S{m.strength} ({h:.1f} hits)"
        # Guided salvos (s.16) may turn up to 45 degrees before they move: the
        # whole cone in reach is at risk, weighted by the chance they turn
        if p_reach > 0 and _in_turn_cone(m, end, r):
            return h * p_reach, f"turning torpedoes S{m.strength} ({h * p_reach:.1f} hits)"
        return 0.0, ""
    if otype == "torpedo_bomber":
        # s.21: from the ordnance phase after launch each squadron may become a
        # strength-2 salvo facing any direction (so the lowest Armour, judgement:
        # the enemy picks the facing), fired from up to a salvo move away; a
        # wave combines them, so the turret kills are shared out per squadron
        tiger = "tiger_shark" in (m.special_rules or [])
        salvo = 40.0 if tiger else 30.0
        if on_path or math.hypot(end[0] - m.x, end[1] - m.y) <= (m.speed or 20) + salvo + r:
            h = max(0.0, 2.0 - 0.5 * _turret_kills(ship)) * p_hit(ship.lowest_armor_value)
            h *= 5 / 6 if tiger else 1.0
            return h, f"torpedo bombers ({h:.1f} hits)"
        return 0.0, ""
    # attack craft that may reach the ship before it moves again
    if on_path or math.hypot(end[0] - m.x, end[1] - m.y) <= (m.speed or 20) + r:
        if "bomber" in otype or otype in ("manta", "thunderhawk", "fighta_bommer"):
            # D6 attacks less one per turret, each hitting the LOWEST Armour
            # value whatever side they come from (s.20)
            h = (sum(max(0, k - ship.effective_turrets) for k in range(1, 7)) / 6.0
                 * p_hit(ship.lowest_armor_value))
        elif "assault" in otype or otype == "gun_cutter":
            h = 0.5 * max(0.0, 1 - 0.5 * ship.effective_turrets / 2)
        else:
            return 0.0, ""                       # fighters don't attack ships
        return h, f"{otype} ({h:.1f} hits)"
    return 0.0, ""


def ordnance_threat(ship: Ship, end: Point, path: Sequence[Point], gs) -> Tuple[float, List[str]]:
    """Expected hits from enemy ordnance on a ship that moves along `path` to
    `end`: what it runs into on the way (attacks at once), and what can reach
    it before its next move (the enemy's ordnance phase; mines also move in
    ours). Returns (expected hits, reasons)."""
    hits, why = 0.0, []
    pts = _dense(path)
    my_ships = [s for s in gs.get_ships() if s.player == ship.player
                and not s.is_destroyed and not s.is_disengaged]
    for o in gs.ordnance:
        m = OrdnanceMarker.from_dict(o)
        if m.owner_player == ship.player:
            continue
        h, w = marker_hits(ship, m, end, pts, my_ships, gs)
        if h > 0:
            hits += h
            why.append(w)
    return hits, why


def marker_threat_vp(m: OrdnanceMarker, gs, player: int) -> float:
    """Expected VP an enemy marker (or its whole wave) threatens against
    `player`'s ships where they stand: the worst ship it can reach. Used to
    pick what fighters intercept and what is worth shooting at."""
    from .waves import whole_wave_ids
    mine = [s for s in gs.get_ships() if s.player == player
            and not s.is_destroyed and not s.is_disengaged]
    ids = set(whole_wave_ids(gs, m.id)) if m.wave_id else {m.id}
    markers = [OrdnanceMarker.from_dict(o) for o in gs.ordnance if o["id"] in ids]
    best = 0.0
    for s in mine:
        hits = sum(marker_hits(s, mk, (s.x, s.y), [(s.x, s.y)], mine, gs)[0] for mk in markers)
        best = max(best, hits * value_per_hit(s, gs))
    return best


# Guided torpedoes turn if their launcher passes a Leadership test (s.16); with
# no game state to look the launcher up, assume Ld 8 (2D6 <= 8: 26 in 36)
GUIDED_TURN_CHANCE = 26 / 36


def guided_turn_chance(m: OrdnanceMarker, gs) -> float:
    """Chance a guided salvo turns next move (s.16): its launcher passes a
    Leadership test (2D6 <= Ld); a launcher no longer in play can't guide it
    (owner ruling). Without the game state, an assumed Ld 8."""
    if gs is None:
        return GUIDED_TURN_CHANCE
    src = gs.get_ship_by_id(m.launched_by) if m.launched_by else None
    if src is None or src.is_destroyed or src.is_disengaged:
        return 0.0
    ld = src.leadership or 8
    return p_sum_at_most(2, min(10, ld))


def _torpedo_heading(m: OrdnanceMarker, ship: Ship, end: Point,
                     my_ships: Sequence[Ship], gs=None) -> Tuple[float, float]:
    """(heading the salvo will run on next, chance it can instead turn anywhere
    in its 45-degree cone). Seeking torpedoes (s.16) must turn up to 45 degrees
    towards the nearest enemy ship, which is this ship at its end position if
    it will be the nearest; guided ones (s.16) may turn on a Leadership test;
    Tau missiles are steered every move (s.09)."""
    otype = m.ordnance_type
    if otype == "torpedo_seeking":
        pts = [(end[0], end[1])] + [(s.x, s.y) for s in my_ships if s.id != ship.id]
        tx, ty = min(pts, key=lambda p: math.hypot(p[0] - m.x, p[1] - m.y))
        want = math.degrees(math.atan2(ty - m.y, tx - m.x)) % 360
        diff = (want - m.heading + 180) % 360 - 180
        return (m.heading + max(-45.0, min(45.0, diff))) % 360, 0.0
    if otype == "torpedo_guided_ld":
        return m.heading, guided_turn_chance(m, gs)
    if otype in ("torpedo_boarding", "torpedo_boarding_guided"):
        return m.heading, 1.0          # manned: turn up to 45 degrees as their owner wishes
    if otype == "torpedo_guided":
        return m.heading, 1.0          # Tau missiles: one 45-degree turn every move
    return m.heading, 0.0


def torpedo_reach(m: OrdnanceMarker) -> float:
    """How far a salvo can go in its next move: Tau missiles 20-40cm at their
    owner's choice (s.09), everything else its speed."""
    return 40.0 if m.ordnance_type == "torpedo_guided" else (m.speed or 0.0)


def _in_turn_cone(m: OrdnanceMarker, end: Point, r: float) -> bool:
    """Is `end` within a salvo's reach after a turn of up to 45 degrees?"""
    d = math.hypot(end[0] - m.x, end[1] - m.y)
    if d > torpedo_reach(m) + r + 1.0:
        return False
    if d <= r + 1.0:
        return True
    bearing = math.degrees(math.atan2(end[1] - m.y, end[0] - m.x)) % 360
    off = abs((bearing - m.heading + 180) % 360 - 180)
    return off <= 45.0 + math.degrees(math.asin(min(1.0, (r + 1.0) / d)))


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


# ── Targeting by expected VP ─────────────────────────────────────────────────

def poisson_pmf(mean: float, k: int) -> float:
    """P(X = k) for X ~ Poisson(mean)."""
    if mean <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-mean + k * math.log(mean) - math.lgamma(k + 1))


def poisson_at_least(mean: float, k: int) -> float:
    """P(X >= k) for X ~ Poisson(mean): a stand-in for the spread of hits."""
    if k <= 0:
        return 1.0
    if mean <= 0:
        return 0.0
    term, cdf = math.exp(-mean), 0.0
    for i in range(k):
        cdf += term
        term *= mean / (i + 1)
    return max(0.0, 1.0 - cdf)


_THREAT_CACHE: Dict = {}


def _opponent(player: int) -> int:
    return 2 if player == 1 else 1


def ship_threat_vp(ship: Ship, gs) -> float:
    """Expected VP the ship could take off its enemies in their next turn: every
    battery / lance mount that can bear (`_mount_bears`: in range + its move,
    facing) at the most valuable enemy it bears on, plus its launch bays
    (`bay_threat_vp`: strikes and the denial of the enemy's). Killing it
    removes this, crippling halves it (s.33: half firepower). Cached per
    position and damage."""
    key = (id(gs), gs.turn_number, gs.current_phase, ship.id, ship.hits_remaining,
           round(ship.x, 1), round(ship.y, 1), round(ship.heading))
    if key in _THREAT_CACHE:
        return _THREAT_CACHE[key]
    if len(_THREAT_CACHE) > 5000:
        _THREAT_CACHE.clear()
    foes = [t for t in gs.get_ships() if t.player != ship.player
            and not t.is_destroyed and not t.is_disengaged
            and t.status not in ("drifting_hulk", "burning_hulk")]
    total = 0.0
    for w in ship.weapons:
        wt = w.get("weapon_type")
        if wt not in ("battery", "lance"):
            continue
        h = (w.get("strength") or 0) * (lance_p(w) if wt == "lance" else 0.35)
        if ship.is_crippled:
            h *= 0.5
        best = max((value_per_hit(t, gs) for t in foes if _mount_bears(ship, w, t)), default=0.0)
        total += h * best
    # its launch bays too (owner: carrier doctrine; already halved when crippled)
    total += bay_threat_vp(ship, gs)
    _THREAT_CACHE[key] = total
    return total


# ── Air power (owner: carrier doctrine) ─────────────────────────────────────
# A carrier's bays are worth what they can do to us (strikes) and what they
# deny us (each fighter can stop one of our strike squadrons), so the side with
# more launch capacity gains by killing the other's carriers (air supremacy),
# and the side with less protects its carriers and flies more interception.

# Share of a carrier's bays that act in a given turn (it launches, then must
# Reload Ordnance; it may also hold them back): judgement
AIR_THREAT_WEIGHT = 0.5


def _bays(ship):
    return [w for w in ship.weapons if w.get("weapon_type") == "launch_bay"]


def launch_capacity(gs, player: int) -> int:
    """Squadrons `player`'s ships in play could launch at once (bay strengths,
    crippled / braced halved; random bays at their listed strength)."""
    from .ordnance import bay_launch_capacity
    return sum(bay_launch_capacity(s, _bays(s), None)[0] for s in gs.get_ships()
               if s.player == player and not s.is_destroyed and not s.is_disengaged
               and _bays(s))


def air_balance(gs, player: int):
    """(our launch capacity, the enemy's)."""
    return launch_capacity(gs, player), launch_capacity(gs, 3 - player)


def bay_threat_vp(ship: Ship, gs) -> float:
    """Expected VP the ship's launch bays are worth to its side per turn
    (owner: carrier doctrine): its strike squadrons (bomber / assault boat
    types) at a bomber squadron's value against its enemies' ships on average,
    plus its fighters denying the enemy's strikes (each stops one squadron, up
    to the enemy's own launch capacity) at a bomber squadron's value against its
    own side; x AIR_THREAT_WEIGHT. Killing it removes this, crippling halves
    the bays (in ship_threat_vp)."""
    from .ordnance import craft_roles, craft_stats, bay_launch_capacity
    from .waves import bomber_squadron_value
    bays = _bays(ship)
    if not bays:
        return 0.0
    n = bay_launch_capacity(ship, bays, None)[0]
    if n <= 0:
        return 0.0
    roles = set()
    for w in bays:
        for ct in w.get("craft_types", []):
            roles |= set(craft_roles(craft_stats(ct, bays)[0]))
    live = [t for t in gs.get_ships() if not t.is_destroyed and not t.is_disengaged
            and not t.is_hulk]
    foes = [t for t in live if t.player != ship.player]
    own = [t for t in live if t.player == ship.player]
    v = 0.0
    if roles & {"bomber", "assault_boat"} and foes:
        v += n * sum(bomber_squadron_value(t, gs) for t in foes) / len(foes)
    if "fighter" in roles and own:
        enemy_cap = launch_capacity(gs, 3 - ship.player)
        v += min(n, enemy_cap) * sum(bomber_squadron_value(t, gs) for t in own) / len(own)
    return AIR_THREAT_WEIGHT * v


def explosion_odds(ship: Ship):
    """(P plasma drive overload, P warp drive implosion) when a capital ship is
    destroyed (Catastrophic Damage, 2D6: 9-11 / 12); the Mercury rolls 3D6
    (over 12 counts as 12). Escorts and small defences never explode (they
    become blast markers)."""
    from .combat import becomes_blast_marker
    if becomes_blast_marker(ship):
        return 0.0, 0.0
    if "catastrophic_3d6" in ship.special_rules:
        p = [0.0] * 19
        for a in range(1, 7):
            for b in range(1, 7):
                for c in range(1, 7):
                    p[a + b + c] += 1 / 216
        plasma = p[9] + p[10] + p[11]
        warp = sum(p[12:])
        return plasma, warp
    return 9 / 36, 1 / 36


def death_explosion_vp(ship: Ship, gs, player: int, at=None) -> float:
    """Net expected VP for `player` of `ship` blowing up (at its position, or
    `at`) if it is destroyed: plasma overload (half its starting hits) or warp
    implosion (all of them) over 3D6cm (explosion_vp)."""
    pp, pw = explosion_odds(ship)
    if not pp and not pw:
        return 0.0
    centre = at or (ship.x, ship.y)
    return (pp * (explosion_vp(centre, ship.hits_max // 2, gs, player, ship.id)
                  + plasma_ordnance_vp(centre, gs, player))
            + pw * explosion_vp(centre, ship.hits_max, gs, player, ship.id))


def plasma_ordnance_vp(centre, gs, player: int) -> float:
    """A plasma drive overload destroys all ordnance within its 3D6cm radius
    (Appendix 5, 9-11; To do 11 c): for `player`, the threat of the enemy's
    markers removed (marker_threat_vp) minus what our own removed markers would
    have done (their threat to the enemy), each at the chance the radius
    (3D6, mean 10.5) reaches it."""
    total = 0.0
    for o in gs.ordnance:
        m = OrdnanceMarker.from_dict(o)
        if m.cap_ship_id:
            continue
        d = math.hypot(m.x - centre[0], m.y - centre[1])
        p = p_sum_at_least(3, math.ceil(d)) if d > 3 else 1.0
        if p <= 0:
            continue
        if m.owner_player == player:
            total -= p * marker_threat_vp(m, gs, _opponent(player))
        else:
            total += p * marker_threat_vp(m, gs, player)
    return total


def damage_vp(target: Ship, gs, mean_hits: float) -> float:
    """Expected VP from `mean_hits` hull hits on a target (s.38): its value if
    destroyed, a quarter if crippled, plus a little for each hit (later
    damage, crits). Owner: also the damage it would have done that we prevent,
    destroying it removes its next turn's threat (ship_threat_vp), crippling
    halves it, and a destroyed ship may explode among the ships near it
    (death_explosion_vp: good for us near enemies, bad near our own ships)."""
    v = ship_value(target, gs)
    rem = max(1, target.hits_remaining)
    p_kill = poisson_at_least(mean_hits, rem)
    to_cripple = rem - target.hits_max // 2
    p_crip = 0.0 if target.is_crippled or to_cripple <= 0 else poisson_at_least(mean_hits, to_cripple)
    from .scenarios import kill_bonus_vp
    base = (p_kill * (v + kill_bonus_vp(gs, target)) + max(0.0, p_crip - p_kill) * v * 0.25
            + min(mean_hits, rem) * value_per_hit(target, gs) * 0.2)
    if p_kill <= 0 and p_crip <= 0:
        return base
    threat = ship_threat_vp(target, gs)
    prevented = p_kill * threat + max(0.0, p_crip - p_kill) * 0.5 * threat
    boom = p_kill * death_explosion_vp(target, gs, _opponent(target.player)) if p_kill > 0.01 else 0.0
    return base + prevented + boom


def shot_vp(attacker: Ship, weapon: dict, target: Ship, gs, committed: float = 0.0) -> float:
    """Marginal expected VP of firing `weapon` at `target`, given `committed`
    expected hull hits already planned against it this phase (so the AI stops
    piling fire on a ship that is probably dead, and doesn't spread too thin)."""
    from .combat import expected_hits
    from .geometry import current_shields
    raw = expected_hits(attacker, weapon, target, gs)     # with column shifts
    if raw <= 0:
        return 0.0
    shields = current_shields(target, gs.get_blast_markers())
    # `committed` counts all expected hits planned so far; shields take the first
    before = max(0.0, committed - shields)
    after = max(0.0, committed + raw - shields)
    # shields knocked down open the target to the rest of the fleet's fire
    shield_hits = min(raw, max(0.0, shields - committed))
    alive = 1.0 - poisson_at_least(before, max(1, target.hits_remaining))
    return (damage_vp(target, gs, after) - damage_vp(target, gs, before)
            + shield_hits * value_per_hit(target, gs) * 0.1 * alive)


def intercept_gain(gs, player: int, target: OrdnanceMarker, already: int = 0) -> float:
    """VP a fighter squadron saves by meeting `target` (s.19: both markers are
    removed). A torpedo salvo or a mine is one marker: the whole of its threat
    goes, however strong the salvo. A wave meets fighters one squadron at a
    time (s.25), lead first: the fighter removes only the squadron it meets
    (`already` fighters have taken the ones in front). Resilient craft save on
    4+, so they are worth half."""
    from .waves import members
    if target.wave_id:
        ms = members([OrdnanceMarker.from_dict(o) for o in gs.ordnance], target.wave_id)
        if already >= len(ms):
            return 0.0
        hit = ms[already]
    else:
        if already:
            return 0.0                       # one fighter is enough for one marker
        hit = target
    mine = [s for s in gs.get_ships() if s.player == player
            and not s.is_destroyed and not s.is_disengaged]
    best = 0.0
    for s in mine:
        h, _ = marker_hits(s, hit, (s.x, s.y), [(s.x, s.y)], mine, gs)
        best = max(best, h * value_per_hit(s, gs))
    if hit.resilient_save:
        best *= 0.5
    return best


def explosion_vp(centre, strength: int, gs, player: int, exclude_id: str = "") -> float:
    """Net expected VP for `player` of a ship exploding at `centre` (s.34,
    combat.resolve_explosion): every ship within a 3D6cm radius takes
    `strength` lance shots hitting on 4+, less its shields; enemy losses count
    for us, our own against us. Finishing a ship off adds part of its value."""
    import math as _m
    from .geometry import current_shields
    total = 0.0
    bms = gs.get_blast_markers()
    for s in gs.get_ships():
        if s.id == exclude_id or s.is_destroyed or s.is_disengaged:
            continue
        d = _m.hypot(s.x - centre[0], s.y - centre[1])
        p_in = 1.0 - p_sum_at_most(3, max(0, _m.ceil(d) - 1))
        if p_in <= 0:
            continue
        hits = max(0.0, strength * 0.5 - current_shields(s, bms))
        if hits <= 0:
            continue
        v = min(hits, s.hits_remaining) * value_per_hit(s, gs)
        if hits >= s.hits_remaining:
            v += ship_value(s, gs) * 0.3
        total += p_in * v * (1 if s.player != player else -1)
    return total


def hulk_shot_vp(hulk: Ship, gs, player: int) -> float:
    """Expected VP for `player` of putting at least one hit on an enemy hulk.
    It already scores as destroyed (s.38), so the value is the re-rolled
    Catastrophic Damage result (owner ruling): 9-11 plasma drive overload
    (half its starting hits as blast strength), 12 warp drive implosion (all of
    them), 7-8 a burning hulk that may blow up at its next re-roll (10 in 36,
    at half value), 2-6 a drifting hulk (nothing). Explosions hurt whoever is near:
    with our own ships close by, the value goes negative. Not counted: the
    Holding the Field points a removed hulk no longer gives."""
    centre = (hulk.x, hulk.y)
    plasma = explosion_vp(centre, hulk.hits_max // 2, gs, player, hulk.id)
    warp = explosion_vp(centre, hulk.hits_max, gs, player, hulk.id)
    p_plasma, p_warp, p_burn = 9 / 36, 1 / 36, 11 / 36
    now = p_plasma * plasma + p_warp * warp
    # A new burning hulk re-rolls in its next movement phase (explodes 10 in
    # 36); half value, as ships will have moved by then
    if_explodes = now / (p_plasma + p_warp)
    later = 0.0 if hulk.status == "burning_hulk" else p_burn * (10 / 36) * 0.5 * if_explodes
    return now + later


def _poisson_at_least(lam: float, k: int) -> float:
    """P(X >= k) for X ~ Poisson(lam)."""
    import math as _m
    if k <= 0:
        return 1.0
    if lam <= 0:
        return 0.0
    term, cdf = _m.exp(-lam), 0.0
    for i in range(k):
        cdf += term
        term *= lam / (i + 1)
    return max(0.0, 1.0 - cdf)


def _mount_bears(e: Ship, w: dict, t: Ship) -> bool:
    """Could enemy `e`'s weapon `w` fire at `t` in its next turn? In range +
    its move, and facing: a port broadside (arcs left only) covers ships on its
    left side, a starboard one ships on its right (turning can swing a
    broadside across that whole side, but not onto the other one); other
    mounts count within their arc after a turn of up to its turn angle."""
    import math as _m
    from .combat import check_weapon_in_arc
    if _m.hypot(e.x - t.x, e.y - t.y) > (w.get("range_cm") or 0) + (e.speed or 0):
        return False
    arcs = w.get("arcs") or []
    h = _m.radians(e.heading)
    cross = _m.cos(h) * (t.y - e.y) - _m.sin(h) * (t.x - e.x)
    if arcs == ["left"]:
        return cross > 0
    if arcs == ["right"]:
        return cross < 0
    turn = e.turn_angle or 0
    for dh in (0, -turn, turn):
        turned = e if not dh else Ship.from_dict({**e.to_dict(), "heading": (e.heading + dh) % 360})
        if check_weapon_in_arc(turned, w, t.x, t.y):
            return True
    return False


def mount_hits(e: Ship, w: dict, t: Ship) -> float:
    """Expected hits of enemy `e`'s battery / lance mount `w` on `t` as it
    stands (its position and heading): batteries 0.35 a firepower point
    against Armour 5+, scaled to the Armour facing `e` would hit (`armor_vs`
    from e's position; To do 8 a: a 6+ prow really is safer than a 5+ side);
    lances 0.5 a lance whatever the Armour (they hit on 4+)."""
    st = w.get("strength") or 0
    if w.get("weapon_type") == "lance":
        return st * lance_p(w)
    return st * 0.35 * p_hit(t.armor_vs(e.x, e.y)) / p_hit(5)


def enemy_fire_plan(gs, player: int) -> dict:
    """Where the enemy's guns are expected to go in its next turn, assuming it
    focuses fire (owner: optimal play concentrates, it doesn't split): each
    enemy battery / lance mount goes wholly to the ship of `player` it adds the
    most expected VP against (`_mount_bears`; 0.35 a battery point, 0.5 a
    lance, scaled to the Armour facing it would hit, mount_hits; that enemy
    ship's first mount on a target loses the target's shields), given the
    hits already planned on it: value per hit up to the
    hits it has left, plus half its value times P(those hits finish it).
    Biggest mounts are placed first. Returns {ship id: expected hits}."""
    from .geometry import current_shields
    bms = gs.get_blast_markers()
    ours = [s for s in gs.get_ships() if s.player == player
            and not s.is_destroyed and not s.is_disengaged]
    planned = {t.id: 0.0 for t in ours}
    shields = {t.id: current_shields(t, bms) for t in ours}
    firing = set()                     # (enemy id, target id) pairs already shooting

    def value(t, h):
        rem = max(1, t.hits_remaining)
        vph = max(1.0, value_per_hit(t, gs))        # points unknown: still worth something
        return (vph * min(h, rem)
                + 0.5 * max(ship_value(t, gs), vph * t.hits_max) * _poisson_at_least(h, rem))
    mounts = []
    for e in gs.get_ships():
        if e.player == player or e.is_destroyed or e.is_disengaged:
            continue
        for w in e.weapons:
            wt = w.get("weapon_type")
            if wt not in ("battery", "lance"):
                continue
            h = (w.get("strength") or 0) * (lance_p(w) if wt == "lance" else 0.35)
            if h > 0:
                mounts.append((h, e, w))
    mounts.sort(key=lambda m: -m[0])
    for _h, e, w in mounts:
        best, best_t, best_dh = 0.0, None, 0.0
        for t in ours:
            if not _mount_bears(e, w, t):
                continue
            h = mount_hits(e, w, t)          # on the Armour facing it would hit
            dh = h if (e.id, t.id) in firing else max(0.0, h - shields[t.id])
            gain = value(t, planned[t.id] + dh) - value(t, planned[t.id])
            if gain > best:
                best, best_t, best_dh = gain, t, dh
        if best_t is not None:
            if (e.id, best_t.id) not in firing:
                firing.add((e.id, best_t.id))
            planned[best_t.id] += best_dh
    return planned


def incoming_hits(ship: Ship, gs) -> float:
    """Expected hits the enemy's guns put on `ship` in their next turn when it
    focuses fire (enemy_fire_plan). An enemy between two of our ships can
    turn port guns on one and starboard guns on the other, never both on one
    (owner)."""
    return enemy_fire_plan(gs, ship.player).get(ship.id, 0.0)


# ── Risk preference (owner, To do 2) ─────────────────────────────────────────
# With a turn limit the AI plays for the win, not for expected VP: behind
# with few turns left it gambles, ahead it plays safe. Choices with uncertain
# outcomes are compared by their certainty equivalent: the sure VP change
# worth the same chance of winning (the expert search uses the same spread,
# lookahead_ai.win_score).

def outcome_sigma(turns_left: int, mean_value: float, activity: float,
                  total_pts: float) -> float:
    """Spread of the final VP margin from the fighting still to come: a turn's
    swing is lumpy (a ship of value V dies or it doesn't: variance about V x
    its expected VP), so variance ~ turns left x mean ship value x both sides'
    expected VP a turn (`activity`), floored at 2% of the points on the table
    (the dice never vanish)."""
    sigma = math.sqrt(max(0, turns_left) * max(0.0, mean_value) * max(0.0, activity))
    return max(sigma, 0.02 * (total_pts or 1))


def game_risk(gs, player: int):
    """(margin, sigma) for `player` with a turn limit, else None: the VP margin
    so far (victory_points, s.38) and the spread of the turns left
    (outcome_sigma, activity from both fleets' expected hits next shooting
    phase at each target's value per hit)."""
    limit = getattr(gs, "turn_limit", None)
    if not limit:
        return None
    from .victory_points import calculate_victory_points
    vp = calculate_victory_points(gs)
    enemy = 3 - player
    margin = vp[player]["total"] - vp[enemy]["total"]
    from .scenarios import scenario_margin_vp
    margin += scenario_margin_vp(gs, player)     # e.g. Domination points (To do 2)
    ships = [s for s in gs.get_ships() if not s.is_destroyed and not s.is_disengaged]
    total = sum(s.points_value or 0 for s in gs.get_ships()) or 1
    mean_value = (sum(s.points_value or 0 for s in ships) / len(ships)) if ships else 0.0
    by_id = {s.id: s for s in ships}
    activity = 0.0
    for side in (player, enemy):
        for sid, hits in fleet_hits_on(gs, side).items():
            t = by_id.get(sid)
            if t is not None:
                activity += hits * value_per_hit(t, gs)
    turns_left = max(0, limit - gs.turn_number + 1)
    return margin, outcome_sigma(turns_left, mean_value, activity, total)


def certainty_equivalent(gs, player: int, outcomes) -> float:
    """The sure VP change worth the same as a gamble `outcomes` [(chance, VP
    change for `player`)], given the game state: its expected value without a
    turn limit; with one, the VP change d with P(win | margin + d) equal to the
    gamble's expected chance of winning (normal approximation, game_risk).
    Behind, a gamble is worth more than its average; ahead, less."""
    ev = sum(p * d for p, d in outcomes)
    risk = game_risk(gs, player)
    if risk is None:
        return ev
    from statistics import NormalDist
    margin, sigma = risk
    nd = NormalDist()
    total_p = sum(p for p, _d in outcomes) or 1.0
    win = sum(p * nd.cdf((margin + d) / sigma) for p, d in outcomes) / total_p
    win = min(1 - 1e-12, max(1e-12, win))
    return sigma * nd.inv_cdf(win) - margin


def disengage_gain(ship: Ship, gs, ld: int, contribution: float,
                   fire_outcomes=None) -> float:
    """Expected VP gained by trying to disengage now (s.37, VP s.38) instead of
    fighting on for another turn. Staying risks the enemy's next turn
    (incoming_hits as a Poisson count): destroyed -> the full value, newly
    crippled -> 25%. Leaving concedes 10% (25% if crippled, which a crippled
    ship concedes anyway). Either way the ship's guns are lost this turn (a
    failed test also forbids firing), worth `contribution`.
    gain = P(pass) x (risk avoided - extra VP conceded) - contribution. With a
    turn limit the risk is the certainty equivalent of staying (owner: play
    for the win; certainty_equivalent)."""
    v = ship_value(ship, gs)
    lam = incoming_hits(ship, gs)
    left = max(1, ship.hits_remaining)
    p_kill = _poisson_at_least(lam, left)
    from .scenarios import kill_bonus_vp, warp_loss_chance
    bonus = kill_bonus_vp(gs, ship)
    risk = p_kill * (v * (0.75 if ship.is_crippled else 1.0) + bonus)
    if not ship.is_crippled:
        to_cripple = left - ship.hits_max // 2
        if to_cripple > 0:
            risk += max(0.0, _poisson_at_least(lam, to_cripple) - p_kill) * 0.25 * v
    extra = 0.0 if ship.is_crippled else 0.10 * v
    # Warp Storm: a ship that leaves may be lost in the warp at the end (the
    # full value instead of the 10% / 25% it concedes)
    q_warp = warp_loss_chance(gs, ship)
    extra += q_warp * v * (0.75 if ship.is_crippled else 0.90)
    p_pass = p_sum_at_most(2, ld) if ld > 1 else 0.0
    if "necron" in ship.special_rules:
        p_pass = 1.0                       # Without a Trace: no test needed
    from .movement import sirens_summon
    if sirens_summon(ship, gs):
        p_pass = 0.0                       # Siren's Summon: no Leadership tests
    esc = _remastered_escort_terms(ship, gs, lam)
    if esc is not None:
        # Remastered escort VP (p.121): staying risks VP only if the whole
        # squadron dies; leaving concedes 25% of the squadron (crippled) or 10%
        p_wipe, v_sq, crippled = esc
        risk = p_wipe * v_sq
        extra = (0.25 if crippled else 0.10) * v_sq
        if getattr(gs, "turn_limit", None):
            fire = fire_outcomes or [(1.0, contribution)]
            dmg = [(p_wipe, -v_sq), (1 - p_wipe, 0.0)]
            stay = certainty_equivalent(gs, ship.player,
                                        [(q1 * q2, d1 + d2) for q1, d1 in dmg for q2, d2 in fire])
            go = certainty_equivalent(gs, ship.player,
                                      [(p_pass, -extra)] + [((1 - p_pass) * q, d) for q, d in dmg])
            return go - stay
        return p_pass * (risk - extra) - contribution
    if getattr(gs, "turn_limit", None):
        # Owner: play for the win. Staying is a gamble (destroyed, crippled or
        # untouched), leaving a sure loss: compared by certainty equivalent,
        # so a fleet behind near the end fights on and one ahead leaves.
        p_crip = 0.0
        if not ship.is_crippled and left - ship.hits_max // 2 > 0:
            p_crip = max(0.0, _poisson_at_least(lam, left - ship.hits_max // 2) - p_kill)
        loss_kill = v * (0.75 if ship.is_crippled else 1.0) + bonus
        dmg = [(p_kill, -loss_kill), (p_crip, -0.25 * v), (1 - p_kill - p_crip, 0.0)]
        # The guns given up are a gamble too (To do 2): staying is both
        # gambles together; trying gives a sure -extra on a pass and the damage
        # without firing on a failure (a failed test forbids firing, s.37)
        fire = fire_outcomes or [(1.0, contribution)]
        stay = certainty_equivalent(gs, ship.player,
                                    [(q1 * q2, d1 + d2) for q1, d1 in dmg for q2, d2 in fire])
        go = certainty_equivalent(gs, ship.player,
                                  [(p_pass, -extra)] + [((1 - p_pass) * q, d) for q, d in dmg])
        return go - stay
    return p_pass * (risk - extra) - contribution


def _remastered_escort_terms(ship: Ship, gs, lam: float):
    """(P(the whole squadron dies next enemy turn), the squadron's value,
    crippled?) for an escort in a squadron under the Remastered escort VP
    option, else None. Each surviving member dies with the chance this ship
    does (`lam` hits on it; independence assumed)."""
    if not getattr(gs, "rule_remastered_escort_vp", False) or ship.ship_type != "escort" \
            or not ship.squadron_id:
        return None
    sq = [s for s in gs.get_ships() if s.squadron_id == ship.squadron_id
          and s.player == ship.player]
    alive = [s for s in sq if not s.is_destroyed and not s.is_disengaged]
    dead = sum(1 for s in sq if s.is_destroyed or s.hits_remaining <= 0)
    p_one = _poisson_at_least(lam, max(1, ship.hits_remaining))
    v_sq = sum(ship_value(s, gs) for s in sq)
    return p_one ** max(1, len(alive)), v_sq, dead >= (len(sq) + 1) // 2


def added_vp(target: Ship, gs, committed: float, hits: float, shields: bool = True) -> float:
    """Expected VP that `hits` more hits add to a target that already has
    `committed` expected hits planned on it this phase: shields take the first
    hits (direct fire; ordnance ignores shields, s.11 / s.15: shields=False),
    then damage_vp's thresholds (destroy, cripple)."""
    from .geometry import current_shields
    sh = current_shields(target, gs.get_blast_markers()) if shields else 0
    before = max(0.0, committed - sh)
    after = max(0.0, committed + hits - sh)
    return damage_vp(target, gs, after) - damage_vp(target, gs, before)


def torpedo_salvo_hits(strength: int, target: Ship, gs, from_xy) -> float:
    """Expected hits (torpedoes ignore shields) of a torpedo salvo of `strength` reaching
    `target`: its turrets (plus massed turrets) shoot torpedoes down first,
    each success one torpedo (Ork turrets 5+), then each torpedo hits its
    Armour facing the launcher's side."""
    from .ordnance import ordnance_turrets, get_massed_turret_bonus, turret_hit_on
    shots = ordnance_turrets(target, gs) + get_massed_turret_bonus(target, gs.get_ships())
    p_turret = max(0, 7 - turret_hit_on(target)) / 6.0
    left = max(0.0, strength - shots * p_turret)
    return left * p_hit(target.armor_vs(*from_xy))


def strike_group_hits(n_fighters: int, n_bombers: int, target: Ship, gs,
                      f_save: int = 0, b_save: int = 0, extra_cap: int = 0) -> float:
    """Expected bomber hits of a wave on `target` (waves.wave_split_value with
    the target's turrets, massed turrets, CAP (+ `extra_cap` interceptors met
    on the way) and Armour)."""
    from .waves import wave_plan_inputs, wave_split_value
    inp = wave_plan_inputs(target, gs)
    p = (7 - (5 if inp.get("ork") else 4)) / 6.0
    t = inp["turrets"]
    return wave_split_value(n_fighters, n_bombers, t, t + inp["massed"],
                            inp["cap"] + extra_cap, inp["armour"], p, f_save, b_save,
                            inp["cap_save"])


def split_wave_survival(shots, groups: int = 2) -> list:
    """Chance each of `groups` waves survives the enemy guns on the way
    (strike_timeline "shots": one weapon's weighted dice in one shooting
    phase). One hit removes a whole wave (s.25), but each weapon fires at one
    marker, so splitting spreads the shots: the biggest go one to each wave in
    turn (the enemy shares its fire to remove as much as it can)."""
    load = [0.0] * max(1, groups)
    for n in sorted(shots or [], reverse=True):
        i = min(range(len(load)), key=lambda g: load[g])
        load[i] += n
    return [(5 / 6) ** (d * ENEMY_FIRE_AT_WAVE) for d in load]


def interception_cases(tl: dict) -> list:
    """[(probability, extra interceptors)] a strike meets on the way, from its
    strike_timeline: the target's reactive CAP and other enemy carriers'
    launches (REACTIVE_CAP_WEIGHT), enemy fighters already flying
    (AIRBORNE_INTERCEPT_WEIGHT); every mix of the two. Each interceptor meets
    the wave's lead like CAP (s.19 / s.25)."""
    react = tl.get("reactive_cap", 0) + tl.get("reactive_intercept", 0)
    air = tl.get("airborne_intercept", 0)
    r_cases = ([(REACTIVE_CAP_WEIGHT, react), (1 - REACTIVE_CAP_WEIGHT, 0)]
               if react else [(1.0, 0)])
    a_cases = ([(AIRBORNE_INTERCEPT_WEIGHT, air), (1 - AIRBORNE_INTERCEPT_WEIGHT, 0)]
               if air else [(1.0, 0)])
    return [(pr * pa, er + ea) for pr, er in r_cases for pa, ea in a_cases]


# Owner: damage sooner beats damage later (the target can dodge, repair, be
# finished by something else or fire back meanwhile; an earlier kill silences
# its guns sooner). Each ordnance phase of delay costs this factor.
PHASE_DISCOUNT = 0.85


def phase_weight(k: int) -> float:
    """Weight of a hit k ordnance phases from now (0 = this phase): x
    PHASE_DISCOUNT per phase, and x LATER_TURN_WEIGHT from the next game turn
    on (k >= 2: where the target will be is a guess by then). E.g. 1, 0.85,
    0.36, 0.31: 2 hits on a side within reach (2 x 0.85) beat 3 on the rear
    after a loop two phases longer (3 x 0.31)."""
    return PHASE_DISCOUNT ** k * (LATER_TURN_WEIGHT if k >= 2 else 1.0)


def travel_discount(dist: float, speed: float) -> float:
    """Ordnance aimed further away is worth less: the target moves, more
    turrets, fighters and blast markers on the way. 1 within one move, x
    PHASE_DISCOUNT per extra move."""
    import math as _m
    moves = max(1, _m.ceil(dist / max(1.0, speed)))
    return PHASE_DISCOUNT ** (moves - 1)


def hull_hits_vp(target: Ship, gs, committed: float, hits: float) -> float:
    """`hits` more expected ordnance hits on `target` (shields don't stop
    ordnance, s.11 / s.15), on the same scale as raid values
    (hit_and_run.raid_result_value: full value per hit) plus the focus bonus of
    crossing its cripple / destroy thresholds (added_vp). Used to compare
    bombers with assault boats and to pick strike targets."""
    rem = max(1, target.hits_remaining)
    hull = max(0.0, min(committed + hits, rem) - min(committed, rem))
    vph = max(1.0, value_per_hit(target, gs))
    return added_vp(target, gs, committed, hits, shields=False) + 0.8 * vph * hull


def plan_strike_targets(gs, player: int) -> dict:
    """Targets for `player`'s ship-attacking craft in flight (bombers, assault
    boats, multi-role craft; not on CAP), by expected VP with focus (owner):
    each wave (or lone squadron) goes to the enemy ship it adds the most to,
    counting what earlier groups are planned to do there, valued when it lands
    (strike_timeline: arrival phase, enemy guns on the way, the raid's repair
    window, every interception case on the way: reactive CAP and intercept,
    fighters already flying). Fighters in a wave follow it. Returns
    {marker id: target ship id}."""
    import math as _m
    from .models import OrdnanceMarker
    from .ordnance import craft_roles, attacks_ships
    from .waves import (expected_survivors, raid_squadron_value, bomber_squadron_value,
                        wave_plan_inputs)
    own = [OrdnanceMarker.from_dict(o) for o in gs.ordnance
           if o["owner_player"] == player and not o.get("cap_ship_id")]
    groups = {}
    for m in own:
        groups.setdefault(m.wave_id or m.id, []).append(m)
    enemies = [e for e in gs.get_ships() if e.player != player and not e.is_destroyed
               and not e.is_disengaged and e.status not in ("drifting_hulk", "burning_hulk")]
    plan, committed = {}, {}
    order = sorted(groups.values(), key=lambda g: -len(g))
    for g in order:
        if not any(attacks_ships(m.ordnance_type) for m in g):
            continue
        lead = g[0]
        speed = min((m.speed or 20) for m in g)
        f = sum(1 for m in g if craft_roles(m.ordnance_type) == ("fighter",))
        b = sum(1 for m in g if set(craft_roles(m.ordnance_type)) == {"bomber"})
        a = sum(1 for m in g if set(craft_roles(m.ordnance_type)) == {"assault_boat"})
        mr = [m for m in g if len(craft_roles(m.ordnance_type)) > 1
              and attacks_ships(m.ordnance_type)]
        best, best_t, best_hits = 0.0, None, 0.0
        for e in enemies:
            # Valued when it lands (To do 2): arrival phase, enemy guns on the way,
            # the raid's repair window; routes round obstacles (owner)
            route = best_route(lead.x, lead.y, e.x, e.y, gs, "craft", speed, target=e)
            d = _m.hypot(e.x - lead.x, e.y - lead.y) or 1.0
            tl = strike_timeline(lead.x, lead.y, speed, e, gs, player,
                                 max(1.0, route[2] / d), gs.active_player == player)
            if tl is None:
                continue
            c = committed.get(e.id, 0.0)
            # every interception case on the way: the target's reactive CAP,
            # other carriers' launches, fighters already flying (as planned
            # strikes, _strike_option)
            cases = interception_cases(tl)
            hits = v = 0.0
            if b:
                for w, ec in cases:
                    h = strike_group_hits(f, b, e, gs, extra_cap=ec)
                    hits += w * h
                    v += w * (hull_hits_vp(e, gs, c, h) if h else 0.0)
            if a or mr:
                inp = wave_plan_inputs(e, gs)
                p = (7 - (5 if inp.get("ork") else 4)) / 6.0
                n = a + len(mr)
                through = sum(w * expected_survivors(n, inp["turrets"] + inp["massed"],
                                                     inp["cap"] + ec, p) for w, ec in cases)
                per = raid_squadron_value(e, gs, player, lead.special_rules or [],
                                          end_phases=tl["end_phases"])
                if mr and getattr(gs, "rule_hit_and_run", True):
                    per_mr = max(per, bomber_squadron_value(e, gs))
                else:
                    per_mr = bomber_squadron_value(e, gs)
                v += through * ((a * per + len(mr) * per_mr) / max(1, n))
            v *= route[1] * tl["survival"] * phase_weight(tl["phase"])
            if v > best:
                best, best_t, best_hits = v, e, hits
        if best_t is None:
            continue
        committed[best_t.id] = committed.get(best_t.id, 0.0) + best_hits
        for m in g:
            plan[m.id] = best_t.id
    return plan


def fleet_hits_on(gs, player: int) -> Dict[str, float]:
    """Expected hits `player`'s batteries / lances in reach (range + the firing
    ship's move) could put on each enemy ship next shooting phase (0.35 a
    battery point scaled by its Armour, 0.5 a lance), before shields."""
    import math as _m
    ours = [s for s in gs.get_ships() if s.player == player
            and not s.is_destroyed and not s.is_disengaged]
    out = {}
    for e in gs.get_ships():
        if (e.player == player or e.is_destroyed or e.is_disengaged
                or e.status in ("drifting_hulk", "burning_hulk")):
            continue
        hits = 0.0
        armour_factor = p_hit(e.lowest_armor_value) / p_hit(5)
        for s in ours:
            d = _m.hypot(s.x - e.x, s.y - e.y)
            for w in s.weapons:
                wt = w.get("weapon_type")
                if wt not in ("battery", "lance") or d > (w.get("range_cm") or 0) + (s.speed or 0):
                    continue
                hits += (w.get("strength") or 0) * (lance_p(w) if wt == "lance" else 0.35 * armour_factor)
        out[e.id] = hits
    return out


def explosion_position_vp(ship: Ship, x: float, y: float, gs, enemy_plan: Dict[str, float],
                          our_hits: Dict[str, float]) -> float:
    """Owner: catastrophic damage and positioning. Net expected VP of the ship
    ending its move at (x, y), from explosions alone:
      - risk: any other ship, friend or foe, that may be destroyed before our
        next move and blow up with this ship inside its 3D6cm radius (our ships
        at the hits the enemy can focus on them, enemy_fire_plan; enemies at
        half the hits our fleet can put on them, fleet_hits_on);
      - opportunity: this ship itself, if it is likely to be destroyed, blowing
        up among enemies (good) or friends (bad) (death_explosion_vp), so a
        wounded ship gains by hugging enemy ships and keeping away from its own.
    Escorts never explode."""
    import math as _m
    from .geometry import current_shields
    shields = current_shields(ship, gs.get_blast_markers())
    vph = max(1.0, value_per_hit(ship, gs))
    risk = 0.0
    for o in gs.get_ships():
        if o.id == ship.id or o.is_destroyed or o.is_disengaged:
            continue
        pp, pw = explosion_odds(o)
        if not pp and not pw:
            continue
        lam = enemy_plan.get(o.id, 0.0) if o.player == ship.player else 0.5 * our_hits.get(o.id, 0.0)
        pd = poisson_at_least(lam, max(1, o.hits_remaining))
        if pd <= 0.001:
            continue
        d = _m.hypot(o.x - x, o.y - y)
        p_in = 1.0 - p_sum_at_most(3, max(0, _m.ceil(d) - 1))
        if p_in <= 0:
            continue
        hits = (pp * max(0.0, (o.hits_max // 2) * 0.5 - shields)
                + pw * max(0.0, o.hits_max * 0.5 - shields))
        risk += pd * p_in * min(hits, ship.hits_remaining) * vph
    lam_me = enemy_plan.get(ship.id, 0.0)
    pd_me = poisson_at_least(lam_me, max(1, ship.hits_remaining))
    bonus = 0.0
    if pd_me > 0.01:
        bonus = pd_me * death_explosion_vp(ship, gs, ship.player, at=(x, y))
    return bonus - risk


def fleet_focus_targets(gs, player: int) -> list:
    """Enemy ships ranked for the fleet to concentrate on (owner: focus fire,
    easier targets first): for each enemy, the expected hits the fleet's
    batteries / lances could put on it next turn (within range + the firing
    ship's move; 0.35 a battery point scaled by its Armour, 0.5 a lance), and
    the VP those hits add through its shields and damage thresholds
    (added_vp). Easier (low Armour / shields) and damaged ships rank first.
    Returns [(VP, enemy ship), ...] best first."""
    import math as _m
    ours = [s for s in gs.get_ships() if s.player == player
            and not s.is_destroyed and not s.is_disengaged]
    ranked = []
    for e in gs.get_ships():
        if (e.player == player or e.is_destroyed or e.is_disengaged
                or e.status in ("drifting_hulk", "burning_hulk")):
            continue
        hits = 0.0
        armour_factor = p_hit(e.lowest_armor_value) / p_hit(5)
        for s in ours:
            d = _m.hypot(s.x - e.x, s.y - e.y)
            for w in s.weapons:
                wt = w.get("weapon_type")
                if wt not in ("battery", "lance") or d > (w.get("range_cm") or 0) + (s.speed or 0):
                    continue
                h = (w.get("strength") or 0) * (lance_p(w) if wt == "lance" else 0.35 * armour_factor)
                hits += h
        if hits > 0:
            ranked.append((added_vp(e, gs, 0.0, hits), e))
    ranked.sort(key=lambda t: -t[0])
    return ranked


def _ship_hits_on(s: Ship, e: Ship) -> float:
    """Expected hits ship `s`'s batteries / lances could put on enemy `e` next
    turn (within range + its move), as fleet_focus_targets counts them."""
    import math as _m
    d = _m.hypot(s.x - e.x, s.y - e.y)
    armour_factor = p_hit(e.lowest_armor_value) / p_hit(5)
    hits = 0.0
    for w in s.weapons:
        wt = w.get("weapon_type")
        if wt not in ("battery", "lance") or d > (w.get("range_cm") or 0) + (s.speed or 0):
            continue
        hits += (w.get("strength") or 0) * (lance_p(w) if wt == "lance" else 0.35 * armour_factor)
    return hits


def fleet_focus_assignment(gs, player: int) -> dict:
    """Several focus targets (owner: focus fire, easier targets first; To do 1):
    each of our ships is given the enemy where its guns add the most VP
    (added_vp, through shields and damage thresholds) on top of what the ships
    already given to that enemy are expected to do. Biggest batteries choose
    first, then every ship reconsiders once with the others fixed. So fire
    piles onto a ship near a threshold, and moves to a second target once the
    first is covered or out of a ship's reach. {ship id: enemy id}; ships that
    reach no enemy are left out (they plan against their nearest enemy)."""
    ours = [s for s in gs.get_ships() if s.player == player
            and not s.is_destroyed and not s.is_disengaged]
    foes = [e for e in gs.get_ships() if e.player != player and not e.is_destroyed
            and not e.is_disengaged and not e.is_hulk]
    contrib = {s.id: {e.id: h for e in foes for h in [_ship_hits_on(s, e)] if h > 0}
               for s in ours}
    by_id = {e.id: e for e in foes}
    order = sorted((s for s in ours if contrib[s.id]),
                   key=lambda s: -max(contrib[s.id].values()))
    assign, load = {}, {e.id: 0.0 for e in foes}

    def pick(sid):
        return max(contrib[sid], key=lambda eid: (
            added_vp(by_id[eid], gs, load[eid], contrib[sid][eid]), contrib[sid][eid]))
    for s in order:
        eid = pick(s.id)
        assign[s.id] = eid
        load[eid] += contrib[s.id][eid]
    for s in order:                       # one round of second thoughts
        old = assign[s.id]
        load[old] -= contrib[s.id][old]
        eid = pick(s.id)
        assign[s.id] = eid
        load[eid] += contrib[s.id][eid]
    return assign


def position_exposure_hits(ship: Ship, x: float, y: float, heading: float, gs) -> float:
    """Expected hits the enemy's guns could put on `ship` if it ended its move
    at (x, y) and the enemy focused on it: every enemy battery / lance mount
    that could bear there (_mount_bears), on the Armour facing it would hit at
    our end heading (mount_hits, To do 8 a), less its shields once per enemy."""
    from .geometry import current_shields
    moved = Ship.from_dict({**ship.to_dict(), "x": x, "y": y, "heading": heading})
    shields = current_shields(ship, gs.get_blast_markers())
    total = 0.0
    for e in gs.get_ships():
        if e.player == ship.player or e.is_destroyed or e.is_disengaged:
            continue
        hits = sum(mount_hits(e, w, moved)
                   for w in e.weapons if w.get("weapon_type") in ("battery", "lance")
                   and _mount_bears(e, w, moved))
        total += max(0.0, hits - shields)
    return total


def ordnance_path_survival(x1: float, y1: float, x2: float, y2: float, gs,
                           kind: str = "torpedo") -> float:
    """Chance ordnance flying straight from (x1, y1) to (x2, y2) gets there,
    as the engine resolves it (ordnance.check_ordnance_vs_phenomena,
    check_ordnance_vs_blast; s.11 and Celestial Phenomena):
      torpedoes: a planet, asteroid field or warp rift on the way destroys
        them (they detonate on it); a gas / dust cloud on a 6; blast markers
        on a 6 (seeking torpedoes on 5+);
      attack craft ("craft"): an asteroid field or gas / dust cloud on a 6
        (dust: owner ruling), a warp rift outright, blast markers on a 6;
        planets don't harm them.
    Each kind of hazard is rolled once along the path (one test per move)."""
    from .los import _line_intersects_circle, _line_intersects_rect
    from .geometry import line_touches_trefoil
    p = 1.0
    for ph in gs.get_phenomena():
        t = ph.phenomenon_type
        if "planet" in t and ph.radius > 0:
            hit = _line_intersects_circle(x1, y1, x2, y2, ph.x, ph.y, ph.radius)
        else:
            hit = _line_intersects_rect(x1, y1, x2, y2, ph.x - ph.width / 2,
                                        ph.y - ph.height / 2, ph.x + ph.width / 2,
                                        ph.y + ph.height / 2)
        if not hit:
            continue
        if t == "warp_rift":
            return 0.0
        if kind == "craft":
            if t in ("asteroid_field", "gas_dust_cloud"):     # dust: owner ruling
                p *= 5 / 6
        else:
            if "planet" in t or t == "asteroid_field":
                return 0.0
            if t == "gas_dust_cloud":
                p *= 5 / 6
    if any(line_touches_trefoil(x1, y1, x2, y2, b.x, b.y, b.heading)
           for b in gs.get_blast_markers()):
        p *= (4 / 6) if kind == "seeking" else (5 / 6)
    return p


def _harmful_obstacles(x1, y1, x2, y2, gs, kind: str):
    """Obstacles on the segment that can destroy `kind` of ordnance, each as a
    list of detour waypoints just outside it (asteroid field / warp rift / dust
    corners, either side of a planet or blast marker)."""
    import math as _m
    from .los import _line_intersects_circle, _line_intersects_rect
    from .geometry import line_touches_trefoil, BLAST_MARKER_RADIUS_CM
    margin = 3.0
    dx, dy = x2 - x1, y2 - y1
    L = _m.hypot(dx, dy) or 1.0
    nx, ny = -dy / L, dx / L
    out = []
    for ph in gs.get_phenomena():
        t = ph.phenomenon_type
        planet = "planet" in t and ph.radius > 0
        if kind == "craft" and t not in ("asteroid_field", "warp_rift", "gas_dust_cloud"):
            continue
        if kind != "craft" and not (planet or t in ("asteroid_field", "warp_rift",
                                                    "gas_dust_cloud")):
            continue
        if planet:
            if not _line_intersects_circle(x1, y1, x2, y2, ph.x, ph.y, ph.radius):
                continue
            r = ph.radius + margin
            out.append([(ph.x + nx * r, ph.y + ny * r), (ph.x - nx * r, ph.y - ny * r)])
        else:
            hw, hh = ph.width / 2, ph.height / 2
            if not _line_intersects_rect(x1, y1, x2, y2, ph.x - hw, ph.y - hh,
                                         ph.x + hw, ph.y + hh):
                continue
            out.append([(ph.x + sx * (hw + margin), ph.y + sy * (hh + margin))
                        for sx in (-1, 1) for sy in (-1, 1)])
    for b in gs.get_blast_markers():
        if line_touches_trefoil(x1, y1, x2, y2, b.x, b.y, b.heading):
            r = BLAST_MARKER_RADIUS_CM + margin
            out.append([(b.x + nx * r, b.y + ny * r), (b.x - nx * r, b.y - ny * r)])
    return out


def attack_survival(target, gs) -> float:
    """Chance ordnance survives the moment it attacks `target`, as
    ordnance_movement._resolve_ship_contacts rolls it: destroyed on a 6 when
    the target has Miasma of Pestilence (Nurgle boon: ordnance attacking it
    counts as passing through blast markers), or under the Modern / Remastered
    blast marker rules when the target is in contact with blast markers."""
    if target is None:
        return 1.0
    if "miasma" in (getattr(target, "special_rules", None) or []):
        return 5 / 6
    from .optional_rules import blast_rules, in_blast_contact
    if blast_rules() != "standard" and in_blast_contact(target, gs.get_blast_markers(),
                                                         gs.get_ships()):
        return 5 / 6
    return 1.0


def best_route(x1: float, y1: float, x2: float, y2: float, gs, kind: str = "craft",
               speed: float = 20.0, max_turn: float = None, target=None):
    """Owner: attack craft (and, within their turns, torpedoes that can turn)
    may fly round obstacles. The best of the straight line, detours via a
    waypoint just outside each harmful obstacle on it, and detours of those
    detours (an obstacle on either leg gets its own waypoints, so a field
    behind a field is flown round too: two waypoints at most), scored by
    ordnance_path_survival x travel_discount(length). Attack craft turn freely
    (max_turn None); turning torpedoes only where every turn is at most
    `max_turn` degrees; standard torpedoes pass max_turn=0 (straight only).
    Returns (value 0-1, survival, length, first waypoint or None); craft
    re-plan every move, so they follow the rest of the route as they go."""
    import math as _m
    at_target = attack_survival(target, gs)    # Miasma / blast contact at the target

    def score(pts):
        if max_turn is not None:
            for a, b, c in zip(pts, pts[1:], pts[2:]):
                h1 = _m.degrees(_m.atan2(b[1] - a[1], b[0] - a[0]))
                h2 = _m.degrees(_m.atan2(c[1] - b[1], c[0] - b[0]))
                if abs((h2 - h1 + 180) % 360 - 180) > max_turn:
                    return None
        surv, length = at_target, 0.0
        for a, b in zip(pts, pts[1:]):
            surv *= ordnance_path_survival(a[0], a[1], b[0], b[1], gs, kind)
            length += _m.hypot(b[0] - a[0], b[1] - a[1])
        return surv * travel_discount(length, speed), surv, length

    start, end = (x1, y1), (x2, y2)
    v, surv, length = score([start, end])
    best = (v, surv, length, None)
    if surv >= at_target or max_turn == 0:
        return best

    def waypoints(a, b):
        return [w for group in _harmful_obstacles(a[0], a[1], b[0], b[1], gs, kind)
                for w in group]
    for w1 in waypoints(start, end):
        routes = [[start, w1, end]]
        routes += [[start, w1, w2, end] for w2 in waypoints(w1, end)]
        routes += [[start, w0, w1, end] for w0 in waypoints(start, w1)]
        for pts in routes:
            r = score(pts)
            if r is not None and r[0] > best[0] + 1e-9:
                best = (r[0], r[1], r[2], pts[1])
    return best


# ── Leading torpedo targets (owner) ─────────────────────────────────────────
# A straight salvo moves its speed in our ordnance phase, sits there while the
# enemy moves (a ship moving into it is attacked, s.15) and moves again in the
# enemy's ordnance phase. Where the target can be by then follows from its
# movement rules (s.10: at least half speed, straight for 10cm (cruisers) /
# 15cm (battleships) / 0 (escorts) before its one turn; s.7: Burn Retros drops
# the minimum and the distance before turning, at most half speed; All Ahead
# Full adds 4D6cm, no turn).

TORP_CONTACT_HALF_W = 1.25        # half the torpedo marker's width (geometry)
# Chance a target that could dodge does (it has other aims too): judgement
DODGE_WEIGHT = 0.5
# A catch on the salvo's second turn counts at this weight: the target sees it
# coming and its course after this move is a guess (judgement)
LATER_TURN_WEIGHT = 0.5


def seg_first_contact(x0, y0, x1, y1, cx, cy, radius):
    """Fraction t in [0, 1] along (x0, y0)->(x1, y1) where a point first comes
    within `radius` of (cx, cy), or None."""
    dx, dy = x1 - x0, y1 - y0
    fx, fy = x0 - cx, y0 - cy
    a = dx * dx + dy * dy
    c = fx * fx + fy * fy - radius * radius
    if c <= 0:
        return 0.0
    if a <= 1e-12:
        return None
    b = 2 * (fx * dx + fy * dy)
    disc = b * b - 4 * a * c
    if disc < 0:
        return None
    t = (-b - disc ** 0.5) / (2 * a)
    return t if 0.0 <= t <= 1.0 else None


def path_touches(path, px, py, radius) -> bool:
    """True if the polyline `path` passes within `radius` of (px, py)."""
    if len(path) == 1:
        return (path[0][0] - px) ** 2 + (path[0][1] - py) ** 2 <= radius * radius
    return any(seg_first_contact(a[0], a[1], b[0], b[1], px, py, radius) is not None
               for a, b in zip(path, path[1:]))


def turn_distance(ship) -> float:
    """Straight distance before a turn (s.10): battleships 15cm, other capital
    ships (all cruisers) 10cm, escorts any point."""
    if ship.ship_type == "escort":
        return 0.0
    return 15.0 if ship.ship_type == "battleship" else 10.0


class _Path(list):
    """A sampled move: a polyline with a prior weight."""
    weight = 1.0


# Prior on a sampled normal move: holding course vs each of the four turns
# (judgement; owner: a receding target sits between closing and abeam, which
# needs ships to hold course more often than any one turn)
MOVE_TURN_WEIGHTS = (0.4, 0.15)


def enemy_move_samples(ship):
    """Polylines for `ship`'s next movement: (normal, dodge). Normal moves go
    half to full speed, turning up to its turn angle after its turning
    distance; dodges need a special order: Burn Retros (0 to half speed, turn
    at once) or All Ahead Full (straight, +4D6cm: 14 on average)."""
    import math as _m
    spd = ship.effective_speed or 0
    start = (ship.x, ship.y)
    if ship.is_hulk or spd <= 0:
        return [_Path([start])], []
    ta = getattr(ship, "turn_angle", 45) or 45
    dt = turn_distance(ship)

    def poly(dist, turn, turn_at):
        h = _m.radians(ship.heading)
        first = min(dist, turn_at)
        p1 = (ship.x + first * _m.cos(h), ship.y + first * _m.sin(h))
        rest = dist - first
        if rest <= 0:
            return _Path([start, p1])
        h2 = h + _m.radians(turn)
        return _Path([start, p1, (p1[0] + rest * _m.cos(h2), p1[1] + rest * _m.sin(h2))])
    normal = []
    for d in sorted({spd / 2.0, 0.75 * spd, float(spd)}):
        for turn in (-ta, -ta / 2.0, 0.0, ta / 2.0, ta):
            if turn and d <= dt:
                continue
            normal.append(poly(d, turn, dt))
            normal[-1].weight = MOVE_TURN_WEIGHTS[0 if not turn else 1]
    dodge = [poly(d, turn, 0.0) if d else _Path([start])
             for d in (0.0, spd / 4.0, spd / 2.0) for turn in (-ta, 0.0, ta)
             if d or not turn]
    dodge.append(poly(spd + 14.0, 0.0, spd + 14.0))
    return normal, dodge


def torpedo_path_survival(x1, y1, x2, y2, gs, kind: str = "torpedo",
                          half_w: float = TORP_CONTACT_HALF_W) -> float:
    """ordnance_path_survival for a torpedo marker's full width: the worst of
    its centre line and its two edges (a field the edge clips still stops it)."""
    import math as _m
    d = _m.hypot(x2 - x1, y2 - y1)
    if d <= 1e-9:
        return ordnance_path_survival(x1, y1, x2, y2, gs, kind)
    nx, ny = -(y2 - y1) / d * half_w, (x2 - x1) / d * half_w
    return min(ordnance_path_survival(x1 + ox, y1 + oy, x2 + ox, y2 + oy, gs, kind)
               for ox, oy in ((0.0, 0.0), (nx, ny), (-nx, -ny)))


# ── Armour-facing approaches for turning salvos (owner) ─────────────────────
# Tau missiles, Leadership-guided and boarding torpedoes can turn up to 45
# degrees at the start of each move after launch (s.16; Tau missiles every
# move), and roll against the Armour facing they hit. Firing off to the side
# or taking a detour so the salvo comes in on a weaker facing (abeam on most
# Imperial ships, the rear on Ork cruisers) can be worth the longer flight.

# Contact weight by ordnance phase from now: phase_weight (sooner is better)
APPROACH_TURN_STEPS = (-1.0, -0.5, 0.0, 0.5, 1.0)


def _predicted_positions(target, our_phase: bool):
    """Target copies at the start of each of the next four ordnance phases:
    its weighted mean end after each of its next moves (enemy_move_samples),
    facing along its course. If it is our ordnance phase it hasn't moved yet:
    [now, after 1 move, after 1 move, after 2 moves]; in the enemy's phase it
    already has: [now, now, after 1, after 1]."""
    import dataclasses
    import math as _m
    paths = enemy_move_samples(target)[0]
    wsum = sum(p.weight for p in paths) or 1.0
    ex = sum(p.weight * p[-1][0] for p in paths) / wsum
    ey = sum(p.weight * p[-1][1] for p in paths) / wsum
    mv = 0.75 * (target.effective_speed or 0)
    h = _m.radians(target.heading)
    e1 = dataclasses.replace(target, x=ex, y=ey)
    e2 = dataclasses.replace(target, x=ex + mv * _m.cos(h), y=ey + mv * _m.sin(h))
    return [target, e1, e1, e2] if our_phase else [target, target, e1, e1]


def approach_plan(x, y, heading, speed, target, gs, player, strength,
                  arc_half=45.0, turn_now=True, max_turn=45.0, p_turn=1.0,
                  our_phase=True, boarding=False, tau=False, friends=(),
                  committed=0.0, lengths=None):
    """Best path for a salvo at (x, y) that can turn, against `target`: the
    first move's heading (within `arc_half` of `heading`; at launch the arc,
    in flight the 45-degree turn, `turn_now` False when it may not turn this
    phase), then a turn of up to `max_turn` at the start of each later move,
    four moves deep. Each path is followed to its first contact with the
    target where it will be (`_predicted_positions`); the hits roll against
    the Armour facing that contact (torpedoes use the facing they hit, s.15),
    after turrets. Friendly ships touched first take hits and cost their VP
    (owner: friendly fire is negative VP), except for boarding torpedoes.
    Value = VP x path survival x phase_weight (owner: sooner beats later;
    1, 0.85, 0.36, 0.31 by ordnance phase) x p_turn per turn made (Leadership-
    guided torpedoes test to turn) x 5/6 per later phase for Tau missiles
    (strength lost on 1s) x 1/2 for boarding torpedoes (raids, as marker_hits).
    `lengths`: move lengths to try (Tau missiles choose 20-40cm each move;
    others move their speed). Returns {"heading", "value", "hits", "armour",
    "phase"} or None."""
    import math as _m
    positions = _predicted_positions(target, our_phase)
    rt = target.base_radius + TORP_CONTACT_HALF_W
    phase_w = tuple(phase_weight(k) for k in range(4))     # owner: sooner is better
    if turn_now:
        firsts = sorted({round(heading + arc_half * f, 1) for f in (-1, -2 / 3, -1 / 3, 0,
                                                                     1 / 3, 2 / 3, 1)})
        # also straight at where it is and where it will be
        for p in positions:
            bearing = _m.degrees(_m.atan2(p.y - y, p.x - x))
            diff = (bearing - heading + 180) % 360 - 180
            if abs(diff) <= arc_half:
                firsts.append(round(heading + diff, 1))
        firsts = sorted(set(firsts))
    else:
        firsts = [heading]
    best = None

    lengths = tuple(lengths or (speed,))

    max_len = max(lengths)
    mid_len = sorted(lengths)[len(lengths) // 2]

    def walk(px, py, h, k, turns, left, lost):
        # Full choice of move lengths on the first two moves; later ones (a
        # guess anyway) at the middle length, to keep the search small
        for ln in (lengths if k <= 1 else (mid_len,)):
            step(px, py, h, k, turns, left, lost, ln)

    def step(px, py, h, k, turns, left, lost, ln):
        nonlocal best
        if k >= 4 or left <= 0:
            return
        rad = _m.radians(h)
        qx, qy = px + ln * _m.cos(rad), py + ln * _m.sin(rad)
        surv = torpedo_path_survival(px, py, qx, qy, gs)
        tgt = positions[k]
        t_hit = seg_first_contact(px, py, qx, qy, tgt.x, tgt.y, rt)
        seq = []
        for f in friends:
            t = seg_first_contact(px, py, qx, qy, f.x, f.y, f.base_radius + TORP_CONTACT_HALF_W)
            if t is not None and (t_hit is None or t < t_hit):
                seq.append((t, f))
        for _t, f in sorted(seq, key=lambda c: c[0]):
            hh = left * p_hit(f.armor_vs(px, py))
            lost += added_vp(f, gs, 0.0, hh, shields=False)
            left -= hh
        if t_hit is not None and left > 0:
            if t_hit <= 1e-9 and k > 0:
                # The target moved onto the waiting salvo (s.15): it meets the
                # salvo with the side it was moving with, seen from where the
                # salvo sits as the target's base first touches it
                import dataclasses
                th = _m.radians(tgt.heading)
                tgt = dataclasses.replace(tgt, x=px - rt * _m.cos(th), y=py - rt * _m.sin(th))
                back = (px, py)
            else:
                cx, cy = px + (qx - px) * t_hit, py + (qy - py) * t_hit
                back = (cx - _m.cos(rad), cy - _m.sin(rad))   # just before contact
            arm = tgt.armor_vs(*back)
            s_eff = left * ((5 / 6) ** k if tau else 1.0)
            hits = torpedo_salvo_hits(s_eff, tgt, gs, back)
            v = added_vp(target, gs, committed, hits, shields=False)
            if boarding:
                v *= 0.5
            v = (v - lost) * surv_acc[0] * surv * phase_w[k] * (p_turn ** turns)
            # ties: the earlier hit, then the heading nearest the target's bearing
            dev = abs((first[0] - bearing0 + 180) % 360 - 180)
            key = (round(v, 6), -k, -dev)
            if best is None or key > best["_key"]:
                best = {"heading": first[0] % 360, "value": v, "hits": hits, "armour": arm,
                        "phase": k, "_key": key}
            return
        if surv <= 0 or k + 1 >= 4:
            return                                   # dies on the way / out of moves
        nxt = positions[k + 1]
        if _m.hypot(nxt.x - qx, nxt.y - qy) > (3 - k) * max_len + rt:
            return                                   # can no longer reach it
        surv_acc[0] *= surv
        steps = APPROACH_TURN_STEPS if k == 0 else (-1.0, 0.0, 1.0)
        for f in (steps if max_turn > 0 else (0.0,)):
            d = f * max_turn
            walk(qx, qy, h + d, k + 1, turns + (1 if d else 0), left, lost)
        surv_acc[0] /= surv

    surv_acc = [1.0]
    bearing0 = _m.degrees(_m.atan2(target.y - y, target.x - x))
    for h0 in firsts:
        first = [h0]
        walk(x, y, h0, 0, 0, float(strength), 0.0)
    if best is not None:
        best.pop("_key", None)
    return best


def salvo_approach(marker, gs, target=None, our_phase=None):
    """approach_plan for a salvo already in flight (the AI's in-flight turn):
    its target (marker.torp_target_id, else the nearest enemy ship), a turn of
    up to 45 degrees now, Tau missiles 20-40cm a move, Leadership-guided
    salvos at the launcher's Ld odds per later turn. None if no target."""
    from .ordnance import is_boarding_torpedo
    ships = [s for s in gs.get_ships() if not s.is_destroyed and not s.is_disengaged]
    enemies = [s for s in ships if s.player != marker.owner_player and not s.is_hulk]
    if target is None:
        target = next((s for s in enemies if s.id == getattr(marker, "torp_target_id", "")),
                      None)
    if target is None and enemies:
        import math as _m
        target = min(enemies, key=lambda s: _m.hypot(s.x - marker.x, s.y - marker.y))
    if target is None:
        return None
    if our_phase is None:
        our_phase = gs.active_player == marker.owner_player
    boarding = is_boarding_torpedo(marker)
    tau = marker.ordnance_type == "torpedo_guided"
    p_turn = 1.0
    if marker.ordnance_type == "torpedo_guided_ld":
        launcher = next((s for s in ships if s.id == marker.launched_by), None)
        if launcher is None:
            return None
        p_turn = p_sum_at_most(2, min(10, launcher.leadership or 8))
    friends = [] if boarding else [
        s for s in ships if s.player == marker.owner_player
        and s.id not in (marker.launch_exempt_ships or [])]
    return approach_plan(marker.x, marker.y, marker.heading, marker.speed or 30.0, target, gs,
                         marker.owner_player, marker.strength, arc_half=45.0,
                         p_turn=p_turn, our_phase=our_phase, boarding=boarding, tau=tau,
                         friends=friends, lengths=(20.0, 30.0, 40.0) if tau else None)


# ── Strikes valued when they land (To do 2) ─────────────────────────────────
# Owner discussion (HANDOFF "Ordnance strike planning"): a strike is worth what
# it does when the wave arrives, discounted by how long that takes, after the
# losses on the way, with its crits valued at the right point in the turn.

# Chance the enemy spends a gun that could hit our wave on it rather than on
# one of our ships (judgement; it only does when that beats its ship shot)
ENEMY_FIRE_AT_WAVE = 0.5
# Chance a loaded enemy carrier puts its fighters on CAP for the target before
# our wave arrives, when it has an ordnance phase to do it in (judgement)
REACTIVE_CAP_WEIGHT = 0.5
# Chance enemy fighters already flying free go for our wave when they can
# reach it (they need no launch; as our own free fighters, 0.75: judgement)
AIRBORNE_INTERCEPT_WEIGHT = 0.75


def _positions_through(target, our_phase: bool, phases: int):
    """_predicted_positions extended to `phases` ordnance phases: after the
    second move the target keeps going along its course, a mean move per turn."""
    import dataclasses
    import math as _m
    pos = list(_predicted_positions(target, our_phase))
    mv = 0.75 * (target.effective_speed or 0)
    h = _m.radians(target.heading)
    while len(pos) < phases:
        last = pos[-1]
        # it moves before the enemy's ordnance phases: odd ones when it is our phase now
        moves = (len(pos) % 2 == 1) if our_phase else (len(pos) % 2 == 0)
        pos.append(dataclasses.replace(last, x=last.x + (mv * _m.cos(h) if moves else 0.0),
                                       y=last.y + (mv * _m.sin(h) if moves else 0.0)))
    return pos[:phases]


def strike_timeline(x: float, y: float, speed: float, target: Ship, gs, player: int,
                    route_ratio: float = 1.0, our_phase: bool = True, max_phases: int = 8):
    """When and how a wave launched from (x, y) at `speed` meets `target`:
    attack craft move in both players' ordnance phases (s.15), flying at the
    target where it will be (`_positions_through`), the route `route_ratio`
    times the straight line. Returns {"phase": k (0 = this ordnance phase),
    "end_phases": damage control phases a raid's crits face before the target
    next shoots (1 landing in our turn, 2 in the enemy's), "survival": the
    chance no enemy gun removes the wave on the way (s.25 / s.30: one hit, a
    6, removes the whole wave; batteries on the Ordnance column; each enemy
    shooting phase before arrival, from the enemy's predicted positions,
    weapons in range of the wave there, out of arc at half weight, x
    ENEMY_FIRE_AT_WAVE), "reactive_cap": fighter squadrons the target could
    put on CAP before arrival (its own loaded bays, when an enemy ordnance
    phase comes first), "reactive_intercept": fighter squadrons other loaded
    enemy carriers could launch at the waiting wave in an enemy ordnance phase
    up to arrival (owner: reactive intercept is a strategy too),
    "airborne_intercept": enemy fighters already flying free that could reach
    it by then}, or None if the wave can't reach it in `max_phases`."""
    import math as _m
    from .combat import ordnance_fire_dice, check_weapon_in_arc
    rt = target.base_radius
    tpos = _positions_through(target, our_phase, max_phases)
    k = None
    for j, p in enumerate(tpos):
        if _m.hypot(p.x - x, p.y - y) * route_ratio <= (j + 1) * speed + rt:
            k = j
            break
    if k is None:
        return None
    # Enemy shooting phases before arrival: after each of its moves, i.e. before
    # the enemy's ordnance phases (odd j when we launch in our own phase)
    enemy_js = [j for j in range(1, k + 1) if (j % 2 == 1) == our_phase]
    enemies = [e for e in gs.get_ships() if e.player != player and not e.is_destroyed
               and not e.is_disengaged and not e.is_hulk]
    epos = {e.id: _positions_through(e, our_phase, max(k + 1, 1)) for e in enemies}
    dice = 0.0
    shots = []          # one enemy weapon's shot in one shooting phase: weighted dice
    for j in enemy_js:
        p = tpos[j]
        d = _m.hypot(p.x - x, p.y - y) * route_ratio or 1.0
        f = min(1.0, j * speed / d)
        wx, wy = x + (p.x - x) * f, y + (p.y - y) * f     # where the wave waits
        for e in enemies:
            ep = epos[e.id][min(j, len(epos[e.id]) - 1)]
            for w in e.weapons:
                if w.get("weapon_type") not in ("battery", "lance"):
                    continue
                if _m.hypot(wx - ep.x, wy - ep.y) > (w.get("range_cm") or 0):
                    continue
                n = ordnance_fire_dice(ep, w, wx, wy, gs, w.get("strength") or 0)
                n *= (1.0 if check_weapon_in_arc(ep, w, wx, wy) else 0.5)
                dice += n
                if n > 0:
                    shots.append(n)
    survival = (5 / 6) ** (dice * ENEMY_FIRE_AT_WAVE)
    cap = 0
    # The enemy launches at the end of its shooting phase and moves its ordnance
    # first in its own ordnance phase (s.15), so arriving in its phase is too late
    enemy_ord_before = any((j % 2 == 1) == our_phase for j in range(0, k + 1))
    if enemy_ord_before and target.ordnance_loaded_craft:
        from .ordnance import craft_roles, craft_stats, bay_launch_capacity
        bays = [w for w in target.weapons if w.get("weapon_type") == "launch_bay"]
        if any("fighter" in craft_roles(craft_stats(ct, bays)[0])
               for w in bays for ct in w.get("craft_types", [])):
            cap = bay_launch_capacity(target, bays, None)[0]
    # Reactive intercept (owner: a strategy too): any other loaded enemy carrier
    # whose fighters can reach the waiting wave in an enemy ordnance phase up to
    # arrival launches them at it; each meets the wave's lead like CAP (s.19 /
    # s.25). Fighters move their speed in the phase they launch (s.15)
    from .ordnance import craft_roles, craft_stats, bay_launch_capacity
    intercept = 0
    for e in enemies:
        if e.id == target.id or not e.ordnance_loaded_craft:
            continue
        bays = [w for w in e.weapons if w.get("weapon_type") == "launch_bay"]
        fspeed = max((craft_stats(ct, bays)[1] or 0) for w in bays
                     for ct in w.get("craft_types", [])
                     if "fighter" in craft_roles(craft_stats(ct, bays)[0])) if any(
            "fighter" in craft_roles(craft_stats(ct, bays)[0])
            for w in bays for ct in w.get("craft_types", [])) else 0
        if not fspeed:
            continue
        for j in range(0, k + 1):
            if (j % 2 == 1) != our_phase:
                continue                       # not an enemy ordnance phase
            p = tpos[j]
            d = _m.hypot(p.x - x, p.y - y) * route_ratio or 1.0
            f = min(1.0, j * speed / d)
            wx, wy = x + (p.x - x) * f, y + (p.y - y) * f
            ep = epos[e.id][min(j, len(epos[e.id]) - 1)]
            if _m.hypot(wx - ep.x, wy - ep.y) <= fspeed:
                intercept += bay_launch_capacity(e, bays, None)[0]
                break
    # Enemy fighters already in flight (free, not on CAP) that can reach the
    # waiting wave by an enemy ordnance phase up to arrival: they move in every
    # ordnance phase (s.15) and need no launch (owner: enemy carriers' fighters
    # threaten our strikes; strike outside their umbrella)
    from .models import OrdnanceMarker
    airborne = 0
    for o in gs.ordnance:
        if o["owner_player"] == player or o.get("cap_ship_id"):
            continue
        m = OrdnanceMarker.from_dict(o)
        if "fighter" not in craft_roles(m.ordnance_type):
            continue
        for j in range(0, k + 1):
            if (j % 2 == 1) != our_phase:
                continue
            p = tpos[j]
            d = _m.hypot(p.x - x, p.y - y) * route_ratio or 1.0
            f = min(1.0, j * speed / d)
            wx, wy = x + (p.x - x) * f, y + (p.y - y) * f
            if _m.hypot(wx - m.x, wy - m.y) <= (m.speed or 20) * (j + 1):
                airborne += 1
                break
    landed_ours = (k % 2 == 0) == our_phase
    return {"phase": k, "end_phases": 1 if landed_ours else 2, "survival": survival,
            "shots": shots,
            "reactive_cap": cap, "reactive_intercept": intercept,
            "airborne_intercept": airborne}


# ── Coordinated strikes: the turret split (owner) ───────────────────────────
def turret_split_gain(target: Ship, gs, torp_strength: float, fighters: int, bombers: int,
                      f_save: int = 0, b_save: int = 0, from_xy=None) -> float:
    """Extra expected hits when a torpedo / missile salvo and an attack craft
    wave reach `target` in the same phase (owner; s.28): its turrets fire at
    attack craft or at torpedoes and mines in a phase, not both, so it saves
    them for whichever they would stop more of and the other gets through
    without shoot-down losses. Our gain is the smaller of the two turret
    savings. (Bombers' attacks are still reduced by turrets either way: only
    the shoot-down roll is blocked, owner ruling.) Ork turrets fire at
    everything (ork_turrets): no gain."""
    from .waves import wave_plan_inputs, wave_split_value
    if "ork_turrets" in target.special_rules or torp_strength <= 0 or bombers <= 0:
        return 0.0
    inp = wave_plan_inputs(target, gs)
    t, shots = inp["turrets"], inp["turrets"] + inp["massed"]
    if shots <= 0:
        return 0.0
    p = (7 - (5 if inp.get("ork") else 4)) / 6.0
    xy = from_xy or (target.x - 10.0, target.y)
    torp_full = torp_strength * p_hit(target.armor_vs(*xy))
    torp_saved = torp_full - torpedo_salvo_hits(torp_strength, target, gs, xy)
    craft_saved = (wave_split_value(fighters, bombers, t, 0, inp["cap"], inp["armour"], p,
                                    f_save, b_save, inp["cap_save"])
                   - wave_split_value(fighters, bombers, t, shots, inp["cap"], inp["armour"], p,
                                      f_save, b_save, inp["cap_save"]))
    return max(0.0, min(torp_saved, craft_saved))


# ── Firepower by range bracket (To do 8 f, owner) ───────────────────────────
# Owner: fight in the bracket where our guns beat theirs, fleet vs fleet and
# ship vs ship. 0-15cm is its own bracket mostly for Ork Heavy Gunz (and the
# Gunnery table's left shift), 45-60 for Chaos long guns, 60-150 for
# artillery such as the Nova Cannon (30cm minimum). The table is measured, not
# scripted: consumers (the range-band goal of To do 11 a, kiting in 8 c) read
# where our expected VP beats theirs.
RANGE_BRACKETS = ((0.0, 15.0), (15.0, 30.0), (30.0, 45.0), (45.0, 60.0), (60.0, 150.0))
_BRACKET_HEADINGS = tuple(range(0, 360, 45))


class _BareState:
    """Just enough game state for the Gunnery table's column shifts between
    two ships on an empty table (range shifts, no blast markers / terrain)."""
    def __init__(self, ships):
        self._ships = ships

    def get_blast_markers(self):
        return []

    def get_phenomena(self):
        return []

    def get_ships(self):
        return self._ships


def nova_expected_hits(dist: float, target: Ship) -> float:
    """Expected hits of a Nova Cannon shot aimed at `target` `dist` away, as
    `combat.resolve_nova_cannon` resolves it: a direct hit (1 in 3 on the
    scatter die) puts the template on the target, D6 hits; otherwise it
    scatters 1D6 (to 45cm), 2D6 (to 60cm) or 3D6cm: D6 hits if the target's base
    still touches the centre hole, 1 if it touches the template. 0 outside
    30-150cm. Shields still stop the hits (owner ruling)."""
    from .geometry import NOVA_CANNON_TEMPLATE_RADIUS_CM as TR, \
        NOVA_CANNON_CENTER_HOLE_RADIUS_CM as CR
    if dist < 30 or dist > 150:
        return 0.0
    n = 1 if dist <= 45 else 2 if dist <= 60 else 3
    r = target.base_radius
    dist_p = {0: 1.0}
    for _ in range(n):
        nxt = {}
        for s, p in dist_p.items():
            for f in range(1, 7):
                nxt[s + f] = nxt.get(s + f, 0.0) + p / 6.0
        dist_p = nxt
    # The scatter direction is random, so only the distance matters here
    centre = sum(p for s, p in dist_p.items() if s <= CR + r)
    edge = sum(p for s, p in dist_p.items() if CR + r < s <= TR + r)
    return (1 / 3) * 3.5 + (2 / 3) * (centre * 3.5 + edge * 1.0)


def past_shields(lam: float, shields: int) -> float:
    """Expected hits past `shields` when the hits are a Poisson count with mean
    `lam`: E[max(0, H - shields)]. Shields stop the first hits each turn, but
    a ship whose average is below its target's shields still gets some through
    on the turns it rolls well."""
    s = max(0, int(shields or 0))
    if s == 0:
        return max(0.0, lam)
    if lam <= 0:
        return 0.0
    p = math.exp(-lam)
    short = 0.0
    for k in range(s):
        short += (s - k) * p
        p *= lam / (k + 1)
    return max(0.0, lam - s + short)


def ship_bracket_raw(a: Ship, b: Ship, dist: float, heading_b: float, heading_a: float) -> float:
    """Expected hits (before shields) of `a`'s direct fire on `b` at `dist`,
    `a` at the origin facing `heading_a`, `b` on its x axis facing `heading_b`:
    batteries on the real Gunnery table with its range shifts (and Ork Heavy
    Gunz' close value), lances 0.5, the Nova Cannon (nova_expected_hits; not
    when crippled). Ordnance isn't counted (it launches once and flies)."""
    from .combat import check_weapon_in_arc, expected_hits, weapon_disabled_by_crit
    tb = Ship.from_dict({**b.to_dict(), "x": dist, "y": 0.0, "heading": float(heading_b)})
    ta = Ship.from_dict({**a.to_dict(), "x": 0.0, "y": 0.0, "heading": float(heading_a),
                         "special_order": ""})
    gs = _BareState([ta, tb])
    hits = 0.0
    for w in ta.weapons:
        wt = w.get("weapon_type")
        if wt not in ("battery", "lance", "nova_cannon") or weapon_disabled_by_crit(ta, w):
            continue
        if not check_weapon_in_arc(ta, w, tb.x, tb.y):
            continue
        if wt == "nova_cannon":
            if not ta.is_crippled:
                hits += nova_expected_hits(dist, tb)
            continue
        if dist > (w.get("range_cm") or 0):
            continue
        hits += expected_hits(ta, w, tb, gs)
    return hits


def ship_bracket_hits(a: Ship, b: Ship, dist: float, shields: bool = True) -> float:
    """Expected hits `a` puts on `b` at `dist`, on average over b's facing,
    `a` turned to bring its best guns to bear; with `shields`, past b's
    shields (past_shields), else before them."""
    total = 0.0
    sh = b.effective_shields or 0
    for hb in _BRACKET_HEADINGS:
        best = 0.0
        for ha in _BRACKET_HEADINGS:
            lam = ship_bracket_raw(a, b, dist, hb, ha)
            best = max(best, past_shields(lam, sh) if shields else lam)
        total += best
    return total / len(_BRACKET_HEADINGS)


def bracket_matchup(a: Ship, b: Ship) -> List[Tuple[Tuple[float, float], float, float]]:
    """Ship vs ship, per range bracket: [((lo, hi), VP a does to b, VP b does
    to a) per shooting phase, past shields], at each bracket's middle
    distance."""
    out = []
    for lo, hi in RANGE_BRACKETS:
        d = (lo + hi) / 2.0
        out.append(((lo, hi), ship_bracket_hits(a, b, d) * value_per_hit(b, None),
                    ship_bracket_hits(b, a, d) * value_per_hit(a, None)))
    return out


def fleet_bracket_table(gs, player: int) -> List[Tuple[Tuple[float, float], float, float]]:
    """Fleet vs fleet, per range bracket: [((lo, hi), our VP, their VP)] per
    shooting phase, on average (owner): each side's fire spread evenly over
    the other's ships, each target's shields taken once against all of it
    (shields stop the first hits of a turn, whoever fires them)."""
    ours = [s for s in gs.get_ships() if s.player == player and not s.is_destroyed
            and not s.is_disengaged]
    theirs = [s for s in gs.get_ships() if s.player != player and not s.is_destroyed
              and not s.is_disengaged]
    table = []
    for lo, hi in RANGE_BRACKETS:
        d = (lo + hi) / 2.0
        sides = []
        for shooters, targets in ((ours, theirs), (theirs, ours)):
            vp = 0.0
            for t in targets:
                lam = sum(ship_bracket_hits(a, t, d, shields=False)
                          for a in shooters) / max(1, len(targets))
                vp += past_shields(lam, t.effective_shields or 0) * value_per_hit(t, None)
            sides.append(vp)
        table.append(((lo, hi), sides[0], sides[1]))
    return table


def best_bracket(table) -> Tuple[float, float]:
    """The bracket where our expected VP beats theirs by most."""
    return max(table, key=lambda r: r[1] - r[2])[0]


def torpedo_bomber_target(gs, group, player: int):
    """(VP, ship) for a torpedo bomber wave's salvo this phase (s.21: 2 a
    squadron; Tiger Sharks a Tau missile salvo, 40cm, 5/6 of it through): the
    enemy ship within the salvo's move where it does most expected VP (turret
    kills 4+ each, the facing it hits; ships don't move in the ordnance phase),
    or None when none is in reach. Shared by the AI and the "Auto (best)"
    choice."""
    from .ordnance import TORPEDO_SPEED_DEFAULT
    lead = group[0]
    tiger = "tiger_shark" in lead.special_rules
    reach = 40.0 if tiger else float(TORPEDO_SPEED_DEFAULT)
    strength = 2 * len(group) * (5 / 6 if tiger else 1.0)
    best = None
    for e in gs.get_ships():
        if e.player == player or e.is_destroyed or e.is_disengaged:
            continue
        if math.hypot(e.x - lead.x, e.y - lead.y) > reach + e.base_radius:
            continue
        hits = max(0.0, strength - 0.5 * e.effective_turrets) * p_hit(e.armor_vs(lead.x, lead.y))
        v = hull_hits_vp(e, gs, 0.0, hits)
        if best is None or v > best[0]:
            best = (v, e)
    return best


ARMAMENT_CRITS = ("dorsal_armament", "port_armament", "starboard_armament", "prow_armament")


def repair_value(ship: Ship, crit: dict, gs) -> float:
    """Expected VP of repairing one critical hit now (damage control, s.36;
    To do 11 e). Fire: the hit it would cost each end phase it burns
    (judgement: 1.5 hits at the ship's value a hit). Armament: what those
    weapons threaten at the next shooting phases (hit_and_run.
    armament_threat_value, the raid model, from the enemy's side). Shields
    collapsed: the enemy's expected hits next turn its shields would stop.
    Engines / thrusters / bridge (judgement): a share of its guns' value
    (`ai_rerolls.firepower_swing`: 0.3 / 0.2) or of its value (0.1)."""
    from .ai_rerolls import firepower_swing
    ct = crit.get("crit_type", "")
    vph = value_per_hit(ship, gs)
    if ct == "fire":
        return 1.5 * vph
    if ct in ARMAMENT_CRITS:
        # valued as if repaired: the raid model counts a location already
        # knocked out as worth nothing
        import dataclasses
        from .hit_and_run import armament_threat_value
        fixed = dataclasses.replace(ship, critical_damage=[
            c for c in ship.critical_damage if c is not crit])
        return armament_threat_value(fixed, ct, gs, 3 - ship.player)
    if ct == "shields_collapse":
        return min(ship.shields_max, incoming_hits(ship, gs)) * vph
    if ct == "engine_room":
        return 0.3 * firepower_swing(ship, gs)
    if ct == "thrusters_damaged":
        return 0.2 * firepower_swing(ship, gs)
    if ct == "bridge_smashed":
        return 0.1 * ship_value(ship, gs)
    return 0.05 * ship_value(ship, gs)


BOARD_CRITS = {1: (5, 5), 2: (5, 4), 3: (6, 3), 4: (6, 2)}   # s.32 (winner, loser)


def boarding_vp(attacker: Ship, target: Ship, gs) -> float:
    """Expected VP for the attacker's side of a boarding action now (s.32;
    To do 8 h): both D6 rolls enumerated with the modifiers resolve_boarding
    uses (troop ratings, crew bonuses, crippled / special orders / blast
    markers); the loser takes the difference in damage (hull_hits_vp: full
    value a hit, thresholds), each side's crit chance by the result table at a
    hit's value each (judgement), a draw (grapple) counts nothing. Knights of
    Titan and Mechanicus re-rolls aren't counted."""
    from .boarding import (troop_rating, _troop_advantage_bonus, _crew_damage_bonus,
                           _get_ship_modifier)
    a_rating = troop_rating(attacker, attacker.is_grappled)
    d_rating = troop_rating(target, target.is_grappled, defending=True)
    a_bonus = _get_ship_modifier(target, gs) + _troop_advantage_bonus(a_rating, d_rating) \
        + _crew_damage_bonus(attacker)
    d_bonus = _get_ship_modifier(attacker, gs) + _troop_advantage_bonus(d_rating, a_rating) \
        + _crew_damage_bonus(target)
    vph_a, vph_t = value_per_hit(attacker, gs), value_per_hit(target, gs)

    def p_at_least(t):
        return 1.0 if t is None or t <= 1 else max(0.0, (7 - t) / 6.0)

    total = 0.0
    for a in range(1, 7):
        for d in range(1, 7):
            diff = (a + a_bonus) - (d + d_bonus)
            if diff == 0:
                continue
            win, lose = BOARD_CRITS.get(min(abs(diff), 5), (None, 0))
            p_win_crit = 0.0 if win is None else p_at_least(win)
            p_lose_crit = 1.0 if lose == 0 else p_at_least(lose)
            if diff > 0:
                total += hull_hits_vp(target, gs, 0.0, diff) + p_lose_crit * vph_t
                total -= p_win_crit * vph_a
            else:
                total -= hull_hits_vp(attacker, gs, 0.0, -diff) + p_lose_crit * vph_a
                total += p_win_crit * vph_t
    return total / 36.0


def ram_vp(rammer: Ship, target: Ship, gs) -> float:
    """Expected VP of a ram that connects (s.12; To do 8 h), as
    combat.resolve_ram resolves it from the rammer's current position: the
    rammer's starting hits in D6 against the Armour of the facing it strikes,
    the target's starting hits back (half, rounding up, unless front to front
    or a defence) against the rammer's prow Armour; shields stop neither."""
    from .models import Arc
    t_arc = target.get_arc_for_bearing(target.bearing_to(rammer.x, rammer.y))
    t_armour = target.armor_for_arc(t_arc)
    r_arc = rammer.get_arc_for_bearing(rammer.bearing_to(target.x, target.y))
    head_on = t_arc == Arc.FRONT and r_arc == Arc.FRONT
    back = target.hits_max if (head_on or target.ship_type == "defense") else \
        (target.hits_max + 1) // 2
    dealt = rammer.hits_max * p_hit(t_armour)
    taken = back * p_hit(rammer.armor_prow_value)
    return hull_hits_vp(target, gs, 0.0, dealt) - hull_hits_vp(rammer, gs, 0.0, taken)
