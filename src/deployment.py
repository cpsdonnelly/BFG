"""BFG:XR Deployment Phase

Handles the pre-game ship placement phase that runs before Turn 1 begins.

Standard BFG deployment: Player 1 deploys within 30cm of their table edge
(y = 0 to 30cm), Player 2 within 30cm of the opposite edge
(y = table_height-30 to table_height).

Squadron coherency: all ships sharing a squadron_id must be placed within
15cm of each other and are deployed as a single placement action.

Deployment order (simplified): Player 1 deploys all ships, then Player 2.

Deployment order (alternating): Players alternate deploying one ship/squadron
at a time, starting with Player 2 (loser of roll-off) by convention.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple

from .models import Ship


COHERENCY_CM = 15.0          # squadron members must be within this distance
ZONE_DEPTH_CM = 30.0         # default deployment zone depth from table edge
SHIP_OVERLAP_CM = 2.5        # minimum centre-to-centre distance between ships


# ── Deployment zone ───────────────────────────────────────────────────────────

@dataclass
class DeploymentZone:
    player: int
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    label: str = ""

    def contains(self, x: float, y: float) -> bool:
        return self.x_min <= x <= self.x_max and self.y_min <= y <= self.y_max


def get_default_zones(table_width: float, table_height: float) -> List[DeploymentZone]:
    """Return standard two-zone layout (30cm from each long edge)."""
    return [
        DeploymentZone(
            player=1,
            x_min=0.0, y_min=0.0,
            x_max=table_width, y_max=ZONE_DEPTH_CM,
            label="Player 1 Deployment Zone",
        ),
        DeploymentZone(
            player=2,
            x_min=0.0, y_min=table_height - ZONE_DEPTH_CM,
            x_max=table_width, y_max=table_height,
            label="Player 2 Deployment Zone",
        ),
    ]


# ── Placement validation ──────────────────────────────────────────────────────

def validate_placement(
    ship: Ship,
    x: float,
    y: float,
    zone: DeploymentZone,
    placed_ships: List[Ship],
) -> Tuple[bool, str]:
    """
    Check whether placing *ship* at (x, y) is legal.

    Returns (True, "") on success or (False, reason) on failure.
    Squadron coherency is NOT checked here — use validate_squadron_placement
    which validates the whole group at once.
    """
    if not zone.contains(x, y):
        return False, f"Position ({x:.1f}, {y:.1f}) is outside {zone.label}."

    for other in placed_ships:
        if other.id == ship.id:
            continue
        dist = math.hypot(other.x - x, other.y - y)
        if dist < SHIP_OVERLAP_CM:
            return False, f"Too close to {other.name} ({dist:.1f}cm — min {SHIP_OVERLAP_CM}cm)."

    return True, ""


def validate_squadron_placement(
    ships: List[Ship],
    positions: List[Tuple[float, float]],
    zone: DeploymentZone,
    placed_ships: List[Ship],
) -> Tuple[bool, List[str]]:
    """
    Validate placing a squadron (multiple ships) at their respective positions.

    *positions* is parallel to *ships*: positions[i] = (x, y) for ships[i].
    Returns (True, []) on success or (False, [errors]).
    """
    errors: List[str] = []

    # Each ship must be in zone and not overlap already-placed ships
    for ship, (x, y) in zip(ships, positions):
        ok, reason = validate_placement(ship, x, y, zone, placed_ships)
        if not ok:
            errors.append(f"{ship.name}: {reason}")

    # All members must be within COHERENCY_CM of each other (pairwise)
    for i, (s1, (x1, y1)) in enumerate(zip(ships, positions)):
        for s2, (x2, y2) in zip(ships[i + 1:], positions[i + 1:]):
            dist = math.hypot(x2 - x1, y2 - y1)
            if dist > COHERENCY_CM:
                errors.append(
                    f"{s1.name} and {s2.name} are {dist:.1f}cm apart — "
                    f"max coherency is {COHERENCY_CM}cm."
                )

    return (len(errors) == 0), errors


# ── Squadron grouping ─────────────────────────────────────────────────────────

def group_ships_for_deployment(ships: List[Ship]) -> List[List[Ship]]:
    """
    Return a list of deployment groups.

    Each group is a list of Ship objects.  A solo ship is a group of one.
    Ships sharing a squadron_id are a single group (deployed all at once).
    Groups are sorted: escorts before capital ships, then by name.
    """
    squads: Dict[str, List[Ship]] = {}
    solos: List[Ship] = []

    for ship in ships:
        if ship.squadron_id:
            squads.setdefault(ship.squadron_id, []).append(ship)
        else:
            solos.append(ship)

    groups: List[List[Ship]] = [[s] for s in solos]
    groups.extend(members for members in squads.values())
    groups.sort(key=lambda g: (g[0].ship_type != "escort", g[0].name))
    return groups


# ── Deployment state ──────────────────────────────────────────────────────────

class DeploymentState:
    """
    Tracks the progress of the deployment phase.

    Attributes
    ----------
    mode : "sequential" | "alternating"
        sequential — P1 deploys all, then P2.
        alternating — players alternate one group at a time (P2 goes first).
    """

    def __init__(
        self,
        p1_ships: List[Ship],
        p2_ships: List[Ship],
        zones: List[DeploymentZone],
        mode: str = "sequential",
    ):
        self.zones: Dict[int, DeploymentZone] = {z.player: z for z in zones}
        self.mode = mode

        self.groups: Dict[int, List[List[Ship]]] = {
            1: group_ships_for_deployment(p1_ships),
            2: group_ships_for_deployment(p2_ships),
        }
        # Indices into self.groups[player]
        self.next_idx: Dict[int, int] = {1: 0, 2: 0}
        self.placed_ships: List[Ship] = []

        if mode == "alternating":
            self.active_player = 2  # P2 goes first by convention
        else:
            self.active_player = 1

    # ── Query helpers ─────────────────────────────────────────────────────────

    def current_group(self) -> Optional[List[Ship]]:
        """The group that must be placed next by the active player."""
        p = self.active_player
        idx = self.next_idx[p]
        groups = self.groups[p]
        if idx >= len(groups):
            return None
        return groups[idx]

    def is_complete(self) -> bool:
        return (self.next_idx[1] >= len(self.groups[1]) and
                self.next_idx[2] >= len(self.groups[2]))

    def groups_remaining(self, player: int) -> int:
        return len(self.groups[player]) - self.next_idx[player]

    # ── Placement ─────────────────────────────────────────────────────────────

    def place_group(
        self,
        positions: List[Tuple[float, float]],
        headings: List[float],
    ) -> Tuple[bool, List[str]]:
        """
        Attempt to place the current group at the given positions/headings.

        positions and headings are parallel to current_group().
        Returns (True, []) on success; (False, errors) on failure.
        """
        group = self.current_group()
        if group is None:
            return False, ["No group to place."]

        zone = self.zones[self.active_player]
        ok, errors = validate_squadron_placement(
            group, positions, zone, self.placed_ships)
        if not ok:
            return False, errors

        for ship, (x, y), heading in zip(group, positions, headings):
            ship.x = x
            ship.y = y
            ship.heading = heading % 360.0
            self.placed_ships.append(ship)

        self.next_idx[self.active_player] += 1
        self._advance_player()
        return True, []

    def _advance_player(self):
        """Move to the next player / deployment turn."""
        if self.mode == "sequential":
            if self.next_idx[1] >= len(self.groups[1]):
                self.active_player = 2
            else:
                self.active_player = 1
        else:
            # alternating
            other = 2 if self.active_player == 1 else 1
            if self.groups_remaining(other) > 0:
                self.active_player = other
            # else stay with current player if they still have ships
