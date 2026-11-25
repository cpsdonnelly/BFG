"""AI deployment (To do 28): buff ships last near friends, squadrons coherent
in a random line / box, every choice from the recorded generator."""
import math
from tests.conftest import make_ship, make_gs
from src.deployment import deployment_state, COHERENCY_CM
from src.ai_deployment import ai_deploy_all, ai_deploy, buff_range


def _fleet():
    ships = [make_ship(id=f"c{i}", player=2, x=0.0, y=0.0) for i in range(3)]
    ships += [make_ship(id=f"e{i}", player=2, ship_type="escort", squadron_id="sq1",
                        x=0.0, y=0.0) for i in range(4)]
    ships.append(make_ship(id="m", player=2, ship_type="escort", x=0.0, y=0.0,
                           special_rules=["tracking_systems_10"]))
    ships += [make_ship(id=f"p{i}", player=1, x=0.0, y=0.0) for i in range(2)]
    gs = make_gs(ships)
    gs.game_seed = 7
    return gs


def test_buff_ranges():
    assert buff_range(make_ship(special_rules=["synapse:8:45"])) == 45
    assert buff_range(make_ship(special_rules=["tracking_systems_20"])) == 20
    assert buff_range(make_ship(special_rules=["fleet_defence_turrets"])) == 15
    assert buff_range(make_ship()) == 0


def test_ai_places_its_fleet_buff_ship_last_and_squadrons_coherent():
    gs = _fleet()
    state = deployment_state(gs)
    lines = []
    assert ai_deploy_all(gs, state, log=lines.append) == []
    assert state.is_complete()
    order = [s.id for s in state.placed_ships if s.player == 2]
    assert order[-1] == "m"                                   # the buff ship last
    m = gs.get_ship_by_id("m")
    friends = [gs.get_ship_by_id(i) for i in ("c0", "c1", "c2", "e0", "e1", "e2", "e3")]
    assert any(math.hypot(f.x - m.x, f.y - m.y) <= 10 for f in friends)
    esc = [gs.get_ship_by_id(f"e{i}") for i in range(4)]
    assert all(math.hypot(a.x - b.x, a.y - b.y) <= COHERENCY_CM for a in esc for b in esc)
    zone = state.zones[2]
    assert all(zone.contains(s.x, s.y) for s in esc + [m])
    assert any("squadron of 4" in ln for ln in lines) and any("places" in ln for ln in lines)


def test_same_seed_same_deployment():
    def run():
        gs = _fleet()
        ai_deploy_all(gs, deployment_state(gs))
        return [(round(s["x"], 2), round(s["y"], 2)) for s in gs.ships]
    assert run() == run()


def test_only_its_own_turn():
    gs = _fleet()
    state = deployment_state(gs)              # sequential: player 1 first
    assert ai_deploy(gs, state, 2) == [] and state.next_idx[2] == 0


def test_tyranid_hive_ships_are_buff_ships():
    """Owner: hive ships buff friendly ships (synapse): placed last, friends in reach."""
    from src.ship_catalog import find_ship_class
    assert buff_range(find_ship_class("Proteus Class Hive Ship")) == 60
    assert buff_range(find_ship_class("Charybdis Class Hive Ship")) == 45
    assert buff_range(find_ship_class("Scylla Strain Bio-Cruiser w/ Synapse Node")) == 30
