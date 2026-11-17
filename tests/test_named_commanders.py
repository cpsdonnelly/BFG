"""Named commanders (To do 4): Rath, Abaddon, Kor'O'Mesme."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.ship_catalog import find_ship_class
from src.fleet_lists import option_allowed


def test_options_and_gating():
    emp = find_ship_class("Emperor Battleship").to_ship_dict(
        "E", 1, upgrades=["Lord Admiral Rath (Ld 10)"])
    assert emp["leadership"] == 10 and emp["rerolls_remaining"] == 2
    assert option_allowed("Lord Admiral Rath (Ld 10)", ["navy_bakka"])
    assert not option_allowed("Lord Admiral Rath (Ld 10)", ["navy_gothic"])
    d = find_ship_class("Despoiler Battleship").to_ship_dict(
        "D", 1, upgrades=["Warmaster Abaddon (Ld 10)"])
    assert d["leadership"] == 10 and "csm_crew" in d["special_rules"]
    assert option_allowed("Warmaster Abaddon (Ld 10)", ["chaos_black_crusade"])
    assert not option_allowed("Warmaster Abaddon (Ld 10)", ["chaos_incursion"])
    t = find_ship_class("Custodian Battleship").to_ship_dict("C", 1, upgrades=["Kor'O'Mesme (Ld 9)"])
    assert t["leadership"] == 9 and t["rerolls_remaining"] == 2


def test_abaddon_rerolls_reset_each_turn_and_retinue_doubles_troops(tmp_path):
    from src.turn_controller import TurnController
    from src.boarding import troop_rating
    ab = make_ship(id="a", player=1, hits_max=12, hits_remaining=12, is_flagship=True,
                   rerolls_remaining=0, special_rules=["abaddon", "doubles_troops"])
    gs = make_gs([ab])
    tc = TurnController(gs, DiceStub([]), save_dir=str(tmp_path))
    gs.active_player = 1
    tc.begin_phase("movement")
    assert gs.get_ship_by_id("a").rerolls_remaining == 1
    assert troop_rating(gs.get_ship_by_id("a")) == 24


def test_rath_inspires_his_boarding_defence():
    from src.boarding import resolve_boarding
    att = make_ship(id="x", player=2, hits_max=8)
    rath = make_ship(id="r", player=1, hits_max=8, turrets=0, special_rules=["inspiring_presence"])
    gs = make_gs([att, rath])
    r = resolve_boarding([gs.get_ship_by_id("x")], gs.get_ship_by_id("r"),
                         DiceStub([4, 3] + [1] * 10), gs)
    assert r["winner"] == "draw"           # 4 v 3 + 1
