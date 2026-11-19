"""Deployment (owner report): ships face the enemy's zone by default, a
placed group can be taken back, and a placed ship can be turned."""
from tests.conftest import make_ship, make_gs
from src.deployment import (deployment_state, auto_place, facing_enemy, placement_heading)


def _gs():
    ships = [make_ship(id=f"a{i}", player=1) for i in range(2)] + \
        [make_ship(id=f"b{i}", player=2) for i in range(2)]
    return make_gs(ships)


def test_default_heading_faces_the_enemy_zone():
    gs = _gs()
    st = deployment_state(gs)
    z1, z2 = st.zones[1], st.zones[2]
    x, y = (z1.x_min + z1.x_max) / 2, (z1.y_min + z1.y_max) / 2
    h = facing_enemy(st, 1, x, y)
    import math
    cx, cy = (z2.x_min + z2.x_max) / 2, (z2.y_min + z2.y_max) / 2
    assert abs(((math.degrees(math.atan2(cy - y, cx - x)) - h + 180) % 360) - 180) <= 2.5
    assert placement_heading(gs, st, 1, x, y) == h
    auto_place(gs, st)
    for s in gs.get_ships():
        assert s.heading == facing_enemy(st, s.player, s.x, s.y)


def test_undo_group_and_rotate_placed():
    gs = _gs()
    st = deployment_state(gs)
    auto_place(gs, st)
    assert st.is_complete()
    last = st.undo_group()
    assert last and not st.is_complete() and all(s not in st.placed_ships for s in last)
    first = st.placed_ships[0]
    h = first.heading
    assert st.rotate_placed(first.id, 45) is first and first.heading == (h + 45) % 360
