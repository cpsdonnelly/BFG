"""BFG:XR game flow (To do 18): the turn flow without the window.

GameFlow runs a game: the first turn, ending each phase (ordnance movement,
the end phase, the next phase and turn, game over and scenario ends), the
AI's phases and the decision hooks the engine asks through. It knows the
screen only through a few methods a subclass overrides: _update_phase_display,
_show_game_over_dialog, _show_victory_points and _disengage_dialog; it asks
players through ctx.prompt and schedules its steps with self.root.after.

GamePanel (game_panel.py) is the desktop window on top of it; HeadlessGame
(headless_game.py) runs it with no window at all.
"""
import os
from contextlib import contextmanager, nullcontext

from .models import Ship, SpecialOrder  # noqa: F401 (used by the moved flow code)
from .movement_panel import MovementPanel
from .combat_panel import CombatPanel
from .ordnance_panel import OrdnancePanel
from .end_phase_panel import EndPhasePanel
from .aa_panel import AAPanelMixin
from . import recorder


class GameFlow(AAPanelMixin):
    """The game's flow; `self.ctx` is its GameContext, `self.root` its
    scheduler (Tk's root, or headless_game's queue)."""

    def _init_flow(self, ctx, root):
        """Compose the panels on `ctx` and wire the engine's decision hooks."""
        self.ctx = ctx
        self.root = root
        tc = ctx.tc
        self.movement = MovementPanel(self.ctx)
        self.combat = CombatPanel(self.ctx)
        self.ordnance = OrdnancePanel(self.ctx)
        self.end_phase = EndPhasePanel(self.ctx)

        # Wire cross-panel references into context
        self.ctx.movement = self.movement
        self.ctx.ordnance = self.ordnance
        self.ctx.combat = self.combat
        # Engine hook: ships about to take damage from ramming, explosions or
        # asteroid fields may brace first (s.7)
        tc.gs.brace_hook = self._brace_hook
        tc.gs.raid_reroll_hook = self._raid_reroll_hook
        tc.gs.ld_reroll_hook = self._ld_reroll_hook
        tc.gs.undivided_hook = self._undivided_hook
        tc.gs.crit_reroll_hook = self._crit_reroll_hook
        tc.gs.turret_choice_hook = self._turret_choice_hook
        tc.gs.mr_suppress_hook = self._mr_suppress_hook
        tc.gs.reserve_hook = self._reserve_hook
        tc.gs.low_orbit_hook = self._low_orbit_hook
        tc.gs.assault_hook = self._assault_hook
        tc.gs.overcharge_hook = self._overcharge_hook

        self._game_over = False
        self._ai_thinking = False   # expert AI search running on a worker thread
        self._ai_epoch = 0          # bumped on load so stale AI callbacks do nothing
        self.ctx.actions_locked = self._actions_locked

    # ── The screen (overridden by GamePanel) ────────────────────────────────

    def _update_phase_display(self):
        """Show the phase, turn and whose turn it is."""

    def _show_victory_points(self):
        """Show the victory points so far."""

    def _show_game_over_dialog(self, winner, reason: str = "", detail: str = ""):
        """The game is over: show the result."""
        self.game_result = {"winner": winner, "reason": reason, "detail": detail}

    def _disengage_dialog(self):
        """A human player's disengage choices (the window asks)."""

    def _brace_hook(self, ship, attacker_key, attacker_name, expected):
        """GameState.brace_hook: ask the ship's player (the AI decides for its
        own ships). Only on the Tk main thread; elsewhere nothing is asked."""
        import threading
        if threading.current_thread() is not threading.main_thread():
            return False
        from .combat import squadron_group
        return self.combat._brace_before_attack(
            attacker_key, attacker_name, ship, expected,
            group=squadron_group(ship, self.ctx.gs.get_ships()))

    def _mr_suppress_hook(self, ship, group):
        """GameState.mr_suppress_hook (s.27): how many of the wave's multi-role
        fighter-bombers suppress turrets instead of attacking (before the
        turrets fire; at least one squadron must attack)."""
        import threading
        from .waves import mr_suppress_candidates
        if threading.current_thread() is not threading.main_thread():
            return 0
        n_mr = len(mr_suppress_candidates(group))
        from .waves import best_mr_suppress
        from .ordnance import turret_hit_on, ordnance_turrets
        from .ordnance import get_massed_turret_bonus
        t = ordnance_turrets(ship, self.ctx.gs)
        best = best_mr_suppress(group, t, (7 - turret_hit_on(ship)) / 6.0, ship.lowest_armor_value,
                                shots=t + get_massed_turret_bonus(ship, self.ctx.gs.get_ships()))
        return self.ctx.prompt.choose("Suppress turrets?",
            f"A wave of {len(group)} squadrons is attacking {ship.name} "
            f"({ship.effective_turrets} turrets). {n_mr} multi-role squadron(s) may suppress "
            f"turrets instead of attacking (s.27): each surviving one gives a bomber exactly 3 "
            f"attacks. At least one squadron must attack. How many suppress?",
            [(str(k), k) for k in range(n_mr + 1)], best)

    def _turret_choice_hook(self, ship, craft, torps):
        """GameState.turret_choice_hook (s.28): attack craft and torpedoes /
        mines attack this ship in one phase; its turrets may defend against
        one kind only. Off the main thread nothing is asked (AI choice)."""
        import threading
        if threading.current_thread() is not threading.main_thread():
            return None
        tdesc = ", ".join(f"{m.ordnance_type} S{m.strength}" for m in torps)
        from .ordnance import choose_turret_target
        best = choose_turret_target(ship, craft, torps, self.ctx.gs, ai=True)
        return self.ctx.prompt.choose("Turrets: attack craft or torpedoes?",
            f"{ship.name} is attacked by {len(craft)} attack craft squadron(s) and by {tdesc}. "
            f"Its turrets can defend against only one kind this phase (s.28).",
            [("Shoot the attack craft", "craft"), ("Shoot the torpedoes / mines", "torp")], best)

    def _crit_reroll_hook(self, player, text, best=False):
        """GameState.crit_reroll_hook (Mark of Tzeentch): ask the owner. Off the
        main thread nothing is asked (the engine's AI choice applies)."""
        import threading
        if threading.current_thread() is not threading.main_thread():
            return False
        return self.ctx.prompt.choose("Mark of Tzeentch", f"Player {player}: {text}",
                      [("Re-roll", True), ("Keep", False)], best)

    def _first_turn_roll_off(self):
        """s.2 First turn: roll off; the winner moves first or second (the AI
        by first_turn.ai_moves_first, a human asked with "Auto (best)")."""
        from .first_turn import roll_off, ai_moves_first
        from .dice import DiceRoller
        gs = self.ctx.gs
        auto = DiceRoller(mode="auto")
        winner, (a, b) = roll_off(auto if self.ctx.is_ai_controlled(1) else self.ctx.dice,
                                  auto if self.ctx.is_ai_controlled(2) else self.ctx.dice)
        best = ai_moves_first(gs, winner)
        if self.ctx.is_ai_controlled(winner):
            first = best
        else:
            first = self.ctx.prompt.choose("First Turn",
                           f"Roll-off: player 1 rolled {a}, player 2 rolled {b}. "
                           f"Player {winner} wins: move first or second?",
                           [("Move first", True), ("Move second", False)], best)
        gs.first_player = winner if first else 3 - winner
        self.ctx.log(f"First turn: player {winner} wins the roll-off ({a} v {b}) and "
                     f"chooses to move {'first' if first else 'second'}")

    def _undivided_hook(self, ship, leader, label):
        """GameState.undivided_hook: Mark of Chaos Undivided, once per game
        before a Leadership test or command check. A human owner is asked
        ("Auto (best)" is the AI's rule); the AI decides for its own fleet.
        Main thread only."""
        import threading
        from .chaos_undivided import ai_wants_undivided
        best = ai_wants_undivided(self.ctx.gs, ship, leader, label)
        if (threading.current_thread() is not threading.main_thread()
                or self.ctx.is_ai_controlled(ship.player)):
            return best
        return self.ctx.prompt.choose("Mark of Chaos Undivided",
                      f"{ship.name} is about to test Leadership ({label}, Ld {ship.leadership}). "
                      f"Use the Mark of Chaos Undivided now (once per game): the whole fleet "
                      f"uses {leader.name}'s Ld {leader.leadership} until the end of the turn?",
                      [("Use it", True), ("Not now", False)], best)

    def _ld_reroll_hook(self, ship, label, roll, needed):
        """GameState.ld_reroll_hook: a failed Leadership test may use a fleet
        commander re-roll (s.5). A human owner is asked; the AI uses one while
        it has two or more left. Main thread only."""
        import threading
        if threading.current_thread() is not threading.main_thread():
            return False
        tc = self.ctx.tc
        left = tc.get_fleet_rerolls(ship.player, ship)
        if left <= 0:
            return False
        if self.ctx.is_ai_controlled(ship.player):
            from .ai_rerolls import should_reroll     # importance-based (owner guidance)
            use = should_reroll(ship, label, self.ctx.gs, left)
        else:
            from .ai_rerolls import should_reroll
            use = self.ctx.prompt.choose("Leadership Test Failed - Re-roll?",
                f"{ship.name}: {label} failed (rolled {roll} vs Ld {needed}). "
                f"Use a fleet commander re-roll ({left} left)?",
                [("Re-roll", True), ("Don't", False)],
                should_reroll(ship, label, self.ctx.gs, left))
        if use and tc.use_fleet_reroll(ship.player, ship):
            self.ctx.log(f"  {ship.name}: fleet re-roll for {label}")
            return True
        return False

    def _raid_reroll_hook(self, owner, roll, effective, target):
        """GameState.raid_reroll_hook (Wings of Fury): ask a human owner whether
        to re-roll a Thunderhawk raid. None lets the engine decide (AI owner,
        or off the Tk main thread)."""
        import threading
        gs = self.ctx.gs
        if (threading.current_thread() is not threading.main_thread()
                or gs.ai_spectator or (gs.ai_player is not None and owner == gs.ai_player)):
            return None
        from .hit_and_run import describe_raid_result
        shown = f"{roll}" + (f" ({effective} after modifiers)" if effective != roll else "")
        from .hit_and_run import best_raid_reroll
        return self.ctx.prompt.choose("Wings of Fury",
            f"Thunderhawk raid on {target.name} rolled {shown}: "
            f"{describe_raid_result(effective, target)}. Re-roll it? The second result "
            f"stands, even if it is worse.",
            [("Re-roll", True), ("Keep", False)],
            best_raid_reroll(roll, effective, target, gs, owner))

    def _is_ai_turn(self) -> bool:
        gs = self.ctx.gs
        if gs.current_phase == "setup":
            return False
        return gs.ai_spectator or (
            gs.ai_player is not None and gs.active_player == gs.ai_player)

    @contextmanager
    def _auto_dice(self):
        """Roll automatically for the duration (rolls made on the AI's behalf)."""
        gs, dice = self.ctx.gs, self.ctx.dice
        old = (gs.dice_mode, dice.mode)
        gs.dice_mode = dice.mode = "auto"
        try:
            yield
        finally:
            gs.dice_mode, dice.mode = old

    def _auto_dice_if(self, condition: bool):
        return self._auto_dice() if condition else nullcontext()

    def _actions_locked(self) -> bool:
        return self._game_over or self._ai_thinking or self._is_ai_turn()

    def _busy_with_ai(self) -> bool:
        """Tell the player to wait if the AI search is mid-flight."""
        if self._ai_thinking:
            self.ctx.prompt.notify("AI Thinking",
                                "The AI is still planning its move. Try again in a moment.")
            return True
        return False

    def _network_sync_phase(self):
        """After each phase: active player sends state; passive player receives."""
        net = self.ctx.network
        if net is None:
            return
        gs = self.ctx.gs
        local = self.ctx.local_player
        try:
            # The player who just finished their turn sends state
            if local == gs.active_player:
                net.send_state(gs)
            else:
                # Receive updated state from the active player
                new_gs = net.recv_state()
                # Preserve our reference but overwrite all mutable fields
                for attr in ("ships", "ordnance", "blast_markers", "phenomena",
                             "log", "turn_number", "current_phase", "active_player",
                             "phase_step"):
                    setattr(gs, attr, getattr(new_gs, attr))
        except ConnectionError as e:
            self.ctx.prompt.notify("Multiplayer Error",
                                 f"Network error: {e}\nGame will continue locally.", "error")
            self.ctx.network = None

    # ── Game flow ─────────────────────────────────────────────────────────────

    def _fleet_engagement_formations(self):
        """Fleet Engagement (p.108): each player secretly picks a formation (a
        human from a dialog; the AI at random, judgement), then the set-up
        and roles follow from the table and a roll (scenarios)."""
        from .rng import game_random
        from .scenarios import FORMATIONS, resolve_formations
        from .dice import DiceRoller
        gs = self.ctx.gs
        forms = {}
        for p in (1, 2):
            if self.ctx.is_ai_controlled(p):
                forms[p] = game_random(gs).choice(FORMATIONS)
            else:
                forms[p] = self.ctx.prompt.choose("Fleet Engagement",
                                  f"Player {p}: choose your fleet's formation (secret)",
                                  [(f.title(), f) for f in FORMATIONS], "wedge")

        def pick(player, options):
            if self.ctx.is_ai_controlled(player):
                return options[0]
            labels = [(f"Set-up {s}" + (f" as {'attacker' if r == 'atk' else 'defender'}"
                                        if r else ""), (s, r)) for s, r in options]
            return self.ctx.prompt.choose("Fleet Engagement", f"Player {player}: you choose the "
                          f"set-up", labels, options[0])
        resolve_formations(gs, forms[1], forms[2], DiceRoller(mode="auto"), pick)
        self.ctx.log(gs.log[-1])

    def _reserve_hook(self, player, names) -> bool:
        """Scenario reinforcements (The Bait, Rearguard Attack) may enter this
        turn: the AI brings them on at once (judgement); a human is asked."""
        import threading
        if self.ctx.is_ai_controlled(player) or \
                threading.current_thread() is not threading.main_thread():
            return True
        return self.ctx.prompt.choose("Reinforcements",
                      f"Player {player}: bring {names} on from the table edge this turn?",
                      [("Enter now", True), ("Wait", False)], True)

    def _low_orbit_hook(self, ship) -> bool:
        """Low orbit (s.39): a ship in the planet's gravity well at the start of
        its turn may enter low orbit. A human is asked, with "Auto (best)"
        (the AI's choice, `planet_scenarios.wants_low_orbit`)."""
        import threading
        from .planet_scenarios import wants_low_orbit
        best = wants_low_orbit(self.ctx.gs, ship)
        if self.ctx.is_ai_controlled(ship.player) or \
                threading.current_thread() is not threading.main_thread():
            return best
        return self.ctx.prompt.choose("Low orbit",
                      f"{ship.name} is in the planet's gravity well: enter low orbit?",
                      [("Enter low orbit", True), ("Stay in high orbit", False)], best)

    def _overcharge_hook(self, ship) -> bool:
        """Macharia's End: at the start of a Chaos turn the Planet Killer may
        begin charging its Armageddon Gun ("Auto (best)": the AI's choice,
        `campaign_scenarios.wants_overcharge`)."""
        import threading
        from .campaign_scenarios import wants_overcharge
        best = wants_overcharge(self.ctx.gs, ship)
        if self.ctx.is_ai_controlled(ship.player) or \
                threading.current_thread() is not threading.main_thread():
            return best
        return self.ctx.prompt.choose("Armageddon Overcharge",
                      f"{ship.name}: begin charging the Armageddon Gun? (3 counters, then it "
                      f"must fire 60cm ahead; while charging +2 shields, no turns, special "
                      f"orders or lances; it can't be stopped)",
                      [("Begin charging", True), ("Not yet", False)], best)

    def _assault_hook(self, ship) -> bool:
        """Planetary Assault: at the start of the attacker's shooting phase a
        ship within 30cm of the planet edge may assault instead of firing."""
        import threading
        if self.ctx.is_ai_controlled(ship.player) or \
                threading.current_thread() is not threading.main_thread():
            return True
        from .planet_scenarios import assault_capacity
        return self.ctx.prompt.choose("Planetary Assault",
                      f"{ship.name}: assault the planet (+{assault_capacity(ship):g} assault "
                      f"points; no shooting, launching or teleporting this turn)?",
                      [("Assault", True), ("Fight normally", False)], True)

    def _roll_subplots(self):
        """Sub-plots (p.80): with the rule on, each player (the attacker
        first) rolls one before deployment; nominations are asked of a human
        owner (the AI nominates the dearest ship)."""
        gs = self.ctx.gs
        if not getattr(gs, "rule_subplots", False) or gs.subplots:
            return
        from .subplots import generate, apply_setup
        from .dice import DiceRoller
        first = gs.scenario_attacker if gs.scenario_mode != "standard" else 1
        for p in (first, 3 - first):
            ai = self.ctx.is_ai_controlled(p)
            dice = DiceRoller(mode="auto") if ai else self.ctx.dice
            sp = generate(gs, p, dice)
            if ai:
                chooser = None
            else:

                def chooser(cands, prompt):
                    if not cands:
                        return None
                    best = max(cands, key=lambda s: s.points_value)
                    return self.ctx.prompt.choose("Sub-plot", prompt,
                                  [(c.name, c) for c in cands], best)
            for line in apply_setup(gs, p, sp, dice, chooser):
                self.ctx.log(f"[Sub-plot] {line}")
            # a faction sub-plot on top (Quest for Knowledge, Business as
            # Usual, an Inquisitor Lord's Secret Ploys)
            from .subplots import faction_subplot
            extra = faction_subplot(gs, p, dice)
            if extra is not None:
                for line in apply_setup(gs, p, extra, dice, chooser):
                    self.ctx.log(f"[Sub-plot] {line}")
        self.ctx.board.redraw()

    def _begin_turn1(self):
        with recorder.flow():                 # the flow's own steps (recorder)
            return self._begin_turn1_steps()

    def _begin_turn1_steps(self):
        """Called by DeploymentPanel when all ships are placed."""
        tc = self.ctx.tc
        gs = self.ctx.gs
        # Meteor Storm wrecks: catastrophic damage where they stand, once
        # deployment is finished (owner ruling)
        from .subplots import deployed_wrecks
        for res in deployed_wrecks(gs, self.ctx.dice):
            self.ctx.log(f"[Meteor Storm] a wreck: {res}")
        from .scenarios import first_player as _scenario_first, first_turn_chooser
        from .scenarios import roll_for_choice
        from .dice import DiceRoller
        chooser = first_turn_chooser(gs) or roll_for_choice(gs, DiceRoller(mode="auto"))
        if _scenario_first(gs):
            gs.first_player = _scenario_first(gs)
            self.ctx.log(f"First turn: player {gs.first_player} (the scenario's attacker)")
        elif chooser:
            # The scenario lets one player choose (Chance Encounter: the defender)
            from .first_turn import ai_moves_first
            best = ai_moves_first(gs, chooser)
            if self.ctx.is_ai_controlled(chooser):
                first = best
            else:
                first = self.ctx.prompt.choose("First Turn",
                               f"Player {chooser}: the scenario lets you choose. Move first "
                               f"or second?", [("Move first", True), ("Move second", False)],
                               best)
            gs.first_player = chooser if first else 3 - chooser
            self.ctx.log(f"First turn: player {chooser} chooses to move "
                         f"{'first' if first else 'second'}")
        else:
            self._first_turn_roll_off()
        tc.start_game()
        if self._aa_on():
            # Alternate activation (To do 13): the AA driver runs the rounds
            self._aa_begin()
            return
        tc.begin_phase("movement")
        with self._auto_dice_if(self._is_ai_turn()):
            self.movement._process_movement_phase_start()
        self._update_phase_display()
        self.ctx.log("=== GAME START ===")
        self.ctx.log(f"Turn 1 - {gs.player1_name}")
        self.ctx.log("Movement Phase")
        self.ctx.log(
            "Keys: M=min-move selected  Space=min-move all  "
            "BackSpace=undo all movement  Scroll=pending turn  Esc=cancel")
        self.ctx.board.canvas.focus_set()
        self.ctx.board.redraw()
        # If Player 1 (or both players) is AI, start automation immediately
        if self._is_ai_turn():
            self._schedule_ai_phase(500)

    def _resolve_end_phase_interactive(self):
        """Run end phase with interactive repair choices."""
        from .end_phase import (get_repair_info, apply_repair_choices,
                                remove_blast_markers, remove_brace_orders)
        gs = self.ctx.gs

        self.ctx.log("=== END PHASE ===")

        # 0a. Boarding actions (before teleport, before damage control)
        self.end_phase._resolve_boarding_actions()

        # 0b. Teleport attacks
        self.end_phase._resolve_teleport_attacks()

        # 1. Damage control with player choice
        for ship in gs.get_ships():
            if ship.is_destroyed or ship.is_disengaged:
                continue
            if ship.status in ("drifting_hulk", "burning_hulk"):
                continue

            info = get_repair_info(ship, self.ctx.dice, gs)
            if info["sixes"] > 0 and info["repairable"]:
                repairs_available = min(info["sixes"], len(info["repairable"]))
                touch_msg = (f" (halved, {info['touching_blast']} blast markers)"
                             if info.get("touching_blast", 0) > 0 else "")
                self.ctx.log(
                    f"{ship.name}: {info['num_dice']} dice{touch_msg}, "
                    f"{info['sixes']} repair(s) available!")
                choices = self.end_phase._repair_choice_dialog(
                    ship, info["repairable"], repairs_available)
                if choices:
                    repair_logs = apply_repair_choices(ship, choices, gs)
                    self.ctx.log_lines(repair_logs)
                else:
                    self.ctx.log(f"  {ship.name}: no repairs applied")
            elif info["num_dice"] > 0:
                self.ctx.log(f"{ship.name}: {info['num_dice']} dice, no 6s rolled")

        # 2. Fires not extinguished by damage control each deal 1 damage
        self._resolve_unextinguished_fires()

        # 3. Remove blast markers
        bm_logs = remove_blast_markers(gs, self.ctx.dice)
        self.ctx.log_lines(bm_logs)

        # 4. Remove expired brace orders
        brace_logs = remove_brace_orders(gs)
        self.ctx.log_lines(brace_logs)

        self.ctx.board.redraw()

    def _end_phase(self, from_ai: bool = False):
        with recorder.flow():
            return self._end_phase_steps(from_ai)

    def _end_phase_steps(self, from_ai: bool = False):
        """Advance to the next phase.

        from_ai: the AI driver already resolved this phase, so skip the
        prompts aimed at a human player and the interactive end phase.
        """
        if self._game_over:
            return
        if self._aa_on() and self.aa is not None:
            if not from_ai:
                self._aa_end_button()
            return
        gs = self.ctx.gs
        tc = self.ctx.tc
        phase = gs.current_phase

        if phase == "movement" and not from_ai:
            unmoved = tc.get_unmoved_ships()
            unmoved_obligated = [
                s for s in unmoved
                if not s.is_destroyed
                and s.special_order != SpecialOrder.BURN_RETROS.value
            ]
            if unmoved_obligated:
                names = "\n  ".join(s.name for s in unmoved_obligated[:8])
                if not gs.allow_movement_pass:
                    self.ctx.prompt.notify(
                        "Ships Must Move",
                        f"These ships have not moved:\n  {names}\n\n"
                        f"All ships must move before ending the movement phase.\n"
                        f"Use Burn Retros to remain stationary.", "error")
                    return
                else:
                    override = self.ctx.prompt.yes_no(
                        "Ships Haven't Moved",
                        f"These ships haven't moved:\n  {names}\n\n"
                        f"All ships should move before ending movement.\n"
                        f"Use Burn Retros to remain stationary.\n\n"
                        f"OVERRIDE and end phase anyway?")
                    if not override:
                        return

        if phase == "ordnance":
            with self._auto_dice_if(from_ai):
                self.ordnance._resolve_ordnance_movement()

        if phase == "shooting" and not from_ai:
            unfired_warnings = []
            for s in gs.player_ships(gs.active_player):
                if s.is_destroyed or s.is_disengaged:
                    continue
                unfired = []
                for i, w in enumerate(s.weapons):
                    wtype = w.get("weapon_type", "")
                    if wtype in ("torpedo", "launch_bay"):
                        continue
                    if self.combat._weapon_disabled_by_crit(s, w):
                        continue
                    if i not in s.weapons_fired_indices:
                        unfired.append(w["name"])
                if unfired:
                    unfired_warnings.append(f"{s.name}: {', '.join(unfired)}")
            if unfired_warnings:
                msg = "\n".join(unfired_warnings[:6])
                self.ctx.prompt.notify("Unfired Weapons",
                    f"These weapons haven't fired:\n{msg}\n\nEnd shooting phase anyway?", "warning")

        if phase == "end" and not from_ai:
            self._resolve_end_phase_interactive()

        tc.end_phase()
        tc.advance_phase()

        # LAN multiplayer: sync state to peer after each phase
        self._network_sync_phase()

        # Check for game-over conditions at the start of each new turn
        if gs.current_phase == "movement" and gs.turn_number > 1:
            if self._check_game_over():
                self._update_phase_display()
                self.ctx.board.redraw()
                return

        if gs.current_phase == "movement":
            with self._auto_dice_if(self._is_ai_turn()):
                self.movement._process_movement_phase_start()
            self._check_artefact_pickup()
            self.ctx.log(
                "Keys: M=min-move selected  Space=min-move all  "
                "BackSpace=undo all  Scroll=pending turn  Esc=cancel")
            self.ctx.board.canvas.focus_set()

        if gs.current_phase == "ordnance":
            for i, o_dict in enumerate(gs.ordnance):
                if o_dict.get("moved_this_phase"):
                    gs.ordnance[i] = {**o_dict, "moved_this_phase": False}

        # Check scenario conditions after shooting and ordnance resolve too
        if phase in ("shooting", "ordnance", "end") and self._check_scenario_end():
            self._update_phase_display()
            self.ctx.board.redraw()
            return

        self._update_phase_display()
        self.ctx.log(f"--- {gs.current_phase.upper()} PHASE ---")
        self.ctx.board.redraw()

        if self._is_ai_turn():
            self._schedule_ai_phase(400)

    # ── AI phase automation ───────────────────────────────────────────────────

    # Fast mode (the headless runner, tools/headless_runner.py; or BFG_FAST=1):
    # no pacing pauses between AI phases, the AI's worker polled every 1ms
    FAST = bool(os.environ.get("BFG_FAST"))

    def _pace(self, ms: int) -> int:
        return 1 if self.FAST else ms

    def _schedule_ai_phase(self, delay_ms: int):
        epoch = self._ai_epoch
        self.root.after(self._pace(delay_ms), lambda: self._run_ai_phase(epoch))

    def _ai_callback_stale(self, epoch: int) -> bool:
        """True if a load or game over happened since this AI callback was queued."""
        return epoch != self._ai_epoch or self._game_over

    def _run_ai_phase(self, epoch: int):
        import threading
        from .ai_player import AIPlayer
        if self._ai_callback_stale(epoch) or self._ai_thinking or not self._is_ai_turn():
            return
        gs = self.ctx.gs
        tc = self.ctx.tc
        dice = self.ctx.dice
        phase = gs.current_phase

        # In spectator mode both players are AI; use active_player as the controller
        ai_player_num = gs.active_player if gs.ai_spectator else gs.ai_player

        # DiceRoller reads its own mode; gs.dice_mode is just the saved setting
        old_modes = (gs.dice_mode, dice.mode)
        gs.dice_mode = dice.mode = "auto"

        def restore_dice():
            gs.dice_mode, dice.mode = old_modes

        if gs.ai_difficulty == "expert":
            from .lookahead_ai import LookaheadAI
            ai = LookaheadAI(ai_player_num, tc, gs, dice, gs.ai_difficulty)
        else:
            ai = AIPlayer(ai_player_num, tc, gs, dice, gs.ai_difficulty)
        # Targets decide on Brace for Impact before the AI's attacks are rolled
        ai.brace_fn = (lambda att, tgt, exp, grp: self.combat._brace_before_attack(
            att.id, att.name, tgt, exp, None, grp, att))
        # A replay (replay.py): this phase's actions come from the record
        replaying = phase in getattr(self, "replay_phases", ()) and phase != "end"
        if replaying:
            from .replay import ReplaySeat
            ai = ReplaySeat(self, ai_player_num, self.replay_events)

        # Expert movement is slow (minimax depth-5); run off-thread so UI stays
        # live. The worker never touches Tk: the main thread polls for it.
        if gs.ai_difficulty == "expert" and phase == "movement" and not replaying:
            outcome = {}

            def _do_movement():
                try:
                    ai.run_movement_phase()
                except Exception as exc:
                    outcome["error"] = exc

            def _poll():
                if worker.is_alive():
                    self.root.after(self._pace(100), _poll)
                    return
                if "error" not in outcome:
                    # Main thread: ordnance the AI's ships ran into attacks them
                    with recorder.flow():
                        self.ordnance._resolve_moving_ship_contacts()
                restore_dice()
                self._ai_thinking = False
                if "error" in outcome:
                    self._report_ai_error(phase, outcome["error"])
                self.ctx.board.redraw()
                self.ctx.log("[AI] movement phase complete")
                self._update_phase_display()
                self._finish_ai_phase(phase, epoch)

            self._ai_thinking = True
            self._update_phase_display()
            worker = threading.Thread(target=_do_movement, daemon=True)
            worker.start()
            self.root.after(self._pace(100), _poll)
            return

        try:
            if phase == "movement":
                ai.run_movement_phase()
                # Ordnance the AI's ships ran into attacks them (s.15)
                with recorder.flow():
                    self.ordnance._resolve_moving_ship_contacts()
            elif phase == "shooting":
                ai.run_shooting_phase()
            elif phase == "ordnance":
                ai.run_ordnance_phase()
            elif phase == "end":
                with recorder.flow():
                    self._resolve_end_phase_auto(ai)
        except Exception as exc:
            self._report_ai_error(phase, exc)
        finally:
            restore_dice()

        self.ctx.board.redraw()
        self.ctx.log(f"[AI] {phase} phase complete")
        self._finish_ai_phase(phase, epoch)

    def _finish_ai_phase(self, phase: str, epoch: int):
        def advance():
            if not self._ai_callback_stale(epoch):
                self._end_phase(from_ai=True)
        self.root.after(self._pace(300), advance)

    def _report_ai_error(self, phase: str, exc: Exception):
        """An AI failure ends the AI's phase instead of freezing the game."""
        import traceback
        traceback.print_exception(type(exc), exc, exc.__traceback__)
        self.ctx.log(f"[AI] Error during {phase} phase: {exc!r} — ending the AI's phase")
        self.ctx.prompt.notify(
            "AI Error",
            f"The AI hit an error during the {phase} phase and will end its phase "
            f"early so the game can continue.\n\n{exc!r}", "error")

    def _resolve_end_phase_auto(self, ai):
        """End phase for the AI player — same logic as interactive but auto-repairs."""
        from .end_phase import (get_repair_info, apply_repair_choices,
                                remove_blast_markers, remove_brace_orders)
        from .ai_player import AIPlayer
        gs = self.ctx.gs

        self.ctx.log("=== END PHASE (AI) ===")

        self.end_phase._resolve_boarding_actions()
        self.end_phase._resolve_teleport_attacks()

        for ship in gs.get_ships():
            if ship.is_destroyed or ship.is_disengaged:
                continue
            if ship.status in ("drifting_hulk", "burning_hulk"):
                continue
            info = get_repair_info(ship, self.ctx.dice, gs)
            if info["sixes"] > 0 and info["repairable"]:
                repairs_available = min(info["sixes"], len(info["repairable"]))
                if self.ctx.is_ai_controlled(ship.player):
                    choices = AIPlayer.auto_repair_choices(
                        info["repairable"], repairs_available)
                else:
                    choices = self.end_phase._repair_choice_dialog(
                        ship, info["repairable"], repairs_available)
                if choices:
                    repair_logs = apply_repair_choices(ship, choices, gs)
                    self.ctx.log_lines(repair_logs)

        self._resolve_unextinguished_fires()

        bm_logs = remove_blast_markers(gs, self.ctx.dice)
        self.ctx.log_lines(bm_logs)
        brace_logs = remove_brace_orders(gs)
        self.ctx.log_lines(brace_logs)
        self.ctx.board.redraw()

    def _resolve_unextinguished_fires(self):
        """After damage control: each fire still burning deals 1 damage."""
        from .end_phase import resolve_fire_damage
        for ship in self.ctx.gs.get_ships():
            if ship.is_destroyed or ship.is_disengaged:
                continue
            if ship.status in ("drifting_hulk", "burning_hulk"):
                continue
            self.ctx.log_lines(resolve_fire_damage(ship, self.ctx.dice, self.ctx.gs))
            if ship.hits_remaining <= 0:
                self.ctx.check_destruction(ship)

    def _check_game_over(self) -> bool:
        from .scenario import check_game_over
        return self._declare_game_over(check_game_over(self.ctx.gs))

    def _check_scenario_end(self) -> bool:
        from .scenario import check_scenario_end
        return self._declare_game_over(check_scenario_end(self.ctx.gs))

    def _declare_game_over(self, result) -> bool:
        if not result:
            return False
        # Rolls the scenario makes when the game ends (Warp Storm's warp tests)
        from .scenarios import end_of_game, winner_at_end
        from .scenario import vp_winner
        from .dice import DiceRoller
        dice = DiceRoller(mode="auto") if all(self.ctx.is_ai_controlled(p) for p in (1, 2)) \
            else self.ctx.dice
        if end_of_game(self.ctx.gs, dice) and result.get("reason") != "objective_points":
            result = {**result, "winner": winner_at_end(self.ctx.gs, vp_winner)}
        self._game_over = True
        self.ctx.log("=== GAME OVER ===")
        self._show_game_over_dialog(
            result["winner"], reason=result["reason"], detail=result["detail"])
        return True

    def _check_artefact_pickup(self):
        """After movement: check if any ship moved onto the uncarried artefact token."""
        from .scenario import check_artefact_pickup
        ship = check_artefact_pickup(self.ctx.gs)
        if ship:
            self.ctx.board.redraw()
            self.ctx.prompt.notify("Artefact Seized",
                f"{ship.name} has picked up the artefact!\n"
                f"Escape the board edge or warp out to win.")
