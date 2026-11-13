"""Ork kustom upgrades, Nobz and clans (To do 4)."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.ship_catalog import find_ship_class
from src.booklet_options import ship_option_errors


def test_kustoms_need_a_boss_or_nob_and_count_by_title():
    kk = find_ship_class("Kill Kroozer")
    names = [u.name for u in kk.upgrades_available]
    assert "Kustom: Extra Turrets" in names and "Ork Nob" in names
    assert ship_option_errors(kk, ["Kustom: Extra Turrets"])                 # no Boss
    assert not ship_option_errors(kk, ["Ork Nob", "Kustom: Extra Turrets"])
    assert ship_option_errors(kk, ["Ork Nob", "Kustom: Extra Turrets", "Kustom: Mad Meks"])
    assert not ship_option_errors(kk, ["Ork Warboss", "Boss title: Big Boss",
                                       "Kustom: Extra Turrets", "Kustom: Mad Meks"])
    d = kk.to_ship_dict("K", 1, upgrades=["Ork Nob", "Kustom: Extra Turrets"])
    assert d["turrets"] == min(6, kk.turrets + 2)


def test_kustom_and_clan_effects():
    from src.hit_and_run import teleport_range
    from src.movement import aaf_bonus_dice
    from src.end_phase import resolve_damage_control
    s = make_ship(special_rules=["soopa_tellyporta", "ork_crew", "ere_we_go", "clan:evil_sunz"])
    assert teleport_range(s) == 30 and aaf_bonus_dice(s) == 5
    mek = make_ship(id="m", hits_max=8, hits_remaining=2, special_rules=["mad_meks"],
                    critical_damage=[{"crit_type": "fire", "description": "Fire!",
                                      "repairable": True}])
    gs = make_gs([mek])
    resolve_damage_control(gs.get_ship_by_id("m"), DiceStub([4, 1]), gs)
    assert not gs.get_ship_by_id("m").critical_damage                      # 4+ repairs
    from src.boarding import troop_rating
    goff = make_ship(hits_remaining=8, turrets=3, special_rules=["clan:goffs"])
    plain = make_ship(hits_remaining=8, turrets=3)
    assert troop_rating(goff) == 11 and troop_rating(plain) == 8   # attackers: Goffs only
    assert troop_rating(goff, defending=True) == troop_rating(plain, defending=True) == 11


def test_grot_riggers_help_reload():
    from src.movement import do_command_check
    s = make_ship(leadership=6, special_rules=["grot_riggers"])
    res = do_command_check(s, "reload_ordnance", DiceStub([7]))
    assert res["passed"] and res["needed"] == 7


def test_zzapp_gunz_hit_on_5_and_overload_on_a_rolled_1():
    from src.combat import resolve_lances, weapon_fire_pool
    z = {"name": "Prow Zzapp Gunz", "weapon_type": "lance", "range_cm": 45, "strength": 5,
         "strength_dice": "D3+3", "hits_on": 5, "zzapp": True, "arcs": ["front"]}
    s = make_ship(id="o", player=1, x=0.0, y=0.0, heading=0.0, weapons=[z])
    t = make_ship(id="t", player=2, x=20.0, y=0.0)
    gs = make_gs([s, t])
    dice = DiceStub([1])                       # the D3 die shows a 1: firepower 1+3
    pool, _m, _e = weapon_fire_pool(gs.get_ship_by_id("o"), z, 0, 20.0, dice, gs)
    assert pool == 4 and len(gs.blast_markers) == 1
    weapon_fire_pool(gs.get_ship_by_id("o"), z, 0, 20.0, DiceStub([1]), gs)
    assert len(gs.blast_markers) == 1          # once a turn
    sr = resolve_lances(s, t, dict(z, strength=4), DiceStub([4, 5, 6, 3]))
    assert sr.hits == 2
