"""Deployment in any order, and taking back any placed group (owner report:
deployment forced a fixed order)."""
from tests.conftest import make_ship
from src.deployment import DeploymentState, DeploymentZone


def _state():
    ships = [make_ship(id=f"a{i}", player=1, name=f"A{i}") for i in range(3)]
    ships += [make_ship(id="b0", player=2, name="B0")]
    zones = [DeploymentZone(player=1, x_min=0, x_max=120, y_min=0, y_max=30),
             DeploymentZone(player=2, x_min=0, x_max=120, y_min=90, y_max=120)]
    return DeploymentState(ships[:3], ships[3:], zones)


def test_any_order_and_take_back_any_group():
    st = _state()
    third = st.groups[1][2][0].id
    assert st.select_group(2) and st.current_group()[0].id == third
    assert st.place_group([(20.0, 10.0)], [90.0])[0]
    assert st.place_group([(50.0, 10.0)], [90.0])[0]
    assert not st.select_group(0)                        # placed already
    first_placed = st.groups[1][0]
    assert st.unplace_group(1, 0) is first_placed
    assert first_placed[0] not in st.placed_ships and st.groups_remaining(1) == 2
    assert st.current_group() is first_placed and st.active_player == 1
