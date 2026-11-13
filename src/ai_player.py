"""Heuristic AI player for singleplayer mode.

Drives movement, shooting, and ordnance phases using pure-logic APIs,
with no Tkinter dialogs. Caller must set dice.mode = "auto" before use.
"""
import math
import random
from typing import List, Optional, Dict

from .models import (Ship, OrdnanceMarker, SpecialOrder,
                     signed_angle_diff)
from .game_state import GameState
from .turn_controller import TurnController
from .dice import DiceRoller
from .geometry import current_shields
from .movement import do_command_check
from .movement import (
    MoveCommand, validate_movement, execute_movement, record_staged_move,
    get_effective_speed, get_max_turns,
)
from .combat import (
    check_weapon_in_arc, check_weapon_in_range, check_los_clear,
    resolve_batteries, resolve_lances, apply_damage,
    squadron_group, fire_at_squadron, weapon_fire_pool, shot_weapon,
    weapon_disabled_by_crit,
)
from .chapter_tactics import shadow_engines_hidden
from .ordnance import ship_torpedo_types, SHORT_BURN_SPEED, unused_once_torpedoes
from .ordnance import (launch_torpedoes, launch_attack_craft,
                       bay_launch_capacity, fleet_craft_slots,
                       fleet_craft_excess, recall_craft, ai_craft_to_recall,
                       TORPEDO_SPEED_DEFAULT)


def _brace_hull_hits(gs: GameState, target: Ship, incoming_hits: int,
                     attacker: Ship = None) -> float:
    """Expected hull hits the brace would face: the current volley past shields
    plus follow-on fire from enemies that haven't fired yet (the attacker's
    other weapons included)."""
    shields = current_shields(target, gs.get_blast_markers())
    current_hull = max(0, incoming_hits - shields)
    shields_left = max(0, shields - incoming_hits)
    future_hull = 0.0
    phenomena = gs.get_phenomena()
    blast_markers = gs.get_blast_markers()
    for enemy in gs.get_ships():
        if enemy.player == target.player or enemy.is_destroyed or enemy.is_disengaged:
            continue
        # Include the current attacker (may have more weapons); skip others
        # that have already fully fired this phase.
        if enemy.has_fired and (attacker is None or enemy.id != attacker.id):
            continue
        for weapon in enemy.weapons:
            if weapon.get("weapon_type", "") not in ("battery", "lance"):
                continue
            if not check_weapon_in_arc(enemy, weapon, target.x, target.y):
                continue
            if not check_weapon_in_range(enemy, weapon, target.x, target.y):
                continue
            if not check_los_clear(enemy, target, phenomena, blast_markers).get("clear", True):
                continue
            armor_num = target.armor_vs(enemy.x, enemy.y)
            expected = weapon.get("strength", 1) * max(0.0, (7 - armor_num) / 6.0)
            future_hull += max(0.0, expected - shields_left)
            shields_left = max(0.0, shields_left - expected)
    return current_hull + future_hull


def brace_value(gs: GameState, target: Ship, incoming_hits: int,
                attacker: Ship = None) -> float:
    """Expected VP (risk-adjusted) of trying Brace for Impact now (s.7; To do
    11 c, priced instead of a fixed share of the hits left). Gain: a 4+ save on
    every hull hit from here to the end of the ship's next turn (hits ~ Poisson,
    braced Poisson at half); the loss of k hits is the ship's value if
    destroyed, a quarter if newly crippled, plus its next turn of fire lost
    (all of it / half), plus a little per hit (damage_vp's terms). Cost if it
    passes: half its fire until the end of its next turn (`ship_threat_vp`),
    twice when the brace comes in
    its own turn before it has fired. With a turn limit both choices are valued
    by their certainty equivalents (To do 2: ahead, a ship braces more readily,
    as a brace narrows the spread; behind, less). Pass chance: the command
    check with Under Fire / Enemy Contacts (s.6)."""
    from .ai_hazards import (p_sum_at_most, ship_value, ship_threat_vp,
                             certainty_equivalent, poisson_pmf)
    from .geometry import count_blast_markers_touching
    hull = _brace_hull_hits(gs, target, incoming_hits, attacker)
    if hull <= 0:
        return 0.0
    v = ship_value(target, gs)
    threat = ship_threat_vp(target, gs)
    rem = max(1, target.hits_remaining)
    to_cripple = rem - target.hits_max // 2
    vph = v / max(1, target.hits_max)

    def loss(k):
        if k >= rem:
            return v + (threat * (2.0 if target.is_crippled else 1.0))
        out = 0.2 * vph * k
        if not target.is_crippled and to_cripple > 0 and k >= to_cripple:
            out += 0.25 * v + 0.5 * threat
        return out

    def dist(mean):
        kmax = rem + 1
        pts = [(poisson_pmf(mean, k), -loss(k)) for k in range(kmax)]
        tail = 1.0 - sum(p for p, _ in pts)
        pts.append((max(0.0, tail), -loss(kmax)))
        return pts

    ld = target.leadership
    if count_blast_markers_touching(target, gs.get_blast_markers()) > 0:
        ld -= 1
    if any(s.player != target.player and not s.is_destroyed and not s.is_disengaged
           and s.special_order not in ("none", "") for s in gs.get_ships()):
        ld += 2 if "improved_sensor_array" in target.special_rules else 1
    ld = max(0, min(10, ld))
    p = p_sum_at_most(2, ld) if ld > 1 else 0.0
    cost = 0.5 * threat
    if gs.active_player == target.player and not target.has_fired:
        cost *= 2.0
    plain = dist(hull)
    braced = ([(p * q, d - cost) for q, d in dist(hull / 2.0)]
              + [((1 - p) * q, d) for q, d in plain])
    player = target.player
    return certainty_equivalent(gs, player, braced) - certainty_equivalent(gs, player, plain)


def ai_should_brace_vs_raid(gs: GameState, target: Ship, attacker: Ship,
                            raids: int = 1) -> bool:
    """Brace against a teleport attack (To do 8 j (3)): a passed brace saves
    the raid on 4+ (half its expected VP, waves.raid_squadron_value), for half
    the ship's fire to the end of its next turn (ship_threat_vp), at the
    command check's odds; the pass chance cancels out, so brace when the
    saving beats the cost."""
    from .waves import raid_squadron_value
    from .ai_hazards import ship_threat_vp
    saving = 0.5 * raids * raid_squadron_value(target, gs, attacker.player,
                                               attacker.special_rules)
    cost = 0.5 * ship_threat_vp(target, gs)
    return saving > cost


def ai_should_brace(gs: GameState, target: Ship,
                    incoming_hits: int, attacker: Ship = None) -> bool:
    """Decide whether an AI-controlled ship should attempt Brace For Impact:
    when its priced value is positive (`brace_value`). incoming_hits: hits
    from the current volley before shields."""
    return brace_value(gs, target, incoming_hits, attacker) > 0.0


class AIPlayer:
    """
    Drives one player's movement, shooting, and ordnance phases
    using pure-logic backend APIs.

    Difficulty tiers:
      easy   — no special orders, random target selection
      normal — situational orders, weakest-HP% target
      hard   — aggressive orders, focus-fire on crippled ships
    """

    def __init__(self, player: int, tc: TurnController,
                 gs: GameState, dice: DiceRoller,
                 difficulty: str = "normal"):
        self.player = player
        self.tc = tc
        self.gs = gs
        self.dice = dice
        self.difficulty = difficulty

    # ── Movement phase ───────────────────────────────────────────────────────

    def run_movement_phase(self):
        gs = self.gs
        tc = self.tc

        my_ships = [s for s in gs.player_ships(self.player)
                    if not s.is_destroyed and not s.is_disengaged
                    and s.id not in tc.ships_moved]

        # Explosion risk / opportunity for this phase's moves (owner): where the
        # enemy is likely to focus, and what our guns can put on each enemy
        self._enemy_plan, self._our_hits = {}, {}
        if self.difficulty != "easy":
            from .ai_hazards import enemy_fire_plan, fleet_hits_on
            self._enemy_plan = enemy_fire_plan(gs, self.player)
            self._our_hits = fleet_hits_on(gs, self.player)
        # Fleet focus (owner): the enemy ship the fleet concentrates on this turn
        self._focus = None
        self._focus_map = {}
        if self.difficulty != "easy":
            from .ai_hazards import fleet_focus_targets, fleet_focus_assignment
            ranked = fleet_focus_targets(gs, self.player)
            self._focus = ranked[0][1].id if ranked else None
            # Several focus targets: each ship's guns where they add the most VP
            # given the rest of the fleet's (owner: focus fire)
            self._focus_map = fleet_focus_assignment(gs, self.player)
            if ranked:
                gs.add_log(f"[AI] fleet focus: {ranked[0][1].name} (about "
                           f"{ranked[0][0]:.0f} VP in reach)")
            groups = {}
            for sid, eid in self._focus_map.items():
                groups.setdefault(eid, []).append(sid)
            if len(groups) > 1:
                names = ", ".join(f"{gs.get_ship_by_id(e).name} ({len(v)})"
                                  for e, v in groups.items())
                gs.add_log(f"[AI] focus targets: {names}")
        self._order_plan = None
        if self.difficulty != "easy":
            my_ships = self._coordinated_order(my_ships)
            self._plan_orders(my_ships)
        for ship in my_ships:
            self._move_ship(ship)
        self._order_plan = None
        if self.difficulty != "easy":
            for ship in my_ships:
                self._consider_disengage(gs.get_ship_by_id(ship.id))

    @staticmethod
    def _coordinated_order(ships: List[Ship]) -> List[Ship]:
        """Move order for fleet coordination (To do 11 a, a first step towards
        the coordination pass): the ships others support move first, so the
        supporters plan against where they end: the commander's ship, then
        carriers, other capital ships, escorts last (they screen, s.29).
        Squadrons stay together (a squadron goes at its earliest member's
        place); otherwise fleet order."""
        def rank(s):
            if s.is_flagship:
                return 0
            if any(w.get("weapon_type") == "launch_bay" for w in s.weapons):
                return 1
            return 3 if s.ship_type == "escort" else 2
        group_rank = {}
        for s in ships:
            if s.squadron_id:
                group_rank[s.squadron_id] = min(group_rank.get(s.squadron_id, 9), rank(s))
        first = {}
        for i, s in enumerate(ships):
            first.setdefault(s.squadron_id or s.id, i)
        return sorted(ships, key=lambda s: (group_rank.get(s.squadron_id, rank(s))
                                            if s.squadron_id else rank(s),
                                            first[s.squadron_id or s.id]))

    def _consider_disengage(self, ship: Optional[Ship]):
        """Voluntary disengagement (s.37) at the end of movement when it is worth
        more in expected VP than fighting on (ai_hazards.disengage_gain): mostly
        crippled ships about to be destroyed. Escort squadrons and ships already
        made to flee are left to the existing rules."""
        from .ai_hazards import disengage_gain
        from .ai_rerolls import firepower_outcomes
        from .disengage import get_disengage_ld_modifiers, attempt_disengage, _ftl_blocked
        gs = self.gs
        if (ship is None or ship.is_destroyed or ship.is_disengaged
                or getattr(ship, "must_flee", False) or ship.status != "active"):
            return
        if ship.ship_type == "escort" and ship.squadron_id and any(
                s.squadron_id == ship.squadron_id and s.id != ship.id
                for s in gs.get_ships() if s.player == ship.player and not s.is_destroyed
                and not s.is_disengaged):
            return
        if _ftl_blocked(ship, gs):
            return
        ld = get_disengage_ld_modifiers(ship, gs)["effective_ld"]
        ev_fire, fire_outs = firepower_outcomes(ship, gs)
        gain = disengage_gain(ship, gs, ld, ev_fire, fire_outs)
        if gain <= 0:
            return
        gs.add_log(f"[AI] {ship.name} tries to disengage (Ld {ld}; worth about "
                   f"{gain:.0f} VP)")
        attempt_disengage(ship, self.dice, gs)

    def _move_ship(self, ship: Ship):
        gs = self.gs
        tc = self.tc

        # Attempt a special order (skip on easy or if check already failed)
        order = ""
        aaf_bonus = 0
        if self.difficulty != "easy" and not tc.command_check_failed:
            chosen = self._choose_special_order(ship)
            if chosen:
                res = tc.issue_special_order(ship, chosen)
                if res.get("success"):
                    gs.add_log(f"[AI] {ship.name}: {chosen} passed")
                    ship = gs.get_ship_by_id(ship.id)
                    order = ship.special_order or ""
                    if order == SpecialOrder.ALL_AHEAD_FULL.value:
                        self._declare_ram(ship)      # before the speed roll (s.12)
                        ship = gs.get_ship_by_id(ship.id)
                        aaf_bonus = self._aaf_bonus(ship)
                else:
                    gs.add_log(f"[AI] {ship.name}: {chosen} failed")
                    ship = gs.get_ship_by_id(ship.id)
                    from .ai_rerolls import should_reroll
                    left = tc.get_fleet_rerolls(ship.player, ship)
                    plan = getattr(self, "_order_plan", None) or {}
                    seq = plan.get("seq", [])
                    blocked = sum(pp * gg for sid in (seq[seq.index(ship.id) + 1:]
                                                      if ship.id in seq else [])
                                  for _oo, gg, pp in [plan.get("orders", {}).get(
                                      sid, (None, 0.0, 0.0))])
                    if left and should_reroll(ship, chosen, gs, left,
                                              {"blocked_orders_vp": blocked}):
                        rr = tc.attempt_reroll_command_check(ship, chosen)
                        gs.add_log(f"[AI] {ship.name}: re-roll for {chosen} "
                                   f"{'passed' if rr.get('success') else 'failed'}")
                        ship = gs.get_ship_by_id(ship.id)
                        if rr.get("success") and ship.special_order == SpecialOrder.ALL_AHEAD_FULL.value:
                            aaf_bonus = self._aaf_bonus(ship)
                    order = ship.special_order or ""
        else:
            order = ship.special_order or ""

        enemy = self._nearest_enemy(ship)
        self._move_nearest = enemy
        focus = self._focus_for(ship)
        if focus is not None:
            enemy = focus
        if ship.must_flee:                 # failed a forced disengage test
            commands = self._plan_flee(ship, order, aaf_bonus)
        else:
            commands = None
        commands = commands or (self._plan_move_toward(ship, enemy, order, aaf_bonus)
                    if enemy else
                    self._forward_commands(ship, order, aaf_bonus, fraction=0.6))

        start = (ship.x, ship.y)
        executed = self._try_execute(ship, commands, order, aaf_bonus)
        if executed:
            ship = gs.get_ship_by_id(ship.id)
            gs.add_log(f"[AI] {ship.name} moved to ({ship.x:.0f},{ship.y:.0f})")
        self._resolve_ram(gs.get_ship_by_id(ship.id), start)
        self._consider_boarding(gs.get_ship_by_id(ship.id))

        tc.mark_ship_moved(ship.id)

    def _ram_candidate(self, ship: Ship):
        """(net VP, target) of the best ram from here (s.12): an enemy dead
        ahead on the straight All Ahead Full line (lateral offset within the
        two bases) and within the move even with the lowest bonus roll, its
        `ram_vp` at the chance of passing the ram's Leadership test (1D6 / 2D6 /
        3D6 by size). None if nothing is worth ramming or ramming is off."""
        from .ai_hazards import ram_vp, p_sum_at_most
        from .combat import ram_ld_dice
        from .movement import aaf_bonus_dice
        if self.difficulty == "easy" or not getattr(self.gs, "rule_ramming", False):
            return None
        reach = (ship.speed or 0) + aaf_bonus_dice(ship)       # every die a 1
        h = math.radians(ship.heading)
        best = None
        for e in self._live_enemies():
            dx, dy = e.x - ship.x, e.y - ship.y
            along = dx * math.cos(h) + dy * math.sin(h)
            side = abs(-dx * math.sin(h) + dy * math.cos(h))
            if along <= 0 or along - e.base_radius > reach or \
                    side > ship.base_radius + e.base_radius:
                continue
            n = ram_ld_dice(ship.ship_type, e.ship_type)
            p = p_sum_at_most(n, ship.leadership) if "goffs" not in ship.special_rules else 1.0
            v = p * ram_vp(ship, e, self.gs)
            if v > 0 and (best is None or v > best[0]):
                best = (v, e)
        return best

    def _declare_ram(self, ship: Ship) -> None:
        """On All Ahead Full, before the speed roll: declare a ram on the best
        target dead ahead and take the Leadership test (s.12; 8 h)."""
        from .combat import ram_ld_dice
        cand = self._ram_candidate(ship)
        if cand is None:
            return
        target = cand[1]
        n = ram_ld_dice(ship.ship_type, target.ship_type)
        if "goffs" in ship.special_rules:
            passed, total = True, 0
        else:
            total = sum(self.dice.roll_d6(n, f"{ship.name} ram Leadership test ({n}D6)"))
            passed = total <= ship.leadership
        if passed:
            ship.ramming_target_id = target.id
            self.gs.update_ship(ship)
            self.gs.add_log(f"[AI] {ship.name} declares a ram on {target.name}")
        else:
            self.gs.add_log(f"[AI] {ship.name} ram on {target.name} fails its Leadership "
                            f"test ({n}D6 = {total})")

    def _resolve_ram(self, ship: Optional[Ship], start) -> None:
        """After the move: a declared ram connects if the path touched the
        target's base (combat.resolve_ram); then it is cleared."""
        if ship is None or not ship.ramming_target_id:
            return
        from .geometry import line_passes_near
        from .combat import resolve_ram
        gs = self.gs
        target = gs.get_ship_by_id(ship.ramming_target_id)
        if target is not None and not target.is_destroyed and line_passes_near(
                start[0], start[1], ship.x, ship.y, target.x, target.y,
                ship.base_radius + target.base_radius):
            gs.add_log(f"[AI] {ship.name} rams {target.name}!")
            resolve_ram(ship, target, self.dice, gs)
            for sid in (target.id, ship.id):
                s2 = gs.get_ship_by_id(sid)
                if s2 is not None:
                    self._resolve_kill(s2)
        ship = gs.get_ship_by_id(ship.id)
        if ship is not None:
            ship.ramming_target_id = None
            gs.update_ship(ship)

    def _boarding_gain(self, ship: Ship, enemy: Ship) -> float:
        """A boarding action's expected VP (ai_hazards.boarding_vp) less what the
        ship gives up: it may not fire or launch ordnance this turn (s.32),
        worth its guns' value (`ai_rerolls.firepower_swing`)."""
        from .ai_hazards import boarding_vp
        from .ai_rerolls import firepower_swing
        if "nicassar" in " ".join(ship.special_rules) or "frail_crew" in ship.special_rules:
            return 0.0                    # Nicassar never initiate boarding
        return boarding_vp(ship, enemy, self.gs) - firepower_swing(ship, self.gs)

    def _consider_boarding(self, ship: Optional[Ship]) -> None:
        """To do 8 h: after moving, declare a boarding action against the enemy
        in base contact where it is worth most, when its value beats the fire
        given up. Only with the boarding rule on (owner)."""
        gs = self.gs
        if (ship is None or self.difficulty == "easy" or not getattr(gs, "rule_boarding", False)
                or ship.has_boarded or ship.is_grappled or ship.is_destroyed):
            return
        from .boarding import ships_in_base_contact
        best = None
        for e in self._live_enemies():
            if e.status in ("drifting_hulk", "burning_hulk") or not ships_in_base_contact(ship, e):
                continue
            g = self._boarding_gain(ship, e)
            if g > 0 and (best is None or g > best[0]):
                best = (g, e)
        if best is None:
            return
        ship.boarding_target_id = best[1].id
        ship.has_boarded = True
        gs.update_ship(ship)
        gs.add_log(f"[AI] {ship.name} declares a boarding action against {best[1].name} "
                   f"(worth about {best[0]:.0f} VP)")

    def _try_execute(self, ship: Ship, commands: List[MoveCommand],
                     order: str, aaf_bonus: int) -> bool:
        """Attempt to execute commands; fall back to simpler moves if invalid."""
        gs = self.gs
        kwargs = dict(
            special_order=order, aaf_bonus=aaf_bonus,
            blast_markers=gs.get_blast_markers(),
            table_width=gs.table_width, table_height=gs.table_height,
        )

        def execute(result, cmds) -> bool:
            execute_movement(ship, result, gs, self.dice)
            record_staged_move(gs, ship.id, result, cmds)
            return True

        r = validate_movement(ship, commands, **kwargs)
        if r.valid:
            return execute(r, commands)

        # Blast markers shortened the move: go straight ahead as far as allowed
        if r.crossed_blast_markers and r.max_allowed > 0:
            cb = [MoveCommand("forward", r.max_allowed)]
            rb = validate_movement(ship, cb, **kwargs)
            if rb.valid:
                return execute(rb, cb)

        # Fallback: straight forward at half speed
        min_spd, max_spd = get_effective_speed(ship, order, aaf_bonus)
        dist = max(min_spd, max_spd / 2)
        c2 = [MoveCommand("forward", dist)]
        r2 = validate_movement(ship, c2, **kwargs)
        if r2.valid:
            return execute(r2, c2)

        # Last resort: minimum speed
        if min_spd > 0:
            c3 = [MoveCommand("forward", min_spd)]
            r3 = validate_movement(ship, c3, **kwargs)
            if r3.valid:
                return execute(r3, c3)

        return False

    def _plan_move_toward(self, ship: Ship, enemy: Ship,
                          order: str, aaf_bonus: int) -> List[MoveCommand]:
        """Choose the move worth most against `enemy` (the move score below)
        among the candidates of `_move_candidates` (To do 11 a: an even grid
        plus target-directed goals)."""
        best_cmds: Optional[List[MoveCommand]] = None
        best_score = -1.0
        best_src = None
        scored = []
        for cand in self._move_candidates(ship, enemy, order, aaf_bonus):
            turn_deg, dist, turn_at, src = cand
            score = self._move_score(ship, enemy, order, turn_deg, dist, turn_at)
            scored.append((score, cand))
            if score > best_score:
                best_score, best_src = score, src
                best_cmds = self._move_cmds(ship, turn_deg, dist, turn_at)
        if scored and self.difficulty == "easy":
            # To do 11 i: Easy picks by softmax on the move score (temperature
            # EASY_TEMPERATURE, judgement), so it errs like a person: usually a
            # good move, sometimes a worse one, never at random
            top = max(sc for sc, _c in scored)
            weights = [math.exp((sc - top) / self.EASY_TEMPERATURE) for sc, _c in scored]
            pick = random.choices(range(len(scored)), weights=weights)[0]
            turn_deg, dist, turn_at, src = scored[pick][1]
            self._last_move_source = src + " (easy)"
            return self._move_cmds(ship, turn_deg, dist, turn_at)
        if scored and self.difficulty != "easy":
            # Refine the best few (To do 11 a, coarse-to-fine)
            valid = self._candidate_validator(ship, order, aaf_bonus)
            scored.sort(key=lambda x: -x[0])
            for sc, cand in scored[:3]:
                if not valid(*cand[:3]):
                    continue
                ref, rs = self._refine_move(ship, enemy, order, aaf_bonus, cand, sc, valid)
                if rs > best_score + 1e-9:
                    best_score, best_src = rs, ref[3] + " (" + cand[3] + ")"
                    best_cmds = self._move_cmds(ship, ref[0], ref[1], ref[2])
        self._last_move_source = best_src            # diagnostic (11 a e)
        if best_cmds is None:
            min_spd, max_spd = get_effective_speed(ship, order, aaf_bonus)
            return [MoveCommand("forward", max(min_spd, max_spd / 2))]
        return best_cmds

    def _move_score(self, ship: Ship, enemy: Ship, order: str, turn_deg: float,
                    dist: float, turn_at: Optional[float]) -> float:
        """The move score of one candidate: guns that bear on the target (0.3
        of those on the nearest enemy), minus hazards and flagship danger on
        the way, exposure, carrier exposure, plus screening and explosions."""
        fx, fy, fh = self._simulate_final_pos(ship, turn_deg, dist, turn_at)
        path = self._simulate_path(ship, turn_deg, dist, turn_at)
        score = (self._arc_score(ship, fx, fy, fh, enemy)
                 - self._position_penalty(fx, fy, ship, path, order, enemy))
        near = getattr(self, "_move_nearest", None)
        if near is not None and near.id != enemy.id:
            score += 0.3 * self._arc_score(ship, fx, fy, fh, near)
        score += self.COVERAGE_WEIGHT * self._mount_coverage(ship, fx, fy, fh, enemy)
        score += self._kite_bonus(ship, fx, fy, fh, enemy)
        score -= self._exposure_penalty(ship, fx, fy, fh, enemy)
        score -= self._carrier_exposure(ship, fx, fy, enemy)
        score -= self._teleport_exposure(ship, fx, fy, enemy)
        score += self._teleport_reach(ship, fx, fy, enemy, order)
        score += self._boarding_reach(ship, fx, fy, enemy)
        score += self._screen_bonus(ship, fx, fy, fh, enemy)
        score += self._explosion_term(ship, fx, fy, enemy)
        return score

    COVERAGE_WEIGHT = 0.5    # judgement: a mount busy on another enemy vs the target
    EASY_TEMPERATURE = 2.0   # judgement: Easy's softmax temperature (move-score units)
    KITE_WEIGHT = 0.5        # judgement: the band bonus, a share of the guns that bear

    @staticmethod
    def _gun_reach(s: Ship) -> float:
        return max([w.get("range_cm") or 0 for w in s.weapons
                    if w.get("weapon_type") in ("battery", "lance")] or [0])

    def range_speed_edge(self, ship: Ship, enemy: Ship) -> bool:
        """To do 8 c: we out-range the enemy's guns and are at least as fast."""
        return (self._gun_reach(ship) > self._gun_reach(enemy)
                and (ship.effective_speed or 0) >= (enemy.effective_speed or 0))

    def _kite_bonus(self, ship: Ship, x: float, y: float, h: float, enemy: Ship) -> float:
        """To do 8 c (kiting): with a range and speed edge, an end position
        where our guns reach the target but its guns can't reach us even after
        its next move (distance in (its range + its speed, our range]) earns
        KITE_WEIGHT x the guns that bear there. No edge (a brawler such as the
        Slaughter): nothing, so it closes as before. Owner: not a hard rule;
        it adds to the move score's values."""
        if self.difficulty == "easy" or not self.range_speed_edge(ship, enemy):
            return 0.0
        d = math.hypot(enemy.x - x, enemy.y - y)
        theirs = self._gun_reach(enemy) + (enemy.effective_speed or 0)
        if not (theirs < d <= self._gun_reach(ship)):
            return 0.0
        return self.KITE_WEIGHT * self._arc_score(ship, x, y, h, enemy, guns_only=True,
                                                  in_range_only=True)

    def _mount_coverage(self, ship: Ship, x: float, y: float, h: float,
                        target: Ship) -> float:
        """To do 8 b (both broadsides busy): the battery / lance strength at the
        end position that can't bear on the target but can on another enemy
        (in arc and range), so a position with an enemy off each beam beats one
        with both off one side; crossing the T comes out of this and the
        Armour-facing exposure (8 a). Mounts knocked out by crits don't count."""
        if self.difficulty == "easy":
            return 0.0
        others = [e for e in self._live_enemies() if e.id != target.id]
        if not others:
            return 0.0
        import dataclasses
        at = dataclasses.replace(ship, x=x, y=y, heading=h)
        total = 0.0
        for w in ship.weapons:
            if w.get("weapon_type") not in ("battery", "lance"):
                continue
            if weapon_disabled_by_crit(ship, w):
                continue
            if check_weapon_in_arc(at, w, target.x, target.y) and \
                    check_weapon_in_range(at, w, target.x, target.y):
                continue
            if any(check_weapon_in_arc(at, w, e.x, e.y) and check_weapon_in_range(at, w, e.x, e.y)
                   for e in others):
                total += w.get("strength", 0) or 0
        return total

    @staticmethod
    def _move_cmds(ship: Ship, turn_deg: float, dist: float,
                   turn_at: Optional[float]) -> List[MoveCommand]:
        """Commands for a move of `dist` with one turn after `turn_at` cm (by
        default right after the minimum distance before turning)."""
        from .movement import MIN_TURN_DISTANCE
        if abs(turn_deg) <= 0.5:
            return [MoveCommand("forward", dist)]
        t = MIN_TURN_DISTANCE.get(ship.ship_type, 0) if turn_at is None else turn_at
        t = max(0.0, min(dist, t))
        cmds: List[MoveCommand] = []
        if t > 0:
            cmds.append(MoveCommand("forward", t))
        cmds.append(MoveCommand("turn_left" if turn_deg > 0 else "turn_right", abs(turn_deg)))
        if dist - t > 0:
            cmds.append(MoveCommand("forward", dist - t))
        return cmds

    def _candidate_validator(self, ship: Ship, order: str, aaf_bonus: int):
        """valid(turn_deg, dist, turn_at): the same limits `_move_candidates`
        applies (speed, turn angle, turning distance)."""
        from .movement import MIN_TURN_DISTANCE
        from .models import SpecialOrder
        min_spd, max_spd = get_effective_speed(ship, order, aaf_bonus)
        max_t = get_max_turns(order, ship)
        min_td = 0 if order == SpecialOrder.BURN_RETROS.value else \
            MIN_TURN_DISTANCE.get(ship.ship_type, 0)
        ta = ship.turn_angle if max_t > 0 else 0

        def valid(turn_deg, dist, turn_at):
            if dist < 1 or dist < min_spd - 1e-9 or dist > max_spd + 1e-9:
                return False
            if abs(turn_deg) > 0.5:
                if abs(turn_deg) > ta + 1e-9 or turn_at is None:
                    return False
                if turn_at < min_td - 1e-9 or turn_at > dist + 1e-9:
                    return False
            return True
        return valid

    def _move_candidates(self, ship: Ship, enemy: Ship, order: str, aaf_bonus: int):
        """[(turn_deg, dist, turn_at, source)] (To do 11 a, owner):
          - the even grid kept as the fallback: straight, half and full turn
            angle each way, at the minimum move (50%), 60, 80 and 100% of speed,
            turning right after the minimum distance before turning;
          - turn points (the rules for every candidate): a capital ship may
            also turn just after its minimum move (half speed) or at the end of
            its move; escorts anywhere, including at the very start; Burn
            Retros needs no movement before turning;
          - target-directed goals against `enemy`: bring the best guns to bear
            (the end heading, searched every 5 degrees up to the turn angle,
            that maximises the arc score) and a range band (the distance along
            those headings that ends nearest the middle of the range bracket
            where this ship beats the target most, ai_hazards.bracket_matchup;
            none when it beats the target nowhere).
        Candidates propose, the move score decides (owner: not hard rules)."""
        from .movement import MIN_TURN_DISTANCE
        from .models import SpecialOrder
        min_spd, max_spd = get_effective_speed(ship, order, aaf_bonus)
        max_t = get_max_turns(order, ship)
        min_td = 0 if order == SpecialOrder.BURN_RETROS.value else \
            MIN_TURN_DISTANCE.get(ship.ship_type, 0)
        ta = ship.turn_angle if max_t > 0 else 0
        out, seen = [], set()

        def add(turn_deg, dist, turn_at, src):
            if dist < 1 or dist < min_spd - 1e-9 or dist > max_spd + 1e-9:
                return
            if abs(turn_deg) > 0.5:
                if abs(turn_deg) > ta + 1e-9:
                    return
                if turn_at is None:
                    if min_td > 0 and dist <= min_td:
                        return                    # the grid turns after min_td
                    turn_at = float(min_td)       # explicit: simulator = commands
                if turn_at < min_td - 1e-9 or turn_at > dist + 1e-9:
                    return                        # not enough distance to turn
            else:
                turn_at = None
            key = (round(turn_deg, 1), round(dist, 1),
                   None if turn_at is None else round(turn_at, 1))
            if key not in seen:
                seen.add(key)
                out.append((turn_deg, dist, turn_at, src))

        dists = sorted({min_spd, max_spd * 0.6, max_spd * 0.8, max_spd})
        dists = [d for d in dists if d >= min_spd]
        turns = [0.0] + ([-ta, -ta * 0.5, ta * 0.5, ta] if ta else [])
        for t in turns:
            for d in dists:
                add(t, d, None, "grid")
        if self.difficulty == "easy" or not ta:
            return out
        # Turn points: after the minimum move, at the end, at the start (escorts,
        # Burn Retros)
        points = {min_td, max(min_td, min_spd)}
        if min_td == 0:
            points.add(0.0)
        for t in (-ta, -ta * 0.5, ta * 0.5, ta):
            for d in dists:
                for p in sorted(points | {d}):
                    add(t, d, p, "turn point")
        # Goal: bring the best guns to bear on the target
        steps = max(1, int(ta // 5))
        angles = [ta * k / steps for k in range(-steps, steps + 1)]
        best_heads = []
        for p in sorted(points):
            for d in (min_spd, max_spd):
                if d < p:
                    continue
                best = max(angles, key=lambda a: self._arc_score(
                    ship, *self._simulate_final_pos(ship, a, d, p), enemy))
                add(best, d, p, "guns to bear")
                best_heads.append((best, p))
        # Goal: the range band where this ship beats the target most
        band = self._range_band(ship, enemy)
        if band is not None:
            span = max(0.0, max_spd - min_spd)
            n = max(1, int(span))
            for a, p in best_heads + [(t, None) for t in turns]:  # noqa: B007
                cands = [min_spd + span * k / n for k in range(n + 1)]
                cands = [d for d in cands if p is None or d >= p]
                if not cands:
                    continue
                d = min(cands, key=lambda dd: abs(math.hypot(
                    *(lambda q: (q[0] - enemy.x, q[1] - enemy.y))(
                        self._simulate_final_pos(ship, a, dd, p))) - band))
                add(a, d, p, "range band")
        # Point goals (To do 11 a, goals c / d / 3): head for a point, turning at
        # each turn point by the angle that points at it (clamped to the turn
        # angle), ending on it or as close as the move allows ("progress
        # towards" when out of reach this turn)
        from .ai_hazards import _predicted_positions
        nxt = _predicted_positions(enemy, True)[1]
        goals = [((nxt.x, nxt.y), "prow-on")]          # c: closing prow-on
        h = math.radians(nxt.heading)
        behind = max(10.0, min(30.0, band or 15.0))
        # d: out of the target's arcs, into its rear (from its predicted end)
        goals.append(((nxt.x - behind * math.cos(h), nxt.y - behind * math.sin(h)),
                      "rear arc"))
        # a second target: guns to bear on the next nearest enemy too
        others = sorted((e for e in self.gs.get_ships() if e.player != self.player
                         and not e.is_destroyed and not e.is_disengaged
                         and e.id != enemy.id), key=lambda e: ship.distance_to(e))
        if others:
            o = others[0]
            for p in sorted(points):
                for d in (min_spd, max_spd):
                    if d >= p:
                        best = max(angles, key=lambda a: self._arc_score(
                            ship, *self._simulate_final_pos(ship, a, d, p), o))
                        add(best, d, p, "second target")
        # f: boarding reach (8 h), only with the boarding rule on: the point in
        # base contact with the target on our side of it
        if getattr(self.gs, "rule_boarding", False) and self.difficulty != "easy":
            d0 = ship.distance_to(enemy) or 1.0
            k = (enemy.base_radius + ship.base_radius) / d0
            goals.append(((enemy.x - (enemy.x - ship.x) * k, enemy.y - (enemy.y - ship.y) * k),
                          "board"))
        # 3: fleet support, an escort to the commander's ship (massed turrets)
        if ship.ship_type == "escort":
            flag = next((f for f in self.gs.get_ships() if f.player == self.player
                         and f.is_flagship and not f.is_destroyed and not f.is_disengaged
                         and f.id != ship.id), None)
            if flag is not None:
                goals.append(((flag.x, flag.y), "support"))
        for (gx, gy), src in goals:
            self._head_for(ship, gx, gy, points, min_spd, max_spd, ta, add, src)
        # g: Lock On next turn forbids turning, so end pointed for a straight
        # move: guns to bear on where the target will be after its next two
        # moves, from our end position moved straight on at speed
        far = _predicted_positions(enemy, True)[3]
        spd = ship.speed or 0
        for p in sorted(points):
            d = max_spd
            if d < p:
                continue

            def lock_score(a, d=d, p=p):
                x, y, hh = self._simulate_final_pos(ship, a, d, p)
                rx = x + spd * math.cos(math.radians(hh))
                ry = y + spd * math.sin(math.radians(hh))
                return self._arc_score(ship, rx, ry, hh, far)
            add(max(angles, key=lock_score), d, p, "lock on next")
        # Denser grid (hybrid b) when enemy ordnance or terrain crowds the
        # reachable area: the best move may be a gap no goal predicts
        reach = max_spd + 30.0
        crowded = sum(1 for o in self.gs.ordnance if o.get("owner_player") != self.player
                      and math.hypot(o["x"] - ship.x, o["y"] - ship.y) <= reach)
        crowded += sum(1 for ph in self.gs.get_phenomena()
                       if math.hypot(ph.x - ship.x, ph.y - ship.y) <= reach)
        crowded += sum(1 for b in self.gs.get_blast_markers()
                       if math.hypot(b.x - ship.x, b.y - ship.y) <= max_spd)
        if crowded >= 2:
            fine = [ta * k / 4 for k in range(-4, 5)]
            for t in fine:
                for d in sorted({min_spd, (min_spd + max_spd) / 2, max_spd}):
                    for p in sorted(points):
                        add(t, d, p, "dense grid")
        return out

    def _head_for(self, ship: Ship, gx: float, gy: float, points, min_spd: float,
                  max_spd: float, ta: float, add, src: str) -> None:
        """Add the candidate per turn point that ends nearest (gx, gy): go
        straight to the turn point, turn towards the goal (clamped to the turn
        angle), then on for the distance left to it (within the move's
        limits)."""
        r = math.radians
        for p in sorted(points):
            if p > max_spd:
                continue
            px = ship.x + p * math.cos(r(ship.heading))
            py = ship.y + p * math.sin(r(ship.heading))
            want = math.degrees(math.atan2(gy - py, gx - px))
            turn = signed_angle_diff(want, ship.heading)
            turn = max(-ta, min(ta, turn))
            rest = math.hypot(gx - px, gy - py)
            d = max(min_spd, min(max_spd, p + rest))
            add(turn, d, p, src)

    def _refine_move(self, ship: Ship, enemy: Ship, order: str, aaf_bonus: int,
                     start, start_score: float, valid):
        """Coarse-to-fine (To do 11 a, hybrid c): hill-climb a candidate with
        small changes to turn angle, distance and turn point until no change
        scores better (at most 12 steps). `valid(turn, dist, turn_at)` keeps
        every step legal. Returns (candidate, score)."""
        best, best_s = start, start_score
        steps = [(5, 0, 0), (-5, 0, 0), (0, 2, 0), (0, -2, 0), (0, 0, 2), (0, 0, -2),
                 (2, 0, 0), (-2, 0, 0), (0, 1, 0), (0, -1, 0)]
        for _ in range(12):
            improved = False
            t0, d0, p0, _src = best
            for dt, dd, dp in steps:
                cand = (t0 + dt, d0 + dd, None if p0 is None else p0 + dp)
                if abs(cand[0]) <= 0.5:
                    cand = (0.0, cand[1], None)
                elif cand[2] is None:
                    continue
                if not valid(*cand):
                    continue
                sc = self._move_score(ship, enemy, order, *cand)
                if sc > best_s + 1e-9:
                    best, best_s, improved = (cand[0], cand[1], cand[2], "refined"), sc, True
            if not improved:
                break
        return best, best_s

    def _range_band(self, ship: Ship, enemy: Ship) -> Optional[float]:
        """The middle of the range bracket where `ship` beats `enemy` most in
        expected VP per shooting phase (ai_hazards.bracket_matchup, To do 8 f),
        or None when it beats it in none. Cached per pair and turn."""
        from .ai_hazards import bracket_matchup
        cache = self.__dict__.setdefault("_band_cache", {})
        key = (ship.id, enemy.id, self.gs.turn_number, ship.hits_remaining,
               enemy.hits_remaining)
        if key not in cache:
            rows = [(br, o - t) for br, o, t in bracket_matchup(ship, enemy)]
            best = max(rows, key=lambda r: r[1])
            cache[key] = (sum(best[0]) / 2.0) if best[1] > 0 else None
        return cache[key]

    def _focus_for(self, ship: Ship) -> Optional[Ship]:
        """This ship's focus target (run_movement_phase: its own from
        fleet_focus_assignment, else the fleet's) if this ship can bring
        guns to bear on it within about two moves (its longest battery / lance
        range + twice its speed), else None (it plans against its nearest
        enemy as before)."""
        if self.difficulty == "easy":
            return None
        fid = getattr(self, "_focus_map", {}).get(ship.id) or getattr(self, "_focus", None)
        if not fid:
            return None
        f = self.gs.get_ship_by_id(fid)
        if f is None or f.is_destroyed or f.is_disengaged:
            return None
        reach = max((w.get("range_cm") or 0) for w in ship.weapons
                    if w.get("weapon_type") in ("battery", "lance")) if any(
            w.get("weapon_type") in ("battery", "lance") for w in ship.weapons) else 0
        if not reach or ship.distance_to(f) > reach + 2 * (ship.speed or 0):
            return None
        return f

    def _explosion_term(self, ship: Ship, x: float, y: float, target: Ship) -> float:
        """ai_hazards.explosion_position_vp in the planner's firepower units:
        keep clear of ships about to blow up; a ship likely to die gains by
        ending next to enemy ships rather than its own (owner)."""
        if self.difficulty == "easy" or getattr(self, "_enemy_plan", None) is None:
            return 0.0
        from .ai_hazards import explosion_position_vp, value_per_hit
        vp = explosion_position_vp(ship, x, y, self.gs, getattr(self, "_enemy_plan", {}),
                                   getattr(self, "_our_hits", {}))
        per_fp = 0.35 * max(1.0, value_per_hit(target, self.gs))
        return vp / per_fp

    def _screen_bonus(self, ship: Ship, x: float, y: float, h: float, target: Ship) -> float:
        """Escorts guard the commander's ship (CLAUDE.md To do 1): ending in base
        contact with it adds one massed turret (s.29: +1 per contributing ship in
        base contact, limit +3; not if this escort is crippled or has no turrets)
        while enemy torpedoes, torpedo bombers, bombers, assault boats or mines
        could reach it in their next ordnance phase (owner: with none of those about, ships don't
        try to mass turrets; enemy fighters don't count). Worth the turret's half chance to stop one of them (a
        torpedo's or bomber's expected hits on the flagship), in the planner's
        firepower units."""
        if self.difficulty == "easy" or ship.ship_type != "escort" or ship.is_crippled:
            return 0.0
        if (ship.turrets or 0) <= 0:
            return 0.0
        from .boarding import ships_in_base_contact
        from .ordnance import get_massed_turret_bonus, ATTACK_CRAFT_TYPES
        from .ai_hazards import value_per_hit, p_hit
        gs = self.gs
        flag = next((s for s in gs.player_ships(self.player) if s.is_flagship
                     and s.id != ship.id and not s.is_destroyed and not s.is_disengaged), None)
        if flag is None:
            return 0.0
        moved = Ship.from_dict({**ship.to_dict(), "x": x, "y": y, "heading": h})
        if not ships_in_base_contact(moved, flag):
            return 0.0
        others = [s for s in gs.get_ships() if s.id != ship.id]
        if get_massed_turret_bonus(flag, others) >= 3:
            return 0.0
        from .ordnance import attacks_ships
        threats = 0
        for o in gs.ordnance:
            if o["owner_player"] == self.player or o.get("cap_ship_id"):
                continue
            kind = o["ordnance_type"]
            # Owner: only massing against torpedoes, torpedo bombers (they fire
            # S2 salvos, s.21), bombers and assault boats (and mines, which turrets
            # also shoot, s.28); fighters don't attack ships
            ship_attacker = kind in ATTACK_CRAFT_TYPES and attacks_ships(kind)
            torps = kind.startswith("torpedo") or kind == "torpedo_bomber"
            if not (torps or "mine" in kind or ship_attacker):
                continue
            if math.hypot(o["x"] - flag.x, o["y"] - flag.y) <= (o.get("speed") or 20) * 2 + 10:
                threats += 1
        if not threats:
            return 0.0
        saved_hits = 0.5 * p_hit(flag.lowest_armor_value) * min(threats, 3)
        per_fp = 0.35 * max(1.0, value_per_hit(target, gs))
        # value_per_hit already counts the commander's ship double while it has re-rolls
        return saved_hits * max(1.0, value_per_hit(flag, gs)) / per_fp

    def _exposure_penalty(self, ship: Ship, x: float, y: float, h: float,
                          target: Ship) -> float:
        """Half the expected hits the enemy could focus on the ship at this end
        position (ai_hazards.position_exposure_hits), in the planner's
        firepower units (one point of in-arc firepower ~ 0.35 expected hits on
        the target). Half, as the enemy has other targets and our own fire
        thins it first."""
        if self.difficulty == "easy":
            return 0.0
        from .ai_hazards import position_exposure_hits, value_per_hit
        hits = position_exposure_hits(ship, x, y, h, self.gs)
        per_fp = 0.35 * max(1.0, value_per_hit(target, self.gs))
        return 0.5 * hits * max(1.0, value_per_hit(ship, self.gs)) / max(1.0, per_fp)

    def _simulate_final_pos(self, ship: Ship, turn_deg: float,
                            total_dist: float, turn_at: Optional[float] = None):
        """Return (x, y, heading) after moving total_dist with one turn of
        turn_deg: after `turn_at` cm of forward movement (To do 11 a turn
        points), by default right after the minimum distance before turning."""
        from .movement import MIN_TURN_DISTANCE
        min_td = MIN_TURN_DISTANCE.get(ship.ship_type, 0)
        r = math.radians
        if turn_at is not None and abs(turn_deg) >= 0.5:
            t = max(0.0, min(total_dist, turn_at))
            h0 = ship.heading
            mx = ship.x + t * math.cos(r(h0))
            my = ship.y + t * math.sin(r(h0))
            h1 = (h0 + turn_deg) % 360
            rem = total_dist - t
            return (mx + rem * math.cos(r(h1)), my + rem * math.sin(r(h1)), h1)

        if abs(turn_deg) < 0.5:
            h = ship.heading
            return (ship.x + total_dist * math.cos(r(h)),
                    ship.y + total_dist * math.sin(r(h)), h)

        if min_td > 0 and total_dist > min_td:
            h0 = ship.heading
            mx = ship.x + min_td * math.cos(r(h0))
            my = ship.y + min_td * math.sin(r(h0))
            h1 = (h0 + turn_deg) % 360
            rem = total_dist - min_td
            return (mx + rem * math.cos(r(h1)),
                    my + rem * math.sin(r(h1)), h1)

        h1 = (ship.heading + turn_deg) % 360
        return (ship.x + total_dist * math.cos(r(h1)),
                ship.y + total_dist * math.sin(r(h1)), h1)

    def _arc_score(self, ship: Ship, final_x: float, final_y: float,
                   final_heading: float, target: Ship, guns_only: bool = False,
                   in_range_only: bool = False) -> float:
        """Score total in-arc weapon strength from a hypothetical end position
        (loaded torpedoes too: they launch from there). guns_only: batteries
        and lances only (what Lock On re-rolls)."""
        dx = target.x - final_x
        dy = target.y - final_y
        dist = math.sqrt(dx * dx + dy * dy)
        bearing = math.degrees(math.atan2(dy, dx)) % 360
        relative = (bearing - final_heading + 360) % 360

        if relative <= 45 or relative > 315:
            arc = "front"
        elif relative <= 135:
            arc = "left"
        elif relative <= 225:
            arc = "rear"
        else:
            arc = "right"

        score = 0.0
        for weapon in ship.weapons:
            if guns_only and weapon.get("weapon_type") not in ("battery", "lance"):
                continue
            if weapon.get("weapon_type") == "torpedo":
                # Torpedoes launch from where the ship ends its move (s.15), within
                # the launcher's arc: worth their strength within one torpedo move,
                # half within two (the lead plan's reach), nothing unloaded. A
                # torpedo hits about as often as a firepower point does
                if not ship.ordnance_loaded_torps:
                    continue
                arcs = weapon.get("arcs", [])
                if arcs and arc not in arcs:
                    continue
                tspeed = weapon.get("torpedo_speed", TORPEDO_SPEED_DEFAULT) or TORPEDO_SPEED_DEFAULT
                strength = weapon.get("strength") or 0
                if dist <= tspeed + target.base_radius:
                    score += strength
                elif dist <= 2 * tspeed + target.base_radius:
                    score += 0.5 * strength
                continue
            if weapon.get("weapon_type") not in ("battery", "lance", "nova_cannon"):
                continue
            arcs = weapon.get("arcs", [])
            if arcs and arc not in arcs:
                continue
            strength = weapon.get("strength", 1)
            w_range  = weapon.get("range_cm", 0)
            if w_range == 0 or dist <= w_range:
                score += strength
            elif not in_range_only:
                score += strength * (w_range / dist) * 0.5  # closing bonus
        return score

    def _simulate_path(self, ship: Ship, turn_deg: float, total_dist: float,
                       turn_at: Optional[float] = None):
        """[(x, y), ...] of a move: start, turn point, end."""
        from .movement import MIN_TURN_DISTANCE
        min_td = MIN_TURN_DISTANCE.get(ship.ship_type, 0) if turn_at is None else turn_at
        pts = [(ship.x, ship.y)]
        if abs(turn_deg) >= 0.5 and 0 < min_td <= total_dist:
            r = math.radians(ship.heading)
            pts.append((ship.x + min_td * math.cos(r), ship.y + min_td * math.sin(r)))
        fx, fy, _ = self._simulate_final_pos(ship, turn_deg, total_dist, turn_at)
        pts.append((fx, fy))
        return pts

    def _position_penalty(self, final_x: float, final_y: float, ship: Ship = None,
                          path=None, order: str = "", enemy: Ship = None) -> float:
        """Penalty for a move, in the planner's units (in-arc firepower). With
        the ship, the hazards along its path in expected VP (ai_hazards:
        mines, torpedoes, attack craft, asteroid fields, warp rifts, dust
        clouds, blast markers), converted at what one point of in-arc
        firepower is worth against the enemy (about 0.35 expected hits)."""
        if ship is not None:
            from .ai_hazards import move_hazard_vp, value_per_hit
            risk = move_hazard_vp(ship, (final_x, final_y), path or [(ship.x, ship.y),
                                  (final_x, final_y)], self.gs, order)["vp"]
            if ship.is_flagship:
                risk += self._flagship_exposure_vp(ship, final_x, final_y)
            target = enemy or self._nearest_enemy(ship)
            per_fp = 0.35 * (value_per_hit(target, self.gs) if target else 20.0)
            return risk / max(1.0, per_fp)
        gs = self.gs
        penalty = 0.0

        # Terrain hazards
        for p in gs.get_phenomena():
            ptype = p.phenomenon_type
            dx = final_x - p.x
            dy = final_y - p.y
            buf = 5.0  # ship base radius buffer
            in_rect = abs(dx) < p.width / 2 + buf and abs(dy) < p.height / 2 + buf

            if "planet" in ptype and p.radius > 0:
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < p.radius + buf:
                    penalty += 5.0
            elif ptype == "warp_rift":
                if in_rect:
                    penalty += 120.0  # very likely to be lost
            elif ptype == "asteroid_field":
                if in_rect:
                    penalty += 30.0  # nav test + damage risk
            elif ptype == "gas_dust_cloud":
                if in_rect:
                    penalty += 8.0   # speed/gunnery penalty

        # Predicted torpedo positions
        for o_dict in gs.ordnance:
            marker = OrdnanceMarker.from_dict(o_dict)
            if marker.owner_player == self.player:
                continue
            if "torpedo" not in marker.ordnance_type and "mine" not in marker.ordnance_type:
                continue
            rad = math.radians(marker.heading)
            next_x = marker.x + marker.speed * math.cos(rad)
            next_y = marker.y + marker.speed * math.sin(rad)
            dist_to_torp = math.sqrt((final_x - next_x) ** 2 + (final_y - next_y) ** 2)
            if dist_to_torp < 6.0:
                penalty += marker.strength * 4.0

        return penalty

    def _flagship_exposure_vp(self, ship: Ship, x: float, y: float) -> float:
        """Owner guidance: keep the commander's ship out of harm. Expected VP of
        the enemy direct fire that could reach it at (x, y) next turn (weapons in
        range, arcs ignored: the enemy will turn), half-weighted since not all
        of it will be aimed there."""
        from .ai_hazards import value_per_hit
        hits = 0.0
        for e in self._live_enemies():
            d = math.hypot(e.x - x, e.y - y) - e.base_radius - ship.base_radius
            for w in e.weapons:
                if w.get("weapon_type") in ("battery", "lance") and d <= (w.get("range_cm") or 0) + e.speed:
                    hits += (w.get("strength") or 0) * 0.35
        hits = max(0.0, hits - ship.effective_shields)
        return hits * value_per_hit(ship, self.gs) * 0.5

    def _plan_flee(self, ship: Ship, order: str, aaf_bonus: int) -> List[MoveCommand]:
        """As fast as possible towards the nearest table edge (s.37; Demiurg
        Mercenaries): the candidate move that ends closest to it."""
        from .movement import MIN_TURN_DISTANCE
        gs = self.gs
        _, max_spd = get_effective_speed(ship, order, aaf_bonus)
        td = min(MIN_TURN_DISTANCE.get(ship.ship_type, 0), max_spd)
        ta = ship.turn_angle
        cands = [[MoveCommand("forward", max_spd)]]
        for turn in ("turn_left", "turn_right"):
            for ang in (ta, ta / 2):
                cmds = ([MoveCommand("forward", td)] if td else []) + [MoveCommand(turn, ang)]
                if max_spd - td > 0:
                    cmds.append(MoveCommand("forward", max_spd - td))
                cands.append(cmds)

        def edge_dist(x, y):
            return min(x, y, gs.table_width - x, gs.table_height - y)

        best, best_d = None, None
        for cmds in cands:
            r = validate_movement(ship, cmds, special_order=order, aaf_bonus=aaf_bonus,
                                  blast_markers=gs.get_blast_markers(),
                                  table_width=gs.table_width, table_height=gs.table_height)
            if not r.valid:
                continue
            d = edge_dist(r.final_x, r.final_y)
            if best_d is None or d < best_d:
                best, best_d = cmds, d
        return best

    def _forward_commands(self, ship: Ship, order: str, aaf_bonus: int,
                          fraction: float = 1.0) -> List[MoveCommand]:
        min_spd, max_spd = get_effective_speed(ship, order, aaf_bonus)
        dist = max(min_spd, int(max_spd * fraction))
        return [MoveCommand("forward", dist)]

    def _choose_special_order(self, ship: Ship) -> Optional[str]:
        """The ship's order, or None when trying it isn't worth the risk to
        the orders still to come (To do 10 c): the first failed command check
        ends every later check this turn (s.2), so an order with gain g and
        pass chance p is tried only if p x g beats (1 - p) x the expected gain
        of the later ships' orders (planned at the start of the phase,
        `_order_plan`)."""
        order = self._pick_special_order(ship)
        plan = getattr(self, "_order_plan", None)
        if order is None or not plan or ship.id not in plan.get("seq", []):
            return order
        _o, g, p = self._order_value(ship, order)
        seq = plan["seq"]
        later = sum(pp * gg for sid in seq[seq.index(ship.id) + 1:]
                    for _oo, gg, pp in [plan["orders"].get(sid, (None, 0.0, 0.0))])
        if g > 0 and p * g < (1 - p) * later:
            self.gs.add_log(f"[AI] {ship.name}: skips {order} (worth {p * g:.1f} VP, risks "
                            f"{(1 - p) * later:.1f} VP of later orders)")
            return None
        return order

    def _plan_orders(self, ships: List[Ship]) -> None:
        """At the start of the movement phase: each ship's order and its value
        (`_order_value`) in move order, for `_choose_special_order`."""
        orders = {}
        for s in ships:
            o = self._pick_special_order(s)
            if o:
                orders[s.id] = self._order_value(s, o)
        self._order_plan = {"seq": [s.id for s in ships], "orders": orders}

    def _order_value(self, ship: Ship, order: str):
        """(order, gain in VP, pass chance) (To do 10 b-c, f): Lock On's move
        gain at 0.35 hits a firepower point at the target's value a hit; Burn
        Retros the hazard it saves less half the firepower; Reload Ordnance
        next turn's launch (judgement: half a hit a torpedo / squadron at the
        nearest enemy's value a hit). Pass chance: the command check (Ld,
        Enemy Contacts +1, Under Fire -1, s.6)."""
        from .ai_hazards import p_sum_at_most, value_per_hit
        from .geometry import count_blast_markers_touching
        ld = ship.leadership
        if any(e.player != ship.player and e.special_order not in ("none", "")
               and not e.is_destroyed for e in self.gs.get_ships()):
            ld += 1
        if count_blast_markers_touching(ship, self.gs.get_blast_markers()) > 0:
            ld -= 1
        p = p_sum_at_most(2, max(0, min(10, ld)))
        target = self._focus_for(ship) or self._nearest_enemy(ship)
        vph = value_per_hit(target, self.gs) if target else 0.0
        if order == SpecialOrder.LOCK_ON.value:
            g = max(0.0, self._lock_on_gain(ship)) / max(p, 1e-9) * 0.35 * vph
        elif order == SpecialOrder.ALL_AHEAD_FULL.value:
            g = max(0.0, self._aaf_gain(ship)) / max(p, 1e-9) * 0.35 * vph
        elif order == SpecialOrder.BURN_RETROS.value:
            g = getattr(self, "_retros_saved", {}).get(ship.id, 0.0)
        elif order == SpecialOrder.RELOAD_ORDNANCE.value:
            g = self._reload_value(ship)
        else:
            g = 0.0
        return order, g, p

    def _pick_special_order(self, ship: Ship) -> Optional[str]:
        """Pick the most tactically useful special order for this ship."""
        # Burn Retros when it avoids more hazard than it costs (expected VP)
        if self._burn_retros_worth_it(ship):
            return SpecialOrder.BURN_RETROS.value

        # Lock On (To do 10 a): worth it when an enemy WILL be in arc after
        # the move, valued against the best move that may turn
        if self.difficulty == "easy":
            enemies = self._live_enemies()
            for enemy in enemies:
                for weapon in ship.weapons:
                    if weapon.get("weapon_type") not in ("battery", "lance"):
                        continue
                    if (check_weapon_in_arc(ship, weapon, enemy.x, enemy.y) and
                            check_weapon_in_range(ship, weapon, enemy.x, enemy.y)):
                        return SpecialOrder.LOCK_ON.value
        else:
            # Lock On / All Ahead Full against Reload Ordnance, all in expected VP
            # (To do 10 b): the gun gains at 0.35 hits a point at the target's
            # value a hit, the reload at next turn's launch (_reload_value)
            lock, aaf = self._lock_on_gain(ship), self._aaf_gain(ship)
            if max(lock, aaf) > 0:
                from .ai_hazards import value_per_hit
                target = self._focus_for(ship) or self._nearest_enemy(ship)
                vph = value_per_hit(target, self.gs) if target else 0.0
                gun_vp = max(lock, aaf) * 0.35 * vph
                if not (self._ordnance_spent(ship) and self._reload_value(ship) > gun_vp):
                    return (SpecialOrder.LOCK_ON.value if lock >= aaf
                            else SpecialOrder.ALL_AHEAD_FULL.value)

        # Reload if ordnance spent (it costs no firepower, so nothing better
        # to do means reload)
        if self._ordnance_spent(ship):
            return SpecialOrder.RELOAD_ORDNANCE.value

        return None

    @staticmethod
    def _ordnance_spent(ship: Ship) -> bool:
        has = {w.get("weapon_type") for w in ship.weapons}
        return (("torpedo" in has and not ship.ordnance_loaded_torps)
                or ("launch_bay" in has and not ship.ordnance_loaded_craft)
                or ("mine_launcher" in has and not ship.ordnance_loaded_mines)
                or "armageddon_spent" in ship.special_rules)

    def _reload_value(self, ship: Ship) -> float:
        """Expected VP of Reload Ordnance (To do 10 b): next turn's launch from
        each spent launcher. Bays: the strike planner's strike a turn on
        (`_strike_option(next_turn=True)`) or the CAP enemy strikes would call
        for, whichever is more; torpedoes: the salvo's expected hits on the
        nearest enemy it could reach (two torpedo moves and its move) on the
        Armour it shows, at its value a hit, discounted to next turn
        (`phase_weight(2)`); mines half a hit a launcher at the nearest enemy
        within 60cm (judgement); the Armageddon Gun its value from here."""
        from .ai_hazards import p_hit, value_per_hit, phase_weight
        enemies = self._live_enemies()
        if not enemies:
            return 0.0
        v = 0.0
        if not ship.ordnance_loaded_craft:
            bays = [w for w in ship.weapons if w.get("weapon_type") == "launch_bay"]
            if bays:
                from .ordnance import craft_type_allowed, bay_launch_capacity
                craft_types = [ct for w in bays for ct in w.get("craft_types", [])
                               if craft_type_allowed(ct, [w], self.gs)]
                count = min(bay_launch_capacity(ship, bays, None)[0],
                            fleet_craft_slots(self.gs, self.player))
                if craft_types and count > 0:
                    try:
                        nxt = self._strike_option(ship, craft_types, count, enemies,
                                                  next_turn=True)
                    except Exception:
                        nxt = None
                    bv = nxt[0] if nxt else 0.0
                    friends = [s for s in self.gs.get_ships() if s.player == self.player
                               and not s.is_destroyed and not s.is_disengaged]
                    cap = sorted((t[0] for t in self._anticipated_strike_slots(friends)),
                                 reverse=True)
                    v += max(bv, sum(cap[:count]))
        if not ship.ordnance_loaded_torps:
            for w in ship.weapons:
                if w.get("weapon_type") != "torpedo":
                    continue
                st = w.get("strength") or 0
                if isinstance(st, str):
                    from .combat import dice_value_average
                    st = dice_value_average(st)
                speed = w.get("torpedo_speed") or 30
                reach = [e for e in enemies
                         if ship.distance_to(e) <= 2 * speed + ship.speed + e.base_radius]
                if not reach or st <= 0:
                    continue
                e = min(reach, key=ship.distance_to)
                v += st * p_hit(e.armor_vs(ship.x, ship.y)) * value_per_hit(e, self.gs) \
                    * phase_weight(2)
        if not ship.ordnance_loaded_mines:
            near = [e for e in enemies if ship.distance_to(e) <= 60.0 + e.base_radius]
            if near:
                e = min(near, key=ship.distance_to)
                n = sum(w.get("strength", 1) or 1 for w in ship.weapons
                        if w.get("weapon_type") == "mine_launcher")
                v += 0.5 * n * value_per_hit(e, self.gs)
        if "armageddon_spent" in ship.special_rules:
            try:
                v += max(0.0, self._armageddon_value(ship))
            except Exception:
                pass
        return v

    LOCK_ON_GAIN = 0.5      # re-rolled misses: lances exactly +50%, batteries about that

    def _lock_on_gain(self, ship: Ship) -> float:
        """Lock On's value in move-score units (To do 10 a): the best straight
        move under Lock On (it may not turn; s.7), its guns that bear on the
        target counted LOCK_ON_GAIN more (missed dice re-rolled), minus the
        best move without the order (which may turn to bring guns to bear),
        at the command check's pass chance (a failed check moves normally, so
        it costs nothing here; what it blocks for later ships is To do 10 c).
        The target is the one the move will plan against (focus, else the
        nearest enemy)."""
        key = (ship.id, round(ship.x, 2), round(ship.y, 2), round(ship.heading, 1),
               ship.hits_remaining, self.gs.turn_number, len(self.gs.ordnance))
        cache = self.__dict__.setdefault("_lock_cache", {})
        if key not in cache:
            if len(cache) > 200:
                cache.clear()
            cache[key] = self._lock_on_gain_uncached(ship)
        return cache[key]

    def _aaf_gain(self, ship: Ship) -> float:
        """All Ahead Full's value in move-score units (To do 10 b): the best
        straight move at full speed plus the expected bonus (4D6, 14cm; Orks
        3D6 and their automatic pass), with everything it brings to bear
        halved (s.7: half firepower), minus the best move without an order,
        at the pass chance. Its uses (closing, escaping hazards and guns,
        reaching torpedo range) come out of the move score. Not yet: ramming
        and disengaging plans (8 h)."""
        from .ai_hazards import p_sum_at_most
        from .movement import aaf_bonus_dice
        if self.difficulty == "easy" or not ship.speed:
            return 0.0
        key = ("aaf", ship.id, round(ship.x, 2), round(ship.y, 2), round(ship.heading, 1),
               ship.hits_remaining, self.gs.turn_number, len(self.gs.ordnance))
        cache = self.__dict__.setdefault("_lock_cache", {})
        if key in cache:
            return cache[key]
        enemy = self._focus_for(ship) or self._nearest_enemy(ship)
        if enemy is None:
            return 0.0
        bonus = int(round(3.5 * aaf_bonus_dice(ship)))
        aaf_o = SpecialOrder.ALL_AHEAD_FULL.value
        prev = getattr(self, "_move_nearest", None)
        self._move_nearest = self._nearest_enemy(ship)
        try:
            free = max((self._move_score(ship, enemy, "", *c[:3])
                        for c in self._move_candidates(ship, enemy, "", 0)), default=None)
            fast = max((self._move_score(ship, enemy, aaf_o, *c[:3])
                        - 0.5 * self._arc_score(ship, *self._simulate_final_pos(ship, *c[:3]),
                                                enemy, in_range_only=True)
                        for c in self._move_candidates(ship, enemy, aaf_o, bonus)), default=None)
        finally:
            self._move_nearest = prev
        if free is None or fast is None:
            cache[key] = 0.0
            return 0.0
        ram = self._ram_candidate(ship)
        if ram is not None:
            from .ai_hazards import value_per_hit
            fast += ram[0] / (0.35 * max(1.0, value_per_hit(enemy, self.gs)))
        if "ere_we_go" in ship.special_rules:
            p = 1.0
        else:
            ld = ship.leadership + (1 if any(
                e.player != ship.player and e.special_order not in ("none", "")
                and not e.is_destroyed for e in self.gs.get_ships()) else 0)
            p = p_sum_at_most(2, min(10, ld))
        cache[key] = p * (fast - free)
        return cache[key]

    def _lock_on_gain_uncached(self, ship: Ship) -> float:
        from .ai_hazards import p_sum_at_most
        if not any(w.get("weapon_type") in ("battery", "lance") for w in ship.weapons):
            return 0.0
        enemy = self._focus_for(ship) or self._nearest_enemy(ship)
        if enemy is None:
            return 0.0
        prev = getattr(self, "_move_nearest", None)
        self._move_nearest = self._nearest_enemy(ship)
        try:
            free = max((self._move_score(ship, enemy, "", *c[:3])
                        for c in self._move_candidates(ship, enemy, "", 0)), default=None)
            lock = SpecialOrder.LOCK_ON.value
            locked = max((self._move_score(ship, enemy, lock, *c[:3])
                          + self.LOCK_ON_GAIN * self._arc_score(
                              ship, *self._simulate_final_pos(ship, *c[:3]), enemy,
                              guns_only=True, in_range_only=True)
                          for c in self._move_candidates(ship, enemy, lock, 0)), default=None)
        finally:
            self._move_nearest = prev
        if free is None or locked is None:
            return 0.0
        ld = ship.leadership
        if any(s.player != ship.player and s.special_order not in ("none", "")
               and not s.is_destroyed for s in self.gs.get_ships()):
            ld += 1                                   # Enemy Contacts (s.6)
        return p_sum_at_most(2, min(10, ld)) * (locked - free)

    def _safest_move_vp(self, ship: Ship, order: str) -> float:
        """The least hazard (ai_hazards.move_hazard_vp, along the path) of the
        moves this order allows: straight or one turn of the ship's turn angle,
        at its minimum, middle and maximum speed."""
        from .ai_hazards import move_hazard_vp
        from .movement import MIN_TURN_DISTANCE
        min_spd, max_spd = get_effective_speed(ship, order, 0)
        turns = [0.0]
        if get_max_turns(order, ship) > 0:
            turns += [-ship.turn_angle, ship.turn_angle]
        min_td = MIN_TURN_DISTANCE.get(ship.ship_type, 0)
        best = None
        for turn in turns:
            for dist in sorted({min_spd, (min_spd + max_spd) / 2.0, max_spd}):
                if abs(turn) > 0.5 and min_td > 0 and dist <= min_td:
                    continue
                fx, fy, _fh = self._simulate_final_pos(ship, turn, dist)
                path = self._simulate_path(ship, turn, dist)
                vp = move_hazard_vp(ship, (fx, fy), path, self.gs, order)["vp"]
                best = vp if best is None else min(best, vp)
        return best or 0.0

    def _teleport_given_up(self, ship: Ship) -> float:
        """To do 10 g: an order other than Lock On / Reload Ordnance gives up
        this turn's end-phase teleport raid (s.31). Its value: the best raid on
        an enemy within teleport range plus the ship's move (waves.
        raid_squadron_value), at half (judgement: the target's shields must be
        down and it must have no more hits left than this ship). Nothing when
        teleports or hit-and-run raids are off (owner), or the ship can't."""
        gs = self.gs
        if not (getattr(gs, "rule_teleport", False) and getattr(gs, "rule_hit_and_run", False)):
            return 0.0
        if "teleport_assault" not in ship.special_rules or ship.is_crippled:
            return 0.0
        from .hit_and_run import teleport_range
        from .waves import raid_squadron_value
        reach = teleport_range(ship) + (ship.effective_speed or 0)
        best = 0.0
        for e in self._live_enemies():
            if ship.distance_to(e) <= reach + e.base_radius and \
                    e.hits_remaining <= ship.hits_remaining:
                best = max(best, raid_squadron_value(e, gs, self.player, ship.special_rules))
        return 0.5 * best

    def _burn_retros_worth_it(self, ship: Ship) -> bool:
        """Burn Retros (s.7: half speed) when the safest normal move risks more
        expected VP from hazards (asteroids, warp rifts, mines, torpedoes, blast
        markers...) than the safest half-speed move, by more than the order
        costs: special orders halve the ship's firepower this turn, worth half
        what its guns can take off the best target (ai_rerolls.firepower_swing)."""
        if self.difficulty == "easy":
            return False
        from .ai_rerolls import firepower_swing
        normal = self._safest_move_vp(ship, "")
        retros = self._safest_move_vp(ship, SpecialOrder.BURN_RETROS.value)
        saved = normal - retros
        if saved <= 0:
            return False
        cost = 0.5 * firepower_swing(ship, self.gs) + self._teleport_given_up(ship)
        self.__dict__.setdefault("_retros_saved", {})[ship.id] = max(0.0, saved - cost)
        if saved > cost:
            self.gs.add_log(f"[AI] {ship.name}: Burn Retros avoids about {saved:.0f} VP of "
                            f"hazards (costs about {cost:.0f})")
            return True
        return False

    # ── Shooting phase ───────────────────────────────────────────────────────

    def run_shooting_phase(self):
        gs = self.gs
        tc = self.tc
        self._committed = {}                # expected hits planned per target this phase
        self._volley_fired = set()          # (ship id, weapon index) used in a squadron volley
        if self.difficulty != "easy":
            self._squadron_volleys()
        for ship in gs.player_ships(self.player):
            if ship.is_destroyed or ship.is_disengaged or ship.has_fired:
                continue
            if ship.has_boarded:                 # boarding: no firing this turn (s.32)
                continue
            self._fire_ship(ship)
            ship = gs.get_ship_by_id(ship.id)
            if not ship.has_fired:
                ship.has_fired = True
                gs.update_ship(ship)
            tc.mark_ship_fired(ship.id)

    def _fire_ship(self, ship: Ship):
        gs = self.gs
        enemies = self._live_enemies()
        if not enemies:
            return

        lock_on = ship.special_order == SpecialOrder.LOCK_ON.value
        blast_markers = gs.get_blast_markers()
        phenomena = gs.get_phenomena()
        all_ships = gs.get_ships()
        siege_done = self._fire_siege_cannons(ship, enemies, lock_on, blast_markers,
                                              phenomena, all_ships)

        # Batteries before lances (To do 11 d): the blast markers that hits on
        # shields leave shift later batteries right but never lances (s.11)
        order = sorted(enumerate(ship.weapons),
                       key=lambda iw: {"battery": 0, "lance": 2}.get(
                           iw[1].get("weapon_type", ""), 1))
        for w_idx, weapon in order:
            wtype = weapon.get("weapon_type", "")
            if wtype in ("torpedo", "launch_bay", "mine_launcher") or w_idx in siege_done:
                continue
            if weapon_disabled_by_crit(ship, weapon):
                continue                        # armament critical hit
            if (ship.id, w_idx) in getattr(self, "_volley_fired", set()):
                continue                        # already fired in its squadron's volley

            if wtype == "nova_cannon":
                self._fire_nova_cannon(ship, enemies, weapon)
                continue
            if wtype == "armageddon_gun":
                if self._armageddon_value(ship) > 0:
                    from .combat import resolve_armageddon_gun
                    for sid in resolve_armageddon_gun(ship, gs, self.dice).get("hits", {}):
                        t = gs.get_ship_by_id(sid)
                        if t is not None:
                            self._resolve_kill(t)
                    ship = gs.get_ship_by_id(ship.id)
                continue

            # Shoot an incoming mine / salvo / wave instead, when that's worth more
            ordshot = self._ordnance_shot(ship, weapon, w_idx) if self.difficulty != "easy" else None
            if ordshot:
                from .combat import fire_at_ordnance
                m = ordshot["marker"]
                res = fire_at_ordnance(ship, weapon, m.id, gs, self.dice, ordshot["avail"])
                gs.add_log(f"[AI] {ship.name} → {m.ordnance_type}: {weapon['name']} "
                           f"{res['dice']} dice, {'destroyed' if res['hits'] else 'missed'}")
                continue

            hulk = self._hulk_shot(ship, weapon) if self.difficulty != "easy" else None
            if hulk is not None:
                enemies = [hulk]                 # worth more than any ship shot (below)
            else:
                enemies = self._live_enemies()  # earlier weapons may have killed some
            target = self._pick_target(ship, weapon, enemies)
            if not target:
                continue
            self._offer_brace(ship, target, [weapon])

            if wtype in ("battery", "lance"):
                # Firepower fixed when fired: random values rolled, Heavy Gunz by range
                pool, _mode, _err = weapon_fire_pool(
                    ship, weapon, w_idx, ship.distance_to(target), self.dice, gs)
                if weapon.get("strength_dice"):
                    gs.add_log(f"[AI] {ship.name} {weapon['name']}: rolled "
                               f"{weapon['strength_dice']} = {pool}")
                weapon = shot_weapon(weapon, pool)

            # A ship in a squadron can't be picked out: fire at the squadron (s.8)
            group = squadron_group(target, gs.get_ships())
            if len(group) > 1 and wtype in ("battery", "lance"):
                crit_on = weapon.get("crit_on", 6)
                sr, applied = fire_at_squadron(
                    ship, weapon, target, group, self.dice,
                    lambda m, n, _c=crit_on, _a=ship.id: self._apply_hits_to(m, n, _c, _a),
                    lock_on, blast_markers, phenomena, all_ships)
                gs.add_log(f"[AI] {ship.name} → squadron {target.squadron_id}: "
                           f"{weapon['name']} {sr.hits} hit(s)")
                continue

            if wtype == "battery":
                sr = resolve_batteries(ship, target, weapon, self.dice,
                                       blast_markers, lock_on=lock_on,
                                       phenomena=phenomena, all_ships=all_ships)
                if weapon.get("kustom_kannon"):
                    from .combat import spend_kustom_kannon
                    spend_kustom_kannon(ship, weapon, gs)
            elif wtype == "lance":
                sr = resolve_lances(ship, target, weapon, self.dice,
                                    lock_on=lock_on)
            else:
                continue
            gs.add_log(f"[AI] {ship.name} → {target.name}: "
                       f"{weapon['name']} {sr.hits} hit(s)")
            if sr.hits > 0:
                self._apply_hits_to(target, sr.hits, weapon.get("crit_on", 6), ship.id)

    def _squadron_volleys(self):
        """Shooting by Squadrons for the AI (s.8, combat.plan_squadron_volley):
        each AI squadron of 2+ ships combines its batteries into one volley
        when that rolls at least as many dice as firing them separately. The
        target is the one adding the most expected VP (ai_hazards.added_vp,
        counting hits already planned this phase), among enemies that are the
        nearest valid target for every contributing battery (so no target
        priority test is needed). Lances, torpedoes and the rest still fire
        ship by ship afterwards."""
        from .combat import plan_squadron_volley, resolve_squadron_volley
        from .ai_hazards import added_vp, p_hit
        gs = self.gs
        squads = {}
        for s in gs.player_ships(self.player):
            if (s.squadron_id and not s.is_destroyed and not s.is_disengaged
                    and not s.has_fired and not s.disengage_failed_this_turn):
                squads.setdefault(s.squadron_id, []).append(s)
        bms, phen, all_ships = gs.get_blast_markers(), gs.get_phenomena(), gs.get_ships()
        for members in squads.values():
            if len(members) < 2:
                continue
            batteries = [(m, i, w) for m in members for i, w in enumerate(m.weapons)
                         if w.get("weapon_type") == "battery" and not w.get("strength_dice")
                         and not weapon_disabled_by_crit(m, w)]
            if len(batteries) < 2:
                continue
            enemies = self._live_enemies()
            best = None
            for target in enemies:
                contrib = []
                for m, i, w in batteries:
                    valid = self._valid_targets(m, w, enemies)
                    if valid and min(valid, key=lambda e: m.distance_to(e)).id == target.id:
                        contrib.append((m, i, w))
                if len(contrib) < 2:
                    continue
                group = squadron_group(target, all_ships)
                pairs = [(m, w) for m, _i, w in contrib]
                from .combat import best_aspect_choice
                aspects = (best_aspect_choice(pairs, group, bms, phen, all_ships)
                           if len(group) > 1 else None)
                plan = plan_squadron_volley(pairs, group, bms, phen, all_ships,
                                            aspect_choice=aspects)
                combined = sum(a["dice"] for a in plan["attacks"])
                separate = sum(sum(a["dice"] for a in plan_squadron_volley(
                    [pr], group, bms, phen, all_ships)["attacks"]) for pr in pairs)
                if combined <= 0 or combined < separate:
                    continue
                hits = sum(a["dice"] * p_hit(min(a["armors"].values())) for a in plan["attacks"])
                value = added_vp(target, gs, self._committed.get(target.id, 0.0), hits)
                if best is None or value > best[0]:
                    best = (value, target, group, contrib, plan, hits)
            if best is None:
                continue
            value, target, group, contrib, plan, hits = best
            lead = contrib[0][0]
            self._offer_brace(lead, target, expected=hits)
            lock_on = all(m.special_order == SpecialOrder.LOCK_ON.value for m, _i, _w in contrib)
            applied = resolve_squadron_volley(
                plan, group, self.dice,
                lambda t, n, _a=lead.id: self._apply_hits_to(t, n, 6, _a),
                lock_on=lock_on, game_state=gs)
            self._committed[target.id] = self._committed.get(target.id, 0.0) + hits
            for m, i, _w in contrib:
                self._volley_fired.add((m.id, i))
            gs.add_log(f"[AI] squadron {lead.squadron_id} combined batteries at "
                       f"{target.name}: {sum(a['dice'] for a in plan['attacks'])} dice, "
                       f"{sum(applied.values())} hit(s)")

    def _aaf_bonus(self, ship) -> int:
        """All Ahead Full speed bonus: a squadron rolls once this turn, members
        taking their own number of the highest dice (s.7)."""
        from .movement import resolve_aaf_speed, squadron_aaf_bonuses
        if not ship.squadron_id:
            return resolve_aaf_speed(ship, self.dice)
        cache = getattr(self, "_aaf_cache", {})
        key = (self.gs.turn_number, ship.squadron_id)
        if key not in cache:
            members = [s for s in self.gs.player_ships(self.player)
                       if s.squadron_id == ship.squadron_id
                       and not s.is_destroyed and not s.is_disengaged]
            cache[key] = squadron_aaf_bonuses(members, self.dice)
            self._aaf_cache = cache
        return cache[key].get(ship.id, resolve_aaf_speed(ship, self.dice))

    def _offer_brace(self, ship, target, weapons=None, expected=None):
        """The target decides on Brace for Impact before this ship's attack on
        it is rolled (s.7). It decides separately against each of the
        attacker's weapons (it may brace against the lances after not bracing
        against the gunnery), so it is asked before each attack: `weapons` are
        the weapons about to fire at it (None: every battery / lance bearing).
        Only one try per attacker per turn: after a failed test, or once
        braced, `_brace_before_attack` doesn't ask again. brace_fn is set by
        the game (asks a human player; the AI decides for its own ships);
        without it nothing is asked. expected: the attack's expected hits when
        known (a squadron volley)."""
        fn = getattr(self, "brace_fn", None)
        if fn is None:
            return
        group = squadron_group(target, self.gs.get_ships())
        if expected is not None:
            fn(ship, target, expected, group)
            return
        from .combat import expected_hits
        if weapons is None:
            weapons = [w for w in ship.weapons
                       if w.get("weapon_type") in ("battery", "lance")
                       and check_weapon_in_arc(ship, w, target.x, target.y)
                       and check_weapon_in_range(ship, w, target.x, target.y)]
        expected = sum(expected_hits(ship, w, target, self.gs) for w in weapons
                       if w.get("weapon_type") in ("battery", "lance"))
        fn(ship, target, expected, group)

    def _fire_siege_cannons(self, ship, enemies, lock_on, blast_markers, phenomena,
                            all_ships) -> set:
        """Siege Cannons: fire bombardment cannons and the macrobatteries that
        can reach the same (non-squadron) target together. Returns the weapon
        indices used."""
        from .chapter_tactics import siege_ship
        from .combat import resolve_siege_cannons
        if not siege_ship(ship):
            return set()
        bcs = [(i, w) for i, w in enumerate(ship.weapons) if w.get("hits_on")
               and not weapon_disabled_by_crit(ship, w)]
        if not bcs:
            return set()
        target = self._pick_target(ship, bcs[0][1], enemies)
        if not target or len(squadron_group(target, self.gs.get_ships())) > 1:
            return set()
        group = [(i, w) for i, w in enumerate(ship.weapons)
                 if w.get("weapon_type") == "battery"
                 and not weapon_disabled_by_crit(ship, w)
                 and self._pick_target(ship, w, [target]) is not None]
        macro = [(i, w) for i, w in group if not w.get("hits_on")]
        bc_ok = [(i, w) for i, w in group if w.get("hits_on")]
        if not macro or not bc_ok:
            return set()
        self._offer_brace(ship, target, [w for _i, w in macro + bc_ok])
        shots = {}
        for i, w in macro + bc_ok:
            pool, _m, _e = weapon_fire_pool(ship, w, i, ship.distance_to(target), self.dice)
            shots[i] = shot_weapon(w, pool)
        m_res, b_res = resolve_siege_cannons(
            ship, target, [shots[i] for i, _ in macro], [shots[i] for i, _ in bc_ok],
            self.dice, blast_markers, lock_on, phenomena, all_ships)
        self.gs.add_log(f"[AI] {ship.name} → {target.name}: Siege Cannons "
                        f"{m_res.hits}+{b_res.hits} hit(s)")
        if m_res.hits:
            self._apply_hits_to(target, m_res.hits, 6, ship.id)
        if b_res.hits:
            self._apply_hits_to(target, b_res.hits, 4, ship.id)
        return {i for i, _ in macro + bc_ok}

    def _apply_hits_to(self, target: Ship, hits: int, crit_on: int = 6,
                       attacker_key: str = ""):
        """Apply hits from AI fire, then resolve the ship's destruction if it died.
        Returns (unused hits, destroyed) for squadron hit allocation."""
        t = self.gs.get_ship_by_id(target.id)
        hulk = t is not None and t.status in ("drifting_hulk", "burning_hulk")
        if not t or (t.is_destroyed and not hulk):
            return hits, True             # hulks take hits: they re-roll catastrophic damage
        braced = t.special_order == SpecialOrder.BRACE_FOR_IMPACT.value
        src = self.gs.get_ship_by_id(attacker_key) if attacker_key else None
        dmg = apply_damage(t, hits, self.dice, self.gs, target_braced=braced,
                           crit_on=crit_on, attacker_key=attacker_key,
                           origin=(src.x, src.y) if src else None)
        self._log_damage(t, dmg)
        self._resolve_kill(t)
        return dmg["unused_hits"], dmg["destroyed"]

    def _resolve_kill(self, target: Ship):
        """A ship the AI reduced to 0 rolls catastrophic damage (or becomes a
        blast marker if it is an escort). Nothing else does this after AI fire."""
        t = self.gs.get_ship_by_id(target.id)
        if t and t.hits_remaining <= 0 and t.status == "active":
            from .combat import resolve_catastrophic
            resolve_catastrophic(t, self.dice, self.gs)

    NOVA_FRIEND_CLEARANCE = 12.0    # cm from the aim point (judgement: scatter + template)

    def _armageddon_value(self, ship: Ship) -> float:
        """Expected VP of firing the Armageddon Gun now: along its track, 3.5
        hits on ships under the centre hole and 1 on those the template
        crosses, past shields (`added_vp`), enemies for us and friends against."""
        from .combat import armageddon_ready, armageddon_path
        from .ai_hazards import added_vp
        from .geometry import (NOVA_CANNON_TEMPLATE_RADIUS_CM as TR,
                               NOVA_CANNON_CENTER_HOLE_RADIUS_CM as CR)
        if armageddon_ready(ship):
            return 0.0
        x0, y0, x1, y1, _b = armageddon_path(ship, self.gs)
        dx, dy = x1 - x0, y1 - y0
        L = dx * dx + dy * dy
        v = 0.0
        for s in self.gs.get_ships():
            if s.id == ship.id or s.is_destroyed or s.is_disengaged:
                continue
            t = 0.0 if L == 0 else max(0.0, min(1.0, ((s.x - x0) * dx + (s.y - y0) * dy) / L))
            d = math.hypot(s.x - (x0 + t * dx), s.y - (y0 + t * dy))
            h = 3.5 if d <= s.base_radius + CR else (1.0 if d <= s.base_radius + TR else 0.0)
            if h:
                g = added_vp(s, self.gs, 0.0, h)
                v += g if s.player != self.player else -g
        return v

    def _fire_nova_cannon(self, ship: Ship, enemies: List[Ship], weapon: Dict = None):
        """The Nova Cannon (s.14) at the enemy in arc and 30-150cm where its
        expected hits (`ai_hazards.nova_expected_hits`: direct hit or scatter by
        range, shields still stop them) add the most VP given this phase's
        other fire (`added_vp`, To do 9); never at a target with one of our
        ships within `NOVA_FRIEND_CLEARANCE` of it (a scatter could land on it)."""
        from .combat import resolve_nova_cannon
        from .ai_hazards import nova_expected_hits, added_vp
        gs = self.gs
        if not enemies:
            return
        friends = [f for f in gs.player_ships(self.player)
                   if f.id != ship.id and not f.is_destroyed and not f.is_disengaged]
        committed = getattr(self, "_committed", {}) or {}
        best = None
        for e in enemies:
            dist = math.hypot(e.x - ship.x, e.y - ship.y)
            if dist < 30 or dist > 150:
                continue
            if weapon is not None and not check_weapon_in_arc(ship, weapon, e.x, e.y):
                continue
            if any(math.hypot(f.x - e.x, f.y - e.y) <= self.NOVA_FRIEND_CLEARANCE
                   for f in friends):
                continue
            v = added_vp(e, gs, committed.get(e.id, 0.0), nova_expected_hits(dist, e))
            if best is None or v > best[0]:
                best = (v, e)
        if best is None or best[0] <= 0:
            return
        target = best[1]
        self._offer_brace(ship, target)          # before the scatter roll (s.7)
        nc = resolve_nova_cannon(ship, target.x, target.y, self.dice, gs)
        if "error" in nc:
            return
        gs.add_log(f"[AI] {ship.name} nova cannon at ({target.x:.0f},{target.y:.0f})")
        for sid, hd in nc.get("ship_hits", {}).items():
            t = gs.get_ship_by_id(sid)
            if t:
                dmg = apply_damage(t, hd["hits"], self.dice, gs,
                                   target_braced=t.special_order
                                   == SpecialOrder.BRACE_FOR_IMPACT.value,
                                   attacker_key=ship.id,
                                   origin=(nc["template_x"], nc["template_y"]))
                self._log_damage(t, dmg)
                self._resolve_kill(t)

    def _ordnance_shot(self, ship: Ship, weapon: Dict, w_idx: int) -> Optional[Dict]:
        """Is shooting enemy ordnance with this weapon worth more than its best
        shot at a ship (owner guidance: shoot incoming mines and the like when
        fighters won't get there first)? The nearest enemy marker in arc, range
        and line of fire (no target priority test needed, s.30); value = P(at
        least one 6) x the VP it threatens, a third of that when a friendly
        fighter squadron can reach it in our ordnance phase."""
        from .ai_hazards import marker_threat_vp, shot_vp
        from .combat import ordnance_fire_dice
        gs = self.gs
        if weapon.get("weapon_type") not in ("battery", "lance"):
            return None
        enemy_ord = [OrdnanceMarker.from_dict(o) for o in gs.ordnance
                     if o["owner_player"] != self.player and not o.get("cap_ship_id")]
        in_reach = [m for m in enemy_ord
                    if check_weapon_in_arc(ship, weapon, m.x, m.y)
                    and check_weapon_in_range(ship, weapon, m.x, m.y)]
        if not in_reach:
            return None
        m = min(in_reach, key=lambda o: math.hypot(o.x - ship.x, o.y - ship.y))
        threat = marker_threat_vp(m, gs, self.player)
        if threat <= 0:
            return None
        from .ordnance import craft_roles
        covered = any("fighter" in craft_roles(o["ordnance_type"]) and o["owner_player"] == self.player
                      and not o.get("cap_ship_id")
                      and math.hypot(o["x"] - m.x, o["y"] - m.y) <= (o.get("speed") or 0)
                      for o in gs.ordnance)
        avail = weapon.get("strength", 0)
        if ship.is_crippled:
            avail = ship.crippled_value(avail)
        n = ordnance_fire_dice(ship, weapon, m.x, m.y, gs, avail)
        need = weapon.get("hits_on") or 6
        p = 1.0 - (1.0 - max(0, 7 - need) / 6.0) ** n
        value = p * threat * (0.33 if covered else 1.0)
        ships = self._valid_targets(ship, weapon, self._live_enemies())
        best_ship = max((shot_vp(ship, weapon, e, gs, self._committed.get(e.id, 0.0))
                         for e in ships), default=0.0) if hasattr(self, "_committed") else 0.0
        if value <= best_ship:
            return None
        return {"marker": m, "avail": avail, "value": value}

    def _hulk_shot(self, ship: Ship, weapon: Dict) -> Optional[Ship]:
        """An enemy hulk worth shooting with this weapon instead of a ship:
        P(at least one hit) x ai_hazards.hulk_shot_vp (its re-rolled
        Catastrophic Damage exploding among enemy ships, never near ours)
        beats the best ship shot. Only when the hulk is the closest target in
        arc, so no target priority test is needed (s.34 Hulks in combat)."""
        from .ai_hazards import hulk_shot_vp, shot_vp
        from .combat import expected_hits
        if weapon.get("weapon_type") not in ("battery", "lance"):
            return None
        gs = self.gs
        hulks = [s for s in gs.get_ships() if s.player != self.player
                 and s.status in ("drifting_hulk", "burning_hulk")]
        hulks = self._valid_targets(ship, weapon, hulks)
        if not hulks:
            return None
        h = min(hulks, key=lambda x: ship.distance_to(x))
        ships = self._valid_targets(ship, weapon, self._live_enemies())
        if any(ship.distance_to(e) < ship.distance_to(h) for e in ships):
            return None
        value = hulk_shot_vp(h, gs, self.player)
        if value <= 0:
            return None
        p_any = 1.0 - math.exp(-max(0.0, expected_hits(ship, weapon, h, self.gs)))
        best_ship = max((shot_vp(ship, weapon, e, gs, self._committed.get(e.id, 0.0))
                         for e in ships), default=0.0) if hasattr(self, "_committed") else 0.0
        if p_any * value <= best_ship:
            return None
        gs.add_log(f"[AI] {ship.name} {weapon['name']}: shooting the hulk of {h.name} "
                   f"(about {p_any * value:.0f} VP if it blows up among enemies)")
        return h

    def _valid_targets(self, ship: Ship, weapon: Dict, enemies: List[Ship]) -> List[Ship]:
        valid = []
        for e in enemies:
            if not check_weapon_in_arc(ship, weapon, e.x, e.y):
                continue
            if not check_weapon_in_range(ship, weapon, e.x, e.y):
                continue
            los = check_los_clear(ship, e, self.gs.get_phenomena(),
                                  self.gs.get_blast_markers(), self.gs.ships)
            if not los.get("clear", True):
                continue
            if shadow_engines_hidden(ship, e, enemies):
                continue
            valid.append(e)
        return valid

    def _pick_target(self, ship: Ship, weapon: Dict,
                     enemies: List[Ship]) -> Optional[Ship]:
        valid = []
        for e in enemies:
            if not check_weapon_in_arc(ship, weapon, e.x, e.y):
                continue
            if not check_weapon_in_range(ship, weapon, e.x, e.y):
                continue
            los = check_los_clear(ship, e,
                                  self.gs.get_phenomena(),
                                  self.gs.get_blast_markers(),
                                  self.gs.ships)
            if not los.get("clear", True):
                continue
            # Shadow Engines: escorts beyond 30cm that aren't the closest target
            if shadow_engines_hidden(ship, e, enemies):
                continue
            valid.append(e)
        if not valid:
            return None

        if self.difficulty == "easy":
            return self._enforce_target_priority(ship, weapon, random.choice(valid), valid)
        # normal / hard / expert: the most expected VP for this weapon, counting the
        # fire already committed to each target this phase (owner guidance:
        # finish and cripple ships, no overkill, don't spread too thin)
        from .ai_hazards import shot_vp
        committed = getattr(self, "_committed", {})
        best = max(valid, key=lambda e: shot_vp(ship, weapon, e, self.gs,
                                                committed.get(e.id, 0.0)))
        if shot_vp(ship, weapon, best, self.gs, committed.get(best.id, 0.0)) <= 0:
            return min(valid, key=lambda s: s.hits_remaining / max(1, s.hits_max))
        best = self._enforce_target_priority(ship, weapon, best, valid)
        from .combat import expected_hits
        committed[best.id] = committed.get(best.id, 0.0) + expected_hits(ship, weapon, best, self.gs)
        self._committed = committed
        return best

    def _enforce_target_priority(self, ship: Ship, weapon: Dict, wanted: Ship,
                                 valid: List[Ship]) -> Ship:
        """Target priority (s.13): a weapon fires at the nearest enemy in its arc
        unless the ship passes a target priority test (once per ship per turn,
        the result stands). A closer hulk may be fired on without a test (s.34).
        Same rule as the player's Fire dialog (`_check_target_priority`)."""
        gs = self.gs
        visible = sorted((e for e in self._live_enemies() if e.status == "active"
                          and check_los_clear(ship, e, gs.get_phenomena(),
                                              gs.get_blast_markers(), gs.ships).get("clear", True)),
                         key=ship.distance_to)
        cv = visible[0] if visible else None
        if cv is None or wanted.id == cv.id or not any(v.id == cv.id for v in valid):
            return wanted                     # the closest isn't a target for this weapon
        if (wanted.status in ("drifting_hulk", "burning_hulk")
                and ship.distance_to(wanted) < ship.distance_to(cv)):
            return wanted
        att = gs.get_ship_by_id(ship.id) or ship
        if att.target_priority_turn != gs.turn_number:
            check = do_command_check(att, "target_priority", self.dice, gs=gs)
            if not check["passed"]:
                from .ai_rerolls import should_reroll
                left = self.tc.get_fleet_rerolls(att.player, att)
                if left and should_reroll(att, "target priority", gs, left) \
                        and self.tc.use_fleet_reroll(att.player, att):
                    check = do_command_check(att, "target_priority", self.dice, gs=gs)
            att = gs.get_ship_by_id(ship.id) or att
            att.target_priority_turn = gs.turn_number
            att.target_priority_passed = check["passed"]
            gs.update_ship(att)
            gs.add_log(f"[AI] {att.name}: target priority "
                       f"{'passed' if check['passed'] else 'FAILED'} "
                       f"(rolled {check['roll']} vs Ld {check['needed']})")
        return wanted if att.target_priority_passed else next(v for v in valid if v.id == cv.id)

    def _log_damage(self, target: Ship, dmg: Dict):
        gs = self.gs
        if dmg.get("crits"):
            for c in dmg["crits"]:
                gs.add_log(f"[AI]   CRIT: {c}")
        if dmg.get("crippled"):
            gs.add_log(f"[AI]   {target.name} CRIPPLED")
        if dmg.get("destroyed"):
            gs.add_log(f"[AI]   {target.name} DESTROYED")

    # ── Ordnance phase ───────────────────────────────────────────────────────

    def run_ordnance_phase(self):
        gs = self.gs

        # Steer this player's guided missiles. Everything else moves when the
        # ordnance phase is resolved (OrdnanceMovementMixin).
        for o_dict in list(gs.ordnance):
            marker = OrdnanceMarker.from_dict(o_dict)
            if marker.owner_player != self.player or marker.moved_this_phase:
                continue
            if marker.can_turn:
                target = next((s for s in self._live_enemies()
                               if s.id == marker.torp_target_id), None) \
                    or self._nearest_enemy_to(marker.x, marker.y)
                self._steer_guided_missile(marker, target)

        # Torpedo bombers launched on an earlier turn fire their salvos (s.21)
        self._fire_torpedo_bombers()

        # Launch new ordnance. Targets are chosen by expected VP from the enemy's
        # actual state (after this turn's shooting) plus what this phase's
        # launches are planned to do (_ord_committed)
        self._ord_committed = {}
        # Planned arrivals this phase: {target id: {"torps": [(phase, strength, xy)],
        # "craft": [(phase, fighters, bombers, f_save, b_save)]}} for the turret
        # split (owner: co-ordinate bombers and missiles, s.28)
        self._ord_arrivals = {}
        enemies = self._live_enemies()
        self._fleet_defence = (self._plan_fleet_defence(enemies)
                               if enemies and self.difficulty != "easy" else None)
        for ship in gs.player_ships(self.player):
            if ship.is_destroyed or ship.is_disengaged or ship.has_boarded:
                continue                          # boarding: no launches (s.32)
            self._launch_ship_ordnance(ship)
        self._fleet_defence = None

    def _fire_torpedo_bombers(self):
        """At the start of the ordnance phase, each torpedo bomber wave (or
        lone squadron) fires its salvo (2 a squadron, s.21) at the enemy ship
        within this phase's salvo move where it does most expected VP, aimed
        straight at it (ships don't move in the ordnance phase); it holds when
        none is in reach (the salvo is removed at the end of the phase)."""
        from .ordnance import torpedo_bomber_groups, fire_torpedo_bombers
        from .ai_hazards import torpedo_bomber_target
        for group in torpedo_bomber_groups(self.gs, self.player):
            lead = group[0]
            best = torpedo_bomber_target(self.gs, group, self.player)
            if best is None or best[0] <= 0:
                continue
            e = best[1]
            heading = math.degrees(math.atan2(e.y - lead.y, e.x - lead.x))
            salvo = fire_torpedo_bombers(self.gs, [m.id for m in group], heading)
            if salvo is not None:
                for o in self.gs.ordnance:
                    if o["id"] == salvo.id:
                        o["torp_target_id"] = e.id
                self.gs.add_log(f"[AI] torpedo bombers fire at {e.name}")

    def _steer_guided_missile(self, marker: OrdnanceMarker,
                              target: Optional[Ship]) -> None:
        gs = self.gs
        if target is not None:
            from .ai_hazards import salvo_approach
            plan = salvo_approach(marker, gs, target=target, our_phase=True)
            if plan is not None:
                # Owner: come in on the weakest facing it can reach
                marker.heading = plan["heading"] % 360
                target = None
        if target is not None:
            # Owner: turning salvos lead too (less than straight ones, since they
            # steer again): out of reach this phase, head for the middle of where
            # the target can end its next move (ai_hazards.enemy_move_samples)
            tx, ty = target.x, target.y
            if math.hypot(tx - marker.x, ty - marker.y) > (marker.speed or 0) + target.base_radius:
                from .ai_hazards import enemy_move_samples
                paths = enemy_move_samples(target)[0]
                wsum = sum(p.weight for p in paths) or 1.0
                tx = sum(p.weight * p[-1][0] for p in paths) / wsum
                ty = sum(p.weight * p[-1][1] for p in paths) / wsum
            dx = tx - marker.x
            dy = ty - marker.y
            desired = math.degrees(math.atan2(dy, dx)) % 360
            diff = signed_angle_diff(desired, marker.heading)
            max_t = getattr(marker, "turn_angle", 45)
            marker.heading = (marker.heading + max(-max_t, min(max_t, diff))) % 360

        rad = math.radians(marker.heading)
        marker.x += marker.speed * math.cos(rad)
        marker.y += marker.speed * math.sin(rad)
        marker.moved_this_phase = True

        for i, o in enumerate(gs.ordnance):
            if o["id"] == marker.id:
                gs.ordnance[i] = marker.to_dict()
                break

    def _launch_ship_ordnance(self, ship: Ship):
        gs = self.gs
        enemies = self._live_enemies()
        if not enemies:
            return

        bays_held = False
        for weapon in ship.weapons:
            wtype = weapon.get("weapon_type", "")

            if wtype == "torpedo" and ship.ordnance_loaded_torps:
                # Pick target whose predicted next position is best covered
                target = self._best_torp_target(ship, weapon, enemies)
                if target:
                    # Short burn torpedoes (if carried) for targets beyond a
                    # standard salvo's reach. Barrage bombs are for planetary
                    # assaults (assault points), which aren't modelled yet
                    kind, aim_weapon = "", weapon
                    once = unused_once_torpedoes(ship)
                    if (once and weapon.get("torpedo_type") != "guided"
                            and target.ship_type != "escort"):
                        # Save the one-per-game salvo for a capital ship
                        kind = next(k for k in ("vortex", "melta", "seeking") if k in once)
                    elif ("guided" in ship_torpedo_types(ship)
                          and weapon.get("torpedo_type") != "guided"):
                        # Owner: the enemy can only take control after a failed
                        # Leadership test (and a re-roll), so guide them freely
                        kind = "guided"
                    elif ("short_burn" in ship_torpedo_types(ship)
                            and weapon.get("torpedo_type") != "guided"
                            and ship.distance_to(target) > weapon.get(
                                "torpedo_speed", TORPEDO_SPEED_DEFAULT)):
                        kind = "short_burn"
                        aim_weapon = {**weapon, "torpedo_speed": SHORT_BURN_SPEED}
                    aim = self._torpedo_aim_heading(ship, aim_weapon, target)
                    m = launch_torpedoes(ship, weapon, gs, heading=aim, dice=self.dice,
                                         kind=kind)
                    if m is not None:
                        for o in gs.ordnance:     # its in-flight turns follow the plan
                            if o["id"] == m.id:
                                o["torp_target_id"] = target.id
                        tsp = aim_weapon.get("torpedo_speed", TORPEDO_SPEED_DEFAULT) or 30
                        tph = 0 if ship.distance_to(target) <= tsp + target.base_radius else 1
                        self.__dict__.setdefault("_ord_arrivals", {}).setdefault(target.id, {}).setdefault(
                            "torps", []).append((tph, m.strength, (ship.x, ship.y)))
                    ship = gs.get_ship_by_id(ship.id)

            elif wtype == "mine_launcher" and ship.ordnance_loaded_mines:
                # Mines (s.17) home 10cm on the nearest enemy vessel in every
                # ordnance phase and stay active until destroyed: lay them when
                # an enemy is within three turns' reach (20cm a turn), where
                # they can still find it
                from .ordnance import lay_mines
                if any(ship.distance_to(e) <= 60.0 + e.base_radius for e in enemies):
                    lay_mines(ship, weapon, gs)
                    ship = gs.get_ship_by_id(ship.id)

            elif wtype == "launch_bay" and ship.ordnance_loaded_craft and not bays_held:
                # All of the ship's bays launch together: launching any craft
                # means reloading before launching again (s.15)
                bays = [w for w in ship.weapons if w.get("weapon_type") == "launch_bay"]
                from .ordnance import craft_type_allowed
                # no assault boats while hit-and-run raids are off (owner)
                craft_types = [ct for w in bays for ct in w.get("craft_types", [])
                               if craft_type_allowed(ct, [w], gs)]
                if not craft_types:
                    continue
                enemy_ord = [OrdnanceMarker.from_dict(o) for o in gs.ordnance
                             if o["owner_player"] != self.player]
                multi_role = ("thunderhawk", "fighta_bommer", "gun_cutter")
                if enemy_ord and self.difficulty != "easy":
                    wanted = multi_role + ("fury_fighter", "barracuda", "fighter")
                else:
                    wanted = multi_role + ("starhawk_bomber", "manta", "bomber")
                preferred = next((ct for ct in wanted if ct in craft_types), craft_types[0])
                if not enemy_ord and self.difficulty != "easy":
                    held = self._hold_bays(ship, bays, craft_types, enemies)
                    if held:
                        gs.add_log(f"[AI] {ship.name} keeps its bays loaded ({held})")
                        bays_held = True
                        continue
                # Craft in play beyond the fleet's bays must go first (s.15)
                excess = fleet_craft_excess(gs, self.player)
                if excess:
                    recall_craft(gs, self.player, ai_craft_to_recall(gs, self.player, excess))
                count, roll_log = bay_launch_capacity(ship, bays, self.dice)
                for line in roll_log:
                    gs.add_log(f"[AI] {line}")
                count = min(count, fleet_craft_slots(gs, self.player))
                alloc = (self._bay_allocation(ship, craft_types, count, enemies)
                         if count > 0 and self.difficulty != "easy" else None)
                plan = None
                if alloc is not None:
                    plan = alloc["strike"]
                    self._launch_defence(ship, bays, alloc)
                    count = sum(n for _ct, n in plan) if plan else 0
                else:
                    plan = self._wave_split(ship, craft_types, count, enemies,
                                            defending=bool(enemy_ord))
                if alloc is not None and not plan:
                    pass                         # all bays went to CAP / free fighters
                elif count > 0 and plan:
                    # Plain fighters + bombers: the wave planner's split against
                    # the nearest enemy ship (waves.plan_wave_against)
                    launched = []
                    for ct, n in plan:
                        if n > 0:
                            bay = next(w for w in bays if ct in w.get("craft_types", []))
                            launched += launch_attack_craft(gs.get_ship_by_id(ship.id),
                                                            bay, ct, n, gs)
                    if len(launched) > 1:
                        from .waves import form_wave
                        for group in self._wave_groups(launched, plan):
                            form_wave(gs, [m.id for m in group], "close")
                    # Fly at the chosen target; later launches this phase see its hits
                    tgt = getattr(self, "_strike_target", None)
                    if tgt:
                        ids = {m.id for m in launched}
                        for o in gs.ordnance:
                            if o["id"] in ids:
                                o["craft_target_id"] = tgt[0]
                        oc = getattr(self, "_ord_committed", {})
                        oc[tgt[0]] = oc.get(tgt[0], 0.0) + tgt[1]
                        self._ord_committed = oc
                        self._strike_target = None
                elif count > 0:
                    launched = launch_attack_craft(ship, next(w for w in bays if preferred in
                                                              w.get("craft_types", [])),
                                                   preferred, count, gs)
                    if len(launched) > 1:            # the AI flies them as one wave (s.25)
                        from .waves import form_wave
                        form_wave(gs, [m.id for m in launched], "close")
                ship = gs.get_ship_by_id(ship.id)

    def _wave_groups(self, launched, plan):
        """The launched strike as one wave, or two when the strike planner chose
        two (`_strike_waves`): each craft type shared out, the first wave
        taking the odd one."""
        tgt = getattr(self, "_strike_target", None)
        counts = tuple(n for _ct, n in plan)
        key = (tgt[0], *counts) if tgt and len(counts) == 2 else None
        if not key or self.__dict__.get("_strike_waves", {}).get(key, 1) < 2:
            return [launched]
        first, second = [], []
        by_type = {}
        for m in launched:
            by_type.setdefault(m.ordnance_type, []).append(m)
        for ms in by_type.values():
            k = len(ms) - len(ms) // 2
            first += ms[:k]
            second += ms[k:]
        return [g for g in (first, second) if g]

    def _two_wave_value(self, tl, caps, wave, target, committed, f, b):
        """(value, expected hits) of launching f fighters + b bombers as two
        waves (fighters and bombers shared out, the first wave taking the odd
        one), or None when it can't help: fewer than two bombers, or fewer than
        two enemy shots on the way. Each wave survives the guns aimed at it
        (`split_wave_survival`), faces the turrets alone and gets half the
        interceptors; outcomes mixed over which waves get through."""
        from .ai_hazards import split_wave_survival, hull_hits_vp
        shots = tl.get("shots") or []
        if b < 2 or len(shots) < 2:
            return None
        s1, s2 = split_wave_survival(shots, 2)
        f1, b1 = f - f // 2, b - b // 2
        f2, b2 = f // 2, b // 2
        value = hits = 0.0
        for w, inp in caps:
            cap = inp["cap"]
            _v1, e1 = wave(dict(inp, cap=cap - cap // 2), f1, b1)
            _v2, e2 = wave(dict(inp, cap=cap // 2), f2, b2)
            gs = self.gs
            value += w * (s1 * s2 * hull_hits_vp(target, gs, committed, e1 + e2)
                          + s1 * (1 - s2) * hull_hits_vp(target, gs, committed, e1)
                          + (1 - s1) * s2 * hull_hits_vp(target, gs, committed, e2))
            hits += w * (s1 * e1 + s2 * e2)
        return value * tl["_disc_no_guns"], hits

    def _turret_split_bonus(self, target: Ship, phase: int, fighters: int, bombers: int,
                            f_save: int = 0, b_save: int = 0) -> float:
        """Extra hits a wave of `fighters` + `bombers` gains from torpedoes /
        missiles planned this phase to reach `target` in the same `phase`
        (ai_hazards.turret_split_gain; none against Ork turrets)."""
        from .ai_hazards import turret_split_gain
        torps = [t for t in getattr(self, "_ord_arrivals", {}).get(target.id, {}).get("torps", [])
                 if t[0] == phase]
        if not torps:
            return 0.0
        strength = sum(t[1] for t in torps)
        return turret_split_gain(target, self.gs, strength, fighters, bombers, f_save, b_save,
                                 torps[0][2])

    def _craft_due(self, target: Ship):
        """Attack craft due at `target`, as [(phase, fighters, bombers)]: planned
        this phase (_ord_arrivals) and our craft already flying at it (arrival
        by ai_hazards.strike_timeline from where they are)."""
        from .ai_hazards import strike_timeline
        from .ordnance import craft_roles
        due = [(c[0], c[1], c[2]) for c in
               getattr(self, "_ord_arrivals", {}).get(target.id, {}).get("craft", [])]
        groups = {}
        for o in self.gs.ordnance:
            if (o["owner_player"] == self.player and o.get("craft_target_id") == target.id
                    and not o.get("cap_ship_id")):
                groups.setdefault(o.get("wave_id") or o["id"], []).append(o)
        for g in groups.values():
            f = sum(1 for o in g if craft_roles(o["ordnance_type"]) == ("fighter",))
            b = sum(1 for o in g if set(craft_roles(o["ordnance_type"])) == {"bomber"})
            if not b:
                continue
            tl = strike_timeline(g[0]["x"], g[0]["y"], min((o.get("speed") or 20) for o in g),
                                 target, self.gs, self.player)
            if tl is not None:
                due.append((tl["phase"], f, b))
        return due

    def _hold_bays(self, ship: Ship, bays, craft_types, enemies) -> str:
        """Whether to keep the bays loaded this turn (a reason, or "" to launch).
        A launch means a Reload Ordnance order before the next one (s.15): a
        Leadership test, odds p. Launching now is worth V_now + p x V_next,
        holding V_next, so hold when (1 - p) x V_next > V_now. V_next: the same
        strike a turn later from a turn closer (_strike_option(next_turn=True),
        two ordnance phases of PHASE_DISCOUNT), or the CAP the enemy's loaded
        carriers would call for by then. Out of the strike planner's reach (no
        enemy within three moves of the fastest craft) the bays are always held.
        Within reach a turn's closure (both ships' moves) saves about as much
        flight as a turn's delay costs, so with fair reload odds this rarely
        holds; it does when the odds are poor and next turn's launch or CAP is
        worth clearly more."""
        from .ordnance import craft_stats, bay_launch_capacity
        from .ai_hazards import p_sum_at_most
        count = min(bay_launch_capacity(ship, bays, None)[0],
                    fleet_craft_slots(self.gs, self.player))
        if count <= 0:
            return ""
        # Out of the strike planner's reach (3 moves of the fastest craft): hold.
        # Craft flying that far face reactive fighters, turrets and guns on the
        # way and can't fly CAP meanwhile, which the values below don't capture
        fast = max((craft_stats(ct, bays)[1] or 20) for ct in set(craft_types))
        if all(ship.distance_to(e) > 3 * fast for e in enemies):
            return f"no enemy within {3 * fast}cm"
        now = self._strike_option(ship, craft_types, count, enemies)
        if now is None:
            return ""
        nxt = self._strike_option(ship, craft_types, count, enemies, next_turn=True)
        v_now, v_next = now[0], (nxt[0] if nxt else 0.0)
        friends = [s for s in self.gs.get_ships() if s.player == self.player
                   and not s.is_destroyed and not s.is_disengaged]
        cap = sorted((t[0] for t in self._anticipated_strike_slots(friends)), reverse=True)
        v_next = max(v_next, sum(cap[:count]))
        p = p_sum_at_most(2, min(10, ship.leadership or 8))
        if (1 - p) * v_next > v_now + 1e-9:
            return (f"launching now ~{v_now:.0f} VP, next turn ~{v_next:.0f} VP; "
                    f"reload odds {p:.0%}")
        return ""

    def _wave_split(self, ship: Ship, craft_types, count: int, enemies,
                    defending: bool):
        """[(type, n), ...] for one strike wave (_strike_option) when there are
        2+ squadrons and no enemy ordnance to defend against, else None (then
        the AI keeps launching fighters; used when _bay_allocation can't plan)."""
        if count < 2 or self.difficulty == "easy" or defending or not enemies:
            return None
        opt = self._strike_option(ship, craft_types, count, enemies)
        if opt is None:
            return None
        value, plan, label, target, ev = opt
        self.gs.add_log(f"[AI] {ship.name} wave vs {target.name}: {label} "
                        f"(about {value:.0f} VP)")
        self._strike_target = (target.id, ev)
        self._note_craft_arrival(target, plan)
        return plan

    def _note_craft_arrival(self, target: Ship, plan) -> None:
        """Record a planned fighter / bomber wave's arrival phase for the turret
        split (torpedoes launched later this phase can join it)."""
        if not plan or len(plan) != 2:
            return
        (_fk, f), (_bk, b) = plan
        ph = getattr(self, "_strike_phase", {}).get((target.id, f, b))
        if ph is not None and b:
            self.__dict__.setdefault("_ord_arrivals", {}).setdefault(target.id, {}).setdefault("craft", []).append(
                (ph, f, b, 0, 0))

    def _strike_option(self, ship: Ship, craft_types, count: int, enemies,
                       next_turn: bool = False):
        """Best strike of `count` squadrons against the nearest enemy ship, in
        expected VP: the wave planner's fighter / bomber split, or all assault
        boats (they ignore Armour, To do 1b). (value, [(type, n)], label,
        target), or None when the bays can't strike (multi-role craft use the
        s.24 / s.27 choices; no bombers or boats)."""
        from .waves import (split_craft_types, wave_plan_inputs,
                            expected_survivors, raid_squadron_value)
        from .ordnance import craft_roles, craft_stats
        if count < 1 or not enemies:
            return None
        cts = set(craft_types)
        bays = [w for w in ship.weapons if w.get("weapon_type") == "launch_bay"]
        stats = {ct: craft_stats(ct, bays) for ct in cts}
        if any(len(craft_roles(st[0])) > 1 for st in stats.values()):
            return None
        types = split_craft_types(ship, cts)
        bomber = next((ct for ct, st in stats.items()
                       if set(craft_roles(st[0])) == {"bomber"}), None)
        boat = next((ct for ct, st in stats.items()
                     if set(craft_roles(st[0])) == {"assault_boat"}), None)
        if not getattr(self.gs, "rule_hit_and_run", True):
            boat = None
        tb = next((ct for ct, st in stats.items() if st[0] == "torpedo_bomber"), None)
        if not bomber and not boat and not tb:
            return None
        from .ai_hazards import hull_hits_vp
        committed = getattr(self, "_ord_committed", {})
        speed = min((stats[ct][1] or 20) for ct in (bomber, boat, tb) if ct)
        near = min(enemies, key=lambda e: ship.distance_to(e))
        # Owner: focus on the easiest, most valuable targets in reach, by
        # expected VP (bomber hits through damage_vp's thresholds, counting the
        # enemy's actual damage and this phase's other launches; raids by
        # raid_squadron_value), less for targets further away
        def closure(e):
            # next_turn: the same launch a turn later, each side having moved closer
            return ((ship.effective_speed or 0) + (e.effective_speed or 0)) if next_turn else 0.0
        targets = [e for e in enemies
                   if ship.distance_to(e) - closure(e) <= 3 * speed] or [near]
        options = []
        self._strike_phase = {}
        from .ai_hazards import (best_route, phase_weight, strike_timeline,
                                 interception_cases, _predicted_positions)
        for target in targets:
            base_inputs = wave_plan_inputs(target, self.gs)
            # craft may fly round obstacles (owner): best of straight line / detours
            route = best_route(ship.x, ship.y, target.x, target.y, self.gs, "craft", speed,
                               target=target)
            ratio = max(1.0, route[2] / max(1.0, ship.distance_to(target)))
            # Valued when it lands (To do 2): the arrival phase (phase_weight),
            # enemy guns on the way, reactive CAP, the raid's repair window
            tls = {}

            def timeline(spd):
                """strike_timeline for a wave of speed `spd` (a wave moves at its
                slowest craft's speed, s.25), with the discount and CAP cases."""
                if spd not in tls:
                    if next_turn:
                        # the same launch a turn later: we move a mean move closer and
                        # the target is where it will be at our next ordnance phase
                        mv = 0.75 * (ship.effective_speed or 0)
                        d = ship.distance_to(target) or 1.0
                        lx = ship.x + (target.x - ship.x) * min(1.0, mv / d)
                        ly = ship.y + (target.y - ship.y) * min(1.0, mv / d)
                        tl = strike_timeline(lx, ly, spd, _predicted_positions(target, True)[2],
                                             self.gs, self.player, ratio)
                        offset = 2
                    else:
                        tl = strike_timeline(ship.x, ship.y, spd, target, self.gs,
                                             self.player, ratio)
                        offset = 0
                    if tl is None:
                        tls[spd] = None
                    else:
                        # Interceptors on the way, each meeting the wave's lead
                        # like CAP (s.19 / s.25): the target's CAP and other
                        # carriers' launches (REACTIVE_CAP_WEIGHT), fighters
                        # already flying (AIRBORNE_INTERCEPT_WEIGHT); every mix
                        caps = [(w, dict(base_inputs, cap=base_inputs["cap"] + ec))
                                for w, ec in interception_cases(tl)]
                        disc = route[1] * tl["survival"] * phase_weight(tl["phase"] + offset)
                        tl = dict(tl, _disc_no_guns=route[1] * phase_weight(tl["phase"] + offset))
                        tls[spd] = (tl, disc, caps)
                return tls[spd]

            def mixed(fn, caps):
                """fn(inputs) -> (value, ev, cases) mixed over the reactive-CAP
                cases; cases [(weight, value)] for risk_value."""
                v = e = 0.0
                vals = []
                for w, inp in caps:
                    a, b = fn(inp)
                    v, e = v + w * a, e + w * b
                    vals.append((w, a))
                return v, e, vals

            def risk_value(vals, disc, tl_x):
                """The strike as a gamble (To do 2, risk preference): it gets
                past the enemy guns on the way (survival) or not, and meets
                each interception case; its certainty equivalent for the game
                state (certainty_equivalent: its expected value, v x disc,
                without a turn limit; behind, gambles are worth more)."""
                from .ai_hazards import certainty_equivalent
                rest = tl_x.get("_disc_no_guns") or disc
                surv = min(1.0, disc / rest) if rest else 0.0
                outs = [(w * surv, a * rest) for w, a in vals] + [(1.0 - surv, 0.0)]
                return certainty_equivalent(self.gs, self.player, outs)
            c = committed.get(target.id, 0.0)
            if types:
                fk, bk, f_save, b_save = types

                def wave(inp, f=0, b=0):
                    from .waves import wave_split_value
                    t = inp["turrets"]
                    pp = (7 - (5 if inp.get("ork") else 4)) / 6.0
                    ev = wave_split_value(f, b, t, t + inp["massed"], inp["cap"],
                                          inp["armour"], pp, f_save, b_save, inp["cap_save"])
                    return hull_hits_vp(target, self.gs, c, ev), ev
                # The split against every interception case on the way (owner:
                # expected interceptors meet the lead, so our fighters may lead)
                best_split = None
                for f in range(count + 1):
                    b = count - f
                    spd = min((stats[k][1] or 20) for k, n in ((fk, f), (bk, b)) if n)
                    got = timeline(spd)
                    if not got:
                        continue
                    tl_s, disc, caps = got
                    v, ev, vals = mixed(lambda inp, f=f, b=b: wave(inp, f, b), caps)
                    # Owner: co-ordinate with torpedoes / missiles reaching it in the
                    # same phase: its turrets can't shoot down both (s.28)
                    syn = self._turret_split_bonus(target, tl_s["phase"], f, b,
                                                   f_save, b_save)
                    if syn:
                        sv = hull_hits_vp(target, self.gs, c + ev, syn)
                        v += sv
                        ev += syn
                        vals = [(w, a + sv) for w, a in vals]
                    rv = risk_value(vals, disc, tl_s)
                    if best_split is None or rv > best_split[0] + 1e-9:
                        best_split = (rv, f, b, ev, tl_s["phase"], 1)
                    # Two waves instead of one (To do 2): one hit removes a whole
                    # wave (s.25), but each enemy weapon fires at one marker, so
                    # splitting spreads the guns; each wave then faces the
                    # turrets and suppresses alone, and the CAP is shared
                    two = self._two_wave_value(tl_s, caps, wave, target, c, f, b)
                    if two and two[0] > best_split[0] + 1e-9:
                        best_split = (two[0], f, b, two[1], tl_s["phase"], 2)
                if best_split:
                    v, f, b, ev, ph, n_waves = best_split
                    label = f"{f} fighters + {b} bombers" + (" in two waves" if n_waves > 1
                                                             else "")
                    options.append((v, [(fk, f), (bk, b)], label, target, ev))
                    self._strike_phase[(target.id, f, b)] = ph
                    self.__dict__.setdefault("_strike_waves", {})[(target.id, f, b)] = n_waves
            elif bomber:
                from .waves import best_wave_split

                def bombers(inp):
                    t = inp["turrets"]
                    pp = (7 - (5 if inp.get("ork") else 4)) / 6.0
                    _f, _b, ev = best_wave_split(count, t, t + inp["massed"], inp["cap"],
                                                 inp["armour"], pp, 0, stats[bomber][2] or 0,
                                                 inp["cap_save"])
                    return hull_hits_vp(target, self.gs, c, ev), ev
                got = timeline(stats[bomber][1] or 20)
                if got:
                    _tl, disc, caps = got
                    v, ev, vals = mixed(bombers, caps)
                    options.append((risk_value(vals, disc, _tl), [(bomber, count)],
                                    f"{count} bombers", target, ev))
            got = timeline(stats[boat][1] or 20) if boat else None
            if got:
                tl, disc, caps = got
                raid = raid_squadron_value(target, self.gs, self.player, ship.special_rules,
                                           end_phases=tl["end_phases"])

                def boats(inp):
                    pp = (7 - (5 if inp.get("ork") else 4)) / 6.0
                    through = expected_survivors(count, inp["turrets"] + inp["massed"],
                                                 inp["cap"], pp, stats[boat][2] or 0,
                                                 inp["cap_save"])
                    return through * raid, 0.0
                v, _e, vals = mixed(boats, caps)
                options.append((risk_value(vals, disc, tl), [(boat, count)],
                                f"{count} assault boats", target, 0.0))
            got = timeline(stats[tb][1] or 20) if tb else None
            if got:
                # Torpedo bombers (s.21): the squadrons that get past the
                # interceptors fire a salvo of 2 each (Tiger Sharks: Tau
                # missiles, 5/6 of it through), which the target's turrets
                # shoot at (4+ each), on the facing it hits; they never meet
                # the turrets as craft
                tl, disc, caps = got
                from .ai_hazards import p_hit as _ph
                tiger = tb == "tiger_shark"

                def tbs(inp):
                    pp = (7 - (5 if inp.get("ork") else 4)) / 6.0
                    through = expected_survivors(count, 0, inp["cap"], pp, stats[tb][2] or 0,
                                                 inp["cap_save"])
                    strength = 2 * through * (5 / 6 if tiger else 1.0)
                    hits = max(0.0, strength - 0.5 * inp["turrets"]) * _ph(
                        target.armor_vs(ship.x, ship.y))
                    return hull_hits_vp(target, self.gs, c, hits), hits
                v, ev, vals = mixed(tbs, caps)
                options.append((risk_value(vals, disc, tl), [(tb, count)],
                                f"{count} torpedo bombers", target, ev))
        if not options:
            return None
        value, plan, label, target, ev = max(options, key=lambda o: o[0])
        return value, plan, label, target, ev

    def _bay_allocation(self, ship: Ship, craft_types, count: int, enemies):
        """CAP vs free fighters vs strike (owner: a trade-off; HANDOFF "AI design").
        Greedy over the ship's launch slots in one VP currency: each slot goes to
        whichever is worth more now -
          - a fighter against the next uncovered enemy threat (intercept_gain:
            a whole salvo or mine, or the next squadron of a wave): on CAP for the
            friendly ship it is closing on (full value; CAP always intercepts,
            s.26) if the fighters can reach that ship, else free (0.75) if the
            threat is within the fighters' reach;
          - one more squadron in the strike (its value with k + 1 squadrons minus
            with k, _strike_option).
        Threats our fighters already fly at count as covered. Returns {"strike":
        [(type, n)], "cap": [(ship_id, n)], "free": n, "fighter": type}, or None
        when the bays have no plain fighter type (multi-role craft)."""
        from .ordnance import craft_roles, craft_stats
        bays = [w for w in ship.weapons if w.get("weapon_type") == "launch_bay"]
        stats = {ct: craft_stats(ct, bays) for ct in set(craft_types)}
        if any(len(craft_roles(st[0])) > 1 for st in stats.values()):
            return None
        fighter = next((ct for ct, st in stats.items()
                        if set(craft_roles(st[0])) == {"fighter"}), None)
        if fighter is None:
            return None
        spd = stats[fighter][1] or 30
        gs = self.gs
        fleet = getattr(self, "_fleet_defence", None)
        if fleet is not None and ship.id in fleet["carriers"]:
            # Fleet-wide plan (_plan_fleet_defence): only the threats this
            # carrier was given; the others are covered by better-placed carriers
            threats = list(fleet["assigned"].get(ship.id, []))
        else:
            threats = [t for slot in self._threat_slots()
                       for t in [self._slot_for(ship, spd, slot)] if t]
        threats.sort(key=lambda t: -t[0])
        cache = {0: (0.0, None)}

        def strike(k):
            if k not in cache:
                opt = self._strike_option(ship, craft_types, k, enemies)
                cache[k] = (opt[0], opt) if opt else (0.0, None)
            return cache[k][0]
        # Strike values are far from linear (fighters suppress turrets, a big
        # wave cripples), so choose how many slots defend exactly: j maximising
        # strike(count - j) + the j best threat gains
        threats = [t for t in threats if t[0] > 0]
        j = self._best_defence_count(count, [t[0] for t in threats], strike)
        cap, free = {}, 0
        for _g, kind, sid in threats[:j]:
            if kind == "cap":
                cap[sid] = cap.get(sid, 0) + 1
            else:
                free += 1
        k = count - j
        plan = None
        if k:
            strike(k)
            opt = cache[k][1]
            if opt:
                value, plan, label, target, ev = opt
                gs.add_log(f"[AI] {ship.name} strike vs {target.name}: {label} "
                           f"(about {value:.0f} VP)")
                self._strike_target = (target.id, ev)
                self._note_craft_arrival(target, plan)
            else:
                free += k                 # nothing to strike with: fighters go free
        if cap or free:
            gs.add_log(f"[AI] {ship.name} keeps {sum(cap.values())} fighter(s) on CAP, "
                       f"{free} free against incoming ordnance")
        return {"strike": plan, "cap": list(cap.items()), "free": free, "fighter": fighter}

    @staticmethod
    def _best_defence_count(count, gains, strike):
        """j in 0..min(count, len(gains)) maximising strike(count - j) +
        sum(gains[:j]) (gains best first); ties keep the strike."""
        best_j, best_v, acc = 0, strike(count), 0.0
        for j in range(1, min(count, len(gains)) + 1):
            acc += gains[j - 1]
            v = strike(count - j) + acc
            if v > best_v + 1e-9:
                best_j, best_v = j, v
        return best_j

    def _threat_slots(self):
        """Enemy ordnance a fighter could meet, one entry per fighter it would
        take: (gain, marker x, y, guard ship id or None, threat key, k). A salvo or
        mine is one slot; a wave one per squadron, lead first (intercept_gain).
        Threats our fighters already fly at count as covered."""
        import math as _m
        from .ai_hazards import intercept_gain
        gs = self.gs
        covered = {o.get("craft_target_id") for o in gs.ordnance
                   if o["owner_player"] == self.player and o.get("craft_target_id")}
        friends = [s for s in gs.get_ships() if s.player == self.player
                   and not s.is_destroyed and not s.is_disengaged]
        slots, seen_waves = [], set()
        for o in gs.ordnance:
            if o["owner_player"] == self.player or o.get("cap_ship_id"):
                continue
            m = OrdnanceMarker.from_dict(o)
            if m.wave_id:
                if m.wave_id in seen_waves:
                    continue
                seen_waves.add(m.wave_id)
            if m.id in covered:
                continue
            n_sq = (sum(1 for x in gs.ordnance if x.get("wave_id") == m.wave_id)
                    if m.wave_id else 1)
            # The friendly ship it is closing on: nearest within its move + 15cm
            reach = (m.speed or 20) + 15.0
            near = [f for f in friends if _m.hypot(f.x - m.x, f.y - m.y) <= reach]
            guard = min(near, key=lambda f: _m.hypot(f.x - m.x, f.y - m.y)) if near else None
            for k in range(n_sq):
                g = intercept_gain(gs, self.player, m, already=k)
                if g <= 0:
                    break
                slots.append((g, m.x, m.y, guard, m.wave_id or m.id, k))
        # Fighters already on CAP for a ship intercept whatever reaches it (s.26):
        # each takes one of the slots closing on that ship, the most valuable first
        cap_left = {}
        for o in gs.ordnance:
            if o["owner_player"] == self.player and o.get("cap_ship_id"):
                cap_left[o["cap_ship_id"]] = cap_left.get(o["cap_ship_id"], 0) + 1
        drop = set()
        for idx in sorted(range(len(slots)), key=lambda i: -slots[i][0]):
            guard = slots[idx][3]
            if guard is not None and cap_left.get(guard.id, 0) > 0:
                cap_left[guard.id] -= 1
                drop.add(idx)
        slots = [t for i, t in enumerate(slots) if i not in drop]
        slots += self._anticipated_strike_slots(friends, cap_left)
        return slots

    # Weight on a strike the enemy hasn't launched yet: it may not launch, may
    # go for another ship, and its wave may lead with a fighter (judgement)
    ANTICIPATED_STRIKE_WEIGHT = 0.5

    def _anticipated_weight(self) -> float:
        """ANTICIPATED_STRIKE_WEIGHT scaled by the air balance (owner: carrier
        doctrine): out-carriered, expect more enemy strikes and fly more CAP /
        interception; dominant, less (x enemy / our launch capacity, kept to
        0.5-1.8 times: 0.25-0.9)."""
        from .ai_hazards import air_balance
        ours, theirs = air_balance(self.gs, self.player)
        ratio = theirs / max(1, ours) if theirs else 0.0
        return self.ANTICIPATED_STRIKE_WEIGHT * max(0.5, min(1.8, ratio)) if theirs else 0.0

    TELEPORT_SHIELDS_DOWN = 0.3   # judgement: chance enemy guns drop our shields first

    def _teleport_exposure(self, ship: Ship, x: float, y: float, target: Ship) -> float:
        """To do 8 j (2), defence: ending within an enemy teleporter's reach
        (teleport range + its move) risks its end-phase raid (s.31) when our
        shields may be down by then (certain if blast markers at the end point
        already cover them, else TELEPORT_SHIELDS_DOWN) and we have no more hits
        left than it. The raid's expected VP (waves.raid_squadron_value), in the
        planner's firepower units. Nothing unless teleports and hit-and-run
        raids are on (owner)."""
        gs = self.gs
        if self.difficulty == "easy" or not (getattr(gs, "rule_teleport", False)
                                             and getattr(gs, "rule_hit_and_run", False)):
            return 0.0
        if ship.ship_type == "escort" and ship.hits_max < 3:
            return 0.0
        from .hit_and_run import teleport_range
        from .waves import raid_squadron_value
        from .ai_hazards import blast_markers_at, value_per_hit
        from .geometry import current_shields
        vp = 0.0
        for e in self._live_enemies():
            if "teleport_assault" not in e.special_rules or e.is_crippled:
                continue
            if ship.hits_remaining > e.hits_remaining:
                continue
            if math.hypot(e.x - x, e.y - y) > teleport_range(e) + (e.effective_speed or 0):
                continue
            shields = current_shields(ship, gs.get_blast_markers())
            down = 1.0 if blast_markers_at(ship, (x, y), gs) >= shields else \
                self.TELEPORT_SHIELDS_DOWN
            vp += down * raid_squadron_value(ship, gs, e.player, e.special_rules)
        if vp <= 0:
            return 0.0
        return vp / (0.35 * max(1.0, value_per_hit(target, gs)))

    def _boarding_reach(self, ship: Ship, x: float, y: float, target: Ship) -> float:
        """To do 8 h: an end position in base contact with an enemy gains the
        boarding action's net value (`_boarding_gain`), in the planner's
        firepower units. Only with the boarding rule on (owner)."""
        if self.difficulty == "easy" or not getattr(self.gs, "rule_boarding", False):
            return 0.0
        from .geometry import BASE_CONTACT_MARGIN_CM
        from .ai_hazards import value_per_hit
        import dataclasses
        at = dataclasses.replace(ship, x=x, y=y)
        best = 0.0
        for e in self._live_enemies():
            if math.hypot(e.x - x, e.y - y) <= e.base_radius + ship.base_radius + BASE_CONTACT_MARGIN_CM:
                best = max(best, self._boarding_gain(at, e))
        if best <= 0:
            return 0.0
        return best / (0.35 * max(1.0, value_per_hit(target, self.gs)))

    def _teleport_reach(self, ship: Ship, x: float, y: float, target: Ship,
                        order: str = "") -> float:
        """To do 8 j (1), offence: a teleporter (s.31: not crippled, on no order
        but Lock On / Reload Ordnance) ending within teleport range of an enemy
        with no more hits left than it gains the best raid there (waves.
        raid_squadron_value) x the chance the target's shields are down in our
        end phase: 1 if they already are, 0.6 if our fleet's guns this turn
        are expected to put at least that many hits on it (`_our_hits`), else
        0.1 (judgement), in the planner's firepower units. Nothing unless
        teleports and hit-and-run raids are on (owner)."""
        gs = self.gs
        if self.difficulty == "easy" or not (getattr(gs, "rule_teleport", False)
                                             and getattr(gs, "rule_hit_and_run", False)):
            return 0.0
        if "teleport_assault" not in ship.special_rules or ship.is_crippled:
            return 0.0
        if order not in ("", "none", SpecialOrder.LOCK_ON.value,
                         SpecialOrder.RELOAD_ORDNANCE.value):
            return 0.0
        from .hit_and_run import teleport_range
        from .waves import raid_squadron_value
        from .ai_hazards import value_per_hit
        from .geometry import current_shields
        ours = getattr(self, "_our_hits", {}) or {}
        best = 0.0
        for e in self._live_enemies():
            if e.hits_remaining > ship.hits_remaining:
                continue
            if e.ship_type == "escort" and e.hits_max < 3:
                continue
            if math.hypot(e.x - x, e.y - y) > teleport_range(ship) + e.base_radius:
                continue
            sh = current_shields(e, gs.get_blast_markers())
            p = 1.0 if sh <= 0 else (0.6 if ours.get(e.id, 0.0) >= sh else 0.1)
            best = max(best, p * raid_squadron_value(e, gs, self.player, ship.special_rules))
        if best <= 0:
            return 0.0
        return best / (0.35 * max(1.0, value_per_hit(target, gs)))

    def _carrier_exposure(self, ship: Ship, x: float, y: float, target: Ship) -> float:
        """Owner: when the enemy has more launch capacity, protect our carriers.
        The expected VP of enemy strikes that could reach this end position (each
        loaded enemy carrier with bombers / assault boats within its move + its
        craft's speed: its squadrons at a bomber squadron's value against this
        ship, shared over our ships in that reach, x the doctrine weight),
        counted for carriers only and weighted by the share of our launch
        capacity this ship carries, doubled when the enemy out-carriers us; in
        the planner's firepower units."""
        if self.difficulty == "easy":
            return 0.0
        from .ai_hazards import air_balance, value_per_hit, _bays
        from .ordnance import craft_roles, craft_stats, bay_launch_capacity
        from .waves import bomber_squadron_value
        mine = _bays(ship)
        if not mine:
            return 0.0
        ours, theirs = air_balance(self.gs, self.player)
        if not theirs:
            return 0.0
        share = bay_launch_capacity(ship, mine, None)[0] / max(1, ours)
        doctrine = 2.0 if theirs > ours else 1.0
        moved = Ship.from_dict({**ship.to_dict(), "x": x, "y": y})
        friends = [f for f in self.gs.get_ships() if f.player == self.player
                   and not f.is_destroyed and not f.is_disengaged]
        vp = 0.0
        for e in self.gs.get_ships():
            if (e.player == self.player or e.is_destroyed or e.is_disengaged
                    or not e.ordnance_loaded_craft):
                continue
            bays = _bays(e)
            strike_speeds = [craft_stats(ct, bays)[1] or 20 for w in bays
                             for ct in w.get("craft_types", [])
                             if set(craft_roles(craft_stats(ct, bays)[0])) & {"bomber",
                                                                              "assault_boat"}]
            if not strike_speeds:
                continue
            reach = (e.effective_speed or 0) + max(strike_speeds)
            if math.hypot(e.x - x, e.y - y) > reach:
                continue
            others = sum(1 for f in friends if f.id != ship.id
                         and math.hypot(e.x - f.x, e.y - f.y) <= reach)
            n = bay_launch_capacity(e, bays, None)[0]
            vp += n * bomber_squadron_value(moved, self.gs) / (1 + others)
        vp *= self._anticipated_weight() * (1 + share) * doctrine
        per_fp = 0.35 * max(1.0, value_per_hit(target, self.gs))
        return vp / per_fp

    def _anticipated_strike_slots(self, friends, cap_left=None):
        """CAP against enemy strikes not launched yet (To do 1): fighters on CAP
        stay with their ship until removed (s.26), so a ship within reach of an
        enemy carrier with loaded bombers / assault boats (its move + the craft's
        speed) gains by one fighter per enemy squadron that could come: each
        removes one squadron (s.19). Value per slot: that squadron's value against
        the ship (waves.bomber_squadron_value / raid_squadron_value), split
        evenly over the ships in that carrier's reach, x ANTICIPATED_STRIKE_WEIGHT.
        Fighters already on CAP for the ship (`cap_left`: those not already taken
        by launched threats) take the best slots first. Slots are
        (gain, None, None, guard, key, k): CAP only."""
        from .ordnance import craft_roles, craft_stats, bay_launch_capacity
        from .waves import bomber_squadron_value, raid_squadron_value
        gs = self.gs
        per_ship = {}                    # ship id -> [(value, squadrons)]
        for e in gs.get_ships():
            if (e.player == self.player or e.is_destroyed or e.is_disengaged
                    or not e.ordnance_loaded_craft):
                continue
            bays = [w for w in e.weapons if w.get("weapon_type") == "launch_bay"]
            roles, speed = set(), None
            for ct in {ct for w in bays for ct in w.get("craft_types", [])}:
                st = craft_stats(ct, bays)
                r = set(craft_roles(st[0]))
                if r - {"fighter"}:
                    roles |= r
                    speed = min(speed or 99, st[1] or 20)
            if not roles:
                continue
            n = bay_launch_capacity(e, bays, None)[0]
            reach = (e.effective_speed or 0) + speed
            near = [f for f in friends if e.distance_to(f) <= reach]
            for f in near:
                v = 0.0
                if roles & {"bomber"}:
                    v = bomber_squadron_value(f, gs)
                if roles & {"assault_boat"} and getattr(gs, "rule_hit_and_run", True):
                    v = max(v, raid_squadron_value(f, gs, e.player, e.special_rules))
                g = self._anticipated_weight() * v / len(near)
                if g > 0 and n > 0:
                    per_ship.setdefault(f.id, []).append((g, n))
        slots = []
        for fid, items in per_ship.items():
            guard = next(f for f in friends if f.id == fid)
            if cap_left is None:
                have = sum(1 for o in gs.ordnance if o["owner_player"] == self.player
                           and o.get("cap_ship_id") == fid)
            else:
                have = cap_left.get(fid, 0)     # CAP not taken by launched threats
            gains = sorted((g for g, n in items for _ in range(n)), reverse=True)[have:]
            slots += [(g, None, None, guard, f"pre:{fid}", k) for k, g in enumerate(gains)]
        return slots

    @staticmethod
    def _slot_for(carrier, spd, slot):
        """A threat slot as this carrier would cover it: (gain, "cap", guard id)
        when its fighters can reach the guarded ship (CAP always intercepts,
        s.26), (0.75 x gain, "free", "") when they can reach the threat, else None."""
        import math as _m
        g, x, y, guard, _key, _k = slot
        if guard is not None and carrier.distance_to(guard) <= spd:
            return (g, "cap", guard.id)
        if x is None:
            return None                       # a strike not launched yet: CAP only
        if _m.hypot(carrier.x - x, carrier.y - y) <= spd:
            return (0.75 * g, "free", "")
        return None

    def _plan_fleet_defence(self, enemies):
        """Fleet-wide CAP vs strike (To do 1): which carrier covers which
        incoming threat. Every carrier starts with all its bays in its strike;
        carriers with the weakest strike per squadron then take threat slots
        first, as many as maximise their strike value (_strike_option) plus the
        fighters' gains (CAP full, free 0.75), best reachable slot first (a
        wave's squadrons lead first). A slot nobody gains by covering is left. Carriers with
        multi-role or no plain fighters, or nothing loaded, are left out (they
        plan alone). Returns {"carriers": set of ids, "assigned": {id: [(gain,
        kind, guard id)]}}."""
        from .ordnance import craft_roles, craft_stats, bay_launch_capacity
        gs = self.gs
        carriers = []
        for ship in gs.player_ships(self.player):
            if ship.is_destroyed or ship.is_disengaged or not ship.ordnance_loaded_craft:
                continue
            bays = [w for w in ship.weapons if w.get("weapon_type") == "launch_bay"]
            cts = [ct for w in bays for ct in w.get("craft_types", [])]
            if not cts:
                continue
            stats = {ct: craft_stats(ct, bays) for ct in set(cts)}
            if any(len(craft_roles(st[0])) > 1 for st in stats.values()):
                continue
            fighter = next((ct for ct, st in stats.items()
                            if set(craft_roles(st[0])) == {"fighter"}), None)
            if fighter is None:
                continue
            count = bay_launch_capacity(ship, bays, None)[0]    # random bays: estimate
            if count > 0:
                carriers.append((ship, cts, count, stats[fighter][1] or 30))
        plan = {"carriers": {c[0].id for c in carriers}, "assigned": {}}
        if not carriers:
            return plan
        cache = {}

        def strike(i, k):
            if (i, k) not in cache:
                ship, cts, _n, _s = carriers[i]
                opt = self._strike_option(ship, cts, k, enemies) if k else None
                cache[(i, k)] = opt[0] if opt else 0.0
            return cache[(i, k)]
        by_key = {}
        for slot in self._threat_slots():
            by_key.setdefault(slot[4], []).append(slot)
        queues = {key: sorted(v, key=lambda t: t[5]) for key, v in by_key.items()}
        # Carriers with the weakest strike per squadron defend first; each takes
        # the exact number of slots that maximises its own strike + the gains
        # (_best_defence_count), always the best slot it can reach next (a wave's
        # squadrons lead first)
        order = sorted(range(len(carriers)),
                       key=lambda i: strike(i, carriers[i][2]) / carriers[i][2])
        for i in order:
            ship, _cts, n, spd = carriers[i]
            trial = {key: list(q) for key, q in queues.items()}
            picks = []
            while len(picks) < n:
                heads = [(self._slot_for(ship, spd, q[0]), key)
                         for key, q in trial.items() if q]
                heads = [(t, key) for t, key in heads if t and t[0] > 0]
                if not heads:
                    break
                t, key = max(heads, key=lambda h: h[0][0])
                picks.append((t, key))
                trial[key].pop(0)
            jn = self._best_defence_count(n, [t[0] for t, _k in picks],
                                          lambda k, i=i: strike(i, k))
            for t, key in picks[:jn]:
                queues[key].pop(0)
                plan["assigned"].setdefault(ship.id, []).append(t)
        return plan

    def _launch_defence(self, ship: Ship, bays, alloc):
        """Launch _bay_allocation's CAP and free fighters (not in the wave)."""
        gs = self.gs
        fk = alloc["fighter"]
        bay = next(w for w in bays if fk in w.get("craft_types", []))
        for sid, n in alloc["cap"]:
            guard = gs.get_ship_by_id(sid)
            launched = launch_attack_craft(gs.get_ship_by_id(ship.id), bay, fk, n, gs)
            ids = {m.id for m in launched}
            for o in gs.ordnance:
                if o["id"] in ids and guard:
                    o["cap_ship_id"] = sid
                    o["x"], o["y"] = guard.x, guard.y
        if alloc["free"]:
            launch_attack_craft(gs.get_ship_by_id(ship.id), bay, fk, alloc["free"], gs)

    # ── Auto repair (for end phase) ──────────────────────────────────────────

    @staticmethod
    def auto_repair_choices(repairable: List[str], max_repairs: int) -> List[str]:
        """Pick the first N repairable crits (list is already priority-ordered)."""
        return repairable[:max_repairs]

    # ── Position / ordnance prediction ──────────────────────────────────────

    def _predict_torp_positions(self):
        """
        Return list of (x, y, strength) for each enemy torpedo/mine
        at its predicted next-turn position.
        """
        gs = self.gs
        results = []
        for o_dict in gs.ordnance:
            marker = OrdnanceMarker.from_dict(o_dict)
            if marker.owner_player == self.player:
                continue
            if "torpedo" not in marker.ordnance_type and "mine" not in marker.ordnance_type:
                continue
            rad = math.radians(marker.heading)
            nx = marker.x + marker.speed * math.cos(rad)
            ny = marker.y + marker.speed * math.sin(rad)
            results.append((nx, ny, marker.strength))
        return results

    def _predict_ship_pos(self, ship: Ship):
        """Rough prediction of where a ship will be next turn (straight ahead, full speed)."""
        rad = math.radians(ship.heading)
        return (ship.x + ship.effective_speed * math.cos(rad),
                ship.y + ship.effective_speed * math.sin(rad))

    def _torpedo_aim_heading(self, ship: Ship, weapon: Dict,
                             target: Ship) -> float:
        """
        Intercept heading for a straight-running torpedo, clamped to the
        front arc. The iterative solve naturally yields direct fire at
        short range (time-to-impact → 0, so the aim point is the target's
        current position) and leads the target at long range.
        """
        if not self._torpedo_turns(ship, weapon):
            plan = self._torp_lead_plan(ship, weapon, target)
        else:
            plan = self._approach_for_launch(ship, weapon, target)
        if plan is not None:
            return plan["heading"]
        return self._torp_lane(ship, weapon, target, *self._intercept(ship, weapon, target))[0]

    def _approach_for_launch(self, ship: Ship, weapon: Dict, target: Ship):
        """Owner: a salvo that can turn and rolls against Armour may fire off to
        the side or take a detour to come in on a weaker facing
        (ai_hazards.approach_plan from the launcher: any heading in the launch
        arc, then a 45-degree turn at the start of each later move)."""
        from .ai_hazards import approach_plan, p_sum_at_most
        from .ordnance import compute_torpedo_launch_exempt
        ttype = weapon.get("torpedo_type")
        boarding = ttype == "boarding"
        tau = ttype == "guided"
        p_turn = 1.0
        if not (boarding or tau):                      # bought Leadership-guided torpedoes
            p_turn = p_sum_at_most(2, min(10, ship.leadership or 8))
        speed = weapon.get("torpedo_speed", TORPEDO_SPEED_DEFAULT) or TORPEDO_SPEED_DEFAULT
        exempt = set(compute_torpedo_launch_exempt(ship, self.gs))
        friends = [] if boarding else [
            f for f in self.gs.get_ships() if f.player == self.player and f.id not in exempt
            and not f.is_destroyed and not f.is_disengaged]
        committed = getattr(self, "_ord_committed", {}).get(target.id, 0.0)
        return approach_plan(ship.x, ship.y, ship.heading, speed, target, self.gs, self.player,
                             weapon.get("strength") or 0, arc_half=45.0, p_turn=p_turn,
                             our_phase=True, boarding=boarding, tau=tau, friends=friends,
                             committed=committed, lengths=(20.0, 30.0, 40.0) if tau else None)

    @staticmethod
    def _torpedo_turns(ship: Ship, weapon: Dict) -> bool:
        """Salvos that can turn after launch (Tau missiles, Leadership-guided
        torpedoes) lead less: they steer (owner). These keep the intercept aim."""
        return (weapon.get("torpedo_type") in ("guided", "boarding")
                or "guided" in ship_torpedo_types(ship))

    def _torp_lane(self, ship: Ship, weapon: Dict, target: Ship, desired: float,
                   dist: float, strength: Optional[int] = None):
        """(heading, value, hits on target, friendly VP lost) for a straight salvo aimed at
        `target`, over the headings that still meet it (the intercept heading
        +/- the angle its base and the marker's half width subtend, s.15),
        clamped to the 45-degree launch arc either side of the heading.
        The salvo attacks every ship it contacts, friend or foe, and carries on
        with its strength reduced by 1 per hit (s.15). So along each lane, in
        order of contact up to one move past the target: a friendly ship takes
        the salvo's strength against its Armour (no turrets: they only fire at
        enemy ordnance, s.28) and costs us its expected VP (owner: friendly fire
        is negative VP), an enemy ship takes torpedo_salvo_hits; each reduces
        the strength. Value = path survival (blast markers, phenomena) x
        (enemy VP added - friendly VP lost). Ships in contiguous base contact
        with the launcher are passed through; boarding torpedoes ignore friends
        (s.16). With no `strength` the weapon's is used."""
        from .geometry import torpedo_first_contact, TORP_BODY_HALF_W_CM
        from .ordnance import compute_torpedo_launch_exempt
        from .ai_hazards import (torpedo_path_survival, torpedo_salvo_hits, added_vp, p_hit,
                                 attack_survival)
        gs = self.gs
        dist = max(dist, 1.0)
        if strength is None:
            strength = weapon.get("strength") or 0
        speed = weapon.get("torpedo_speed", TORPEDO_SPEED_DEFAULT) or TORPEDO_SPEED_DEFAULT
        reach = dist + speed
        window = math.degrees(math.atan((target.base_radius + TORP_BODY_HALF_W_CM) / dist))
        friendly_ok = weapon.get("torpedo_type") == "boarding"
        exempt = set(compute_torpedo_launch_exempt(ship, gs))
        committed = getattr(self, "_ord_committed", {})
        others = [o for o in gs.get_ships() if o.id not in exempt and not o.is_destroyed
                  and not o.is_disengaged and not (friendly_ok and o.player == self.player)]
        best = None
        for frac in (0.0, -0.3, 0.3, -0.6, 0.6, -0.85, 0.85):
            diff = signed_angle_diff((desired + frac * window) % 360, ship.heading)
            h = (ship.heading + max(-45.0, min(45.0, diff))) % 360
            ex = ship.x + reach * math.cos(math.radians(h))
            ey = ship.y + reach * math.sin(math.radians(h))
            contacts = []
            for o in others:
                pt = torpedo_first_contact(o.x, o.y, o.base_radius, ship.x, ship.y, ex, ey, h)
                if pt:
                    contacts.append((math.hypot(pt[0] - ship.x, pt[1] - ship.y), o, pt))
            contacts.sort(key=lambda c: c[0])
            left, value, on_target, met, lost = float(strength), 0.0, 0.0, False, 0.0
            for _d, o, _pt in contacts:
                if left <= 0:
                    break
                if o.player == self.player:
                    hits = left * p_hit(o.armor_vs(ship.x, ship.y))
                    loss = added_vp(o, gs, 0.0, hits, shields=False)
                    value -= loss
                    lost += loss
                else:
                    hits = torpedo_salvo_hits(left, o, gs, (ship.x, ship.y))
                    value += added_vp(o, gs, committed.get(o.id, 0.0), hits, shields=False)
                    if o.id == target.id:
                        on_target, met = hits, True
                left -= hits
            if not met:
                continue                          # this heading misses the target
            value *= torpedo_path_survival(ship.x, ship.y, ex, ey, gs) * attack_survival(target, gs)
            if best is None or value > best[1] + 1e-9:
                best = (h, value, on_target, lost)
        if best is None:                          # no heading meets it: aim as near as allowed
            diff = signed_angle_diff(desired % 360, ship.heading)
            return ((ship.heading + max(-45.0, min(45.0, diff))) % 360, 0.0, 0.0, 0.0)
        return best

    def _torp_lead_plan(self, ship: Ship, weapon: Dict, target: Ship,
                        strength: Optional[int] = None):
        """Owner: lead the target with straight-running torpedoes from where it
        can be. The salvo moves its speed now (P0 -> P1), stays at P1 while the
        enemy moves (a ship moving into it is attacked, s.15) and moves on to P2
        in the enemy's ordnance phase. The target's next move is sampled
        (ai_hazards.enemy_move_samples: half to full speed, one turn after its
        turning distance); it dodges when it can with DODGE_WEIGHT: by a normal
        move that misses if there is one (so abeam targets, spread across the
        lane, are hard to hit and closing ones, spread along it, easy), else by
        Burn Retros / All Ahead Full at its Leadership odds; a salvo parked
        within its minimum move ahead can only be escaped that way. Friendly
        ships stay put until our next turn, so every one the salvo touches on
        P0 -> P2 costs its damage's VP (owner: friendly fire is negative VP);
        hits weaken the salvo (s.15); other enemies in the lane soak up strength
        but their VP is left to their own plans. Returns {"heading", "value" (expected VP,
        path survival included), "p_hit", "hits"} for the best heading in the
        launch arc, or None when no heading can reach the target within this
        turn and the enemy's (then the longer-range intercept is used)."""
        from .ai_hazards import (attack_survival, enemy_move_samples, seg_first_contact, path_touches,
                                 TORP_CONTACT_HALF_W, DODGE_WEIGHT, torpedo_path_survival,
                                 LATER_TURN_WEIGHT, phase_weight,
                                 torpedo_salvo_hits, added_vp, p_hit, p_sum_at_most)
        from .ordnance import compute_torpedo_launch_exempt
        gs = self.gs
        if strength is None:
            strength = weapon.get("strength") or 0
        speed = weapon.get("torpedo_speed", TORPEDO_SPEED_DEFAULT) or TORPEDO_SPEED_DEFAULT
        normal, dodge = enemy_move_samples(target)
        reach = 2 * speed + target.base_radius + TORP_CONTACT_HALF_W
        if min(math.hypot(p[-1][0] - ship.x, p[-1][1] - ship.y) for p in normal + dodge) > reach:
            return None
        friendly_ok = weapon.get("torpedo_type") == "boarding"
        exempt = set(compute_torpedo_launch_exempt(ship, gs))
        friends = [] if friendly_ok else [
            f for f in gs.get_ships() if f.player == self.player and f.id not in exempt
            and not f.is_destroyed and not f.is_disengaged]
        foes = [o for o in gs.get_ships() if o.player != self.player and o.id != target.id
                and not o.is_destroyed and not o.is_disengaged]
        committed = getattr(self, "_ord_committed", {})
        from_xy = (ship.x, ship.y)
        rt = target.base_radius + TORP_CONTACT_HALF_W
        p_pass = p_sum_at_most(2, min(10, target.leadership or 8))

        heads = {round(math.degrees(math.atan2(target.y - ship.y, target.x - ship.x)) % 360, 1)}
        for path in normal + dodge:
            for pt in path[1:]:
                heads.add(round(math.degrees(math.atan2(pt[1] - ship.y, pt[0] - ship.x)) % 360, 1))
        heads.add(round(self._intercept(ship, weapon, target)[0], 1))
        clamped = set()
        for h in heads:
            diff = signed_angle_diff(h, ship.heading)
            clamped.add(round((ship.heading + max(-45.0, min(45.0, diff))) % 360, 1))

        def friend_hits(seg, left):
            """Friendly losses (VP) and strength left along a static segment."""
            hits_on = []
            for f in friends:
                t = seg_first_contact(*seg, f.x, f.y, f.base_radius + TORP_CONTACT_HALF_W)
                if t is not None:
                    hits_on.append((t, f))
            return sorted(hits_on, key=lambda c: c[0])

        best = None
        for h in sorted(clamped):
            c, sn = math.cos(math.radians(h)), math.sin(math.radians(h))
            p1 = (ship.x + speed * c, ship.y + speed * sn)
            p2 = (ship.x + 2 * speed * c, ship.y + 2 * speed * sn)
            # Launch move: ships where they are now
            left, base_v, lost = float(strength), 0.0, 0.0
            hit_now = False
            seq = [(t, f) for t, f in friend_hits((ship.x, ship.y, p1[0], p1[1]), left)]
            for o in foes + [target]:
                t = seg_first_contact(ship.x, ship.y, p1[0], p1[1], o.x, o.y,
                                      o.base_radius + TORP_CONTACT_HALF_W)
                if t is not None:
                    seq.append((t, o))
            target_hits_now = 0.0
            for _t, o in sorted(seq, key=lambda c: c[0]):
                if left <= 0:
                    break
                if o.player == self.player:
                    hh = left * p_hit(o.armor_vs(*from_xy))
                    loss = added_vp(o, gs, 0.0, hh, shields=False)
                    base_v -= loss
                    lost += loss
                else:
                    hh = torpedo_salvo_hits(left, o, gs, from_xy)
                    if o.id == target.id:
                        hit_now, target_hits_now = True, hh
                    # other enemies in the lane soak up strength; their VP is
                    # counted when they are the target (keeps targets distinct)
                left -= hh

            def outcome(path):
                """(hit?, value) of this enemy move after the launch move."""
                if hit_now:
                    return True, added_vp(target, gs, committed.get(target.id, 0.0),
                                          target_hits_now, shields=False)
                lft, v = left, 0.0
                w1 = phase_weight(1)           # the enemy's turn: one phase later
                if lft > 0 and path_touches(path, p1[0], p1[1], rt):
                    hh = torpedo_salvo_hits(lft, target, gs, from_xy)   # it runs into the salvo
                    v = w1 * added_vp(target, gs, committed.get(target.id, 0.0), hh,
                                      shields=False)
                    lft -= hh
                    hit = True
                else:
                    hit = False
                ex, ey = path[-1]
                seq2 = friend_hits((p1[0], p1[1], p2[0], p2[1]), lft)
                if not hit:
                    t = seg_first_contact(p1[0], p1[1], p2[0], p2[1], ex, ey, rt)
                    if t is not None:
                        seq2.append((t, target))
                for _t, o in sorted(seq2, key=lambda cc: cc[0]):
                    if lft <= 0:
                        break
                    if o.player == self.player:
                        hh = lft * p_hit(o.armor_vs(*from_xy))
                        v -= added_vp(o, gs, 0.0, hh, shields=False)
                    else:
                        hh = torpedo_salvo_hits(lft, o, gs, from_xy)
                        v += w1 * added_vp(o, gs, committed.get(o.id, 0.0), hh, shields=False)
                        hit = True
                    lft -= hh
                if hit or lft <= 0:
                    return (1.0 if hit else 0.0), v
                # Missed this turn: the salvo runs on (P2 -> P3 in our next
                # ordnance phase while the target sits at E, P3 -> P4 in the
                # enemy's), and the target carries on along its course for a mean
                # move. A receding target is chased down the lane; an abeam one
                # that was missed stays missed. Weighted LATER_TURN_WEIGHT: it
                # sees the salvo coming and the course is a guess
                fh = (math.atan2(path[-1][1] - path[-2][1], path[-1][0] - path[-2][0])
                      if len(path) > 1 else math.radians(target.heading))
                mv = 0.75 * (target.effective_speed or 0)
                e2 = (ex + mv * math.cos(fh), ey + mv * math.sin(fh))
                p3 = (p2[0] + speed * c, p2[1] + speed * sn)
                p4 = (p3[0] + speed * c, p3[1] + speed * sn)
                if seg_first_contact(p2[0], p2[1], p3[0], p3[1], ex, ey, rt) is not None:
                    k2 = 2                     # our next ordnance phase
                elif (path_touches([(ex, ey), e2], p3[0], p3[1], rt)
                      or seg_first_contact(p3[0], p3[1], p4[0], p4[1], e2[0], e2[1], rt)
                      is not None):
                    k2 = 3                     # the enemy's next turn
                else:
                    return 0.0, v
                hh = torpedo_salvo_hits(lft, target, gs, from_xy)
                # phase_weight includes LATER_TURN_WEIGHT from the next turn on
                v += phase_weight(k2) * added_vp(target, gs, committed.get(target.id, 0.0),
                                                 hh, shields=False)
                return LATER_TURN_WEIGHT, v
            outs_n = [outcome(p) for p in normal]
            outs_d = [outcome(p) for p in dodge]
            wts = [getattr(p, "weight", 1.0) for p in normal]
            wsum = sum(wts) or 1.0
            mean_v = sum(w * v for w, (_h, v) in zip(wts, outs_n)) / wsum
            mean_p = sum(w * hh for w, (hh, _v) in zip(wts, outs_n)) / wsum
            # A dodge is any move that escapes this turn's hit; the enemy takes the
            # one worst for us (a later-turn catch still counts, discounted)
            miss_n = [(v, hh) for hh, v in outs_n if hh < 1.0]
            miss_d = [(v, hh) for hh, v in outs_d if hh < 1.0]
            if miss_n:
                dv, dp = min(miss_n)
            elif miss_d:
                mv_, mp_ = min(miss_d)
                dv = p_pass * mv_ + (1 - p_pass) * mean_v
                dp = p_pass * mp_ + (1 - p_pass) * mean_p
            else:
                dv, dp = mean_v, 1.0
            value = (1 - DODGE_WEIGHT) * mean_v + DODGE_WEIGHT * dv + base_v
            p_h = (1 - DODGE_WEIGHT) * mean_p + DODGE_WEIGHT * dp
            at_t = attack_survival(target, gs)    # Miasma / blast contact
            value *= torpedo_path_survival(ship.x, ship.y, p2[0], p2[1], gs) * at_t
            p_h *= torpedo_path_survival(ship.x, ship.y, p2[0], p2[1], gs) * at_t
            if best is None or value > best["value"] + 1e-9:
                best = {"heading": h, "value": value, "p_hit": p_h, "lost": lost,
                        "hits": torpedo_salvo_hits(strength, target, gs, from_xy)}
        if best is None or best["p_hit"] <= 0:
            return None
        return best

    def _intercept(self, ship: Ship, weapon: Dict, target: Ship):
        """(heading, distance) to where a straight torpedo meets `target`."""
        torp_speed = weapon.get("torpedo_speed", TORPEDO_SPEED_DEFAULT) or TORPEDO_SPEED_DEFAULT
        tvx = target.effective_speed * math.cos(math.radians(target.heading))
        tvy = target.effective_speed * math.sin(math.radians(target.heading))
        aim_x, aim_y = target.x, target.y
        for _ in range(4):
            dist = math.hypot(aim_x - ship.x, aim_y - ship.y)
            t = dist / torp_speed
            aim_x = target.x + tvx * t
            aim_y = target.y + tvy * t
        return (math.degrees(math.atan2(aim_y - ship.y, aim_x - ship.x)) % 360,
                math.hypot(aim_x - ship.x, aim_y - ship.y))

    def _best_torp_target(self, ship: Ship, weapon: Dict,
                          enemies: List[Ship]) -> Optional[Ship]:
        """
        Pick the enemy that the torpedo is most likely to hit.
        Checks both current position and predicted position; prefers targets
        whose predicted position is still in arc and within torpedo range.
        """
        torp_range = weapon.get("torpedo_speed", TORPEDO_SPEED_DEFAULT) * 3  # rough 3-turn intercept range
        candidates = []
        for e in enemies:
            # Check current position in arc
            current_in_arc = check_weapon_in_arc(ship, weapon, e.x, e.y)
            # Check predicted position in arc
            px, py = self._predict_ship_pos(e)
            predicted_in_arc = check_weapon_in_arc(ship, weapon, px, py)
            if not (current_in_arc or predicted_in_arc):
                continue
            # Prefer targets within intercept range
            dist = math.sqrt((ship.x - e.x) ** 2 + (ship.y - e.y) ** 2)
            if dist <= torp_range:
                candidates.append(e)
        if candidates and self.difficulty != "easy":
            # Owner: focus by expected VP; easy targets (low Armour / turrets /
            # shields, damaged ships) score most. Counts what the guns have done
            # (ships' actual state) and what this phase's ordnance is planned to do
            from .ai_hazards import added_vp, torpedo_salvo_hits, travel_discount
            committed = getattr(self, "_ord_committed", {})
            speed = weapon.get("torpedo_speed", TORPEDO_SPEED_DEFAULT) or TORPEDO_SPEED_DEFAULT
            strength = weapon.get("strength") or 0

            from .ai_hazards import best_route

            def split_bonus(e, phase, hits):
                """Owner: co-ordinate missiles with bombers reaching `e` in the
                same phase; its turrets can't shoot down both (s.28)."""
                from .ai_hazards import turret_split_gain
                due = [d for d in self._craft_due(e) if d[0] == phase]
                if not due:
                    return 0.0
                f = sum(d[1] for d in due)
                b = sum(d[2] for d in due)
                gain = turret_split_gain(e, self.gs, strength, f, b, from_xy=(ship.x, ship.y))
                return added_vp(e, self.gs, committed.get(e.id, 0.0) + hits, gain,
                                shields=False) if gain else 0.0

            def phase_of(e):
                return 0 if ship.distance_to(e) <= speed + e.base_radius else 1

            def score(e):
                if not self._torpedo_turns(ship, weapon):
                    plan = self._torp_lead_plan(ship, weapon, e)
                    if plan is not None:
                        # Within this turn and the enemy's: value from where the
                        # target can move (owner: lead it; dodges counted)
                        hits = plan["p_hit"] * plan["hits"]
                        return plan["value"] + split_bonus(e, phase_of(e), hits), hits
                else:
                    plan = self._approach_for_launch(ship, weapon, e)
                    if plan is not None:
                        # Turning salvo: best approach, weaker facings included
                        return (plan["value"] + split_bonus(e, plan["phase"], plan["hits"]),
                                plan["hits"])
                hits = torpedo_salvo_hits(strength, e, self.gs, (ship.x, ship.y))
                # Planets / asteroid fields on the way destroy the salvo; blast
                # markers and dust clouds on a 6 (owner: hazards on the path)
                # Salvos that can turn may go round obstacles within 45 degrees:
                # Tau missiles (weapon "guided") always; Leadership-guided torpedoes
                # (bought type) at the launcher's Ld odds; standard ones run straight
                straight = best_route(ship.x, ship.y, e.x, e.y, self.gs, "torpedo",
                                      speed, max_turn=0, target=e)[1]
                if weapon.get("torpedo_type") == "guided":
                    surv = best_route(ship.x, ship.y, e.x, e.y, self.gs, "torpedo", 40.0,
                                      max_turn=45.0, target=e)[1]
                elif "guided" in ship_torpedo_types(ship):
                    from .ai_hazards import p_sum_at_most
                    p_ld = p_sum_at_most(2, min(10, ship.leadership or 8))
                    turned = best_route(ship.x, ship.y, e.x, e.y, self.gs, "torpedo",
                                        speed, max_turn=45.0, target=e)[1]
                    surv = p_ld * turned + (1 - p_ld) * straight
                else:
                    surv = straight
                # Owner: friendly fire is negative VP. The best lane (_torp_lane)
                # counts every ship the salvo contacts on the way (s.15: it attacks
                # friend or foe and carries on, weakened by its hits): the target
                # takes what is left, and our ships hit cost their damage's VP
                friendly = 0.0
                lane = self._torp_lane(ship, weapon, e, *self._intercept(ship, weapon, e))
                if lane[2] > 0:
                    hits, friendly = min(hits, lane[2]), lane[3]
                hits *= surv
                px, py = self._predict_ship_pos(e)
                both = (check_weapon_in_arc(ship, weapon, e.x, e.y)
                        and check_weapon_in_arc(ship, weapon, px, py))
                return ((added_vp(e, self.gs, committed.get(e.id, 0.0), hits, shields=False)
                         * (1.0 if both else 0.6) - friendly * surv)
                        * travel_discount(ship.distance_to(e), speed), hits)
            best = max(candidates, key=lambda e: score(e)[0])
            if score(best)[0] < 0:
                return None                     # friendly fire would cost more than it gains
            committed[best.id] = committed.get(best.id, 0.0) + score(best)[1]
            self._ord_committed = committed
            return best
        if candidates:
            return self._nearest_ship(ship, candidates)
        # Fallback: nearest enemy in current arc
        in_arc = [e for e in enemies
                  if check_weapon_in_arc(ship, weapon, e.x, e.y)]
        return self._nearest_ship(ship, in_arc) if in_arc else None

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _live_enemies(self) -> List[Ship]:
        return [s for s in self.gs.get_ships()
                if s.player != self.player
                and not s.is_destroyed and not s.is_disengaged]

    def _nearest_enemy(self, ship: Ship) -> Optional[Ship]:
        return self._nearest_ship(ship, self._live_enemies())

    def _nearest_ship(self, ref: Ship, ships: List[Ship]) -> Optional[Ship]:
        if not ships:
            return None
        return min(ships,
                   key=lambda s: math.sqrt((s.x - ref.x)**2 + (s.y - ref.y)**2))

    def _nearest_enemy_to(self, x: float, y: float) -> Optional[Ship]:
        enemies = self._live_enemies()
        if not enemies:
            return None
        return min(enemies,
                   key=lambda s: math.sqrt((s.x - x)**2 + (s.y - y)**2))
