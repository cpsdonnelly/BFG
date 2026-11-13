"""Miasma of Pestilence: ordnance attacking the ship counts as passing through
blast markers (Chaos, Plague Fleet of Nurgle), so the AI values its ordnance at
5/6 survival against it (`ai_hazards.attack_survival`, `best_route`)."""
from src.ai_hazards import attack_survival, best_route
from src.game_state import GameState
from src.models import Ship


def _ship(id, player, x, rules):
    return Ship(id=id, name=id, ship_class="T", faction="chaos", player=player,
                ship_type="cruiser", base_size="small", x=x, y=60.0, heading=0.0, speed=20,
                turn_angle=45, shields_max=2, armor_prow="6+", armor_side="5+", turrets=1,
                hits_max=8, leadership=7, weapons=[], special_rules=rules, upgrades=[],
                critical_damage=[], points_value=180)


def test_attack_survival_miasma():
    gs = GameState()
    plain, nurgle = _ship("p", 2, 100.0, []), _ship("n", 2, 100.0, ["miasma"])
    gs.add_ship(plain)
    assert attack_survival(plain, gs) == 1.0
    assert abs(attack_survival(nurgle, gs) - 5 / 6) < 1e-9
    assert attack_survival(None, gs) == 1.0


def test_best_route_counts_miasma():
    gs = GameState()
    nurgle = _ship("n", 2, 100.0, ["miasma"])
    gs.add_ship(nurgle)
    plain = best_route(20.0, 60.0, 100.0, 60.0, gs, "craft", 20.0)
    miasma = best_route(20.0, 60.0, 100.0, 60.0, gs, "craft", 20.0, target=nurgle)
    assert abs(miasma[1] - plain[1] * 5 / 6) < 1e-9
    assert miasma[0] < plain[0]
