"""Booklet scenarios (bfgxr/rules/14_scenarios.md; CLAUDE.md To do 7), pure
logic. First slice: the scenario registry (set-up zones, first turn, game end,
victory) with the matched-play Confrontation and Domination (XR p.117,
p.125-126). The older generic modes (kill the admiral, destroy / protect a
ship, capture the artefact) stay in `scenario.py`; `GameState.scenario_mode`
names either kind.

Coordinates: the engine's frame (x right, y up, player 1's default edge at
y = 0). The booklet's deployment diagrams are drawn with their top edge at
y = table height. Domination's diagrams are for a 180 x 120cm table; every
position here is measured from a table edge or the centre, as the diagrams
dimension it, so a different table size keeps the same distances.

Readings to confirm with the owner are marked "reading"."""
import math
from typing import Dict, List, Optional, Tuple

from .deployment import DeploymentZone

CONTROL_RANGE = 15.0        # Domination: within 15cm of the marker centre (to the stem)
DOMINATION_TARGET = 10      # ...the game ends when a player has 10 objective points

# key -> booklet facts the engine plays
SCENARIOS: Dict[str, Dict] = {
    "cruiser_clash": {
        "name": "Cruiser Clash (XR p.84)",
        "first_turn": "roll_off",
        "end": "fleet_gone",
        "victory": "damage_points",
        "game_turns": 8,
    },
    "chance_encounter": {
        "name": "Chance Encounter (XR p.88)",
        "first_turn": "defender_choice",
        "end": "fleet_gone",
        "victory": "chance_encounter",
        "game_turns": 6,
    },
    "raiders": {
        "name": "The Raiders (XR p.91)",
        "first_turn": "attacker",
        "end": "fleet_gone",
        "victory": "vp",
        "game_turns": 8,
    },
    "blockade_run": {
        "name": "Blockade Run (XR p.92)",
        "first_turn": "roll_off",
        "end": "fleet_gone",
        "victory": "vp",
        "game_turns": 6,
    },
    "the_bait": {
        "name": "The Bait (XR p.86)",
        "first_turn": "defender",
        "end": "fleet_gone",
        "victory": "vp",
    },
    "rearguard": {
        "name": "Rearguard Attack (XR p.97)",
        "first_turn": "attacker",
        "end": "fleet_gone",
        "victory": "vp",
        "game_turns": 8,
    },
    "alien_intervention": {
        "name": "Alien Intervention (XR p.103)",
        "first_turn": "roll_2d6_vs_d6",
        "end": "fleet_gone",
        "victory": "vp",
        "game_turns": 8,
    },
    "surprise_attack": {
        "name": "Surprise Attack (XR p.104)",
        "first_turn": "attacker",
        "end": "fleet_gone",
        "victory": "vp",
    },
    "navigate_storm": {
        "name": "Navigate the Storm (XR p.98)",
        "first_turn": "attacker_choice",
        "end": "fleet_gone_or_no_cargo",
        "victory": "navigate_storm",
    },
    "convoy_narrative": {
        "name": "Convoy (XR p.94-95, narrative)",
        "first_turn": "defender",
        "end": "convoy_narrative",
        "victory": "convoy_narrative",
    },
    "destroy_docks": {
        "name": "Destroy the Docks (XR p.99)",
        "first_turn": "roll_2d6_vs_d6",
        "end": "fleet_gone",
        "victory": "destroy_docks",
        "game_turns": 8,
    },
    "escalating_engagement": {
        "name": "Escalating Engagement (XR p.107)",
        "first_turn": "roll_off",
        "end": "fleet_gone",
        "victory": "vp",
    },
    "fleet_engagement": {
        "name": "Fleet Engagement (XR p.108-109)",
        "first_turn": "roll_off",
        "end": "fleet_gone",
        "victory": "vp",
    },
    "confrontation": {
        "name": "Confrontation (XR p.117)",
        "first_turn": "attacker",
        "end": "fleet_gone",            # one fleet disengages or is destroyed
        "victory": "vp",
    },
    "ambush": {
        "name": "Ambush (XR p.119)",
        "first_turn": "attacker",
        "end": "fleet_gone",
        "victory": "vp",
    },
    "rescue": {
        "name": "Rescue (XR p.122)",
        "first_turn": "defender",
        "end": "fleet_gone",
        "victory": "vp",
    },
    "warp_storm": {
        "name": "Warp Storm (XR p.123)",
        "first_turn": "attacker",
        "end": "fleet_gone",
        "victory": "vp",
    },
    "line_breaker": {
        "name": "Line Breaker (XR p.118)",
        "first_turn": "attacker",
        "end": "fleet_gone_or_breakthrough",
        "victory": "line_breaker",
    },
    "space_assault": {
        "name": "Space Assault (XR p.121)",
        "first_turn": "attacker",
        "end": "fleet_gone",
        "victory": "vp",
    },
    "convoy_matched": {
        "name": "Convoy (XR p.120, matched play)",
        "first_turn": "defender",
        "end": "fleet_gone_or_no_cargo",
        "victory": "vp",
    },
    "planet_strike": {
        "name": "Planet Strike (XR p.124)",
        "first_turn": "attacker",
        "end": "fleet_gone",
        "victory": "planet_strike",
    },
    "domination": {
        "name": "Domination (XR p.125-126)",
        "first_turn": "attacker",
        "end": "fleet_gone_or_points",
        "victory": "objective_points",
    },
}


def is_booklet_scenario(gs) -> bool:
    return getattr(gs, "scenario_mode", "standard") in SCENARIOS


def first_player(gs) -> Optional[int]:
    """The player the scenario says takes the first turn (None: roll off, s.2)."""
    sc = SCENARIOS.get(getattr(gs, "scenario_mode", ""))
    if sc and sc.get("first_turn") == "attacker":
        return gs.scenario_attacker
    if sc and sc.get("first_turn") == "defender":
        return 3 - gs.scenario_attacker
    return None


def _group_key_d(sd: Dict) -> str:
    return sd["squadron_id"] if (sd.get("ship_type") == "escort" and sd.get("squadron_id")) \
        else sd["id"]


# --- Reinforcements (The Bait, Rearguard Attack) ------------------------------------
RESERVE = "reserve"


def _to_reserve(sd: Dict) -> None:
    """Hold a ship off the table as a reinforcement: everything that ignores
    disengaged ships ignores it until it arrives."""
    sd["status"] = RESERVE
    sd["is_disengaged"] = True


def _main_faction(gs, player: int) -> Optional[str]:
    pts: Dict[str, int] = {}
    for s in gs.get_ships():
        if s.player == player and s.faction != "support_assets":
            pts[s.faction] = pts.get(s.faction, 0) + (s.points_value or 0)
    return max(pts, key=pts.get) if pts else None


def _place_planet(gs, kind: str, r: float, x: float, y: float) -> None:
    from .models import Phenomenon
    gs.phenomena = [p for p in gs.phenomena if p.get("id") != "scenario_planet"]
    gs.add_phenomenon(Phenomenon(id="scenario_planet", phenomenon_type=kind, x=x, y=y,
                                 width=2 * r, height=2 * r, radius=r))


# --- Surprise Attack: standby -------------------------------------------------------

def on_standby(gs, ship) -> bool:
    """Surprise Attack: a defending ship still on standby can't move, shoot,
    launch ordnance, board or teleport (it may brace, repair and use its
    turrets against ordnance)."""
    if getattr(gs, "scenario_mode", "") != "surprise_attack":
        return False
    return _group_key(ship) in (gs.scenario_state or {}).get("standby", [])


def _standby_tests(gs, dice) -> None:
    """At the start of the defender's turn each ship or squadron on standby
    takes a Leadership test (a squadron once, on its best Ld, reading); a
    pass puts it on full alert, acting normally but without special orders
    that turn."""
    if dice is None or (getattr(gs, "turn_system", "igougo") != "aa"
                        and gs.active_player != defender(gs)):
        return
    st = dict(gs.scenario_state or {})
    keep, alerted = [], dict(st.get("alerted", {}))
    for key in st.get("standby", []):
        ships = [s for s in gs.get_ships() if _group_key(s) == key and not s.is_destroyed]
        if not ships:
            continue
        ld = max(s.leadership for s in ships)
        roll = dice.roll_2d6(f"Surprise Attack: {ships[0].name} goes to full alert (Ld {ld})")
        if roll <= ld:
            alerted[key] = gs.turn_number
            gs.add_log(f"[Surprise Attack] {ships[0].name} goes to full alert (rolled {roll})")
        else:
            keep.append(key)
    st["standby"], st["alerted"] = keep, alerted
    gs.scenario_state = st


def is_reserve(ship) -> bool:
    return getattr(ship, "status", "") == RESERVE


def bait_unit(gs) -> Optional[str]:
    """The Bait: the pursued ship or squadron (worth up to 250pts). Kept in
    scenario_state when chosen; otherwise (reading) the defender's dearest
    unit within 250pts, or its cheapest."""
    st = gs.scenario_state or {}
    if st.get("fleeing"):
        return st["fleeing"]
    units: Dict[str, int] = {}
    for sd in gs.ships:
        if sd["player"] == defender(gs):
            units[_group_key_d(sd)] = units.get(_group_key_d(sd), 0) + sd.get("points_value", 0)
    if not units:
        return None
    fits = [k for k, v in units.items() if v <= 250]
    return max(fits, key=units.get) if fits else min(units, key=units.get)


def reserve_units(gs, player: int) -> Dict[str, list]:
    out: Dict[str, list] = {}
    for s in gs.get_ships():
        if s.player == player and is_reserve(s):
            out.setdefault(_group_key(s), []).append(s)
    return out


def entry_edge(gs) -> Optional[str]:
    """The edge reinforcements enter from: The Bait the short edge in front of
    the pursued ship (the right one), Rearguard Attack the sunward table edge
    (the left one, as the diagram draws it)."""
    mode = getattr(gs, "scenario_mode", "")
    if mode == "alien_intervention":
        return (gs.scenario_state or {}).get("ally_edge", "top")
    if mode == "convoy_narrative":
        return (gs.scenario_state or {}).get("entry_edge", "left")
    return {"the_bait": "right", "rearguard": "left", "destroy_docks": "top"}.get(mode)


def place_arrival(gs, ships, index: int = 0) -> None:
    """Put an arriving unit on the table at the entry edge, facing in, stacked
    along the edge from its middle (each later unit further along)."""
    edge = entry_edge(gs)
    w, h = gs.table_width, gs.table_height
    occupied = [s for s in gs.get_ships() if not s.is_destroyed and not s.is_disengaged]
    off = 0
    centre = (gs.scenario_state or {}).get("entry_y", h / 2.0) \
        if getattr(gs, "scenario_mode", "") == "convoy_narrative" else h / 2.0
    while True:
        y0 = centre + ((-1) ** off) * 8.0 * ((off + 1) // 2)
        pts = [(y0 + 4.0 * i) for i in range(len(ships))]
        r = ships[0].base_radius + 0.1
        if edge in ("top", "bottom"):
            # along a long edge: the stack runs along x, the ships at the edge
            line = [(w / 2.0 + (yy - h / 2.0) * 1.0, (h - r) if edge == "top" else r)
                    for yy in pts]
        else:
            x = r if edge == "left" else (w - r)
            line = [(x, max(5.0, min(h - 5.0, yy))) for yy in pts]
        if all((o.x - px) ** 2 + (o.y - py) ** 2 >= 25.0 for o in occupied for px, py in line) \
                or off > 20:
            break
        off += 1
    facing = {"left": 0.0, "right": 180.0, "top": 270.0, "bottom": 90.0}[edge]
    for s, (px, py) in zip(ships, line):
        s.x, s.y = px, py
        s.heading = facing
        s.status = "active"
        s.is_disengaged = False
        gs.update_ship(s)


def arrivals(gs, player: int, wants=None, dice=None) -> List[str]:
    """Reinforcements may enter on any turn, including the first: offer each
    of `player`'s reserve units; `wants(ship names) -> bool` decides (a
    human's prompt; None or an AI: they all come on at once, judgement).
    Returns the names that arrived."""
    came = []
    if getattr(gs, "scenario_mode", "") == "convoy_narrative":
        if player != defender(gs):
            return came           # the attacker's ships come from contact markers
        from .convoy_narrative import wants_arrival
        inner = wants
        wants = (lambda names, _k=None: True)
        for i, (k, ships) in enumerate(sorted(reserve_units(gs, player).items())):
            names = ", ".join(s.name for s in ships)
            ans = True if inner is None else bool(inner(names))
            if not wants_arrival(gs, player, k, ans):
                gs.add_log(f"[Convoy] {names} held back for the second turn")
                continue
            place_arrival(gs, ships, i)
            came.append(names)
            gs.add_log(f"[Reinforcements] arriving from the {entry_edge(gs)} edge: {names}")
        return came
    if getattr(gs, "scenario_mode", "") == "destroy_docks":
        if player != defender(gs):
            return came
        from .destroy_docks import arrivals as _docks_arrivals
        return _docks_arrivals(gs, player, dice)
    if getattr(gs, "scenario_mode", "") == "alien_intervention":
        # The alien fleet comes as one: a D6 from the defender's 2nd turn on
        # (2: 4+, 3: 3+, 4-5: 2+, 6: automatic), the whole fleet from one
        # long edge (reading: game turns)
        game_turn = gs.turn_number if getattr(gs, "turn_system", "igougo") == "aa" \
            else (gs.turn_number + 1) // 2
        need = {2: 4, 3: 3, 4: 2, 5: 2}.get(game_turn, 1 if game_turn >= 6 else None)
        if need is None or dice is None:
            return came
        if need > 1:
            r = dice.roll_d6(1, f"Alien reinforcements (turn {game_turn}: {need}+)")[0]
            if r < need:
                gs.add_log(f"[Alien Intervention] the allies don't arrive (rolled {r})")
                return came
        ships = [s for us in reserve_units(gs, player).values() for s in us]
        place_arrival(gs, ships)
        names = ", ".join(s.name for s in ships)
        gs.add_log(f"[Reinforcements] arriving from the {entry_edge(gs)} edge: {names}")
        return [names]
    for i, (_k, ships) in enumerate(sorted(reserve_units(gs, player).items())):
        names = ", ".join(s.name for s in ships)
        if wants is not None and not wants(names):
            continue
        place_arrival(gs, ships, i)
        came.append(names)
        gs.add_log(f"[Reinforcements] arriving from the {entry_edge(gs)} edge: {names}")
    return came


def _group_key(ship) -> str:
    return ship.squadron_id if (ship.ship_type == "escort" and ship.squadron_id) else ship.id


def _dice_for(gs, player: int, dice):
    """An AI-controlled player's scenario rolls are made automatically (in
    "mixed" dice mode the human isn't asked to roll for the AI)."""
    if dice is None:
        return None
    if getattr(gs, "ai_spectator", False) or getattr(gs, "ai_player", None) == player:
        from .dice import DiceRoller
        return DiceRoller(mode="auto")
    return dice


def turn_start(gs, dice=None) -> None:
    """At the start of each turn: reinforcements may arrive (The Bait,
    Rearguard Attack: the player whose turn it is, both players in an
    alternate-activation round), and The Raiders' / Rearguard's defender gets
    its Ld back after its D6 turns of reduced alert (reading: game turns, both
    players' turns)."""
    mode = getattr(gs, "scenario_mode", "")
    if mode == "destroy_docks":
        from .destroy_docks import lay_orbital_mines
        lay_orbital_mines(gs)
    if entry_edge(gs):
        hook = getattr(gs, "reserve_hook", None)
        players = (1, 2) if getattr(gs, "turn_system", "igougo") == "aa" else (gs.active_player,)
        for p in players:
            if reserve_units(gs, p):
                arrivals(gs, p, (lambda names, p=p: hook(p, names)) if hook else None,
                         _dice_for(gs, p, dice))
    if mode == "surprise_attack":
        _standby_tests(gs, _dice_for(gs, defender(gs), dice))
    if mode == "convoy_narrative":
        from .convoy_narrative import attacker_turn_start, record_start_positions
        players = (1, 2) if getattr(gs, "turn_system", "igougo") == "aa" else (gs.active_player,)
        for p in players:
            if p == defender(gs):
                record_start_positions(gs, p)
            else:
                attacker_turn_start(gs, p, dice)
    if mode == "navigate_storm":
        from .navigate_storm import turn_start as _storm_start
        players = (1, 2) if getattr(gs, "turn_system", "igougo") == "aa" else (gs.active_player,)
        for p in players:
            _storm_start(gs, p)
    if mode == "escalating_engagement":
        from .escalating import turn_start as _ee_turn_start
        players = (1, 2) if getattr(gs, "turn_system", "igougo") == "aa" else (gs.active_player,)
        for p in players:
            _ee_turn_start(gs, p, _dice_for(gs, p, dice))
    if mode not in ("raiders", "rearguard"):
        return
    st = dict(gs.scenario_state or {})
    n = st.get("alert_turns")
    if not n or st.get("alert_restored"):
        return
    limit = n if getattr(gs, "turn_system", "igougo") == "aa" else 2 * n
    if gs.turn_number > limit:
        for sd in gs.ships:
            if sd["player"] == defender(gs) and sd.get("leadership"):
                sd["leadership"] = min(10, sd["leadership"] + 1)
        st["alert_restored"] = True
        gs.scenario_state = st
        gs.add_log("[The Raiders] the defender is fully alert again (+1 Ld)")


def roll_for_choice(gs, dice) -> Optional[int]:
    """Alien Intervention: the attacker rolls 2D6, the defender 1D6; the
    higher total chooses to go first or second (reading: ties re-rolled)."""
    sc = SCENARIOS.get(getattr(gs, "scenario_mode", ""))
    if not sc or sc.get("first_turn") != "roll_2d6_vs_d6":
        return None
    while True:
        a = dice.roll_2d6("Attacker's roll for the first turn (2D6)")
        d = dice.roll_d6(1, "Defender's roll for the first turn (D6)")[0]
        if a != d:
            return gs.scenario_attacker if a > d else defender(gs)


# --- Fleet Engagement: formations and set-ups A-D ------------------------------------
FORMATIONS = ("sphere", "wedge", "cross")
# (your formation, the opponent's) -> the possible results for you:
# (set-up, your role) with role "atk" / "def" / "either" (wedge v wedge: the
# chooser picks) / None (set-up B: no roles)
_FORMATION_TABLE = {
    ("sphere", "sphere"): [("B", None)],
    ("sphere", "wedge"): [("A", "atk"), ("C", "atk")],
    ("sphere", "cross"): [("A", "atk"), ("D", "atk")],
    ("wedge", "sphere"): [("A", "def"), ("C", "def")],
    ("wedge", "wedge"): [("D", "atk"), ("D", "def")],
    ("wedge", "cross"): [("B", None)],
    ("cross", "sphere"): [("A", "def"), ("D", "def")],
    ("cross", "wedge"): [("B", None)],
    ("cross", "cross"): [("B", None)],
}


def formation_bonus(gs, player: int) -> int:
    """+1 each for the fleet with the fastest ship, the best commander (by
    Ld) and the most escorts (reading: a tie gives neither the bonus)."""
    def stat(p, f):
        return f([s for s in gs.get_ships() if s.player == p and not s.is_disengaged
                  or s.player == p and is_reserve(s)])
    fast = {p: stat(p, lambda ss: max((s.speed for s in ss), default=0)) for p in (1, 2)}
    ld = {p: stat(p, lambda ss: max((s.leadership for s in ss if s.is_flagship),
                                    default=max((s.leadership for s in ss), default=0)))
          for p in (1, 2)}
    esc = {p: stat(p, lambda ss: sum(1 for s in ss if s.ship_type == "escort")) for p in (1, 2)}
    o = 3 - player
    return sum(1 for d in (fast, ld, esc) if d[player] > d[o])


def resolve_formations(gs, f1: str, f2: str, dice, choose=None) -> Dict:
    """Compare the two secret formations (p.108): the result set-up and
    who attacks. Where two results are possible each player rolls a D6 +
    `formation_bonus` (ties re-rolled, reading); the winner chooses from the
    results for its own formation (`choose(player, options) -> option`;
    default: the first). Set-up B has no attacker: the chooser (or player 1)
    takes the bottom zone (reading). Stored in `gs.scenario_state`."""
    forms = {1: f1, 2: f2}
    opts = {p: _FORMATION_TABLE[(forms[p], forms[3 - p])] for p in (1, 2)}
    chooser = 1
    if len(opts[1]) > 1:
        while True:
            r = {p: dice.roll_d6(1, f"Fleet Engagement: player {p}'s set-up roll")[0]
                 + formation_bonus(gs, p) for p in (1, 2)}
            if r[1] != r[2]:
                chooser = 1 if r[1] > r[2] else 2
                break
    pick = (choose or (lambda p, o: o[0]))(chooser, opts[chooser])
    setup, role = pick
    if role == "atk":
        attacker = chooser
    elif role == "def":
        attacker = 3 - chooser
    else:
        attacker = chooser                       # set-up B: the chooser's fleet below
    gs.scenario_attacker = attacker
    st = {"formations": {"1": f1, "2": f2}, "setup": setup, "chooser": chooser}
    gs.scenario_state = st
    gs.add_log(f"[Fleet Engagement] formations {f1} v {f2}: set-up {setup}, "
               f"player {attacker} {'attacks' if setup != 'B' else 'deploys below'}")
    return st


def _fe_rects(gs):
    """Fleet Engagement's zones: [(player, (left, right, top, bottom), heading)]
    in the diagram frame (top = y at the table height)."""
    w, h = gs.table_width, gs.table_height
    st = gs.scenario_state or {}
    a = gs.scenario_attacker
    d = 3 - a
    s = st.get("setup")
    if s == "A":
        return [(d, (w / 2 - 30, w / 2 - 30, 0, h - 30), 270.0),
                (a, (0, w - 30, 0, 0), 45.0),
                (a, (30, 30, h - 30, 0), 90.0),
                (a, (w - 30, 0, 0, 0), 135.0)]
    if s == "B":
        x0 = w / 2 - 67.5
        top = [(d, (x0 + 45 * i, w - x0 - 45 * (i + 1), 0, h - 30), 0.0) for i in range(3)]
        bot = [(a, (x0 + 45 * i, w - x0 - 45 * (i + 1), h - 30, 0), 180.0) for i in range(3)]
        return top + bot
    if s == "C":
        return [(d, (w / 2 - 30, w / 2 - 30, 0, h - 45), 270.0),
                (a, (0, w - 30, 0, 0), 90.0),
                (a, (w - 30, 0, 0, 0), 90.0)]
    if s == "D":
        return [(d, (45, 45, 0, h - 30), 270.0)] + \
            [(a, (w / 3 * i, w - w / 3 * (i + 1), h - 30, 0), 90.0) for i in range(3)]
    return []


def fe_division_at(gs, player: int, x: float, y: float):
    """The Fleet Engagement division (index, heading) containing a point."""
    w, h = gs.table_width, gs.table_height
    i = 0
    for p, (left, right, top, bottom), hd in _fe_rects(gs):
        if p != player:
            continue
        if left <= x <= w - right and bottom <= y <= h - top:
            return i, hd
        i += 1
    return None


def first_turn_chooser(gs) -> Optional[int]:
    """The player the scenario lets choose to go first or second (Chance
    Encounter: the defender), or None."""
    sc = SCENARIOS.get(getattr(gs, "scenario_mode", ""))
    if sc and sc.get("first_turn") == "defender_choice":
        return defender(gs)
    if sc and sc.get("first_turn") == "attacker_choice":
        return gs.scenario_attacker
    return None


def game_turn_limit(gs) -> Optional[int]:
    """The scenario's game length as `GameState.turn_limit` (which counts
    player turns in IGOUGO, rounds in alternate activation)."""
    sc = SCENARIOS.get(getattr(gs, "scenario_mode", ""))
    n = sc.get("game_turns") if sc else None
    if not n:
        return None
    return n if getattr(gs, "turn_system", "igougo") == "aa" else 2 * n


def defender(gs) -> int:
    return 3 - gs.scenario_attacker


# --- Attack ratings (p.78) --------------------------------------------------------
# Faction -> attack rating (the booklet's table and faction fleet lists).
# Readings (no fleet list recorded on the ships): Eldar 3 (Craftworld; Corsair
# lists are 4), Necrons 4 (Harvest; Dynasty 3), Space Marines 3 (Dominion with
# allies of convenience 2).
ATTACK_RATINGS = {
    "imperial_navy_gothic": 2, "chaos": 2, "adeptus_mechanicus": 2, "tau_kororvesh": 2,
    "space_marines": 3, "orks": 3, "eldar": 3, "necrons": 4,
    "dark_eldar": 4, "tyranids": 2,
}
# Factions with more than one list rated differently (sign-off answer 44):
# Corsair Eldar 4 / Craftworld 3, Necron Harvest 4 / Dynasty 3. Without a
# list the first value above stands (reading: Craftworld 3, Harvest 4).
LIST_ATTACK_RATINGS = {"corsair": 4, "craftworld": 3, "harvest": 4, "dynasty": 3}


def attack_rating(gs, player: int) -> int:
    """A fleet's attack rating: its main faction's (by points). Inquisition
    fleets: a Grey Knights banisher fleet 3, 2 when more than half its ships
    aren't Grey Knights (p.84); a Rogue Trader or Inquisition detachment
    doesn't change the fleet it joins; support assets don't count. A fleet of
    Rogue Traders alone has 3 (both their lists). Tyranids' Pheromone Rage (3)
    waits for the Tyranid rules."""
    ships = [s for s in gs.get_ships() if s.player == player]
    pts: Dict[str, int] = {}
    for s in ships:
        if s.faction != "support_assets":
            pts[s.faction] = pts.get(s.faction, 0) + (s.points_value or 0)
    main = [f for f in pts if f not in ("rogue_traders", "inquisition_grey_knights")]
    if main:
        top = max(main, key=pts.get)
        lists = {(getattr(s, "fleet_list", "") or "").lower() for s in ships if s.faction == top}
        for key, rating in LIST_ATTACK_RATINGS.items():
            if any(key in fl for fl in lists):
                return rating
        return ATTACK_RATINGS.get(top, 2)
    if "inquisition_grey_knights" in pts:
        inq = [s for s in ships if s.faction == "inquisition_grey_knights"]
        gk = sum(1 for s in inq if "knights_of_titan" in s.special_rules)
        return 3 if gk * 2 >= len([s for s in ships if s.faction != "support_assets"]) else 2
    if "rogue_traders" in pts:
        return 3            # both Rogue Trader lists say "Attack rating 3"
    return 2


def roll_attack_ratings(gs, dice) -> int:
    """Each player rolls D6s equal to the fleet's attack rating; the best die
    wins, ties compare the next highest and so on, and a player who runs out
    of dice loses; a complete tie is rolled again. Returns the attacker."""
    r = {p: attack_rating(gs, p) for p in (1, 2)}
    while True:
        rolls = {p: sorted(dice.roll_d6(r[p], f"Player {p} attack rating ({r[p]}D6)"),
                           reverse=True) for p in (1, 2)}
        for a, b in zip(rolls[1], rolls[2]):
            if a != b:
                win = 1 if a > b else 2
                break
        else:
            if len(rolls[1]) == len(rolls[2]):
                continue                         # still tied: roll again
            win = 1 if len(rolls[1]) > len(rolls[2]) else 2
        gs.add_log(f"[Scenario] attack ratings: player 1 {rolls[1]}, player 2 "
                   f"{rolls[2]}: player {win} attacks")
        return win


# --- Deployment zones and objective markers -------------------------------------

def _rect(player, w, h, left, right, top, bottom, label) -> DeploymentZone:
    """A zone given as distances in from the left / right edges and down from
    the top edge (diagram frame); converted to engine x / y."""
    return DeploymentZone(player=player, x_min=left, x_max=w - right,
                          y_min=bottom, y_max=h - top, label=label)


def _domination_layout(n: int, w: float, h: float):
    """Deployment n (D6) as (attacker zone rects, defender zone rects,
    objectives), from the six diagrams. Rect args: (left, right, top, bottom)
    insets from the edges; objectives (x, y) in the engine frame."""
    cx, cy = w / 2.0, h / 2.0
    top = lambda d: h - d              # noqa: E731  y of a point d below the top edge
    bot = lambda d: d                  # noqa: E731
    if n == 1:
        att = [(0, 0, 0, h - 30)]
        dfn = [(0, 0, h - 30, 0)]
        obj = [(30, cy), (cx, cy), (w - 30, cy)]
    elif n == 2:
        att = [(0, 60, 0, h - 30)]
        dfn = [(60, 0, h - 30, 0)]
        obj = [(w - 30, top(30)), (cx, cy), (30, bot(30))]
    elif n == 3:
        # L-shapes: attacker bottom-left (45 wide x 30 deep, plus 30 wide up
        # to 45 from the bottom); defender the mirror image top-right
        att = [(0, w - 45, h - 30, 0), (0, w - 30, h - 45, 0)]
        dfn = [(w - 45, 0, 0, h - 30), (w - 30, 0, 0, h - 45)]
        obj = [(30, top(30)), (cx, top(30)), (cx, bot(30)), (w - 30, bot(30))]
    elif n == 4:
        att = [(0, 0, 0, h - 30)]
        dfn = [(0, 0, h - 30, 0)]
        obj = [(45, cy), (w - 45, cy), (cx, top(45)), (cx, bot(45))]
    elif n == 5:
        att = [(0, w - 45, 0, 0)]
        dfn = [(w - 45, 0, 0, 0)]
        obj = [(cx, top(30)), (w - 60, top(30)), (60, bot(30)), (cx, bot(30))]
    elif n == 6:
        att = [(0, w - 45, 0, 0)]
        dfn = [(w - 45, 0, 0, 0)]
        obj = [(cx, top(15)), (cx, cy), (cx, bot(15))]
    else:
        raise ValueError(f"Domination deployment {n} (D6)")
    return att, dfn, obj


def setup_scenario(gs, dice=None, layout: Optional[int] = None) -> None:
    """Before deployment: roll what the scenario needs (Domination: the D6
    deployment diagram) and store it in `gs.scenario_state`."""
    mode = getattr(gs, "scenario_mode", "standard")
    if mode == "domination":
        if layout is None:
            if dice is None:
                from .dice import DiceRoller
                dice = DiceRoller(mode="auto")
            layout = dice.roll_d6(1, "Domination deployment (D6)")[0]
        _, _, obj = _domination_layout(layout, gs.table_width, gs.table_height)
        gs.scenario_state = {"layout": layout,
                             "objectives": [[round(x, 3), round(y, 3)] for x, y in obj],
                             "points": {"1": 0, "2": 0}}
        gs.add_log(f"[Domination] deployment {layout}: {len(obj)} objective markers")
    elif mode == "ambush":
        # The defender is caught unawares: no ordnance loaded (as if expended),
        # Reload Ordnance needed before launching or firing any
        for sd in gs.ships:
            if sd["player"] == defender(gs):
                sd["ordnance_loaded_torps"] = False
                sd["ordnance_loaded_craft"] = False
                sd["ordnance_loaded_mines"] = False
        gs.scenario_state = {"ambush": True}
        gs.add_log("[Ambush] the defender starts with no ordnance loaded")
    elif mode == "rescue":
        flag = rescue_flagship(gs)
        gs.scenario_state = {"flagship": flag.id if flag else None}
        if flag is not None:
            gs.add_log(f"[Rescue] the defending flagship is {flag.name}")
    elif mode == "convoy_matched":
        gs.scenario_state = {"had_cargo": cargo_on_table(gs, defender(gs)) > 0}
    elif mode == "the_bait":
        # The pursued ship or squadron (chosen, or the AI's pick) stays; the
        # defender's other ships are reinforcements
        flee = bait_unit(gs)
        for sd in gs.ships:
            if sd["player"] == defender(gs) and _group_key_d(sd) != flee:
                _to_reserve(sd)
        gs.scenario_state = {"fleeing": flee}
        gs.add_log(f"[The Bait] the pursued unit is {flee}; the rest are reinforcements")
    elif mode == "rearguard":
        # At least 25% of the defender's points are reinforcements (reading:
        # the cheapest ships / squadrons first, until a quarter is reached),
        # and the defender's reduced alert as in The Raiders
        if dice is None:
            from .dice import DiceRoller
            dice = DiceRoller(mode="auto")
        units: Dict[str, int] = {}
        for sd in gs.ships:
            if sd["player"] == defender(gs) and "immobile" not in sd.get("special_rules", []):
                units[_group_key_d(sd)] = units.get(_group_key_d(sd), 0) + sd.get("points_value", 0)
        total = sum(units.values())
        chosen, got = set(gs.scenario_state.get("reserve_units", []) if gs.scenario_state
                          else []), 0
        if not chosen:
            for k, v in sorted(units.items(), key=lambda kv: kv[1]):
                if got * 4 >= total:
                    break
                chosen.add(k)
                got += v
        for sd in gs.ships:
            if sd["player"] == defender(gs) and _group_key_d(sd) in chosen:
                _to_reserve(sd)
        n = dice.roll_d6(1, "Rearguard Attack: turns of reduced alert (D6)")[0]
        for sd in gs.ships:
            if sd["player"] == defender(gs) and sd.get("leadership"):
                sd["leadership"] = max(1, sd["leadership"] - 1)
        gs.scenario_state = {"alert_turns": n, "alert_restored": False,
                             "reserve_units": sorted(chosen)}
        gs.add_log(f"[Rearguard] reinforcements: {sorted(chosen)}; the defender is at -1 Ld "
                   f"for {n} turn(s)")
    elif mode == "fleet_engagement":
        # The formations are chosen before set-up (GamePanel asks a human and
        # picks at random for the AI, judgement: the three beat each other in
        # a circle); without them, random formations here
        if not (gs.scenario_state or {}).get("setup"):
            import random
            if dice is None:
                from .dice import DiceRoller
                dice = DiceRoller(mode="auto")
            resolve_formations(gs, random.choice(FORMATIONS), random.choice(FORMATIONS), dice)
    elif mode == "convoy_narrative":
        if dice is None:
            from .dice import DiceRoller
            dice = DiceRoller(mode="auto")
        from .convoy_narrative import setup as _cn_setup
        _cn_setup(gs, dice)
    elif mode == "destroy_docks":
        from .destroy_docks import setup as _docks_setup
        _docks_setup(gs, dice)
    elif mode == "navigate_storm":
        from .navigate_storm import setup as _storm_setup
        _storm_setup(gs, dice)
    elif mode == "escalating_engagement":
        if dice is None:
            from .dice import DiceRoller
            dice = DiceRoller(mode="auto")
        from .escalating import setup as _ee_setup
        _ee_setup(gs, dice)
    elif mode == "alien_intervention":
        # The defender's allies of convenience (ships of another faction than
        # its main one) are the alien reinforcements; a planet within 30cm of
        # the centre (reading: medium, just below the centre as drawn)
        main = _main_faction(gs, defender(gs))
        for sd in gs.ships:
            if sd["player"] == defender(gs) and sd.get("faction") not in (main, "support_assets"):
                _to_reserve(sd)
        _place_planet(gs, "planet_medium", 5.0, gs.table_width / 2.0, gs.table_height / 2.0 - 15.0)
        gs.scenario_state = {"ally_edge": "top"}
        gs.add_log("[Alien Intervention] the defender's allies wait off the table")
    elif mode == "surprise_attack":
        # A planet at the centre sized by the battle; D3 of the defender's
        # ships / squadrons on full alert (reading: its dearest units unless
        # chosen), the rest on standby
        if dice is None:
            from .dice import DiceRoller
            dice = DiceRoller(mode="auto")
        pts = sum(s.points_value for s in gs.get_ships() if s.player == defender(gs))
        kind, r = (("planet_small", 3.0) if pts <= 500 else
                   ("planet_medium", 5.0) if pts <= 1500 else ("planet_large", 8.0))
        _place_planet(gs, kind, r, gs.table_width / 2.0, gs.table_height / 2.0)
        n = (dice.roll_d6(1, "Surprise Attack: units on full alert (D3)")[0] + 1) // 2
        units: Dict[str, int] = {}
        for sd in gs.ships:
            if sd["player"] == defender(gs):
                units[_group_key_d(sd)] = units.get(_group_key_d(sd), 0) + sd.get("points_value", 0)
        alert = sorted(units, key=units.get, reverse=True)[:n]
        gs.scenario_state = {"standby": sorted(k for k in units if k not in alert),
                             "alerted": {}}
        gs.add_log(f"[Surprise Attack] on full alert: {alert}; the rest on standby")
    elif mode == "raiders":
        # The defender's reduced state of alert: -1 Ld for the first D6 turns
        if dice is None:
            from .dice import DiceRoller
            dice = DiceRoller(mode="auto")
        n = dice.roll_d6(1, "The Raiders: turns of reduced alert (D6)")[0]
        for sd in gs.ships:
            if sd["player"] == defender(gs) and sd.get("leadership"):
                sd["leadership"] = max(1, sd["leadership"] - 1)
        gs.scenario_state = {"alert_turns": n, "alert_restored": False}
        gs.add_log(f"[The Raiders] the defender is at -1 Ld for {n} turn(s)")
    elif mode == "blockade_run":
        # A D6 for each blockading ship or squadron: which third it deploys in
        if dice is None:
            from .dice import DiceRoller
            dice = DiceRoller(mode="auto")
        thirds = {}
        for s in gs.get_ships():
            if s.player != defender(gs):
                continue
            key = _group_key(s)
            if key not in thirds:
                r = dice.roll_d6(1, f"Blockade Run: {s.name}'s area (D6)")[0]
                thirds[key] = (r + 1) // 2           # 1-2 left, 3-4 middle, 5-6 right
        gs.scenario_state = {"thirds": thirds}
        gs.add_log(f"[Blockade Run] blockade areas: {thirds}")
    elif mode == "cruiser_clash":
        # One player rolls a D6: 1-3 they set up in Fleet A (the top zone),
        # 4-6 in Fleet B (reading: player 1 rolls)
        if dice is None:
            from .dice import DiceRoller
            dice = DiceRoller(mode="auto")
        r = dice.roll_d6(1, "Cruiser Clash: player 1's zone (1-3 Fleet A, 4-6 Fleet B)")[0]
        gs.scenario_state = {"fleet_a": 1 if r <= 3 else 2}
        gs.add_log(f"[Cruiser Clash] player {gs.scenario_state['fleet_a']} sets up in Fleet A")
    elif mode == "chance_encounter":
        flag = chance_flagship(gs)
        gs.scenario_state = {"flagship": flag.id if flag else None}
        if flag is not None:
            gs.add_log(f"[Chance Encounter] the attacking flagship is {flag.name}")
    elif mode == "planet_strike":
        # A large planet centred between the long edges, its far side exactly
        # 45cm from the defender's short edge (the right one); no other planets
        # (reading: planets already placed are removed)
        from .models import Phenomenon
        r = 8.0
        gs.phenomena = [p for p in gs.phenomena if "planet" not in p.get("phenomenon_type", "")]
        gs.add_phenomenon(Phenomenon(id="strike_planet", phenomenon_type="planet_large",
                                     x=gs.table_width - 45.0 + r, y=gs.table_height / 2.0,
                                     width=2 * r, height=2 * r, radius=r))
        gs.scenario_state = {"bombardment": 0}
        gs.add_log("[Planet Strike] a large planet 45cm from the defender's short edge")
    elif mode in SCENARIOS:
        gs.scenario_state = {"started": True}
    limit = game_turn_limit(gs)
    if limit:
        gs.turn_limit = limit           # the scenario's game length


def chance_flagship(gs):
    """Chance Encounter: the attacker's flagship (the one carrying the fleet
    commander; reading: without one marked, its dearest ship)."""
    sid = (gs.scenario_state or {}).get("flagship")
    if sid:
        return gs.get_ship_by_id(sid)
    ships = [s for s in gs.get_ships() if s.player == gs.scenario_attacker
             and not s.is_destroyed]
    flag = next((s for s in ships if s.is_flagship), None)
    return flag or max(ships, key=lambda s: s.points_value, default=None)


def rescue_flagship(gs):
    """Rescue: the defender's fleet commander's capital ship. Reading: without
    a flagship marked, the defender's most expensive capital ship."""
    sid = (gs.scenario_state or {}).get("flagship")
    if sid:
        return gs.get_ship_by_id(sid)
    caps = [s for s in gs.get_ships() if s.player == defender(gs)
            and s.ship_type != "escort" and not s.is_destroyed]
    flag = next((s for s in caps if s.is_flagship), None)
    return flag or max(caps, key=lambda s: s.points_value, default=None)


def fixed_placements(gs) -> Dict[str, Tuple[float, float, float]]:
    """Ships the scenario places itself (not deployed by the player): Rescue's
    flagship at the exact centre, pointing at the defender's short edge (the
    left edge, x = 0, here)."""
    if getattr(gs, "scenario_mode", "") == "rescue":
        flag = rescue_flagship(gs)
        if flag is not None:
            return {flag.id: (gs.table_width / 2.0, gs.table_height / 2.0, 180.0)}
    if getattr(gs, "scenario_mode", "") == "the_bait":
        flee = (gs.scenario_state or {}).get("fleeing")
        ships = [s for s in gs.get_ships() if _group_key(s) == flee]
        # at the centre, facing the right short edge (squadron members stacked)
        return {s.id: (gs.table_width / 2.0, gs.table_height / 2.0 + 4.0 * i, 0.0)
                for i, s in enumerate(ships)}
    if getattr(gs, "scenario_mode", "") == "chance_encounter":
        flag = chance_flagship(gs)
        if flag is not None:
            # on the centre line of the attacker's long edge (the top), 10cm in,
            # facing the defender (reading: facing straight down the table)
            return {flag.id: (gs.table_width / 2.0, gs.table_height - 10.0, 270.0)}
    if getattr(gs, "scenario_mode", "") == "space_assault":
        st = space_station(gs)
        if st is not None:
            # exactly 30cm from the defender's edge, equidistant from the short edges
            return {st.id: (gs.table_width / 2.0, 30.0, 90.0)}
    return {}


PLATFORMS = ("Orbital Weapons Platform", "Orbital Defence Laser Platform",
             "Orbital Torpedo Launcher")


def is_platform(ship) -> bool:
    """Line Breaker's defence platforms (Support Assets)."""
    return any(ship.ship_class.startswith(p) for p in PLATFORMS)


def transport(ship, building: bool = False) -> float:
    """A convoy ship's transport capacity (Support Assets p.64): halved while
    crippled for ships larger than an escort; escort carriers and Q-ships
    count only when assembling the fleet (`building`)."""
    cap = next((float(r.split(":")[1]) for r in ship.special_rules
                if r.startswith("transport:")), 0.0)
    if building:
        return cap
    if "transport_build_only" in ship.special_rules:
        return 0.0
    if ship.ship_type != "escort" and ship.damage_crippled:
        cap /= 2.0
    return cap


def is_convoy(ship) -> bool:
    return any(r.startswith("transport:") for r in ship.special_rules)


def cargo_on_table(gs, player: int) -> float:
    return sum(transport(s) for s in gs.get_ships() if s.player == player and is_convoy(s)
               and not s.is_destroyed and not s.is_disengaged)


def scores_normally(gs, ship) -> bool:
    """False for ships the scenario scores itself (vp_bonus): Convoy's convoy
    ships."""
    if getattr(gs, "scenario_mode", "") == "navigate_storm":
        # Ships evacuated via the exit point don't count towards the attacker
        from .navigate_storm import evacuated
        return not evacuated(gs, ship)
    return not (getattr(gs, "scenario_mode", "") == "convoy_matched" and is_convoy(ship)
                and ship.player == defender(gs))


def strike_planet(gs):
    return next((p for p in gs.get_phenomena() if p.id == "strike_planet"), None)


def in_planet_contact(gs, ship) -> bool:
    """Base contact with Planet Strike's planet marker."""
    pl = strike_planet(gs)
    if pl is None:
        return False
    margin = getattr(gs, "contact_margin_cm", 0.2)
    return ((ship.x - pl.x) ** 2 + (ship.y - pl.y) ** 2
            <= (pl.radius + ship.base_radius + margin) ** 2)


def bombardment_points(gs, ship) -> float:
    """What a ship scores for holding position over the planet: its remaining
    hits plus its total transport capacity."""
    return ship.hits_remaining + transport(ship)


# Planet Strike's table: bombardment points -> the D6 the attacker needs
# (None: the defender wins automatically, 1: the attacker wins automatically)
STRIKE_TABLE = ((5, None), (10, 6), (15, 5), (20, 4), (25, 3), (30, 2))


def strike_need(points_: float) -> Optional[int]:
    for top, need in STRIKE_TABLE:
        if points_ <= top:
            return need
    return 1


def space_station(gs):
    return next((s for s in gs.get_ships() if s.player == defender(gs)
                 and s.ship_class.startswith("Space Station")), None)


def force_errors(gs) -> List[str]:
    """The scenario's force requirements (checked at set-up, warnings only):
    Line Breaker one defence platform per 200pts or portion thereof of the
    defender's fleet; Space Assault a single space station."""
    mode = getattr(gs, "scenario_mode", "")
    ships = [s for s in gs.get_ships() if s.player == defender(gs)]
    if mode == "navigate_storm":
        from .navigate_storm import force_errors as _storm_errors
        return _storm_errors(gs)
    if mode == "destroy_docks":
        from .destroy_docks import force_errors as _docks_errors
        return _docks_errors(gs)
    if mode == "convoy_narrative":
        from .convoy_narrative import force_errors as _cn_errors
        return _cn_errors(gs)
    if mode == "line_breaker":
        pts = sum(s.points_value for s in ships)
        need = -(-pts // 200)
        have = sum(1 for s in ships if is_platform(s))
        if have < need:
            return [f"Line Breaker: the defender needs {need} defence platforms "
                    f"({pts}pts), has {have}"]
    if mode == "planet_strike":
        att = [s for s in gs.get_ships() if s.player == gs.scenario_attacker]
        pts = sum(s.points_value for s in att if not is_convoy(s))
        need = -(-pts // 100)
        have = sum(transport(s, building=True) for s in att if is_convoy(s))
        if have < need:
            return [f"Planet Strike: the attacker needs {need} transport capacity "
                    f"({pts}pts), has {have:g}"]
        return []
    if mode == "convoy_matched":
        convoy = [s for s in ships if is_convoy(s)]
        pts = sum(s.points_value for s in ships if not is_convoy(s))
        need = -(-pts // 100)
        have = sum(transport(s, building=True) for s in convoy)
        errs = []
        if abs(have - need) > 1e-9:
            errs.append(f"Convoy: the defender needs exactly {need} transport capacity "
                        f"({pts}pts), has {have:g}")
        if not any(transport(s) > 0 for s in convoy):
            errs.append("Convoy: at least one convoy ship whose capacity counts in the game")
        return errs
    if mode == "space_assault":
        n = sum(1 for s in ships if s.ship_class.startswith("Space Station"))
        if n != 1:
            return [f"Space Assault: the defender must include a single space station ({n})"]
    return []


def deployment_zones(gs) -> Optional[List[DeploymentZone]]:
    """The scenario's deployment zones (each player's first rect carries any
    others in `extra`), or None for the default 30cm zones."""
    mode = getattr(gs, "scenario_mode", "standard")
    w, h = gs.table_width, gs.table_height
    att_p = gs.scenario_attacker
    if mode == "confrontation":
        # Attacker within 30cm of a long table edge, defender the opposite one
        rects = {att_p: [(0, 0, 0, h - 30)], 3 - att_p: [(0, 0, h - 30, 0)]}
    elif mode == "ambush":
        # Defender more than 30cm from every edge; attacker within 30cm of any
        rects = {3 - att_p: [(30, 30, 30, 30)],
                 att_p: [(0, 0, h - 30, 0), (0, 0, 0, h - 30), (0, w - 30, 0, 0),
                         (w - 30, 0, 0, 0)]}
    elif mode == "rescue":
        # The defender's short edge is the left one (x = 0), the attacker's the right
        rects = {3 - att_p: [(0, w - 30, 0, 0)], att_p: [(w - 30, 0, 0, 0)]}
    elif mode == "warp_storm":
        # Two divisions each in opposite corners (30cm squares): attacker
        # bottom-left and top-right, defender top-left and bottom-right
        rects = {att_p: [(0, w - 30, h - 30, 0), (w - 30, 0, 0, h - 30)],
                 3 - att_p: [(0, w - 30, 0, h - 30), (w - 30, 0, h - 30, 0)]}
    elif mode == "line_breaker":
        # The defender's long edge is the bottom one (y = 0): its fleet within
        # 60cm of it, its platforms more than 30cm from every edge
        # (placement_errors tells them apart); the attacker within 15cm of the top
        rects = {3 - att_p: [(0, 0, h - 60, 0), (30, 30, 30, 30)],
                 att_p: [(0, 0, 0, h - 15)]}
    elif mode == "space_assault":
        # Defender within 30cm of the bottom edge (the station is placed by the
        # scenario, 30cm in and centred); attacker within 30cm of the top
        rects = {3 - att_p: [(0, 0, h - 30, 0)], att_p: [(0, 0, 0, h - 30)]}
    elif mode == "planet_strike":
        # Attacker within 30cm of the left short edge; defender within 45cm of
        # the right one, where the planet is (its defences in the gravity well,
        # the extra rect, placement_errors tells them apart)
        pl = strike_planet(gs)
        well = pl.gravity_well_radius if pl else 38.0
        px, py = (pl.x, pl.y) if pl else (w - 37.0, h / 2.0)
        rects = {att_p: [(0, w - 30, 0, 0)],
                 3 - att_p: [(w - 45, 0, 0, 0),
                             (max(0.0, px - well), max(0.0, w - px - well),
                              max(0.0, h - py - well), max(0.0, py - well))]}
    elif mode == "raiders":
        # Defender more than 30cm from every edge; the attacker moves on from
        # any edge on its first turn (reading: it deploys touching an edge,
        # within a base of it, facing onto the table)
        e = 3.0
        rects = {3 - att_p: [(30, 30, 30, 30)],
                 att_p: [(0, 0, h - e, 0), (0, 0, 0, h - e), (0, w - e, 0, 0),
                         (w - e, 0, 0, 0)]}
    elif mode == "navigate_storm":
        # Defender: the bottom-left quarter, 20cm in from the left edge;
        # attacker: the top-right quarter, 10cm down from the top, short of
        # the exit point (the right edge's 20cm strip)
        rects = {3 - att_p: [(20, w / 2.0, h / 2.0, 0)],
                 att_p: [(w / 2.0, 20, 10, h / 2.0)]}
    elif mode == "convoy_narrative":
        # Nobody deploys: the attacker's forces are contact markers, the
        # convoy moves on from its entry point (zones kept for the panels)
        rects = {att_p: [(30, 30, 30, 30)], 3 - att_p: [(0, w - 3, 0, 0)]
                 if (gs.scenario_state or {}).get("entry_edge", "left") == "left"
                 else [(w - 3, 0, 0, 0)]}
    elif mode == "destroy_docks":
        from .destroy_docks import zone_rects as _docks_rects
        rects = _docks_rects(gs)
    elif mode == "escalating_engagement":
        from .escalating import zone_rects
        rects = zone_rects(gs)
        if not rects:
            return None
    elif mode == "fleet_engagement":
        if not (gs.scenario_state or {}).get("setup"):
            return None
        rects = {1: [], 2: []}
        for p, r, _hd in _fe_rects(gs):
            rects[p].append(r)
    elif mode == "alien_intervention":
        # Defender within 30cm of the centre line (a 60cm strip); attacker
        # within 20cm of either short edge
        rects = {3 - att_p: [(w / 2.0 - 30, w / 2.0 - 30, 0, 0)],
                 att_p: [(0, w - 20, 0, 0), (w - 20, 0, 0, 0)]}
    elif mode == "surprise_attack":
        # Defender: full-alert units more than 30cm from the edges, standby
        # ones within 15cm of the planet (placement_errors); the attacker
        # moves on from one table edge of its choice (reading: deploys within
        # 3cm of it, as The Raiders)
        e = 3.0
        rects = {3 - att_p: [(30, 30, 30, 30)],
                 att_p: [(0, 0, h - e, 0), (0, 0, 0, h - e), (0, w - e, 0, 0),
                         (w - e, 0, 0, 0)]}
    elif mode == "the_bait":
        # The pursued ship at the centre (fixed_placements); the pursuers more
        # than 60cm behind it (towards the left short edge)
        rects = {att_p: [(0, w / 2.0 + 60.0, 0, 0)], 3 - att_p: [(w / 2.0 - 1, w / 2.0 - 1, 0, 0)]}
    elif mode == "rearguard":
        # Defender at least 30cm from the long edges and 60cm from the sunward
        # (left) edge; the attacker moves on from any edge (as The Raiders)
        e = 3.0
        rects = {3 - att_p: [(60, 0, 30, 30)],
                 att_p: [(0, 0, h - e, 0), (0, 0, 0, h - e), (0, w - e, 0, 0),
                         (w - e, 0, 0, 0)]}
    elif mode == "blockade_run":
        # Attacker within 15cm of its (bottom) edge; blockaders not within 60cm
        # of it, in the third of the table their D6 gave (placement_errors)
        rects = {att_p: [(0, 0, h - 15, 0)], 3 - att_p: [(0, 0, 0, 60)]}
    elif mode == "cruiser_clash":
        # Fleet A and B: 90cm wide, centred on each long edge, 30cm deep
        side = (w - 90.0) / 2.0
        a = (gs.scenario_state or {}).get("fleet_a", 1)
        rects = {a: [(side, side, 0, h - 30)], 3 - a: [(side, side, h - 30, 0)]}
    elif mode == "chance_encounter":
        # Attacker: 60cm wide, centred on the top edge, 30cm deep; defender
        # within 30cm of the bottom edge
        side = (w - 60.0) / 2.0
        rects = {att_p: [(side, side, 0, h - 30)], 3 - att_p: [(0, 0, h - 30, 0)]}
    elif mode == "convoy_matched":
        # Defender (and its convoy) within 30cm of the bottom edge; attacker
        # between 15 and 45cm of the top edge
        rects = {3 - att_p: [(0, 0, h - 30, 0)], att_p: [(0, 0, 15, h - 45)]}
    elif mode == "domination":
        layout = (gs.scenario_state or {}).get("layout")
        if not layout:
            return None
        att, dfn, _ = _domination_layout(layout, w, h)
        rects = {att_p: att, 3 - att_p: dfn}
    else:
        return None
    zones = []
    for p in (1, 2):
        role = "Attacker" if p == att_p else "Defender"
        rs = [_rect(p, w, h, *r, label=f"Player {p} ({role})") for r in rects[p]]
        main = rs[0]
        main.extra = rs[1:]
        zones.append(main)
    return zones


def placement_errors(gs, group, positions, headings, placed) -> List[str]:
    """Scenario deployment rules beyond the zone (DeploymentState's
    extra_check). Ambush: every defending ship and squadron faces the same
    direction and is at least 20cm from any other ship or squadron (its own
    squadron excepted)."""
    errs: List[str] = []
    mode = getattr(gs, "scenario_mode", "")
    if mode == "raiders" and group:
        if group[0].player == defender(gs):
            return _raiders_defender_errors(gs, group, positions, headings, placed)
        return errs
    if mode == "destroy_docks":
        from .destroy_docks import placement_errors as _docks_errors
        return _docks_errors(gs, group, positions)
    if mode == "escalating_engagement":
        from .escalating import placement_errors as _ee_errors
        return _ee_errors(gs, group, positions)
    if mode == "fleet_engagement" and group:
        # each ship faces its division's approach arrow
        for s_, (x, y), hd in zip(group, positions, headings):
            div = fe_division_at(gs, group[0].player, x, y)
            if div is not None and abs((hd - div[1] + 180.0) % 360.0 - 180.0) > 1.0:
                errs.append(f"Fleet Engagement: {s_.name} faces its division's arrow "
                            f"(heading {div[1]:g})")
        return errs
    if mode == "alien_intervention" and group and group[0].player == defender(gs):
        return _same_facing_apart(gs, group, positions, headings, placed, 10.0,
                                  "Alien Intervention")
    if mode == "surprise_attack" and group:
        if group[0].player == gs.scenario_attacker:
            # one table edge for the whole attacking fleet
            def edge_of(x, y):
                return min((("left", x), ("right", gs.table_width - x), ("bottom", y),
                            ("top", gs.table_height - y)), key=lambda t: t[1])[0]
            mine = [s for s in placed if s.player == group[0].player]
            if mine:
                e0 = edge_of(mine[0].x, mine[0].y)
                if any(edge_of(x, y) != e0 for x, y in positions):
                    errs.append(f"Surprise Attack: the whole fleet comes on from the {e0} edge")
            return errs
        if on_standby(gs, group[0]):
            pl = next((p for p in gs.get_phenomena() if p.id == "scenario_planet"), None)
            for s_, (x, y), hd in zip(group, positions, headings):
                if pl is None:
                    break
                d = ((x - pl.x) ** 2 + (y - pl.y) ** 2) ** 0.5
                if d > pl.radius + 15.0:
                    errs.append(f"Surprise Attack: {s_.name} on standby within 15cm of the planet")
                radial = math.degrees(math.atan2(y - pl.y, x - pl.x))
                off = abs((hd - radial + 180.0) % 180.0 - 90.0)
                if off > 10.0:
                    errs.append(f"Surprise Attack: {s_.name} on standby abeam of the planet")
        return errs
    if mode == "rearguard" and group and group[0].player == defender(gs):
        # every defending ship faces the sunward (left) edge, 10cm apart
        for s_, h in zip(group, headings):
            if abs((h - 180.0 + 180.0) % 360.0 - 180.0) > 0.5:
                errs.append(f"Rearguard Attack: {s_.name} must face the sunward edge (180)")
        others = [s for s in placed if s.player == group[0].player
                  and not (group[0].squadron_id and s.squadron_id == group[0].squadron_id)]
        for s in others:
            if any((x - s.x) ** 2 + (y - s.y) ** 2 < 100.0 for x, y in positions):
                errs.append(f"Rearguard Attack: at least 10cm from {s.name}")
                break
        return errs
    if mode == "blockade_run" and group and group[0].player == defender(gs):
        third = (gs.scenario_state or {}).get("thirds", {}).get(_group_key(group[0]))
        if third:
            lo = (third - 1) * gs.table_width / 3.0
            hi = third * gs.table_width / 3.0
            for s_, (x, _y) in zip(group, positions):
                if not lo <= x <= hi:
                    errs.append(f"Blockade Run: {s_.name} deploys in third {third} "
                                f"({lo:g}-{hi:g}cm)")
        return errs
    if mode == "cruiser_clash" and group:
        # Every ship faces the opposite long table edge
        top = (gs.scenario_state or {}).get("fleet_a", 1) == group[0].player
        want = 270.0 if top else 90.0
        for s_, h in zip(group, headings):
            if abs((h - want + 180.0) % 360.0 - 180.0) > 0.5:
                errs.append(f"Cruiser Clash: {s_.name} must face the opposite long edge "
                            f"(heading {want:g})")
        return errs
    if mode == "line_breaker" and group and group[0].player == defender(gs):
        w, h = gs.table_width, gs.table_height
        for s_, (x, y) in zip(group, positions):
            if is_platform(s_):
                if min(x, y, w - x, h - y) <= 30.0:
                    errs.append(f"Line Breaker: {s_.name} more than 30cm from every edge")
                for o in placed:
                    if is_platform(o) and (o.x - x) ** 2 + (o.y - y) ** 2 <= 15.0 ** 2:
                        errs.append(f"Line Breaker: platforms more than 15cm apart ({o.name})")
                if any(_in_phenomenon(x, y, p) for p in gs.get_phenomena()):
                    errs.append(f"Line Breaker: {s_.name} not within a celestial phenomenon")
            elif y > 60.0:
                errs.append(f"Line Breaker: {s_.name} within 60cm of the defender's edge")
        return errs
    if mode == "planet_strike" and group and group[0].player == defender(gs):
        pl = strike_planet(gs)
        for s_, (x, y) in zip(group, positions):
            if "immobile" in s_.special_rules:
                if pl and (x - pl.x) ** 2 + (y - pl.y) ** 2 > pl.gravity_well_radius ** 2:
                    errs.append(f"Planet Strike: {s_.name} within the planet's gravity well")
            elif x < gs.table_width - 45.0:
                errs.append(f"Planet Strike: {s_.name} within 45cm of the defender's edge")
        return errs
    if mode != "ambush" or not group:
        return errs
    if group[0].player != defender(gs):
        return errs
    others = [s for s in placed if s.player == defender(gs)
              and not (group[0].squadron_id and s.squadron_id == group[0].squadron_id)]
    for s in others:
        for h in headings:
            if abs((h - s.heading + 180.0) % 360.0 - 180.0) > 1e-6:
                errs.append(f"Ambush: every defending ship faces the same direction "
                            f"({s.name} faces {s.heading:g})")
                break
        for (x, y) in positions:
            if (x - s.x) ** 2 + (y - s.y) ** 2 < 20.0 ** 2:
                errs.append(f"Ambush: at least 20cm from {s.name}")
                break
    return errs


def _same_facing_apart(gs, group, positions, headings, placed, apart: float,
                       label: str) -> List[str]:
    errs = []
    others = [s for s in placed if s.player == group[0].player
              and not (group[0].squadron_id and s.squadron_id == group[0].squadron_id)]
    for s in others:
        if any(abs((h - s.heading + 180.0) % 360.0 - 180.0) > 0.5 for h in headings):
            errs.append(f"{label}: every defending ship faces the same way as {s.name}")
            break
    for s in others:
        if any((x - s.x) ** 2 + (y - s.y) ** 2 < apart * apart for x, y in positions):
            errs.append(f"{label}: at least {apart:g}cm from {s.name}")
            break
    return errs


def _raiders_defender_errors(gs, group, positions, headings, placed) -> List[str]:
    """The Raiders: every defending ship faces the same table edge (one of the
    four edge directions) and each ship or squadron is 20cm from the others."""
    errs = []
    for s_, h in zip(group, headings):
        if min(abs((h - a + 180.0) % 360.0 - 180.0) for a in (0, 90, 180, 270)) > 0.5:
            errs.append(f"The Raiders: {s_.name} must face a table edge")
    others = [s for s in placed if s.player == group[0].player
              and not (group[0].squadron_id and s.squadron_id == group[0].squadron_id)]
    for s in others:
        if any(abs((h - s.heading + 180.0) % 360.0 - 180.0) > 0.5 for h in headings):
            errs.append(f"The Raiders: every defending ship faces the same edge as {s.name}")
            break
    for s in others:
        if any((x - s.x) ** 2 + (y - s.y) ** 2 < 400.0 for x, y in positions):
            errs.append(f"The Raiders: at least 20cm from {s.name}")
            break
    return errs


def _in_phenomenon(x: float, y: float, p) -> bool:
    """A point inside a celestial phenomenon's area (planets by radius, the
    rest by their rectangle, as the map editor draws them)."""
    if "planet" in p.phenomenon_type and p.radius > 0:
        return (x - p.x) ** 2 + (y - p.y) ** 2 <= p.radius ** 2
    return abs(x - p.x) <= p.width / 2 and abs(y - p.y) <= p.height / 2


def auto_positions(gs, group, zone, placed, index: int):
    """Scenario-aware automatic placement, or None for the default: Warp
    Storm alternates its divisions' corners; Ambush spaces the defender's
    groups 25cm apart."""
    mode = getattr(gs, "scenario_mode", "")
    if mode == "destroy_docks":
        from .destroy_docks import auto_positions as _docks_auto
        return _docks_auto(gs, group, placed)
    if mode == "escalating_engagement":
        from .escalating import auto_positions as _ee_auto
        return _ee_auto(gs, group, placed)
    if mode == "fleet_engagement" and group:
        # round-robin over the player's divisions, so each gets a unit
        r = zone.rects()[index % len(zone.rects())]
        n = sum(1 for s in placed if s.player == group[0].player
                and r.x_min <= s.x <= r.x_max and r.y_min <= s.y <= r.y_max)
        cx, cy = (r.x_min + r.x_max) / 2.0, (r.y_min + r.y_max) / 2.0
        return [(cx - 6.0 + 4.0 * i + 9.0 * (n % 3) - 9.0, cy + 7.0 * (n // 3))
                for i in range(len(group))]
    if mode == "line_breaker" and group and group[0].player == defender(gs):
        rects = zone.rects()
        r = rects[1] if is_platform(group[0]) else rects[0]
        others = [s for s in placed if s.player == defender(gs)]
        y = r.y_min + (2.0 if is_platform(group[0]) else 5.0)
        while y <= r.y_max:
            x = r.x_min + 5.0
            while x <= r.x_max:
                pts = [(x + 4.0 * i, y) for i in range(len(group))]
                if not placement_errors(gs, group, pts, [90.0] * len(group), others) and all(
                        (px - s.x) ** 2 + (py - s.y) ** 2 >= 6.0 ** 2
                        for px, py in pts for s in others):
                    return pts
                x += 16.0
            y += 8.0
    if mode == "warp_storm":
        r = zone.rects()[index % len(zone.rects())]
        cx, cy = (r.x_min + r.x_max) / 2, (r.y_min + r.y_max) / 2
        return [(cx + 5.0 * (i % 3) - 5.0, cy + 5.0 * (i // 3)) for i in range(len(group))]
    if mode == "blockade_run" and group and group[0].player == defender(gs):
        third = (gs.scenario_state or {}).get("thirds", {}).get(_group_key(group[0]), 2)
        lo = (third - 1) * gs.table_width / 3.0
        n_here = sum(1 for s in placed if s.player == group[0].player
                     and lo <= s.x <= lo + gs.table_width / 3.0)
        cx = lo + gs.table_width / 6.0
        cy = gs.table_height - 15.0 - 10.0 * (n_here % 4)
        return [(cx - 6.0 + 4.0 * i, cy) for i in range(len(group))]
    if mode == "surprise_attack" and group and on_standby(gs, group[0]):
        pl = next((p for p in gs.get_phenomena() if p.id == "scenario_planet"), None)
        if pl is not None:
            k = sum(1 for s in placed if on_standby(gs, s))
            out = []
            for i in range(len(group)):
                a = math.radians(40.0 * (k + i))
                rr = pl.radius + 8.0
                out.append((pl.x + rr * math.cos(a), pl.y + rr * math.sin(a)))
            return out
    if mode in ("raiders", "rearguard", "surprise_attack") and group \
            and group[0].player == gs.scenario_attacker:
        r = zone.rects()[0]
        cx = (r.x_min + r.x_max) / 2.0 - 8.0 * index
        y = r.y_max - max(s_.base_radius for s_ in group) - 0.1      # base on the table
        return [(cx + 4.0 * i, y) for i in range(len(group))]
    if mode in ("ambush", "raiders", "rearguard", "surprise_attack", "alien_intervention") \
            and group and group[0].player == defender(gs):
        others = [s for s in placed if s.player == defender(gs)]
        y = zone.y_min + 5.0
        while y <= zone.y_max:
            x = zone.x_min + 5.0
            while x <= zone.x_max:
                pts = [(x + 4.0 * i, y) for i in range(len(group))]
                if all(zone.contains(px, py) for px, py in pts) and all(
                        (px - s.x) ** 2 + (py - s.y) ** 2 >= 21.0 ** 2
                        for px, py in pts for s in others):
                    return pts
                x += 25.0
            y += 25.0
    return None


def fe_division_errors(gs, player: int) -> List[str]:
    """Fleet Engagement: at least one ship or squadron in each division."""
    if getattr(gs, "scenario_mode", "") != "fleet_engagement":
        return []
    n = sum(1 for p, _r, _h in _fe_rects(gs) if p == player)
    used = {fe_division_at(gs, player, s.x, s.y)[0] for s in gs.get_ships()
            if s.player == player and not s.is_disengaged
            and fe_division_at(gs, player, s.x, s.y) is not None}
    missing = [i + 1 for i in range(n) if i not in used]
    return [f"Fleet Engagement: nothing deployed in division(s) {missing}"] if missing else []


def auto_heading(gs, player: int, x: float, y: float) -> Optional[float]:
    """The heading a scenario requires at a deployment point (Fleet
    Engagement's arrows, Cruiser Clash's facing), or None."""
    mode = getattr(gs, "scenario_mode", "")
    if mode == "fleet_engagement":
        div = fe_division_at(gs, player, x, y)
        return div[1] if div else None
    if mode == "cruiser_clash":
        return 270.0 if y > gs.table_height / 2 else 90.0
    return None


def division_errors(gs, player: int) -> List[str]:
    """Warp Storm: the two divisions (one per corner) as close to the same
    number of capital ships and escort squadrons as possible (a difference of
    at most one of each, reading)."""
    if getattr(gs, "scenario_mode", "") != "warp_storm":
        return []
    zone = next((z for z in deployment_zones(gs) if z.player == player), None)
    if zone is None:
        return []
    caps, sqs = [0, 0], [set(), set()]
    for s in gs.get_ships():
        if s.player != player:
            continue
        i = next((k for k, r in enumerate(zone.rects())
                  if r.x_min <= s.x <= r.x_max and r.y_min <= s.y <= r.y_max), None)
        if i is None:
            continue
        if s.ship_type == "escort" and s.squadron_id:
            sqs[i].add(s.squadron_id)
        else:
            caps[i] += 1
    errs = []
    if abs(caps[0] - caps[1]) > 1:
        errs.append(f"capital ships {caps[0]} v {caps[1]}")
    if abs(len(sqs[0]) - len(sqs[1])) > 1:
        errs.append(f"escort squadrons {len(sqs[0])} v {len(sqs[1])}")
    return errs


# --- Special rules during the game -------------------------------------------

def _in_defenders_first_turn(gs) -> bool:
    """Up to the end of the defender's first turn. Reading: the attacker's
    turn before it counts too (the defender is caught unawares; a Brace in
    the attacker's first turn would last into the defender's turn)."""
    first = 1 if getattr(gs, "turn_system", "igougo") == "aa" or \
        gs.first_player == defender(gs) else 2
    return gs.turn_number <= first


def orders_forbidden(gs, ship) -> Optional[str]:
    """Why `ship` may not go on special orders now (Brace included), or None.
    Ambush: no defending ship during the defender's first turn. Rescue: the
    defending flagship during the defender's first turn."""
    from .subplots import orders_forbidden as _subplot_forbidden
    why = _subplot_forbidden(gs, ship)
    if why:
        return why
    mode = getattr(gs, "scenario_mode", "")
    if mode == "surprise_attack" and ship.player == defender(gs):
        if (gs.scenario_state or {}).get("alerted", {}).get(_group_key(ship)) == gs.turn_number:
            return "Surprise Attack: just on full alert, no special orders this turn"
    if ship.player != defender(gs) or not _in_defenders_first_turn(gs):
        return None
    if mode == "ambush":
        return "Ambush: the defender is caught unawares (no special orders in its first turn)"
    if mode == "rescue" and ship.id == (gs.scenario_state or {}).get("flagship"):
        return "Rescue: the sabotaged flagship takes no special orders in its first turn"
    return None


def disengage_forbidden(gs, ship) -> Optional[str]:
    """Why `ship` may not take a disengage test, or None. Ambush: no defending
    ship in the defender's first turn. Rescue: the flagship may only
    disengage by moving off the defender's short edge (reading: no Leadership
    test to disengage)."""
    mode = getattr(gs, "scenario_mode", "")
    if mode == "ambush" and ship.player == defender(gs) and _in_defenders_first_turn(gs):
        return "Ambush: the defender may not disengage in its first turn"
    if mode == "rescue" and ship.id == (gs.scenario_state or {}).get("flagship"):
        return "Rescue: the flagship can only disengage off the defender's short edge"
    return None


def off_table_destroyed(gs, ship) -> bool:
    """Rescue: the flagship moving off any edge but the defender's short edge
    (the left edge, x = 0) is destroyed instead of disengaging."""
    if getattr(gs, "scenario_mode", "") != "rescue":
        return False
    if ship.id != (gs.scenario_state or {}).get("flagship"):
        return False
    r = ship.base_radius
    over = {"left": r - ship.x, "right": ship.x + r - gs.table_width,
            "bottom": r - ship.y, "top": ship.y + r - gs.table_height}
    return max(over, key=over.get) != "left"


def exit_edge(gs, ship) -> str:
    """The table edge a ship has moved off (the one it is furthest past)."""
    r = ship.base_radius
    over = {"left": r - ship.x, "right": ship.x + r - gs.table_width,
            "bottom": r - ship.y, "top": ship.y + r - gs.table_height}
    return max(over, key=over.get)


def record_exit(gs, ship) -> None:
    """A ship moved off the table: remember the edge (Line Breaker's
    breakthrough is a capital ship off the defender's long edge)."""
    if not is_booklet_scenario(gs):
        return
    st = dict(gs.scenario_state or {})
    exits = dict(st.get("exits", {}))
    exits[ship.id] = exit_edge(gs, ship)
    st["exits"] = exits
    gs.scenario_state = st
    from .navigate_storm import record_exit as _storm_exit
    _storm_exit(gs, ship)
    from .convoy_narrative import record_exit as _cn_exit
    _cn_exit(gs, ship)


def damage_points(gs, player: int) -> int:
    """Cruiser Clash: 1 point per point of damage inflicted on enemy ships,
    +1 per crippled enemy ship or +3 per destroyed one (not both)."""
    pts = 0
    for s in gs.get_ships():
        if s.player == player:
            continue
        pts += min(s.hits_max, s.hits_max - max(0, s.hits_remaining))
        if s.is_destroyed:
            pts += 3
        elif s.damage_crippled:
            pts += 1
    return pts


def chance_result(gs) -> Optional[int]:
    """Chance Encounter: the defender wins if the attacker's flagship is
    crippled (or destroyed: a heroic victory); the attacker wins if the
    flagship and at least one other capital ship disengaged off the
    defender's long edge (the bottom) and the flagship isn't crippled.
    Reading: neither, a draw."""
    flag = chance_flagship(gs)
    if flag is None:
        return None
    if flag.is_destroyed or flag.damage_crippled:
        return defender(gs)
    exits = (gs.scenario_state or {}).get("exits", {})
    out = [sid for sid, e in exits.items() if e == "bottom"
           and (s := gs.get_ship_by_id(sid)) is not None
           and s.player == gs.scenario_attacker and s.ship_type != "escort"]
    if flag.id in out and len(out) >= 2:
        return gs.scenario_attacker
    return None


def line_breaker_won(gs) -> bool:
    """The attacker has destroyed every defence platform and moved at least
    one capital ship off the defender's long edge (the bottom one)."""
    plats = [s for s in gs.get_ships() if s.player == defender(gs) and is_platform(s)]
    if any(not s.is_destroyed for s in plats):
        return False
    exits = (gs.scenario_state or {}).get("exits", {})
    return any(edge == "bottom" and (s := gs.get_ship_by_id(sid)) is not None
               and s.player == gs.scenario_attacker and s.ship_type != "escort"
               for sid, edge in exits.items())


def vp_bonus(gs, result: Dict) -> None:
    """Scenario victory points added to calculate_victory_points' result.
    Rescue: the attacker +100% of the defending flagship's cost if it is
    destroyed at the end of the game. Space Assault: 250 to the attacker if
    the space station is destroyed, else 250 to the defender."""
    if getattr(gs, "scenario_mode", "") == "convoy_matched":
        # Each convoy ship moving off the attacker's long edge (the top) gives
        # the defender 100 VP instead of counting for the attacker; leaving
        # any other way counts as destroyed and gives the attacker +50.
        # Reading: convoy ships are scored one by one, not as squadrons
        exits = (gs.scenario_state or {}).get("exits", {})
        att, dfn = gs.scenario_attacker, defender(gs)
        for c in gs.get_ships():
            if c.player != dfn or not is_convoy(c):
                continue
            pts = c.points_value
            if c.is_disengaged and exits.get(c.id) == "top":
                vp, who, why = 100, dfn, "escaped"
            elif c.is_disengaged:
                vp, who, why = pts + 50, att, "left the board (destroyed)"
            elif c.is_destroyed:
                vp, who, why = pts, att, "destroyed"
            elif c.damage_crippled:
                vp, who, why = max(1, pts // 4) if pts else 0, att, "crippled"
            else:
                continue
            if vp:
                result[who]["scenario"] = result[who].get("scenario", 0) + vp
                result[who]["details"].append(f"Convoy: {c.name} {why}: +{vp} VP")
        return
    if getattr(gs, "scenario_mode", "") == "blockade_run":
        # The attacker's ships off the blockader's (top) edge: 100% of their
        # points, 25% if crippled (an escort squadron as a unit, reading: by
        # its ships that escaped)
        exits = (gs.scenario_state or {}).get("exits", {})
        att = gs.scenario_attacker
        for c in gs.get_ships():
            if c.player == att and c.is_disengaged and exits.get(c.id) == "top":
                vp = c.points_value if not c.damage_crippled else c.points_value // 4
                result[att]["scenario"] = result[att].get("scenario", 0) + vp
                result[att]["details"].append(f"Blockade Run: {c.name} broke through: +{vp} VP")
        return
    if getattr(gs, "scenario_mode", "") == "destroy_docks":
        # Orbital mines give their points when removed (Support Assets)
        from .destroy_docks import mines_removed, MINE_VP
        n = mines_removed(gs)
        if n:
            att = gs.scenario_attacker
            result[att]["scenario"] = result[att].get("scenario", 0) + n * MINE_VP
            result[att]["details"].append(f"Destroy the Docks: {n} orbital mine(s) removed: "
                                          f"+{n * MINE_VP} VP")
        return
    if getattr(gs, "scenario_mode", "") == "space_assault":
        st = space_station(gs)
        if st is None:
            return
        p = gs.scenario_attacker if st.is_destroyed else defender(gs)
        result[p]["scenario"] = result[p].get("scenario", 0) + 250
        result[p]["details"].append(f"Space Assault: station "
                                    f"{'destroyed' if st.is_destroyed else 'survives'}: +250 VP")
        return
    if getattr(gs, "scenario_mode", "") != "rescue":
        return
    sid = (gs.scenario_state or {}).get("flagship")
    flag = gs.get_ship_by_id(sid) if sid else None
    if flag is not None and flag.is_destroyed:
        att = gs.scenario_attacker
        result[att]["scenario"] = result[att].get("scenario", 0) + flag.points_value
        result[att]["details"].append(f"Rescue: {flag.name} destroyed: +{flag.points_value} VP")


def cripple_bonus_vp(gs, ship) -> float:
    """Extra VP-equivalent the scenario puts on crippling `ship` (destroying
    it counts too): Chance Encounter's attacking flagship, whose crippling wins
    the game for the defender (judgement: half the points on the table)."""
    if getattr(gs, "scenario_mode", "") == "chance_encounter":
        flag = chance_flagship(gs)
        if flag is not None and flag.id == ship.id:
            return 0.5 * table_points(gs)
    return 0.0


def kill_bonus_vp(gs, ship) -> float:
    """Extra VP the scenario gives the enemy for destroying `ship` (Rescue's
    flagship: +100% of its cost; Space Assault's station: the 250 the attacker
    gains and the 250 the defender loses). Line Breaker's platforms: the
    attacker can only win with them all destroyed (judgement: each worth the
    defender's points / platforms). Used by the AI's damage and disengage
    values."""
    from .subplots import kill_bonus_vp as _subplot_bonus
    sub = _subplot_bonus(gs, ship)
    return sub + _scenario_kill_bonus(gs, ship)


def _scenario_kill_bonus(gs, ship) -> float:
    mode = getattr(gs, "scenario_mode", "")
    if mode == "convoy_matched" and is_convoy(ship) and ship.player == defender(gs):
        return 100.0        # a convoy ship escaping would give the defender 100
    if mode == "convoy_narrative" and is_convoy(ship) and ship.player == defender(gs):
        from .convoy_narrative import capacity_vp
        return capacity_vp(gs) * transport(ship)
    if mode == "destroy_docks" and ship.player == defender(gs):
        from .destroy_docks import target_bonus_vp
        return target_bonus_vp(gs, ship)
    if mode == "navigate_storm" and ship.player == defender(gs):
        from .navigate_storm import capacity_vp
        return capacity_vp(gs) * transport(ship, building=True)
    if mode == "space_assault" and ship.ship_class.startswith("Space Station") \
            and ship.player == defender(gs):
        return 500.0
    if mode == "line_breaker" and is_platform(ship) and ship.player == defender(gs):
        ds = [s for s in gs.get_ships() if s.player == defender(gs)]
        n = max(1, sum(1 for s in ds if is_platform(s)))
        return sum(s.points_value for s in ds) / n
    if (getattr(gs, "scenario_mode", "") == "rescue"
            and ship.id == (gs.scenario_state or {}).get("flagship")):
        return float(ship.points_value or 0)
    return 0.0


def warp_loss_chance(gs, ship) -> float:
    """Warp Storm: the chance a ship that disengages is lost in the warp at
    the end of the game (2D6 over its Ld). 0 in other scenarios."""
    if getattr(gs, "scenario_mode", "") != "warp_storm":
        return 0.0
    ld = ship.leadership
    ways = sum(1 for a in range(1, 7) for b in range(1, 7) if a + b > ld)
    return ways / 36.0


def end_of_game(gs, dice) -> bool:
    """Rolls the scenario makes when the game ends, once. Warp Storm: each
    ship or squadron that disengaged takes a Leadership test (2D6 against its
    Ld; a squadron once); those that fail are lost in the warp and count as
    destroyed. Returns True when anything changed."""
    if getattr(gs, "scenario_mode", "") == "planet_strike":
        # Planet Strike: the attacker holding the field wins; otherwise a D6
        # on the bombardment table decides the invasion
        st = dict(gs.scenario_state or {})
        if st.get("strike_winner"):
            return False
        from .victory_points import _holds_field
        pts = st.get("bombardment", 0)
        need = strike_need(pts)
        if _holds_field(gs.scenario_attacker, gs.get_ships()):
            win = gs.scenario_attacker
        elif need is None:
            win = defender(gs)
        elif need == 1:
            win = gs.scenario_attacker
        else:
            roll = dice.roll_d6(1, f"Planet Strike invasion ({pts:g} bombardment points: "
                                   f"{need}+)")[0]
            win = gs.scenario_attacker if roll >= need else defender(gs)
            gs.add_log(f"[Planet Strike] invasion roll {roll} (needs {need}+)")
        st["strike_winner"] = win
        gs.scenario_state = st
        gs.add_log(f"[Planet Strike] player {win} wins ({pts:g} bombardment points)")
        return True
    if getattr(gs, "scenario_mode", "") != "warp_storm":
        return False
    st = dict(gs.scenario_state or {})
    if st.get("ended"):
        return False
    st["ended"] = True
    gs.scenario_state = st
    changed = False
    groups: Dict[str, list] = {}
    for s in gs.get_ships():
        if s.is_disengaged and not s.is_destroyed:
            key = s.squadron_id if (s.ship_type == "escort" and s.squadron_id) else s.id
            groups.setdefault(key, []).append(s)
    for members in groups.values():
        ld = max(m.leadership for m in members)
        roll = dice.roll_2d6(f"Warp Storm: {members[0].name} returns through the warp (Ld {ld})")
        if roll > ld:
            for m in members:
                m.is_disengaged = False
                m.status = "destroyed"
                m.hits_remaining = 0
                gs.update_ship(m)
            gs.add_log(f"[Warp Storm] {members[0].name} is lost in the warp (rolled {roll} "
                       f"v Ld {ld}): destroyed")
            changed = True
        else:
            gs.add_log(f"[Warp Storm] {members[0].name} escapes the warp (rolled {roll} v Ld {ld})")
    return changed


# --- Domination: control and scoring --------------------------------------------

def objectives(gs) -> List[Tuple[float, float]]:
    return [tuple(o) for o in (gs.scenario_state or {}).get("objectives", [])]


def _counts_for_control(ship) -> bool:
    """A ship that can hold a marker: on the table and operational (reading:
    hulks, destroyed and disengaged ships don't count)."""
    return not (ship.is_destroyed or ship.is_disengaged or getattr(ship, "is_hulk", False))


def controller(gs, marker: Tuple[float, float], ships=None) -> Optional[int]:
    """The player controlling a marker: at least one ship within 15cm of it
    (marker centre to the ship's stem) and no enemy ship (p.126)."""
    ships = gs.get_ships() if ships is None else ships
    mx, my = marker
    near = {s.player for s in ships if _counts_for_control(s)
            and (s.x - mx) ** 2 + (s.y - my) ** 2 <= CONTROL_RANGE ** 2}
    return next(iter(near)) if len(near) == 1 else None


def controlled(gs, player: int, ships=None) -> int:
    return sum(1 for m in objectives(gs) if controller(gs, m, ships) == player)


def points(gs) -> Dict[int, int]:
    pts = (gs.scenario_state or {}).get("points", {})
    return {1: int(pts.get("1", 0)), 2: int(pts.get("2", 0))}


def score_end_of_turn(gs, player: int) -> int:
    """At the end of each player's own turn that player scores 1 objective
    point per marker controlled. Returns the points scored. Called from
    TurnController.end_phase; alternate activation calls that for each player
    in the round's end phase, so both score once a round (reading, outside the
    booklet)."""
    if getattr(gs, "scenario_mode", "") == "planet_strike":
        if player != gs.scenario_attacker:
            return 0
        got = 0.0
        for sh in gs.get_ships():
            if (sh.player == player and not sh.is_destroyed and not sh.is_disengaged
                    and (sh.distance_moved_this_turn or 0.0) <= 1e-9
                    and in_planet_contact(gs, sh)):
                got += bombardment_points(gs, sh)
        if got:
            st = dict(gs.scenario_state or {})
            st["bombardment"] = st.get("bombardment", 0) + got
            gs.scenario_state = st
            gs.add_log(f"[Planet Strike] bombardment +{got:g}: {st['bombardment']:g} points")
        return got
    if getattr(gs, "scenario_mode", "") != "domination":
        return 0
    n = controlled(gs, player)
    st = dict(gs.scenario_state or {})
    pts = dict(st.get("points", {"1": 0, "2": 0}))
    pts[str(player)] = int(pts.get(str(player), 0)) + n
    st["points"] = pts
    gs.scenario_state = st
    gs.add_log(f"[Domination] player {player} controls {n} objective(s): "
               f"{pts['1']} - {pts['2']} points")
    return n


def check_end(gs) -> Optional[dict]:
    """Booklet scenario game-end and victory (scenario.check_game_over's
    contract). Fleet-gone checks stay in check_game_over."""
    mode = getattr(gs, "scenario_mode", "")
    if mode == "convoy_narrative":
        from .convoy_narrative import check_end as _cn_end
        return _cn_end(gs)
    if mode == "convoy_matched":
        st = gs.scenario_state or {}
        if st.get("had_cargo") and cargo_on_table(gs, defender(gs)) <= 0:
            from .scenario import vp_winner
            return {"winner": vp_winner(gs), "reason": "convoy_gone",
                    "detail": "no transport capacity left on the table"}
    if mode == "navigate_storm":
        from .navigate_storm import cargo_left, winner
        st = gs.scenario_state or {}
        if cargo_left(gs) <= 0 and gs.turn_number >= 1 and gs.get_ships():
            return {"winner": winner(gs), "reason": "convoy_gone",
                    "detail": "no transport capacity left in play"}
    if mode == "line_breaker" and line_breaker_won(gs):
        return {"winner": gs.scenario_attacker, "reason": "breakthrough",
                "detail": "the line is broken"}
    if mode == "domination":
        pts = points(gs)
        if max(pts.values()) >= DOMINATION_TARGET:
            return {"winner": points_winner(gs), "reason": "objective_points",
                    "detail": f"{pts[1]} - {pts[2]}"}
    return None


def points_winner(gs) -> Optional[int]:
    pts = points(gs)
    if pts[1] == pts[2]:
        return None
    return 1 if pts[1] > pts[2] else 2


# --- AI: scenario points as VP ---------------------------------------------------
OBJECTIVE_POINT_WEIGHT = 0.5    # judgement: 10 Domination points ~ half the points on the table
BOMBARD_WEIGHT = 0.5            # judgement: winning Planet Strike ~ half the points on the table


def table_points(gs) -> float:
    return float(sum(s.points_value for s in gs.get_ships()) or 1000)


def domination_point_vp(total: float) -> float:
    """A Domination objective point in VP: a tenth of the game (judgement)."""
    return OBJECTIVE_POINT_WEIGHT * total / (2.0 * DOMINATION_TARGET)


def bombard_point_vp(total: float) -> float:
    """A Planet Strike bombardment point in VP: about a 25th of the game,
    the table running from 6 (6+) to 31 (automatic) (judgement)."""
    return BOMBARD_WEIGHT * total / 25.0


def scenario_margin_vp(gs, player: int) -> float:
    """The scenario points banked so far, as VP for `player` (To do 2: the
    margin the AI plays for counts them): Domination's objective points,
    Planet Strike's bombardment points (the attacker's)."""
    mode = getattr(gs, "scenario_mode", "")
    if mode == "domination":
        pts = points(gs)
        return (pts[player] - pts[3 - player]) * domination_point_vp(table_points(gs))
    if mode == "planet_strike":
        b = (gs.scenario_state or {}).get("bombardment", 0)
        sign = 1 if player == gs.scenario_attacker else -1
        return sign * b * bombard_point_vp(table_points(gs))
    return 0.0


def sim_scenario(gs) -> Dict:
    """What the expert search's leaf needs about the scenario (lookahead_ai):
    Domination's markers, points and point value; Planet Strike's planet,
    bombardment and point value."""
    mode = getattr(gs, "scenario_mode", "")
    if mode == "domination":
        return {"mode": mode, "objectives": objectives(gs), "points": points(gs),
                "point_vp": domination_point_vp(table_points(gs))}
    if mode == "planet_strike":
        pl = strike_planet(gs)
        return {"mode": mode, "attacker": gs.scenario_attacker,
                "bombard": (gs.scenario_state or {}).get("bombardment", 0),
                "planet": (pl.x, pl.y, pl.radius) if pl else None,
                "point_vp": bombard_point_vp(table_points(gs))}
    return {}


def winner_at_end(gs, vp_winner_fn) -> Optional[int]:
    """Who wins when the game ends for any reason (fleet gone, turn limit):
    Domination by objective points, the others by VP."""
    sc = SCENARIOS.get(getattr(gs, "scenario_mode", ""))
    if sc and sc["victory"] == "objective_points":
        return points_winner(gs)
    if sc and sc["victory"] == "line_breaker":
        return gs.scenario_attacker if line_breaker_won(gs) else defender(gs)
    if sc and sc["victory"] == "damage_points":
        a, b = damage_points(gs, 1), damage_points(gs, 2)
        return None if a == b else (1 if a > b else 2)
    if sc and sc["victory"] == "chance_encounter":
        return chance_result(gs)
    if sc and sc["victory"] == "convoy_narrative":
        from .convoy_narrative import winner as _cn_winner
        return _cn_winner(gs)
    if sc and sc["victory"] == "destroy_docks":
        from .destroy_docks import winner as _docks_winner
        return _docks_winner(gs)
    if sc and sc["victory"] == "navigate_storm":
        from .navigate_storm import winner
        return winner(gs)
    if sc and sc["victory"] == "planet_strike":
        st = gs.scenario_state or {}
        if st.get("strike_winner"):
            return st["strike_winner"]
        from .victory_points import _holds_field
        if _holds_field(gs.scenario_attacker, gs.get_ships()):
            return gs.scenario_attacker
        need = strike_need(st.get("bombardment", 0))
        if need is None:
            return defender(gs)
        if need == 1:
            return gs.scenario_attacker
        return None                       # decided by end_of_game's roll
    return vp_winner_fn(gs)
