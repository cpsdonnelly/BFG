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
                     armour: int, shots: Optional[int] = None) -> int:
    """AI / "Auto (best)": how many multi-role squadrons should suppress (s.27).
    It depends on the target's turrets and the wave's size and make-up:
    - the turrets roll `shots` dice (its turrets plus massed turrets), each
      success removing a squadron from the front of the wave, where the
      suppressors stand; the expectation is over every possible number of
      kills (binomial), not a rounded average;
    - each surviving suppressor (pure fighter or multi-role) gives one bomber
      exactly 3 attacks; the others make D6 attacks less one per turret (the
      ship's own turrets only, never massed).
    Returns the number with the most expected hits on the ship."""
    from math import comb
    shots = turrets if shots is None else shots
    ph = max(1, 7 - armour) / 6.0
    plain = sum(max(0, k - turrets) for k in range(1, 7)) / 6.0
    dist = [comb(shots, k) * p_turret ** k * (1 - p_turret) ** (shots - k)
            for k in range(shots + 1)]
    best_n, best_v = 0, -1.0
    for n in range(len(mr_suppress_candidates(group)) + 1):
        g, sup = apply_mr_suppress(group, n)
        v = 0.0
        for kills, pk in enumerate(dist):
            plan = ship_attack_plan(g, min(kills, len(g)), sup)
            v += pk * sum((3.0 if m.id in plan["suppressed"] else plain) * ph
                          for m in plan["attackers"] if "bomber" in _roles(m))
        if v > best_v + 1e-9:
            best_n, best_v = n, v
    return best_n


def _save_p(save: int) -> float:
    """Chance to pass a resilient save of `save`+ (0 = no save)."""
    return 0.0 if not save else max(0, 7 - save) / 6.0


def cap_survivors(fighters: int, bombers: int, cap: int, f_save: int = 0,
                  b_save: int = 0, cap_save: int = 0) -> dict:
    """Distribution of (fighters, bombers) left after a wave meets `cap` enemy
    CAP fighter squadrons (s.26: CAP intercepts on contact, before the turrets
    fire). Each CAP squadron meets the wave's lead squadron (fighters lead).
    Interception removes both markers, except that a resilient squadron
    passing its save stays in play (s.23). A save is used once per phase: a
    squadron that passed stays the lead and is removed by the next CAP
    squadron it meets (removing that one too); if both sides pass, both are
    removed. A resilient CAP fighter that passes stays and meets the next lead
    squadron without a save."""
    from functools import lru_cache
    pf, pb, pc = _save_p(f_save), _save_p(b_save), _save_p(cap_save)

    @lru_cache(maxsize=None)
    def go(f, b, c, lead_used, cap_used):
        if c <= 0 or f + b <= 0:
            return {(f, b): 1.0}
        lead_f = f > 0
        ps = 0.0 if lead_used else (pf if lead_f else pb)
        pcap = 0.0 if cap_used else pc
        nf, nb = (f - 1, b) if lead_f else (f, b - 1)
        out = {}

        def add(dist, w):
            if w <= 0:
                return
            for k, v in dist.items():
                out[k] = out.get(k, 0.0) + v * w
        add(go(nf, nb, c - 1, False, False), ps * pcap + (1 - ps) * (1 - pcap))  # both removed
        add(go(f, b, c - 1, True, False), ps * (1 - pcap))          # lead saved, CAP gone
        add(go(nf, nb, c, False, True), (1 - ps) * pcap)            # CAP saved, lead gone
        return out
    return go(fighters, bombers, cap, False, False)


def wave_split_value(fighters: int, bombers: int, turrets: int, shots: int, cap: int,
                     armour: int, p_turret: float = 0.5, f_save: int = 0,
                     b_save: int = 0, cap_save: int = 0) -> float:
    """Expected hits on a ship from a wave of `fighters` then `bombers` (s.25,
    s.27). Enemy CAP fighters intercept first (cap_survivors; resilient saves
    f_save / b_save / cap_save, 0 = none, s.23); then the turrets roll `shots`
    dice (its turrets plus massed turrets), each success removing a squadron
    from the front (resilient saves don't work against turrets); each surviving
    fighter gives one bomber exactly 3 attacks, the other bombers make D6
    attacks less one per turret (its own turrets only). Resilient bombers that
    saved against CAP still attack (s.26)."""
    from math import comb
    if bombers <= 0:
        return 0.0
    ph = max(1, 7 - armour) / 6.0
    plain = sum(max(0, k - turrets) for k in range(1, 7)) / 6.0
    total = 0.0
    for (f0, b0), pw in cap_survivors(fighters, bombers, cap, f_save, b_save, cap_save).items():
        n = f0 + b0
        for kills in range(shots + 1):
            pk = comb(shots, kills) * p_turret ** kills * (1 - p_turret) ** (shots - kills)
            lost = min(n, kills)                     # from the front: fighters first
            f_left = max(0, f0 - lost)
            b_left = b0 - max(0, lost - f0)
            sup = min(f_left, b_left)
            total += pw * pk * (sup * 3.0 + (b_left - sup) * plain) * ph
    return total


def best_wave_split(slots: int, turrets: int, shots: int, cap: int, armour: int,
                    p_turret: float = 0.5, f_save: int = 0, b_save: int = 0,
                    cap_save: int = 0):
    """For fleets without multi-role craft: how many of `slots` squadrons in
    one wave should be fighters and how many bombers against a target with
    `turrets` (and `shots` turret dice incl. massed turrets) and `cap` enemy
    CAP fighter squadrons, with the craft's resilient saves (0 = none).
    `slots` is the wave size: it may be less than the ship's launch capacity
    when other bays launch lone fighters or CAP. Returns (fighters, bombers,
    expected hits)."""
    def val(f):
        return wave_split_value(f, slots - f, turrets, shots, cap, armour, p_turret,
                                f_save, b_save, cap_save)
    best = (0, slots, val(0))
    for f in range(1, slots):
        v = val(f)
        if v > best[2] + 1e-9:
            best = (f, slots - f, v)
    return best


def wave_plan_inputs(target, gs) -> dict:
    """The wave planner's inputs read from a target as it is now: innate
    turrets, massed turrets, enemy CAP fighter squadrons escorting it and their
    best resilient save, its lowest Armour and whether it has Ork turrets (5+)."""
    from .ordnance import craft_roles, ordnance_turrets, get_massed_turret_bonus
    caps = [o for o in gs.ordnance if o.get("cap_ship_id") == target.id
            and "fighter" in craft_roles(o["ordnance_type"])]
    return {"turrets": ordnance_turrets(target, gs),
            "massed": get_massed_turret_bonus(target, gs.get_ships()),
            "cap": len(caps), "armour": target.lowest_armor_value,
            "cap_save": max((o.get("resilient_save") or 0 for o in caps), default=0),
            "ork": "ork_turrets" in target.special_rules}


def split_craft_types(ship, craft_types):
    """(fighter type, bomber type, fighter save, bomber save) when the ship's
    bays offer one plain fighter and one plain bomber type and no multi-role
    craft (those use the s.27 suppression choice instead), else None."""
    from .ordnance import craft_roles, craft_stats
    bay_ws = [w for w in ship.weapons if w.get("weapon_type") == "launch_bay"]
    stats = {ct: craft_stats(ct, bay_ws) for ct in craft_types}
    roles = {ct: set(craft_roles(st[0])) for ct, st in stats.items()}
    if any(len(r) > 1 for r in roles.values()):
        return None
    fk = next((ct for ct, r in roles.items() if r == {"fighter"}), None)
    bk = next((ct for ct, r in roles.items() if r == {"bomber"}), None)
    if not fk or not bk:
        return None
    return fk, bk, stats[fk][2] or 0, stats[bk][2] or 0


def plan_wave_against(slots: int, inputs: dict, f_save: int = 0, b_save: int = 0):
    """best_wave_split from wave_plan_inputs-style inputs (any of f_save / b_save
    / cap_save in `inputs` override the arguments)."""
    t = inputs["turrets"]
    p = (7 - (5 if inputs.get("ork") else 4)) / 6.0
    return best_wave_split(slots, t, t + inputs["massed"], inputs["cap"], inputs["armour"], p,
                           inputs.get("f_save", f_save), inputs.get("b_save", b_save),
                           inputs.get("cap_save", 0))


def resolve_cap_vs_group(group, caps, dice, gs) -> dict:
    """Enemy CAP fighters meet an incoming wave (or lone squadron) on contact,
    before the turrets fire (s.26). Each CAP squadron intercepts the group's
    current lead squadron (fighters lead, `group` in wave order); interception
    removes both unless a resilient save is passed (s.23, resolve_fighter_
    intercept: a save once per phase, both passing removes both). A lead that
    saved stays the lead and meets the next CAP squadron without a save; a CAP
    squadron that saved meets the next lead without one.
    Returns {"survivors": [...], "removed": [ids], "cap_removed": [ids]}."""
    from .ordnance import resolve_fighter_intercept
    survivors = list(group)
    removed, cap_removed = [], []
    for cap in caps:
        while survivors:
            lead = survivors[0]
            gs.add_log(f"  CAP fighter intercepts the lead {lead.ordnance_type} squadron")
            res = resolve_fighter_intercept(cap, lead, dice, gs)
            if res["target_removed"]:
                removed.append(survivors.pop(0).id)
            if res["fighter_removed"]:
                cap_removed.append(cap.id)
                break
        if not survivors:
            break
    return {"survivors": survivors, "removed": removed, "cap_removed": cap_removed}


def bomber_squadron_value(target, gs, suppressed: bool = False) -> float:
    """Expected VP of one bomber squadron that reaches the target (s.20): D6
    attacks less one per turret (the ship's own, not massed; exactly 3 when a
    fighter suppresses), each hitting on its lowest Armour."""
    from .ordnance import ordnance_turrets
    from .ai_hazards import value_per_hit, ship_value
    t = ordnance_turrets(target, gs)
    p_hit = max(1, 7 - target.lowest_armor_value) / 6.0
    counts = [3] if suppressed else [max(0, k - t) for k in range(1, 7)]
    if target.hits_remaining <= 1:
        # one hit destroys it: worth the ship once, whatever the number of hits
        p_any = sum(1 - (1 - p_hit) ** a for a in counts) / len(counts)
        return p_any * ship_value(target, gs)
    attacks = sum(counts) / len(counts)
    return attacks * p_hit * max(1.0, value_per_hit(target, gs))


def raid_squadron_value(target, gs, owner: int, rules=None) -> float:
    """Expected VP of one assault boat squadron that reaches the target (s.22:
    one hit-and-run raid, no Armour roll): the mean over a D6 of
    hit_and_run.raid_result_value, with the crews' raid modifiers."""
    from .hit_and_run import raid_result_value, _raid_roll_modifier
    mod = _raid_roll_modifier(list(rules or []), target)
    return sum(raid_result_value(r + mod, target, gs, owner) for r in range(1, 7)) / 6.0


def expected_survivors(n: int, shots: int, cap: int, p_turret: float = 0.5,
                       save: int = 0, cap_save: int = 0) -> float:
    """Expected squadrons of a wave of `n` identical attackers left after the
    target's CAP (cap_survivors) and its turret roll (`shots` dice, no saves)."""
    from math import comb
    total = 0.0
    for (_f, b0), pw in cap_survivors(0, n, cap, 0, save, cap_save).items():
        for kills in range(shots + 1):
            pk = comb(shots, kills) * p_turret ** kills * (1 - p_turret) ** (shots - kills)
            total += pw * pk * max(0, b0 - kills)
    return total


def best_attack_mode(target, gs, owner: int, rules=None) -> str:
    """"bomber" or "assault_boat", whichever is worth more in expected VP per
    squadron that reaches the target (owner idea: assault boats ignore Armour,
    so they beat bombers against heavily armoured, high-turret ships; bombers
    win against escorts, which raids only damage on 4+)."""
    if not getattr(gs, "rule_hit_and_run", True):
        return "bomber"
    b = bomber_squadron_value(target, gs)
    a = raid_squadron_value(target, gs, owner, rules)
    return "assault_boat" if a > b else "bomber"
