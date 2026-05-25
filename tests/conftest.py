"""Shared fixtures and helpers for BFG:XR tests."""
import pytest
from src.models import Ship, OrdnanceMarker


def make_ship(**overrides) -> Ship:
    """Construct a minimal valid Ship for testing."""
    base = dict(
        id="t1", name="Test Ship", ship_class="Test Class",
        faction="imperial_navy_gothic", player=1,
        ship_type="cruiser", base_size="small",
        x=0.0, y=0.0, heading=0.0,
        speed=20, turn_angle=45, shields_max=2,
        armor_prow="6+", armor_side="5+",
        turrets=2, hits_max=8, leadership=7,
        weapons=[], special_rules=[], upgrades=[],
        critical_damage=[],
    )
    base.update(overrides)
    return Ship(**base)


def make_torp(strength: int = 6, x: float = 10.0, y: float = 0.0,
              heading: float = 180.0) -> OrdnanceMarker:
    """Construct a minimal torpedo marker for testing."""
    return OrdnanceMarker(
        id="torp1",
        ordnance_type="torpedo_standard",
        owner_player=1,
        launched_by="t1",
        x=x, y=y, heading=heading,
        strength=strength,
        speed=30.0,
    )


class DiceStub:
    """Deterministic dice replacement for tests.

    Usage: DiceStub([4, 5, 6]) returns those values in sequence from roll_d6.
    Wraps around if exhausted.
    """
    def __init__(self, results: list):
        self._results = results
        self._idx = 0

    def roll_d6(self, count: int, label: str = "") -> list:
        out = []
        for _ in range(count):
            out.append(self._results[self._idx % len(self._results)])
            self._idx += 1
        return out

    def roll_nd6(self, count: int, label: str = "") -> list:
        return self.roll_d6(count, label)


@pytest.fixture
def ship():
    return make_ship()
