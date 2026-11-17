"""Celestial effects (core s.40): Fighting Sunward, Solar Flares and Radiation
Bursts, each an optional rule (Advanced settings, `GameState.rule_*`).

Readings (to confirm with the owner): with a toggle on the battle counts as
taking place where the effect applies (Fighting Sunward: "from the Flare
Region to the Inner Biosphere"); the celestial phenomena table isn't rolled
by the engine, so `GameState.solar_flare_dice` / `radiation_burst_dice` (1
each by default) stand for the flares and bursts it would generate. Demiurg
commerce vessels are immune to both (Xenos, absorber fields)."""
import math
from typing import List

SUN_ANGLE = {"north": 90.0, "south": 270.0, "east": 0.0, "west": 180.0,
             "top": 90.0, "bottom": 270.0, "right": 0.0, "left": 180.0}


def is_sunward(shooter, target, edge: str) -> bool:
    """Fighting Sunward: with the bearing compass over the firing ship and its
    arrows parallel to the sunward edge, the target lies in the abeam arc on
    the sunward side (within 45 degrees of the direction of that edge)."""
    sun = SUN_ANGLE.get(edge or "north", 90.0)
    bearing = math.degrees(math.atan2(target.y - shooter.y, target.x - shooter.x))
    diff = (bearing - sun + 180.0) % 360.0 - 180.0
    return abs(diff) <= 45.0


def _immune(s) -> bool:
    """Demiurg absorber fields; Necron reactive hulls are immune to the Ld and
    damage penalties of solar flares and radiation (Xenos p.40)."""
    return "demiurg_commerce" in s.special_rules or "necron" in s.special_rules


def radiation_active(gs) -> bool:
    return bool(getattr(gs, "radiation_level", 0)) and \
        getattr(gs, "radiation_turn", None) == [gs.turn_number, gs.active_player]


def flare_now(gs) -> bool:
    return getattr(gs, "solar_flare_turn", None) == [gs.turn_number, gs.active_player]


def start_of_turn(gs, dice) -> List[str]:
    """At the start of each turn: solar flares (a 6 on any of the dice, once
    per game) and radiation bursts (a 5+ on any, at most one a turn)."""
    logs = []
    if getattr(gs, "rule_solar_flares", False) and not getattr(gs, "solar_flare_done", False):
        n = max(1, getattr(gs, "solar_flare_dice", 1))
        rolls = dice.roll_d6(n, "Solar flare (a 6 sets it off)")
        if any(r == 6 for r in rolls):
            logs += _solar_flare(gs, dice)
    if getattr(gs, "rule_radiation_bursts", False):
        n = max(1, getattr(gs, "radiation_burst_dice", 1))
        rolls = dice.roll_d6(n, "Radiation burst (5+)")
        if any(r >= 5 for r in rolls):
            level = dice.roll_d6(1, "Radiation burst interference level")[0]
            deltas = {}
            for s in gs.ships:
                ship = gs.get_ship_by_id(s["id"])
                if ship.is_destroyed or ship.is_disengaged or _immune(ship):
                    continue
                cut = min(level, s.get("leadership", 0) or 0)
                s["leadership"] = (s.get("leadership", 0) or 0) - cut
                deltas[s["id"]] = cut
            gs.radiation_level = level
            gs.radiation_turn = [gs.turn_number, gs.active_player]
            gs.radiation_deltas = deltas
            logs.append(f"RADIATION BURST: every ship -{level} Ld this turn; fleet commanders' "
                        f"re-rolls only for their own ship or squadron")
    for line in logs:
        gs.add_log(line)
    return logs


def _solar_flare(gs, dice) -> List[str]:
    from .combat import _place_shield_impacts, apply_damage
    from .geometry import current_shields
    gs.solar_flare_done = True
    gs.solar_flare_turn = [gs.turn_number, gs.active_player]
    logs = ["SOLAR FLARE! A blast marker on every ship, sunward side"]
    sun = math.radians(SUN_ANGLE.get(gs.sunward_edge or "north", 90.0))
    for s0 in gs.get_ships():
        if s0.is_destroyed or s0.is_disengaged or _immune(s0):
            continue
        s = gs.get_ship_by_id(s0.id)
        unshielded = current_shields(s, gs.get_blast_markers()) <= 0
        _place_shield_impacts(s, 1, gs, origin=(s.x + 500 * math.cos(sun),
                                                  s.y + 500 * math.sin(sun)))
        if unshielded:
            s = gs.get_ship_by_id(s0.id)
            apply_damage(s, 1, dice, gs, ignores_shields=True, crit_on=4,
                         rolled_to_hit=False)
            logs.append(f"  {s.name} has no shields: one hit (critical on 4+)")
    gone = []
    for o in list(gs.ordnance):
        if dice.roll_d6(1, f"Solar flare vs {o['ordnance_type']} (4+ removed)")[0] >= 4:
            gone.append(o["id"])
    if gone:
        gs.ordnance = [o for o in gs.ordnance if o["id"] not in gone]
        logs.append(f"  {len(gone)} ordnance marker(s) burnt out")
    return logs


def end_of_turn(gs, player: int) -> None:
    """The radiation burst lasts for the turn: give back the Ld it took."""
    if getattr(gs, "radiation_turn", None) != [gs.turn_number, player]:
        return
    for s in gs.ships:
        d = (getattr(gs, "radiation_deltas", {}) or {}).get(s["id"])
        if d:
            s["leadership"] = (s.get("leadership", 0) or 0) + d
    gs.radiation_level = 0
    gs.radiation_deltas = {}
