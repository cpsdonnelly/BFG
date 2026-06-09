"""BFG:XR Campaign Mode — persistent fleet damage and VP across battles."""
import json
import os
import time
from dataclasses import dataclass, asdict

from .game_state import GameState
from .fleet_loader import export_fleet_with_damage


@dataclass
class CampaignState:
    campaign_name: str = "campaign"
    battles_played: int = 0
    player1_name: str = "Player 1"
    player2_name: str = "Player 2"
    player1_faction: str = "imperial_navy"
    player2_faction: str = "tau_kororvesh"
    player1_total_vp: int = 0
    player2_total_vp: int = 0
    player1_fleet_file: str = ""   # path to persisted fleet JSON
    player2_fleet_file: str = ""
    repair_budget_p1: int = 0      # points available for repairs before next battle
    repair_budget_p2: int = 0
    points_limit: int = 800

    # ── Repair rules ─────────────────────────────────────────────────────────
    CRIT_REPAIR_COST: int = 25     # points per critical repaired
    HULL_REPAIR_COST: int = 10     # points per hull point restored (up to cripple threshold)


def save_campaign(cs: CampaignState, directory: str) -> None:
    os.makedirs(directory, exist_ok=True)
    data = asdict(cs)
    data["timestamp"] = time.time()
    with open(os.path.join(directory, "campaign.json"), "w") as f:
        json.dump(data, f, indent=2)


def load_campaign(directory: str) -> CampaignState:
    with open(os.path.join(directory, "campaign.json")) as f:
        data = json.load(f)
    cs = CampaignState()
    for k, v in data.items():
        if k == "timestamp":
            continue
        if hasattr(cs, k):
            setattr(cs, k, v)
    return cs


def post_battle_update(cs: CampaignState, gs: GameState,
                       battle_vp_p1: int, battle_vp_p2: int,
                       campaign_dir: str) -> CampaignState:
    """
    Called after a battle ends.  Updates VP totals, exports surviving fleets,
    and calculates repair budgets.  Returns the updated CampaignState.
    """
    cs.battles_played += 1
    cs.player1_total_vp += battle_vp_p1
    cs.player2_total_vp += battle_vp_p2

    # Repair budget = 20% of opponent's destroyed points value
    def _destroyed_pts(player: int) -> int:
        total = 0
        for s_dict in gs.ships:
            if s_dict["player"] == player and s_dict.get("is_destroyed"):
                total += s_dict.get("points_value", 0)
        return total

    cs.repair_budget_p1 = int(_destroyed_pts(2) * 0.20)
    cs.repair_budget_p2 = int(_destroyed_pts(1) * 0.20)

    # Export surviving fleets
    battle_tag = f"battle_{cs.battles_played:02d}"
    p1_path = os.path.join(campaign_dir, f"p1_fleet_{battle_tag}.json")
    p2_path = os.path.join(campaign_dir, f"p2_fleet_{battle_tag}.json")
    p1_ships = [s for s_dict in gs.ships
                if s_dict["player"] == 1
                for s in [__import__("src.models", fromlist=["Ship"]).Ship.from_dict(s_dict)]
                if not s.is_destroyed]
    p2_ships = [s for s_dict in gs.ships
                if s_dict["player"] == 2
                for s in [__import__("src.models", fromlist=["Ship"]).Ship.from_dict(s_dict)]
                if not s.is_destroyed]
    export_fleet_with_damage(p1_ships, 1, p1_path)
    export_fleet_with_damage(p2_ships, 2, p2_path)
    cs.player1_fleet_file = p1_path
    cs.player2_fleet_file = p2_path

    save_campaign(cs, campaign_dir)
    return cs


def apply_repairs(fleet_path: str, repair_orders: list, budget: int) -> int:
    """
    Apply repair orders to a fleet file in place.  Returns remaining budget.

    repair_orders: list of dicts with keys:
      {"ship_id": str, "action": "crit"|"hull", "crit_index": int (for crit)}

    Hull repair: restores 1 HP per application (up to cripple threshold = hits_max // 2).
    Crit repair: removes the critical at the given index.
    """
    from .campaign import CampaignState
    crit_cost = CampaignState.CRIT_REPAIR_COST
    hull_cost = CampaignState.HULL_REPAIR_COST

    with open(fleet_path) as f:
        fleet_data = json.load(f)

    ship_map = {s["id"]: s for s in fleet_data.get("ships", [])}
    remaining = budget

    for order in repair_orders:
        sid = order.get("ship_id")
        if sid not in ship_map:
            continue
        ship = ship_map[sid]
        action = order.get("action")

        if action == "crit" and remaining >= crit_cost:
            crits = ship.get("critical_damage", [])
            idx = order.get("crit_index", 0)
            if 0 <= idx < len(crits):
                crits.pop(idx)
                ship["critical_damage"] = crits
                remaining -= crit_cost

        elif action == "hull" and remaining >= hull_cost:
            max_restore = ship.get("hits_max", 8) // 2  # cripple threshold
            if ship.get("hits_remaining", 0) < max_restore:
                ship["hits_remaining"] = min(
                    max_restore, ship.get("hits_remaining", 0) + 1)
                remaining -= hull_cost

    with open(fleet_path, "w") as f:
        json.dump(fleet_data, f, indent=2)

    return remaining
