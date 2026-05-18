"""BFG:XR Dice System - Manual input, auto RNG, or mixed"""
import random
from typing import List, Optional, Callable

try:
    import tkinter as tk
    from tkinter import simpledialog
    HAS_TK = True
except ImportError:
    HAS_TK = False
    tk = None


class DiceRoller:
    """Handles all dice rolling with configurable input mode."""

    def __init__(self, mode: str = "auto", root=None):
        """
        mode: "auto" (computer RNG), "manual" (player types results),
              "mixed" (popup asks each time with auto-resolve button)
        """
        self.mode = mode
        self.root = root
        self.log: List[str] = []
        self.simplified_input: bool = False

    def roll_d6(self, count: int = 1, description: str = "",
                allow_reroll: bool = False) -> List[int]:
        """Roll count D6 dice. Returns list of results."""
        if count <= 0:
            return []

        if self.mode == "auto":
            results = [random.randint(1, 6) for _ in range(count)]
        elif self.mode == "manual":
            results = self._manual_input(count, description)
        else:  # mixed
            results = self._mixed_input(count, description)

        desc = description or f"{count}D6"
        self.log.append(f"{desc}: {results} (sum={sum(results)})")
        return results

    def roll_2d6(self, description: str = "") -> int:
        """Roll 2D6 and return the sum."""
        if self.mode == "mixed" and self.root:
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
        angle = random.uniform(0, 360)
        self.log.append(f"  -> Scatter direction: {angle:.0f}°")
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
            return [random.randint(1, 6) for _ in range(count)]

        prompt = f"Roll {count}D6"
        if description:
            prompt += f" for: {description}"
        prompt += f"\nEnter {count} results separated by spaces (1-6):"

        while True:
            result_str = simpledialog.askstring("Dice Roll", prompt, parent=self.root)
            if result_str is None:
                # User cancelled, auto-resolve
                return [random.randint(1, 6) for _ in range(count)]
            try:
                values = [int(x.strip()) for x in result_str.split()]
                if len(values) == count and all(1 <= v <= 6 for v in values):
                    return values
                elif len(values) == 1 and count == 1:
                    if 1 <= values[0] <= 6:
                        return values
            except ValueError:
                pass
            prompt = f"Invalid input. Need {count} numbers from 1-6.\nTry again:"

    def _mixed_input(self, count: int, description: str) -> List[int]:
        """Show popup with auto-resolve button or manual entry."""
        if not self.root:
            return [random.randint(1, 6) for _ in range(count)]

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
                        dialog.destroy()
                    else:
                        entry.delete(0, tk.END)
                        entry.insert(0, f"Need {count} values 1-6")
                except ValueError:
                    entry.delete(0, tk.END)
                    entry.insert(0, f"Need {count} values 1-6")

            def on_auto():
                result_var.extend([random.randint(1, 6) for _ in range(count)])
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
                result_var = [random.randint(1, 6) for _ in range(count)]

        if not result_var:
            return [random.randint(1, 6) for _ in range(count)]
        return list(result_var)

    def _mixed_2d6_input(self, description: str) -> int:
        """2D6 dialog with both per-die entry and direct sum entry alongside auto-roll."""
        result_var = [None]

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
                        dialog.destroy()
                except ValueError:
                    pass

            tk.Button(sum_frame, text="Submit", command=on_sum,
                      font=("Consolas", 9), bg="#333366", fg="white").pack(side=tk.LEFT, padx=4)
            sum_entry.bind("<Return>", lambda e: on_sum())

            # Auto-roll button
            def on_auto():
                result_var[0] = random.randint(1, 6) + random.randint(1, 6)
                dialog.destroy()

            tk.Button(dialog, text="Auto-Roll (RNG)", command=on_auto,
                      font=("Consolas", 10), bg="#336633", fg="white").pack(pady=6)

            dialog.protocol("WM_DELETE_WINDOW", on_auto)
            self.root.wait_window(dialog)
        except Exception:
            pass

        if result_var[0] is None:
            result_var[0] = random.randint(1, 6) + random.randint(1, 6)
        v = result_var[0]
        self.log.append(f"{description or '2D6'}: [sum={v}]")
        return v
