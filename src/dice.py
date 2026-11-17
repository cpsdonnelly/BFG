"""BFG:XR Dice System - Manual input, auto RNG, or mixed"""
import random
from typing import List

try:
    import tkinter as tk
    from tkinter import simpledialog
    HAS_TK = True
except ImportError:
    HAS_TK = False
    tk = None


class ReplayDivergence(Exception):
    """A replayed game asked for a roll the record doesn't have next."""


class DiceSource:
    """The game's dice (To do 17): one seeded generator behind every
    DiceRoller, so a game repeats from its seed, and an optional record of
    every roll in order (kind, count, values, description, "auto" or
    "manual" for a player's own dice). In replay the recorded values come
    back in order whatever the roller's mode, and a roll of another kind
    or count raises ReplayDivergence."""

    def __init__(self, seed=None, record: bool = False, replay: list = None):
        self.seed = seed
        self.rng = random.Random(seed)
        self.record = [] if record or replay is not None else None
        self.replay = replay
        self.pos = 0

    # auto rolls
    def d6s(self, count: int) -> List[int]:
        return [self.rng.randint(1, 6) for _ in range(count)]

    def note(self, kind: str, count: int, values, desc: str, src: str = "auto"):
        if self.record is not None:
            self.record.append([kind, count, values, desc, src])

    def take(self, kind: str, count: int, desc: str):
        """The next recorded roll, which must be of this kind and count."""
        if self.pos >= len(self.replay):
            raise ReplayDivergence(f"roll {self.pos}: {kind} x{count} ({desc}) past the end of the record")
        entry = self.replay[self.pos]
        if entry[0] != kind or entry[1] != count:
            raise ReplayDivergence(f"roll {self.pos}: wanted {kind} x{count} ({desc}), "
                                   f"the record has {entry[0]} x{entry[1]} ({entry[3]})")
        self.pos += 1
        self.record.append(list(entry))
        return entry[2]

    @property
    def replaying(self) -> bool:
        return self.replay is not None

    def state(self) -> dict:
        """Saved with the game: the seed, the generator's state and the record."""
        st = self.rng.getstate()
        return {"seed": self.seed, "rng": [st[0], list(st[1]), st[2]], "record": self.record}

    @classmethod
    def from_state(cls, d: dict) -> "DiceSource":
        src = cls(d.get("seed"))
        st = d.get("rng")
        if st:
            src.rng.setstate((st[0], tuple(st[1]), st[2]))
        src.record = d.get("record")
        return src


_SOURCE = DiceSource()          # unseeded, unrecorded until a game starts one


def current_source() -> DiceSource:
    return _SOURCE


def set_source(source: DiceSource) -> DiceSource:
    """Make `source` the game's dice (start of a game, a load, a replay)."""
    global _SOURCE
    _SOURCE = source
    return source


def start_game_dice(seed: int, record: bool = True) -> DiceSource:
    """A new game's dice from its seed (GameState.game_seed)."""
    return set_source(DiceSource(seed, record=record))


class DiceRoller:
    """Handles all dice rolling with configurable input mode. Every roller
    draws from the game's DiceSource (current_source), so all of a game's
    rolls come from one seeded generator and are recorded in order."""

    def __init__(self, mode: str = "auto", root=None):
        """
        mode: "auto" (computer RNG), "manual" (player types results),
              "mixed" (popup asks each time with auto-resolve button)
        """
        self.mode = mode
        self.root = root
        self.log: List[str] = []
        self._typed = False      # the last manual roll was typed by a player

    def roll_d6(self, count: int = 1, description: str = "") -> List[int]:
        """Roll count D6 dice. Returns list of results."""
        if count <= 0:
            return []
        src = _SOURCE
        desc = description or f"{count}D6"
        if src.replaying:
            results = list(src.take("d6", count, desc))
        elif self.mode == "auto":
            results = src.d6s(count)
            src.note("d6", count, results, desc)
        else:
            self._typed = False
            results = (self._manual_input(count, description) if self.mode == "manual"
                       else self._mixed_input(count, description))
            src.note("d6", count, results, desc, "manual" if self._typed else "auto")
        self.log.append(f"{desc}: {results} (sum={sum(results)})")
        return results

    def roll_2d6(self, description: str = "") -> int:
        """Roll 2D6 and return the sum."""
        src = _SOURCE
        if src.replaying and src.pos < len(src.replay) and src.replay[src.pos][0] == "2d6sum":
            return src.take("2d6sum", 1, description or "2D6")   # a player typed the sum
        if self.mode == "mixed" and self.root and not src.replaying:
            return self._mixed_2d6_input(description)
        results = self.roll_d6(2, description)
        return sum(results)

    def roll_d3(self, description: str = "") -> int:
        """Roll a D3 (D6 halved, round up)."""
        result = self.roll_d6(1, description or "D3")
        val = (result[0] + 1) // 2
        self.log.append(f"  -> D3 result: {val}")
        return val

    def roll_scatter(self, description: str = "") -> bool:
        """Roll a scatter die. Returns True for Hit, False for Miss."""
        # Scatter die: 2 faces Hit, 4 faces Miss (arrow)
        # Represented as D6: 1-2 = Hit, 3-6 = Miss
        result = self.roll_d6(1, description or "Scatter")[0]
        is_hit = result <= 2
        self.log.append(f"  -> Scatter: {'HIT' if is_hit else 'MISS'}")
        return is_hit

    def roll_scatter_direction(self) -> float:
        """Roll for scatter direction in degrees (0-360)."""
        # In tabletop, the arrow on the scatter die points a direction
        # We simulate with a random angle
        return self.roll_direction("Scatter direction")

    def roll_direction(self, description: str = "Direction") -> float:
        """A random direction in degrees (0-360), from the game's dice."""
        src = _SOURCE
        if src.replaying:
            angle = src.take("angle", 1, description)
        else:
            angle = src.rng.uniform(0, 360)
            src.note("angle", 1, angle, description)
        self.log.append(f"  -> {description}: {angle:.0f}°")
        return angle

    def count_successes(self, dice: List[int], threshold: int) -> int:
        """Count dice that meet or exceed a threshold."""
        return sum(1 for d in dice if d >= threshold)

    def armor_value_to_threshold(self, armor_str: str) -> int:
        """Convert armor string like '5+' to integer threshold."""
        return int(armor_str.replace("+", ""))

    def _manual_input(self, count: int, description: str) -> List[int]:
        """Get dice results from player input via dialog."""
        if not self.root:
            # Fallback to auto if no GUI
            return _SOURCE.d6s(count)

        prompt = f"Roll {count}D6"
        if description:
            prompt += f" for: {description}"
        prompt += f"\nEnter {count} results separated by spaces (1-6):"

        while True:
            result_str = simpledialog.askstring("Dice Roll", prompt, parent=self.root)
            if result_str is None:
                # User cancelled, auto-resolve
                return _SOURCE.d6s(count)
            try:
                values = [int(x.strip()) for x in result_str.split()]
                if len(values) == count and all(1 <= v <= 6 for v in values):
                    self._typed = True
                    return values
                elif len(values) == 1 and count == 1:
                    if 1 <= values[0] <= 6:
                        self._typed = True
                        return values
            except ValueError:
                pass
            prompt = f"Invalid input. Need {count} numbers from 1-6.\nTry again:"

    def _mixed_input(self, count: int, description: str) -> List[int]:
        """Show popup with auto-resolve button or manual entry."""
        if not self.root:
            return _SOURCE.d6s(count)

        result_var = []

        try:
            h = 230
            dialog = tk.Toplevel(self.root)
            dialog.title("Dice Roll")
            dialog.geometry(f"420x{h}")
            dialog.transient(self.root)
            # Don't use grab_set - it conflicts with other open dialogs
            dialog.focus_set()
            dialog.lift()

            desc = description or f"{count}D6"
            tk.Label(dialog, text=f"Roll {count}D6: {desc}",
                     font=("Consolas", 10, "bold")).pack(pady=5)

            entry_frame = tk.Frame(dialog)
            entry_frame.pack(pady=5)
            tk.Label(entry_frame, text="Results:").pack(side=tk.LEFT)
            entry = tk.Entry(entry_frame, width=20, font=("Consolas", 11))
            entry.pack(side=tk.LEFT, padx=5)
            entry.focus_set()

            def on_manual():
                try:
                    vals = [int(x.strip()) for x in entry.get().split()]
                    if len(vals) == count and all(1 <= v <= 6 for v in vals):
                        result_var.extend(vals)
                        self._typed = True
                        dialog.destroy()
                    else:
                        entry.delete(0, tk.END)
                        entry.insert(0, f"Need {count} values 1-6")
                except ValueError:
                    entry.delete(0, tk.END)
                    entry.insert(0, f"Need {count} values 1-6")

            def on_auto():
                result_var.extend(_SOURCE.d6s(count))
                dialog.destroy()

            btn_frame = tk.Frame(dialog)
            btn_frame.pack(pady=5)
            tk.Button(btn_frame, text="Submit Manual", command=on_manual,
                      font=("Consolas", 10)).pack(side=tk.LEFT, padx=10)
            tk.Button(btn_frame, text="Auto-Roll (RNG)", command=on_auto,
                      font=("Consolas", 10), bg="#336633", fg="white").pack(side=tk.LEFT, padx=10)

            entry.bind("<Return>", lambda e: on_manual())
            dialog.protocol("WM_DELETE_WINDOW", on_auto)

            sep = tk.Frame(dialog, height=1, bg="#666666")
            sep.pack(fill=tk.X, padx=10, pady=4)
            succ_frame = tk.Frame(dialog)
            succ_frame.pack(pady=4)
            tk.Label(succ_frame, text=f"Successes (0–{count}):",
                     font=("Consolas", 9)).pack(side=tk.LEFT)
            succ_entry = tk.Entry(succ_frame, width=4, font=("Consolas", 11))
            succ_entry.pack(side=tk.LEFT, padx=5)

            def on_successes():
                try:
                    n = max(0, min(int(succ_entry.get()), count))
                    result_var.extend([6] * n + [1] * (count - n))
                    self._typed = True
                    dialog.destroy()
                except ValueError:
                    succ_entry.delete(0, tk.END)

            tk.Button(succ_frame, text="Use Successes", command=on_successes,
                      font=("Consolas", 9), bg="#333366", fg="white").pack(side=tk.LEFT, padx=5)
            succ_entry.bind("<Return>", lambda e: on_successes())

            self.root.wait_window(dialog)
        except Exception:
            # Fallback to auto if dialog fails
            if not result_var:
                result_var = _SOURCE.d6s(count)

        if not result_var:
            return _SOURCE.d6s(count)
        return list(result_var)

    def _mixed_2d6_input(self, description: str) -> int:
        """2D6 dialog with both per-die entry and direct sum entry alongside auto-roll."""
        result_var = [None]
        typed = [False]

        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("2D6 Roll")
            dialog.geometry("420x210")
            dialog.transient(self.root)
            dialog.focus_set()
            dialog.lift()

            tk.Label(dialog, text=description or "Roll 2D6",
                     font=("Consolas", 10, "bold"), wraplength=400).pack(pady=5)

            # Per-die entry row
            dice_frame = tk.Frame(dialog)
            dice_frame.pack(pady=4)
            tk.Label(dice_frame, text="Two dice (e.g. 3 4):",
                     font=("Consolas", 9)).pack(side=tk.LEFT)
            dice_entry = tk.Entry(dice_frame, width=8, font=("Consolas", 11))
            dice_entry.pack(side=tk.LEFT, padx=5)
            dice_entry.focus_set()

            def on_dice():
                try:
                    parts = dice_entry.get().split()
                    if len(parts) == 2:
                        a, b = int(parts[0]), int(parts[1])
                        if 1 <= a <= 6 and 1 <= b <= 6:
                            result_var[0] = a + b
                            typed[0] = True
                            dialog.destroy()
                            return
                    dice_entry.delete(0, tk.END)
                    dice_entry.insert(0, "need 2 dice 1-6")
                except ValueError:
                    dice_entry.delete(0, tk.END)

            tk.Button(dice_frame, text="Submit", command=on_dice,
                      font=("Consolas", 9)).pack(side=tk.LEFT, padx=4)
            dice_entry.bind("<Return>", lambda e: on_dice())

            # Separator
            tk.Frame(dialog, height=1, bg="#666666").pack(fill=tk.X, padx=10, pady=4)

            # Direct sum entry row
            sum_frame = tk.Frame(dialog)
            sum_frame.pack(pady=4)
            tk.Label(sum_frame, text="Sum (2–12):     ",
                     font=("Consolas", 9)).pack(side=tk.LEFT)
            sum_entry = tk.Entry(sum_frame, width=5, font=("Consolas", 11))
            sum_entry.pack(side=tk.LEFT, padx=5)

            def on_sum():
                try:
                    v = int(sum_entry.get())
                    if 2 <= v <= 12:
                        result_var[0] = v
                        typed[0] = True
                        dialog.destroy()
                except ValueError:
                    pass

            tk.Button(sum_frame, text="Submit", command=on_sum,
                      font=("Consolas", 9), bg="#333366", fg="white").pack(side=tk.LEFT, padx=4)
            sum_entry.bind("<Return>", lambda e: on_sum())

            # Auto-roll button
            def on_auto():
                result_var[0] = sum(_SOURCE.d6s(2))
                dialog.destroy()

            tk.Button(dialog, text="Auto-Roll (RNG)", command=on_auto,
                      font=("Consolas", 10), bg="#336633", fg="white").pack(pady=6)

            dialog.protocol("WM_DELETE_WINDOW", on_auto)
            self.root.wait_window(dialog)
        except Exception:
            pass

        if result_var[0] is None:
            result_var[0] = sum(_SOURCE.d6s(2))
        v = result_var[0]
        _SOURCE.note("2d6sum", 1, v, description or "2D6", "manual" if typed[0] else "auto")
        self.log.append(f"{description or '2D6'}: [sum={v}]")
        return v
