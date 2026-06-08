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
        min_spd, max_spd = get_effective_speed(ship, order, aaf_bonus)
        max_t = get_max_turns(order, ship)

        dx = enemy.x - ship.x
        dy = enemy.y - ship.y
        desired = math.degrees(math.atan2(dy, dx)) % 360
        delta = (desired - ship.heading + 180) % 360 - 180

        cmds: List[MoveCommand] = []
        if max_t > 0 and abs(delta) > 1:
            amount = min(ship.turn_angle, abs(delta))
            cmds.append(MoveCommand("turn_left" if delta < 0 else "turn_right", amount))

        dist = max(min_spd, int(max_spd * 0.85))
        cmds.append(MoveCommand("forward", dist))
        return cmds

    def _forward_commands(self, ship: Ship, order: str, aaf_bonus: int,
                          fraction: float = 1.0) -> List[MoveCommand]:
        min_spd, max_spd = get_effective_speed(ship, order, aaf_bonus)
        dist = max(min_spd, int(max_spd * fraction))
        return [MoveCommand("forward", dist)]

    def _choose_special_order(self, ship: Ship) -> Optional[str]:
        """Pick the most tactically useful special order for this ship."""
        gs = self.gs

        # Brace if enemy ordnance within 30cm
        for o_dict in gs.ordnance:
            marker = OrdnanceMarker.from_dict(o_dict)
            if marker.owner_player == self.player:
                continue
            if math.sqrt((ship.x - marker.x)**2 + (ship.y - marker.y)**2) < 30:
                return SpecialOrder.BRACE_FOR_IMPACT.value

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
            from .game_context import GameContext
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
                target = self._nearest_ship(ship, enemies)
                if target and check_weapon_in_arc(ship, weapon, target.x, target.y):
                    launch_torpedoes(ship, weapon, gs)
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
