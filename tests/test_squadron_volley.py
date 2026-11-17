"""Shooting by Squadrons: different aspects or ranges, squadron against
squadron (core rules s.8)."""
from tests.conftest import make_ship, make_gs, DiceStub
from src.combat import plan_squadron_volley, resolve_squadron_volley, apply_damage

BAT = {"name": "Macrobatteries", "weapon_type": "battery", "strength": 2, "range_cm": 30,
       "arcs": ["front", "left", "right", "rear"]}


def frigate(i, x, y, heading=0.0):
    return make_ship(id=f"f{i}", name=f"F{i}", player=1, ship_type="escort", x=x, y=y,
                     heading=heading, hits_max=1, shields_max=1, weapons=[dict(BAT)],
                     squadron_id="sq")


def cruiser(cid="c", x=50.0, y=50.0, **kw):
    base = dict(id=cid, name=cid, player=2, x=x, y=y, heading=0.0, hits_max=8, shields_max=0,
                armor_prow="6+", armor_side="5+")
    base.update(kw)
    return make_ship(**base)


def test_booklet_example_five_frigates_one_attack_per_armour_value():
    target = cruiser()
    front = frigate(0, 70.0, 50.0, 180.0)                 # sees it closing: prow 6+
    behind = frigate(1, 30.0, 50.0)                       # moving away: 5+
    abeam = [frigate(2 + i, 48.0 + 2 * i, 70.0, 270.0) for i in range(3)]
    contrib = [(s, s.weapons[0]) for s in [front, behind] + abeam]
    plan = plan_squadron_volley(contrib, [target], [])
    armours = sorted(tuple(sorted(set(a["armors"].values()))) for a in plan["attacks"])
    assert armours == [(5,), (6,)]                       # one attack per Armour value
    vs5 = next(a for a in plan["attacks"] if a["armors"]["c"] == 5)
    assert len(vs5["parts"]) == 2                         # abeam and moving away groups


def test_single_target_hits_applied_together():
    target = cruiser()
    gs = make_gs([target])
    front = frigate(0, 70.0, 50.0, 180.0)
    behind = frigate(1, 30.0, 50.0)
    plan = plan_squadron_volley([(front, BAT), (behind, BAT)], [target], [])
    calls = []

    def apply(ship, n):
        calls.append(n)
        return 0, False
    n_dice = [a["dice"] for a in plan["attacks"]]
    rolls = [6] * sum(n_dice)
    dice = DiceStub(rolls)
    resolve_squadron_volley(plan, [target], dice, apply, game_state=gs)
    assert dice._idx == len(rolls) and calls == [sum(n_dice)]   # one application


def test_squadron_vs_squadron_aspect_choice_limits_eligible_ships():
    # Two target cruisers: one closing on the attacker, one abeam to it
    t1 = cruiser("t1", 70.0, 50.0, heading=180.0, squadron_id="tsq")   # coming at it
    t2 = cruiser("t2", 70.0, 60.0, heading=90.0, squadron_id="tsq")    # abeam
    att = frigate(0, 50.0, 50.0)
    view_plan = plan_squadron_volley([(att, BAT)], [t1, t2], [])
    (view, present), = view_plan["views"].items()
    assert present == ["closing", "abeam"]
    assert {m.id for m in view_plan["attacks"][0]["eligible"]} == {"t1", "t2"}  # hardest
    closing = plan_squadron_volley([(att, BAT)], [t1, t2], [],
                                   aspect_choice={view: "closing"})
    assert [m.id for m in closing["attacks"][0]["eligible"]] == ["t1"]


def test_groups_resolve_separately_shields_stay_down_shifts_from_before():
    # Two groups see different target sets and resolve separately. Shields
    # knocked down by the first attack stay down for the second (owner ruling);
    # column shifts were fixed from the blast markers before the volley.
    t1 = cruiser("t1", 70.0, 50.0, squadron_id="tsq", shields_max=1)
    t2 = cruiser("t2", 70.0, 58.0, squadron_id="tsq", shields_max=1)
    gs = make_gs([t1, t2])
    near = frigate(0, 50.0, 50.0)                       # both in range
    far = dict(BAT, range_cm=21)
    far_frig = frigate(1, 50.0, 48.0)                   # only t1 within 21cm
    plan = plan_squadron_volley([(near, BAT), (far_frig, far)], [t1, t2], [])
    assert len(plan["attacks"]) == 2
    from src.geometry import current_shields
    shields_seen = []

    def apply(ship, n):
        fresh = gs.get_ship_by_id(ship.id)
        shields_seen.append((ship.id, current_shields(fresh, gs.get_blast_markers())))
        apply_damage(fresh, n, DiceStub([1] * 10), gs)
        return 0, False
    rolls = [6] * sum(a["dice"] for a in plan["attacks"])
    resolve_squadron_volley(plan, [t1, t2], DiceStub(rolls), apply, game_state=gs)
    t1_seen = [s for sid, s in shields_seen if sid == "t1"]
    assert t1_seen[0] == 1 and t1_seen[-1] == 0          # knocked down, stays down
