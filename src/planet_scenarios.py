"""Exterminatus! (XR p.101-102) and Planetary Assault (XR p.105-106): battles
over a planet, fought partly on the low orbit table (src/low_orbit.py).

Shared: the defender says primary or inner biosphere (not modelled); a planet
(D6: 1 small, 2-5 medium, 6 large) no more than 150cm from a short table edge
(as drawn: its near edge 150cm from the attacker's short edge, the right one,
centred between the long edges; reading); other planets removed; the
attacker within 15cm of the short edge furthest from the planet; a roll-off,
the winner choosing who goes first.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional

PLANET_RADIUS = {"planet_small": 3.0, "planet_medium": 5.0, "planet_large": 8.0}
PLANET_BY_D6 = {1: "planet_small", 2: "planet_medium", 3: "planet_medium",
                4: "planet_medium", 5: "planet_medium", 6: "planet_large"}
PATROL_EDGE_BY_D6 = {1: "left", 2: "top", 3: "top", 4: "bottom", 5: "bottom", 6: "right"}
ASSAULT_RANGE = 30.0        # ships within 30cm of the planet table edge may assault
EXTERMINATUS_RANGE = 45.0   # an Exterminator within 45cm of the planet table edge


def mode(gs) -> str:
    """The scenario mode; Craftworld Assault plays as Planetary Assault (its
    own defences are in src/craftworld.py)."""
    m = getattr(gs, "scenario_mode", "")
    return "planetary_assault" if m == "craftworld_assault" else m


def active(gs) -> bool:
    return mode(gs) in ("exterminatus", "planetary_assault")


def _key(sd: Dict) -> str:
    return sd["squadron_id"] if (sd.get("ship_type") == "escort" and sd.get("squadron_id")) \
        else sd["id"]


def _key_ship(s) -> str:
    return s.squadron_id if (s.ship_type == "escort" and s.squadron_id) else s.id


def place_planet(gs, dice) -> None:
    from .models import Phenomenon
    kind = PLANET_BY_D6[dice.roll_d6(1, "Planet size (1 small, 2-5 medium, 6 large)")[0]]
    r = PLANET_RADIUS[kind]
    w, h = gs.table_width, gs.table_height
    gs.phenomena = [p for p in gs.phenomena if "planet" not in p.get("phenomenon_type", "")]
    x = max(r + 2.0, w - 150.0 - r)
    gs.add_phenomenon(Phenomenon(id="assault_planet", phenomenon_type=kind, x=x, y=h / 2.0,
                                 width=2 * r, height=2 * r, radius=r))


def setup(gs, dice) -> None:
    from .scenarios import _to_reserve, defender
    place_planet(gs, dice)
    st: Dict = {"low_orbit_planet": "assault_planet"}
    dfn = defender(gs)
    units: Dict[str, int] = {}
    for sd in gs.ships:
        if sd["player"] == dfn and "immobile" not in sd.get("special_rules", []):
            units[_key(sd)] = units.get(_key(sd), 0) + sd.get("points_value", 0)
    fleet_pts = sum(sd.get("points_value", 0) for sd in gs.ships if sd["player"] == dfn)
    if mode(gs) == "exterminatus":
        # One capital ship or escort squadron away on patrol per 500pts or
        # portion (judgement: the cheapest units, so the main force guards)
        n = -(-fleet_pts // 500) if fleet_pts else 0
        patrol = [k for k, _v in sorted(units.items(), key=lambda kv: (kv[1], kv[0]))][:n]
        for sd in gs.ships:
            if sd["player"] == dfn and _key(sd) in patrol:
                _to_reserve(sd)
        st["patrol"] = patrol
        st["exterminators"] = nominate_exterminators(gs)
        gs.add_log(f"[Exterminatus] patrols away: {patrol}; Exterminators: "
                   f"{[gs.get_ship_by_id(i).name for i in st['exterminators']]}")
    else:
        # Ships on alert deploy in the gravity well, the rest on patrol
        # (judgement: the dearest half by points on alert)
        order = sorted(units.items(), key=lambda kv: (-kv[1], kv[0]))
        alert, got = [], 0
        for k, v in order:
            if got * 2 >= sum(units.values()):
                break
            alert.append(k)
            got += v
        st["alert"] = alert
        st["assault_points"] = 0.0
        st["assaulted"] = {}
        gs.add_log(f"[Planetary Assault] on alert in the gravity well: {alert}")
    gs.scenario_state = st


# --- Exterminators -------------------------------------------------------------------

def _need_for(ship) -> Optional[int]:
    """The Exterminatus roll a ship needs, or None if it can't be one by
    itself: Space Marine battle barges (virus bombs) and Inquisitorial
    Cruisers with torpedoes 3+; others 4+ once refitted."""
    if "battle barge" in ship.ship_class.lower() and "space_marine_crew" in ship.special_rules:
        return 3
    if ship.ship_class == "Inquisitorial Cruiser" and any(
            w.get("weapon_type") == "torpedo" for w in ship.weapons):
        return 3
    return 4


def nominate_exterminators(gs) -> List[str]:
    """For every 1000pts or portion of the attacker's fleet one capital ship
    becomes an Exterminator, its prow armament replaced by an Armageddon
    weapon (judgement: the ships with most hits). The Planet Killer and an
    Activated Blackstone Fortress count by themselves, alone. Space Marine
    battle barges keep their prow (virus bombs) and need a 3+, as does an
    Inquisitorial Cruiser with torpedoes."""
    att = gs.scenario_attacker
    ships = [s for s in gs.get_ships() if s.player == att and s.ship_type != "escort"
             and not s.is_destroyed]
    special = [s for s in ships if s.ship_class in ("Planet Killer",
                                                    "Activated Blackstone Fortress")]
    if special:
        chosen = special[:1]
    else:
        pts = sum(s.points_value or 0 for s in gs.get_ships() if s.player == att)
        n = -(-pts // 1000) if pts else 0
        chosen = sorted(ships, key=lambda s: (-s.hits_max, -(s.points_value or 0), s.id))[:n]
    for s in chosen:
        need = 4 if s in special else _need_for(s)
        keep_prow = s in special or need == 3
        if not keep_prow:
            s.weapons = [w for w in s.weapons if not _is_prow(w)]
        s.special_rules = [r for r in s.special_rules if not r.startswith("exterminator")] + \
            ["exterminator", f"exterminator:{need}"]
        gs.update_ship(s)
    return [s.id for s in chosen]


def _is_prow(w: Dict) -> bool:
    loc = (w.get("location") or "").lower()
    name = (w.get("name") or "").lower()
    return loc == "prow" or name.startswith("prow")


def is_exterminator(ship) -> bool:
    return "exterminator" in (ship.special_rules or [])


def priority_free(gs, attacker, target) -> bool:
    """Exterminatus!: defending ships may always treat Exterminators as the
    closest enemy for target priority (no test needed to fire at one)."""
    from .scenarios import defender
    return (mode(gs) == "exterminatus" and attacker.player == defender(gs)
            and is_exterminator(target))


def exterminators_left(gs) -> List:
    return [s for s in gs.get_ships() if is_exterminator(s) and not s.is_destroyed
            and s.status not in ("drifting_hulk", "burning_hulk")]


def exterminatus_rolls(gs, dice) -> None:
    """At the start of each attacker's turn (reading: "each turn" as the
    attacker's) every Exterminator within 45cm of the planet table edge rolls
    a D6: on its need (4+, 3+ for virus bombs) the planet is destroyed."""
    from .low_orbit import in_low_orbit, distance_to_planet_edge
    st = gs.scenario_state or {}
    if st.get("planet_destroyed") or dice is None:
        return
    for s in exterminators_left(gs):
        if s.is_disengaged or not in_low_orbit(s):
            continue
        if distance_to_planet_edge(s) > EXTERMINATUS_RANGE:
            continue
        need = next((int(r.split(":")[1]) for r in s.special_rules
                     if r.startswith("exterminator:")), 4)
        r = dice.roll_d6(1, f"{s.name}: Exterminatus on {need}+")[0]
        if r >= need:
            st = dict(gs.scenario_state or {})
            st["planet_destroyed"] = True
            gs.scenario_state = st
            gs.add_log(f"[Exterminatus] {s.name} deploys its Armageddon weapon: the planet "
                       f"is destroyed!")
            return
        gs.add_log(f"[Exterminatus] {s.name} fails to deploy its weapon (rolled {r})")


def patrol_arrivals(gs, player: int, dice) -> List[str]:
    """Exterminatus: at the start of the defender's turn a D6 for each patrol
    (5+ / 4+ / 3+ by its slowest speed), arriving from a random edge (D6: 1
    left, 2-3 top, 4-5 bottom, 6 right)."""
    from .scenarios import reserve_units, place_arrival_at
    came = []
    for i, (k, ships) in enumerate(sorted(reserve_units(gs, player).items())):
        slowest = min(s.speed for s in ships)
        need = 5 if slowest <= 20 else (4 if slowest < 30 else 3)
        r = dice.roll_d6(1, f"Patrol {ships[0].name} arrives on {need}+")[0]
        if r < need:
            continue
        edge = PATROL_EDGE_BY_D6[dice.roll_d6(1, "Patrol arrival edge (1 left, 2-3 top, "
                                                 "4-5 bottom, 6 right)")[0]]
        place_arrival_at(gs, ships, edge, i)
        came.append(", ".join(s.name for s in ships))
        gs.add_log(f"[Exterminatus] patrol arriving from the {edge} edge: {came[-1]}")
    return came


# --- Planetary Assault ---------------------------------------------------------------

def assault_capacity(ship) -> float:
    """Twice the ship's transport capacity; capital ships count at least ½."""
    from .scenarios import transport
    cap = transport(ship)
    if ship.ship_type != "escort":
        cap = max(0.5, cap)
    return 2.0 * cap


def can_assault(gs, ship) -> bool:
    """An attacking capital ship or convoy vessel within 30cm of the planet
    table edge, not boarding or being boarded."""
    from .low_orbit import in_low_orbit, distance_to_planet_edge
    from .scenarios import transport
    if mode(gs) != "planetary_assault" or ship.player != gs.scenario_attacker:
        return False
    if ship.is_destroyed or ship.is_disengaged or not in_low_orbit(ship):
        return False
    if ship.ship_type == "escort" and transport(ship) <= 0:
        return False
    if getattr(ship, "aa_locked", False) or "boarding" in (ship.special_order or ""):
        return False
    return distance_to_planet_edge(ship) <= ASSAULT_RANGE


def declare_assault(gs, ship) -> float:
    """The ship assaults the planet: it can't shoot, launch ordnance or
    teleport for the rest of the turn; the attacker scores its points."""
    pts = assault_capacity(ship)
    from .craftworld import filter_assault_points
    pts = filter_assault_points(gs, pts)       # Craftworld Assault: the fortresses
    st = dict(gs.scenario_state or {})
    st["assault_points"] = st.get("assault_points", 0.0) + pts
    done = dict(st.get("assaulted", {}))
    done[ship.id] = gs.turn_number
    st["assaulted"] = done
    gs.scenario_state = st
    ship.has_fired = True
    ship.special_rules = list(ship.special_rules) + [f"assaulting:{gs.turn_number}"]
    gs.update_ship(ship)
    gs.add_log(f"[Planetary Assault] {ship.name} assaults the planet: +{pts:g} assault points "
               f"({st['assault_points']:g})")
    return pts


def assaulting(gs, ship) -> bool:
    return f"assaulting:{gs.turn_number}" in (ship.special_rules or [])


def record_landing(gs, ship) -> None:
    """Escort-sized convoy ships that land score on that turn (as if within
    30cm), not later; the defender still scores them as disengaged."""
    from .scenarios import transport
    if mode(gs) != "planetary_assault" or ship.player != gs.scenario_attacker:
        return
    if ship.ship_type == "escort" and transport(ship) > 0:
        declare_assault(gs, ship)


def assault_total(gs) -> float:
    """Assault points + 1 per full 500 VP the attacker scored - 1 per 500 VP
    (or portion) the defender scored; holding the field, each attacking
    capital ship and convoy ship on the table, uncrippled, scores once more."""
    from .victory_points import calculate_victory_points, _holds_field
    from .scenarios import defender
    st = gs.scenario_state or {}
    vp = calculate_victory_points(gs)
    att, dfn = gs.scenario_attacker, defender(gs)
    total = st.get("assault_points", 0.0)
    total += vp[att]["total"] // 500
    total -= -(-vp[dfn]["total"] // 500)
    if _holds_field(att, gs.get_ships()):
        from .scenarios import transport
        for s in gs.get_ships():
            if (s.player == att and not s.is_destroyed and not s.is_disengaged
                    and not s.damage_crippled
                    and (s.ship_type != "escort" or transport(s) > 0)):
                total += assault_capacity(s)
    return total


def assault_result(total: float) -> str:
    if total >= 10:
        return "Attacker's Victory"
    if total >= 6:
        return "Attacker's Marginal Win"
    if total >= 2:
        return "Defender's Marginal Win"
    return "Defender's Victory"


# --- game end and victory -------------------------------------------------------------

def check_end(gs) -> Optional[dict]:
    from .scenarios import defender
    st = gs.scenario_state or {}
    if mode(gs) == "exterminatus":
        if st.get("planet_destroyed"):
            return {"winner": gs.scenario_attacker, "reason": "exterminatus",
                    "detail": "the planet is destroyed"}
        if st.get("exterminators") and not exterminators_left(gs):
            return {"winner": defender(gs), "reason": "exterminators_destroyed",
                    "detail": "every Exterminator is destroyed"}
    if mode(gs) == "planetary_assault" and st.get("assault_points", 0) >= 10:
        total = assault_total(gs)
        return {"winner": gs.scenario_attacker if total >= 6 else defender(gs),
                "reason": "assault_points", "detail": f"{assault_result(total)} ({total:g})"}
    return None


def winner(gs) -> Optional[int]:
    from .scenarios import defender
    from .victory_points import _holds_field
    st = gs.scenario_state or {}
    if mode(gs) == "exterminatus":
        if st.get("planet_destroyed"):
            return gs.scenario_attacker
        if st.get("exterminators") and not exterminators_left(gs):
            return defender(gs)
        if _holds_field(gs.scenario_attacker, gs.get_ships()):
            return gs.scenario_attacker
        if _holds_field(defender(gs), gs.get_ships()):
            return defender(gs)
        return None
    total = assault_total(gs)
    return gs.scenario_attacker if total >= 6 else defender(gs)


def force_errors(gs) -> List[str]:
    from .scenarios import transport
    if mode(gs) != "planetary_assault":
        return []
    att = gs.scenario_attacker
    pts = sum(s.points_value or 0 for s in gs.get_ships())
    need = 2 * (-(-pts // 500)) if pts else 0
    cap = sum(transport(s, building=True) for s in gs.get_ships() if s.player == att)
    if cap < need:
        return [f"Planetary Assault: the attacker must take {need} transport capacity "
                f"(2 per 500pts or portion of the fleets), has {cap:g}"]
    return []


# --- deployment -----------------------------------------------------------------------

def zone_rects(gs) -> Dict[int, list]:
    """(left, right, top, bottom) distances: attacker within 15cm of the
    right short edge; Exterminatus defender more than 30cm from every edge;
    Planetary Assault defender: alert ships in the gravity well (its bounding
    square), patrols more than 30cm from every edge (placement_errors tells
    them apart)."""
    from .scenarios import defender
    w, h = gs.table_width, gs.table_height
    att = gs.scenario_attacker
    rects = {att: [(w - 15, 0, 0, 0)], defender(gs): [(30, 30, 30, 30)]}
    if mode(gs) == "planetary_assault":
        pl = next((p for p in gs.get_phenomena() if p.id == "assault_planet"), None)
        if pl is not None:
            well = pl.gravity_well_radius
            rects[defender(gs)].append((max(0.0, pl.x - well), max(0.0, w - pl.x - well),
                                        max(0.0, h - pl.y - well), max(0.0, pl.y - well)))
    return rects


def placement_errors(gs, group, positions) -> List[str]:
    from .scenarios import defender
    if mode(gs) != "planetary_assault" or not group or group[0].player != defender(gs):
        return []
    pl = next((p for p in gs.get_phenomena() if p.id == "assault_planet"), None)
    alert = set((gs.scenario_state or {}).get("alert", []))
    errs = []
    for s, (x, y) in zip(group, positions):
        on_alert = _key_ship(s) in alert
        in_well = pl is not None and math.hypot(x - pl.x, y - pl.y) <= pl.gravity_well_radius
        inner = 30 <= x <= gs.table_width - 30 and 30 <= y <= gs.table_height - 30
        if on_alert and not in_well:
            errs.append(f"Planetary Assault: {s.name} is on alert, in the gravity well")
        if not on_alert and not inner:
            errs.append(f"Planetary Assault: {s.name} is on patrol, 30cm from every edge")
    return errs


def auto_positions(gs, group, placed):
    from .scenarios import defender as _defender
    if not group:
        return None
    pl = next((p for p in gs.get_phenomena() if p.id == "assault_planet"), None)
    if group[0].player == gs.scenario_attacker:
        k = sum(1 for p in placed if p.player == group[0].player)
        x = gs.table_width - 7.0
        return [(x, gs.table_height / 2.0 + (-1) ** (k + i) * 8.0 * ((k + i + 1) // 2))
                for i in range(len(group))]
    if group[0].player == _defender(gs) and pl is not None:
        alert = set((gs.scenario_state or {}).get("alert", []))
        k = sum(1 for p in placed if p.player == group[0].player)
        if mode(gs) == "planetary_assault" and _key_ship(group[0]) in alert:
            rr = pl.radius + 10.0
            return [(pl.x + rr * math.cos(math.radians(40.0 * (k + i) - 60)),
                     pl.y + rr * math.sin(math.radians(40.0 * (k + i) - 60)))
                    for i in range(len(group))]
        # between the planet and the attacker's edge
        x = min(gs.table_width - 31.0, pl.x + pl.gravity_well_radius + 10.0 + 6.0 * (k // 4))
        return [(x, gs.table_height / 2.0 - 15.0 + 10.0 * ((k + i) % 4))
                for i in range(len(group))]
    return None


def turn_start(gs, player: int, dice) -> None:
    """Exterminatus rolls (the attacker's turn), patrols (the defender's)."""
    from .scenarios import defender
    if mode(gs) == "exterminatus":
        if player == gs.scenario_attacker:
            exterminatus_rolls(gs, dice)
        elif player == defender(gs):
            patrol_arrivals(gs, player, dice)


# --- AI choices (judgement, first forms) ---------------------------------------------

def wants_low_orbit(gs, ship) -> bool:
    """Whether a ship in the gravity well enters low orbit (the AI; also the
    default for a human without a prompt): Exterminators and, in Planetary
    Assault, attacking capital ships and convoy ships always; any other ship
    when an enemy ship is in low orbit (to fight it there)."""
    from .low_orbit import in_low_orbit
    from .scenarios import transport
    if mode(gs) == "exterminatus" and is_exterminator(ship):
        return True
    if (mode(gs) == "planetary_assault" and ship.player == gs.scenario_attacker
            and (ship.ship_type != "escort" or transport(ship) > 0)):
        return True
    return any(in_low_orbit(s) and s.player != ship.player and not s.is_destroyed
               and not s.is_disengaged for s in gs.get_ships())


ASSAULT_POINT_WEIGHT = 0.05   # judgement: 10 assault points ~ half the points on the table


def assault_point_vp(gs) -> float:
    from .scenarios import table_points
    return ASSAULT_POINT_WEIGHT * table_points(gs)


def kill_bonus_vp(gs, ship) -> float:
    """AI: an Exterminator's kill is worth the planet (half the points on the
    table, judgement, shared out); an assaulting ship its assault points for
    the turns it could keep scoring (judgement: two)."""
    from .scenarios import table_points, transport
    if mode(gs) == "exterminatus" and is_exterminator(ship):
        return 0.5 * table_points(gs) / max(1, len(exterminators_left(gs)))
    if (mode(gs) == "planetary_assault" and ship.player == gs.scenario_attacker
            and (ship.ship_type != "escort" or transport(ship) > 0)):
        return 2.0 * assault_capacity(ship) * assault_point_vp(gs)
    return 0.0


def shooting_start(gs, player: int, ask=None) -> None:
    """At the start of the attacker's shooting phase its eligible ships may
    assault the planet instead of fighting (the AI always does, judgement:
    the points outweigh a turn of fire; a human answers `ask(ship)`)."""
    if mode(gs) != "planetary_assault" or player != gs.scenario_attacker:
        return
    ai = getattr(gs, "ai_spectator", False) or getattr(gs, "ai_player", None) == player
    for s in gs.get_ships():
        if s.player == player and can_assault(gs, s) and not assaulting(gs, s):
            if ai or ask is None or ask(s):
                declare_assault(gs, s)
