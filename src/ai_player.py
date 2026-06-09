"""Heuristic AI player for singleplayer mode.

Drives movement, shooting, and ordnance phases using pure-logic APIs,
with no Tkinter dialogs. Caller must set dice.mode = "auto" before use.
"""
import math
import random
from typing import List, Optional, Dict

from .models import Ship, OrdnanceMarker, SpecialOrder, OrdnanceType
from .game_state import GameState
from .turn_controller import TurnController
from .dice import DiceRoller
from .movement import (
    MoveCommand, validate_movement, execute_movement,
    get_effective_speed, get_max_turns,
)
from .combat import (
    check_weapon_in_arc, check_weapon_in_range, check_los_clear,
    resolve_batteries, resolve_lances, apply_damage,
)
from .ordnance import launch_torpedoes, launch_attack_craft, move_ordnance


def ai_should_brace(gs: GameState, target: Ship,
                    incoming_hits: int, attacker: Ship = None) -> bool:
    """
    Decide whether an AI-controlled ship should attempt Brace For Impact.

    incoming_hits: already-rolled hits (post-armor) from the current volley.
    Brace if expected total hull damage (current volley + follow-on fire
    from other unfired enemies in arc/range/LoS) >= hits_remaining / 4.
    """
    shields = target.shields_remaining
    current_hull = max(0, incoming_hits - shields)
    shields_left = max(0, shields - incoming_hits)

    future_hull = 0.0
    phenomena = gs.get_phenomena()
    blast_markers = gs.get_blast_markers()

    for enemy in gs.get_ships():
        if enemy.player == target.player:
            continue
        if enemy.is_destroyed or enemy.is_disengaged:
            continue
        # Include the current attacker (may have more weapons); skip others
        # that have already fully fired this phase.
        if enemy.has_fired and (attacker is None or enemy.id != attacker.id):
            continue
        for weapon in enemy.weapons:
            wtype = weapon.get("weapon_type", "")
            if wtype not in ("battery", "lance"):
                continue
            if not check_weapon_in_arc(enemy, weapon, target.x, target.y):
                continue
            if not check_weapon_in_range(enemy, weapon, target.x, target.y):
                continue
            los = check_los_clear(enemy, target, phenomena, blast_markers)
            if not los.get("clear", True):
                continue
            strength = weapon.get("strength", 1)
            arc = target.get_arc_for_bearing(enemy.bearing_to(target.x, target.y))
            armor_str = target.armor_prow if arc.value == "front" else target.armor_side
            try:
                armor_num = int(armor_str.rstrip("+"))
            except (ValueError, AttributeError):
                armor_num = 5
            hit_prob = max(0.0, (7 - armor_num) / 6.0)
            expected = strength * hit_prob
            net = max(0.0, expected - shields_left)
            future_hull += net
            shields_left = max(0.0, shields_left - expected)

    return (current_hull + future_hull) >= target.hits_remaining / 4.0


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

        for ship in my_ships:
            self._move_ship(ship)

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
                        from .movement import resolve_aaf_speed
                        aaf_bonus = resolve_aaf_speed(ship, self.dice)
                else:
                    gs.add_log(f"[AI] {ship.name}: {chosen} failed")
                    ship = gs.get_ship_by_id(ship.id)
                    order = ship.special_order or ""
        else:
            order = ship.special_order or ""

        enemy = self._nearest_enemy(ship)
        commands = (self._plan_move_toward(ship, enemy, order, aaf_bonus)
                    if enemy else
                    self._forward_commands(ship, order, aaf_bonus, fraction=0.6))

        executed = self._try_execute(ship, commands, order, aaf_bonus)
        if executed:
            ship = gs.get_ship_by_id(ship.id)
            gs.add_log(f"[AI] {ship.name} moved to ({ship.x:.0f},{ship.y:.0f})")

        tc.mark_ship_moved(ship.id)

    def _try_execute(self, ship: Ship, commands: List[MoveCommand],
                     order: str, aaf_bonus: int) -> bool:
        """Attempt to execute commands; fall back to simpler moves if invalid."""
        gs = self.gs
        kwargs = dict(
            special_order=order, aaf_bonus=aaf_bonus,
            blast_markers=gs.get_blast_markers(),
            table_width=gs.table_width, table_height=gs.table_height,
        )

        r = validate_movement(ship, commands, **kwargs)
        if r.valid:
            execute_movement(ship, r, gs)
            return True

        # Fallback: straight forward at half speed
        min_spd, max_spd = get_effective_speed(ship, order, aaf_bonus)
        dist = max(min_spd, max_spd // 2)
        r2 = validate_movement(ship, [MoveCommand("forward", dist)], **kwargs)
        if r2.valid:
            execute_movement(ship, r2, gs)
            return True

        # Last resort: minimum speed
        if min_spd > 0:
            r3 = validate_movement(ship, [MoveCommand("forward", min_spd)], **kwargs)
            if r3.valid:
                execute_movement(ship, r3, gs)
                return True

        return False

    def _plan_move_toward(self, ship: Ship, enemy: Ship,
                          order: str, aaf_bonus: int) -> List[MoveCommand]:
        """Choose movement commands that maximise in-arc weapon coverage against enemy."""
        from .movement import MIN_TURN_DISTANCE
        min_spd, max_spd = get_effective_speed(ship, order, aaf_bonus)
        max_t  = get_max_turns(order, ship)
        min_td = MIN_TURN_DISTANCE.get(ship.ship_type, 0)
        ta = ship.turn_angle

        turn_candidates = [0.0]
        if max_t > 0:
            turn_candidates += [-ta, -ta * 0.5, ta * 0.5, ta]

        best_cmds: Optional[List[MoveCommand]] = None
        best_score = -1.0

        for turn_deg in turn_candidates:
            for frac in (0.6, 0.8, 1.0):
                dist = max(min_spd, int(max_spd * frac))
                if dist < 1:
                    continue
                if abs(turn_deg) > 0.5 and min_td > 0 and dist <= min_td:
                    continue  # not enough distance to turn
                fx, fy, fh = self._simulate_final_pos(ship, turn_deg, dist)
                score = (self._arc_score(ship, fx, fy, fh, enemy)
                         - self._position_penalty(fx, fy))
                if score > best_score:
                    best_score = score
                    cmds: List[MoveCommand] = []
                    if abs(turn_deg) > 0.5:
                        if min_td > 0:
                            cmds.append(MoveCommand("forward", min_td))
                        cmds.append(MoveCommand(
                            "turn_left" if turn_deg > 0 else "turn_right",
                            abs(turn_deg)))
                        rem = dist - (min_td if 0 < min_td < dist else 0)
                        if rem > 0:
                            cmds.append(MoveCommand("forward", rem))
                    else:
                        cmds.append(MoveCommand("forward", dist))
                    best_cmds = cmds

        return best_cmds or [MoveCommand("forward", max(min_spd, max_spd // 2))]

    def _simulate_final_pos(self, ship: Ship, turn_deg: float,
                            total_dist: float):
        """Return (x, y, heading) after applying turn_deg then moving total_dist."""
        from .movement import MIN_TURN_DISTANCE
        min_td = MIN_TURN_DISTANCE.get(ship.ship_type, 0)
        r = math.radians

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
                   final_heading: float, target: Ship) -> float:
        """Score total in-arc weapon strength from a hypothetical end position."""
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
            if weapon.get("weapon_type") not in ("battery", "lance", "nova_cannon"):
                continue
            arcs = weapon.get("arcs", [])
            if arcs and arc not in arcs:
                continue
            strength = weapon.get("strength", 1)
            w_range  = weapon.get("range_cm", 0)
            if w_range == 0 or dist <= w_range:
                score += strength
            else:
                score += strength * (w_range / dist) * 0.5  # closing bonus
        return score

    def _position_penalty(self, final_x: float, final_y: float) -> float:
        """Penalty for landing in dangerous terrain or a torpedo's predicted path."""
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

    def _forward_commands(self, ship: Ship, order: str, aaf_bonus: int,
                          fraction: float = 1.0) -> List[MoveCommand]:
        min_spd, max_spd = get_effective_speed(ship, order, aaf_bonus)
        dist = max(min_spd, int(max_spd * fraction))
        return [MoveCommand("forward", dist)]

    def _choose_special_order(self, ship: Ship) -> Optional[str]:
        """Pick the most tactically useful special order for this ship."""
        gs = self.gs

        # Burn Retros if ship is about to enter dangerous terrain at full speed
        _, max_spd = get_effective_speed(ship, "", 0)
        rad = math.radians(ship.heading)
        projected_x = ship.x + max_spd * math.cos(rad)
        projected_y = ship.y + max_spd * math.sin(rad)
        if self._position_penalty(projected_x, projected_y) >= 30.0:
            return SpecialOrder.BURN_RETROS.value

        # Lock On if an enemy is in a battery or lance arc+range
        enemies = self._live_enemies()
        for enemy in enemies:
            for weapon in ship.weapons:
                if weapon.get("weapon_type") not in ("battery", "lance"):
                    continue
                if (check_weapon_in_arc(ship, weapon, enemy.x, enemy.y) and
                        check_weapon_in_range(ship, weapon, enemy.x, enemy.y)):
                    if self.difficulty == "hard":
                        return SpecialOrder.LOCK_ON.value
                    return SpecialOrder.LOCK_ON.value

        # Reload if ordnance spent
        has_torps = any(w.get("weapon_type") == "torpedo" for w in ship.weapons)
        has_bays  = any(w.get("weapon_type") == "launch_bay" for w in ship.weapons)
        if ((has_torps and not ship.ordnance_loaded_torps) or
                (has_bays and not ship.ordnance_loaded_craft)):
            return SpecialOrder.RELOAD_ORDNANCE.value

        return None

    # ── Shooting phase ───────────────────────────────────────────────────────

    def run_shooting_phase(self):
        gs = self.gs
        tc = self.tc
        for ship in gs.player_ships(self.player):
            if ship.is_destroyed or ship.is_disengaged or ship.has_fired:
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

        for weapon in ship.weapons:
            wtype = weapon.get("weapon_type", "")
            if wtype in ("torpedo", "launch_bay", "mine_launcher"):
                continue

            if wtype == "nova_cannon":
                self._fire_nova_cannon(ship, enemies)
                continue

            target = self._pick_target(ship, weapon, enemies)
            if not target:
                continue

            braced = target.special_order == SpecialOrder.BRACE_FOR_IMPACT.value

            if wtype == "battery":
                sr = resolve_batteries(ship, target, weapon, self.dice,
                                       blast_markers, lock_on=lock_on,
                                       phenomena=phenomena, all_ships=all_ships)
                gs.add_log(f"[AI] {ship.name} → {target.name}: "
                           f"{weapon['name']} {sr.hits} hit(s)")
                if sr.hits > 0:
                    dmg = apply_damage(target, sr.hits, self.dice, gs,
                                       target_braced=braced)
                    self._log_damage(target, dmg)

            elif wtype == "lance":
                sr = resolve_lances(ship, target, weapon, self.dice,
                                    lock_on=lock_on)
                gs.add_log(f"[AI] {ship.name} → {target.name}: "
                           f"{weapon['name']} {sr.hits} hit(s)")
                if sr.hits > 0:
                    dmg = apply_damage(target, sr.hits, self.dice, gs,
                                       target_braced=braced)
                    self._log_damage(target, dmg)

    def _fire_nova_cannon(self, ship: Ship, enemies: List[Ship]):
        from .combat import resolve_nova_cannon
        gs = self.gs
        # Pick centroid of enemy cluster for nova shot
        if not enemies:
            return
        target = min(enemies,
                     key=lambda s: math.sqrt((s.x - ship.x)**2 + (s.y - ship.y)**2))
        dist = math.sqrt((target.x - ship.x)**2 + (target.y - ship.y)**2)
        if dist < 30 or dist > 150:
            return
        nc = resolve_nova_cannon(ship, target.x, target.y, self.dice, gs)
        if "error" in nc:
            return
        gs.add_log(f"[AI] {ship.name} nova cannon at ({target.x:.0f},{target.y:.0f})")
        for sid, hd in nc.get("ship_hits", {}).items():
            t = gs.get_ship_by_id(sid)
            if t:
                dmg = apply_damage(t, hd["hits"], self.dice, gs,
                                   ignores_shields=True)
                self._log_damage(t, dmg)

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
                                  self.gs.get_blast_markers())
            if not los.get("clear", True):
                continue
            valid.append(e)
        if not valid:
            return None

        if self.difficulty == "easy":
            return random.choice(valid)
        elif self.difficulty == "normal":
            return min(valid, key=lambda s: s.hits_remaining / max(1, s.hits_max))
        else:  # hard: focus crippled, then lowest HP
            crippled = [s for s in valid if s.is_crippled]
            pool = crippled if crippled else valid
            return min(pool, key=lambda s: s.hits_remaining)

    def _log_damage(self, target: Ship, dmg: Dict):
        gs = self.gs
        if dmg.get("crits"):
            for c in dmg["crits"]:
                gs.add_log(f"[AI]   CRIT: {c}")
        if dmg.get("crippled"):
            gs.add_log(f"[AI]   {target.name} CRIPPLED")
        if dmg.get("destroyed"):
            gs.add_log(f"[AI]   {target.name} DESTROYED")
        # destruction check is called by game_panel after each phase

    # ── Ordnance phase ───────────────────────────────────────────────────────

    def run_ordnance_phase(self):
        gs = self.gs

        # Move existing ordnance owned by this player
        for o_dict in list(gs.ordnance):
            marker = OrdnanceMarker.from_dict(o_dict)
            if marker.owner_player != self.player or marker.moved_this_phase:
                continue
            if marker.can_turn:
                target = self._nearest_enemy_to(marker.x, marker.y)
                self._steer_guided_missile(marker, target)
            else:
                move_ordnance(marker, gs)

        # Launch new ordnance
        for ship in gs.player_ships(self.player):
            if ship.is_destroyed or ship.is_disengaged:
                continue
            self._launch_ship_ordnance(ship)

    def _steer_guided_missile(self, marker: OrdnanceMarker,
                              target: Optional[Ship]) -> None:
        gs = self.gs
        if target is not None:
            dx = target.x - marker.x
            dy = target.y - marker.y
            desired = math.degrees(math.atan2(dy, dx)) % 360
            diff = (desired - marker.heading + 180) % 360 - 180
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

        for weapon in ship.weapons:
            wtype = weapon.get("weapon_type", "")

            if wtype == "torpedo" and ship.ordnance_loaded_torps:
                # Pick target whose predicted next position is best covered
                target = self._best_torp_target(ship, weapon, enemies)
                if target:
                    aim = self._torpedo_aim_heading(ship, weapon, target)
                    launch_torpedoes(ship, weapon, gs, heading=aim)
                    ship = gs.get_ship_by_id(ship.id)

            elif wtype == "launch_bay" and ship.ordnance_loaded_craft:
                craft_types = weapon.get("craft_types", [])
                if not craft_types:
                    continue
                enemy_ord = [OrdnanceMarker.from_dict(o) for o in gs.ordnance
                             if o["owner_player"] != self.player]
                if enemy_ord and self.difficulty != "easy":
                    preferred = next(
                        (ct for ct in craft_types if ct in ("fury_fighter", "barracuda")),
                        craft_types[0])
                else:
                    preferred = next(
                        (ct for ct in craft_types if ct in ("starhawk_bomber", "manta")),
                        craft_types[0])
                count = weapon.get("strength", 1)
                launch_attack_craft(ship, weapon, preferred, count, gs)
                ship = gs.get_ship_by_id(ship.id)

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
        torp_speed = weapon.get("torpedo_speed", 30) or 30
        tvx = target.effective_speed * math.cos(math.radians(target.heading))
        tvy = target.effective_speed * math.sin(math.radians(target.heading))
        aim_x, aim_y = target.x, target.y
        for _ in range(4):  # converge the intercept point
            dist = math.hypot(aim_x - ship.x, aim_y - ship.y)
            t = dist / torp_speed
            aim_x = target.x + tvx * t
            aim_y = target.y + tvy * t
        desired = math.degrees(math.atan2(aim_y - ship.y, aim_x - ship.x)) % 360
        diff = (desired - ship.heading + 180) % 360 - 180
        diff = max(-45.0, min(45.0, diff))
        return (ship.heading + diff) % 360

    def _best_torp_target(self, ship: Ship, weapon: Dict,
                          enemies: List[Ship]) -> Optional[Ship]:
        """
        Pick the enemy that the torpedo is most likely to hit.
        Checks both current position and predicted position; prefers targets
        whose predicted position is still in arc and within torpedo range.
        """
        torp_range = weapon.get("torpedo_speed", 30) * 3  # rough 3-turn intercept range
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
