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


def touches_blast(ship, blast_markers) -> bool:
    from .geometry import count_blast_markers_touching
    return count_blast_markers_touching(ship, blast_markers or []) > 0


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
