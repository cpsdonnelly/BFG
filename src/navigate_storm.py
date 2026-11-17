"""Navigate the Storm (XR p.98): a convoy runs for the exit point through warp
rifts the players place; attacking ships lost in a rift come back next to a
capital ship.

Diagram (180 x 120cm, transcribed edge-relative): the defender deploys in the
bottom-left quarter, 20cm in from the left edge (x 20-90, y 0-60); the
attacker in the top-right quarter, 10cm down from the top and short of the
exit point (x 90-160, y 60-110); the exit point is the strip along the right
edge beside the attacker's zone (x 160-180, y 60-110, reading: leaving off the
right edge between y 60 and 110).
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

RIFTS_EACH = 8
RIFT_GAP = 10.0             # at least 10cm from any other rift (edge to edge)
# Warp rifts are D3x5cm wide and D3x10cm long (s.39, sign-off answer 17);
# placed with the long side along the table (judgement)
RETURN_RANGE = 20.0         # a lost ship returns within 20cm of a capital ship
ATTACKER_TARGET_CAP = 8     # attacker: destroy 8 transport capacity ...
ATTACKER_VP_SHARE = 0.5     # ... and score 50% of the defender's points
DEFENDER_TARGET_CAP = 5     # defender: 5 capacity off via the exit point ...
DEFENDER_POINTS_SHARE = 0.25    # ... and 25% of its fleet (ignoring crippled ships)
CONVOY_CAPACITY = 10        # the defender must take 10 transport capacity
LOST = "lost_in_warp"
MATERIALISING = "materialising"
HALF_ARMAMENT = "half_armament"


def active(gs) -> bool:
    return getattr(gs, "scenario_mode", "") == "navigate_storm"


def zones(gs) -> Dict[str, Tuple[float, float, float, float]]:
    """(x_min, y_min, x_max, y_max) of the defender's / attacker's zones and
    the exit point, scaled to the table (the diagram is 180 x 120)."""
    w, h = gs.table_width, gs.table_height
    return {"defender": (20.0, 0.0, w / 2.0, h / 2.0),
            "attacker": (w / 2.0, h / 2.0, w - 20.0, h - 10.0),
            "exit": (w - 20.0, h / 2.0, w, h - 10.0)}


def exit_target(gs) -> Tuple[float, float]:
    x0, y0, x1, y1 = zones(gs)["exit"]
    return x1, (y0 + y1) / 2.0


def via_exit_point(gs, ship) -> bool:
    """A ship off the right edge beside the exit point (its centre between
    the strip's ends, reading)."""
    _x0, y0, _x1, y1 = zones(gs)["exit"]
    return ship.x + ship.base_radius > gs.table_width and y0 <= ship.y <= y1


# --- set-up: the warp rifts ----------------------------------------------------------

def _seg_dist(px, py, ax, ay, bx, by) -> float:
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / max(1e-9, dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def _in_rect(x, y, r, pad=0.0) -> bool:
    return r[0] - pad <= x <= r[2] + pad and r[1] - pad <= y <= r[3] + pad


def rift_spot(gs, player: int, attacker: int, w_cm: float = 10.0,
              h_cm: float = 10.0) -> Optional[Tuple[float, float]]:
    """Where a player places its next rift (judgement): the attacker on the
    convoy's way from the defender's zone to the exit point, the defender as
    far off that way as it can. Legal: at least 10cm from every other rift
    (reading: edge to edge); kept out of the deployment zones and the exit
    point (judgement, so both fleets can deploy and leave)."""
    zs = zones(gs)
    dz, ex = zs["defender"], exit_target(gs)
    ax, ay = (dz[0] + dz[2]) / 2.0, (dz[1] + dz[3]) / 2.0
    rifts = [p for p in gs.get_phenomena() if p.phenomenon_type == "warp_rift"]
    hw, hh = w_cm / 2.0, h_cm / 2.0
    best, best_v = None, None
    y = hh + 5.0
    while y <= gs.table_height - hh - 5.0:
        x = hw + 5.0
        while x <= gs.table_width - hw - 5.0:
            ok = not any(zs[k][0] - hw <= x <= zs[k][2] + hw and zs[k][1] - hh <= y <= zs[k][3] + hh
                         for k in zs)
            if ok:
                for r in rifts:
                    gap_x = abs(x - r.x) - (hw + r.width / 2.0)
                    gap_y = abs(y - r.y) - (hh + r.height / 2.0)
                    if max(gap_x, gap_y) < RIFT_GAP:
                        ok = False
                        break
            if ok:
                d = _seg_dist(x, y, ax, ay, ex[0], ex[1])
                v = -d if player == attacker else d
                if best_v is None or v > best_v + 1e-9:
                    best, best_v = (x, y), v
            x += 5.0
        y += 5.0
    return best


def setup(gs, dice=None) -> None:
    """Instead of the normal battlezone, the players place eight warp rifts
    each, the attacker first, and no other celestial phenomena (the ones on
    the table are removed). Each rift is D3x5cm wide and D3x10cm long (s.39).
    Placed automatically (judgement, see rift_spot)."""
    if dice is None:
        from .dice import DiceRoller
        dice = DiceRoller(mode="auto")
    from .models import Phenomenon
    gs.phenomena = []
    att = gs.scenario_attacker
    placed = 0
    for i in range(2 * RIFTS_EACH):
        p = att if i % 2 == 0 else 3 - att
        a, b = dice.roll_d6(2, f"Warp rift {i + 1}: D3x5cm wide, D3x10cm long")
        wide, long_ = 5.0 * ((a + 1) // 2), 10.0 * ((b + 1) // 2)
        spot = rift_spot(gs, p, att, long_, wide)
        if spot is None:
            continue
        gs.add_phenomenon(Phenomenon(id=f"storm_rift_{i}", phenomenon_type="warp_rift",
                                     x=spot[0], y=spot[1], width=long_,
                                     height=wide, radius=0))
        placed += 1
    gs.scenario_state = {"lost": [], "exits": {}}
    gs.add_log(f"[Navigate the Storm] {placed} warp rifts placed (8 each, attacker first)")


def force_errors(gs) -> List[str]:
    from .scenarios import transport, defender
    cap = sum(transport(s, building=True) for s in gs.get_ships() if s.player == defender(gs))
    if cap < CONVOY_CAPACITY:
        return [f"Navigate the Storm: the defender must take {CONVOY_CAPACITY} transport "
                f"capacity of convoy ships (has {cap:g})"]
    return []


# --- ships lost in the warp ----------------------------------------------------------

def lose_ship(gs, ship) -> None:
    """A failed warp rift test. An attacking ship is lost for now and comes
    back in the attacker's end phase; a defending ship is lost for good and
    counts as destroyed (its transport capacity and VP go to the attacker)."""
    if ship.player == gs.scenario_attacker:
        ship.status = LOST
        ship.is_disengaged = True
        gs.update_ship(ship)
        st = dict(gs.scenario_state or {})
        st["lost"] = sorted(set(st.get("lost", [])) | {ship.id})
        gs.scenario_state = st
        gs.add_log(f"[Navigate the Storm] {ship.name} is lost in the warp; it will try to "
                   f"come back in the attacker's end phase")
    else:
        ship.status = "destroyed"
        ship.hits_remaining = 0
        gs.update_ship(ship)
        st = dict(gs.scenario_state or {})
        st["warp_dead"] = sorted(set(st.get("warp_dead", [])) | {ship.id})
        gs.scenario_state = st
        gs.add_log(f"[Navigate the Storm] {ship.name} is lost in the warp (counts as destroyed)")


def _return_spot(gs, ship, anchor) -> Tuple[float, float, float]:
    """Where a returning ship appears (judgement): 15cm from the chosen capital
    ship towards the nearest defending convoy ship, facing it; nudged round
    the anchor until clear of other bases."""
    from .scenarios import is_convoy, defender
    convoys = [s for s in gs.get_ships() if s.player == defender(gs) and is_convoy(s)
               and not s.is_destroyed and not s.is_disengaged]
    goal = min(convoys, key=lambda c: math.hypot(c.x - anchor.x, c.y - anchor.y), default=None)
    base = math.atan2(goal.y - anchor.y, goal.x - anchor.x) if goal and (
        goal.x, goal.y) != (anchor.x, anchor.y) else 0.0
    others = [s for s in gs.get_ships() if not s.is_destroyed and not s.is_disengaged
              and s.id != ship.id]
    for k in range(12):
        a = base + ((-1) ** k) * math.radians(30.0) * ((k + 1) // 2)
        x = anchor.x + 15.0 * math.cos(a)
        y = anchor.y + 15.0 * math.sin(a)
        if not (3.0 <= x <= gs.table_width - 3.0 and 3.0 <= y <= gs.table_height - 3.0):
            continue
        if all(math.hypot(x - o.x, y - o.y) >= o.base_radius + ship.base_radius + 0.5
               for o in others):
            break
    x = max(3.0, min(gs.table_width - 3.0, x))
    y = max(3.0, min(gs.table_height - 3.0, y))
    hd = math.degrees(math.atan2(goal.y - y, goal.x - x)) % 360.0 if goal else ship.heading
    return x, y, hd


def choose_anchor(gs, ship):
    """The capital ship (friendly or enemy, on the table) a lost ship returns
    next to (judgement, also for a human until a dialog exists): the one
    nearest the defender's convoy ships still in play."""
    from .scenarios import is_convoy, defender
    caps = [s for s in gs.get_ships() if s.ship_type != "escort" and not s.is_destroyed
            and not s.is_disengaged and s.status == "active" and s.id != ship.id]
    convoys = [s for s in gs.get_ships() if s.player == defender(gs) and is_convoy(s)
               and not s.is_destroyed and not s.is_disengaged]
    if not caps:
        return None
    if not convoys:
        return caps[0]
    return min(caps, key=lambda c: min(math.hypot(c.x - v.x, c.y - v.y) for v in convoys))


def end_phase(gs, player: int, dice) -> None:
    """The attacker's end phase: each of its ships lost in the warp picks a
    capital ship on the table and rolls a D6: 2+ it is placed within 20cm of
    it, facing any way, materialising; otherwise it stays lost another turn."""
    if not active(gs) or player != gs.scenario_attacker or dice is None:
        return
    st = dict(gs.scenario_state or {})
    keep = []
    for sid in st.get("lost", []):
        ship = gs.get_ship_by_id(sid)
        if ship is None:
            continue
        anchor = choose_anchor(gs, ship)
        if anchor is None:
            keep.append(sid)
            continue
        r = dice.roll_d6(1, f"{ship.name} returns from the warp near {anchor.name} (2+)")[0]
        if r < 2:
            keep.append(sid)
            gs.add_log(f"[Navigate the Storm] {ship.name} stays in the warp (rolled 1)")
            continue
        x, y, hd = _return_spot(gs, ship, anchor)
        ship.x, ship.y, ship.heading = x, y, hd
        ship.status = "active"
        # out of play (untouchable) until the attacker's next movement phase
        ship.is_disengaged = True
        ship.special_rules = sorted(set(ship.special_rules) | {MATERIALISING})
        gs.update_ship(ship)
        gs.add_log(f"[Navigate the Storm] {ship.name} materialises near {anchor.name}")
    st["lost"] = keep
    gs.scenario_state = st


def is_materialising(ship) -> bool:
    return MATERIALISING in (ship.special_rules or [])


def turn_start(gs, player: int) -> None:
    """The attacker's turn: materialising ships come into play to move (they
    still take no damage and interact with nothing until the end of the
    movement phase)."""
    if not active(gs) or player != gs.scenario_attacker:
        return
    for sd in gs.ships:
        if sd["player"] == player and MATERIALISING in sd.get("special_rules", []) \
                and sd.get("status") == "active":
            sd["is_disengaged"] = False
    if getattr(gs, "turn_system", "igougo") == "aa":
        # Alternate activation (reading): the round has no attacker's
        # movement phase before the shooting, so they come back at once
        end_of_movement(gs, player, None, aa=True)


def end_of_movement(gs, player: int, dice, aa: bool = False) -> None:
    """At the end of the attacker's movement phase each materialising ship
    not in base contact with an enemy vessel returns to normal and tests
    Leadership: a failure halves its armament until the end of the turn. One
    in base contact stays materialising (reading: out of play again until
    the attacker's next movement phase)."""
    if not active(gs) or player != gs.scenario_attacker:
        return
    from .scenarios import _dice_for
    dice = _dice_for(gs, player, dice) if dice is not None else None
    if dice is None:
        from .dice import DiceRoller
        dice = DiceRoller(mode="auto")
    enemies = [s for s in gs.get_ships() if s.player != player and not s.is_destroyed
               and not s.is_disengaged]
    for ship in gs.get_ships():
        if ship.player != player or not is_materialising(ship) or ship.status != "active":
            continue
        touching = any(math.hypot(ship.x - e.x, ship.y - e.y)
                       <= ship.base_radius + e.base_radius + 0.01 for e in enemies)
        if touching and not aa:
            ship.is_disengaged = True
            gs.update_ship(ship)
            continue
        ship.special_rules = [r for r in ship.special_rules if r != MATERIALISING]
        ship.is_disengaged = False
        roll = dice.roll_2d6(f"{ship.name} recovers from the warp (Ld {ship.leadership})")
        if roll > ship.leadership:
            ship.special_rules = sorted(set(ship.special_rules) | {HALF_ARMAMENT})
            gs.add_log(f"[Navigate the Storm] {ship.name} returns to normal, its armament at "
                       f"half strength this turn (rolled {roll})")
        else:
            gs.add_log(f"[Navigate the Storm] {ship.name} returns to normal (rolled {roll})")
        gs.update_ship(ship)


def clear_half_armament(gs, player: int) -> None:
    for sd in gs.ships:
        if sd["player"] == player and HALF_ARMAMENT in sd.get("special_rules", []):
            sd["special_rules"] = [r for r in sd["special_rules"] if r != HALF_ARMAMENT]


def halved(ship) -> bool:
    return HALF_ARMAMENT in (ship.special_rules or [])


# --- AI values (judgement) -----------------------------------------------------------

CAPACITY_WEIGHT = 0.05      # judgement: a capacity point ~ 5% of the points on the table
WARSHIP_EXIT_WEIGHT = 0.25  # judgement: a warship's share of the 25% points objective


def capacity_vp(gs) -> float:
    """A transport capacity point in VP (judgement: the 10 capacity decide
    the game, about half the points on the table)."""
    from .scenarios import table_points
    return CAPACITY_WEIGHT * table_points(gs)


def exit_value(gs, ship) -> float:
    """What a defending ship gains by leaving via the exit point: a convoy
    ship its capacity (`capacity_vp`) and its points kept from the attacker;
    a warship `WARSHIP_EXIT_WEIGHT` x its points while the 25% points goal is
    still short (uncrippled ships only count)."""
    from .scenarios import transport, defender
    if not active(gs) or ship.player != defender(gs):
        return 0.0
    cap = transport(ship, building=True)
    if cap > 0:
        return cap * capacity_vp(gs) + ship.points_value
    if ship.damage_crippled:
        return 0.0
    fleet = sum(s.points_value for s in gs.get_ships() if s.player == ship.player)
    if points_evacuated(gs) >= DEFENDER_POINTS_SHARE * fleet:
        return 0.0
    return WARSHIP_EXIT_WEIGHT * ship.points_value


def exit_progress(gs, ship, x: float, y: float) -> float:
    """The share of the way to the exit point a move covers (1 for leaving
    through it)."""
    moved_r = ship.base_radius
    _x0, y0, _x1, y1 = zones(gs)["exit"]
    if x + moved_r > gs.table_width and y0 <= y <= y1:
        return 1.0
    tx, ty = exit_target(gs)
    d0 = math.hypot(tx - ship.x, ty - ship.y)
    d1 = math.hypot(tx - x, ty - y)
    return max(0.0, d0 - d1) / max(1.0, d0)


# --- scoring -------------------------------------------------------------------------

def capacity_destroyed(gs) -> float:
    """Transport capacity destroyed (incl. lost in the warp), at the ships'
    full capacity (reading)."""
    from .scenarios import transport, defender
    return sum(transport(s, building=True) for s in gs.get_ships()
               if s.player == defender(gs) and s.is_destroyed)


def capacity_evacuated(gs) -> float:
    from .scenarios import transport, defender
    exits = (gs.scenario_state or {}).get("storm_exit", [])
    return sum(transport(s, building=True) for s in gs.get_ships()
               if s.player == defender(gs) and s.id in exits)


def points_evacuated(gs) -> int:
    """The defender's points off via the exit point, ignoring crippled ships
    (an escort squadron counted ship by ship, reading)."""
    from .scenarios import defender
    exits = (gs.scenario_state or {}).get("storm_exit", [])
    return sum(s.points_value for s in gs.get_ships()
               if s.player == defender(gs) and s.id in exits and not s.damage_crippled)


def record_exit(gs, ship) -> None:
    if active(gs) and via_exit_point(gs, ship):
        st = dict(gs.scenario_state or {})
        st["storm_exit"] = sorted(set(st.get("storm_exit", [])) | {ship.id})
        gs.scenario_state = st


def evacuated(gs, ship) -> bool:
    return ship.id in (gs.scenario_state or {}).get("storm_exit", [])


def cargo_left(gs) -> float:
    """Transport capacity still in play (on the table)."""
    from .scenarios import transport, defender
    return sum(transport(s, building=True) for s in gs.get_ships()
               if s.player == defender(gs) and not s.is_destroyed and not s.is_disengaged)


def objectives_met(gs) -> Dict[str, bool]:
    from .scenarios import defender
    from .victory_points import calculate_victory_points
    att = gs.scenario_attacker
    dfn = defender(gs)
    vp = calculate_victory_points(gs)
    fleet = sum(s.points_value for s in gs.get_ships() if s.player == dfn)
    return {
        "attacker": capacity_destroyed(gs) >= ATTACKER_TARGET_CAP
        and vp[att]["total"] >= ATTACKER_VP_SHARE * fleet,
        "defender": capacity_evacuated(gs) >= DEFENDER_TARGET_CAP
        and points_evacuated(gs) >= DEFENDER_POINTS_SHARE * fleet,
    }


def winner(gs) -> int:
    """Only one player meeting its objective wins; otherwise (both or
    neither) the most transport capacity destroyed or evacuated wins, the
    attacker on a tie."""
    from .scenarios import defender
    met = objectives_met(gs)
    if met["attacker"] != met["defender"]:
        return gs.scenario_attacker if met["attacker"] else defender(gs)
    return defender(gs) if capacity_evacuated(gs) > capacity_destroyed(gs) \
        else gs.scenario_attacker
