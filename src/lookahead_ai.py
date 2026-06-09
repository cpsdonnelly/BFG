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
        )

    @classmethod
    def from_ship(cls, ship: Ship) -> "SimShip":
        return cls(
            id=ship.id, player=ship.player, x=ship.x, y=ship.y,
            heading=ship.heading, speed=ship.speed,
            turn_angle=ship.turn_angle, ship_type=ship.ship_type,
            points_value=ship.points_value,
            hits_remaining=ship.hits_remaining, hits_max=ship.hits_max,
            shields_remaining=ship.shields_remaining, shields_max=ship.shields_max,
            armor_prow=ship.armor_prow, armor_side=ship.armor_side,
            weapons=ship.weapons,
        )

    def bearing_to(self, tx: float, ty: float) -> float:
        return bearing_between(self.x, self.y, tx, ty)

    def get_arc(self, tx: float, ty: float) -> str:
        return arc_name_for_bearing(self.bearing_to(tx, ty), self.heading)


@dataclass
class SimState:
    ships: List[SimShip]
    turn: int
    turn_limit: Optional[int]

    @classmethod
    def from_gs(cls, gs: GameState) -> "SimState":
        ships = [SimShip.from_ship(Ship.from_dict(s)) for s in gs.ships]
        return cls(ships=ships, turn=gs.turn_number, turn_limit=gs.turn_limit)

    def clone(self) -> "SimState":
        return SimState(
            ships=[s.clone() for s in self.ships],
            turn=self.turn,
            turn_limit=self.turn_limit,
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

def _expected_weapon_hits(attacker: SimShip, weapon: Dict,
                          target: SimShip) -> float:
    """Expected hull hits from one weapon (deterministic, no dice)."""
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
    strength = weapon.get("strength", 1)
    target_arc = target.get_arc(attacker.x, attacker.y)
    armor = parse_armor(target.armor_prow if target_arc == "front" else target.armor_side)
    hit_prob = max(0.0, (7 - armor) / 6.0)
    return strength * hit_prob


def _apply_expected_combat(state: SimState, shooter_player: int) -> None:
    """Apply expected (deterministic) combat damage for one player's shooting."""
    shooters = state.alive(shooter_player)
    targets  = state.alive(3 - shooter_player)
    if not targets:
        return

    for attacker in shooters:
        # Pick the target with the highest expected damage (mirrors hard AI)
        best_target: Optional[SimShip] = None
        best_dmg = -1.0
        for t in targets:
            total = sum(_expected_weapon_hits(attacker, w, t)
                        for w in attacker.weapons)
            if total > best_dmg:
                best_dmg = total
                best_target = t
        if best_target is None or best_dmg <= 0:
            continue
        # Apply damage: shields absorb first, then hull
        raw = best_dmg
        absorbed = min(best_target.shields_remaining, raw)
        best_target.shields_remaining -= absorbed
        hull_dmg = raw - absorbed
        best_target.hits_remaining = max(0, best_target.hits_remaining - hull_dmg)
        if best_target.hits_remaining <= 0:
            best_target.is_destroyed = True


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
            score -= ai_player_ref._position_penalty(fx, fy)
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

def _evaluate(state: SimState, ai_player: int) -> float:
    """Score state from ai_player's perspective.  Approx range -1..+1."""
    enemy = 3 - ai_player
    total_pts = sum(s.points_value for s in state.ships) or 1

    my_score = sum(s.points_value for s in state.ships
                   if s.player == enemy and s.is_destroyed)
    my_score += sum(s.points_value * 0.25 for s in state.ships
                    if s.player == enemy and s.is_crippled and not s.is_destroyed)
    en_score = sum(s.points_value for s in state.ships
                   if s.player == ai_player and s.is_destroyed)
    en_score += sum(s.points_value * 0.25 for s in state.ships
                    if s.player == ai_player and s.is_crippled and not s.is_destroyed)
    vp_diff = (my_score - en_score) / total_pts

    # Tactical bonus: relative firepower
    def fp(attacker_player: int) -> float:
        targets = state.alive(3 - attacker_player)
        if not targets:
            return 0.0
        total = 0.0
        for a in state.alive(attacker_player):
            nearest = min(targets, key=lambda t: math.hypot(t.x - a.x, t.y - a.y))
            for w in a.weapons:
                total += _expected_weapon_hits(a, w, nearest)
        return total

    my_fp = fp(ai_player)
    en_fp = fp(enemy)
    fp_diff = (my_fp - en_fp) / max(1.0, my_fp + en_fp)

    return 0.7 * vp_diff + 0.3 * fp_diff


# ── Simulate one full turn ────────────────────────────────────────────────────

def _simulate_turn(state: SimState,
                   ai_player: int,
                   my_moves: Dict[str, Tuple[float, float]],
                   enemy_moves: Dict[str, Tuple[float, float]]) -> SimState:
    """Apply one full game turn deterministically and return the new state."""
    s = state.clone()
    # Movement (both sides simultaneously — simpler; ignores interaction)
    for ship in s.ships:
        moves = my_moves if ship.player == ai_player else enemy_moves
        if ship.id in moves and ship.is_alive:
            turn_deg, dist = moves[ship.id]
            _apply_move(ship, turn_deg, dist)
            # Clamp to table
            ship.x = max(0.0, min(120.0, ship.x))
            ship.y = max(0.0, min(120.0, ship.y))
    # Combat: AI shoots first, then enemy
    _apply_expected_combat(s, ai_player)
    _apply_expected_combat(s, 3 - ai_player)
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

    def _plan_move_toward(self, ship: Ship, enemy: Ship,
                          order: str, aaf_bonus: int) -> List[MoveCommand]:
        """Override: choose move using minimax search rather than greedy heuristic."""
        min_spd, max_spd = get_effective_speed(ship, order, aaf_bonus)
        ta = ship.turn_angle
        deadline = time.monotonic() + self.TIME_BUDGET

        state = SimState.from_gs(self.gs)
        best_cmds = None
        best_score = -_INF

        for turn_mult, speed_frac in _TURN_FRACS:
            turn_deg = ta * turn_mult
            dist = max(min_spd, int(max_spd * speed_frac))
            if dist < 1:
                continue
            min_td = MIN_TURN_DISTANCE.get(ship.ship_type, 0)
            if abs(turn_deg) > 0.5 and min_td > 0 and dist <= min_td:
                continue

            # Apply this candidate move to a clone and start search
            candidate = state.clone()
            sim_ship = next((s for s in candidate.ships if s.id == ship.id), None)
            if sim_ship is None:
                continue
            _apply_move(sim_ship, turn_deg, dist)

            enemy_moves = _generate_best_moves(candidate, 3 - self.player, self)
            next_s = _simulate_turn(candidate, self.player,
                                    {ship.id: (turn_deg, dist)}, enemy_moves)
            score = _minimax(next_s, self.DEPTH - 1, -_INF, _INF,
                             False, self.player, deadline, self)

            if score > best_score:
                best_score = score
                best_cmds = _cmds_for_move(ship, turn_deg, dist, order)

            if time.monotonic() > deadline:
                break  # time's up; use best found so far

        return best_cmds or super()._plan_move_toward(ship, enemy, order, aaf_bonus)


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
