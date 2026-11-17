"""Tests for src/geometry.py — collision detection and geometric helpers."""
from src.geometry import (
    circle_touches_square,
    circle_touches_trefoil,
    circle_touches_oriented_rect,
    line_passes_near,
    BLAST_LOBE_RADIUS_CM,
    BLAST_LOBE_OFFSET_CM,
    BLAST_MARKER_RADIUS_CM,
    ATTACK_CRAFT_HALF_SIDE_CM,
    TORP_BODY_HALF_W_CM,
    NOVA_CANNON_TEMPLATE_RADIUS_CM,
    NOVA_CANNON_CENTER_HOLE_RADIUS_CM,
)


# ── constants sanity ──────────────────────────────────────────────────────────

def test_blast_lobe_radius():
    assert BLAST_LOBE_RADIUS_CM == 0.8


def test_blast_lobe_offset():
    assert BLAST_LOBE_OFFSET_CM == 0.8


def test_blast_marker_radius_derived():
    assert BLAST_MARKER_RADIUS_CM == BLAST_LOBE_OFFSET_CM + BLAST_LOBE_RADIUS_CM


def test_attack_craft_half_side():
    assert ATTACK_CRAFT_HALF_SIDE_CM == 1.0


def test_nova_cannon_template_radius():
    assert NOVA_CANNON_TEMPLATE_RADIUS_CM == 2.5


def test_nova_cannon_center_hole_radius():
    assert NOVA_CANNON_CENTER_HOLE_RADIUS_CM == 0.6


# ── circle_touches_square ─────────────────────────────────────────────────────

def test_circle_touches_square_overlap():
    # Square centred at origin, heading 0°. Circle at (1.5, 0), radius 0.5.
    # half_side=1: square spans [-1,1] × [-1,1]. Circle at 1.5 with r=0.5 → edge at 1.0 touches.
    assert circle_touches_square(1.5, 0, 0.5, 0, 0, 0)


def test_circle_touches_square_clear():
    assert not circle_touches_square(10, 0, 0.5, 0, 0, 0)


def test_circle_touches_square_centre():
    # Circle centred exactly on the square
    assert circle_touches_square(0, 0, 0.1, 0, 0, 0)


def test_circle_touches_square_rotated():
    # Square at origin rotated 45°; circle at (2, 0), radius 0.5
    # Rotated square has corners at (±1.414, 0), (0, ±1.414)
    # Circle at x=2 cannot reach rotated square (max extent ~1.41)
    assert not circle_touches_square(2, 0, 0.5, 0, 0, 45)


# ── line_passes_near ──────────────────────────────────────────────────────────

def test_line_passes_near_direct_hit():
    # Line from (0,0) to (10,0) passes through (5, 0) → within threshold 1
    assert line_passes_near(0, 0, 10, 0, 5, 0, 1.0)


def test_line_passes_near_within_threshold():
    assert line_passes_near(0, 0, 10, 0, 5, 0.8, 1.0)


def test_line_passes_near_just_outside():
    assert not line_passes_near(0, 0, 10, 0, 5, 1.5, 1.0)


def test_line_passes_near_endpoint():
    # Point is at the endpoint of the segment
    assert line_passes_near(0, 0, 10, 0, 10, 0, 0.1)


def test_line_passes_near_zero_length_segment():
    # Degenerate segment (same start and end)
    assert line_passes_near(5, 5, 5, 5, 5.3, 5, 0.5)
    assert not line_passes_near(5, 5, 5, 5, 10, 5, 0.5)


# ── circle_touches_trefoil ────────────────────────────────────────────────────

def test_circle_touches_trefoil_at_centre():
    # Large circle centred on the trefoil
    assert circle_touches_trefoil(0, 0, 2.0, 0, 0, 0)


def test_circle_touches_trefoil_near_lobe():
    # Circle near the first lobe (pointing east at heading=0)
    # lobe centre = (0.8, 0); circle at (1.0, 0) radius 0.5 → distance 0.2 < 0.8
    assert circle_touches_trefoil(1.0, 0, 0.5, 0, 0, 0)


def test_circle_touches_trefoil_clear():
    assert not circle_touches_trefoil(20, 20, 0.1, 0, 0, 0)


def test_circle_touches_trefoil_second_lobe():
    # Heading 0: second lobe at 120° from east
    import math
    angle = math.radians(120)
    lobe_x = 0.8 * math.cos(angle)
    lobe_y = 0.8 * math.sin(angle)
    # Circle right on the second lobe centre
    assert circle_touches_trefoil(lobe_x, lobe_y, 0.1, 0, 0, 0)


# ── circle_touches_oriented_rect ─────────────────────────────────────────────

def test_oriented_rect_overlap():
    # Rect at (5,5), half_w=2, half_h=1, heading=0. Circle at (5,5) radius 0.5
    assert circle_touches_oriented_rect(5, 5, 0.5, 5, 5, 2, 1, 0)


def test_oriented_rect_clear():
    assert not circle_touches_oriented_rect(20, 20, 0.5, 0, 0, 1, 1, 0)
