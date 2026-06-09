"""BFG:XR Line of Sight - LoS checking through terrain and blast markers"""
import math
from typing import List
from .models import Ship, Phenomenon, BlastMarker
from .geometry import line_touches_trefoil


def check_los(x1: float, y1: float, x2: float, y2: float,
              phenomena: List[Phenomenon],
              blast_markers: List[BlastMarker] = None) -> dict:
    """
    Check line of sight between two points.
    Returns dict with:
      - clear: bool (true if LoS is not blocked)
      - blocked_by: str or None (what blocks it)
      - blast_markers_crossed: int (count of blast markers in the line)
      - dust_clouds_crossed: int
      - column_shifts: int (right shifts from blast/dust)
    """
    result = {
        "clear": True,
        "blocked_by": None,
        "blast_markers_crossed": 0,
        "dust_clouds_crossed": 0,
        "column_shifts": 0,
    }
    blast_markers = blast_markers or []

    for p in phenomena:
        ptype = p.phenomenon_type

        # Planets block LoS
        if "planet" in ptype and p.radius > 0:
            if _line_intersects_circle(x1, y1, x2, y2, p.x, p.y, p.radius):
                result["clear"] = False
                result["blocked_by"] = f"Planet ({p.id})"
                return result

        # Asteroid fields block LoS
        if ptype == "asteroid_field":
            if _line_intersects_rect(x1, y1, x2, y2,
                                      p.x - p.width/2, p.y - p.height/2,
                                      p.x + p.width/2, p.y + p.height/2):
                result["clear"] = False
                result["blocked_by"] = f"Asteroid Field ({p.id})"
                return result

        # Warp rifts block LoS
        if ptype == "warp_rift":
            if _line_intersects_rect(x1, y1, x2, y2,
                                      p.x - p.width/2, p.y - p.height/2,
                                      p.x + p.width/2, p.y + p.height/2):
                result["clear"] = False
                result["blocked_by"] = f"Warp Rift ({p.id})"
                return result

        # Gas/dust clouds cause column shift but don't block
        if ptype == "gas_dust_cloud":
            if _line_intersects_rect(x1, y1, x2, y2,
                                      p.x - p.width/2, p.y - p.height/2,
                                      p.x + p.width/2, p.y + p.height/2):
                result["dust_clouds_crossed"] += 1
                result["column_shifts"] += 1

    # Check blast markers in line of fire (cause column shift for batteries)
    blast_crossed = False
    for bm in blast_markers:
        if line_touches_trefoil(x1, y1, x2, y2, bm.x, bm.y, bm.heading):
            if not blast_crossed:
                result["blast_markers_crossed"] += 1
                result["column_shifts"] += 1
                blast_crossed = True  # only one shift for blast markers total

    return result


def check_los_ships(attacker: Ship, target: Ship,
                    phenomena: List[Phenomenon],
                    blast_markers: List[BlastMarker] = None) -> dict:
    """Check LoS between two ships."""
    return check_los(attacker.x, attacker.y, target.x, target.y,
                     phenomena, blast_markers)


def _line_intersects_circle(x1, y1, x2, y2, cx, cy, r) -> bool:
    """Check if line segment (x1,y1)-(x2,y2) intersects circle at (cx,cy) with radius r."""
    dx, dy = x2 - x1, y2 - y1
    fx, fy = x1 - cx, y1 - cy

    a = dx * dx + dy * dy
    b = 2 * (fx * dx + fy * dy)
    c = fx * fx + fy * fy - r * r

    discriminant = b * b - 4 * a * c
    if discriminant < 0:
        return False

    discriminant = math.sqrt(discriminant)
    t1 = (-b - discriminant) / (2 * a)
    t2 = (-b + discriminant) / (2 * a)

    # Check if intersection is within segment [0, 1]
    return (0 <= t1 <= 1) or (0 <= t2 <= 1) or (t1 < 0 and t2 > 1)


def _line_intersects_rect(x1, y1, x2, y2,
                           rx1, ry1, rx2, ry2) -> bool:
    """Check if line segment intersects axis-aligned rectangle."""
    # Cohen-Sutherland style clipping test
    def _outcode(x, y):
        code = 0
        if x < rx1: code |= 1
        elif x > rx2: code |= 2
        if y < ry1: code |= 4
        elif y > ry2: code |= 8
        return code

    c1 = _outcode(x1, y1)
    c2 = _outcode(x2, y2)

    if c1 == 0 or c2 == 0:
        return True  # one endpoint inside
    if c1 & c2:
        return False  # both on same outside

    # Need full clip test - simplified: check if line passes through
    # Use parametric line intersection with each edge
    dx, dy = x2 - x1, y2 - y1

    for edge_x in [rx1, rx2]:
        if abs(dx) > 1e-9:
            t = (edge_x - x1) / dx
            if 0 <= t <= 1:
                y_at = y1 + t * dy
                if ry1 <= y_at <= ry2:
                    return True

    for edge_y in [ry1, ry2]:
        if abs(dy) > 1e-9:
            t = (edge_y - y1) / dy
            if 0 <= t <= 1:
                x_at = x1 + t * dx
                if rx1 <= x_at <= rx2:
                    return True

    return False


