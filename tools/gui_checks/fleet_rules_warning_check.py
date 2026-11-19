"""Owner request: starting a game with a fleet that relies on an optional rule
switched off (here the Dark Eldar Impalers, hit-and-run off) asks first. Clicks
the setup wizard's Start Game with the owner's Dark Eldar fleet and checks the
question, then that "Yes" turns the rule on and "Cancel" stays in the wizard.
Run: xvfb-run -a /usr/bin/python3.12 tools/gui_checks/fleet_rules_warning_check.py"""
import os
import sys
import tkinter as tk
from tkinter import messagebox

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
import src.main as M  # noqa: E402

DE = "data/fleets/owner_dark_eldar_1000.json"
M.get_available_fleets = lambda _d: [DE, "data/fleets/owner_gothic_1000.json"]


def run(answer):
    asked = []

    def ask(title, text, **_k):
        asked.append(text)
        return answer
    messagebox.askyesnocancel = ask
    root = tk.Tk()
    root.withdraw()
    out = {}

    def press():
        for w in _walk(root):
            if isinstance(w, tk.Button) and w.cget("text") == "Start Game":
                w.invoke()
                break
        # still open after Cancel: close it
        for w in root.winfo_children():
            if isinstance(w, tk.Toplevel) and w.winfo_exists():
                w.destroy()
    root.after(300, press)
    out["setup"] = M._show_setup_dialog(root)
    root.destroy()
    return asked, out["setup"]


def _walk(w):
    yield w
    for c in w.winfo_children():
        yield from _walk(c)


ok = True
asked, setup = run(True)
ok &= bool(asked) and "Impalers" in asked[0] and "Hit and Run Raids" in asked[0]
ok &= bool(setup) and setup.get("rule_hit_and_run") is True
print("Yes ->", "asked" if asked else "NOT ASKED", "rule_hit_and_run =", (setup or {}).get("rule_hit_and_run"))
asked, setup = run(None)
ok &= bool(asked) and setup is None
print("Cancel ->", "stayed in the wizard" if setup is None else "STARTED")
asked, setup = run(False)
ok &= bool(setup) and setup.get("rule_hit_and_run") is False
print("No ->", "started with raids off" if setup and not setup.get("rule_hit_and_run") else "WRONG")
print("RESULT:", "ALL OK" if ok else "FAILED")
sys.exit(0 if ok else 1)
