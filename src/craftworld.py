"""Craftworld Assault (XR p.113-115, campaign set piece).

Planetary Assault against an Eldar craftworld: the craftworld is a planet
(gravity well, low orbit table; `planet_scenarios` plays the assault points,
the game end and the result, treating this mode as Planetary Assault) with
its own defences:
- the Fortresses: each assault point is negated on a 4+ (5+ / 6+ once damaged);
  in the Eldar shooting phase each fires an FP1 pulsar lance at every enemy
  capital ship and escort squadron in low orbit within 45cm of the planet edge;
- the Spear of Light: a nova cannon on the craftworld;
- both roll a D6 per assault point scored in each end phase, damaged on any 6
  (at most once a turn each);
- the Forges: an Eldar capital ship in low orbit moving into the planet edge
  docks until the end of the next Eldar turn (+4D6 to repairs, hits back on
  6s, free reloads, no moving / shooting / launching / boarding / teleports);
- the Gates: from its second turn the Eldar player rolls a D6 each turn, on a
  5+ D3 reserve units arrive touching the craftworld (no moving or shooting
  that turn).
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional

MODE = "craftworld_assault"
PLANET_ID = "assault_planet"           # the id planet_scenarios looks for
# D6 -> (phenomenon type, radius, gravity well): the size table (diameter
# 10-15 / 16-20 / 21-30cm, judgement: the middle of each range); Iyanden is
# about 25cm across, so large
SIZES = {1: ("planet_small", 6.25, 10.0), 2: ("planet_medium", 9.0, 15.0),
         3: ("planet_medium", 9.0, 15.0), 4: ("planet_medium", 9.0, 15.0),
         5: ("planet_medium", 9.0, 15.0), 6: ("planet_large", 12.5, 20.0)}
IYANDEN = ("planet_large", 12.5, 20.0)
FORTRESS_RANGE = 45.0
SPEAR_RELOAD_LD = 8
SPEAR_FRIEND_CLEARANCE = 12.0


def active(gs) -> bool:
    return getattr(gs, "scenario_mode", "") == MODE


def _key(s) -> str:
    return s.squadron_id if (s.ship_type == "escort" and s.squadron_id) else s.id


def _auto_dice(dice=None):
    if dice is not None:
        return dice
    from .dice import DiceRoller
    return DiceRoller(mode="auto")


def craftworld(gs):
    return next((p for p in gs.get_phenomena() if p.id == PLANET_ID), None)


# --- set-up ---------------------------------------------------------------------------

def place_craftworld(gs, dice, roll_size: bool = False) -> None:
    """Iyanden (25cm across, gravity well 20cm), or a D6 on the size table;
    its near edge 150cm from the attacker's (right) short edge (as Planetary
    Assault's planet; "no more than 150cm from one of the short table edges")."""
    from .models import Phenomenon
    kind, r, well = SIZES[dice.roll_d6(1, "Craftworld size (D6)")[0]] if roll_size else IYANDEN
    w, h = gs.table_width, gs.table_height
    gs.phenomena = [p for p in gs.phenomena if "planet" not in p.get("phenomenon_type", "")]
    x = max(r + 2.0, w - 150.0 - r)
    gs.add_phenomenon(Phenomenon(id=PLANET_ID, phenomenon_type=kind, x=x, y=h / 2.0,
                                 width=2 * r, height=2 * r, radius=r,
                                 special_rules=["craftworld", f"well:{well:g}"]))


def _set_sides(gs) -> None:
    """The Eldar defend: the player whose main faction is Eldar."""
    from .scenarios import _main_faction
    for p in (1, 2):
        if _main_faction(gs, p) == "eldar" and _main_faction(gs, 3 - p) != "eldar":
            gs.scenario_attacker = 3 - p


def setup(gs, dice) -> None:
    """The craftworld; the Eldar units on alert (judgement: the dearest half
    by points) deploy in the gravity well, the rest are on patrol: a D6 each,
    1-3 placed by the attacker (Shadowhunter squadrons always on patrol,
    placed by the defender); units bought as special reserves (the
    `gate_reserve` rule, or `scenario_state["gate_reserves"]` when chosen)
    wait for the Gates."""
    from .scenarios import _to_reserve, defender
    _set_sides(gs)
    st0 = dict(gs.scenario_state or {})
    place_craftworld(gs, dice, roll_size=bool(st0.get("roll_size")))
    dfn = defender(gs)
    reserves = set(st0.get("gate_reserves", []))
    for s in gs.get_ships():
        if s.player == dfn and "gate_reserve" in s.special_rules:
            reserves.add(_key(s))
    units: Dict[str, int] = {}
    shadow: Dict[str, bool] = {}
    for s in gs.get_ships():
        if s.player != dfn or "immobile" in s.special_rules or _key(s) in reserves:
            continue
        k = _key(s)
        units[k] = units.get(k, 0) + (s.points_value or 0)
        shadow[k] = shadow.get(k, True) and "Shadowhunter" in s.ship_class
    free = {k: v for k, v in units.items() if not shadow[k]}
    order = sorted(free.items(), key=lambda kv: (-kv[1], kv[0]))
    alert, got = [], 0
    for k, v in order:
        if got * 2 >= sum(free.values()):
            break
        alert.append(k)
        got += v
    by_attacker = []
    for k in sorted(units):
        if k in alert or shadow[k]:
            continue
        if dice.roll_d6(1, f"Craftworld Assault: patrol {k} (1-3 placed by the attacker)")[0] <= 3:
            by_attacker.append(k)
    for sd in gs.ships:
        k = sd["squadron_id"] if (sd.get("ship_type") == "escort" and sd.get("squadron_id")) \
            else sd["id"]
        if sd["player"] == dfn and k in reserves:
            _to_reserve(sd)
    gs.scenario_state = {"low_orbit_planet": PLANET_ID, "assault_points": 0.0, "assaulted": {},
                         "alert": alert, "patrol_by_attacker": by_attacker,
                         "gate_reserves": sorted(reserves), "fortress_damage": 0,
                         "spear_damage": 0, "spear_loaded": True, "eldar_turns": 0}
    gs.add_log(f"[Craftworld Assault] on alert in the gravity well: {alert}; patrols placed "
               f"by the attacker: {by_attacker}; in reserve for the Gates: {sorted(reserves)}")


def auto_positions(gs, group, placed):
    """Patrols the attacker places (judgement: as close to the attacker's
    edge as a patrol may be, 30cm in); the rest as Planetary Assault."""
    st = gs.scenario_state or {}
    if group and _key(group[0]) in st.get("patrol_by_attacker", []):
        k = sum(1 for p in placed if p.player == group[0].player
                and _key(p) in st.get("patrol_by_attacker", []))
        x = gs.table_width - 31.0
        return [(x, gs.table_height / 2.0 + (-1) ** (k + i) * 12.0 * ((k + i + 1) // 2))
                for i in range(len(group))]
    from .planet_scenarios import auto_positions as _pa_auto
    return _pa_auto(gs, group, placed)


# --- the Fortresses -------------------------------------------------------------------

def fortresses(gs) -> int:
    d = (gs.scenario_state or {}).get("fortress_damage", 0)
    return 0 if d >= 6 else (1 if d >= 5 else 2)


def negate_need(gs) -> Optional[int]:
    """The roll that negates an assault point (None: no fortress cover)."""
    d = (gs.scenario_state or {}).get("fortress_damage", 0)
    if d >= 6:
        return None
    return 6 if d >= 4 else (5 if d >= 2 else 4)


def filter_assault_points(gs, pts: float, dice=None) -> float:
    """Each assault point that would be scored is negated on the fortresses'
    roll (reading: a part point is rolled for as one)."""
    need = negate_need(gs)
    if not active(gs) or need is None or pts <= 0:
        return pts
    dice = _auto_dice(dice)
    n = int(math.ceil(pts))
    rolls = dice.roll_d6(n, f"Craftworld fortresses: negate assault points ({need}+)")
    kept = pts
    for i, r in enumerate(rolls):
        if r >= need:
            kept -= min(1.0, pts - i) if i == n - 1 else 1.0
    kept = max(0.0, kept)
    gs.add_log(f"[Craftworld Assault] the fortresses negate {pts - kept:g} of {pts:g} assault "
               f"points (rolled {rolls})")
    return kept


def fortress_targets(gs) -> List:
    """Enemy capital ships and escort squadrons (the member nearest the
    planet edge, reading) on the low orbit table within 45cm of its planet
    edge."""
    from .low_orbit import in_low_orbit, distance_to_planet_edge
    from .scenarios import defender
    out: Dict[str, object] = {}
    for s in gs.get_ships():
        if (s.player == defender(gs) or s.is_destroyed or s.is_disengaged
                or not in_low_orbit(s) or distance_to_planet_edge(s) > FORTRESS_RANGE):
            continue
        k = _key(s)
        if k not in out or distance_to_planet_edge(s) < distance_to_planet_edge(out[k]):
            out[k] = s
    return list(out.values())


def fortress_fire(gs, dice=None) -> int:
    """Each fortress makes an FP1 pulsar lance attack against each target:
    4+ to hit, each hit allows another attack, at most three hits (the
    Eldar pulsar rule). Returns the hits scored."""
    from .combat import apply_damage, offer_brace
    from .models import SpecialOrder
    n = fortresses(gs)
    if not active(gs) or n == 0:
        return 0
    dice = _auto_dice(dice)
    total = 0
    for t in fortress_targets(gs):
        for f in range(n):
            t = gs.get_ship_by_id(t.id)
            if t is None or t.is_destroyed:
                break
            braced = offer_brace(gs, t, "craftworld_fortress", "Craftworld fortress", 0.5)
            hits = 0
            if dice.roll_d6(1, f"Fortress {f + 1} pulsar lance at {t.name} (4+)")[0] >= 4:
                hits = 1
                for _k in range(2):
                    if dice.roll_d6(1, "Fortress pulsar follow-up (4+)")[0] < 4:
                        break
                    hits += 1
            if hits:
                t = gs.get_ship_by_id(t.id)
                apply_damage(t, hits, dice, gs, target_braced=braced
                             or t.special_order == SpecialOrder.BRACE_FOR_IMPACT.value,
                             attacker_key="craftworld_fortress")
                total += hits
            gs.add_log(f"[Craftworld Assault] fortress {f + 1} fires at {t.name}: {hits} hit(s)")
    return total


# --- the Spear of Light ---------------------------------------------------------------

def spear_ready(gs) -> bool:
    st = gs.scenario_state or {}
    return active(gs) and st.get("spear_damage", 0) < 2 and st.get("spear_loaded", True)


def _spear_ship(gs, tx: float, ty: float):
    """The Spear as a stand-in ship at the craftworld's edge facing the target
    (reading: range measured from the craftworld's edge)."""
    from .models import Ship
    from .scenarios import defender
    pl = craftworld(gs)
    a = math.atan2(ty - pl.y, tx - pl.x)
    return Ship(id="spear_of_light", name="the Spear of Light", ship_class="Spear of Light",
                faction="eldar", player=defender(gs), ship_type="defense", base_size="small",
                x=pl.x + pl.radius * math.cos(a), y=pl.y + pl.radius * math.sin(a),
                heading=math.degrees(a) % 360.0, speed=0, turn_angle=0, shields_max=0,
                hits_max=1, leadership=SPEAR_RELOAD_LD, weapons=[], special_rules=[],
                upgrades=[], critical_damage=[])


def spear_target(gs):
    """Judgement (also for a human, first form): the enemy ship off the low
    orbit table in 30-150cm where the nova cannon's expected hits add the
    most VP, never with an Eldar ship within 12cm of it."""
    from .ai_hazards import nova_expected_hits, added_vp
    from .low_orbit import in_low_orbit
    from .scenarios import defender
    pl = craftworld(gs)
    if pl is None:
        return None
    friends = [f for f in gs.get_ships() if f.player == defender(gs) and not f.is_destroyed
               and not f.is_disengaged]
    best = None
    for e in gs.get_ships():
        if (e.player == defender(gs) or e.is_destroyed or e.is_disengaged
                or in_low_orbit(e) or e.status == "reserve"):
            continue
        dist = math.hypot(e.x - pl.x, e.y - pl.y) - pl.radius
        if dist < 30 or dist > 150:
            continue
        if any(math.hypot(f.x - e.x, f.y - e.y) <= SPEAR_FRIEND_CLEARANCE for f in friends):
            continue
        v = added_vp(e, gs, 0.0, nova_expected_hits(dist, e))
        if best is None or v > best[0]:
            best = (v, e)
    return best[1] if best and best[0] > 0 else None


def fire_spear(gs, target, dice=None) -> Dict:
    """The Spear of Light fires as a nova cannon at `target`."""
    from .combat import resolve_nova_cannon, apply_damage, offer_brace
    from .models import SpecialOrder
    dice = _auto_dice(dice)
    if not spear_ready(gs) or target is None:
        return {"error": "not ready"}
    shooter = _spear_ship(gs, target.x, target.y)
    braced = offer_brace(gs, target, "spear_of_light", "the Spear of Light", 1.0)
    nc = resolve_nova_cannon(shooter, target.x, target.y, dice, gs)
    if "error" in nc:
        return nc
    for sid, hd in nc.get("ship_hits", {}).items():
        t = gs.get_ship_by_id(sid)
        if t:
            apply_damage(t, hd["hits"], dice, gs,
                         target_braced=(braced and t.id == target.id)
                         or t.special_order == SpecialOrder.BRACE_FOR_IMPACT.value,
                         attacker_key="spear_of_light",
                         origin=(nc["template_x"], nc["template_y"]))
    from .models import BlastMarker
    import random as _r
    for (bx, by) in nc.get("blast_markers", []):
        gs.add_blast_marker(BlastMarker(id=f"spear_{_r.randint(0, 99999)}", x=bx, y=by))
    st = dict(gs.scenario_state or {})
    if st.get("spear_damage", 0) >= 1:
        st["spear_loaded"] = False         # damaged: Reload Ordnance (Ld 8) before it fires again
    gs.scenario_state = st
    gs.add_log(f"[Craftworld Assault] the Spear of Light fires at {target.name}: "
               f"{ {gs.get_ship_by_id(k).name: v['hits'] for k, v in nc['ship_hits'].items()} }")
    return nc


def spear_reload(gs, dice=None) -> None:
    """A damaged Spear reloads with Reload Ordnance at Ld 8 (reading: tried
    at the start of each Eldar turn, outside the fleet's chain of command
    checks)."""
    st = dict(gs.scenario_state or {})
    if st.get("spear_loaded", True) or st.get("spear_damage", 0) >= 2:
        return
    r = _auto_dice(dice).roll_2d6(f"Spear of Light Reload Ordnance (Ld {SPEAR_RELOAD_LD})")
    if r <= SPEAR_RELOAD_LD:
        st["spear_loaded"] = True
    gs.scenario_state = st
    gs.add_log(f"[Craftworld Assault] the Spear of Light reload: rolled {r} "
               f"({'reloaded' if r <= SPEAR_RELOAD_LD else 'failed'})")


# --- damage to the defences -----------------------------------------------------------

def end_phase(gs, player: int, dice=None) -> None:
    """Each player's end phase: a D6 per assault point already scored for the
    fortresses, and again for the Spear; any 6 is one damage (at most one a
    turn each)."""
    if not active(gs):
        return
    st = dict(gs.scenario_state or {})
    n = int(st.get("assault_points", 0.0))
    dice = _auto_dice(dice)
    if n > 0 and st.get("fortress_damage", 0) < 6:
        rolls = dice.roll_d6(n, "Craftworld fortresses damage (any 6)")
        if 6 in rolls:
            st["fortress_damage"] = st.get("fortress_damage", 0) + 1
            gs.add_log(f"[Craftworld Assault] the fortresses are damaged "
                       f"({st['fortress_damage']})")
    if n > 0 and st.get("spear_damage", 0) < 2:
        rolls = dice.roll_d6(n, "Spear of Light damage (any 6)")
        if 6 in rolls:
            st["spear_damage"] = st.get("spear_damage", 0) + 1
            gs.add_log("[Craftworld Assault] the Spear of Light is "
                       + ("destroyed" if st["spear_damage"] >= 2 else "damaged"))
    gs.scenario_state = st
    _undock(gs, player)


# --- the Forges -----------------------------------------------------------------------

def can_dock(gs, ship) -> bool:
    from .scenarios import defender
    return (active(gs) and ship.player == defender(gs) and ship.ship_type != "escort"
            and "eldar_mms" in ship.special_rules)


def dock(gs, ship) -> None:
    """The ship stays touching the planet edge, docked until the end of the
    next Eldar turn; it reloads its ordnance."""
    from .low_orbit import planet_edge_y
    from .ordnance import reload_ship_ordnance
    step = 1 if getattr(gs, "turn_system", "igougo") == "aa" else 2
    ship.y = planet_edge_y() - ship.base_radius - 0.1
    ship.special_rules = [r for r in ship.special_rules if not r.startswith("docked:")
                          and r != "undocking"] + [f"docked:{gs.turn_number + step}"]
    for line in reload_ship_ordnance(ship):
        gs.add_log(line)
    gs.update_ship(ship)
    gs.add_log(f"[Craftworld Assault] {ship.name} docks at the forges")


def docked(ship) -> bool:
    return any(r.startswith("docked:") for r in (getattr(ship, "special_rules", None) or []))


def held_in_orbit(ship) -> bool:
    """Docked ships don't fall; nor does one just undocked before its next
    move (reading: "remains docked until the end of the next Eldar turn",
    and it can't climb away before the start of the next player's turn)."""
    rules = getattr(ship, "special_rules", None) or []
    return docked(ship) or "undocking" in rules


def _undock(gs, player: int) -> None:
    for s in gs.get_ships():
        if s.player != player:
            continue
        for r in list(s.special_rules):
            if r.startswith("docked:") and int(r.split(":")[1]) <= gs.turn_number:
                s.special_rules = [x for x in s.special_rules if x != r] + ["undocking"]
                gs.update_ship(s)
                gs.add_log(f"[Craftworld Assault] {s.name} undocks")


# --- the Gates ------------------------------------------------------------------------

def gate_arrivals(gs, player: int, dice=None) -> List[str]:
    """At the start of each Eldar turn after the first: on a 5+, D3 units
    from reserve (judgement, also for a human: the dearest first) touching
    the craftworld at its rear (judgement: the side away from the attacker),
    facing the closest short edge; they can't move or shoot that turn."""
    from .scenarios import defender, reserve_units
    if not active(gs) or player != defender(gs):
        return []
    st = dict(gs.scenario_state or {})
    st["eldar_turns"] = st.get("eldar_turns", 0) + 1
    gs.scenario_state = st
    waiting = reserve_units(gs, player)
    if st["eldar_turns"] < 2 or not waiting:
        return []
    dice = _auto_dice(dice)
    r = dice.roll_d6(1, "Craftworld Assault: the Gates open on 5+")[0]
    if r < 5:
        gs.add_log(f"[Craftworld Assault] the Gates stay closed (rolled {r})")
        return []
    n = (dice.roll_d6(1, "Craftworld Assault: D3 units through the Gates")[0] + 1) // 2
    pl = craftworld(gs)
    order = sorted(waiting, key=lambda k: -sum(s.points_value or 0 for s in waiting[k]))
    names, slot = [], 0
    facing = 180.0 if pl.x < gs.table_width / 2.0 else 0.0
    for k in order[:n]:
        for s in waiting[k]:
            a = math.radians(180.0 + 25.0 * ((-1) ** slot) * ((slot + 1) // 2)
                             if facing == 180.0 else 25.0 * ((-1) ** slot) * ((slot + 1) // 2))
            rr = pl.radius + s.base_radius + 0.1
            x = min(gs.table_width - s.base_radius, max(s.base_radius, pl.x + rr * math.cos(a)))
            y = min(gs.table_height - s.base_radius, max(s.base_radius, pl.y + rr * math.sin(a)))
            fresh = gs.get_ship_by_id(s.id)
            fresh.x, fresh.y, fresh.heading = x, y, facing
            fresh.status, fresh.is_disengaged = "active", False
            fresh.special_rules = list(fresh.special_rules) + [f"gate_arrived:{gs.turn_number}"]
            gs.update_ship(fresh)
            slot += 1
        names.append(waiting[k][0].name)
    gs.add_log(f"[Craftworld Assault] the Gates open (rolled {r}): {', '.join(names)}")
    return names


def held_back(gs, ship) -> bool:
    """A docked ship, or one arrived through the Gates this turn: no moving,
    shooting, launching, boarding or teleports (as on standby)."""
    if not active(gs):
        return False
    return docked(ship) or f"gate_arrived:{gs.turn_number}" in (ship.special_rules or [])


# --- turn hooks -----------------------------------------------------------------------

def turn_start(gs, player: int, dice=None) -> None:
    from .scenarios import defender
    if not active(gs):
        return
    if player == defender(gs):
        for s in gs.get_ships():
            if s.player == player and "undocking" in s.special_rules:
                s.special_rules = [r for r in s.special_rules if r != "undocking"]
                gs.update_ship(s)
        gate_arrivals(gs, player, dice)
        spear_reload(gs, dice)


def shooting_start(gs, player: int, dice=None) -> None:
    """The Eldar shooting phase: the fortresses fire into low orbit, the
    Spear of Light at its best target (judgement, first form: automatic for
    a human too)."""
    from .scenarios import defender
    if not active(gs) or player != defender(gs):
        return
    fortress_fire(gs, dice)
    if spear_ready(gs):
        t = spear_target(gs)
        if t is not None:
            fire_spear(gs, t, dice)
