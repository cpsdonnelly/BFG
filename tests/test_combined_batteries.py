"""Owner ruling (s.11 / s.13): a ship's macrobatteries of one gunnery type at
one target make ONE Gunnery table roll on their total firepower; blast
markers come into effect at once for later attacks; different gunnery
types may fire simultaneously (s.13 Mixing Different Gunnery Weapons)."""
from src.combat import (combined_battery, gunnery_kind, resolve_battery_group,
                        get_gunnery_column, gunnery_target_type)
from src.tables import lookup_gunnery_dice
from tests.conftest import make_gs, make_ship

BAT = dict(name="Prow Battery", weapon_type="battery", strength=4, range=45,
           arcs=["front"], crit_on=6)
BC = dict(name="Bombardment Cannon", weapon_type="battery", strength=3, range=30,
          arcs=["front"], hits_on=4, crit_on=4)


class Dice:
    """Every die a 4; records each roll's count."""

    def __init__(self):
        self.calls = []

    def roll_d6(self, n, label=""):
        self.calls.append((n, label))
        return [4] * n


def _ships():
    a = make_ship(id="a", x=0.0, y=0.0, heading=0.0,
                  weapons=[dict(BAT), dict(BAT, name="Dorsal Battery"), dict(BC)])
    t = make_ship(id="t", player=2, x=20.0, y=0.0, heading=180.0, shields_max=0)
    return a, t


def test_two_batteries_make_one_roll_on_their_total():
    a, t = _ships()
    dice = Dice()
    sr, applied = resolve_battery_group(a, t, [dict(BAT), dict(BAT, name="Dorsal Battery")],
                                        dice, [])
    assert applied is None and len(dice.calls) == 1
    col = get_gunnery_column(gunnery_target_type(t), a.get_target_orientation(t))
    assert dice.calls[0][0] == lookup_gunnery_dice(8, col, 0)      # FP 4 + 4 = 8, not 4 and 4


def test_each_weapon_halved_before_totalling():
    a, t = _ships()
    a.special_order = "burn_retros"                 # half firepower, rounding up, each
    w = combined_battery(a, [dict(BAT, strength=3), dict(BAT, strength=3)], t)
    assert w["combined_fp"] == 4                    # 2 + 2, not (3 + 3) / 2 = 3


def test_gunnery_kinds_keep_bombardment_cannons_apart():
    assert gunnery_kind(BAT) == gunnery_kind(dict(BAT, name="x"))
    assert gunnery_kind(BAT) != gunnery_kind(BC)


def test_ai_fires_a_ships_batteries_at_one_target_as_one_roll(monkeypatch):
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    import src.combat as combat
    a, t = _ships()
    a.weapons = [dict(BAT), dict(BAT, name="Dorsal Battery")]
    gs = make_gs([a, t])
    seen = []
    real = combat.resolve_battery_group

    def spy(attacker, target, shots, *args, **kw):
        seen.append((target.id, [s["strength"] for s in shots]))
        return real(attacker, target, shots, *args, **kw)
    monkeypatch.setattr(combat, "resolve_battery_group", spy)
    dice = Dice()
    tc = TurnController(gs, dice, save_dir=None)
    ai = AIPlayer(1, tc, gs, dice)
    ai.brace_fn = lambda *a, **k: None
    ai.run_shooting_phase()
    assert seen == [("t", [4, 4])]                  # one attack with both batteries


def test_later_attacks_see_new_markers_unless_simultaneous(monkeypatch):
    """Two gunnery types at one target: in sequence the second sees the
    markers the first placed; together both use the markers from before."""
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    import src.combat as combat
    a, t = _ships()
    t.shields_max = 2
    gs = make_gs([a, t])
    markers_seen = []
    real = combat.resolve_battery_group

    def spy(attacker, target, shots, dice, markers, *args, **kw):
        markers_seen.append(len(markers))
        return real(attacker, target, shots, dice, markers, *args, **kw)
    monkeypatch.setattr(combat, "resolve_battery_group", spy)
    dice = Dice()
    tc = TurnController(gs, dice, save_dir=None)
    ai = AIPlayer(1, tc, gs, dice)
    ai.brace_fn = lambda *a, **k: None
    ai.run_shooting_phase()
    # 8 hits remaining + 2 shields is more than the batteries' expected hits:
    # fired together, so both attacks see the table as it was (no markers)
    assert markers_seen == [0, 0]


def test_an_escort_totals_first_then_halves():
    """Standing ruling: escorts total first, then halve (s.8)."""
    a, t = _ships()
    a.ship_type = "escort"
    a.special_order = "burn_retros"
    w = combined_battery(a, [dict(BAT, strength=3), dict(BAT, strength=3)], t)
    assert w["combined_fp"] == 3                    # (3 + 3) / 2, not 2 + 2
