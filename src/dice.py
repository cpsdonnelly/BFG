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
            dialog = tk.Toplevel(self.root)
            dialog.title("Dice Roll")
            dialog.geometry("420x180")
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
            btn_frame.pack(pady=10)
            tk.Button(btn_frame, text="Submit Manual", command=on_manual,
                      font=("Consolas", 10)).pack(side=tk.LEFT, padx=10)
            tk.Button(btn_frame, text="Auto-Roll (RNG)", command=on_auto,
                      font=("Consolas", 10), bg="#336633", fg="white").pack(side=tk.LEFT, padx=10)

            entry.bind("<Return>", lambda e: on_manual())
            dialog.protocol("WM_DELETE_WINDOW", on_auto)

            self.root.wait_window(dialog)
        except Exception:
            # Fallback to auto if dialog fails
            if not result_var:
                result_var = [random.randint(1, 6) for _ in range(count)]

        if not result_var:
            return [random.randint(1, 6) for _ in range(count)]
        return list(result_var)
