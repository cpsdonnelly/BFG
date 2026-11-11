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
    """Expected torpedoes a ship's turrets shoot down: 4+ each (Orks 5+)."""
    need = 5 if "ork_turrets" in ship.special_rules else 4
    return ship.effective_turrets * (7 - need) / 6.0


def marker_hits(ship: Ship, m: OrdnanceMarker, end: Point, pts: Sequence[Point],
                my_ships: Sequence[Ship]) -> Tuple[float, str]:
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
            h = 8 * ph
            return h, f"mine ({h:.1f} hits)"
        return 0.0, ""
    if "torpedo" in otype and otype != "torpedo_bomber":
        strength = max(0.0, m.strength - _turret_kills(ship))
        if strength <= 0:
            return 0.0, ""
        rad = math.radians(m.heading)
        ex, ey = m.x + m.speed * math.cos(rad), m.y + m.speed * math.sin(rad)
        if on_path or _seg_dist(end[0], end[1], m.x, m.y, ex, ey) <= r + 1.0:
            h = strength * ph * (0.5 if "boarding" in otype else 1.0)   # raids, not hull
            return h, f"torpedoes S{m.strength} ({h:.1f} hits)"
        return 0.0, ""
    # attack craft that may reach the ship before it moves again
    if on_path or math.hypot(end[0] - m.x, end[1] - m.y) <= (m.speed or 20) + r:
        if "bomber" in otype or otype in ("manta", "thunderhawk", "fighta_bommer"):
            # D6 attacks less one per turret (s.20)
            h = sum(max(0, k - ship.effective_turrets) for k in range(1, 7)) / 6.0 * ph
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
        h, w = marker_hits(ship, m, end, pts, my_ships)
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
        hits = sum(marker_hits(s, mk, (s.x, s.y), [(s.x, s.y)], mine)[0] for mk in markers)
        best = max(best, hits * value_per_hit(s, gs))
    return best


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


def damage_vp(target: Ship, gs, mean_hits: float) -> float:
    """Expected VP from `mean_hits` hull hits on a target (s.38): its value if
    destroyed, a quarter if crippled, plus a little for each hit (later
    damage, crits)."""
    v = ship_value(target, gs)
    rem = max(1, target.hits_remaining)
    p_kill = poisson_at_least(mean_hits, rem)
    to_cripple = rem - target.hits_max // 2
    p_crip = 0.0 if target.is_crippled or to_cripple <= 0 else poisson_at_least(mean_hits, to_cripple)
    return (p_kill * v + max(0.0, p_crip - p_kill) * v * 0.25
            + min(mean_hits, rem) * value_per_hit(target, gs) * 0.2)


def shot_vp(attacker: Ship, weapon: dict, target: Ship, gs, committed: float = 0.0) -> float:
    """Marginal expected VP of firing `weapon` at `target`, given `committed`
    expected hull hits already planned against it this phase (so the AI stops
    piling fire on a ship that is probably dead, and doesn't spread too thin)."""
    from .combat import expected_hits
    from .geometry import current_shields
    raw = expected_hits(attacker, weapon, target)
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
        h, _ = marker_hits(s, hit, (s.x, s.y), [(s.x, s.y)], mine)
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


def incoming_hits(ship: Ship, gs) -> float:
    """Rough hits the enemy's guns can put on `ship` in their next turn: every
    enemy battery / lance within its range + the enemy's move (0.35 a battery
    point, 0.5 a lance; only the stronger broadside), less the ship's shields
    once per firing ship, shared among the ships of ours that enemy can reach."""
    import math as _m
    from .geometry import current_shields
    shields = current_shields(ship, gs.get_blast_markers())
    ours = [s for s in gs.get_ships() if s.player == ship.player
            and not s.is_destroyed and not s.is_disengaged]
    total = 0.0
    for e in gs.get_ships():
        if e.player == ship.player or e.is_destroyed or e.is_disengaged:
            continue
        reach = (e.speed or 0)

        def in_reach(w, t):
            return _m.hypot(e.x - t.x, e.y - t.y) <= (w.get("range_cm") or 0) + reach
        side = {"left": 0.0, "right": 0.0}
        hits = 0.0
        for w in e.weapons:
            wt = w.get("weapon_type")
            if wt not in ("battery", "lance") or not in_reach(w, ship):
                continue
            h = (w.get("strength") or 0) * (0.5 if wt == "lance" else 0.35)
            arcs = w.get("arcs") or []
            if arcs in (["left"], ["right"]):
                side[arcs[0]] += h          # only one broadside bears on one target
            else:
                hits += h
        hits += max(side.values())
        # its fire is shared among the ships of ours it can reach
        n = sum(1 for t in ours if any(in_reach(w, t) for w in e.weapons
                                       if w.get("weapon_type") in ("battery", "lance")))
        total += max(0.0, hits - shields) / max(1, n)
    return total


def disengage_gain(ship: Ship, gs, ld: int, contribution: float) -> float:
    """Expected VP gained by trying to disengage now (s.37, VP s.38) instead of
    fighting on for another turn. Staying risks the enemy's next turn
    (incoming_hits as a Poisson count): destroyed -> the full value, newly
    crippled -> 25%. Leaving concedes 10% (25% if crippled, which a crippled
    ship concedes anyway). Either way the ship's guns are lost this turn (a
    failed test also forbids firing), worth `contribution`.
    gain = P(pass) x (risk avoided - extra VP conceded) - contribution."""
    v = ship_value(ship, gs)
    lam = incoming_hits(ship, gs)
    left = max(1, ship.hits_remaining)
    p_kill = _poisson_at_least(lam, left)
    risk = p_kill * v * (0.75 if ship.is_crippled else 1.0)
    if not ship.is_crippled:
        to_cripple = left - ship.hits_max // 2
        if to_cripple > 0:
            risk += max(0.0, _poisson_at_least(lam, to_cripple) - p_kill) * 0.25 * v
    extra = 0.0 if ship.is_crippled else 0.10 * v
    p_pass = p_sum_at_most(2, ld) if ld > 1 else 0.0
    return p_pass * (risk - extra) - contribution
