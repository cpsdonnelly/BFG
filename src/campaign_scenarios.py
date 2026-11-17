"""Campaign set pieces (XR p.111-112): The Defence of Pelucidar and
Macharia's End.

The Defence of Pelucidar: the Imperial fleet (the defender) holds out while
Ghazghkull's Orks arrive at random every Ork turn (D6 + turn number); the
Imperium wins by scoring 2000 more VP than the Orks, nobody holds the field.

Macharia's End: the Planet Killer must overcharge its Armageddon Gun (three
charge counters, then a 60cm blast) to destroy Macharia; the Imperium wins by
crippling or destroying it.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional

PELUCIDAR_MARGIN = 2000
# D6 + turn number -> forces (highest band first); results the engine can't
# field drop to the next lowest result (the rule says so for missing models):
# the Ork Rok and Space Hulk aren't playable, so 13-14 is a Hammer and 15+
# falls to 13-14
PELUCIDAR_TABLE = ((15, "hammer"), (13, "hammer"), (12, "two_kroozers"), (11, "kroozer"),
                   (10, "three_squadrons"), (7, "two_squadrons"), (5, "one_squadron"),
                   (2, "fighta_bommerz"))
EDGE_BY_D6 = {1: "left", 2: "top", 3: "top", 4: "bottom", 5: "bottom", 6: "right"}
# judgement picks, standing in for the Ork player's choice "in any combination"
ORK_ESCORT = "Ravager Attack Ship"
ORK_KROOZER = "Kill Kroozer"
ORK_HAMMER = "Hammer Battlekroozer"

MACHARIA_ID = "macharia"
OVERCHARGE_COUNTERS = 3
OVERCHARGE_RANGE = 60.0
OVERCHARGE_SHIELDS = 2


def mode(gs) -> str:
    return getattr(gs, "scenario_mode", "")


# --- The Defence of Pelucidar --------------------------------------------------------

def _set_attacker(gs, faction: str) -> None:
    """The scenario names the sides: the player whose main faction is the
    attacking one (Orks / Chaos) attacks, else the chosen attacker stands."""
    from .scenarios import _main_faction
    for p in (1, 2):
        if _main_faction(gs, p) == faction and _main_faction(gs, 3 - p) != faction:
            gs.scenario_attacker = p


def pelucidar_setup(gs, dice) -> None:
    """The Orks (the attacker) start with nothing: their built fleet is
    removed (reading: forces arrive from the table instead). Pelucidar, a
    medium planet, more than 5cm from an edge (judgement: the table centre)."""
    from .scenarios import _place_planet
    _set_attacker(gs, "orks")
    att = gs.scenario_attacker
    gs.ships = [sd for sd in gs.ships if sd["player"] != att]
    _place_planet(gs, "planet_medium", 5.0, gs.table_width / 2.0, gs.table_height / 2.0)
    gs.scenario_state = {"arrivals": 0}
    gs.add_log("[Pelucidar] the Ork fleet will arrive at random; Pelucidar at the centre")


def _game_turn(gs) -> int:
    return gs.turn_number if getattr(gs, "turn_system", "igougo") == "aa" \
        else (gs.turn_number + 1) // 2


def pelucidar_result(total: int) -> str:
    for low, res in PELUCIDAR_TABLE:
        if total >= low:
            return res
    return "fighta_bommerz"


def _add_ork(gs, cls: str, sid: str, dice, squadron: str = ""):
    from .ship_catalog import find_ship_class
    from .models import Ship
    from .booklet_ships import LEADERSHIP_TABLES
    e = find_ship_class(cls)
    d = e.to_ship_dict(e.ship_class, gs.scenario_attacker, ship_id=sid)
    d.update(x=0.0, y=0.0, heading=0.0, squadron_id=squadron)
    if e.leadership_table:
        d["leadership"] = LEADERSHIP_TABLES.get(e.leadership_table, LEADERSHIP_TABLES["Orks"])[
            dice.roll_d6(1, f"{cls} Leadership")[0] - 1]
    s = Ship.from_dict(d)
    gs.add_ship(s)
    return gs.get_ship_by_id(sid)


def pelucidar_arrivals(gs, dice) -> List[str]:
    """At the start of each Ork turn: D6 + the game turn on the table; the
    forces arrive from a random table edge (reading: the rule doesn't say
    where, so a D6 edge as other scenarios' arrivals: 1 left, 2-3 top, 4-5
    bottom, 6 right), touching it and facing in."""
    from .scenarios import place_arrival_at
    from .models import OrdnanceMarker, OrdnanceType
    r = dice.roll_d6(1, "Pelucidar: Ork arrivals (D6 + turn)")[0]
    total = r + _game_turn(gs)
    res = pelucidar_result(total)
    edge = EDGE_BY_D6[dice.roll_d6(1, "Pelucidar: arrival edge (1 left, 2-3 top, 4-5 bottom, "
                                      "6 right)")[0]]
    st = dict(gs.scenario_state or {})
    n = st.get("arrivals", 0)
    names = []
    if res == "fighta_bommerz":
        w, h = gs.table_width, gs.table_height
        x, y, hd = {"left": (1.0, h / 2, 0.0), "right": (w - 1.0, h / 2, 180.0),
                    "top": (w / 2, h - 1.0, 270.0), "bottom": (w / 2, 1.0, 90.0)}[edge]
        wave = f"pelucidar_wave_{n}"
        for k in range(4):
            gs.add_ordnance(OrdnanceMarker(
                id=f"{wave}_{k}", ordnance_type=OrdnanceType.FIGHTA_BOMMER.value,
                owner_player=gs.scenario_attacker, launched_by="", x=x, y=y, heading=hd,
                speed=25.0, launched_turn=gs.turn_number, wave_id=wave, wave_order=k,
                wave_formation="close", special_rules=["ork_turrets"]))
        names.append("a wave of 4 squadrons of Fighta-Bommerz")
    else:
        groups = []
        if res.endswith("squadrons") or res == "one_squadron":
            count = {"one_squadron": 1, "two_squadrons": 2, "three_squadrons": 3}[res]
            for g in range(count):
                k = dice.roll_d6(1, "Pelucidar: escorts in the squadron (D6)")[0]
                sq = f"pelucidar_sq_{n}_{g}"
                groups.append([_add_ork(gs, ORK_ESCORT, f"ork_{n}_{g}_{i}", dice, sq)
                               for i in range(k)])
        elif res in ("kroozer", "two_kroozers"):
            for g in range(1 if res == "kroozer" else 2):
                groups.append([_add_ork(gs, ORK_KROOZER, f"ork_{n}_{g}", dice)])
        else:
            groups.append([_add_ork(gs, ORK_HAMMER, f"ork_{n}_0", dice)])
        for i, ships in enumerate(groups):
            place_arrival_at(gs, ships, edge, i)
            names.append(f"{len(ships)} x {ships[0].ship_class}")
    st["arrivals"] = n + 1
    gs.scenario_state = st
    gs.add_log(f"[Pelucidar] rolled {r} + turn {_game_turn(gs)} = {total}: "
               f"{', '.join(names)} from the {edge} edge")
    return names


def pelucidar_force_errors(gs) -> List[str]:
    from .scenarios import defender
    bad = [s.name for s in gs.get_ships() if s.player == defender(gs) and (
        s.ship_type == "escort" or "Light Cruiser" in s.ship_class
        or "Grand Cruiser" in s.ship_class)]
    return [f"Pelucidar: the Imperial fleet may only include cruisers, battlecruisers and "
            f"battleships ({', '.join(bad)})"] if bad else []


def pelucidar_winner(gs) -> int:
    from .victory_points import calculate_victory_points
    from .scenarios import defender
    vp = calculate_victory_points(gs)
    dfn, att = defender(gs), gs.scenario_attacker
    return dfn if vp[dfn]["total"] - vp[att]["total"] >= PELUCIDAR_MARGIN else att


# --- Macharia's End -------------------------------------------------------------------

def planet_killer(gs):
    return next((s for s in gs.get_ships() if s.ship_class == "The Planet Killer"
                 and s.player == gs.scenario_attacker), None)


def macharia(gs):
    return next((p for p in gs.get_phenomena() if p.id == MACHARIA_ID), None)


def macharia_setup(gs, dice) -> None:
    """Macharia (medium) at the centre of the Imperial (left) short edge; the
    Planet Killer joins the Chaos fleet at no cost if it isn't in it and waits
    off the table to move on in the first Chaos turn; the Imperial vanguard
    (judgement: the defender's cheapest units up to 500pts) deploys within 5cm
    of the centre line."""
    from .scenarios import _to_reserve, defender
    from .ship_catalog import find_ship_class
    from .models import Ship, Phenomenon
    from .booklet_ships import LEADERSHIP_TABLES
    _set_attacker(gs, "chaos")
    h = gs.table_height
    gs.phenomena = [p for p in gs.phenomena if "planet" not in p.get("phenomenon_type", "")]
    r = 5.0
    gs.add_phenomenon(Phenomenon(id=MACHARIA_ID, phenomenon_type="planet_medium", x=r,
                                 y=h / 2.0, width=2 * r, height=2 * r, radius=r))
    pk = planet_killer(gs)
    if pk is None:
        e = find_ship_class("The Planet Killer")
        d = e.to_ship_dict(e.ship_class, gs.scenario_attacker, ship_id="planet_killer")
        d.update(x=0.0, y=0.0, heading=180.0, points_value=0)
        if not d.get("leadership"):
            d["leadership"] = LEADERSHIP_TABLES.get(e.leadership_table or "Default",
                                                    LEADERSHIP_TABLES["Default"])[
                dice.roll_d6(1, "The Planet Killer's Leadership")[0] - 1]
        gs.add_ship(Ship.from_dict(d))
        pk = gs.get_ship_by_id("planet_killer")
    for sd in gs.ships:
        if sd["id"] == pk.id:
            _to_reserve(sd)
    units: Dict[str, int] = {}
    for sd in gs.ships:
        if sd["player"] == defender(gs):
            k = sd["squadron_id"] if (sd.get("ship_type") == "escort" and sd.get("squadron_id")) \
                else sd["id"]
            units[k] = units.get(k, 0) + sd.get("points_value", 0)
    vanguard, got = [], 0
    for k, v in sorted(units.items(), key=lambda kv: (kv[1], kv[0])):
        if got + v > 500:
            continue
        vanguard.append(k)
        got += v
    gs.scenario_state = {"vanguard": vanguard, "charge": 0, "recharge": 0,
                         "planet_destroyed": False}
    gs.add_log(f"[Macharia's End] the Imperial vanguard ({got}pts): {vanguard}; the Planet "
               f"Killer arrives in the first Chaos turn")


def is_vanguard(gs, ship) -> bool:
    k = ship.squadron_id if (ship.ship_type == "escort" and ship.squadron_id) else ship.id
    return k in (gs.scenario_state or {}).get("vanguard", [])


def macharia_turn_start(gs, player: int, dice, ask=None) -> None:
    """The Chaos turn: the Planet Killer moves on (first turn); then the
    charge-up: begun (a human asked via `ask`, the AI by `wants_overcharge`),
    a counter a turn once begun."""
    from .scenarios import place_arrival_at, is_reserve
    if player != gs.scenario_attacker:
        return
    pk = planet_killer(gs)
    if pk is None:
        return
    if is_reserve(pk):
        place_arrival_at(gs, [pk], "right", 0)
        gs.add_log("[Macharia's End] the Planet Killer moves onto the table")
        return
    st = dict(gs.scenario_state or {})
    if pk.is_destroyed or pk.is_disengaged:
        return
    if st.get("charge", 0) > 0:
        st["charge"] = min(OVERCHARGE_COUNTERS, st["charge"] + 1)
        gs.add_log(f"[Macharia's End] Armageddon Gun charge {st['charge']}")
    elif st.get("recharge", 0) == 0:
        want = wants_overcharge(gs, pk) if ask is None else bool(ask(pk))
        if want:
            st["charge"] = 1
            gs.add_log("[Macharia's End] the Planet Killer begins overcharging its "
                       "Armageddon Gun")
    gs.scenario_state = st
    _apply_charging(gs, pk, st.get("charge", 0) > 0)


def _apply_charging(gs, pk, charging: bool) -> None:
    """While charging: +2 shields, no turning, no special orders, no lances
    (rule tags read by the engine)."""
    pk = gs.get_ship_by_id(pk.id)
    has = "overcharging" in pk.special_rules
    if charging and not has:
        pk.special_rules = list(pk.special_rules) + ["overcharging"]
        pk.shields_max += OVERCHARGE_SHIELDS
    elif not charging and has:
        pk.special_rules = [r for r in pk.special_rules if r != "overcharging"]
        pk.shields_max = max(0, pk.shields_max - OVERCHARGE_SHIELDS)
    gs.update_ship(pk)


def charged(gs) -> bool:
    return (gs.scenario_state or {}).get("charge", 0) >= OVERCHARGE_COUNTERS


def overcharge_path(gs, pk):
    """The template's path: from the stem straight ahead 60cm."""
    h = math.radians(pk.heading)
    x0 = pk.x + pk.base_radius * math.cos(h)
    y0 = pk.y + pk.base_radius * math.sin(h)
    return x0, y0, x0 + OVERCHARGE_RANGE * math.cos(h), y0 + OVERCHARGE_RANGE * math.sin(h)


def fire_overcharged(gs, pk) -> Dict:
    """The overcharged shot: the nova template from the stem moved 60cm
    straight ahead; every ship whose base any part of it passes over is
    destroyed; the centre hole touching Macharia obliterates the planet."""
    from .geometry import (NOVA_CANNON_TEMPLATE_RADIUS_CM as TR,
                           NOVA_CANNON_CENTER_HOLE_RADIUS_CM as CR)
    x0, y0, x1, y1 = overcharge_path(gs, pk)

    def seg(px, py):
        dx, dy = x1 - x0, y1 - y0
        L = dx * dx + dy * dy
        t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L))
        return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))
    killed = []
    for s in gs.get_ships():
        if s.id == pk.id or s.is_destroyed or s.is_disengaged:
            continue
        if seg(s.x, s.y) <= s.base_radius + TR:
            s.status, s.hits_remaining = "destroyed", 0
            gs.update_ship(s)
            killed.append(s.name)
    pl = macharia(gs)
    hit = pl is not None and seg(pl.x, pl.y) <= pl.radius + CR
    st = dict(gs.scenario_state or {})
    st["charge"] = 0
    if hit:
        st["planet_destroyed"] = True
    else:
        st["recharge"] = 2        # two Reload Ordnance orders on consecutive turns
    gs.scenario_state = st
    _apply_charging(gs, pk, False)
    if not hit:
        _tag(gs, pk.id, "pk_recharging", True)
    gs.add_log(f"[Macharia's End] the overcharged Armageddon Gun fires: "
               f"{'MACHARIA IS DESTROYED' if hit else 'it misses Macharia'}"
               + (f"; destroyed: {', '.join(killed)}" if killed else ""))
    return {"planet": hit, "destroyed": killed}


def record_reload(gs, ship) -> None:
    """Recharging after a miss: two Reload Ordnance orders passed on two
    consecutive Chaos turns (reading: a Chaos turn without a passed Reload
    Ordnance starts the count again)."""
    if mode(gs) != "macharia":
        return
    pk = planet_killer(gs)
    st = dict(gs.scenario_state or {})
    if pk is None or ship.id != pk.id or st.get("recharge", 0) <= 0:
        return
    step = 1 if getattr(gs, "turn_system", "igougo") == "aa" else 2
    if st["recharge"] < 2 and st.get("reload_turn") != gs.turn_number - step:
        st["recharge"] = 2
    st["recharge"] -= 1
    st["reload_turn"] = gs.turn_number
    gs.scenario_state = st
    if st["recharge"] == 0:
        _tag(gs, pk.id, "pk_recharging", False)
    gs.add_log("[Macharia's End] recharging the Armageddon Gun: "
               + (f"{st['recharge']} more Reload Ordnance to go" if st["recharge"]
                  else "back online"))


def charging(gs, ship) -> bool:
    return mode(gs) == "macharia" and "overcharging" in (ship.special_rules or [])


def order_forbidden(gs, ship, order: str) -> Optional[str]:
    """Macharia's End: no special orders while overcharging; only Reload
    Ordnance while recharging (Brace included in both, reading)."""
    if mode(gs) != "macharia":
        return None
    pk = planet_killer(gs)
    if pk is None or ship.id != pk.id:
        return None
    if charging(gs, ship):
        return "Macharia's End: the Planet Killer can't attempt special orders while charging"
    if recharging(gs) and order != "reload_ordnance":
        return "Macharia's End: while recharging it can only move and Reload Ordnance"
    return None


def _tag(gs, ship_id: str, tag: str, on: bool) -> None:
    sh = gs.get_ship_by_id(ship_id)
    if sh is None:
        return
    rules = [r for r in sh.special_rules if r != tag]
    sh.special_rules = rules + [tag] if on else rules
    gs.update_ship(sh)


def weapon_blocked(ship, weapon) -> bool:
    """Macharia's End (rule tags on the Planet Killer, so the engine's weapon
    check needs no game state): no lances while charging (reading: nor the
    Armageddon Gun fired normally, the charge-up is the gun's); no weapon at
    all while recharging ("it can do nothing except move")."""
    rules = getattr(ship, "special_rules", None) or []
    if "pk_recharging" in rules:
        return True
    return "overcharging" in rules and weapon.get("weapon_type") in ("lance", "armageddon_gun")


def shooting_start(gs, player: int) -> None:
    """At the start of the Chaos shooting phase a fully charged gun fires
    (it must fire during the Shooting Phase; reading: at its start)."""
    if mode(gs) != "macharia" or player != gs.scenario_attacker or not charged(gs):
        return
    pk = planet_killer(gs)
    if pk is not None and not pk.is_destroyed and not pk.is_disengaged:
        fire_overcharged(gs, pk)


def recharging(gs) -> bool:
    return mode(gs) == "macharia" and (gs.scenario_state or {}).get("recharge", 0) > 0


def wants_overcharge(gs, pk) -> bool:
    """AI (judgement): begin charging when the shot will hit. It moves straight
    in this and the next two Chaos turns (at least half speed each, no turns)
    and fires in the third: Macharia's centre must lie within the centre
    hole's reach of its line ahead, and three minimum moves must leave the
    planet within 60cm of the stem without running into it."""
    from .geometry import NOVA_CANNON_CENTER_HOLE_RADIUS_CM as CR
    pl = macharia(gs)
    if pl is None:
        return False
    rad = math.radians(pk.heading)
    dx, dy = pl.x - pk.x, pl.y - pk.y
    along = dx * math.cos(rad) + dy * math.sin(rad) - pk.base_radius
    lateral = abs(-dx * math.sin(rad) + dy * math.cos(rad))
    least = 1.5 * pk.speed               # three moves of at least half speed
    return (lateral <= pl.radius + CR - 0.5 and along - least <= OVERCHARGE_RANGE
            and along - least > pl.radius + 1.0)


def macharia_check_end(gs) -> Optional[dict]:
    from .scenarios import defender
    st = gs.scenario_state or {}
    if st.get("planet_destroyed"):
        return {"winner": gs.scenario_attacker, "reason": "macharia_destroyed",
                "detail": "Macharia is obliterated"}
    pk = planet_killer(gs)
    if pk is not None and not pk.status == "reserve" and (pk.is_destroyed or pk.damage_crippled):
        return {"winner": defender(gs), "reason": "planet_killer_stopped",
                "detail": "the Planet Killer is crippled or destroyed"}
    return None
