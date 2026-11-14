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
        from .scenarios import turn_start as _scenario_turn_start
        _scenario_turn_start(self.gs, self.tc.dice)
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
        pending = (self.gs.aa_state or {}).get("pending_rams", [])
        self.gs.aa_state = {"round": self.round, "phase": ph, "pending_rams": pending}
        for sd in self.gs.ships:
            sd["turrets_used_vs"] = ""            # s.28: the split lasts one phase
        self.scheduler = None
        if ph == "shooting":
            from .planet_scenarios import shooting_start as _assault_start
            for p in (1, 2):
                _assault_start(self.gs, p, getattr(self.gs, "assault_hook", None))
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

    def force_first(self, requests: Dict[int, str], dice) -> Optional[int]:
        """System 1 forcing (`allow_forcing`): at the start of the shooting or
        movement phase each requesting player spends a re-roll to make one
        ship (friendly or enemy) activate first. Both forcing: a dice-off,
        2D6 + the highest Ld in each fleet, re-rolled on a tie. Returns the
        winning player (None if nobody forced)."""
        if not requests or self.scheduler is None or self.scheduler.mode != "fixed_initiative":
            return None
        paid = {p: k for p, k in requests.items() if self.tc.use_fleet_reroll(p)}
        if not paid:
            return None
        winner = next(iter(paid))
        if len(paid) == 2:
            best = {p: max((s.leadership for s in self.gs.get_ships()
                            if s.player == p and not s.is_destroyed), default=0)
                    for p in paid}
            while True:
                r = {p: dice.roll_2d6(f"Player {p} forcing dice-off (2D6 + Ld {best[p]})")
                     + best[p] for p in paid}
                if r[1] != r[2]:
                    winner = 1 if r[1] > r[2] else 2
                    break
        self.scheduler.force(paid[winner])
        self.gs.add_log(f"[AA] player {winner} forces {paid[winner]} to activate first")
        return winner

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


def lock_boarding(gs, boarder_id: str, target_id: str) -> None:
    """AA (the AA notes, from ABFG): a boarding action locks both ships the
    instant it is declared: neither moves, fires nor launches for the rest of
    the round, and it resolves in the end phase (as IGOUGO's does). In IGOUGO
    only the boarder is marked (s.32); the target's own turn comes later."""
    if getattr(gs, "turn_system", "igougo") != "aa":
        return
    t = gs.get_ship_by_id(target_id)
    if t is not None:
        t.aa_locked = True
        gs.update_ship(t)


def is_locked(ship) -> bool:
    """A ship that can't act this AA round: it declared a boarding action or
    is the target of one (or is still grappled from a drawn one)."""
    return bool(ship.has_boarded or ship.is_grappled or getattr(ship, "aa_locked", False))


def defer_ram(gs, rammer_id: str, target_id: str) -> bool:
    """AA (the AA notes, from ABFG): a ram that connects locks both ships the
    instant it happens (no further move, fire or launch this round) and is
    resolved in the end phase. Returns True when deferred (AA), False in
    IGOUGO, where the caller resolves it at once (s.12)."""
    if getattr(gs, "turn_system", "igougo") != "aa":
        return False
    st = dict(gs.aa_state or {})
    st["pending_rams"] = list(st.get("pending_rams", [])) + [[rammer_id, target_id]]
    gs.aa_state = st
    for sid in (rammer_id, target_id):
        s = gs.get_ship_by_id(sid)
        if s is not None:
            s.aa_locked = True
            gs.update_ship(s)
    gs.add_log("[AA] the ram resolves in the end phase; both ships are locked")
    return True


def resolve_pending_rams(gs, dice, on_hit=None) -> list:
    """The AA end phase: resolve every deferred ram (combat.resolve_ram), in the
    order declared; `on_hit(ship)` after each (destruction checks)."""
    from .combat import resolve_ram
    out = []
    st = dict(gs.aa_state or {})
    for rid, tid in st.get("pending_rams", []):
        r, t = gs.get_ship_by_id(rid), gs.get_ship_by_id(tid)
        if r is None or t is None or r.is_destroyed or t.is_destroyed:
            continue
        gs.add_log(f"[AA] {r.name} rams {t.name} (end phase)")
        out.append(resolve_ram(r, t, dice, gs))
        if on_hit is not None:
            for sid in (tid, rid):
                s = gs.get_ship_by_id(sid)
                if s is not None:
                    on_hit(s)
    st["pending_rams"] = []
    gs.aa_state = st
    return out
