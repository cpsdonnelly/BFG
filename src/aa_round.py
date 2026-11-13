"""Alternate activation (AA) round and phase scheduling (CLAUDE.md To do 13;
docs/AA_ORDER_SYSTEMS_NOTES.md is the source, docs/AA_ACTIVATION_NOTES.md the
framework). Pure logic, no Tk: which side (and, in System 1, which unit)
activates next in a phase, for all three order systems, built on the core in
`activation.py`. The turn controller and UI wiring come on top of this.

Open framework items stay settings (`AARoundConfig`), never decided here:
the phase order (the working round puts Shooting before Movement; the notes
leave it open), the ordnance phase new launches happen in, and the end-phase
cadence."""
from dataclasses import dataclass, field
import random
from typing import Callable, Dict, List, Optional, Tuple

from .activation import AAConfig, Bag, Unit, band, edge, fixed_order, units

# The working round (AA notes, "Discussion summary"): Command, Ordnance A,
# Shooting, Movement, Ordnance B, End
ROUND_SHOOT_FIRST = ("command", "ordnance_a", "shooting", "movement", "ordnance_b", "end")
ROUND_MOVE_FIRST = ("command", "ordnance_a", "movement", "shooting", "ordnance_b", "end")
ACTIVATION_PHASES = ("shooting", "movement")      # units activate one at a time here


@dataclass
class AARoundConfig:
    """Settings for the open items (owner: make them configurable)."""
    activation: AAConfig = field(default_factory=AAConfig)
    phase_order: str = "shoot_first"          # or "move_first" (open)
    launch_phase: str = "ordnance_b"          # where new launches happen (open)
    first_turn_moves: int = 1                 # ordnance: 1 move on its first turn...
    later_moves: int = 2                      # ...then 2 (Ciaran's rule)
    brace_in_command_phase: bool = True       # Brace is a command-phase order

    def round_phases(self) -> Tuple[str, ...]:
        return ROUND_MOVE_FIRST if self.phase_order == "move_first" else ROUND_SHOOT_FIRST


def ordnance_moves(launched_round: int, this_round: int, cfg: AARoundConfig = None) -> int:
    """Moves a marker makes this round: `first_turn_moves` on its first round
    on the board (whatever brought it there), `later_moves` afterwards. Split
    over the round's two ordnance phases by the caller."""
    cfg = cfg or AARoundConfig()
    return cfg.first_turn_moves if this_round <= launched_round else cfg.later_moves


class EdgeTracker:
    """The edge holder and gap, recomputed by the configured trigger
    (`start_only`, `on_unit_destroyed`, `abfg_turn_start`)."""

    def __init__(self, gs, cfg: AAConfig = None):
        self.cfg = cfg or AAConfig()
        self.holder, self.gap = edge(gs, self.cfg)
        self._units_seen = self._unit_count(gs)

    @staticmethod
    def _unit_count(gs) -> int:
        return len(units(gs, 1)) + len(units(gs, 2))

    def turn_start(self, gs) -> None:
        if self.cfg.recompute == "abfg_turn_start":
            self.holder, self.gap = edge(gs, self.cfg)

    def unit_destroyed(self, gs) -> None:
        if self.cfg.recompute == "on_unit_destroyed":
            n = self._unit_count(gs)
            if n != self._units_seen:
                self._units_seen = n
                self.holder, self.gap = edge(gs, self.cfg)


class PhaseScheduler:
    """One activation phase (shooting or movement). Call `next()` for who acts:
    (player, unit key) in System 1 (the unit is fixed), (player, None) in the
    bag systems (the player picks one of its units not yet activated), or None
    when the phase is over. Report each activation with `activated(player,
    key)`; in a bag system a side may instead `decline()` a draw when passing
    is allowed (`can_decline`).

    eligible: {player: [Unit]} that can activate this phase.
    choose_first: System 3 with the choice: f(edge holder) -> the side that
      takes the first activation (asked at the start of every phase).
    """

    def __init__(self, phase: str, eligible: Dict[int, List[Unit]], tracker: EdgeTracker,
                 cfg: AARoundConfig = None, rng: random.Random = None,
                 choose_first: Optional[Callable[[int], int]] = None,
                 admiral_ld: Dict[int, int] = None, rating: Dict[int, int] = None):
        self.phase = phase
        self.cfg = cfg or AARoundConfig()
        self.rng = rng or random.Random()
        self.mode = self.cfg.activation.order_mode
        self.eligible = {p: list(us) for p, us in eligible.items()}
        self.done: Dict[int, set] = {p: set() for p in self.eligible}
        self._pending: Optional[int] = None         # side owed an activation
        self._last_draw: Optional[int] = None
        self.log: List[str] = []
        if self.mode == "fixed_initiative":
            allu = [u for us in self.eligible.values() for u in us]
            self.order = fixed_order(allu, phase, admiral_ld, rating, self.rng,
                                     abfg=self.cfg.activation.recompute == "abfg_turn_start")
            self.bag = None
            return
        n_units = {p: len(us) for p, us in self.eligible.items()}
        extra = {}
        first = None
        if self.mode == "bag_adjusted" and tracker.holder is not None:
            holder = tracker.holder
            choice, k = band(tracker.gap, n_units.get(holder, 0), self.cfg.activation)
            if k:
                extra[holder] = k
            if choice:
                first = choose_first(holder) if choose_first else holder
        self.bag = Bag(n_units, extra, self.cfg.activation.allow_pass, self.rng)
        if first is not None and n_units.get(first, 0) > 0:
            self.bag.take_first(first)          # spends one of its dice (the notes)
            self._pending = first
            self.log.append(f"player {first} takes the first activation (edge choice)")

    def remaining(self, player: int) -> List[Unit]:
        return [u for u in self.eligible.get(player, []) if u.key not in self.done[player]]

    def next(self) -> Optional[Tuple[int, Optional[str]]]:
        if self.mode == "fixed_initiative":
            for u in self.order:
                if u.key not in self.done[u.player]:
                    return u.player, u.key
            return None
        if self._pending is not None:
            return self._pending, None
        while not self.bag.empty():
            p = self.bag.draw()
            self._last_draw = p
            if self.bag.activate(p):
                self._pending = p
                return p, None
            # a side with every unit done: its die does nothing
        return None

    def can_decline(self, player: int) -> bool:
        """Passing (`allow_pass`): decline this draw while the side still has
        more dice in the bag than units left (counting the drawn die)."""
        return (self.bag is not None and self._pending == player and self._last_draw == player
                and self.bag.allow_pass and self.bag.dice[player] + 1 > self.bag.left[player] + 1)

    def decline(self, player: int) -> None:
        if not self.can_decline(player):
            raise ValueError("this draw can't be declined")
        self.bag.left[player] += 1                  # the unit stays to act later
        self._pending = None
        self.log.append(f"player {player} passes")

    def activated(self, player: int, key: str) -> None:
        if key in self.done[player]:
            raise ValueError(f"unit {key} has already activated this phase")
        self.done[player].add(key)
        if self.mode != "fixed_initiative":
            if self._pending != player:
                raise ValueError(f"player {player} isn't the side to activate")
            self._pending = None
        self.log.append(f"player {player} activates {key}")

    def finished(self) -> bool:
        return all(not self.remaining(p) for p in self.eligible)


def phase_units(gs, player: int, phase: str, cfg: AARoundConfig = None) -> List[Unit]:
    """The units that can activate in `phase`: every unit in movement; in
    shooting, units with at least one ship that has a battery, lance or nova
    cannon (a unit with nothing to fire gets no die)."""
    cfg = cfg or AARoundConfig()
    us = units(gs, player, cfg.activation)
    if phase != "shooting":
        return us
    guns = ("battery", "lance", "nova_cannon")
    out = []
    for u in us:
        ships = [gs.get_ship_by_id(i) for i in u.ship_ids]
        if any(s is not None and any(w.get("weapon_type") in guns for w in s.weapons)
               for s in ships):
            out.append(u)
    return out
