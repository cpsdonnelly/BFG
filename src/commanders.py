"""Commander placement after the Leadership roll (To do 29, owner): "All
commanders must be assigned to an appropriate ship during deployment" (s.5,
pre-battle step 7, after the Ld roll in step 6). The fleet builder buys the
commander on a ship; at deployment, before any ship is placed, a player may move
the fleet commander (with the options that belong to him: his re-rolls and
anything that requires him) to another of its capital ships, where the fleet list
doesn't fix his ship (owner: e.g. Chaos lists put him on the most expensive
capital ship; Tyranid hive ships work differently, so Tyranids never move one).

A move works on the ship profiles: the difference the commander's options make
to a ship (from its catalog entry, built with and without them: Leadership,
re-rolls, flagship, points, rules) comes off the ship he leaves and goes on the
ship he joins. The ship he leaves rolls its own Leadership then (it never rolled:
a commander's ship takes his fixed Ld); the ship he joins keeps its rolled value
in an `own_ld:<n>` tag, so a later move gives it back.

The AI (and "Auto") places him on the capital ship with the lowest Leadership
(where his fixed Ld gains most), unless the dearest allowed ship costs at least
twice the next (`DEAREST_RATIO`, judgement: the Lord on the Cairn), or, in Kill
the Admiral, on the hardest ship to kill (owner)."""
from typing import Callable, List, Optional

DEAREST_RATIO = 2.0          # judgement


def _entry(ship):
    from .ship_catalog import find_ship_class
    return find_ship_class(ship.ship_class)


def fleet_list_of(ship) -> str:
    return next((r.split(":", 1)[1] for r in ship.special_rules
                 if r.startswith("fleet_list:")), "")


def commander_options(ship) -> List[str]:
    """The fleet commander's options on the ship: the commander and his
    re-rolls / upgrades (as victory_points.commander_points counts them), and
    the options that require one of those (a Chapter tactic, honour guards,
    Mark of Chaos Undivided, an Ork Boss's kustoms...). [] if none."""
    entry = _entry(ship)
    if entry is None or "fleet_commander" not in ship.special_rules:
        return []
    from .victory_points import _COMMANDER_GROUPS
    have = set(ship.upgrades or [])
    by_name = {u.name: u for u in entry.upgrades_available if u.name in have}
    core = set()
    for n, u in by_name.items():
        eff = u.effect or {}
        rules = eff.get("add_special_rules", [])
        if (any(r in _COMMANDER_GROUPS for r in u.restrictions) or eff.get("rerolls")
                or "fleet_commander" in rules):
            if "secondary_commander" not in rules:
                core.add(n)
    if not core:
        return []
    grew = True
    while grew:                             # options that require the commander
        grew = False
        for n, u in by_name.items():
            if n in core:
                continue
            for r in u.restrictions:
                if r.startswith("requires:") and r.split(":", 1)[1] in core or \
                        r.startswith("requires_any:") and set(r.split(":", 1)[1].split("|")) & core:
                    core.add(n)
                    grew = True
                    break
    return [u for u in ship.upgrades if u in core]


def _profile(ship, upgrades):
    return _entry(ship).to_ship_dict(name=ship.name, player=ship.player, upgrades=upgrades)


def allowed_ships(gs, player: int) -> List:
    """The capital ships the player's fleet commander may move to (including
    where he is): every capital ship offering all his options, with no option
    restriction broken and the fleet list's placement rule kept
    (fleet_lists.commander_placement_errors). [] when he can't move."""
    ships = [s for s in gs.player_ships(player) if not s.is_destroyed and s.status == "active"]
    holder = next((s for s in ships if commander_options(s)), None)
    if holder is None or any(r == "tyranid" for r in holder.special_rules):
        return []
    opts = commander_options(holder)
    from .booklet_options import ship_option_errors
    from .fleet_model import make_fleet_row
    from .fleet_lists import commander_placement_errors
    from .ship_catalog import get_upgrades_for_ship
    key = fleet_list_of(holder)
    out = []
    for s in ships:
        if s.ship_type == "escort" or s.ship_type == "defense":
            continue
        e = _entry(s)
        if e is None:
            continue
        names = {u.name for u in get_upgrades_for_ship(e)}
        if s is not holder and not set(opts) <= names:
            continue
        new = (list(s.upgrades) + [o for o in opts if o not in s.upgrades]
               if s is not holder else list(s.upgrades))
        if ship_option_errors(e, new):
            continue
        rows = []
        for o in ships:
            ups = (new if o is s else
                   [u for u in o.upgrades if u not in opts] if o is holder else list(o.upgrades))
            oe = _entry(o)
            if oe is not None:
                rows.append(make_fleet_row(oe, upgrades=ups, list_key=key))
        if key and commander_placement_errors(key, rows):
            continue
        out.append(s)
    return out if len(out) > 1 else []


def _diff(without: dict, with_: dict):
    """What the commander's options change in a profile."""
    out = {}
    for k, v in with_.items():
        a = without.get(k)
        if k in ("id", "name", "upgrades", "leadership", "leadership_table") or a == v:
            continue
        if isinstance(v, list):
            out[k] = ("list", [x for x in v if x not in (a or [])],
                      [x for x in (a or []) if x not in v])
        elif isinstance(v, (int, float)) and not isinstance(v, bool) and isinstance(a, (int, float)):
            out[k] = ("delta", v - a)
        else:
            out[k] = ("set", a, v)
    return out


def _ld_always(rules) -> int:
    return sum(int(r.split(":")[1]) for r in rules if r.startswith("ld_always:"))


def move_commander(gs, to_id: str, dice, log: Optional[Callable[[str], None]] = None) -> bool:
    """Move the player's fleet commander (and the options belonging to him)
    to the ship `to_id`. The ship he leaves rolls its own Ld (on its table)
    unless it already rolled one; the ship he joins keeps its rolled Ld for
    later. Ships written back to `gs`."""
    log = log or gs.add_log
    target = gs.get_ship_by_id(to_id)
    if target is None:
        return False
    allowed = allowed_ships(gs, target.player)
    if not any(s.id == to_id for s in allowed):
        return False
    source = next(s for s in gs.player_ships(target.player) if commander_options(s))
    if source.id == to_id:
        return True
    opts = commander_options(source)
    src_with = _profile(source, list(source.upgrades))
    src_without = _profile(source, [u for u in source.upgrades if u not in opts])
    tgt_without = _profile(target, list(target.upgrades))
    tgt_with = _profile(target, list(target.upgrades) + opts)
    for ship, change, sign in ((source, _diff(src_without, src_with), -1),
                               (target, _diff(tgt_without, tgt_with), +1)):
        for k, ch in change.items():
            cur = getattr(ship, k, None)
            if ch[0] == "list":
                added, removed = ch[1], ch[2]
                cur = list(cur or [])
                if sign > 0:
                    cur = [x for x in cur if x not in removed] + [x for x in added if x not in cur]
                else:
                    cur = [x for x in cur if x not in added] + [x for x in removed if x not in cur]
                setattr(ship, k, cur)
            elif ch[0] == "delta":
                setattr(ship, k, (cur or 0) + sign * ch[1])
            else:
                setattr(ship, k, ch[2] if sign > 0 else ch[1])
    # Upgrades
    source.upgrades = [u for u in source.upgrades if u not in opts]
    target.upgrades = list(target.upgrades) + [o for o in opts if o not in target.upgrades]
    # Leadership: the commander's fixed Ld on the ship he joins (with its own
    # "+1 at all times" refits), the ship he leaves its own rolled Ld
    cmd_ld = tgt_with.get("leadership") or src_with.get("leadership") or 0
    own = [r for r in target.special_rules if r.startswith("own_ld:")]
    if not own:
        target.special_rules = list(target.special_rules) + [f"own_ld:{target.leadership}"]
    target.leadership = min(10, cmd_ld + _ld_always(target.special_rules))
    target.leadership_table = ""
    back = next((r for r in source.special_rules if r.startswith("own_ld:")), None)
    if back is not None:
        source.leadership = int(back.split(":")[1])
        source.special_rules = [r for r in source.special_rules if r != back]
    else:
        from .booklet_ships import LEADERSHIP_TABLES
        table_key = src_without.get("leadership_table") or "Default"
        table = LEADERSHIP_TABLES.get(table_key, LEADERSHIP_TABLES["Default"])
        roll = dice.roll_d6(1, f"Starting Leadership for {source.name} ({table_key} table)")[0]
        source.leadership = min(10, table[roll - 1] + _ld_always(source.special_rules))
    source.leadership_table = ""            # rolled now, never again
    gs.update_ship(source)
    gs.update_ship(target)
    log(f"Fleet commander moves from {source.name} (now Ld {source.leadership}) to "
        f"{target.name} (Ld {target.leadership})")
    return True


def best_ship(gs, player: int):
    """Where the AI (and "Auto") puts the commander (judgement): Kill the
    Admiral, the hardest ship to kill; otherwise the dearest allowed ship when
    it costs at least DEAREST_RATIO times the next, else the lowest Ld."""
    ships = allowed_ships(gs, player)
    if not ships:
        return None
    if getattr(gs, "scenario_mode", "") == "kill_admiral":
        from .scenarios import flagship_durability
        return max(ships, key=flagship_durability)
    holder = next(s for s in ships if commander_options(s))
    opts_cost = holder.points_value - _profile(
        holder, [u for u in holder.upgrades if u not in commander_options(holder)])["points_value"]

    def cost(s):
        return s.points_value - (opts_cost if s is holder else 0)

    ranked = sorted(ships, key=cost, reverse=True)
    if len(ranked) > 1 and cost(ranked[0]) >= DEAREST_RATIO * cost(ranked[1]):
        return ranked[0]

    def own_ld(s):
        tag = next((r for r in s.special_rules if r.startswith("own_ld:")), None)
        if tag:
            return int(tag.split(":")[1])
        if s is not holder:
            return s.leadership
        # the commander's ship never rolled: its table's average
        from .booklet_ships import LEADERSHIP_TABLES
        key = _profile(s, [u for u in s.upgrades if u not in commander_options(s)]).get(
            "leadership_table") or "Default"
        table = LEADERSHIP_TABLES.get(key, LEADERSHIP_TABLES["Default"])
        return sum(table) / len(table)
    return min(ships, key=lambda s: (own_ld(s), -cost(s)))


def ai_place_commander(gs, player: int, dice, log=None) -> None:
    """The AI places its fleet commander (before deployment)."""
    best = best_ship(gs, player)
    if best is not None and not commander_options(best):
        move_commander(gs, best.id, dice, log)
