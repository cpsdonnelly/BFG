"""BFG:XR Shared geometry utilities."""
import math
from typing import List, Tuple
from .models import Ship, BlastMarker


# ── Ship / base-contact constants ────────────────────────────────────────────

# Extra margin added on top of the sum of two ship base radii to count as
# "base contact". Default 0.2 cm; configurable via GameState.contact_margin_cm.
BASE_CONTACT_MARGIN_CM = 1.0  # legacy default kept for callers that can't
                               # reach GameState — use gs.contact_margin_cm where possible.

# ── Blast-marker (trefoil token) geometry ────────────────────────────────────

# Printed trefoil token is ~30 mm across.  Each of the three lobes has an
# 8 mm radius; lobe centres sit 8 mm from the trefoil centre, 120° apart.
BLAST_LOBE_RADIUS_CM = 0.8
BLAST_LOBE_OFFSET_CM = 0.8

# Legacy scalar used for LoS and contact before proper trefoil shapes were
# introduced.  Kept so existing call-sites that import it still compile.
BLAST_MARKER_RADIUS_CM = BLAST_LOBE_OFFSET_CM + BLAST_LOBE_RADIUS_CM  # 1.6 cm

# ── Torpedo marker geometry ───────────────────────────────────────────────────

# Printed token: 25 mm wide × 20 mm tall (body 10 mm + three fins 10 mm each).
TORP_BODY_HALF_W_CM = 1.25   # half the 25 mm body width (perpendicular to heading)
TORP_BODY_HALF_H_CM = 0.50   # half the 10 mm body depth (along heading)
TORP_FIN_HEIGHT_CM  = 1.00   # 10 mm fins project from the forward edge
_TORP_FIN_THIRD_CM  = TORP_BODY_HALF_W_CM * 2 / 3   # 8.33 mm — one-third of body width

# ── Attack-craft marker geometry ─────────────────────────────────────────────

# Each squadron is a 20 mm square marker.
ATTACK_CRAFT_HALF_SIDE_CM = 1.0   # half the 20 mm side


# ── Basic helpers ─────────────────────────────────────────────────────────────

def line_passes_near(x1: float, y1: float, x2: float, y2: float,
                     px: float, py: float, threshold: float) -> bool:
    """True if line segment (x1,y1)→(x2,y2) passes within threshold of (px,py)."""
    dx, dy = x2 - x1, y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.sqrt((px - x1) ** 2 + (py - y1) ** 2) <= threshold
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / length_sq))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.sqrt((px - proj_x) ** 2 + (py - proj_y) ** 2) <= threshold


# ── Primitive shape collision tests ──────────────────────────────────────────

def circle_touches_oriented_rect(cx: float, cy: float, r: float,
                                  rect_cx: float, rect_cy: float,
                                  half_w: float, half_h: float,
                                  heading_deg: float) -> bool:
    """True if circle (cx,cy,r) overlaps a rectangle centred at (rect_cx,rect_cy).

    half_w  — half-extent perpendicular to heading
    half_h  — half-extent along heading
    heading_deg — rectangle's forward direction (degrees, 0 = East)
    """
    angle = math.radians(heading_deg)
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    dx = cx - rect_cx
    dy = cy - rect_cy
    # Project into the rectangle's local frame
    local_fwd = dx * cos_a + dy * sin_a
    local_lat = -dx * sin_a + dy * cos_a
    # Distance from circle centre to nearest point on rect
    near_fwd = max(-half_h, min(half_h, local_fwd))
    near_lat = max(-half_w, min(half_w, local_lat))
    dist_sq = (local_fwd - near_fwd) ** 2 + (local_lat - near_lat) ** 2
    return dist_sq <= r * r


def circle_touches_triangle(cx: float, cy: float, r: float,
                             ax: float, ay: float,
                             bx: float, by: float,
                             tx: float, ty: float) -> bool:
    """True if circle (cx,cy,r) overlaps triangle A-B-T."""
    def _cross(px, py, x1, y1, x2, y2):
        return (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)

    d1 = _cross(cx, cy, ax, ay, bx, by)
    d2 = _cross(cx, cy, bx, by, tx, ty)
    d3 = _cross(cx, cy, tx, ty, ax, ay)
    has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
    has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
    if not (has_neg and has_pos):   # centre inside triangle
        return True

    def _seg_dist_sq(px, py, x1, y1, x2, y2):
        edx, edy = x2 - x1, y2 - y1
        len_sq = edx * edx + edy * edy
        if len_sq == 0:
            return (px - x1) ** 2 + (py - y1) ** 2
        t = max(0.0, min(1.0, ((px - x1) * edx + (py - y1) * edy) / len_sq))
        return (px - x1 - t * edx) ** 2 + (py - y1 - t * edy) ** 2

    r_sq = r * r
    return min(
        _seg_dist_sq(cx, cy, ax, ay, bx, by),
        _seg_dist_sq(cx, cy, bx, by, tx, ty),
        _seg_dist_sq(cx, cy, tx, ty, ax, ay),
    ) <= r_sq


def circle_touches_trefoil(cx: float, cy: float, r: float,
                            trefoil_x: float, trefoil_y: float,
                            heading_deg: float) -> bool:
    """True if circle (cx,cy,r) overlaps a trefoil blast marker.

    The trefoil is centred at (trefoil_x, trefoil_y).  Its first lobe points
    in the direction heading_deg; the other two are 120° and 240° further.
    """
    for i in range(3):
        angle = math.radians(heading_deg + i * 120.0)
        lobe_x = trefoil_x + BLAST_LOBE_OFFSET_CM * math.cos(angle)
        lobe_y = trefoil_y + BLAST_LOBE_OFFSET_CM * math.sin(angle)
        dist_sq = (cx - lobe_x) ** 2 + (cy - lobe_y) ** 2
        if dist_sq <= (r + BLAST_LOBE_RADIUS_CM) ** 2:
            return True
    return False


# ── Composite token collision tests ──────────────────────────────────────────

def circle_touches_torpedo(cx: float, cy: float, r: float,
                            torp_x: float, torp_y: float,
                            heading_deg: float) -> bool:
    """True if circle (cx,cy,r) overlaps a torpedo marker.

    Token shape: rectangular body (25 mm × 10 mm) plus three triangular fins
    projecting 10 mm forward from the leading edge, evenly spaced.
    heading_deg is the direction of travel (forward direction).
    """
    # Body
    if circle_touches_oriented_rect(cx, cy, r, torp_x, torp_y,
                                     TORP_BODY_HALF_W_CM, TORP_BODY_HALF_H_CM,
                                     heading_deg):
        return True

    angle = math.radians(heading_deg)
    cos_a, sin_a = math.cos(angle), math.sin(angle)

    def _w(lat: float, fwd: float) -> Tuple[float, float]:
        """Local (lateral, forward) offsets → world coordinates."""
        return (torp_x + fwd * cos_a - lat * sin_a,
                torp_y + fwd * sin_a + lat * cos_a)

    third = _TORP_FIN_THIRD_CM
    hw = TORP_BODY_HALF_W_CM
    hh = TORP_BODY_HALF_H_CM
    tip_fwd = hh + TORP_FIN_HEIGHT_CM

    fins = [
        # (left base vertex, right base vertex, tip vertex) — in local coords
        ((-hw,             hh), (-hw + third,     hh), (-hw + third / 2,   tip_fwd)),
        ((-hw + third,     hh), (-hw + 2 * third, hh), (0.0,               tip_fwd)),
        ((-hw + 2 * third, hh), (hw,              hh), (hw - third / 2,    tip_fwd)),
    ]
    for (la1, fwd1), (la2, fwd2), (lat, fwdt) in fins:
        ax, ay = _w(la1, fwd1)
        bx_, by_ = _w(la2, fwd2)
        tx, ty = _w(lat, fwdt)
        if circle_touches_triangle(cx, cy, r, ax, ay, bx_, by_, tx, ty):
            return True
    return False


def circle_touches_square(cx: float, cy: float, r: float,
                           sq_x: float, sq_y: float,
                           heading_deg: float) -> bool:
    """True if circle (cx,cy,r) overlaps a square attack-craft marker.

    The marker is a 20 mm × 20 mm square (ATTACK_CRAFT_HALF_SIDE_CM on each side).
    """
    return circle_touches_oriented_rect(
        cx, cy, r,
        sq_x, sq_y,
        ATTACK_CRAFT_HALF_SIDE_CM, ATTACK_CRAFT_HALF_SIDE_CM,
        heading_deg,
    )


# ── Line vs token tests (for LoS / movement obstruction) ─────────────────────

def line_touches_trefoil(x1: float, y1: float, x2: float, y2: float,
                          trefoil_x: float, trefoil_y: float,
                          heading_deg: float) -> bool:
    """True if line segment (x1,y1)→(x2,y2) passes through a trefoil blast marker."""
    for i in range(3):
        angle = math.radians(heading_deg + i * 120.0)
        lobe_x = trefoil_x + BLAST_LOBE_OFFSET_CM * math.cos(angle)
        lobe_y = trefoil_y + BLAST_LOBE_OFFSET_CM * math.sin(angle)
        if line_passes_near(x1, y1, x2, y2, lobe_x, lobe_y, BLAST_LOBE_RADIUS_CM):
            return True
    return False


# ── Blast-marker placement helpers ───────────────────────────────────────────

def contact_point_on_ship(ship_cx: float, ship_cy: float, ship_r: float,
                           attacker_x: float, attacker_y: float) -> Tuple[float, float]:
    """Return the point on a ship's base perimeter closest to the attacker."""
    dx = attacker_x - ship_cx
    dy = attacker_y - ship_cy
    dist = math.sqrt(dx * dx + dy * dy)
    if dist == 0:
        return ship_cx + ship_r, ship_cy
    return ship_cx + ship_r * dx / dist, ship_cy + ship_r * dy / dist


def place_trefoil(ship_cx: float, ship_cy: float, ship_r: float,
                  contact_x: float, contact_y: float
                  ) -> Tuple[float, float, float]:
    """Return (tx, ty, heading_deg) for a trefoil blast marker placed so that
    two inner lobes are tangent to the ship's base circle at the contact point.

    The trefoil centre sits along the direction from ship centre → contact point
    at distance p, where p is derived from the tangency condition:

        p = (L + sqrt(4*(R+r)^2 - 3*L^2)) / 2

    with L = BLAST_LOBE_OFFSET_CM, r = BLAST_LOBE_RADIUS_CM, R = ship_r.
    heading_deg points the first lobe inward toward the ship centre.
    """
    dx = contact_x - ship_cx
    dy = contact_y - ship_cy
    dist = math.sqrt(dx * dx + dy * dy)
    if dist == 0:
        dx, dy, dist = 1.0, 0.0, 1.0

    L = BLAST_LOBE_OFFSET_CM
    r = BLAST_LOBE_RADIUS_CM
    R = ship_r
    discriminant = 4.0 * (R + r) ** 2 - 3.0 * L ** 2
    p = (L + math.sqrt(max(0.0, discriminant))) / 2.0

    tx = ship_cx + p * dx / dist
    ty = ship_cy + p * dy / dist
    # First lobe faces inward (toward ship centre)
    heading_deg = math.degrees(math.atan2(-dy, -dx)) % 360.0
    return tx, ty, heading_deg


# ── Convenience: count blast markers touching a ship ─────────────────────────

def count_blast_markers_touching(ship: Ship,
                                  blast_markers: List[BlastMarker]) -> int:
    """Count blast markers whose trefoil overlaps the ship's base circle."""
    count = 0
    for bm in blast_markers:
        if circle_touches_trefoil(ship.x, ship.y, ship.base_radius,
                                   bm.x, bm.y, bm.heading):
            count += 1
    return count
