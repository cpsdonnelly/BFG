"""Eldar MMS v2.0 rules (bfgxr/rules/09_eldar.md, MMS pp.3-5; CLAUDE.md To do
14), pure logic. First slice: speeds by the sun, the two-move movement
(turn on the spot at the start of each move), special-order limits, holofields
and Fragile. Wiring into the catalog, combat, movement dialogs and the AI comes
on top of this.

Readings to confirm with the owner are marked "reading"."""
import math
import re
from typing import List, Optional, Tuple

SUN, AWAY, ABEAM = "sun", "away", "abeam"

# The battle's sunward edge (GameState.sunward_edge; set by the TurnController),
# which Eldar speeds depend on whether or not Fighting Sunward is played
_SUNWARD = {"edge": "north"}


def set_sunward_edge(edge: str) -> None:
    _SUNWARD["edge"] = edge or "north"


def sunward_edge() -> str:
    return _SUNWARD["edge"]

# Compass bearing of each sunward edge in the engine's frame (x right, y up;
# celestial.SUN_ANGLE uses the same convention)
_SUN_ANGLE = {"north": 90.0, "south": 270.0, "east": 0.0, "west": 180.0}


def parse_speeds(raw: str) -> Optional[Tuple[int, int, int]]:
    """'10/15/20' -> (into the sun, away from the sun, abeam), the order the
    rules list them (MMS p.3: "the first is into the sun, the second is away
    from the sun and the third is abeam")."""
    m = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\s*(?:cm)?\s*", raw or "")
    return tuple(int(g) for g in m.groups()) if m else None


def parse_holofield(raw: str) -> Optional[int]:
    """'2+H' -> 2 shields with a holofield; None when not a holofield value."""
    m = re.fullmatch(r"\s*(\d+)\s*\+\s*H\s*", raw or "")
    return int(m.group(1)) if m else None


def sun_aspect(heading: float, sunward_edge: str = "north") -> str:
    """Which of the three speeds applies to a heading (MMS: "dependent on the
    Eldar's facing to the nearest point of the sunward table edge"). Reading:
    the nearest point of a straight edge is always straight towards it, so
    within 45 degrees of that direction is into the sun, within 45 degrees of
    the opposite away, otherwise abeam (exactly 45 counts as abeam)."""
    sun = _SUN_ANGLE.get(sunward_edge or "north", 90.0)
    d = abs((heading - sun + 180.0) % 360.0 - 180.0)
    if d < 45.0:
        return SUN
    if d > 135.0:
        return AWAY
    return ABEAM


def speed_for(speeds: Tuple[int, int, int], heading: float, sunward_edge: str = "north") -> int:
    return dict(zip((SUN, AWAY, ABEAM), speeds))[sun_aspect(heading, sunward_edge)]


ALLOWED_ORDERS = ("all_ahead_full", "come_to_new_heading", "lock_on", "reload_ordnance",
                  "brace_for_impact", "none", "")


def order_allowed(order: str) -> bool:
    """Eldar may not use Burn Retros (MMS p.3)."""
    return order in ALLOWED_ORDERS


def validate_mms_move(speeds: Tuple[int, int, int], start_heading: float, turn_limit: float,
                      legs: List[Tuple[float, float]], order: str = "",
                      sunward_edge: str = "north", aaf_bonus: float = 0.0,
                      extra_turn: float = 0.0, crippled: bool = False,
                      slowed_at: Optional[Tuple[int, float]] = None) -> List[str]:
    """Check an Eldar move (MMS p.3): up to two legs, each a turn on the spot
    (up to the ship's turn angle) then a move of any length up to the speed
    for the new heading; no minimum move. Lock On: no turns; All Ahead Full:
    no turns, +aaf_bonus (5D6cm, rolled by the caller) to one leg; Come to New
    Heading: one extra turn after the second move (`extra_turn`); Burn Retros
    not allowed. Crippled: -5cm on every speed (the core rule, reading).
    legs: [(turn degrees, signed; distance cm)]. Returns the errors.
    slowed_at: (leg index, cm into that leg) where the ship first touches a
    blast marker (sign-off answer 58: MMS has no blast marker exemption):
    -5cm from that point (s.11 owner ruling: with nothing left it stops where
    it first touches) and on every later move."""
    errs = []
    if not order_allowed(order):
        errs.append("Eldar may not use Burn Retros")
    if len(legs) > 2:
        errs.append("Eldar move at most twice a movement phase")
    no_turn = order in ("lock_on", "all_ahead_full")
    h = start_heading
    bonus_left = aaf_bonus if order == "all_ahead_full" else 0.0
    for i, (turn, dist) in enumerate(legs):
        if abs(turn) > 1e-9:
            if no_turn:
                errs.append(f"no turns on {order}")
            elif abs(turn) > turn_limit + 1e-9:
                errs.append(f"move {i + 1}: turn {abs(turn):g} exceeds {turn_limit:g} degrees")
        h = (h + turn) % 360.0
        cap = speed_for(speeds, h, sunward_edge) - (5 if crippled else 0)
        if slowed_at is not None and i == slowed_at[0]:
            cap = max(slowed_at[1], cap - 5)
        elif slowed_at is not None and i > slowed_at[0]:
            cap = max(0, cap - 5)
        if dist > cap + bonus_left + 1e-9:
            errs.append(f"move {i + 1}: {dist:g}cm exceeds {cap:g}cm "
                        f"({sun_aspect(h, sunward_edge)})")
        elif dist > cap + 1e-9:
            bonus_left = 0.0                     # the AAF bonus goes to one move
        if dist < -1e-9:
            errs.append("negative distance")
    if extra_turn:
        if order != "come_to_new_heading":
            errs.append("an extra turn needs Come to New Heading")
        elif abs(extra_turn) > turn_limit + 1e-9:
            errs.append(f"extra turn exceeds {turn_limit:g} degrees")
    return errs


def mms_end(x: float, y: float, heading: float, legs, extra_turn: float = 0.0):
    """(x, y, heading) after the legs (and Come to New Heading's last turn)."""
    for turn, dist in legs:
        heading = (heading + turn) % 360.0
        x += dist * math.cos(math.radians(heading))
        y += dist * math.sin(math.radians(heading))
    return x, y, (heading + extra_turn) % 360.0


# --- Holofields (MMS p.4) -------------------------------------------------------
def holofield_gunnery_shift(range_cm: float) -> int:
    """Gunnery at an Eldar ship: one extra right column shift, not under 15cm."""
    return 0 if range_cm < 15.0 else 1


def holofield_save(range_cm: float) -> Optional[int]:
    """Save against lances and other direct attacks that don't use the gunnery
    table (not nova cannons, Armageddon guns or ordnance): 5+ beyond 30cm, 6+
    at 15-30cm, none under 15cm. A save stops the blast marker (the hit is
    thwarted); it works even with every shield down."""
    if range_cm < 15.0:
        return None
    return 5 if range_cm > 30.0 else 6


def holofield_saves(dice, hits: int, range_cm: float, label: str = "Holofield") -> int:
    """Roll the holofield save per hit; returns how many hits are thwarted."""
    need = holofield_save(range_cm)
    if need is None or hits <= 0:
        return 0
    rolls = dice.roll_d6(hits, f"{label} save ({need}+)")
    return sum(1 for r in rolls if r >= need)


def p_holofield_save(range_cm: float) -> float:
    need = holofield_save(range_cm)
    return 0.0 if need is None else (7 - need) / 6.0


# --- Fragile, Natural Spacefarers -----------------------------------------------
FRAGILE_CRIT_ON = 5          # Eldar take critical hits on 5+ (Ghostships excepted)


def crit_threshold(ship) -> int:
    rules = getattr(ship, "special_rules", None) or []
    if "fragile" in rules and "ghostship" not in rules:
        return FRAGILE_CRIT_ON
    return 6


def ship_speeds(ship) -> Optional[Tuple[int, int, int]]:
    for r in getattr(ship, "special_rules", None) or []:
        if r.startswith("eldar_speeds:"):
            return parse_speeds(r.split(":", 1)[1])
    return None


def commands_to_legs(commands):
    """MoveCommands -> ([(turn, distance)] legs, extra turn): a turn starts a
    leg, forward moves add to it; a turn after the second leg's move is Come to
    New Heading's extra turn. Left turns are positive."""
    legs, extra = [], 0.0
    cur_turn, cur_dist, moved = 0.0, 0.0, False
    for c in commands:
        if c.action in ("turn_left", "turn_right"):
            signed = c.value if c.action == "turn_left" else -c.value
            if moved:
                legs.append((cur_turn, cur_dist))
                cur_turn, cur_dist, moved = signed, 0.0, False
            else:
                cur_turn += signed
        elif c.action == "forward":
            cur_dist += c.value
            moved = True
    if moved or cur_turn:
        legs.append((cur_turn, cur_dist))
    if len(legs) == 3 and legs[2][1] == 0:
        extra = legs.pop()[0]
    return legs, extra
