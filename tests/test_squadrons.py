"""Squadron rules and the organiser (owner: the AI and players form and
reorganise squadrons, never breaking the squadron rules; core s.8, XR p.58)."""
import random
from src.ship_catalog import find_ship_class
from src.fleet_model import make_fleet_row
from src.squadrons import (fleet_squadron_errors, organize_escorts, form_capital_squadrons,
                           squadron_errors)


def _rows(*names, upgrades=None):
    return [make_fleet_row(find_ship_class(n), upgrades=upgrades) for n in names]


def test_capital_squadron_sizes_and_mixing():
    cr = _rows("Lunar Class Cruiser", "Dauntless Class Light Cruiser")
    assert squadron_errors(cr, "a") == []                 # cruisers of any kind mix
    assert squadron_errors(_rows(*["Lunar Class Cruiser"] * 5), "a")       # 2-4
    assert squadron_errors(_rows("Retribution Class Battleship", "Lunar Class Cruiser"), "a")
    assert squadron_errors(_rows("Retribution Class Battleship",
                                 "Vengeance Class Grand Cruiser"), "a")   # never mixed
    assert squadron_errors(_rows(*["Retribution Class Battleship"] * 4), "a")   # 2-3


def test_never_squadroned_and_factions():
    assert squadron_errors(_rows("Charybdis Class Hive Ship", "Charybdis Class Hive Ship"), "a")
    assert squadron_errors(_rows("Lunar Class Cruiser", "Murder Class Cruiser"), "a")


def test_lone_escort_must_join_a_squadron():
    rows = _rows("Cobra Class Destroyer", "Sword Class Frigate")
    assert fleet_squadron_errors(rows)                     # two escorts, none squadroned
    assert organize_escorts(rows, rng=random.Random(1)) == []
    assert rows[0]["squadron_id"] and rows[0]["squadron_id"] == rows[1]["squadron_id"]


def test_escorts_by_class_in_2d3_squadrons():
    rows = _rows(*["Cobra Class Destroyer"] * 7, *["Sword Class Frigate"] * 3)
    assert organize_escorts(rows, rng=random.Random(4)) == []
    for sid in {r["squadron_id"] for r in rows}:
        members = [r for r in rows if r["squadron_id"] == sid]
        assert 2 <= len(members) <= 6
    assert all(r["squadron_id"] for r in rows)


def test_tyranid_escorts_keep_one_weapon_a_squadron():
    rows = (_rows(*["Kraken"] * 2, upgrades=["Weapon: Pyro-acid Battery"])
            + _rows(*["Kraken"] * 2, upgrades=["Weapon: Feeder Tendrils"]))
    organize_escorts(rows, "tyranid_hive", rng=random.Random(2))
    assert fleet_squadron_errors(rows, "tyranid_hive") == []
    for sid in {r["squadron_id"] for r in rows}:
        assert len({tuple(r["upgrades"]) for r in rows if r["squadron_id"] == sid}) == 1


def test_capital_squadrons_follow_the_rules_and_are_logged():
    rows = _rows(*["Lunar Class Cruiser"] * 3, "Dictator Class Cruiser",
                 "Dictator Class Cruiser", "Charybdis Class Hive Ship")
    lines = []
    formed = form_capital_squadrons(rows, rng=random.Random(0), chance=1.0, log=lines.append)
    assert formed and fleet_squadron_errors(rows) == []
    assert not rows[-1]["squadron_id"]                     # hive ships stay alone
    assert all(len({r["entry"].ship_class for r in g}) == 1 for g in formed)   # one role
    assert lines


def _state():
    from tests.conftest import make_ship, make_gs
    from src.deployment import deployment_state
    ships = [make_ship(id=f"c{i}", name=f"C{i}", player=1, x=0.0, y=0.0) for i in range(4)]
    ships += [make_ship(id=f"e{i}", name=f"E{i}", player=1, ship_type="escort",
                        squadron_id="sq1", x=0.0, y=0.0) for i in range(3)]
    ships.append(make_ship(id="p", player=2, x=0.0, y=0.0))
    gs = make_gs(ships)
    return gs, deployment_state(gs)


def test_any_order_keeps_the_list_order():
    _gs, st = _state()
    names = [g[0].id for g in st.groups[1]]
    assert st.select_group(3)
    after = [g[0].id for g in st.groups[1]]
    assert after[0] == names[3] and [n for n in after if n != names[3]] == \
        [n for n in names if n != names[3]]


def test_any_ship_of_a_squadron_next():
    _gs, st = _state()
    sq = next(i for i, g in enumerate(st.groups[1]) if len(g) > 1)
    st.select_group(sq)
    assert st.select_member(0, "e2") and st.current_group()[0].id == "e2"
    assert not st.select_member(1, "e2")                  # already placed


def test_capital_squadrons_regroup_only_before_deployment():
    _gs, st = _state()
    caps = [s for g in st.groups[1] for s in g if s.ship_type != "escort"]
    for s in caps[:2]:
        s.squadron_id = "csq1"
    assert st.regroup(1)
    assert any(len(g) == 2 and g[0].squadron_id == "csq1" for g in st.groups[1])


def test_ai_forms_capital_squadrons_before_deployment():
    from src.squadrons import ai_form_squadrons
    gs, _st = _state()
    gs.game_seed = 5
    lines = []
    ai_form_squadrons(gs, 1, log=lines.append, chance=1.0)
    caps = [s for s in gs.player_ships(1) if s.ship_type != "escort"]
    assert any(s.squadron_id for s in caps) and lines
    assert {s.squadron_id for s in gs.player_ships(1) if s.ship_type == "escort"} == {"sq1"}
