"""Squadron rules and the squadron organiser (owner: the AI forms and
reorganises escort and capital ship squadrons, players can too, and the
squadron rules are always kept).

Rules (core s.8 and "Forming Squadrons", XR p.58, unless a list says otherwise):
  - escorts are squadroned when the fleet is chosen: 2-6 a squadron, at most
    four 2-hit escorts, classes may mix (fleet_lists.escort_squadron_limits:
    Tyranids 1-12 / Vanguard 6-12, Kraken count two, at most 4 a squadron);
    a fleet with two or more escorts leaves none on its own, except those
    allowed alone (transports, Tau Messengers, the Sword of Eldanesh);
  - capital ships are squadroned at the start of a game, before deployment:
    cruisers of every kind but grand cruisers 2-4 and may mix; battleships
    2-3, grand cruisers 2-3, never mixed with each other (reading: nor grand
    cruisers with other cruisers);
  - never: defences, Tyranid primary hive ships and Scylla with synapse nodes
    (every Tyranid synapse capital ship), ships of different factions (allies
    of convenience), xenos cutters with any other type, Nicassar Dhows with Tau
    escorts, the Sword of Eldanesh with other escorts; support assets only
    with their own category, six 1-hit ships or four others, none over 10
    hits (Support Assets);
  - Tyranid Kraken, Vanguard and escort drones: every one of a class in a
    squadron carries the same weapon.

Works on fleet rows (`fleet_model.make_fleet_row`, the entry is the profile)
and on game ships alike (`_info`)."""
import random
from typing import Callable, Dict, List, Optional

TYRANID_SAME_WEAPON = ("Kraken", "Vanguard Drone", "Escort Drone")
ALONE_OK = ("Messenger Starship", "Sword of Eldanesh (Alaitoc)")
CAPITAL_SQUADRON_CHANCE = 0.5    # judgement: how often the AI squadrons a matching group
CAPITAL_SQUADRON_MAX = 3         # judgement: the AI's largest capital squadron


class _I:
    """What the rules need of a row or a ship."""
    __slots__ = ("cls", "faction", "type", "hits", "rules", "weapons", "speed",
                 "upgrades", "points", "flagship", "obj")


def _info(x) -> _I:
    i = _I()
    i.obj = x
    if isinstance(x, dict):
        e = x["entry"]
        i.upgrades = list(x.get("upgrades", []))
        i.points = x.get("points", e.points_cost)
        i.flagship = bool(x.get("is_flagship"))
    else:
        e = x
        i.upgrades = list(getattr(x, "upgrades", []) or [])
        i.points = getattr(x, "points_value", 0)
        i.flagship = bool(getattr(x, "is_flagship", False))
    i.cls = e.ship_class
    i.faction = e.faction
    i.type = e.ship_type
    i.hits = e.hits_max
    i.rules = list(e.special_rules or [])
    i.weapons = list(e.weapons or [])
    i.speed = e.speed
    return i


def get_sid(x) -> str:
    return (x.get("squadron_id", "") if isinstance(x, dict) else x.squadron_id) or ""


def set_sid(x, sid: str) -> None:
    if isinstance(x, dict):
        x["squadron_id"] = sid
    else:
        x.squadron_id = sid


def size_class(i: _I) -> str:
    """escort, cruiser (all cruisers but grand), grand_cruiser, battleship, defense."""
    if i.type in ("escort", "defense", "battleship"):
        return i.type
    return "grand_cruiser" if "grand cruiser" in i.cls.lower() else "cruiser"


def never_squadroned(i: _I) -> Optional[str]:
    """Why a ship may never be in a squadron, or None."""
    if i.type == "defense" and "fleet_support" not in i.rules:
        return "defences cannot form squadrons"
    if i.type != "escort" and any(r.startswith("synapse:") for r in i.rules):
        return "Tyranid primary hive ships and Scylla with synapse nodes cannot be squadroned"
    if "daemonship" in i.rules:
        return "daemonships must operate alone"
    if "fleet_support" in i.rules and i.hits > 10:
        return "support assets with more than 10 hits cannot form squadrons"
    return None


def alone_ok(i: _I) -> bool:
    return (i.cls in ALONE_OK or any(r.startswith("transport:") for r in i.rules)
            or "fleet_support" in i.rules)


def _support_kind(i: _I) -> str:
    if "fleet_support" not in i.rules:
        return "warship"
    return "convoy" if any(r.startswith("transport:") for r in i.rules) else "system"


def _tyranid_weapon(i: _I) -> str:
    return next((u for u in i.upgrades if u.startswith("Weapon:")), "")


def squadron_errors(members: List, sid: str, list_key: str = "") -> List[str]:
    """Every rule one squadron breaks."""
    infos = [_info(m) for m in members]
    errors: List[str] = []
    for i in infos:
        why = never_squadroned(i)
        if why:
            errors.append(f"Squadron '{sid}': {i.cls}: {why}.")
    if errors:
        return errors
    if len({i.faction for i in infos}) > 1:
        errors.append(f"Squadron '{sid}': ships of different factions cannot be squadroned "
                      f"together (allies of convenience).")
    kinds = {size_class(i) for i in infos}
    if len(kinds) > 1:
        errors.append(f"Squadron '{sid}': cannot mix {', '.join(sorted(kinds))}.")
        return errors
    kind = next(iter(kinds))
    n = len(infos)
    if len({_support_kind(i) for i in infos}) > 1:
        errors.append(f"Squadron '{sid}': support assets only squadron with their own "
                      f"category, never with warships.")
    elif _support_kind(infos[0]) != "warship":
        cap = 6 if all(i.hits <= 1 for i in infos) else 4
        if n > cap:
            errors.append(f"Squadron '{sid}': at most {cap} of these support units (has {n}).")
        return errors
    if kind == "escort":
        from .fleet_lists import escort_squadron_errors
        errors += escort_squadron_errors(list_key, [{"entry": _Entry(i)} for i in infos], sid)
        clss = {i.cls for i in infos}
        if "Xenos Cutter" in clss and len(clss) > 1:
            errors.append(f"Squadron '{sid}': xenos cutters cannot be squadroned with other types.")
        if "Sword of Eldanesh (Alaitoc)" in clss and n > 1:
            errors.append(f"Squadron '{sid}': the Sword of Eldanesh cannot be squadroned.")
        if "Nicassar Dhow" in clss and any(i.faction.startswith("tau") and i.cls != "Nicassar Dhow"
                                           for i in infos):
            errors.append(f"Squadron '{sid}': Nicassar Dhows may not be squadroned with Tau escorts.")
        for c in TYRANID_SAME_WEAPON:
            if len({_tyranid_weapon(i) for i in infos if i.cls == c}) > 1:
                errors.append(f"Squadron '{sid}': every {c} in a squadron must have the "
                              f"same weapon.")
    elif kind == "cruiser":
        if not 2 <= n <= 4:
            errors.append(f"Squadron '{sid}': cruiser squadrons need 2–4 ships (has {n}).")
    elif kind in ("battleship", "grand_cruiser"):
        what = "battleship" if kind == "battleship" else "grand cruiser"
        if not 2 <= n <= 3:
            errors.append(f"Squadron '{sid}': {what} squadrons need 2–3 ships (has {n}).")
    return errors


class _Entry:
    """The bit of a profile escort_squadron_errors reads."""
    def __init__(self, i: _I):
        self.ship_class, self.hits_max = i.cls, i.hits


def fleet_squadron_errors(items: List, list_key: str = "") -> List[str]:
    """Every squadron's problems, and escorts left on their own when the
    fleet has two or more (unless allowed alone, or the list takes 1-ship
    squadrons)."""
    from .fleet_lists import escort_squadron_limits
    errors: List[str] = []
    by: Dict[str, List] = {}
    for x in items:
        if get_sid(x):
            by.setdefault(get_sid(x), []).append(x)
    for sid, members in by.items():
        errors += squadron_errors(members, sid, list_key)
    escorts = [_info(x) for x in items if _info(x).type == "escort"]
    if len(escorts) >= 2 and escort_squadron_limits(list_key)["min"] > 1:
        for x in items:
            i = _info(x)
            if i.type == "escort" and not get_sid(x) and not alone_ok(i):
                errors.append(f"{i.cls}: with two or more escorts in the fleet, every escort "
                              f"must be in a squadron.")
    return errors


# ── The organiser ─────────────────────────────────────────────────────────────

def _escort_key(i: _I) -> tuple:
    """Same class and set-up together (owner: one class to a squadron, and the
    same ordnance combines, s.15)."""
    return (i.cls, _tyranid_weapon(i), tuple(sorted(_row_ordnance(i))))


def _row_ordnance(i: _I) -> set:
    out = set()
    for w in i.weapons:
        t = w.get("weapon_type")
        if t in ("torpedo", "launch_bay", "mine_launcher", "impaler_bay"):
            out.add(t)
    return out


def _new_sid(used: set, prefix: str) -> str:
    n = 1
    while f"{prefix}{n}" in used:
        n += 1
    used.add(f"{prefix}{n}")
    return f"{prefix}{n}"


def _sizes(n: int, lim: dict, rng: random.Random) -> List[int]:
    """Squadron sizes for n escorts of one kind (owner): 2D3 or the escorts
    left, whichever is smaller; a single one left over joins the last
    squadron, which splits in half if that breaks the maximum. Lists with
    other sizes (Tyranids 1-12 / 6-12) split as evenly as their sizes allow."""
    lo, hi = lim["min"], lim["max"]
    if lo != 2 or hi != 6:
        k = max(1, -(-n // hi))
        k = min(k, max(1, n // max(1, lo)))
        return [n // k + (1 if j < n % k else 0) for j in range(k)]
    sizes: List[int] = []
    left = n
    while left > 0:
        s = min(left, rng.randint(1, 3) + rng.randint(1, 3))
        sizes.append(s)
        left -= s
    if len(sizes) > 1 and sizes[-1] == 1:
        sizes.pop()
        sizes[-1] += 1
        if sizes[-1] > hi:
            big = sizes.pop()
            sizes += [big // 2, big - big // 2]
    return sizes


def organize_escorts(items: List, list_key: str = "", rng: Optional[random.Random] = None,
                     log: Optional[Callable[[str], None]] = None,
                     mix: bool = False) -> List[str]:
    """Re-form every escort squadron of the fleet (fleet building: escorts are
    squadroned when chosen, s.8): escorts of one class and set-up together in
    squadrons of 2D3 within the list's sizes (`_sizes`); a lone escort joins a
    squadron of the same ordnance (classes may mix, core s.8); escorts allowed
    alone stay alone when they are the only one of their kind. Every squadron
    is checked against the rules; one that breaks them is split up again into
    the list's even sizes. mix: classes squadron together (a list limit that
    needs it, the list builder's repair). Returns the problems left (fleet_squadron_errors)."""
    from .fleet_lists import escort_squadron_limits
    rng = rng or random.Random(0)
    log = log or (lambda _m: None)
    lim = escort_squadron_limits(list_key)
    escorts = [x for x in items if _info(x).type == "escort"]
    for x in escorts:
        set_sid(x, "")
    used = {get_sid(x) for x in items if get_sid(x)}
    groups: Dict[tuple, List] = {}
    for x in escorts:
        i = _info(x)
        if never_squadroned(i) or i.cls == "Sword of Eldanesh (Alaitoc)":
            continue
        if (lim["mix"] or mix) and i.cls not in TYRANID_SAME_WEAPON:
            key = ("all",)                     # mixing where a list (or a repair) needs it
        else:
            key = _escort_key(i)
        groups.setdefault(key, []).append(x)
    singles = []
    for key, members in groups.items():
        weight = sum(lim["kraken_weight"] if _info(m).cls == "Kraken" else 1 for m in members)
        if len(members) == 1 and lim["min"] > 1:
            singles.append(members[0])
            continue
        sizes = _sizes(weight, lim, rng)
        pos = 0
        for s in sizes:
            sid = _new_sid(used, "esq")
            w = 0
            while pos < len(members) and w < s:
                set_sid(members[pos], sid)
                w += lim["kraken_weight"] if _info(members[pos]).cls == "Kraken" else 1
                pos += 1
        log(f"[squadrons] {key[0]}: {len(members)} escort(s) in squadrons of "
            f"{', '.join(map(str, sizes))}")
    # a lone escort joins a squadron (the same ordnance first) it fits, the
    # squadron splitting in half if it would break the maximum; else it pairs
    # with another lone escort; escorts allowed alone stay alone
    for x in singles:
        i = _info(x)
        if alone_ok(i) or get_sid(x):
            continue
        mine = _row_ordnance(i)
        sids = sorted({get_sid(e) for e in escorts if get_sid(e)})
        sids.sort(key=lambda sd: _row_ordnance(_info(next(
            e for e in escorts if get_sid(e) == sd))) != mine)
        placed = False
        for sid in sids:
            members = [e for e in escorts if get_sid(e) == sid] + [x]
            if not squadron_errors(members, sid, list_key):
                set_sid(x, sid)
                log(f"[squadrons] lone {i.cls} joins squadron {sid}")
                placed = True
                break
            if len(members) >= 4:
                half = len(members) // 2
                sid2 = _new_sid(used, "esq")
                a_, b_ = members[:half], members[half:]
                if not squadron_errors(a_, sid, list_key) and \
                        not squadron_errors(b_, sid2, list_key):
                    for m in b_:
                        set_sid(m, sid2)
                    set_sid(x, sid2 if x in b_ else sid)
                    log(f"[squadrons] lone {i.cls} joins squadron {sid}, which splits in two")
                    placed = True
                    break
                used.discard(sid2)
        if placed:
            continue
        other = next((e for e in singles if e is not x and not get_sid(e)
                      and not alone_ok(_info(e))), None)
        if other is not None:
            sid = _new_sid(used, "esq")
            if squadron_errors([x, other], sid, list_key):
                used.discard(sid)
            else:
                set_sid(x, sid)
                set_sid(other, sid)
                log(f"[squadrons] {i.cls} and {_info(other).cls} squadron together")
    return fleet_squadron_errors(items, list_key)


def _role(i: _I) -> tuple:
    """Similar roles squadron together (owner): carriers, torpedo ships,
    direct fire by its longest range bracket."""
    types = {w.get("weapon_type") for w in i.weapons}
    if "launch_bay" in types:
        return ("carrier",)
    if "torpedo" in types:
        return ("torpedoes",)
    reach = max((w.get("range_cm") or 0 for w in i.weapons
                 if w.get("weapon_type") in ("battery", "lance")), default=0)
    return ("guns", 0 if reach <= 30 else 1 if reach <= 45 else 2)


def form_capital_squadrons(ships: List, list_key: str = "",
                           rng: Optional[random.Random] = None,
                           log: Optional[Callable[[str], None]] = None,
                           chance: float = CAPITAL_SQUADRON_CHANCE,
                           keep_existing: bool = False) -> List[List]:
    """The AI's capital ship squadrons, formed at the start of the game before
    deployment (s.8): ships of one size class, faction, speed and role
    (`_role`) may squadron, 2 to CAPITAL_SQUADRON_MAX (judgement, within the
    rules' 2-4 / 2-3) a squadron, each matching group squadroned with
    `chance` (a logged random draw, To do 31). Never the flagship or a ship
    helping friends in range (both move on their own, judgement), never a
    ship the rules keep alone. Existing capital squadrons are broken up
    first, unless keep_existing (then only those breaking the rules are, and
    the ships in the rest stay as they are). Returns the squadrons formed."""
    from .buffs import buff_kinds
    rng = rng or random.Random(0)
    log = log or (lambda _m: None)
    caps = [x for x in ships if _info(x).type != "escort"]
    if keep_existing:
        by: Dict[str, List] = {}
        for x in caps:
            if get_sid(x):
                by.setdefault(get_sid(x), []).append(x)
        for sid, members in by.items():
            if squadron_errors(members, sid, list_key):
                for x in members:
                    set_sid(x, "")
                log(f"[AI] breaks up squadron {sid} (it breaks the squadron rules)")
        caps = [x for x in caps if not get_sid(x)]
    else:
        for x in caps:
            set_sid(x, "")
    used = {get_sid(x) for x in ships if get_sid(x)}
    pools: Dict[tuple, List] = {}
    for x in caps:
        i = _info(x)
        if never_squadroned(i) or i.flagship or buff_kinds(i.obj if not isinstance(i.obj, dict)
                                                          else i.obj["entry"]):
            continue
        pools.setdefault((size_class(i), i.faction, i.speed, _role(i)), []).append(x)
    formed = []
    for key, members in pools.items():
        cap = min(CAPITAL_SQUADRON_MAX, 3 if key[0] in ("battleship", "grand_cruiser") else 4)
        while len(members) >= 2:
            take = min(cap, len(members))
            if take == len(members) - 1 and take > 2:
                take -= 1                       # don't leave one out if two can go
            group, members = members[:take], members[take:]
            draw = rng.random()
            if draw >= chance:
                log(f"[AI] keeps {', '.join(_info(g).cls for g in group)} apart "
                    f"(draw {draw:.2f})")
                continue
            sid = _new_sid(used, "csq")
            if squadron_errors(group, sid, list_key):
                used.discard(sid)
                continue
            for g in group:
                set_sid(g, sid)
            formed.append(group)
            log(f"[AI] squadrons {', '.join(_info(g).cls for g in group)} together "
                f"(draw {draw:.2f})")
    return formed


def ai_form_squadrons(gs, player: int, log: Optional[Callable[[str], None]] = None,
                      chance: float = CAPITAL_SQUADRON_CHANCE) -> List[List]:
    """At the start of the game, before deployment (s.8), the AI's squadrons:
    escort squadrons re-formed only if the fleet's break the rules (they are
    chosen with the fleet); capital ship squadrons kept if legal, the rest of
    its capital ships squadroned by `form_capital_squadrons`. Random draws
    from the game's recorded generator (To do 31). Ships written back."""
    from .rng import game_random
    log = log or (lambda _m: None)
    rng = game_random(gs, "squadrons")
    ships = [s for s in gs.player_ships(player) if s.status not in ("reserve",)]
    # ships don't carry their fleet list: only the Tyranid squadron sizes
    # differ by list (a fleet without synapse creatures plays as the Vanguard)
    list_key = ""
    if any(s.faction == "tyranids" for s in ships):
        from .tyranids import is_synapse_creature
        list_key = ("tyranid_hive" if any(is_synapse_creature(s) for s in ships)
                    else "tyranid_vanguard")
    escorts = [s for s in ships if s.ship_type == "escort"]
    if fleet_squadron_errors(escorts, list_key):
        organize_escorts(escorts, list_key, rng, log)
    formed = form_capital_squadrons(ships, list_key, rng, log, chance, keep_existing=True)
    for s in ships:
        gs.update_ship(s)
    return formed
