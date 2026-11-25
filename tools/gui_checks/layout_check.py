"""To do 32: the setup wizard, the fleet builder and the ship Edit dialog
show their buttons on a laptop screen (run under xvfb-run -a -s "-screen 0
1366x768x24"). Before the fix the wizard's Start buttons, the builder's Load /
Save / Validate and the Edit dialog's Save were cut off."""
import sys
import tkinter as tk

sys.path.insert(0, ".")
from src import main as M                      # noqa: E402
from src import fleet_builder as FB           # noqa: E402
from src.ship_catalog import find_ship_class  # noqa: E402

fails = []


def visible(win, names):
    win.update()
    W, H = win.winfo_width(), win.winfo_height()
    found = {}

    def walk(x):
        for c in x.winfo_children():
            if isinstance(c, tk.Button) and c.cget("text") in names:
                bx, by = c.winfo_rootx() - win.winfo_rootx(), c.winfo_rooty() - win.winfo_rooty()
                found[c.cget("text")] = (c.winfo_ismapped() and c.winfo_width() > 2
                                         and bx + c.winfo_width() <= W
                                         and by + c.winfo_height() <= H)
            walk(c)
    walk(win)
    for n in names:
        ok = found.get(n, False)
        print(f"  {'ok  ' if ok else 'FAIL'} {n}")
        if not ok:
            fails.append(n)


root = tk.Tk()
root.geometry("10x10+0+0")


def check_setup():
    for w in root.winfo_children():
        if isinstance(w, tk.Toplevel):
            print("setup wizard", w.winfo_width(), "x", w.winfo_height())
            visible(w, ["Start Game", "Open Map Editor", "Start Game, No Terrain", "Cancel"])
            w.destroy()


root.after(1200, check_setup)
M._show_setup_dialog(root)

fb = FB.FleetBuilderWindow(root)
fb.win.update()
print("fleet builder", fb.win.winfo_width(), "x", fb.win.winfo_height())
visible(fb.win, ["Load Fleet", "Save Fleet", "Validate", "Add to Fleet ▶",
                 "Add with options... ▶", "Options / Edit...", "Flagship", "Remove",
                 "Squadron selected", "Leave squadron", "Auto escort squadrons"])

for name in ("Lunar Class Cruiser", "Tyrant Class Cruiser"):
    def check_edit(name=name):
        for w in fb.win.winfo_children():
            if isinstance(w, tk.Toplevel):
                print(f"edit dialog ({name})", w.winfo_width(), "x", w.winfo_height())
                visible(w, ["Save", "Cancel"])
                w.destroy()
    root.after(800, check_edit)
    FB._ShipEditDialog(fb.win, find_ship_class(name), name, [], lambda *a: None)

print("RESULT:", "ALL OK" if not fails else f"FAILED {fails}")
sys.exit(1 if fails else 0)
