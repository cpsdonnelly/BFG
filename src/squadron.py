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


def get_coherency_components(
    ships: List[Ship],
) -> Tuple[List[List[Ship]], List[Ship]]:
    """Return (coherent_groups, isolated_ships).

    coherent_groups: connected components of size >= 2, sorted largest-first.
                     Ties in size are broken by highest max-leadership.
    isolated_ships:  ships that are >COHERENCY_RANGE from every other member.
    """
    if len(ships) <= 1:
        return ([list(ships)] if ships else []), []

    n = len(ships)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for i in range(n):
        for j in range(i + 1, n):
            if ships[i].distance_to(ships[j]) <= COHERENCY_RANGE:
                union(i, j)

    comp: Dict[int, List[int]] = {}
    for i in range(n):
        comp.setdefault(find(i), []).append(i)

    groups: List[List[Ship]] = []
    isolated: List[Ship] = []
    for indices in comp.values():
        members = [ships[i] for i in indices]
        if len(members) >= 2:
            groups.append(members)
        else:
            isolated.extend(members)

    groups.sort(key=lambda g: (len(g), max(s.leadership for s in g)), reverse=True)
    return groups, isolated


def partition_by_coherency(ships: List[Ship]) -> Tuple[List[Ship], List[Ship]]:
    """Return (in_coherency, out_of_coherency) using chain-coherency connected components.

    The primary (in_coherency) group is the largest connected component.
    All other ships go to out_of_coherency.
    """
    if len(ships) <= 1:
        return list(ships), []

    groups, isolated = get_coherency_components(ships)
    if not groups:
        return [], list(ships)   # all isolated

    primary = groups[0]          # largest (already sorted)
    primary_ids = {s.id for s in primary}
    in_coh  = [s for s in ships if     s.id in primary_ids]
    out_coh = [s for s in ships if s.id not in primary_ids]
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
