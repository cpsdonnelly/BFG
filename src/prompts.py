"""The questions the game asks a player while it resolves something (To do
18: the game flow out of the Tk panels; To do 17: their answers recorded and
replayed). Game code asks through `ctx.prompt` and never opens a dialog itself:

- Prompter: answers with "best" (what the AI's expected-value logic would
  pick, the "Auto (best)" choice) and needs no window: headless games, AI
  seats, tests.
- TkPrompter: the desktop dialogs (choice_dialog with its "Auto (best)"
  button, Tk's yes / no and number boxes). It calls choice_dialog.choose /
  yes_no at call time, so tests and GUI checks that replace those still work.
- ReplayPrompter: the answers recorded in a game's events, in order.

Every answer is recorded as a "prompt" event (recorder), whoever gives it.
"""
from typing import Any, List, Optional

from . import recorder


class Prompter:
    """No window: every question takes its best answer (a plain yes / no
    question with no best takes "no"; a number takes its default)."""

    def _answered(self, kind: str, title: str, answer, best=None):
        recorder.event(recorder.current_gs(), "prompt", ask=kind, title=title,
                       answer=answer, best=best, auto=(answer == best))
        return answer

    # Questions -----------------------------------------------------------------
    def choose(self, title: str, text: str, options, best):
        """options: [(label, value), ...]; returns a value."""
        return self._answered("choose", title, self._choose(title, text, options, best), best)

    def yes_no(self, title: str, text: str, best: Optional[bool] = None) -> bool:
        return self._answered("yes_no", title, bool(self._yes_no(title, text, best)), best)

    def number(self, title: str, text: str, default: Optional[float], lo: float, hi: float,
               integer: bool = False):
        """A number between lo and hi; None if the player cancels."""
        v = self._number(title, text, default, lo, hi, integer)
        return self._answered("number", title, v, default)

    def pick_ship(self, title: str, ships, best=None):
        """One of the ships (a decision inside an action: a ram, boarding or
        teleport target); None if the player picks none."""
        pick = self._pick_ship(title, ships, best)
        self._answered("pick_ship", title, getattr(pick, "id", None), getattr(best, "id", None))
        return pick

    def pick_many(self, title: str, text: str, options: List[str], most: int,
                  best: List[str]) -> List[str]:
        """Up to `most` of the options (e.g. the criticals to repair)."""
        return self._answered("pick_many", title,
                              list(self._pick_many(title, text, options, most, best)), best)

    def notify(self, title: str, text: str, level: str = "info") -> None:
        """A message the player only acknowledges (info / warning / error)."""
        self._notify(title, text, level)

    # How this prompter answers -------------------------------------------------
    def _choose(self, title, text, options, best):
        return best

    def _yes_no(self, title, text, best):
        return bool(best) if best is not None else False

    def _number(self, title, text, default, lo, hi, integer):
        return default

    def _pick_many(self, title, text, options, most, best):
        return best

    def _pick_ship(self, title, ships, best):
        return best

    def _notify(self, title, text, level):
        pass


class TkPrompter(Prompter):
    """The desktop dialogs."""

    def __init__(self, root):
        self.root = root

    def _choose(self, title, text, options, best):
        from . import choice_dialog
        return choice_dialog.choose(self.root, title, text, options, best)

    def _yes_no(self, title, text, best):
        if best is not None:
            from . import choice_dialog
            return choice_dialog.yes_no(self.root, title, text, best)
        from tkinter import messagebox
        return messagebox.askyesno(title, text)

    def _number(self, title, text, default, lo, hi, integer):
        from tkinter import simpledialog
        ask = simpledialog.askinteger if integer else simpledialog.askfloat
        kw = {"minvalue": lo, "maxvalue": hi, "parent": self.root}
        if default is not None:
            kw["initialvalue"] = round(default) if not integer else int(default)
        return ask(title, text, **kw)

    def _pick_ship(self, title, ships, best):
        from .game_context import pick_ship_dialog
        return pick_ship_dialog(self.root, ships, title)

    def _pick_many(self, title, text, options, most, best):
        import tkinter as tk
        from tkinter import messagebox
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("400x380")
        dialog.transient(self.root)
        tk.Label(dialog, text=text, font=("Consolas", 10, "bold")).pack(pady=5)
        check_vars = {}
        for opt in options:
            var = tk.BooleanVar(value=False)
            check_vars[opt] = var
            tk.Checkbutton(dialog, text=opt, variable=var,
                           font=("Consolas", 9)).pack(anchor=tk.W, padx=20)
        result = [None]

        def confirm():
            selected = [o for o, var in check_vars.items() if var.get()]
            if len(selected) > most:
                messagebox.showwarning("Too Many", f"Select at most {most}.")
                return
            result[0] = selected
            dialog.destroy()

        def take(v):
            result[0] = list(v)
            dialog.destroy()

        row = tk.Frame(dialog)
        row.pack(pady=10)
        tk.Button(row, text="Repair Selected", command=confirm, bg="#336633", fg="white",
                  font=("Consolas", 10)).pack(side=tk.LEFT, padx=5)
        tk.Button(row, text="Skip Repairs", command=lambda: take([]),
                  font=("Consolas", 10)).pack(side=tk.LEFT, padx=5)
        tk.Button(dialog, text="Auto", bg="#335533",
                  fg="white", wraplength=360, command=lambda: take(best)).pack(pady=(0, 8))
        dialog.protocol("WM_DELETE_WINDOW", lambda: take(best))
        self.root.wait_window(dialog)
        return result[0] if result[0] is not None else []

    def _notify(self, title, text, level):
        from tkinter import messagebox
        {"warning": messagebox.showwarning, "error": messagebox.showerror}.get(
            level, messagebox.showinfo)(title, text)


class ReplayDivergence(Exception):
    """A replay asked a question the record doesn't have next."""


class ReplayPrompter(Prompter):
    """The answers recorded in a game's events, in order."""

    def __init__(self, events: List[dict]):
        self.answers = [e for e in events if e.get("kind") == "prompt"]
        self.pos = 0

    def _next(self, kind: str, title: str) -> Any:
        if self.pos >= len(self.answers):
            raise ReplayDivergence(f"prompt {self.pos}: {kind} '{title}' past the end of the record")
        e = self.answers[self.pos]
        if e.get("ask", kind) != kind or e.get("title") != title:
            raise ReplayDivergence(f"prompt {self.pos}: wanted {kind} '{title}', the record has "
                                   f"{e.get('ask')} '{e.get('title')}'")
        self.pos += 1
        return e.get("answer")

    def _choose(self, title, text, options, best):
        ans = self._next("choose", title)
        # recorded values are JSON: match them back to the option values
        for _lbl, v in options:
            if v == ans or recorder._jsonable(v) == ans:
                return v
        return ans

    def _yes_no(self, title, text, best):
        return self._next("yes_no", title)

    def _number(self, title, text, default, lo, hi, integer):
        return self._next("number", title)

    def _pick_many(self, title, text, options, most, best):
        return self._next("pick_many", title)

    def _pick_ship(self, title, ships, best):
        sid = self._next("pick_ship", title)
        return next((s for s in ships if s.id == sid), None)
