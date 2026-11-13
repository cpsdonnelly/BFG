"""Alternate activation (AA) turn driver (CLAUDE.md To do 13), on top of the
IGOUGO TurnController: a round is Command, Ordnance A, Shooting, Movement,
Ordnance B, End (the phase order is a setting, `AARoundConfig.phase_order`),
both fleets in every phase, units activating one at a time in shooting and
movement by the chosen order system (`aa_round.PhaseScheduler`). Pure logic,
no Tk; the UI and the AI drive it through:

    aa = AATurn(tc)               # reads gs.aa_settings
    aa.start_game()
    while not over:
        ph = aa.phase                       # "command", "shooting", ...
        if ph in ACTIVATION_PHASES:
            while (nxt := aa.next_activation()) is not None:
                player, unit_key = nxt       # unit_key None: the player picks
                ... activate a unit (gs.active_player is set to player) ...
                aa.activated(player, key)
        else:
            ... both players' command orders / ordnance / end phase ...
        aa.advance()

The booklet stays IGOUGO: none of this is a booklet rule."""
import random
from typing import Callable, Dict, Optional, Tuple

from .activation import AAConfig
from .aa_round import (AARoundConfig, ACTIVATION_PHASES, EdgeTracker, PhaseScheduler,
                       ordnance_moves, phase_units)


def config_from(gs) -> AARoundConfig:
    """AARoundConfig from gs.aa_settings (flat: the round fields plus the
    activation fields, e.g. {"order_mode": "bag", "phase_order": "move_first"})."""
    st = dict(getattr(gs, "aa_settings", None) or {})
    act_fields = AAConfig.__dataclass_fields__
    act = AAConfig(**{k: v for k, v in st.items() if k in act_fields})
    rnd = {k: v for k, v in st.items() if k in AARoundConfig.__dataclass_fields__
           and k != "activation"}
    return AARoundConfig(activation=act, **rnd)


class AATurn:
    def __init__(self, tc, cfg: AARoundConfig = None, rng: random.Random = None,
                 choose_first: Optional[Callable[[int, str], int]] = None):
        """choose_first(edge holder, phase) -> the side taking the phase's
        first activation (System 3's choice); default: the edge holder."""
        self.tc = tc
        self.gs = tc.gs
        self.cfg = cfg or config_from(self.gs)
        self.rng = rng or random.Random()
        self.choose_first = choose_first
        self.phases = self.cfg.round_phases()
        self.phase_index = 0
        self.tracker: Optional[EdgeTracker] = None
        self.scheduler: Optional[PhaseScheduler] = None
        self.command_check_failed: Dict[int, bool] = {1: False, 2: False}
        self.ord_moves: Dict[str, Dict[int, int]] = {}

    # --- round structure ---------------------------------------------------
    @property
    def phase(self) -> str:
        return self.phases[self.phase_index]

    @property
    def round(self) -> int:
        return self.gs.turn_number

    def start_game(self) -> None:
        self.gs.turn_system = "aa"
        self.gs.turn_number = 1
        self.tracker = EdgeTracker(self.gs, self.cfg.activation)
        self.tc.record_action("game_start", description="Game begins (alternate activation)")
        self._start_round()

    def _start_round(self) -> None:
        self.tracker.turn_start(self.gs)
        self.command_check_failed = {1: False, 2: False}
        keep = self.gs.active_player
        for p in (1, 2):
            # Orders last until the ship's next command phase (the AA notes);
            # Brace is a command-phase order too, so it goes with the rest
            self.gs.active_player = p
            self.tc._clear_previous_orders()
            if self.cfg.brace_in_command_phase:
                for sd in self.gs.ships:
                    if sd["player"] == p and sd.get("special_order") == "brace_for_impact":
                        sd["special_order"] = "none"
        self.gs.active_player = keep
        self.tc.ships_moved.clear()
        self.tc.ships_fired.clear()
        self.phase_index = 0
        self._begin_phase()

    def _begin_phase(self) -> None:
        ph = self.phase
        self.gs.current_phase = "ordnance" if ph.startswith("ordnance") else ph
        self.gs.aa_state = {"round": self.round, "phase": ph}
        for sd in self.gs.ships:
            sd["turrets_used_vs"] = ""            # s.28: the split lasts one phase
        self.scheduler = None
        if ph in ACTIVATION_PHASES:
            elig = {p: phase_units(self.gs, p, ph, self.cfg) for p in (1, 2)}
            chooser = None
            if self.choose_first is not None:
                chooser = lambda holder, ph=ph: self.choose_first(holder, ph)  # noqa: E731
            self.scheduler = PhaseScheduler(ph, elig, self.tracker, self.cfg, self.rng,
                                            choose_first=chooser)
            for line in self.scheduler.log:
                self.gs.add_log(f"[AA] {line}")
        self.tc.record_action("phase_start", description=f"=== {ph.upper()} (AA) ===")

    def advance(self) -> None:
        """To the next phase; after the end phase, the next round."""
        if self.phase_index < len(self.phases) - 1:
            self.phase_index += 1
            self._begin_phase()
            return
        self.gs.turn_number += 1
        self.tc.record_action("turn_start", description=f"=== ROUND {self.round} (AA) ===")
        self._start_round()

    # --- activations -------------------------------------------------------
    def next_activation(self) -> Optional[Tuple[int, Optional[str]]]:
        if self.scheduler is None:
            return None
        nxt = self.scheduler.next()
        if nxt is not None:
            self.gs.active_player = nxt[0]
        return nxt

    def remaining_units(self, player: int):
        return self.scheduler.remaining(player) if self.scheduler else []

    def can_decline(self, player: int) -> bool:
        return self.scheduler is not None and self.scheduler.can_decline(player)

    def decline(self, player: int) -> None:
        self.scheduler.decline(player)
        self.gs.add_log(f"[AA] player {player} passes")

    def activated(self, player: int, unit_key: str) -> None:
        self.scheduler.activated(player, unit_key)
        for s in self.gs.get_ships():
            if s.is_destroyed:
                self.tracker.unit_destroyed(self.gs)
                break

    # --- ordnance cadence ----------------------------------------------------
    def may_move_ordnance(self, marker: Dict) -> bool:
        """Ordnance moves `first_turn_moves` times in its first round on the
        board, `later_moves` afterwards, one move per ordnance phase. Moves are
        counted here by marker id (markers are rebuilt from dicts, so extra
        fields wouldn't survive)."""
        launched = marker.get("aa_round_placed", marker.get("launched_turn", self.round))
        used = self.ord_moves.get(marker.get("id"), {}).get(self.round, 0)
        return used < ordnance_moves(launched, self.round, self.cfg)

    def record_ordnance_move(self, marker: Dict, rnd: int = None) -> None:
        rnd = self.round if rnd is None else rnd
        moves = self.ord_moves.setdefault(marker.get("id"), {})
        moves[rnd] = moves.get(rnd, 0) + 1

    def launch_allowed(self) -> bool:
        """New ordnance is launched in the configured ordnance phase."""
        return self.phase == self.cfg.launch_phase



def brace_is_reactive(gs) -> bool:
    """IGOUGO: Brace for Impact is declared when attacked (s.7). AA with
    `brace_in_command_phase` (the AA notes' decision): it is a command-phase
    order only, so no reactive prompts."""
    if getattr(gs, "turn_system", "igougo") != "aa":
        return True
    return not config_from(gs).brace_in_command_phase
