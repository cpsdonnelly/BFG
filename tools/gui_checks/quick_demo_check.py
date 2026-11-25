"""To do 26: the setup wizard's Quick Demo makes a Cruiser Clash on random
terrain with the fleets and mode chosen (a random fleet built by the list
builder for Player 2), and the game starts from it."""
import os
import sys
import tkinter as tk
from tkinter import messagebox

sys.path.insert(0, ".")
import src.main as M                                         # noqa: E402

messagebox.askyesnocancel = lambda *a, **k: False          # rules prompt: start anyway
root = tk.Tk()
root.withdraw()


def press(widget, text):
    for w in widget.winfo_children():
        if isinstance(w, tk.Button) and w.cget("text") == text:
            w.invoke()
            return True
        if press(w, text):
            return True
    return False


def drive():
    wiz = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)][0]
    press(wiz, "Quick Demo...")
    root.update()
    dlg = [w for w in wiz.winfo_children() if isinstance(w, tk.Toplevel)][-1]
    # Player 2: random fleet, mode AI vs AI
    opts = [w for f in dlg.winfo_children() if isinstance(f, tk.Frame)
            for w in f.winfo_children() if isinstance(w, tk.OptionMenu)]
    var_name = opts[1].cget("textvariable")
    root.setvar(var_name, "random")
    for w in dlg.winfo_children():
        if isinstance(w, tk.Radiobutton) and w.cget("text") == "AI vs AI":
            w.invoke()
    press(dlg, "Start")


root.after(500, drive)
setup = M._show_setup_dialog(root)
ok = (setup is not None and setup["scenario_mode"] == "cruiser_clash"
      and setup["terrain"] == "random" and setup["ai_spectator"]
      and "random" in os.path.basename(setup["p2_fleet"]) and os.path.exists(setup["p2_fleet"]))
print("  setup:", {k: setup.get(k) for k in ("scenario_mode", "terrain", "battlezone",
                                              "ai_spectator", "p1_fleet", "p2_fleet")}
      if setup else None)
root.destroy()
print("RESULT:", "OK" if ok else "FAILED")
sys.exit(0 if ok else 1)
