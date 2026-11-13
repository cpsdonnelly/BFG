"""Alternate activation (To do 13) in the game window: a GamePanel mixin that
walks `aa_turn.AATurn` through each round. AI players act on their own; a
human player acts with the usual buttons and presses "End Phase" to finish the
current step (their command-phase orders, an activation, their launches, the
end phase). Optional, outside the booklet (`GameState.turn_system == "aa"`).

First form: every AI activation uses the normal AI's per-unit methods (the
expert's search isn't run per unit yet); a human activation is the ship or
squadron they moved or fired with, the first unit left if they did nothing."""
from .aa_turn import AATurn
from .aa_round import ACTIVATION_PHASES


class AAPanelMixin:
    aa = None

    def _aa_on(self) -> bool:
        return getattr(self.ctx.gs, "turn_system", "igougo") == "aa"

    def _aa_ai(self, player: int):
        """The AI for `player` this round (kept for the round: command-phase
        orders and their All Ahead Full bonuses carry into movement)."""
        ais = self.__dict__.setdefault("_aa_ais", {})
        if player not in ais:
            from .ai_player import AIPlayer
            gs = self.ctx.gs
            diff = gs.ai_difficulty if gs.ai_difficulty != "expert" else "hard"
            ai = AIPlayer(player, self.ctx.tc, gs, self.ctx.dice, diff)
            ai.brace_fn = (lambda att, tgt, exp, grp: self.combat._brace_before_attack(
                att.id, att.name, tgt, exp, None, grp, att))
            ais[player] = ai
        return ais[player]

    def _aa_choose_first(self, holder: int, phase: str) -> int:
        if self.ctx.is_ai_controlled(holder):
            return holder if self._aa_ai(holder).aa_choose_first(phase) else 3 - holder
        from tkinter import messagebox
        first = messagebox.askyesno(
            "Initiative", f"You hold the initiative edge. Take the first activation of the "
                          f"{phase} phase? (No: the enemy goes first)")
        return holder if first else 3 - holder

    def _aa_begin(self) -> None:
        """After deployment and the first-turn roll-off: start the AA game."""
        self.aa = AATurn(self.ctx.tc, choose_first=self._aa_choose_first)
        self.ordnance.aa_turn = self.aa
        self.aa.start_game()
        self._aa_ais = {}
        self._aa_waiting = None
        self._aa_done = set()
        self._aa_phase_started = False
        self.ctx.log("=== GAME START (alternate activation) ===")
        self._aa_after(300)

    def _aa_after(self, ms: int) -> None:
        epoch = self._ai_epoch
        self.root.after(ms, lambda: self._aa_step(epoch))

    def _aa_step(self, epoch=None) -> None:
        """Run the current AA step until a human has to act."""
        if self._game_over or (epoch is not None and epoch != self._ai_epoch):
            return
        gs = self.ctx.gs
        ph = self.aa.phase
        self._update_phase_display()
        if ph == "command":
            for p in (1, 2):
                if self._aa_waiting == ("command", p) or ("command", p) in self._aa_done:
                    continue
                gs.active_player = p
                if self.ctx.is_ai_controlled(p):
                    with self._auto_dice():
                        self._aa_ai(p).aa_command_phase()
                    self._aa_done.add(("command", p))
                else:
                    return self._aa_wait(("command", p), "declare special orders, then End Phase")
            return self._aa_next_phase()
        if ph.startswith("ordnance"):
            launch = self.aa.launch_allowed()
            for p in (gs.first_player, 3 - gs.first_player):
                if (ph, p) in self._aa_done:
                    continue
                gs.active_player = p
                if self.ctx.is_ai_controlled(p):
                    ai = self._aa_ai(p)
                    ai.aa_no_launch = not launch
                    with self._auto_dice():
                        ai.run_ordnance_phase()
                    ai.aa_no_launch = False
                    self._aa_done.add((ph, p))
                elif launch:
                    return self._aa_wait((ph, p), "launch ordnance, then End Phase")
                else:
                    self._aa_done.add((ph, p))
            gs.active_player = gs.first_player
            with self._auto_dice_if(self.ctx.is_ai_controlled(gs.first_player)):
                self.ordnance._resolve_ordnance_movement()
            for i, o in enumerate(gs.ordnance):
                gs.ordnance[i] = {**o, "moved_this_phase": False}
            return self._aa_next_phase()
        if ph in ACTIVATION_PHASES:
            if self._aa_waiting is None and not self._aa_phase_started:
                for p in (1, 2):
                    if self.ctx.is_ai_controlled(p):
                        self._aa_ai(p).aa_phase_start(ph)
                self._aa_phase_started = True
                self._aa_offer_forcing(ph)
            nxt = self.aa.next_activation()
            if nxt is None:
                return self._aa_next_phase()
            p, key = nxt
            if self.ctx.is_ai_controlled(p):
                ai = self._aa_ai(p)
                if (key is None and self.aa.can_decline(p)
                        and ai.aa_decline(ph, len(self.aa.remaining_units(3 - p)))):
                    self.aa.decline(p)
                    return self._aa_after(100)
                units = self.aa.remaining_units(p)
                unit = next((u for u in units if u.key == key), None) if key else \
                    ai.aa_pick_unit(ph, units)
                with self._auto_dice():
                    if ph == "shooting":
                        ai.aa_shoot_unit(unit.ship_ids)
                    else:
                        ai.aa_move_unit(unit.ship_ids)
                        self.ordnance._resolve_moving_ship_contacts()
                self.aa.activated(p, unit.key)
                self.ctx.board.redraw()
                if self._check_game_over():
                    return
                return self._aa_after(150)
            self._aa_acted_before = (set(self.ctx.tc.ships_moved), set(self.ctx.tc.ships_fired))
            self._aa_named = key
            return self._aa_wait((ph, p), f"activate one unit ({ph}), then End Phase")
        if ph == "end":
            ai = self._aa_ai(1 if self.ctx.is_ai_controlled(1) else 2)
            with self._auto_dice_if(all(self.ctx.is_ai_controlled(p) for p in (1, 2))):
                self._resolve_end_phase_auto(ai)
            for p in (1, 2):
                gs.active_player = p
                self.ctx.tc.end_phase()
            return self._aa_next_phase()

    def _aa_offer_forcing(self, ph: str) -> None:
        """System 1 forcing (`allow_forcing`): each human with a re-roll may
        make one ship activate first. The AI doesn't force yet (judgement:
        not valued)."""
        cfg = self.aa.cfg.activation
        if cfg.order_mode != "fixed_initiative" or not cfg.allow_forcing:
            return
        from tkinter import messagebox
        requests = {}
        for p in (1, 2):
            if self.ctx.is_ai_controlled(p) or self.ctx.tc.get_fleet_rerolls(p) <= 0:
                continue
            if not messagebox.askyesno("Force an activation",
                                       f"Player {p}: spend a re-roll to make one ship "
                                       f"(yours or the enemy's) activate first this {ph} phase?"):
                continue
            ships = [s for s in self.ctx.gs.get_ships() if not s.is_destroyed
                     and not s.is_disengaged]
            pick = self.ctx.pick_ship(ships, "Ship to activate first")
            if pick is not None:
                unit = next((u for us in self.aa.scheduler.eligible.values() for u in us
                             if pick.id in u.ship_ids), None)
                if unit is not None:
                    requests[p] = unit.key
        if requests:
            self.aa.force_first(requests, self.ctx.dice)

    def _aa_wait(self, what, text: str) -> None:
        self._aa_waiting = what
        self.ctx.gs.active_player = what[1]
        name = self.ctx.gs.player1_name if what[1] == 1 else self.ctx.gs.player2_name
        self.ctx.log(f"[AA] {name}: {text}")
        self._update_phase_display()
        self.ctx.board.redraw()

    def _aa_end_button(self) -> None:
        """'End Phase' during an AA game: the waiting human's step is done."""
        if self._aa_waiting is None:
            return
        ph, p = self._aa_waiting
        self._aa_waiting = None
        if ph in ACTIVATION_PHASES:
            moved0, fired0 = self._aa_acted_before
            tc = self.ctx.tc
            acted = (set(tc.ships_moved) - moved0) | (set(tc.ships_fired) - fired0)
            units = self.aa.remaining_units(p)
            unit = next((u for u in units if set(u.ship_ids) & acted), None)
            if self._aa_named:
                unit = next((u for u in units if u.key == self._aa_named), unit)
            if unit is None:
                if self.aa.can_decline(p):
                    self.aa.decline(p)
                    return self._aa_after(100)
                unit = units[0]
            self.aa.activated(p, unit.key)
        else:
            self._aa_done.add((ph, p))
        self._aa_after(100)

    def _aa_next_phase(self) -> None:
        self.aa.advance()
        self._aa_done = set()
        self._aa_phase_started = False
        if self.aa.phase == "command":
            self._aa_ais = {}
            if self._check_game_over():
                self._update_phase_display()
                return
        self.ctx.log(f"--- {self.aa.phase.upper()} (AA, round {self.aa.round}) ---")
        self._aa_after(200)

    _aa_done: set = set()
    _aa_phase_started = False
    _aa_waiting = None
    _aa_named = None
    _aa_acted_before = (set(), set())
