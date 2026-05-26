"""BFG:XR — Squadron rules: coherency utilities."""
from typing import Dict, List
from .models import Ship
from .game_state import GameState

COHERENCY_RANGE = 15.0  # cm


def get_squadrons(gs: GameState, player: int) -> Dict[str, List[Ship]]:
    """Return {squadron_id: [Ship …]} for active (non-destroyed, non-disengaged) ships."""
    result: Dict[str, List[Ship]] = {}
    for s_dict in gs.ships:
        ship = Ship.from_dict(s_dict)
        if ship.player != player or ship.is_destroyed or ship.is_disengaged:
            continue
        if not ship.squadron_id:
            continue
        result.setdefault(ship.squadron_id, []).append(ship)
    return result


def check_squadron_coherency(gs: GameState, player: int) -> List[str]:
    """Return one warning string per ship that is >15 cm from every other member."""
    violations: List[str] = []
    for sid, members in get_squadrons(gs, player).items():
        if len(members) < 2:
            continue
        for ship in members:
            in_range = any(
                ship.distance_to(other) <= COHERENCY_RANGE
                for other in members if other.id != ship.id
            )
            if not in_range:
                names = ", ".join(s.name for s in members)
                violations.append(
                    f"{ship.name} is >15 cm from all other members [{names}]"
                )
    return violations
