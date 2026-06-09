"""BFG:XR Victory Points - End-of-game scoring"""
from typing import List, Dict
from .models import Ship
from .game_state import GameState


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

    for s in ships:
        opponent = 2 if s.player == 1 else 1
        pts = s.points_value
        if pts <= 0:
            continue

        # Skip escorts that are part of a squadron (handled below)
        if s.squadron_id and s.ship_type == "escort":
            if s.squadron_id not in scored_squadron_ids:
                scored_squadron_ids.add(s.squadron_id)
                _score_squadron(squadrons[s.squadron_id], opponent, result)
            continue

        # Capital ships and solo escorts
        if s.status == "destroyed" or s.hits_remaining <= 0:
            # Destroyed: 100% points to opponent
            result[opponent]["destroyed"] += pts
            result[opponent]["details"].append(
                f"{s.name} destroyed: +{pts} VP")

        elif s.status in ("drifting_hulk", "burning_hulk"):
            # Hulk: treated as destroyed for VP
            result[opponent]["destroyed"] += pts
            result[opponent]["details"].append(
                f"{s.name} hulked: +{pts} VP")

        elif s.is_disengaged and not s.is_crippled:
            # Non-crippled disengaged: 10% points
            vp = max(1, pts // 10)
            result[opponent]["disengaged"] += vp
            result[opponent]["details"].append(
                f"{s.name} disengaged (scattered): +{vp} VP")

        elif s.is_disengaged and s.is_crippled:
            # Crippled and disengaged: 25% (crippled value)
            vp = max(1, pts // 4)
            result[opponent]["crippled"] += vp
            result[opponent]["details"].append(
                f"{s.name} disengaged crippled: +{vp} VP")

        elif s.is_crippled:
            # Crippled on table: 25% points
            vp = max(1, pts // 4)
            result[opponent]["crippled"] += vp
            result[opponent]["details"].append(
                f"{s.name} crippled: +{vp} VP")

    # Holding the field
    p1_holds = _holds_field(1, ships)
    p2_holds = _holds_field(2, ships)

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

    # Totals
    for p in [1, 2]:
        result[p]["total"] = (result[p]["destroyed"] +
                               result[p]["crippled"] +
                               result[p]["disengaged"] +
                               result[p]["holding_field"])

    return result


def _score_squadron(squadron: List[Ship], opponent: int, result: Dict):
    """Score an escort squadron as a unit."""
    total_pts = sum(s.points_value for s in squadron)
    total_ships = len(squadron)
    destroyed = sum(1 for s in squadron
                    if s.status in ("destroyed",) or s.hits_remaining <= 0)
    disengaged = sum(1 for s in squadron if s.is_disengaged)

    if destroyed == total_ships:
        # Entire squadron destroyed
        result[opponent]["destroyed"] += total_pts
        result[opponent]["details"].append(
            f"Squadron destroyed ({squadron[0].ship_class}): +{total_pts} VP")

    elif destroyed + disengaged == total_ships:
        # All destroyed or disengaged
        destroyed_pts = sum(s.points_value for s in squadron
                           if s.status == "destroyed" or s.hits_remaining <= 0)
        result[opponent]["destroyed"] += destroyed_pts
        disengaged_pts = sum(max(1, s.points_value // 10)
                            for s in squadron if s.is_disengaged)
        result[opponent]["disengaged"] += disengaged_pts
        result[opponent]["details"].append(
            f"Squadron scattered ({squadron[0].ship_class}): "
            f"+{destroyed_pts} destroyed, +{disengaged_pts} disengaged")

    else:
        # Partially destroyed: check if crippled (half or more destroyed)
        cripple_threshold = (total_ships + 1) // 2  # round up
        if destroyed >= cripple_threshold:
            vp = max(1, total_pts // 4)
            result[opponent]["crippled"] += vp
            # Also count fully destroyed ships
            destroyed_pts = sum(s.points_value for s in squadron
                               if s.status == "destroyed" or s.hits_remaining <= 0)
            result[opponent]["destroyed"] += destroyed_pts
            result[opponent]["details"].append(
                f"Squadron crippled ({squadron[0].ship_class}): "
                f"+{destroyed_pts} destroyed, +{vp} crippled")


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
        lines.append(f"")
        lines.append(f"--- {pname} ---")
        lines.append(f"  Enemies Destroyed:  {data['destroyed']} VP")
        lines.append(f"  Enemies Crippled:   {data['crippled']} VP")
        lines.append(f"  Enemies Scattered:  {data['disengaged']} VP")
        lines.append(f"  Holding the Field:  {data['holding_field']} VP")
        lines.append(f"  TOTAL:              {data['total']} VP")
        if data["details"]:
            lines.append(f"  Breakdown:")
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
