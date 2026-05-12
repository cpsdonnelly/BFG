#!/usr/bin/env python3
"""
Splits game_panel.py into mixin files + thin coordinator.

Usage:  python3 tools/split_game_panel.py [--dry-run]
"""
import sys
import os

SRC = os.path.join(os.path.dirname(__file__), '..', 'src')
GP  = os.path.join(SRC, 'game_panel.py')
DRY = '--dry-run' in sys.argv

with open(GP) as f:
    lines = f.readlines()   # 0-indexed; line N (1-indexed) = lines[N-1]

TOTAL = len(lines)
print(f"Read {TOTAL} lines from {GP}")

# ── Method ranges (1-indexed, inclusive) ─────────────────────────────────────
# Each range covers a method plus any trailing blank/comment lines up to the
# next method definition.

MOVEMENT_RANGES = [
    (189, 314),    # _wire_drag_callbacks
    (315, 432),    # _quick_min_move_selected
    (447, 493),    # _min_move_all_ships
    (494, 504),    # _undo_all_movement
    (505, 549),    # _redraw_pending_turn_ghost
    (550, 577),    # _process_movement_phase_start
    (877, 996),    # _special_order_dialog
    (997, 1457),   # _move_ship_dialog
    (1458, 1477),  # _undo_movement
]

END_PHASE_RANGES = [
    (641, 732),    # _resolve_teleport_attacks
    (733, 784),    # _repair_choice_dialog
]

COMBAT_RANGES = [
    (1478, 1988),  # _fire_dialog
    (2168, 2371),  # _fire_at_ordnance_dialog
    (3489, TOTAL), # _weapon_disabled_by_crit  (last method — run to EOF)
]

ORDNANCE_RANGES = [
    (1989, 2167),  # _move_tau_missiles_dialog
    (2372, 2385),  # _get_player_bay_capacity
    (2386, 2400),  # _count_active_craft
    (2401, 2411),  # _update_cap_positions
    (2412, 2456),  # _check_cap_intercept
    (2468, 2761),  # _resolve_ordnance_movement
    (2762, 3351),  # _launch_ordnance_dialog
]

# Build a set of all line numbers that move into a mixin (1-indexed)
def ranges_to_set(ranges):
    s = set()
    for a, b in ranges:
        for i in range(a, b + 1):
            s.add(i)
    return s

moved = (ranges_to_set(MOVEMENT_RANGES)
         | ranges_to_set(END_PHASE_RANGES)
         | ranges_to_set(COMBAT_RANGES)
         | ranges_to_set(ORDNANCE_RANGES))

# ── Helpers ───────────────────────────────────────────────────────────────────

def extract(ranges):
    """Return the file content for the given 1-indexed ranges."""
    out = []
    for a, b in ranges:
        out.extend(lines[a - 1 : b])
    return out


COMMON_IMPORTS = """\
\"\"\"BFG:XR — extracted panel mixin (see game_panel.py for context).\"\"\"
import tkinter as tk
from tkinter import messagebox, simpledialog
import math
from typing import Optional, Callable, List

from .models import Ship, SpecialOrder, OrdnanceMarker, OrdnanceType
from .game_state import GameState
from .turn_controller import TurnController
from .dice import DiceRoller
from .movement import (MoveCommand, validate_movement, execute_movement,
                       resolve_aaf_speed, MIN_TURN_DISTANCE)
from .combat import (check_weapon_in_arc, check_weapon_in_range,
                     resolve_batteries, resolve_lances, resolve_nova_cannon,
                     apply_damage, check_los_clear)
from .end_phase import resolve_end_phase
from .geometry import (circle_touches_square, circle_touches_torpedo,
                        ATTACK_CRAFT_HALF_SIDE_CM)
"""


def write_mixin(filename, classname, ranges, extra_header=''):
    body = extract(ranges)
    content = COMMON_IMPORTS
    if extra_header:
        content += extra_header + '\n'
    content += f'\n\nclass {classname}:\n    """Mixin — methods injected into GamePanel."""\n\n'
    content += ''.join(body)
    # Ensure file ends with newline
    if not content.endswith('\n'):
        content += '\n'
    path = os.path.join(SRC, filename)
    if DRY:
        print(f"[DRY] Would write {path}  ({len(body)} lines of methods)")
    else:
        with open(path, 'w') as f:
            f.write(content)
        print(f"Wrote {path}  ({len(body)} lines of methods)")


# ── Build new game_panel.py ───────────────────────────────────────────────────

def build_coordinator():
    """Return lines for the new slim game_panel.py."""
    out = []
    for i, line in enumerate(lines, start=1):
        if i in moved:
            continue
        out.append(line)
    return out


# ── Verify coverage ───────────────────────────────────────────────────────────

all_method_starts = {
    27, 46, 141, 178, 185, 189, 315, 433, 447, 494, 505, 550, 578, 641,
    733, 785, 877, 997, 1458, 1478, 1989, 2168, 2372, 2386, 2401, 2412,
    2457, 2468, 2762, 3352, 3438, 3447, 3489,
}
coordinator_methods = {27, 46, 141, 178, 185, 433, 578, 785, 2457, 3352, 3438, 3447}
expected_in_mixin = all_method_starts - coordinator_methods

print("\n=== COVERAGE CHECK ===")
for m in sorted(expected_in_mixin):
    if m not in moved:
        print(f"  WARNING: method at line {m} not covered by any mixin range!")
    else:
        print(f"  OK  line {m}")

coordinator_lines = build_coordinator()
print(f"\nCoordinator will be ~{len(coordinator_lines)} lines "
      f"(was {TOTAL}; removed {TOTAL - len(coordinator_lines)})")

# ── Write files ───────────────────────────────────────────────────────────────

write_mixin('_movement_mixin.py', '_MovementMixin', MOVEMENT_RANGES)
write_mixin('_combat_mixin.py',   '_CombatMixin',   COMBAT_RANGES)
write_mixin('_ordnance_mixin.py', '_OrdnanceMixin', ORDNANCE_RANGES)
write_mixin('_end_phase_mixin.py','_EndPhaseMixin', END_PHASE_RANGES)

# Patch coordinator: add mixin imports + inheritance right after existing imports
if not DRY:
    coord_content = ''.join(coordinator_lines)

    # Replace original class line with mixin imports + new class definition
    old_class = 'class GamePanel:\n'
    new_class = (
        'from ._movement_mixin  import _MovementMixin\n'
        'from ._combat_mixin    import _CombatMixin\n'
        'from ._ordnance_mixin  import _OrdnanceMixin\n'
        'from ._end_phase_mixin import _EndPhaseMixin\n'
        '\n'
        '\n'
        'class GamePanel(_MovementMixin, _CombatMixin, _OrdnanceMixin, _EndPhaseMixin):\n'
    )
    if old_class in coord_content:
        coord_content = coord_content.replace(old_class, new_class, 1)
        print(f"\nPatched class definition with mixin inheritance")
    else:
        print(f"\nWARNING: could not find 'class GamePanel:' to patch!")

    with open(GP, 'w') as f:
        f.write(coord_content)
    print(f"Wrote updated {GP}  ({len(coordinator_lines)} lines)")
else:
    print("\n[DRY] Would patch class GamePanel to inherit from mixins")

print("\nDone.")
