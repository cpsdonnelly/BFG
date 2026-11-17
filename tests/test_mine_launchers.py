"""Mine launchers (s.17) and the launch bay swap (To do 3)."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.ship_catalog import find_ship_class
from src.models import Ship
from src.booklet_options import fleet_option_errors, MINE_SWAP

MINES = {"name": "Port Mine Launchers", "weapon_type": "mine_launcher", "strength": 2,
         "range_cm": 0, "arcs": ["left"], "mine_speed": 10}


def test_swap_replaces_every_bay_at_five_points_a_bay():
    e = find_ship_class("Dictator Cruiser")
    d = e.to_ship_dict("D", 1, upgrades=[MINE_SWAP])
    kinds = [w["weapon_type"] for w in d["weapons"]]
    assert "launch_bay" not in kinds and kinds.count("mine_launcher") == 2
    assert d["points_value"] == e.points_cost + 20
    # Space Marine cruisers, Chaos heavy cruisers, Tau cruisers; not battleships
    assert any(u.name == MINE_SWAP for u in find_ship_class("Strike Cruiser").upgrades_available)
    assert any(u.name == MINE_SWAP for u in find_ship_class("Styx Heavy Cruiser").upgrades_available)
    assert not any(u.name == MINE_SWAP for u in find_ship_class("Emperor Battleship")
                   .upgrades_available)
    # up to two ships in the fleet
    rows = [(e, [MINE_SWAP])] * 3
    assert fleet_option_errors(rows)
    assert not fleet_option_errors(rows[:2])


def test_bastion_gains_mines_as_a_third_mode():
    e = find_ship_class("Bastion Commerce Vessel")
    s = Ship.from_dict(e.to_ship_dict("B", 1, upgrades=[MINE_SWAP]))
    assert {"launch_bay", "torpedo", "mine_launcher"} <= {w["weapon_type"] for w in s.weapons}
    s.mark_launched("mines")
    assert not (s.ordnance_loaded_mines or s.ordnance_loaded_craft or s.ordnance_loaded_torps)


def test_lay_mines_one_per_launcher_halved_when_crippled():
    from src.ordnance import lay_mines
    s = make_ship(id="m", player=1, weapons=[dict(MINES)])
    gs = make_gs([s, make_ship(id="e", player=2, x=40.0)])
    assert len(lay_mines(gs.get_ship_by_id("m"), MINES, gs)) == 2
    assert not gs.get_ship_by_id("m").ordnance_loaded_mines
    assert lay_mines(gs.get_ship_by_id("m"), MINES, gs) == []      # unloaded
    c = make_ship(id="c", player=1, hits_max=8, hits_remaining=3,
                  weapons=[dict(MINES, strength=3)])
    gs2 = make_gs([c])
    assert len(lay_mines(gs2.get_ship_by_id("c"), dict(MINES, strength=3), gs2)) == 2


def test_launcher_crit_sets_off_mines():
    from src.combat import mine_launcher_crit
    s = make_ship(id="m", player=1, hits_max=8, hits_remaining=8, weapons=[dict(MINES)])
    gs = make_gs([s])
    dice = DiceStub([2])
    assert not mine_launcher_crit(s, "port_armament", dice, gs)
    assert s.hits_remaining == 6 and dice._idx == 1
    assert not mine_launcher_crit(s, "starboard_armament", DiceStub([]), gs)
    assert s.hits_remaining == 6


def test_ai_lays_mines_when_an_enemy_is_in_reach():
    from src.ai_player import AIPlayer
    from src.turn_controller import TurnController
    s = make_ship(id="m", player=1, weapons=[dict(MINES)])
    far = make_ship(id="e", player=2, x=150.0, y=0.0)
    gs = make_gs([s, far])
    ai = AIPlayer(1, TurnController(gs, DiceStub([])), gs, DiceStub([]))
    ai._launch_ship_ordnance(gs.get_ship_by_id("m"))
    assert not gs.ordnance
    near = make_ship(id="e", player=2, x=40.0, y=0.0)
    gs = make_gs([make_ship(id="m", player=1, weapons=[dict(MINES)]), near])
    ai = AIPlayer(1, TurnController(gs, DiceStub([])), gs, DiceStub([]))
    ai._launch_ship_ordnance(gs.get_ship_by_id("m"))
    assert len(gs.ordnance) == 2


def test_light_cruisers_take_mines_only_in_a_cruisers_category():
    """Update 58 / sign-off answer 49: a light cruiser counts as a cruiser when
    its list places it in the Cruisers category."""
    from src.fleet_lists import fleet_list_errors
    defiant = find_ship_class("Defiant Light Cruiser")
    assert any(u.name == MINE_SWAP for u in defiant.upgrades_available)
    ok = [{"entry": defiant, "upgrades": [MINE_SWAP], "list": "navy_armageddon"}]
    assert not [e for e in fleet_list_errors("navy_armageddon", ok, 500)
                if "mine launchers" in e]
    mech = find_ship_class("Mechanicus Defiant Light Cruiser")
    bad = [{"entry": mech, "upgrades": [MINE_SWAP], "list": "navy_bakka"}]
    assert [e for e in fleet_list_errors("navy_bakka", bad, 500) if "mine launchers" in e]
    # the Eldar hybrid option (update 58): Corsair cruisers
    assert any(u.name == MINE_SWAP for u in find_ship_class("Eclipse Class Cruiser")
               .upgrades_available)
