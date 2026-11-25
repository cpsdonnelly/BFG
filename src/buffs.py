"""Ships that help friends in range (owner: the AI places and moves them to
cover as many friends as it can), shared by AI deployment and the move score.

Kinds and reaches, from the ships' special rules:
  - "synapse": Tyranid synapse creatures (`synapse:<ld>:<range>`; the Proteus
    60cm, Charybdis 45cm, a Scylla's synapse node 30cm): friends in range can
    be controlled instead of acting on instinct (tyranids.in_range, measured
    stem to stem);
  - "tracking": Tau tracking systems (`tracking_systems_<range>`): Tau vessels
    within range re-roll missed turret dice and ignore the beyond-30cm
    gunnery shift (combat._has_tracking_support, stem to stem);
  - "fdt": Fleet Defence Turrets (Mechanicus Gift): +1 massed turret to
    friends within 15cm, base edge to base edge (ordnance.get_massed_turret_bonus).

`BUFF_SHARE` is what a friend kept in range is worth per turn, as a share of
its points (judgement, not tuned): control instead of instinct matters most."""
import math
from typing import Dict, List

BUFF_SHARE = {"synapse": 0.05, "tracking": 0.02, "fdt": 0.02}   # judgement


def buff_kinds(ship) -> Dict[str, float]:
    """{kind: reach in cm} of the ship's help to friends ({} if none)."""
    out: Dict[str, float] = {}
    for r in getattr(ship, "special_rules", None) or []:
        if r.startswith("synapse:"):
            try:
                out["synapse"] = max(out.get("synapse", 0.0), float(r.split(":")[2]))
            except (IndexError, ValueError):
                pass
        elif r.startswith("tracking_systems"):
            try:
                rng = float(r.rsplit("_", 1)[1])
            except ValueError:
                rng = 10.0
            out["tracking"] = max(out.get("tracking", 0.0), rng)
        elif r == "fleet_defence_turrets":
            out["fdt"] = 15.0
    return out


def buff_range(ship) -> float:
    """The furthest the ship's help reaches (cm), 0 if it has none."""
    return max(buff_kinds(ship).values(), default=0.0)


def benefits(kind: str, friend) -> bool:
    """Whether the friend can use that kind of help at all. A ship with the
    same kind of help has it already (a synapse creature controls itself,
    tracking systems and Fleet Defence Turrets count their own ship)."""
    rules = getattr(friend, "special_rules", None) or []
    if kind in buff_kinds(friend):
        return False
    if kind == "synapse":
        return "tyranid" in rules
    if kind == "tracking":
        return (getattr(friend, "faction", "") or "").startswith("tau")
    return True


def in_reach(kind: str, reach: float, x: float, y: float, r: float, friend) -> bool:
    d = math.hypot(friend.x - x, friend.y - y)
    if kind == "fdt":
        d -= r + friend.base_radius
    return d <= reach + 1e-9


def _usable(s) -> bool:
    return not (s.is_destroyed or s.is_disengaged) and s.status == "active"


def buff_value(ship, x: float, y: float, friends: List) -> float:
    """VP a turn of the help `ship` would give standing at (x, y): for each
    kind, each friend in reach (not the ship itself) that no other ship of
    that kind already covers, BUFF_SHARE x its points. A crippled Fleet
    Defence Turrets ship gives nothing (owner ruling)."""
    kinds = buff_kinds(ship)
    if not kinds:
        return 0.0
    total = 0.0
    others = [f for f in friends if f.id != ship.id and _usable(f)]
    for kind, reach in kinds.items():
        if kind == "fdt" and ship.is_crippled:
            continue
        if kind == "synapse":
            from .tyranids import synapse
            if not synapse(ship):
                continue
        helpers = [h for h in others if kind in buff_kinds(h)
                   and not (kind == "fdt" and h.is_crippled)]
        for f in others:
            if not benefits(kind, f) or not in_reach(kind, reach, x, y, ship.base_radius, f):
                continue
            if any(in_reach(kind, buff_kinds(h)[kind], h.x, h.y, h.base_radius, f)
                   for h in helpers if h.id != f.id):
                continue                   # already covered by another
            total += BUFF_SHARE[kind] * f.points_value
    return total
