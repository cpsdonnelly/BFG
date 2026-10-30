"""Tests for catastrophic damage explosions and chain reactions.

Dice sequences are listed roll by roll; every value is one a real die
could show (D6 rolls 1-6, 2D6 rolls 2-12).
"""
from src.combat import resolve_catastrophic
from src.models import OrdnanceMarker
from tests.conftest import make_ship, make_gs, DiceStub


def test_warp_implosion_chain_reaction():
    exploder = make_ship(id="boom", hits_max=10, hits_remaining=0, x=0.0)
    victim = make_ship(id="victim", player=2, hits_max=8, x=10.0)
    escort = make_ship(id="escort", player=2, ship_type="escort", hits_max=1, x=5.0)
    # 26cm from the first explosion (outside its 18cm blast), 16cm from the victim
    bystander = make_ship(id="far", player=2, hits_max=8, x=26.0)
    gs = make_gs([exploder, victim, escort, bystander])
    gs.add_ordnance(OrdnanceMarker(id="near", ordnance_type="torpedo_standard",
                                   owner_player=2, launched_by="x", x=12.0, y=0.0))
    gs.add_ordnance(OrdnanceMarker(id="away", ordnance_type="torpedo_standard",
                                   owner_player=2, launched_by="x", x=100.0, y=0.0))
    rolls = (
        [12]               # boom: catastrophic 2D6 -> warp drive implosion (str 10)
        + [6, 6, 6]        # blast radius 18cm
        + [5] * 10         # 10 lance shots at the victim, all hit (4+)
        + [1] * 7          # victim: 2 shields, 8 hull; 7 crit checks, no crits
        + [12]             # victim: catastrophic -> warp drive implosion (str 8)
        + [6, 6, 6]        # blast radius 18cm
        + [5] * 8          # 8 hits on the escort: 2 shields, then destroyed
        + [5] * 8          # 8 hits on the bystander
        + [1] * 6          # bystander: 2 shields, 6 hull; 6 crit checks
    )
    dice = DiceStub(rolls)

    assert resolve_catastrophic(exploder, dice, gs) == "warp_drive_implosion"

    assert dice._idx == len(rolls)     # every roll used, none wrapped around
    v = gs.get_ship_by_id("victim")
    assert (v.status, v.hits_remaining) == ("destroyed", 0)
    assert gs.get_ship_by_id("escort").status == "destroyed"
    wrecks = [bm for bm in gs.get_blast_markers() if bm.id == "wreck_escort"]
    assert len(wrecks) == 1            # destroyed once, not resurrected and re-destroyed
    assert gs.get_ship_by_id("far").hits_remaining == 2
    assert [o["id"] for o in gs.ordnance] == ["away"]


def test_explosion_kill_can_leave_a_hulk():
    exploder = make_ship(id="boom", hits_max=4, hits_remaining=0, x=0.0)
    victim = make_ship(id="victim", player=2, hits_max=4, shields_max=0, x=10.0)
    gs = make_gs([exploder, victim])
    rolls = (
        [12]               # boom: warp drive implosion (str 4)
        + [6, 6, 6]        # blast radius 18cm
        + [5] * 4          # 4 lance hits on the victim
        + [1] * 3          # 3 crit checks before the 4th hit kills it
        + [4]              # victim: catastrophic 2D6 = 4 -> drifting hulk
    )
    dice = DiceStub(rolls)

    resolve_catastrophic(exploder, dice, gs)

    assert dice._idx == len(rolls)
    assert gs.get_ship_by_id("victim").status == "drifting_hulk"
