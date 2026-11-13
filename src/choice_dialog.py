"""A modal choice prompt with an "Auto (best)" button (owner request: the
player can let the game pick the expected best option, the one the AI's
expected-value logic would take). Tk UI: main thread only."""
import tkinter as tk


def choose(root, title: str, text: str, options, best):
    """options: [(label, value), ...]; best: the value the AI logic picks.
    Returns the chosen value (closing the window takes the best one)."""
    best_label = next((lbl for lbl, v in options if v == best), str(best))
    result = {"v": best}
    win = tk.Toplevel(root)
    win.title(title)
    win.transient(root)
    tk.Label(win, text=text, justify=tk.LEFT, wraplength=440, padx=12, pady=8).pack()
    row = tk.Frame(win)
    row.pack(padx=10, pady=(0, 6))

    def pick(v):
        result["v"] = v
        win.destroy()

    for label, value in options:
        tk.Button(row, text=label, command=lambda v=value: pick(v)).pack(side=tk.LEFT, padx=3)
    tk.Button(win, text=f"Auto (best: {best_label})", bg="#335533", fg="white",
              command=lambda: pick(best)).pack(pady=(0, 10))
    win.protocol("WM_DELETE_WINDOW", lambda: pick(best))
    win.grab_set()
    root.wait_window(win)
    return result["v"]


def yes_no(root, title: str, text: str, best: bool) -> bool:
    """A yes / no question with the "Auto (best)" button (owner request):
    `best` is what the AI's expected-value logic would answer. GUI checks
    replace this function to answer it."""
    return bool(choose(root, title, text, [("Yes", True), ("No", False)], best))
