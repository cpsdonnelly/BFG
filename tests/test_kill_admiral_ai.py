"""Kill the Admiral (owner): the AI values the flagship above the whole fleet,
both ways, counting crits (a Bridge Smashed kills the admiral and ends the game)."""
from tests.conftest import make_ship, make_gs
from src.ai_hazards import damage_vp, ship_value
from src.scenario import check_scenario_end
from src.scenarios import admiral_bonus_vp, bridge_smashed_chance


def _fleet():
    flag = make_ship(id="f", player=2, is_flagship=True, hits_max=8, points_value=200)
    others = [make_ship(id=f"o{i}", player=2, hits_max=8, points_value=180, x=30.0 * i)
              for i in range(1, 4)]
    gs = make_gs([flag] + others)
    gs.scenario_mode = "kill_admiral"
    return gs


def test_flagship_worth_more_than_the_whole_fleet():
    gs = _fleet()
    flag = gs.get_ship_by_id("f")
    fleet = sum(s.points_value for s in gs.player_ships(2))
    assert admiral_bonus_vp(gs, flag) > fleet - 1
    assert ship_value(flag, gs) + admiral_bonus_vp(gs, flag) > fleet
    assert admiral_bonus_vp(gs, gs.get_ship_by_id("o1")) == 0
    # the same hits are worth far more on the flagship (kills and bridge crits)
    assert damage_vp(flag, gs, 4.0) > 2 * damage_vp(gs.get_ship_by_id("o1"), gs, 4.0)
    gs.scenario_mode = "cruiser_clash"
    assert admiral_bonus_vp(gs, flag) == 0


def test_crits_count_and_bridge_smashed_ends_the_game():
    gs = _fleet()
    flag = gs.get_ship_by_id("f")
    assert abs(bridge_smashed_chance(flag) - 4 / 36) < 1e-9
    # a hit that can't kill is still worth a share of the bonus via the crit chance
    assert damage_vp(flag, gs, 1.0) > damage_vp(gs.get_ship_by_id("o1"), gs, 1.0) + 5
    assert check_scenario_end(gs) is None
    flag.critical_damage = [{"crit_type": "bridge_smashed"}]
    gs.update_ship(flag)
    end = check_scenario_end(gs)
    assert end and end["winner"] == 1 and end["reason"] == "admiral_killed"
    assert admiral_bonus_vp(gs, gs.get_ship_by_id("f")) == 0    # already dead: no more value


def test_dark_eldar_commanders_slain_kills_the_admiral():
    de = make_ship(id="d", player=2, is_flagship=True, hits_max=8, points_value=200,
                   special_rules=["dark_eldar", "shadowfield"])
    gs = make_gs([de, make_ship(id="x", player=1)])
    gs.scenario_mode = "kill_admiral"
    assert abs(bridge_smashed_chance(de) - 4 / 36) < 1e-9        # 9 on the DE table
    de.critical_damage = [{"crit_type": "commanders_slain"}]
    gs.update_ship(de)
    end = check_scenario_end(gs)
    assert end and end["winner"] == 1
