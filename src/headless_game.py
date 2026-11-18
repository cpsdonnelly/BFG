"""A game with no window (To do 18 / 16): the same GameFlow the desktop window
runs, with
- HeadlessContext: the log kept as a list, a board that ignores drawing,
  questions answered by ctx.prompt (prompts.Prompter: the best answer);
- QueueRoot: Tk's `after` scheduling as a queue run in order (virtual time),
  so the flow's steps run exactly as the window would run them;
- HeadlessGame.play(): from the first turn to game over.

Every seat is played by the AI (gs.ai_spectator); a human seat needs a
window. Used by tools/headless_runner.py --no-display; the window and this
give the same game from the same seed (the runner's --replay-check / hashes)."""
import heapq
import itertools
import time

from .game_context import GameContext
from .game_flow import GameFlow


class _Null:
    """A board that ignores everything: every attribute and call is itself."""

    def __getattr__(self, name):
        return self

    def __call__(self, *a, **k):
        return self

    def __bool__(self):
        return False

    def __iter__(self):
        return iter(())


class QueueRoot:
    """Tk's root.after as a queue: callbacks run in due order (virtual time,
    ties first-come); no real waiting, except a short pause while an AI search
    runs on its worker thread."""

    def __init__(self):
        self._q = []
        self._now = 0
        self._seq = itertools.count()

    def after(self, ms, fn=None, *args):
        if fn is not None:
            heapq.heappush(self._q, (self._now + int(ms), next(self._seq), fn, args))
        return None

    def after_idle(self, fn, *args):
        return self.after(0, fn, *args)

    def update(self):
        pass

    def update_idletasks(self):
        pass

    def bind(self, *a, **k):
        pass

    def run(self, done, timeout: float = 600.0) -> bool:
        """Run queued callbacks until done() or the queue is empty; False on
        timeout (seconds of real time)."""
        start = time.time()
        while self._q and not done():
            if time.time() - start > timeout:
                return False
            due, _n, fn, args = heapq.heappop(self._q)
            self._now = max(self._now, due)
            fn(*args)
            if self._q and len(self._q) == 1 and self._q[0][2].__name__ == "_poll":
                time.sleep(0.001)          # an AI search is running: let it work
        return True


class HeadlessContext(GameContext):
    """A GameContext with no widgets: the log is a list."""

    def __init__(self, tc, gs, dice):
        super().__init__(tc=tc, gs=gs, dice=dice, board=_Null(), root=None, log_widget=None)
        self.lines = []

    def log(self, text: str):
        self.lines.append(text)


class HeadlessGame(GameFlow):
    """GameFlow with no window: every seat is the AI's."""

    def __init__(self, tc, replay_events=None, replay_phases=()):
        """replay_events / replay_phases: play those phases from a recorded
        game's actions (replay.ReplaySeat) instead of deciding them."""
        tc.gs.ai_spectator = True
        self.parent = None
        self._init_flow(HeadlessContext(tc, tc.gs, tc.dice), QueueRoot())
        self.game_result = None
        self.replay_events = replay_events or []
        self.replay_phases = tuple(replay_phases)

    def play(self, timeout: float = 600.0):
        """Deployment is the start state; play from the first turn to game
        over. Returns the result ({winner, reason, detail}) or None."""
        self._begin_turn1()
        self.root.run(lambda: self._game_over, timeout)
        return self.game_result
