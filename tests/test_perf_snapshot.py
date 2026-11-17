"""To do 16: the fast ship copy and the read-only ships snapshot behave as the
code they replace."""
import dataclasses
import threading

from src.game_state import GameState
from src.models import Ship, ship_copy
from src.ship_catalog import find_ship_class


def _gs():
    gs = GameState()
    for i, (p, n) in enumerate(((1, "Lunar Class Cruiser"), (2, "Murder Class Cruiser"))):
        d = find_ship_class(n).to_ship_dict(n, p, ship_id=f"s{i}")
        d.update(x=10.0 + 50 * i, y=30.0)
        gs.add_ship(Ship.from_dict(d))
    return gs


def test_ship_copy_matches_dataclasses_replace():
    sh = _gs().get_ships()[0]
    a = ship_copy(sh, x=5.0, heading=90.0)
    b = dataclasses.replace(sh, x=5.0, heading=90.0)
    assert a.to_dict() == b.to_dict()
    assert sh.x != 5.0                        # the original is untouched
    # a ship missing hits_remaining takes the normal path (__post_init__)
    sh.hits_remaining = None
    assert ship_copy(sh).hits_remaining == sh.hits_max


def test_snapshot_shares_copies_inside_the_scope_only():
    gs = _gs()
    assert gs.get_ships()[0] is not gs.get_ships()[0]
    with gs.ships_snapshot():
        a, b = gs.get_ships(), gs.get_ships()
        assert a[0] is b[0] and a is not b    # same copies, a fresh list
        with gs.ships_snapshot():             # nested: shares the outer one
            assert gs.get_ships()[0] is a[0]
    assert gs.get_ships()[0] is not a[0]


def test_snapshot_dropped_by_writes():
    gs = _gs()
    with gs.ships_snapshot():
        sh = gs.get_ships()[0]
        moved = ship_copy(sh, x=99.0)
        gs.update_ship(moved)
        assert gs.get_ships()[0].x == 99.0
        gs.ships = gs.ships[:1]               # replacing the list is seen too
        assert len(gs.get_ships()) == 1


def test_snapshot_belongs_to_its_thread():
    gs = _gs()
    seen = {}
    with gs.ships_snapshot():
        mine = gs.get_ships()[0]

        def other():
            seen["same"] = gs.get_ships()[0] is mine
        t = threading.Thread(target=other)
        t.start()
        t.join()
    assert seen["same"] is False
