"""Waves of attack craft (core rules s.25, with s.23 resilient waves, s.24
multi-role craft in waves and s.27 turret suppression).

A wave is the set of attack craft markers sharing a `wave_id`, ordered by
`wave_order` (0 = the lead marker). Fighters go ahead of other craft, and
multi-role craft that can act as fighters go between pure fighters and the
rest. A wave moves as one marker at its slowest squadron's speed (one blast
marker roll for the whole wave), interacts with ordnance one squadron at a
time from the lead, and is destroyed by a single hit from enemy shooting.
Against a ship it must attack, the ship's turrets fire once at the whole wave
(each success removes one squadron, lead first), the rest attack together, and
then the whole wave is removed.
"""
import uuid
from typing import Dict, List, Optional

from .models import OrdnanceMarker

FORMATIONS = ("close", "loose")


def _roles(marker: OrdnanceMarker):
    from .ordnance import craft_roles
    return craft_roles(marker.ordnance_type)


def wave_rank(marker: OrdnanceMarker) -> int:
    """0 pure fighters, 1 multi-role craft that can act as fighters, 2 the rest."""
    roles = set(_roles(marker))
    if roles == {"fighter"}:
        return 0
    return 1 if "fighter" in roles else 2


def order_for_wave(markers: List[OrdnanceMarker]) -> List[OrdnanceMarker]:
    """Wave order: fighters first, then multi-role fighters, then other craft
    (stable within each group)."""
    return sorted(markers, key=wave_rank)


def form_wave(game_state, marker_ids: List[str], formation: str = "close") -> str:
    """Combine attack craft markers (launched together) into one wave, stacked
    on the lead marker's position. Returns the wave id ("" if fewer than two)."""
    if formation not in FORMATIONS:
        raise ValueError(f"formation must be one of {FORMATIONS}")
    markers = [OrdnanceMarker.from_dict(o) for o in game_state.ordnance
               if o["id"] in set(marker_ids)]
    if len(markers) < 2:
        return ""
    wid = f"wave_{uuid.uuid4().hex[:8]}"
    ordered = order_for_wave(markers)
    lead = ordered[0]
    for i, m in enumerate(ordered):
        m.wave_id, m.wave_order, m.wave_formation = wid, i, formation
        m.x, m.y, m.heading = lead.x, lead.y, lead.heading
        m.cap_ship_id = ""                      # a wave is never on CAP (s.26)
        _write(game_state, m)
    return wid


def _write(game_state, marker: OrdnanceMarker) -> None:
    for i, o in enumerate(game_state.ordnance):
        if o["id"] == marker.id:
            game_state.ordnance[i] = marker.to_dict()
            return


def members(markers: List[OrdnanceMarker], wave_id: str,
            removed=frozenset()) -> List[OrdnanceMarker]:
    """The wave's markers still in play, lead first."""
    return sorted((m for m in markers if wave_id and m.wave_id == wave_id
                   and m.id not in removed), key=lambda m: m.wave_order)


def is_lead(marker: OrdnanceMarker, markers: List[OrdnanceMarker],
            removed=frozenset()) -> bool:
    """A marker not in a wave is its own lead; in a wave only the frontmost
    surviving squadron interacts (s.25 Waves against ordnance)."""
    if not marker.wave_id:
        return True
    ms = members(markers, marker.wave_id, removed)
    return bool(ms) and ms[0].id == marker.id


def wave_speed(ms: List[OrdnanceMarker]) -> float:
    """A wave moves at the speed of its slowest squadron."""
    return min(m.speed for m in ms)


def split_from_wave(game_state, marker_ids: List[str]) -> str:
    """Squadrons split off a wave (when it moves): alone, or as a new wave in
    the same formation. They can never rejoin. Returns the new wave id or ""."""
    ids = set(marker_ids)
    split = [OrdnanceMarker.from_dict(o) for o in game_state.ordnance if o["id"] in ids]
    if not split:
        return ""
    formation = split[0].wave_formation or "close"
    if len(split) == 1:
        m = split[0]
        m.wave_id, m.wave_order, m.wave_formation = "", 0, ""
        _write(game_state, m)
        new = ""
    else:
        new = f"wave_{uuid.uuid4().hex[:8]}"
        for i, m in enumerate(order_for_wave(split)):
            m.wave_id, m.wave_order, m.wave_formation = new, i, formation
            _write(game_state, m)
    _dissolve_if_single(game_state)
    return new


def _dissolve_if_single(game_state) -> None:
    """A "wave" left with one squadron is just that squadron."""
    counts: Dict[str, int] = {}
    for o in game_state.ordnance:
        if o.get("wave_id"):
            counts[o["wave_id"]] = counts.get(o["wave_id"], 0) + 1
    for i, o in enumerate(game_state.ordnance):
        if o.get("wave_id") and counts[o["wave_id"]] == 1:
            game_state.ordnance[i] = {**o, "wave_id": "", "wave_order": 0, "wave_formation": ""}


def tidy_waves(game_state) -> None:
    """After markers are removed: renumber each wave from 0 and dissolve waves
    of one."""
    by: Dict[str, List[int]] = {}
    for i, o in enumerate(game_state.ordnance):
        if o.get("wave_id"):
            by.setdefault(o["wave_id"], []).append(i)
    for wid, idx in by.items():
        idx.sort(key=lambda i: game_state.ordnance[i].get("wave_order", 0))
        for n, i in enumerate(idx):
            game_state.ordnance[i] = {**game_state.ordnance[i], "wave_order": n}
    _dissolve_if_single(game_state)


def whole_wave_ids(game_state, marker_id: str) -> List[str]:
    """Every marker id in the same wave as marker_id (just it, if none):
    shooting removes a whole wave with one hit (s.25)."""
    o = next((o for o in game_state.ordnance if o["id"] == marker_id), None)
    if o is None:
        return []
    wid = o.get("wave_id")
    if not wid:
        return [marker_id]
    return [x["id"] for x in game_state.ordnance if x.get("wave_id") == wid]


def wave_label(ms: List[OrdnanceMarker]) -> str:
    """Open information (s.25): what a wave contains, lead first."""
    return ", ".join(m.ordnance_type.replace("_", " ") for m in ms)


def ship_attack_plan(group: List[OrdnanceMarker], turret_kills: int,
                     mr_suppress: Optional[Dict[str, bool]] = None) -> Dict:
    """How a wave (or a lone squadron) attacking a ship resolves after the
    ship's turrets fire once at it (s.25, s.27).

    group: the wave's markers, lead first. turret_kills: turret successes, each
    removing one squadron from the front. mr_suppress: {marker id: True} for
    multi-role fighter-bombers that suppress turrets instead of attacking
    (chosen before the turrets fire; they must be at the front).

    Returns {"killed": [ids], "attackers": [markers], "suppressors": n,
    "suppressed": set of bomber ids making exactly 3 (4) attacks,
    "removed_after": [ids of every marker in the group]}."""
    mr_suppress = mr_suppress or {}
    killed = group[:turret_kills]
    alive = group[turret_kills:]
    suppressors = []
    attackers = []
    for m in alive:
        roles = _roles(m)
        # Pure fighters suppress turrets; multi-role fighter-bombers may instead
        # of attacking (s.27)
        if set(roles) == {"fighter"} or (mr_suppress.get(m.id) and "bomber" in roles):
            suppressors.append(m)
        elif any(r in roles for r in ("bomber", "assault_boat")):
            attackers.append(m)
    # Fighta-Bommerz can't suppress turrets; Mantas aren't fighters
    from .models import OrdnanceType
    suppressors = [m for m in suppressors
                   if m.ordnance_type != OrdnanceType.FIGHTA_BOMMER.value]
    bombers = [m for m in attackers if "bomber" in _roles(m)]
    suppressed = {m.id for m in bombers[:len(suppressors)]}
    return {"killed": [m.id for m in killed], "attackers": attackers,
            "suppressors": len(suppressors), "suppressed": suppressed,
            "removed_after": [m.id for m in group]}


def mr_suppress_candidates(group: List[OrdnanceMarker]) -> List[OrdnanceMarker]:
    """Multi-role squadrons in the wave that can act as fighters and bombers
    and so may suppress turrets instead of attacking (s.27); Fighta-Bommerz
    never suppress."""
    from .models import OrdnanceType
    return [m for m in group if {"fighter", "bomber"} <= set(_roles(m))
            and m.ordnance_type != OrdnanceType.FIGHTA_BOMMER.value]


def apply_mr_suppress(group: List[OrdnanceMarker], n: int):
    """Choose `n` multi-role squadrons to suppress (s.27): they move as close to
    the front as possible (after pure fighters), so turrets remove them first.
    At least one squadron must still attack. Returns (reordered group,
    {id: True})."""
    cands = mr_suppress_candidates(group)
    attackers = [m for m in group if any(r in _roles(m) for r in ("bomber", "assault_boat"))]
    n = max(0, min(n, len(cands), len(attackers) - 1))
    chosen = cands[:n]
    fighters = [m for m in group if set(_roles(m)) == {"fighter"}]
    rest = [m for m in group if m not in fighters and m not in chosen]
    return fighters + chosen + rest, {m.id: True for m in chosen}


def best_mr_suppress(group: List[OrdnanceMarker], turrets: int, p_turret: float,
                     armour: int) -> int:
    """AI: how many multi-role squadrons should suppress, by expected hits on
    the ship: turrets remove about turrets x p squadrons from the front, each
    surviving fighter suppresses one bomber (exactly 3 attacks), unsuppressed
    bombers make D6 attacks less one per turret."""
    ph = max(1, 7 - armour) / 6.0
    plain = sum(max(0, k - turrets) for k in range(1, 7)) / 6.0
    kills = int(round(turrets * p_turret))
    best_n, best_v = 0, -1.0
    for n in range(len(mr_suppress_candidates(group)) + 1):
        g, sup = apply_mr_suppress(group, n)
        plan = ship_attack_plan(g, min(kills, len(g)), sup)
        v = sum((3.0 if m.id in plan["suppressed"] else plain) * ph
                for m in plan["attackers"] if "bomber" in _roles(m))
        if v > best_v + 1e-9:
            best_n, best_v = n, v
    return best_n
