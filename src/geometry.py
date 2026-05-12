"""BFG:XR Shared geometry utilities."""
import math
from typing import List
from .models import Ship, BlastMarker


# Physical radius of a blast marker token (30mm wide trefoil → 15mm = 1.5cm).
# Used for ship-blast-marker contact and LoS obstruction checks.
BLAST_MARKER_RADIUS_CM = 1.5

# Extra margin added on top of the sum of two ship base radii to count as
# "base contact". +1cm per the player-friendliness rule requested.
BASE_CONTACT_MARGIN_CM = 1.0


def line_passes_near(x1, y1, x2, y2, px, py, threshold) -> bool:
    """Return True if the line segment (x1,y1)→(x2,y2) passes within threshold of (px,py)."""
    dx, dy = x2 - x1, y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.sqrt((px - x1) ** 2 + (py - y1) ** 2) <= threshold
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / length_sq))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.sqrt((px - proj_x) ** 2 + (py - proj_y) ** 2) <= threshold


def count_blast_markers_touching(ship: Ship,
                                  blast_markers: List[BlastMarker]) -> int:
    """Count blast markers whose centre is within base contact of a ship."""
    count = 0
    for bm in blast_markers:
        dist = math.sqrt((bm.x - ship.x) ** 2 + (bm.y - ship.y) ** 2)
        if dist <= ship.base_radius + BLAST_MARKER_RADIUS_CM:
            count += 1
    return count
