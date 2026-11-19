"""Owner's Dark Eldar checklist (CLAUDE.md To do 19): Spectral Plating, the
Impaler launch pool, Voidraven salvos keeping their rules, flickerfields in the
AI's turret maths, squadron orders taken once for a squadron (s.8), the AI
keeping squadrons in coherency and combining their attack craft (s.15)."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.models import OrdnanceMarker, OrdnanceType, SpecialOrder
from src.movement import _blast_marker_damage
from src.terrain_effects import resolve_gas_dust_contact
from src.ordnance import fleet_craft_slots, fire_torpedo_bombers
from src.ai_hazards import craft_turret_p
from src.turn_controller import TurnController
from src.ai_player import AIPlayer

DE = ["dark_eldar", "shadowfield"]
IMPALER_BAY = {"name": "Prow Impaler Bay", "weapon_type": "launch_bay", "strength": 1,
               "arcs": ["front"], "craft_types": ["impaler"], "impaler_bay": True}
BAY = {"name": "Keel Launch Bays", "weapon_type": "launch_bay", "strength": 2,
       "craft_types": ["raptor", "razorwing"]}


def test_spectral_plating_no_blast_marker_or_cloud_damage():
    de = make_ship(id="d", shields_max=0, special_rules=list(DE))
    gs = make_gs([de])
    dice = DiceStub([])
    assert _blast_marker_damage(de, gs, dice) is False
    assert resolve_gas_dust_contact(de, dice, gs)["damage"] == 0
    assert dice._idx == 0                      # no damage roll at all


def test_impalers_have_their_own_launch_pool():
    gs = make_gs([make_ship(id="c", player=1, weapons=[dict(IMPALER_BAY)]),
                  make_ship(id="s", player=1, weapons=[dict(BAY)])])
    assert fleet_craft_slots(gs, 1, impaler=True) == 1
    assert fleet_craft_slots(gs, 1) == 2
    gs.add_ordnance(OrdnanceMarker(id="i", ordnance_type=OrdnanceType.ASSAULT_BOAT.value,
                                   owner_player=1, launched_by="c",
                                   special_rules=["dark_eldar", "impaler"]))
    assert fleet_craft_slots(gs, 1, impaler=True) == 0 and fleet_craft_slots(gs, 1) == 2


def test_voidraven_salvo_keeps_dark_eldar_rules():
    gs = make_gs([make_ship(id="s", player=1, special_rules=list(DE))])
    tb = OrdnanceMarker(id="v", ordnance_type=OrdnanceType.TORPEDO_BOMBER.value,
                        owner_player=1, launched_by="s", launched_turn=0, x=10.0, y=10.0,
                        special_rules=list(DE))
    gs.add_ordnance(tb)
    gs.turn_number = 2
    fire_torpedo_bombers(gs, ["v"], 0.0)
    salvo = next(o for o in gs.ordnance if "limited_fuel" in (o.get("special_rules") or []))
    assert "dark_eldar" in salvo["special_rules"]


def test_ai_turret_maths_counts_flickerfields():
    t = make_ship(turrets=2)
    assert craft_turret_p(t, []) == 0.5
    assert abs(craft_turret_p(t, ["dark_eldar"]) - 1 / 6) < 1e-9


def _squadron(n=3, spacing=5.0):
    ships = [make_ship(id=f"e{i}", player=1, ship_type="escort", squadron_id="sq",
                       x=20.0 + i * spacing, y=20.0, leadership=7, speed=30)
             for i in range(n)]
    ships.append(make_ship(id="foe", player=2, x=60.0, y=80.0))
    return ships


def test_ai_squadron_takes_one_command_check():
    gs = make_gs(_squadron())
    gs.current_phase = "movement"
    dice = DiceStub([3] * 20)
    tc = TurnController(gs, dice)
    ai = AIPlayer(1, tc, gs, dice)
    ai._choose_special_order = lambda ship: SpecialOrder.LOCK_ON.value
    before = dice._idx
    for sid in ("e0", "e1", "e2"):
        order, _ = ai._issue_order(gs.get_ship_by_id(sid))
        assert order == SpecialOrder.LOCK_ON.value
    assert dice._idx - before == 1             # one 2D6 test for the squadron
    assert all(gs.get_ship_by_id(s).special_order == SpecialOrder.LOCK_ON.value
               for s in ("e0", "e1", "e2"))


def test_ai_out_of_formation_ship_gets_no_squadron_order():
    ships = _squadron(2)
    ships.insert(2, make_ship(id="e9", player=1, ship_type="escort", squadron_id="sq",
                              x=90.0, y=20.0, leadership=7))
    gs = make_gs(ships)
    gs.current_phase = "movement"
    dice = DiceStub([3] * 20)
    ai = AIPlayer(1, TurnController(gs, dice), gs, dice)
    ai._choose_special_order = lambda ship: SpecialOrder.LOCK_ON.value
    ai._issue_order(gs.get_ship_by_id("e0"))
    order, _ = ai._issue_order(gs.get_ship_by_id("e9"))
    assert order == "" and gs.get_ship_by_id("e9").special_order in ("", "none", None)


def test_ai_coherency_term():
    gs = make_gs(_squadron(2))
    dice = DiceStub([])
    ai = AIPlayer(1, TurnController(gs, dice), gs, dice)
    e0 = gs.get_ship_by_id("e0")
    near = ai._coherency_term(e0, 25.0, 30.0)          # 11cm from e1
    far = ai._coherency_term(e0, 25.0, 60.0)
    assert near == 0.0 and far < -ai.COHERENCY_WEIGHT


def test_ai_combines_squadron_craft_into_one_wave():
    ships = [make_ship(id=f"c{i}", player=1, ship_type="escort", squadron_id="sq",
                       x=20.0 + i * 2.0, y=20.0, weapons=[dict(IMPALER_BAY)])
             for i in range(3)] + [make_ship(id="foe", player=2, x=60.0, y=80.0)]
    gs = make_gs(ships)
    gs.turn_number = 3
    for i in range(3):
        gs.add_ordnance(OrdnanceMarker(
            id=f"m{i}", ordnance_type=OrdnanceType.ASSAULT_BOAT.value, owner_player=1,
            launched_by=f"c{i}", launched_turn=3, x=20.0 + i * 2.0, y=20.0,
            craft_target_id="foe", special_rules=["dark_eldar", "impaler"]))
    dice = DiceStub([])
    ai = AIPlayer(1, TurnController(gs, dice), gs, dice)
    ai._combine_squadron_waves()
    waves = {o.get("wave_id") for o in gs.ordnance}
    assert len(waves) == 1 and "" not in waves and None not in waves
    far = max(ships[:3], key=lambda s: s.distance_to(ships[3]))
    assert all((o["x"], o["y"]) == (far.x, far.y) for o in gs.ordnance)


def test_impaler_value_beats_a_plain_raid_against_a_capital_ship():
    from src.waves import raid_squadron_value
    t = make_ship(id="t", player=2, hits_max=8, armor_prow="5+", armor_side="5+",
                  armor_rear="5+")
    gs = make_gs([t])
    plain = raid_squadron_value(t, gs, 1, ["dark_eldar"])
    imp = raid_squadron_value(t, gs, 1, ["dark_eldar", "impaler"])
    assert imp > plain


def test_impalers_get_flickerfields_and_mines_dont():
    from src.ordnance import launch_attack_craft, turret_hit_on
    from tests.conftest import make_gs_raids
    de = make_ship(id="c", player=1, special_rules=list(DE), weapons=[dict(IMPALER_BAY)])
    gs = make_gs_raids([de, make_ship(id="t", player=2, x=50.0, y=0.0)])
    imp = launch_attack_craft(gs.get_ship_by_id("c"), dict(IMPALER_BAY), "impaler", 1, gs)[0]
    t = gs.get_ship_by_id("t")
    assert "impaler" in imp.special_rules and turret_hit_on(t, imp) == 6
    mine = OrdnanceMarker(id="m", ordnance_type=OrdnanceType.MINE_FIELD.value,
                          owner_player=1, launched_by="c", special_rules=list(DE))
    assert turret_hit_on(t, mine) == 4


def test_ai_hazard_counts_flickerfields_on_incoming_impalers():
    from src.ai_hazards import marker_hits
    t = make_ship(id="t", player=2, x=0.0, y=0.0, turrets=3, armor_prow="5+",
                  armor_side="5+", armor_rear="5+")
    gs = make_gs([t])
    imp = OrdnanceMarker(id="i", ordnance_type=OrdnanceType.ASSAULT_BOAT.value,
                         owner_player=1, launched_by="c", x=10.0, y=0.0, speed=30,
                         special_rules=list(DE) + ["impaler"])
    plain = OrdnanceMarker(id="p", ordnance_type=OrdnanceType.ASSAULT_BOAT.value,
                           owner_player=1, launched_by="c", x=10.0, y=0.0, speed=30)
    h_imp, _ = marker_hits(t, imp, (0.0, 0.0), [(0.0, 0.0)], [], gs)
    h_plain, _ = marker_hits(t, plain, (0.0, 0.0), [(0.0, 0.0)], [], gs)
    # 6+ to shoot an Impaler down (3 turrets: (5/6)^3 survive) vs 4+ for a boat
    assert abs(h_imp - (5 / 6) ** 3 * (5 / 6 + 2 / 6)) < 1e-9
    assert abs(h_plain - 0.125 * 0.5) < 1e-9
