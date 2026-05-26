"""BFG:XR — Squadron rules: coherency utilities."""
from typing import Dict, List, Tuple
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


def partition_by_coherency(ships: List[Ship]) -> Tuple[List[Ship], List[Ship]]:
    """Return (in_coherency, out_of_coherency) partitions.

    A ship is in coherency if it is within COHERENCY_RANGE of at least one
    other member.  Single-ship lists are always fully in coherency.
    """
    if len(ships) <= 1:
        return list(ships), []
    in_coh: List[Ship] = []
    out_coh: List[Ship] = []
    for s in ships:
        near = any(
            s2.id != s.id and s.distance_to(s2) <= COHERENCY_RANGE
            for s2 in ships
        )
        (in_coh if near else out_coh).append(s)
    return in_coh, out_coh


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
