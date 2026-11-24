"""Necron Dynasty / Harvest fleet building and the systems the owner's
Necron fleet uses (Xenos p.40-51): the Shroud's refits, the Lord's vessel
upgrades, the nightmare field, bloodswarm nanoscarabs, the negative energy
veil and nebuloscope pylons."""
from tests.conftest import make_ship, make_gs, make_marker, DiceStub
from src.ship_catalog import get_ship_class
from src.combat import resolve_nightmare_field
from src.scenarios import orders_forbidden
from src.necrons import end_of_turn_nightmare, veil_hidden
from src.movement import do_command_check
from src.hit_and_run import _raid_roll_modifier

NF = {"name": "Nightmare Field", "weapon_type": "nightmare_field", "range_cm": 20,
      "strength": 1, "arcs": []}


def test_shroud_refits_combine_the_whips():
    e = get_ship_class("necrons", "Shroud Class Light Cruiser")
    assert {"negative_energy_veil", "nebuloscope_pylons"} <= set(e.special_rules)
    d = e.to_ship_dict(name="s", player=1, upgrades=[
        "Shroud refit: Khopesh Configuration", "Shroud refit: Cartouche Configuration",
        "Shroud refit: War Configuration"])
    assert d["hits_max"] == 6 and d["turrets"] == 2 and d["points_value"] == 155
    assert "negative_energy_veil" not in d["special_rules"]
    arc = next(w for w in d["weapons"] if w["name"] == "Lightning Arc")
    whips = [w for w in d["weapons"] if w.get("particle_whip")]
    assert arc["strength"] == 8 and arc["arcs"] == ["left", "right"]
    assert len(whips) == 1 and whips[0]["strength"] == 2


def _game(target_ld=7):
    nec = make_ship(id="n", player=1, x=0.0, y=0.0, special_rules=["necron", "necron_awake"],
                    weapons=[NF])
    foe = make_ship(id="f", player=2, x=0.0, y=15.0, leadership=target_ld)
    far = make_ship(id="far", player=2, x=0.0, y=60.0)
    gs = make_gs([nec, foe, far])
    gs.active_player = 1
    return gs


def test_nightmare_field_failed_test_lasts_until_after_its_next_turn():
    gs = _game()
    gs.ordnance.append(make_marker(id="b", ordnance_type="bomber", owner_player=2,
                                   x=5.0, y=5.0).to_dict())
    rolls = [4,            # the bomber within 20cm: 4+ destroyed
             5, 4]         # Ld test 9 vs Ld 7: failed
    dice = DiceStub(rolls)
    res = resolve_nightmare_field(gs.get_ship_by_id("n"), gs, dice, "f")
    assert dice._idx == len(rolls) and res["failed"] and res["ordnance_destroyed"] == 1
    f = gs.get_ship_by_id("f")
    assert f.leadership == 6 and orders_forbidden(gs, f)
    end_of_turn_nightmare(gs, 1)                       # the Necrons' own end phase
    assert orders_forbidden(gs, gs.get_ship_by_id("f"))
    end_of_turn_nightmare(gs, 2)                       # the end of its next turn
    assert not orders_forbidden(gs, gs.get_ship_by_id("f"))
    assert "error" in resolve_nightmare_field(gs.get_ship_by_id("n"), gs, DiceStub([]), "far")


def test_bloodswarm_adds_to_portal_raids():
    assert _raid_roll_modifier(["necron", "bloodswarm"], make_ship()) == 1


def test_veil_and_nebuloscope_pylons_in_command_checks():
    shroud = make_ship(id="sh", player=2, x=50.0, y=50.0, special_order="lock_on",
                       special_rules=["necron", "negative_energy_veil"])
    ship = make_ship(id="s", player=1, leadership=7)
    gs = make_gs([shroud, ship])
    # the only enemy on orders is veiled: no Enemy Contacts (7 needed, 8 rolled fails)
    assert not do_command_check(gs.get_ship_by_id("s"), "lock_on", DiceStub([8]),
                                gs=gs)["passed"]
    pylons = make_ship(id="p", player=1, special_rules=["necron", "nebuloscope_pylons"])
    enemy = make_ship(id="e", player=2, x=80.0, y=80.0, special_order="lock_on")
    gs2 = make_gs([pylons, enemy, make_ship(id="m", player=1, leadership=7,
                                            special_rules=["necron"])])
    # Enemy Contacts +1, nebuloscope +1: Ld 9 passes a 9
    assert do_command_check(gs2.get_ship_by_id("m"), "lock_on", DiceStub([9]),
                            gs=gs2)["passed"]


def test_a_conserving_veiled_shroud_is_hidden():
    s = make_ship(id="sh", player=2, ship_type="cruiser",
                  special_rules=["necron", "negative_energy_veil"])
    assert veil_hidden(s) == bool(s.is_crippled)
