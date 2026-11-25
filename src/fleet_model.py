"""A fleet under construction, without a window (To do 18: rules out of the UI;
To do 24: the AI list builder builds fleets through it too).

A fleet is a list of rows (`make_fleet_row`): a catalog entry, its options,
the fleet list it was taken from and its cost there. `fleet_total` prices it,
`validate_fleet` lists its problems (points, flagships, options, the fleet
list's rules, squadrons) and `fleet_data` turns it into the saved fleet file's
contents (what `fleet_loader` reads). The fleet builder window keeps its rows
in the same form and calls these."""
from typing import Dict, List, Optional

from .ship_catalog import ShipClassEntry, get_upgrades_for_ship


def _lists():
    from .fleet_lists import LISTS
    return LISTS


def make_fleet_row(entry: ShipClassEntry, custom_name: str = "",
                   upgrades: Optional[List[str]] = None,
                   is_flagship: bool = False,
                   squadron_id: str = "",
                   damage: Optional[dict] = None,
                   list_key: str = "", base_cost: Optional[int] = None) -> dict:
    """A fleet row. list_key: the fleet list the ship was taken from (the main
    list, a detachment, or "reserve:<key>"); base_cost: its cost in that list."""
    upgrade_map = {u.name: u for u in get_upgrades_for_ship(entry)}
    upgrade_cost = sum(upgrade_map[u].points_cost
                       for u in (upgrades or []) if u in upgrade_map)
    base = entry.points_cost if base_cost is None else base_cost
    return {
        "list":        list_key,
        "base_cost":   base,
        "entry":       entry,
        "custom_name": custom_name or entry.ship_class,
        "upgrades":    list(upgrades or []),
        "is_flagship": is_flagship,
        "squadron_id": squadron_id,
        "points":      base + upgrade_cost,
        "damage":      damage or {},
    }


def reprice_row(row: dict) -> None:
    """The row's points from its base cost and options (after a change)."""
    upgrade_map = {u.name: u for u in get_upgrades_for_ship(row["entry"])}
    row["points"] = row["base_cost"] + sum(upgrade_map[u].points_cost
                                           for u in row["upgrades"] if u in upgrade_map)


def fleet_total(rows: List[dict]) -> int:
    """Ship points plus fleet-wide adjustments (a Chapter tactic removes the
    Tactical Flexibility discount on Strike Cruiser Variants)."""
    from .booklet_options import tactical_flexibility_refund
    from .fleet_lists import no_tactical_flexibility, notable_xenos_cost
    # Armageddon: its Space Marine ships never had the discount
    no_tf = sum(tactical_flexibility_refund([r.get("upgrades", []) + ["Chapter tactic:"]],
                                            [r["entry"]])
                for r in rows if no_tactical_flexibility(r.get("list") or ""))
    return (sum(r["points"] for r in rows) + no_tf
            + notable_xenos_cost(rows)
            + tactical_flexibility_refund([r.get("upgrades", []) for r in rows],
                                          [r["entry"] for r in rows]))


def validate_fleet(rows: List[dict], list_key: str = "", detachment: str = "",
                   limit: Optional[int] = None) -> List[str]:
    """Every problem with the fleet: empty, over the points limit, more than
    one flagship, ship and fleet option restrictions, the fleet list's rules
    (s.4; points-based limits use what the fleet is worth, owner ruling),
    towed escorts' gravitic hooks and squadron sizes. [] when it is valid.
    limit None: the window reported an unreadable limit."""
    errors: List[str] = []
    if not rows:
        errors.append("Fleet is empty.")
        return errors
    total = fleet_total(rows)
    if limit is None:
        limit = 0
        errors.append("Invalid points limit.")
    if total > limit:
        errors.append(f"Fleet exceeds points limit: {total} > {limit} pts.")

    # A Master of the Fleet's ship is the flagship
    from .booklet_options import commander_names, COMMANDERS, INQ_LORD
    unique_cmds = {"Master of the Fleet (Ld 10)", INQ_LORD} | {
        n for f in COMMANDERS for n in commander_names(f)}
    flagship_count = sum(1 for r in rows if r["is_flagship"]
                         or unique_cmds & set(r.get("upgrades", [])))
    if flagship_count > 1:
        errors.append("Fleet has more than one flagship.")

    from .booklet_options import ship_option_errors, fleet_option_errors
    for r in rows:
        for p in ship_option_errors(r["entry"], r.get("upgrades", [])):
            errors.append(f"{r.get('name', r['entry'].ship_class)}: {p}")
    errors += fleet_option_errors([(r["entry"], r.get("upgrades", [])) for r in rows], total)

    from .fleet_lists import fleet_list_errors, towed_errors
    errors += fleet_list_errors(
        list_key, [{**r, "list": r.get("list") or list_key} for r in rows],
        total, [detachment] if detachment else [])
    errors += towed_errors(rows)

    # Squadrons by ship type
    squadrons: Dict[str, List[dict]] = {}
    for r in rows:
        sid = r.get("squadron_id", "")
        if sid:
            squadrons.setdefault(sid, []).append(r)
    for sid, members in squadrons.items():
        types = {m["entry"].ship_type for m in members}
        if len(types) > 1:
            errors.append(
                f"Squadron '{sid}': cannot mix ship types "
                f"({', '.join(sorted(types))}).")
            continue
        ship_type = next(iter(types))
        count = len(members)
        if ship_type == "escort":
            if count < 2 or count > 6:
                errors.append(
                    f"Squadron '{sid}': escort squadrons need 2–6 ships "
                    f"(has {count}).")
        elif ship_type == "cruiser":
            if count < 2 or count > 4:
                errors.append(
                    f"Squadron '{sid}': cruiser squadrons need 2–4 ships "
                    f"(has {count}).")
        elif ship_type == "battleship":
            if count < 2 or count > 3:
                errors.append(
                    f"Squadron '{sid}': battleship squadrons need 2–3 ships "
                    f"(has {count}).")
        elif ship_type == "defense":
            errors.append(
                f"Squadron '{sid}': defence platforms cannot form squadrons.")
    return errors


def fleet_data(rows: List[dict], faction: str, list_key: str = "", detachment: str = "",
               name: str = "My Fleet", limit: int = 0, description: str = "") -> dict:
    """The saved fleet file's contents: each ship's stats with its options
    applied, at its cost in its fleet list (Bakka's premium, the Notable Xenos
    squadron's +30, Tactical Flexibility lost to a Chapter tactic), list stat
    changes (Bakka's +1 Turret), Ork reserves looted, campaign damage kept."""
    data = {
        "fleet_name":   name or "My Fleet",
        "faction":      faction or "",
        "description":  description,
        "points_limit": limit,
        "total_points": fleet_total(rows),
        "fleet_list":   list_key,
        "detachments":  [detachment] if detachment else [],
        "ships": [],
    }

    from .fleet_lists import notable_xenos_first, NOTABLE_XENOS_SQUADRON
    notable_first = notable_xenos_first(rows)
    # A Chapter tactic anywhere in the fleet ends Tactical Flexibility: each
    # Strike Cruiser Variant then costs its full price, on its own ship's
    # value too (victory points score that), not only in the fleet total
    tactic = any(u.startswith("Chapter tactic:") for r in rows
                 for u in r.get("upgrades", []))
    for row_i, row in enumerate(rows):
        entry = row["entry"]
        ship_dict = entry.to_ship_dict(
            name=row["custom_name"],
            player=1,
            upgrades=row["upgrades"],
            is_flagship=row["is_flagship"],
        )
        # Strip runtime-only keys; keep only fleet-storable fields
        storable = {k: v for k, v in ship_dict.items()
                    if k not in ("id", "player", "x", "y", "heading")}
        storable["squadron_id"] = row.get("squadron_id", "")
        # The ship's cost in its fleet list (Bakka's premium, for example)
        storable["points_value"] += row.get("base_cost", entry.points_cost) - entry.points_cost
        if row_i in notable_first:              # the Notable Xenos squadron's +30
            storable["points_value"] += NOTABLE_XENOS_SQUADRON
        from .fleet_lists import no_tactical_flexibility as _no_tf
        if tactic and not _no_tf(row.get("list") or ""):
            from .booklet_options import tactical_flexibility_refund
            storable["points_value"] += tactical_flexibility_refund(
                [row["upgrades"] + ["Chapter tactic:"]], [entry])
        if row.get("list"):
            storable["fleet_list"] = row["list"]
            from .fleet_lists import list_stat_changes, no_tactical_flexibility
            if no_tactical_flexibility(row["list"]):
                from .booklet_options import tactical_flexibility_refund
                storable["points_value"] += tactical_flexibility_refund(
                    [row["upgrades"] + ["Chapter tactic:"]], [entry])
            for stat, delta in list_stat_changes(row["list"], entry.ship_class).items():
                if stat == "special_rules":       # Renegade cruisers: -1 rolled Ld
                    storable["special_rules"] = list(storable["special_rules"]) + delta
                else:
                    storable[stat] = storable.get(stat, 0) + delta   # Bakka +1 Turret
        if (row.get("list") or "").startswith("reserve:") and \
                (_lists().get(list_key) or {}).get("looted_reserves"):
            from .orks import loot          # Ork fleets: reserves are looted vessels
            storable = loot(storable)
        # Write non-default damage state for campaign/scenario use
        dmg = row.get("damage", {})
        if "hits_remaining" in dmg:
            storable["hits_remaining"] = dmg["hits_remaining"]
        if dmg.get("ordnance_loaded_torps") is False:
            storable["ordnance_loaded_torps"] = False
        if dmg.get("ordnance_loaded_craft") is False:
            storable["ordnance_loaded_craft"] = False
        if dmg.get("critical_damage"):
            storable["critical_damage"] = dmg["critical_damage"]
        data["ships"].append(storable)
    return data


def list_catalog(list_key: str, detachment: str = "") -> List[tuple]:
    """The ships a fleet list offers, as (entry or None for a section heading,
    list key, cost, section name): its sections at the list's costs, then the
    detachment's and the reserve lists' ships (reserve key "reserve:<key>")."""
    from .ship_catalog import find_ship_class
    from .fleet_lists import reserve_allowed
    LISTS = _lists()
    out: List[tuple] = []
    main = LISTS[list_key]

    def add_list(fl, key, label_prefix=""):
        for sec in fl["sections"]:
            rows = [(find_ship_class(c), key, cost, sec["name"])
                    for c, cost in sec["ships"].items()]
            rows = [r for r in rows if r[0] is not None]
            if rows:
                out.append((None, "", 0, f"{label_prefix}{sec['name']}"))
                out.extend(rows)

    add_list(main, list_key)
    if detachment:
        det = LISTS[detachment]
        add_list(det, detachment, f"{det['name'].split(' (')[0]}: ")
    for rkey in main.get("reserves", []):
        if rkey not in LISTS or rkey == list_key:
            continue
        fl = LISTS[rkey]
        out.append((None, "", 0, f"Reserves: {fl['name'].split(' (')[0]}"))
        for sec in fl["sections"]:
            for c, cost in sec["ships"].items():
                e = find_ship_class(c)
                if e is not None and reserve_allowed(list_key, rkey, c):
                    out.append((e, f"reserve:{rkey}", cost, "Reserves"))
    return out
