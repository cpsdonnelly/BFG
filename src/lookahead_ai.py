"""BFG:XR Expert AI — alpha-beta minimax with 5-turn lookahead.

Uses a lightweight game-state clone (SimState) with deterministic combat
(expected hit values, no dice) for the search.  Inherits all heuristic
phase methods from AIPlayer; only movement is replaced by minimax.
"""
import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .models import Ship, parse_armor, bearing_between, arc_name_for_bearing
from .game_state import GameState
from .ai_player import AIPlayer
from .movement import (
    MoveCommand, get_effective_speed, MIN_TURN_DISTANCE,
)


# ── Lightweight simulation state ─────────────────────────────────────────────

@dataclass
class SimShip:
    id: str
    player: int
    x: float
    y: float
    heading: float
    speed: int
    turn_angle: int
    ship_type: str
    points_value: int
    hits_remaining: int
    hits_max: int
    shields_remaining: int
    shields_max: int
    armor_prow: str
    armor_side: str
    weapons: List[Dict] = field(default_factory=list)
    is_destroyed: bool = False
    is_disengaged: bool = False
    armor_rear: str = ""        # third Armour value (front/abeam/rear), if any
    turrets: int = 0
    torps_loaded: bool = False
    base_radius: float = 1.6
    p_plasma: float = 0.0       # Catastrophic Damage odds when destroyed (s.34)
    p_warp: float = 0.0

    @property
    def is_crippled(self) -> bool:
        return self.hits_remaining <= self.hits_max // 2 and not self.is_destroyed

    @property
    def is_alive(self) -> bool:
        return not self.is_destroyed and not self.is_disengaged

    def clone(self) -> "SimShip":
        return SimShip(
            id=self.id, player=self.player, x=self.x, y=self.y,
            heading=self.heading, speed=self.speed, turn_angle=self.turn_angle,
            ship_type=self.ship_type, points_value=self.points_value,
            hits_remaining=self.hits_remaining, hits_max=self.hits_max,
            shields_remaining=self.shields_remaining, shields_max=self.shields_max,
            armor_prow=self.armor_prow, armor_side=self.armor_side,
            weapons=self.weapons,   # shared; weapons don't change during search
            is_destroyed=self.is_destroyed, is_disengaged=self.is_disengaged,
            armor_rear=self.armor_rear, turrets=self.turrets,
            torps_loaded=self.torps_loaded, base_radius=self.base_radius,
            p_plasma=self.p_plasma, p_warp=self.p_warp,
        )

    @classmethod
    def from_ship(cls, ship: Ship) -> "SimShip":
        from .ai_hazards import explosion_odds
        p_plasma, p_warp = explosion_odds(ship)
        return cls(
            turrets=ship.effective_turrets if hasattr(ship, "effective_turrets") else ship.turrets,
            torps_loaded=bool(ship.ordnance_loaded_torps) and any(
                w.get("weapon_type") == "torpedo" for w in ship.weapons),
            base_radius=ship.base_radius, p_plasma=p_plasma, p_warp=p_warp,
            id=ship.id, player=ship.player, x=ship.x, y=ship.y,
            heading=ship.heading, speed=ship.speed,
            turn_angle=ship.turn_angle, ship_type=ship.ship_type,
            points_value=ship.points_value,
            hits_remaining=ship.hits_remaining, hits_max=ship.hits_max,
            shields_remaining=ship.effective_shields, shields_max=ship.shields_max,
            armor_prow=ship.armor_prow, armor_side=ship.armor_side,
            weapons=ship.weapons, armor_rear=ship.armor_rear,
        )

    def bearing_to(self, tx: float, ty: float) -> float:
        return bearing_between(self.x, self.y, tx, ty)

    def get_arc(self, tx: float, ty: float) -> str:
        return arc_name_for_bearing(self.bearing_to(tx, ty), self.heading)


@dataclass
class SimOrdnance:
    """One of the searching player's ordnance markers in flight (To do 2: the
    expert values its own craft in flight). Torpedoes fly straight; attack
    craft fly at their target (or the nearest enemy). The enemy's ordnance
    isn't simulated: the root's path-hazard cost already counts it."""
    owner: int
    kind: str                 # "torpedo" or "craft"
    otype: str
    x: float
    y: float
    heading: float
    speed: float
    strength: int = 0
    target_id: str = ""

    def clone(self) -> "SimOrdnance":
        return SimOrdnance(self.owner, self.kind, self.otype, self.x, self.y,
                           self.heading, self.speed, self.strength, self.target_id)

    @classmethod
    def from_marker(cls, m: dict) -> Optional["SimOrdnance"]:
        otype = m.get("ordnance_type", "")
        if m.get("cap_ship_id") or otype in ("mine_field", "torpedo_bomber"):
            return None
        if "torpedo" in otype:
            kind = "torpedo"
        elif otype in ("bomber", "manta", "thunderhawk", "fighta_bommer", "gun_cutter",
                       "assault_boat") or "bomber" in otype or "assault" in otype:
            kind = "craft"
        else:
            return None                # fighters don't attack ships
        target = m.get("craft_target_id") or m.get("torp_target_id") or ""
        return cls(m.get("owner_player", 0), kind, otype, m.get("x", 0.0), m.get("y", 0.0),
                   m.get("heading", 0.0), m.get("speed", 30.0) or 30.0,
                   m.get("strength", 0) or 0, target)


@dataclass
class SimState:
    ships: List[SimShip]
    turn: int
    turn_limit: Optional[int]
    table_w: float = 120.0
    table_h: float = 120.0
    ordnance: List[SimOrdnance] = field(default_factory=list)

    @classmethod
    def from_gs(cls, gs: GameState, ord_player: int = 0) -> "SimState":
        """ord_player: whose ordnance in flight to simulate (the searching
        player's; 0 = none)."""
        ships = [SimShip.from_ship(Ship.from_dict(s)) for s in gs.ships]
        ords = []
        if ord_player:
            for m in getattr(gs, "ordnance", []) or []:
                if m.get("owner_player") == ord_player:
                    o = SimOrdnance.from_marker(m)
                    if o is not None:
                        ords.append(o)
        return cls(ships=ships, turn=gs.turn_number, turn_limit=gs.turn_limit,
                   table_w=getattr(gs, "table_width", 120.0) or 120.0,
                   table_h=getattr(gs, "table_height", 120.0) or 120.0,
                   ordnance=ords)

    def clone(self) -> "SimState":
        return SimState(
            ships=[s.clone() for s in self.ships],
            turn=self.turn,
            turn_limit=self.turn_limit,
            table_w=self.table_w,
            table_h=self.table_h,
            ordnance=[o.clone() for o in self.ordnance],
        )

    def alive(self, player: int) -> List[SimShip]:
        return [s for s in self.ships if s.player == player and s.is_alive]

    def is_terminal(self) -> bool:
        if not self.alive(1) or not self.alive(2):
            return True
        if self.turn_limit and self.turn > self.turn_limit:
            return True
        return False


# ── Deterministic combat helpers ─────────────────────────────────────────────

def _p_hit(armor: int) -> float:
    return max(1, 7 - armor) / 6.0 if armor <= 6 else 1 / 6.0


def _armor_facing(target: SimShip, x: float, y: float) -> int:
    arc = target.get_arc(x, y)
    return parse_armor(target.armor_prow if arc == "front"
                       else (target.armor_rear or target.armor_side) if arc == "rear"
                       else target.armor_side)


def _expected_weapon_hits(attacker: SimShip, weapon: Dict,
                          target: SimShip) -> float:
    """Expected hull hits from one weapon (deterministic, no dice), as the
    normal AI counts them (ai_hazards): a battery point 0.35 hits against
    Armour 5+, scaled by the Armour it fires at; a lance 0.5 (4+ whatever the
    Armour, s.13)."""
    wtype = weapon.get("weapon_type", "")
    if wtype not in ("battery", "lance"):
        return 0.0
    arc = attacker.get_arc(target.x, target.y)
    arcs = weapon.get("arcs", [])
    if arcs and arc not in arcs:
        return 0.0
    dist = math.hypot(target.x - attacker.x, target.y - attacker.y)
    w_range = weapon.get("range_cm", 0)
    if w_range and dist > w_range:
        return 0.0
    strength = weapon.get("strength", 1) or 0
    if wtype == "lance":
        return strength * 0.5
    armor = _armor_facing(target, attacker.x, attacker.y)
    return strength * 0.35 * _p_hit(armor) / _p_hit(5)


def _torpedo_hits(attacker: SimShip, target: SimShip) -> float:
    """A loaded launcher with the target in its arc and within two torpedo
    moves: strength less turret kills (4+), each hitting the facing (torpedoes
    ignore shields, s.15); at a phase's discount when it takes a second move."""
    from .ai_hazards import phase_weight
    if not attacker.torps_loaded:
        return 0.0
    arc = attacker.get_arc(target.x, target.y)
    dist = math.hypot(target.x - attacker.x, target.y - attacker.y)
    total = 0.0
    for w in attacker.weapons:
        if w.get("weapon_type") != "torpedo":
            continue
        arcs = w.get("arcs", [])
        if arcs and arc not in arcs:
            continue
        spd = w.get("torpedo_speed", 30) or 30
        if dist > 2 * spd + target.base_radius:
            continue
        left = max(0.0, (w.get("strength") or 0) - 0.5 * target.turrets)
        h = left * _p_hit(_armor_facing(target, attacker.x, attacker.y))
        total += h * (1.0 if dist <= spd + target.base_radius else phase_weight(1))
    return total


TORP_CONTACT = 1.5          # the marker's half width (ai_hazards.TORP_CONTACT_HALF_W)


def _seg_point(px, py, ax, ay, bx, by) -> float:
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _ordnance_hits(o: SimOrdnance, t: SimShip) -> float:
    """Expected hits a marker does on contact, as the normal AI's hazard model
    counts them (ai_hazards.marker_hits): torpedoes strength less turret kills
    (4+) on the facing they hit (boarding torpedoes half: raids, Tau missiles
    5/6); bombers D6 attacks less one per turret on the lowest Armour (s.20);
    assault boats half a hit past the turrets."""
    if o.kind == "torpedo":
        left = max(0.0, o.strength - 0.5 * t.turrets)
        h = left * _p_hit(_armor_facing(t, o.x, o.y))
        if "boarding" in o.otype:
            h *= 0.5
        if o.otype == "torpedo_guided":
            h *= 5 / 6
        return h
    if "assault" in o.otype or o.otype == "gun_cutter":
        return 0.5 * max(0.0, 1 - 0.5 * t.turrets / 2)
    lowest = min(parse_armor(a) for a in (t.armor_prow, t.armor_side, t.armor_rear or
                                          t.armor_side))
    return sum(max(0, k - t.turrets) for k in range(1, 7)) / 6.0 * _p_hit(lowest)


def _resolve_ordnance(state: SimState, player: int) -> None:
    """Move `player`'s ordnance through a game turn's two ordnance phases (it
    moves in both players', s.15) and attack: a torpedo salvo the first enemy
    ship its path touches, then it is spent; attack craft their target (or the
    nearest enemy) if they reach it, else they close on it. Hits go straight
    to the hull (ordnance ignores shields, s.15)."""
    keep = []
    for o in state.ordnance:
        if o.owner != player:
            keep.append(o)
            continue
        enemies = state.alive(3 - player)
        if not enemies:
            continue
        reach = 2 * o.speed
        if o.kind == "torpedo":
            rad = math.radians(o.heading)
            ex, ey = o.x + reach * math.cos(rad), o.y + reach * math.sin(rad)
            hit = None
            for t in enemies:
                if _seg_point(t.x, t.y, o.x, o.y, ex, ey) <= t.base_radius + TORP_CONTACT:
                    d = math.hypot(t.x - o.x, t.y - o.y)
                    if hit is None or d < hit[0]:
                        hit = (d, t)
            if hit:
                _apply_hits(state, hit[1], _ordnance_hits(o, hit[1]), shields=False)
                continue
            o.x, o.y = ex, ey
            if 0 <= o.x <= state.table_w and 0 <= o.y <= state.table_h:
                keep.append(o)
            continue
        t = next((s for s in enemies if s.id == o.target_id), None)
        if t is None:
            t = min(enemies, key=lambda s: math.hypot(s.x - o.x, s.y - o.y))
        d = math.hypot(t.x - o.x, t.y - o.y)
        if d <= reach + t.base_radius:
            _apply_hits(state, t, _ordnance_hits(o, t), shields=False)
            continue
        o.x += (t.x - o.x) * reach / d
        o.y += (t.y - o.y) * reach / d
        keep.append(o)
    state.ordnance = keep


def _sim_value(t: SimShip, hits_remaining: float) -> float:
    """VP the enemy scores off `t` at `hits_remaining` (s.38: destroyed full,
    crippled 25%), plus 0.2 a hit for damage short of a threshold (as
    ai_hazards.damage_vp)."""
    pts = t.points_value or 0
    if hits_remaining <= 0:
        return float(pts)
    v = 0.25 * pts if hits_remaining <= t.hits_max // 2 else 0.0
    per_hit = pts / max(1, t.hits_max)
    return v + 0.2 * per_hit * (t.hits_max - hits_remaining)


def _apply_hits(state: SimState, t: SimShip, hits: float, shields: bool = True) -> None:
    if shields:
        absorbed = min(t.shields_remaining, hits)
        t.shields_remaining -= absorbed
        hits -= absorbed
    was_alive = not t.is_destroyed
    t.hits_remaining = max(0, t.hits_remaining - hits)
    if t.hits_remaining <= 0:
        t.is_destroyed = True
        if was_alive:
            _explode(state, t)


def _explode(state: SimState, dead: SimShip) -> None:
    """Expected Catastrophic Damage (s.34): a plasma drive overload (half its
    starting hits) or warp drive implosion (all of them) as 4+ lance shots at
    every ship within the 3D6cm radius (10.5 on average). No chains."""
    shots = dead.p_plasma * dead.hits_max / 2 + dead.p_warp * dead.hits_max
    if shots <= 0:
        return
    for s in state.ships:
        if s is dead or not s.is_alive:
            continue
        if math.hypot(s.x - dead.x, s.y - dead.y) - s.base_radius <= 10.5:
            h = max(0.0, shots * 0.5 - s.shields_remaining)
            s.shields_remaining = max(0, s.shields_remaining - shots * 0.5)
            s.hits_remaining = max(0, s.hits_remaining - h)
            if s.hits_remaining <= 0:
                s.is_destroyed = True


def _apply_expected_combat(state: SimState, shooter_player: int) -> float:
    """Apply one player's expected shooting (and torpedoes) and return the VP
    it scored. Owner: focus fire, no overkill - each ship (biggest guns first)
    fires at the target where its expected hits add the most VP given what
    the ships before it have done (_sim_value: thresholds, then 0.2 a hit)."""
    shooters = sorted(state.alive(shooter_player),
                      key=lambda a: -sum(w.get("strength", 0) or 0 for w in a.weapons))
    scored = 0.0
    for attacker in shooters:
        targets = state.alive(3 - shooter_player)
        if not targets:
            break
        best, best_key = None, None
        for t in targets:
            guns = sum(_expected_weapon_hits(attacker, w, t) for w in attacker.weapons)
            torps = _torpedo_hits(attacker, t)
            if guns + torps <= 0:
                continue
            after = t.hits_remaining - max(0.0, guns - t.shields_remaining) - torps
            gain = _sim_value(t, after) - _sim_value(t, t.hits_remaining)
            key = (gain, guns + torps)
            if best_key is None or key > best_key:
                best, best_key = (t, guns, torps), key
        if best is None:
            continue
        t, guns, torps = best
        before = sum(_sim_value(s, s.hits_remaining) for s in state.alive(3 - shooter_player)
                     ) + sum(s.points_value for s in state.ships
                             if s.player != shooter_player and s.is_destroyed)
        _apply_hits(state, t, guns)
        if torps > 0:
            _apply_hits(state, t, torps, shields=False)
            attacker.torps_loaded = False          # no reloads in the search
        after = sum(_sim_value(s, s.hits_remaining) for s in state.alive(3 - shooter_player)
                    ) + sum(s.points_value for s in state.ships
                            if s.player != shooter_player and s.is_destroyed)
        scored += after - before
    return scored


# ── Move generation ───────────────────────────────────────────────────────────

_TURN_FRACS = ((0.0, 0.6), (0.0, 0.8), (0.0, 1.0),
               (1.0, 0.8), (1.0, 1.0),
               (-1.0, 0.8), (-1.0, 1.0),
               (0.5, 1.0), (-0.5, 1.0))  # (turn_mult, speed_frac)


def _apply_move(ship: SimShip, turn_deg: float, dist: float) -> None:
    """Move ship in place (SimShip). Mirrors _simulate_final_pos logic."""
    r = math.radians
    min_td = MIN_TURN_DISTANCE.get(ship.ship_type, 0)
    if abs(turn_deg) < 0.5:
        ship.x += dist * math.cos(r(ship.heading))
        ship.y += dist * math.sin(r(ship.heading))
        return
    if min_td > 0 and dist > min_td:
        ship.x += min_td * math.cos(r(ship.heading))
        ship.y += min_td * math.sin(r(ship.heading))
        ship.heading = (ship.heading + turn_deg) % 360
        rem = dist - min_td
        ship.x += rem * math.cos(r(ship.heading))
        ship.y += rem * math.sin(r(ship.heading))
    else:
        ship.heading = (ship.heading + turn_deg) % 360
        ship.x += dist * math.cos(r(ship.heading))
        ship.y += dist * math.sin(r(ship.heading))


def _generate_best_moves(state: SimState, player: int,
                          ai_player_ref: "LookaheadAI") -> Dict[str, Tuple[float, float]]:
    """
    Greedy sequential move generation for every ship of `player`.
    For each ship, pick the (turn_deg, dist) that maximises arc_score - position_penalty
    against the nearest enemy — same criterion as the base heuristic AI.
    Returns {ship_id: (turn_deg, dist)}.
    """
    moves: Dict[str, Tuple[float, float]] = {}
    enemies = state.alive(3 - player)
    if not enemies:
        return moves

    for ship in state.alive(player):
        nearest = min(enemies, key=lambda e: math.hypot(e.x - ship.x, e.y - ship.y))
        best_score = -math.inf
        best = (0.0, ship.speed * 0.8)
        ta = ship.turn_angle
        for turn_mult, speed_frac in _TURN_FRACS:
            turn_deg = ta * turn_mult
            dist = max(1, int(ship.speed * speed_frac))
            min_td = MIN_TURN_DISTANCE.get(ship.ship_type, 0)
            if abs(turn_deg) > 0.5 and min_td > 0 and dist <= min_td:
                continue
            # Simulate position
            fx, fy, fh = _sim_pos(ship, turn_deg, dist)
            score = _arc_score_sim(ship, fx, fy, fh, nearest)
            real = ai_player_ref.gs.get_ship_by_id(ship.id)
            score -= (ai_player_ref._position_penalty(fx, fy, real, [(ship.x, ship.y), (fx, fy)])
                      if real else ai_player_ref._position_penalty(fx, fy))
            if score > best_score:
                best_score = score
                best = (turn_deg, dist)
        moves[ship.id] = best
    return moves


def _sim_pos(ship: SimShip, turn_deg: float, dist: float) -> Tuple[float, float, float]:
    r = math.radians
    min_td = MIN_TURN_DISTANCE.get(ship.ship_type, 0)
    if abs(turn_deg) < 0.5:
        h = ship.heading
        return (ship.x + dist * math.cos(r(h)),
                ship.y + dist * math.sin(r(h)), h)
    if min_td > 0 and dist > min_td:
        h0 = ship.heading
        mx = ship.x + min_td * math.cos(r(h0))
        my = ship.y + min_td * math.sin(r(h0))
        h1 = (h0 + turn_deg) % 360
        rem = dist - min_td
        return (mx + rem * math.cos(r(h1)), my + rem * math.sin(r(h1)), h1)
    h1 = (ship.heading + turn_deg) % 360
    return (ship.x + dist * math.cos(r(h1)),
            ship.y + dist * math.sin(r(h1)), h1)


def _arc_score_sim(ship: SimShip, fx: float, fy: float, fh: float,
                   target: SimShip) -> float:
    dx = target.x - fx
    dy = target.y - fy
    dist = math.hypot(dx, dy)
    bearing = math.degrees(math.atan2(dy, dx)) % 360
    relative = (bearing - fh + 360) % 360
    if relative <= 45 or relative > 315:
        arc = "front"
    elif relative <= 135:
        arc = "left"
    elif relative <= 225:
        arc = "rear"
    else:
        arc = "right"
    score = 0.0
    for w in ship.weapons:
        if w.get("weapon_type") not in ("battery", "lance", "nova_cannon"):
            continue
        arcs = w.get("arcs", [])
        if arcs and arc not in arcs:
            continue
        strength = w.get("strength", 1)
        w_range = w.get("range_cm", 0)
        if w_range == 0 or dist <= w_range:
            score += strength
        else:
            score += strength * (w_range / dist) * 0.5
    return score


# ── Evaluation function ───────────────────────────────────────────────────────

# Risk preference (owner, To do 2): with a turn limit the expert AI scores
# a position by its chance of winning, not expected VP alone, so behind with
# few turns left it gambles and ahead it plays safe. RISK_TIEBREAK keeps a
# little expected VP in the score so the search still prefers more VP when
# the result is all but settled (judgement).
RISK_TIEBREAK = 0.1


def win_score(margin: float, activity: float, mean_value: float, turns_left: int,
              total_pts: float) -> float:
    """Chance of winning from a VP `margin` with `turns_left` game turns to
    play (normal approximation), plus RISK_TIEBREAK x margin / total_pts. The
    spread comes from the fighting still to come: a turn's VP swing is lumpy
    (a ship of value V dies or it doesn't: variance about V x its expected
    VP), so variance ~ turns left x mean ship value x `activity` (both sides'
    expected VP a turn). More activity (closing to brawl, all-in strikes)
    widens the spread: worth it when behind, not when ahead."""
    import math as _m
    from .ai_hazards import outcome_sigma
    sigma = outcome_sigma(turns_left, mean_value, activity, total_pts)
    p = 0.5 * (1.0 + _m.erf(margin / (sigma * _m.sqrt(2.0))))
    return p + RISK_TIEBREAK * margin / (total_pts or 1)


def _evaluate(state: SimState, ai_player: int) -> float:
    """Score state from ai_player's perspective, in VP over the total points
    on the table: VP banked so far (destroyed full, crippled 25%, s.38) plus
    next turn's expected VP swing (each side's focused, no-overkill shooting
    from where it stands, _apply_expected_combat) at LATER_TURN_WEIGHT, the
    weight the normal AI gives the next turn. With a turn limit (owner): the
    chance of winning from that margin with the turns left (win_score), so the
    search takes risks when behind near the end and plays safe when ahead."""
    from .ai_hazards import LATER_TURN_WEIGHT
    enemy = 3 - ai_player
    total_pts = sum(s.points_value for s in state.ships) or 1

    def banked(victim_player):
        return sum(s.points_value if s.is_destroyed else
                   (0.25 * s.points_value if s.is_crippled else 0.0)
                   for s in state.ships if s.player == victim_player)
    vp_diff = banked(enemy) - banked(ai_player)
    mine = _apply_expected_combat(state.clone(), ai_player)
    if any(o.owner == ai_player for o in state.ordnance):
        mine += _ordnance_swing(state, ai_player)
    theirs = _apply_expected_combat(state.clone(), enemy)
    margin = vp_diff + LATER_TURN_WEIGHT * (mine - theirs)
    if not state.turn_limit:
        return margin / total_pts
    alive = [s.points_value for s in state.ships if s.is_alive]
    mean_value = sum(alive) / len(alive) if alive else 0.0
    turns_left = max(0, state.turn_limit - state.turn + 1)
    return win_score(margin, mine + theirs, mean_value, turns_left, total_pts)


def _ordnance_swing(state: SimState, player: int) -> float:
    """VP `player`'s ordnance in flight scores next turn (the leaf's swing)."""
    enemy = 3 - player
    s = state.clone()

    def worth(st):
        return sum(_sim_value(x, x.hits_remaining) for x in st.alive(enemy)) + sum(
            x.points_value for x in st.ships if x.player == enemy and x.is_destroyed)
    before = worth(s)
    _resolve_ordnance(s, player)
    return worth(s) - before


# ── Simulate one full turn ────────────────────────────────────────────────────

def _simulate_turn(state: SimState,
                   ai_player: int,
                   my_moves: Dict[str, Tuple[float, float]],
                   enemy_moves: Dict[str, Tuple[float, float]]) -> SimState:
    """Apply one full game turn deterministically and return the new state."""
    s = state.clone()
    # Shields come back up each turn (blast markers are not tracked here)
    for ship in s.ships:
        if ship.is_alive:
            ship.shields_remaining = ship.shields_max if not ship.is_crippled else \
                (ship.shields_max + 1) // 2
    # Movement (both sides simultaneously — simpler; ignores interaction)
    for ship in s.ships:
        moves = my_moves if ship.player == ai_player else enemy_moves
        if ship.id in moves and ship.is_alive:
            turn_deg, dist = moves[ship.id]
            _apply_move(ship, turn_deg, dist)
            # Clamp to the table
            ship.x = max(0.0, min(s.table_w, ship.x))
            ship.y = max(0.0, min(s.table_h, ship.y))
    # Combat: AI shoots first, then enemy; then our ordnance in flight
    _apply_expected_combat(s, ai_player)
    _apply_expected_combat(s, 3 - ai_player)
    if s.ordnance:
        _resolve_ordnance(s, ai_player)
    s.turn += 1
    return s


# ── Alpha-beta minimax ────────────────────────────────────────────────────────

_INF = math.inf


def _minimax(state: SimState, depth: int,
             alpha: float, beta: float, maximising: bool,
             ai_player: int, deadline: float,
             ai_ref: "LookaheadAI") -> float:
    if time.monotonic() > deadline or depth == 0 or state.is_terminal():
        return _evaluate(state, ai_player)

    active = ai_player if maximising else 3 - ai_player
    passive = 3 - active

    my_moves    = _generate_best_moves(state, active,  ai_ref)
    enemy_moves = _generate_best_moves(state, passive, ai_ref)

    # Generate B candidate perturbations of the active player's moves,
    # then evaluate each and keep the best B for recursion.
    candidates: List[Tuple[float, SimState]] = []
    ta = 45  # typical turn angle
    for tdelta, sfrac in _TURN_FRACS[:6]:   # 6 lightweight variants
        tweaked = {}
        for ship in state.alive(active):
            base_td, base_dist = my_moves.get(ship.id, (0.0, ship.speed * 0.8))
            turn_deg = max(-ta, min(ta, base_td + tdelta * ship.turn_angle))
            dist     = max(1, int(base_dist * sfrac)) if sfrac < 1 else base_dist
            tweaked[ship.id] = (turn_deg, dist)
        next_s = _simulate_turn(state, ai_player, tweaked, enemy_moves)
        score = _evaluate(next_s, ai_player)
        candidates.append((score, next_s))

    candidates.sort(key=lambda x: -x[0] if maximising else x[0])
    B = 4  # beam width

    if maximising:
        value = -_INF
        for _, child in candidates[:B]:
            value = max(value, _minimax(child, depth - 1, alpha, beta,
                                        False, ai_player, deadline, ai_ref))
            alpha = max(alpha, value)
            if alpha >= beta:
                break
        return value
    else:
        value = _INF
        for _, child in candidates[:B]:
            value = min(value, _minimax(child, depth - 1, alpha, beta,
                                        True, ai_player, deadline, ai_ref))
            beta = min(beta, value)
            if beta <= alpha:
                break
        return value


# ── LookaheadAI class ─────────────────────────────────────────────────────────

class LookaheadAI(AIPlayer):
    """Expert difficulty: uses minimax with 5-turn lookahead for movement."""

    DEPTH = 5
    TIME_BUDGET = 2.0  # seconds per ship decision
    ROOT_MOVES = 12    # root candidates searched, best first by the move score

    def _plan_move_toward(self, ship: Ship, enemy: Ship,
                          order: str, aaf_bonus: int) -> List[MoveCommand]:
        """Override: choose move using minimax search rather than greedy heuristic."""
        min_spd, max_spd = get_effective_speed(ship, order, aaf_bonus)
        deadline = time.monotonic() + self.TIME_BUDGET

        state = SimState.from_gs(self.gs, ord_player=self.player)
        best_cmds = None
        best_score = -_INF
        from .ai_hazards import move_hazard_vp
        vp_scale = self._vp_to_score(state)

        # Root moves: the normal AI's candidates (To do 11 a: grid, turn points,
        # goals), best first by its move score so alpha-beta and the time
        # budget spend their effort on the likeliest moves; at most ROOT_MOVES
        cands = []
        for c in self._move_candidates(ship, enemy, order, aaf_bonus):
            cands.append((self._move_score(ship, enemy, order, *c[:3]), c))
        cands.sort(key=lambda x: -x[0])
        for _normal, (turn_deg, dist, turn_at, _src) in cands[:self.ROOT_MOVES]:
            candidate = state.clone()
            sim_ship = next((s for s in candidate.ships if s.id == ship.id), None)
            if sim_ship is None:
                continue
            fx, fy, fh = self._simulate_final_pos(ship, turn_deg, dist, turn_at)
            sim_ship.x, sim_ship.y, sim_ship.heading = fx, fy, fh

            enemy_moves = _generate_best_moves(candidate, 3 - self.player, self)
            next_s = _simulate_turn(candidate, self.player, {}, enemy_moves)
            score = _minimax(next_s, self.DEPTH - 1, -_INF, _INF,
                             False, self.player, deadline, self)
            # Hazards on the way (To do 11 b): the search's sim has no terrain
            # and only our own ordnance, so the root move pays the normal AI's
            # path-hazard cost (mines, torpedoes, attack craft in flight,
            # asteroid fields, warp rifts, clouds, blast markers) in the
            # search's score units
            path = self._simulate_path(ship, turn_deg, dist, turn_at)
            score -= vp_scale * move_hazard_vp(ship, (fx, fy), path, self.gs, order)["vp"]

            if score > best_score:
                best_score = score
                best_cmds = self._move_cmds(ship, turn_deg, dist, turn_at)

            if time.monotonic() > deadline:
                break  # time's up; use best found so far

        return best_cmds or super()._plan_move_toward(ship, enemy, order, aaf_bonus)

    def _vp_to_score(self, state: SimState) -> float:
        return _vp_scale_for(state, self.gs, self.player)


def _vp_scale_for(state: SimState, gs, player: int) -> float:
    """Score units per VP for the root's hazard cost: _evaluate's units (VP
    over the points on the table); with a turn limit, the slope of win_score
    at the current margin (a VP matters most when the game is close)."""
    import math as _m
    total = sum(s.points_value for s in state.ships) or 1
    if not state.turn_limit:
        return 1.0 / total
    from .ai_hazards import game_risk
    risk = game_risk(gs, player)
    if risk is None:
        return 1.0 / total
    margin, sigma = risk
    density = _m.exp(-0.5 * (margin / sigma) ** 2) / (sigma * _m.sqrt(2 * _m.pi))
    return density + RISK_TIEBREAK / total


def _cmds_for_move(ship: Ship, turn_deg: float, dist: float,
                   order: str) -> List[MoveCommand]:
    """Convert (turn_deg, dist) to a MoveCommand sequence."""
    min_td = MIN_TURN_DISTANCE.get(ship.ship_type, 0)
    cmds: List[MoveCommand] = []
    if abs(turn_deg) < 0.5:
        cmds.append(MoveCommand("forward", dist))
    else:
        if min_td > 0 and dist > min_td:
            cmds.append(MoveCommand("forward", min_td))
        cmds.append(MoveCommand(
            "turn_left" if turn_deg > 0 else "turn_right", abs(turn_deg)))
        rem = dist - (min_td if 0 < min_td < dist else 0)
        if rem > 0:
            cmds.append(MoveCommand("forward", rem))
    return cmds
