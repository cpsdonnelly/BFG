"""Tests for src/tables.py — pure table lookups, no dice needed."""
from src.tables import get_gunnery_column, lookup_gunnery_dice, lookup_catastrophic


# ── get_gunnery_column ────────────────────────────────────────────────────────

def test_capital_closing():
    assert get_gunnery_column("capital", "closing") == 2


def test_capital_moving_away():
    assert get_gunnery_column("capital", "moving_away") == 3


def test_capital_abeam():
    assert get_gunnery_column("capital", "abeam") == 4


def test_escort_closing():
    assert get_gunnery_column("escort", "closing") == 3


def test_escort_moving_away():
    assert get_gunnery_column("escort", "moving_away") == 4


def test_escort_abeam():
    assert get_gunnery_column("escort", "abeam") == 5


def test_defense_is_col1():
    assert get_gunnery_column("defense", "closing") == 1


def test_ordnance_type_is_col5():
    assert get_gunnery_column("ordnance", "closing") == 5


def test_is_ordnance_flag_overrides_type():
    assert get_gunnery_column("capital", "closing", is_ordnance=True) == 5


# ── lookup_gunnery_dice ───────────────────────────────────────────────────────

def test_fp_zero_returns_zero():
    assert lookup_gunnery_dice(0, 2) == 0


def test_basic_lookup_fp6_col2():
    # GUNNERY_TABLE[6][col2-1] = GUNNERY_TABLE[6][1] = 4
    assert lookup_gunnery_dice(6, 2) == 4


def test_left_shift_to_col1():
    # FP 6, col 2, shift -1 → col 1 → GUNNERY_TABLE[6][0] = 5
    assert lookup_gunnery_dice(6, 2, shifts=-1) == 5


def test_left_shift_past_col0_returns_fp():
    # FP 6, col 2, shift -2 → col 0 → returns FP value (6)
    assert lookup_gunnery_dice(6, 2, shifts=-2) == 6


def test_right_shift_past_col5_returns_zero():
    # FP 6, col 2, shift +4 → col 6 → 0 dice
    assert lookup_gunnery_dice(6, 2, shifts=4) == 0


def test_right_shift_to_col5():
    # FP 6, col 2, shift +3 → col 5 → GUNNERY_TABLE[6][4] = 1
    assert lookup_gunnery_dice(6, 2, shifts=3) == 1


def test_fp_above_20_splits():
    # FP 22 = lookup(20, col2) + lookup(2, col2)
    assert lookup_gunnery_dice(22, 2) == lookup_gunnery_dice(20, 2) + lookup_gunnery_dice(2, 2)


def test_fp1_col2_no_shifts():
    # GUNNERY_TABLE[1][1] = 1
    assert lookup_gunnery_dice(1, 2) == 1


# ── lookup_catastrophic ───────────────────────────────────────────────────────

def test_roll_2_drifting_hulk():
    assert lookup_catastrophic(2) == "drifting_hulk"


def test_roll_6_drifting_hulk():
    assert lookup_catastrophic(6) == "drifting_hulk"


def test_roll_7_burning_hulk():
    assert lookup_catastrophic(7) == "burning_hulk"


def test_roll_8_burning_hulk():
    assert lookup_catastrophic(8) == "burning_hulk"


def test_roll_9_plasma_drive_overload():
    assert lookup_catastrophic(9) == "plasma_drive_overload"


def test_roll_11_plasma_drive_overload():
    assert lookup_catastrophic(11) == "plasma_drive_overload"


def test_roll_12_warp_drive_implosion():
    assert lookup_catastrophic(12) == "warp_drive_implosion"
