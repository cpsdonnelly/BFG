"""Replaying a game from its record (To do 17): the start state, the rolls
(dice.DiceSource in replay), the answers to questions (prompts.ReplayPrompter)
and each player's actions (the depth-0 seat events, actions.replay_event).

ReplaySeat stands in for a player in the phases being replayed: instead of
deciding, it does that player's recorded actions for the phase again. The
game flow runs as it did (it resolves the consequences itself), so a replay
that reaches the same state shows the record held every decision. Phases not
replayed are played by the AI as before; with every phase replayed, a game
with human players replays too."""
from . import actions


def seat_events(events, turn: int, phase: str, player: int):
    """The player's own recorded actions in one phase, in order."""
    return [e for e in events
            if e.get("depth") == 0 and e.get("seat") and e["turn"] == turn
            and e["phase"] == phase and e["player"] == player
            and e["kind"] not in ("prompt",)]


class ReplaySeat:
    """A player whose phase is played from the record."""

    def __init__(self, flow, player: int, events):
        self.flow, self.player, self.events = flow, player, events
        self.gs, self.tc, self.dice = flow.ctx.gs, flow.ctx.tc, flow.ctx.dice
        self.brace_fn = None

    def _replay(self, phase: str):
        contacts = self.flow.ordnance._resolve_moving_ship_contacts
        for ev in seat_events(self.events, self.gs.turn_number, phase, self.player):
            actions.replay_event(self.gs, self.tc, self.dice, ev, contacts=contacts,
                                 panel=self.flow.combat)

    def run_movement_phase(self):
        self._replay("movement")

    def run_shooting_phase(self):
        self._replay("shooting")

    def run_ordnance_phase(self):
        self._replay("ordnance")
