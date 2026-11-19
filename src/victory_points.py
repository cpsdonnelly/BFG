"""BFG:XR Victory Points - End-of-game scoring"""
from typing import List, Dict
from .models import Ship
from .game_state import GameState


_COMMANDER_GROUPS = ("group:fleet_commander", "group:commander_rerolls", "group:boss_title",
                     "group:scylla_rerolls")


def commander_points(ship: Ship) -> int:
    """The commander's VPs on a ship: the cost of its commander, the
    commander's re-rolls and upgrades (s.5, update 34): the options bought in
    the commander groups or giving re-rolls."""
    from .ship_catalog import find_ship_class
    entry = find_ship_class(ship.ship_class)
    if entry is None:
        return 0
    total = 0
    for u in entry.upgrades_available:
        if u.name not in (ship.upgrades or []):
            continue
        eff = u.effect or {}
        rules = eff.get("add_special_rules", [])
        if (any(r in _COMMANDER_GROUPS for r in u.restrictions) or eff.get("rerolls")
                or (eff.get("set") or {}).get("own_rerolls")
                or "fleet_commander" in rules or "secondary_commander" in rules):
            total += u.points_cost
    return total


def calculate_victory_points(gs: GameState) -> Dict:
    """
    Calculate victory points for both players at end of game.
    Returns dict with detailed breakdown per player.
    """
    result = {
        1: {"destroyed": 0, "crippled": 0, "disengaged": 0,
            "holding_field": 0, "total": 0, "details": []},
        2: {"destroyed": 0, "crippled": 0, "disengaged": 0,
            "holding_field": 0, "total": 0, "details": []},
    }

    ships = gs.get_ships()

    # Group ships by player and squadron for escort VP calculation
    player_ships = {1: [], 2: []}
    for s in ships:
        player_ships[s.player].append(s)

    # Process escort squadrons
    squadrons = {}  # squadron_id -> list of ships
    for s in ships:
        if s.squadron_id:
            squadrons.setdefault(s.squadron_id, []).append(s)

    # Score each ship/squadron
    scored_squadron_ids = set()

    from .scenarios import scores_normally
    for s in ships:
        opponent = 2 if s.player == 1 else 1
        pts = s.points_value
        if pts <= 0 or not scores_normally(gs, s) or s.status == "reserve":
            continue            # (reinforcements that never arrived score nothing, reading)            # (convoy ships in Convoy are scored by vp_bonus)
        from .models import commander_dead
        if commander_dead(s) and not (s.status in ("destroyed", "drifting_hulk", "burning_hulk")
                                      or s.hits_remaining <= 0):
            # Bridge Smashed / an alien table's result 9 (s.5, updates 34 and 62):
            # "The opponent scores the commander's VPs"; the ship itself scores
            # on the rest of its points (a destroyed ship already counts them all)
            cmd = min(pts, commander_points(s))
            if cmd:
                result[opponent]["destroyed"] += cmd
                result[opponent]["details"].append(
                    f"{s.name}: commander killed: +{cmd} VP")
                pts -= cmd

        # Skip escorts that are part of a squadron (handled below)
        if s.squadron_id and s.ship_type == "escort":
            if s.squadron_id not in scored_squadron_ids:
                scored_squadron_ids.add(s.squadron_id)
                _score_squadron(squadrons[s.squadron_id], opponent, result,
                                getattr(gs, "rule_remastered_escort_vp", False))
            continue

        # Venerable Battle Barges (Space Marines): 50% of cost if crippled,
        # 125% if destroyed, instead of the normal VP
        venerable = "venerable" in s.special_rules
        destroyed_vp = pts * 5 // 4 if venerable else pts
        crippled_vp = pts // 2 if venerable else max(1, pts // 4)
        # Demiurg VP: a commerce vessel destroyed is worth its higher value
        # (Stronghold 400, Bastion 300, Citadel 200) only if its fleet is all
        # Demiurg or the opposing fleet has any Ork vessels
        higher = next((int(r.split(":")[1]) for r in s.special_rules
                       if r.startswith("demiurg_vp:")), None)
        if higher is not None:
            own = [o for o in ships if o.player == s.player]
            if (all("demiurg_commerce" in o.special_rules for o in own)
                    or any(o.player == opponent and o.faction == "orks" for o in ships)):
                from .ship_catalog import find_ship_class
                entry = find_ship_class(s.ship_class)
                base = entry.points_cost if entry else pts
                destroyed_vp = pts + max(0, higher - base)
        # Awakened Necron capital ships (and their hulks) are worth double VP
        if "necron_awake" in s.special_rules:
            destroyed_vp, crippled_vp = destroyed_vp * 2, crippled_vp * 2

        # Capital ships and solo escorts
        if s.status == "destroyed" or s.hits_remaining <= 0:
            # Destroyed: 100% points to opponent
            pts = destroyed_vp
            result[opponent]["destroyed"] += pts
            result[opponent]["details"].append(
                f"{s.name} destroyed: +{pts} VP")

        elif s.status in ("drifting_hulk", "burning_hulk"):
            # Hulk: treated as destroyed for VP
            pts = destroyed_vp
            result[opponent]["destroyed"] += pts
            result[opponent]["details"].append(
                f"{s.name} hulked: +{pts} VP")

        elif s.is_disengaged and not s.damage_crippled:
            # Non-crippled disengaged: 10% points
            vp = max(1, pts // 10)
            result[opponent]["disengaged"] += vp
            result[opponent]["details"].append(
                f"{s.name} disengaged (scattered): +{vp} VP")

        elif s.is_disengaged and s.damage_crippled:
            # Crippled and disengaged: 25% (crippled value)
            vp = crippled_vp
            result[opponent]["crippled"] += vp
            result[opponent]["details"].append(
                f"{s.name} disengaged crippled: +{vp} VP")

        elif s.damage_crippled:
            # Crippled on table: 25% points
            vp = crippled_vp
            result[opponent]["crippled"] += vp
            result[opponent]["details"].append(
                f"{s.name} crippled: +{vp} VP")

    # Holding the field
    # (The Defence of Pelucidar: neither fleet holds the field)
    no_field = getattr(gs, "scenario_mode", "") == "pelucidar"
    p1_holds = not no_field and _holds_field(1, ships)
    p2_holds = not no_field and _holds_field(2, ships)

    if p1_holds:
        hulk_vp = _hulk_points(ships)
        result[1]["holding_field"] = hulk_vp
        result[1]["details"].append(
            f"Holding the field: +{hulk_vp} VP from hulks")

    if p2_holds:
        hulk_vp = _hulk_points(ships)
        result[2]["holding_field"] = hulk_vp
        result[2]["details"].append(
            f"Holding the field: +{hulk_vp} VP from hulks")

    # Scenario victory points (src/scenarios.py, e.g. Rescue's flagship)
    from .scenarios import vp_bonus
    vp_bonus(gs, result)

    _insatiable_greed(gs, ships, result)
    # Dark Eldar slave-taking (Xenos p.4), counted in the scenario VP
    for p in (1, 2):
        sv = int((getattr(gs, "slave_vp", None) or {}).get(str(p), 0))
        if sv:
            result[p]["scenario"] = result[p].get("scenario", 0) + sv
            result[p]["details"].append(f"Slave-taking: +{sv} VP")

    # Totals
    for p in [1, 2]:
        result[p]["total"] = (result[p]["destroyed"] +
                               result[p]["crippled"] +
                               result[p]["disengaged"] +
                               result[p]["holding_field"] +
                               result[p].get("scenario", 0))

    return result


def _insatiable_greed(gs: GameState, ships: List[Ship], result: Dict) -> None:
    """Dark Eldar Insatiable Greed (Xenos p.4): non-crippled Dark Eldar ships
    that disengaged count as destroyed unless their fleet has scored at least
    25% of its own value in VP (reading: the VP scored before this rule; ships
    whose disengaging a scenario scores itself are left alone; an escort
    squadron scattered whole counts destroyed whole)."""
    from .scenarios import scores_normally
    for p in (1, 2):
        own = [s for s in ships if s.player == p and "dark_eldar" in s.special_rules]
        if not own:
            continue
        opp = 3 - p
        fleet_value = sum(s.points_value for s in ships if s.player == p)
        scored = sum(result[p][k] for k in ("destroyed", "crippled", "disengaged",
                                            "holding_field")) + result[p].get("scenario", 0)
        if scored * 4 >= fleet_value:
            continue
        squads = {}
        for s in own:
            if not scores_normally(gs, s) or s.points_value <= 0:
                continue
            if s.squadron_id and s.ship_type == "escort":
                squads.setdefault(s.squadron_id, []).append(s)
            elif s.is_disengaged and not s.damage_crippled and s.hits_remaining > 0:
                was = max(1, s.points_value // 10)
                result[opp]["disengaged"] -= was
                result[opp]["destroyed"] += s.points_value
                result[opp]["details"].append(
                    f"{s.name} disengaged (Insatiable Greed: counts destroyed): "
                    f"+{s.points_value - was} VP")
        for sq in squads.values():
            # every member of the squadron, not only Dark Eldar ones
            members = [s for s in ships if s.squadron_id == sq[0].squadron_id]
            total = sum(s.points_value for s in members)
            dead = sum(1 for s in members if s.status == "destroyed" or s.hits_remaining <= 0)
            gone = sum(1 for s in members if s.is_disengaged)
            if gone and dead + gone == len(members) and dead < (len(members) + 1) // 2:
                was = max(1, total // 10)
                result[opp]["disengaged"] -= was
                result[opp]["destroyed"] += total
                result[opp]["details"].append(
                    f"Squadron {members[0].ship_class} disengaged (Insatiable Greed: counts "
                    f"destroyed): +{total - was} VP")


def _score_squadron(squadron: List[Ship], opponent: int, result: Dict,
                    remastered: bool = False):
    """Score an escort squadron once, as a single unit.

    A squadron earns exactly one result, never a mix: destroyed (every ship)
    = full points; crippled (at least half its ships destroyed, rounding up)
    = 25%; scattered (not crippled, every surviving ship disengaged) = 10%.

    Remastered option (p.121, `GameState.rule_remastered_escort_vp`): only a
    squadron destroyed entirely scores its value; no 25% for a crippled
    squadron left on the table; disengaged, 25% of the whole squadron's value
    if crippled before leaving, else 10% ("total points value" read as the full
    original squadron: unconfirmed).
    """
    total_pts = sum(s.points_value for s in squadron)
    total_ships = len(squadron)
    destroyed = sum(1 for s in squadron
                    if s.status == "destroyed" or s.hits_remaining <= 0)
    disengaged = sum(1 for s in squadron if s.is_disengaged)
    name = squadron[0].ship_class

    if destroyed == total_ships:
        result[opponent]["destroyed"] += total_pts
        result[opponent]["details"].append(
            f"Squadron destroyed ({name}): +{total_pts} VP")
        return
    if remastered:
        if not (disengaged and destroyed + disengaged == total_ships):
            return                       # on the table: nothing (Remastered)
        crippled = destroyed >= (total_ships + 1) // 2
        vp = max(1, total_pts // 4) if crippled else max(1, total_pts // 10)
        result[opponent]["disengaged"] += vp
        result[opponent]["details"].append(
            f"Squadron disengaged{' crippled' if crippled else ''} ({name}): +{vp} VP")
        return

    if destroyed >= (total_ships + 1) // 2:
        vp = max(1, total_pts // 4)
        result[opponent]["crippled"] += vp
        result[opponent]["details"].append(
            f"Squadron crippled ({name}, {destroyed}/{total_ships} destroyed): +{vp} VP")

    elif disengaged and destroyed + disengaged == total_ships:
        vp = max(1, total_pts // 10)
        result[opponent]["disengaged"] += vp
        result[opponent]["details"].append(
            f"Squadron scattered ({name}): +{vp} VP")


def _holds_field(player: int, ships: List[Ship]) -> bool:
    """
    Check if a player holds the field.
    Requires: no enemy ships remaining (all destroyed or disengaged)
    AND at least one operational friendly ship on table.
    """
    has_operational = False
    enemy_on_table = False

    for s in ships:
        if s.player == player:
            if (not s.is_destroyed and not s.is_disengaged
                    and s.status == "active" and s.hits_remaining > 0):
                has_operational = True
        else:
            if (not s.is_destroyed and not s.is_disengaged
                    and s.status not in ("destroyed", "disengaged")):
                enemy_on_table = True

    return has_operational and not enemy_on_table


def _hulk_points(ships: List[Ship]) -> int:
    """Calculate 50% of points value of all hulks on the table."""
    total = 0
    for s in ships:
        if s.status in ("drifting_hulk", "burning_hulk"):
            total += max(1, s.points_value // 2)
    return total


def format_vp_summary(vp_result: Dict, gs: GameState) -> str:
    """Format victory points into a readable summary string."""
    lines = ["", "=" * 50, "VICTORY POINTS SUMMARY", "=" * 50]

    for p in [1, 2]:
        pname = gs.player1_name if p == 1 else gs.player2_name
        data = vp_result[p]
        lines.append("")
        lines.append(f"--- {pname} ---")
        lines.append(f"  Enemies Destroyed:  {data['destroyed']} VP")
        lines.append(f"  Enemies Crippled:   {data['crippled']} VP")
        lines.append(f"  Enemies Scattered:  {data['disengaged']} VP")
        lines.append(f"  Holding the Field:  {data['holding_field']} VP")
        lines.append(f"  TOTAL:              {data['total']} VP")
        if data["details"]:
            lines.append("  Breakdown:")
            for d in data["details"]:
                lines.append(f"    {d}")

    # Winner
    p1_total = vp_result[1]["total"]
    p2_total = vp_result[2]["total"]
    lines.append("")
    if p1_total > p2_total:
        lines.append(f"WINNER: {gs.player1_name} ({p1_total} vs {p2_total})")
    elif p2_total > p1_total:
        lines.append(f"WINNER: {gs.player2_name} ({p2_total} vs {p1_total})")
    else:
        lines.append(f"DRAW ({p1_total} vs {p2_total})")
    lines.append("=" * 50)

    return "\n".join(lines)
