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
from dataclasses import dataclass, field
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
    # Further rectangles of the same zone (L-shaped scenario zones, e.g.
    # Domination 3); `contains` accepts any of them
    extra: list = field(default_factory=list)

    def contains(self, x: float, y: float) -> bool:
        if self.x_min <= x <= self.x_max and self.y_min <= y <= self.y_max:
            return True
        return any(r.contains(x, y) for r in self.extra)

    def rects(self) -> list:
        return [self] + list(self.extra)


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
        extra_check=None,
    ):
        """extra_check(group, positions, headings, placed ships) -> [errors]:
        a scenario's deployment rules beyond the zone (scenarios.placement_errors)."""
        self.extra_check = extra_check
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
        if self.extra_check is not None:
            errors = self.extra_check(group, positions, headings, self.placed_ships)
            if errors:
                return False, errors

        for ship, (x, y), heading in zip(group, positions, headings):
            ship.x = x
            ship.y = y
            ship.heading = heading % 360.0
            self.placed_ships.append(ship)

        self.next_idx[self.active_player] += 1
        self._advance_player()
        return True, []

    def undo_group(self) -> Optional[List[Ship]]:
        """Take back the last group placed (by either player in sequential
        deployment, the one just placed in alternating): it returns to the
        list to place again. Returns the group, or None."""
        for p in ((self.active_player, 3 - self.active_player)
                  if self.mode == "sequential" else (3 - self.active_player, self.active_player)):
            idx = self.next_idx[p] - 1
            if idx < 0:
                continue
            group = self.groups[p][idx]
            if not all(s in self.placed_ships for s in group):
                continue
            ids = {s.id for s in group}
            self.placed_ships = [s for s in self.placed_ships if s.id not in ids]
            self.next_idx[p] = idx
            self.active_player = p
            return group
        return None

    def select_group(self, idx: int) -> bool:
        """Place the active player's groups in any order (owner): the chosen
        unplaced group becomes the one to place next (swapped into the slot
        `current_group` reads). False if it is placed already or out of range."""
        p = self.active_player
        nxt = self.next_idx[p]
        if not nxt <= idx < len(self.groups[p]):
            return False
        g = self.groups[p]
        g[nxt], g[idx] = g[idx], g[nxt]
        return True

    def unplace_group(self, player: int, idx: int) -> Optional[List[Ship]]:
        """Take back any group already placed (not only the last one): it
        goes back to the list to place again, and that player places next.
        Returns the group, or None."""
        last = self.next_idx[player] - 1
        if not 0 <= idx <= last:
            return None
        g = self.groups[player]
        g[idx], g[last] = g[last], g[idx]
        group = g[last]
        ids = {s.id for s in group}
        self.placed_ships = [s for s in self.placed_ships if s.id not in ids]
        self.next_idx[player] = last
        self.active_player = player
        return group

    def rotate_placed(self, ship_id: str, degrees: float) -> Optional[Ship]:
        """Turn a ship already placed (and the rest of its squadron) by
        degrees, if the scenario's checks still pass. Returns the ship."""
        ship = next((s for s in self.placed_ships if s.id == ship_id), None)
        if ship is None:
            return None
        group = [s for s in self.placed_ships if s is ship or (
            ship.squadron_id and s.squadron_id == ship.squadron_id and s.player == ship.player)]
        new = [(s.heading + degrees) % 360.0 for s in group]
        if self.extra_check is not None:
            others = [s for s in self.placed_ships if s not in group]
            if self.extra_check(group, [(s.x, s.y) for s in group], new, others):
                return None
        for s, h in zip(group, new):
            s.heading = h
        return ship

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


# ── Engine-side deployment (To do 32: the window's auto-place, also for games
# with no window, e.g. tools/headless_runner.py with builder-saved fleets) ──

def deployment_state(gs, mode: str = "sequential") -> "DeploymentState":
    """The deployment of `gs`'s ships: the scenario's fixed placements made
    (Rescue's flagship), reserves left out, the scenario's zones and rules."""
    from .scenarios import deployment_zones, fixed_placements, placement_errors
    fixed = fixed_placements(gs)
    for sd in gs.ships:
        if sd["id"] in fixed:
            sd["x"], sd["y"], sd["heading"] = fixed[sd["id"]]
    ships = {p: [Ship.from_dict(s) for s in gs.ships if s["player"] == p
                 and s["id"] not in fixed and s.get("status") != "reserve"] for p in (1, 2)}
    zones = deployment_zones(gs) or get_default_zones(gs.table_width, gs.table_height)
    state = DeploymentState(
        ships[1], ships[2], zones, mode=mode,
        extra_check=lambda g, pos, hd, placed: placement_errors(gs, g, pos, hd, placed))
    state.placed_ships.extend(Ship.from_dict(s) for s in gs.ships if s["id"] in fixed)
    return state


def grid_positions(group, zone: DeploymentZone, placed) -> List[Tuple[float, float]]:
    """Positions for `group` in `zone`: a compact block (two rows, 6cm apart,
    so a squadron of up to six keeps well within 15cm coherency), at the spot
    nearest the zone's centre that is clear of ships already placed (8cm,
    judgement) and inside the zone."""
    import math
    n = len(group)
    cols = n if n <= 3 else (n + 1) // 2
    rows = 1 if n <= 3 else 2
    step = 6.0
    offsets = [((i % cols - (cols - 1) / 2.0) * step, (i // cols - (rows - 1) / 2.0) * step)
               for i in range(n)]
    cx, cy = (zone.x_min + zone.x_max) / 2.0, (zone.y_min + zone.y_max) / 2.0
    margin = 2.5
    best = None
    for ring in range(0, 40):
        for dx_i in range(-ring, ring + 1):
            for dy_i in range(-ring, ring + 1):
                if max(abs(dx_i), abs(dy_i)) != ring:
                    continue
                px, py = cx + dx_i * 4.0, cy + dy_i * 4.0
                pos = [(px + ox, py + oy) for ox, oy in offsets]
                if not all(zone.x_min + margin <= x <= zone.x_max - margin and
                           zone.y_min + margin <= y <= zone.y_max - margin for x, y in pos):
                    continue
                if all(math.hypot(x - s.x, y - s.y) >= 8.0 for x, y in pos for s in placed):
                    best = pos
                    break
            if best:
                break
        if best:
            break
    return best or [(cx + ox, cy + oy) for ox, oy in offsets]


def facing_enemy(state: "DeploymentState", player: int, x: float, y: float) -> float:
    """The heading from (x, y) towards the centre of the enemy's deployment
    zone, to the nearest 5 degrees (headings: 0 = +x, 90 = +y)."""
    import math
    other = state.zones.get(3 - player)
    if other is None:
        return 0.0
    cx, cy = (other.x_min + other.x_max) / 2, (other.y_min + other.y_max) / 2
    h = math.degrees(math.atan2(cy - y, cx - x)) % 360.0
    return (round(h / 5.0) * 5.0) % 360.0


def placement_heading(gs, state: "DeploymentState", player: int, x: float, y: float) -> float:
    """A ship's default heading where it is placed: the scenario's required
    facing if it has one (scenarios.auto_heading), else facing the enemy's
    zone. (Before, Auto-Place faced every ship along the table, and a
    scenario's 0-degree facing was taken for "none".)"""
    from .scenarios import auto_heading
    h = auto_heading(gs, player, x, y)
    return facing_enemy(state, player, x, y) if h is None else h


def auto_place(gs, state: "DeploymentState") -> List[str]:
    """Place every group still to deploy (the window's Auto-Place): the
    scenario's positions where it has them (scenarios.auto_positions), else a
    row in the zone; headings from the scenario or facing the enemy. Placed
    ships are written to `gs`. Returns the errors of a group that couldn't be
    placed (it stops there)."""
    from .scenarios import auto_positions
    while not state.is_complete():
        group = state.current_group()
        if group is None:
            break
        p = state.active_player
        zone = state.zones[p]
        positions = (auto_positions(gs, group, zone, state.placed_ships, state.next_idx[p])
                     or grid_positions(group, zone, state.placed_ships))
        headings = [placement_heading(gs, state, p, x, y) for x, y in positions]
        ok, errors = state.place_group(positions, headings)
        if not ok:
            return [f"{group[0].name}: {e}" for e in errors]
        for ship in state.placed_ships[-len(group):]:
            gs.update_ship(ship)
    return []
