"""Optional blast marker rules (core s.11), chosen in the game's Advanced settings.

"standard": the XR rules. "modern": Optional: Modern Blast Markers (intervening
blasts, overlapping bases). "remastered": Remastered Blast Markers (the modern
rules plus whole-base contact and a firing ship in contact shifting right).
The spill-over limit isn't modelled. The game sets the mode from
GameState.blast_marker_rules (TurnController, the settings dialog); the engine
reads it here because gunnery and ordnance code don't always see the game state.
"""
import math

MODES = ("standard", "modern", "remastered")
_mode = "standard"


def set_blast_rules(mode: str) -> None:
    global _mode
    _mode = mode if mode in MODES else "standard"


def blast_rules() -> str:
    return _mode


_remastered_suppression = False


def set_suppression_rules(remastered: bool) -> None:
    """Turret suppression mode (Advanced settings, `GameState.
    rule_turret_suppression_remastered`): False = XR (s.27: a surviving fighter
    gives one bomber exactly 3 attacks), True = Remastered p.82 (each fighter in
    the wave adds +1 attack to the wave's total, capped at the surviving bombers)."""
    global _remastered_suppression
    _remastered_suppression = bool(remastered)


def remastered_suppression() -> bool:
    return _remastered_suppression


_ships_source = None


def set_ship_source(fn) -> None:
    """fn() -> the ships on the table (TurnController registers the game's)."""
    global _ships_source
    _ships_source = fn


def overlap_ships(ship) -> list:
    """Other ships whose base overlaps this ship's base (Modern / Remastered
    "Overlapping bases")."""
    if _ships_source is None:
        return []
    out = []
    for o in _ships_source():
        if o.id == ship.id or getattr(o, "is_destroyed", False) or getattr(o, "is_disengaged", False):
            continue
        if math.hypot(o.x - ship.x, o.y - ship.y) < o.base_radius + ship.base_radius:
            out.append(o)
    return out


def touches_blast(ship, blast_markers) -> bool:
    from .geometry import blast_markers_touching_direct
    return bool(blast_markers_touching_direct(ship, blast_markers or []))


def in_blast_contact(ship, blast_markers, ships=None) -> bool:
    """A ship touching blast markers, or (modern / remastered "Overlapping
    bases") one whose base overlaps the base of a ship touching them; no
    cascade along a chain of overlapping ships."""
    if touches_blast(ship, blast_markers):
        return True
    if _mode == "standard" or not ships:
        return False
    for o in ships:
        if o.id == ship.id or getattr(o, "is_destroyed", False):
            continue
        if (math.hypot(o.x - ship.x, o.y - ship.y) < o.base_radius + ship.base_radius
                and touches_blast(o, blast_markers)):
            return True
    return False


def blast_gunnery_shift(firer, target, line_shift: int, blast_markers, ships=None) -> int:
    """Right column shifts from blast markers for gunnery. Modern: a target in
    contact counts as behind them (at least one shift). Remastered: one shift if
    the line passes through markers or the firer or target is in contact."""
    if _mode == "standard":
        return line_shift
    contact = in_blast_contact(target, blast_markers, ships)
    if _mode == "remastered":
        contact = contact or in_blast_contact(firer, blast_markers, ships)
    return max(line_shift, 1 if contact else 0)


_sunward_edge = None          # set when Fighting Sunward (s.40) is on


def set_sunward(enabled: bool, edge: str = "north") -> None:
    global _sunward_edge
    _sunward_edge = edge if enabled else None


def sunward_edge():
    return _sunward_edge
