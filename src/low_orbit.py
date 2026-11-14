"""Low orbit (core s.39, High Orbit / Fighting in Low Orbit; sign-off answer 1).

The low orbit table is a separate area of the engine's coordinate space, far
from the main table so that no weapon, ordnance or effect reaches between
them: x 0..LENGTH, y Y0..Y0+WIDTH. Its top long edge (y = Y0 + WIDTH) is the
planet edge; ships enter touching the opposite edge (y = Y0).

Rules:
- Entering: a ship within the planet's gravity well at the start of its turn
  may enter low orbit; it is removed and placed on the low orbit table,
  touching the edge furthest from the planet (Remastered p.116; XR is silent:
  proposed in the sign-off answers, for the owner to confirm).
- In low orbit: no minimum move; capital ships need no distance before
  turning; gunnery one column right; lances and nova cannons fire only on a
  4+; no torpedoes or mines (barrage bombs may be launched).
- Falling: at the start of each player's turn every ship within 45cm of the
  planet edge falls straight towards it (small 5cm, medium 8cm, large 10cm);
  off the planet edge that way, it is destroyed.
- Leaving: escorts and transports moving off the planet edge voluntarily have
  landed (they count as disengaging); capital ships can't land. Off any other
  edge a ship returns to high orbit, placed touching the outer edge of the
  planet template. Not in the turn it entered. Ordnance launched in low orbit
  can't leave it.
"""
from __future__ import annotations

import math
from typing import Optional

Y0 = 10000.0           # far from any main table
LENGTH = 120.0         # 90-135cm long (judgement: 120)
WIDTH = 60.0           # 45-60cm wide (judgement: 60)
GRIP = 45.0            # within 45cm of the planet edge ships fall
FALL = {"planet_small": 5.0, "planet_medium": 8.0, "planet_large": 10.0}
FLAG = "in_low_orbit"


def planet_edge_y() -> float:
    return Y0 + WIDTH


def in_region(x: float, y: float, pad: float = 0.0) -> bool:
    return -pad <= x <= LENGTH + pad and Y0 - pad <= y <= Y0 + WIDTH + pad


def is_low(y: float) -> bool:
    """A point in (or just off) the low orbit area."""
    return y >= Y0 - 500.0


def in_low_orbit(ship) -> bool:
    return FLAG in (getattr(ship, "special_rules", None) or [])


def bounds_for(y: float, table_width: float, table_height: float):
    """(x0, y0, x1, y1) of the table a point is on."""
    if is_low(y):
        return 0.0, Y0, LENGTH, Y0 + WIDTH
    return 0.0, 0.0, table_width, table_height


def off_bounds(ship, table_width: float, table_height: float) -> bool:
    """The ship's base is off the edge of the table it is on."""
    x0, y0, x1, y1 = bounds_for(ship.y, table_width, table_height)
    r = ship.base_radius
    return ship.x - r < x0 or ship.x + r > x1 or ship.y - r < y0 or ship.y + r > y1


def marker_off_bounds(x: float, y: float, table_width: float, table_height: float,
                      pad: float = 5.0) -> bool:
    x0, y0, x1, y1 = bounds_for(y, table_width, table_height)
    if is_low(y):
        pad = 0.0                    # ordnance can't leave low orbit at all
    return x < x0 - pad or x > x1 + pad or y < y0 - pad or y > y1 + pad


# --- the planet ---------------------------------------------------------------------

def planet(gs):
    """The planet the scenario attacks (its low orbit), or None."""
    pid = (gs.scenario_state or {}).get("low_orbit_planet")
    if not pid:
        return None
    return next((p for p in gs.get_phenomena() if p.id == pid), None)


def active(gs) -> bool:
    return planet(gs) is not None


def in_gravity_well(gs, ship) -> bool:
    pl = planet(gs)
    if pl is None or in_low_orbit(ship):
        return False
    return math.hypot(ship.x - pl.x, ship.y - pl.y) <= pl.gravity_well_radius


def can_enter(gs, ship) -> bool:
    """At the start of its turn a ship in the gravity well may enter (not a
    defence that can't move, not one that left low orbit this turn)."""
    return (active(gs) and not ship.is_destroyed and not ship.is_disengaged
            and "immobile" not in ship.special_rules and in_gravity_well(gs, ship)
            and ship.speed > 0)


def _angle_to_x(angle: float) -> float:
    """Where on the low orbit table a ship from a given side of the planet
    enters (judgement: the planet's circumference unrolled along the table)."""
    return 5.0 + (LENGTH - 10.0) * ((angle % 360.0) / 360.0)


def _x_to_angle(x: float) -> float:
    return 360.0 * max(0.0, min(1.0, (x - 5.0) / (LENGTH - 10.0)))


def _clear_spot(gs, ship, x: float, y: float, along: str = "x"):
    others = [s for s in gs.get_ships() if s.id != ship.id and not s.is_destroyed
              and not s.is_disengaged]
    for k in range(40):
        dx = ((-1) ** k) * 4.0 * ((k + 1) // 2)
        px = x + dx if along == "x" else x
        py = y if along == "x" else y + dx
        if all(math.hypot(px - o.x, py - o.y) >= o.base_radius + ship.base_radius
               for o in others):
            return px, py
    return x, y


def enter(gs, ship) -> None:
    """Move a ship from high orbit onto the low orbit table, touching the edge
    furthest from the planet, facing along the planet edge (reading: its
    heading's side, left or right; facing the planet would leave a 45-degree
    ship unable to climb away before it falls)."""
    pl = planet(gs)
    angle = math.degrees(math.atan2(ship.y - pl.y, ship.x - pl.x)) % 360.0
    x = max(ship.base_radius, min(LENGTH - ship.base_radius, _angle_to_x(angle)))
    x, y = _clear_spot(gs, ship, x, Y0 + ship.base_radius + 0.1)
    along = 0.0 if math.cos(math.radians(ship.heading)) >= 0 else 180.0
    ship.x, ship.y, ship.heading = x, y, along
    ship.special_rules = [r for r in ship.special_rules
                          if r != FLAG and not r.startswith("lo_entered:")] + \
        [FLAG, f"lo_entered:{gs.turn_number}"]
    gs.update_ship(ship)
    gs.add_log(f"{ship.name} enters low orbit")


def entered_this_turn(gs, ship) -> bool:
    return f"lo_entered:{gs.turn_number}" in ship.special_rules


def return_to_high_orbit(gs, ship) -> None:
    """Placed touching the outer edge of the planet template, on the side its
    low orbit position stands for, facing away from the planet (reading)."""
    pl = planet(gs)
    a = math.radians(_x_to_angle(ship.x))
    rr = pl.radius + ship.base_radius + 0.1
    ship.x, ship.y = pl.x + rr * math.cos(a), pl.y + rr * math.sin(a)
    ship.heading = math.degrees(a) % 360.0
    ship.special_rules = [r for r in ship.special_rules
                          if r != FLAG and not r.startswith("lo_entered:")]
    gs.update_ship(ship)
    gs.add_log(f"{ship.name} returns to high orbit")


def lands(ship) -> bool:
    """Escorts and transports may land (off the planet edge, voluntarily)."""
    return ship.ship_type == "escort" or any(r.startswith("transport:")
                                             for r in ship.special_rules)


def handle_move_end(gs, ship, dice=None) -> bool:
    """After a move ends off the low orbit table's edge. Returns True when it
    was handled (the caller skips the normal off-table rules)."""
    if not in_low_orbit(ship):
        return False
    r = ship.base_radius
    if not off_bounds(ship, gs.table_width, gs.table_height):
        return False
    if ship.y + r > planet_edge_y():
        if lands(ship):
            ship.status = "disengaged"
            ship.is_disengaged = True
            ship.special_rules = [x for x in ship.special_rules if x != FLAG] + ["landed"]
            gs.update_ship(ship)
            gs.add_log(f"{ship.name} lands on the planet (counts as disengaging)")
            from .scenarios import record_landing
            record_landing(gs, ship)
        else:
            # capital ships can't land: it stops at the planet edge (reading)
            ship.y = planet_edge_y() - r - 0.1
            gs.update_ship(ship)
            gs.add_log(f"{ship.name} can't land (capital ship): it stops at the planet edge")
        return True
    if entered_this_turn(gs, ship):
        # a ship may not enter and leave low orbit in the same turn: it stops
        # at the edge (reading)
        ship.x = max(r + 0.1, min(LENGTH - r - 0.1, ship.x))
        ship.y = max(Y0 + r + 0.1, ship.y)
        gs.update_ship(ship)
        gs.add_log(f"{ship.name} can't leave low orbit the turn it entered")
        return True
    return_to_high_orbit(gs, ship)
    return True


def falling(gs) -> None:
    """At the start of each player's turn every ship within 45cm of the planet
    edge falls straight towards it; off the edge it is totally destroyed."""
    pl = planet(gs)
    if pl is None:
        return
    d = FALL.get(pl.phenomenon_type, 8.0)
    edge = planet_edge_y()
    for s in gs.get_ships():
        if not in_low_orbit(s) or s.is_destroyed or s.is_disengaged:
            continue
        if edge - s.y > GRIP:
            continue
        s.y += d
        if s.y + s.base_radius > edge:
            s.status = "destroyed"
            s.hits_remaining = 0
            gs.add_log(f"{s.name} falls onto the planet and is destroyed")
        else:
            gs.add_log(f"{s.name} falls {d:g}cm towards the planet")
        gs.update_ship(s)


def distance_to_planet_edge(ship) -> float:
    return planet_edge_y() - ship.y


def gunnery_shift(attacker) -> int:
    """All gunnery weapons in low orbit suffer one column shift right."""
    return 1 if in_low_orbit(attacker) else 0


def needs_fire_roll(attacker) -> bool:
    """Lances and nova cannons in low orbit need a 4+ to fire."""
    return in_low_orbit(attacker)


def launch_forbidden(ship, kind: str = "torpedo") -> Optional[str]:
    """Torpedoes and mines may not be launched in low orbit (barrage bombs
    may, s.16)."""
    if in_low_orbit(ship) and kind in ("torpedo", "mine"):
        return "torpedoes and mines can't be launched in low orbit"
    return None


def board_offset(table_height: float) -> float:
    """Where the board draws the low orbit table: just above the main one."""
    return table_height + 8.0
