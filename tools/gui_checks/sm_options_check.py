import faulthandler, sys as _s; faulthandler.dump_traceback_later(25, exit=True)
import os, sys, json, tempfile, tkinter as tk
from tkinter import messagebox, filedialog
sys.path.insert(0, "/home/user/BFG"); os.chdir("/home/user/BFG")
from src import fleet_builder as fb
errors, infos = [], []
messagebox.showerror = lambda *a, **k: errors.append(a)
messagebox.showwarning = lambda *a, **k: errors.append(a)
messagebox.showinfo = lambda *a, **k: infos.append(a)
messagebox.askyesno = lambda *a, **k: True
fb.messagebox = messagebox
out = os.path.join(tempfile.mkdtemp(), "sm_fleet.json")
filedialog.asksaveasfilename = lambda **k: out
fb.filedialog = filedialog
failures = []
def check(c, label):
    print(("  ok   " if c else "  FAIL ") + label)
    if not c: failures.append(label)
def walk(w):
    yield w
    for c in w.winfo_children(): yield from walk(c)
root = tk.Tk(); root.withdraw()
w = fb.FleetBuilderWindow(root); root.update()
w._faction_combo.current(w._faction_ids.index("space_marines")); w._on_faction_selected(); root.update()
lst = w._catalog_list
def add(cls):
    idx = next(i for i, e in enumerate(w._catalog_entries) if e is not None and e.ship_class == cls)
    lst.selection_clear(0, tk.END); lst.selection_set(idx); w._show_catalog_entry(); w._add_selected()
add("Space Marine Battle Barge"); add("Strike Cruiser"); add("Strike Cruiser")
w._pts_limit_var.set("1500")
def edit(i, picks):
    seen = {}
    def act():
        tops = [x for x in walk(root) if isinstance(x, tk.Toplevel) and x.title().startswith("Edit")]
        if not tops:
            root.after(50, act); return
        d = tops[-1]
        rows = {}
        for c in walk(d):
            if isinstance(c, tk.Checkbutton):
                labels = [x.cget("text") for x in c.master.winfo_children() if isinstance(x, tk.Label)]
                if labels: rows[labels[0]] = c
        seen["opts"] = list(rows)
        for p in picks:
            rows[next(k for k in rows if k.startswith(p))].invoke()
        [b for b in walk(d) if isinstance(b, tk.Button) and b.cget("text") == "Save"][0].invoke()
        def cancel_if_open():
            if d.winfo_exists():
                [b for b in walk(d) if isinstance(b, tk.Button) and b.cget("text") == "Cancel"][0].invoke()
        root.after(50, cancel_if_open)
    root.after(50, act)
    w._fleet_list.selection_clear(0, tk.END); w._fleet_list.selection_set(i)
    w._edit_selected(); root.update()
    return seen.get("opts", [])
print("1. Battle barge options; a re-roll without the Master of the Fleet is refused")
opts = edit(0, ["Master of the Fleet: 2"])
print("   options:", opts)
check(any("Master of the Fleet (Ld 10)" in o for o in opts), "Master of the Fleet listed")
check(errors and "needs Master of the Fleet" in errors[-1][1], "refused without the Master of the Fleet")
errors.clear()
for t in [x for x in walk(root) if isinstance(x, tk.Toplevel)][1:]:
    pass
print("2. Master of the Fleet + 2 re-rolls + Terminator honour guard; strike cruiser variants")
# close any open edit dialog left from the refused save
edit(0, ["Master of the Fleet (Ld 10)", "Master of the Fleet: 2", "Master of the Fleet: Terminator"])
edit(1, ["Variant: prow torpedoes", "Secondary Shield"])
check(not errors, f"saved without errors {errors}")
w._validate_and_report(); root.update()
check(infos and "valid" in infos[-1][1].lower(), f"fleet valid {infos[-1:] or errors[-1:]}")
print("3. Second strike cruiser also takes a variant: over the half limit")
edit(2, ["Variant: macrobatteries"])
errors.clear(); w._validate_and_report(); root.update()
check(errors and "Strike Cruiser Variants" in errors[-1][1], f"refused: {errors[-1][1][:90] if errors else None}")
edit(2, ["Variant: macrobatteries"])   # untick again
errors.clear()
w._save_fleet()
saved = json.load(open(out))
from src.fleet_builder import fleet_list_to_ships
ships = fleet_list_to_ships(saved, 1)
bb = ships[0]; sc = ships[1]
print("   barge:", bb["leadership"], bb["leadership_table"], bb["rerolls_remaining"], bb["is_flagship"], bb["points_value"])
check(bb["leadership"] == 10 and bb["rerolls_remaining"] == 2 and bb["is_flagship"]
      and "terminator_honour_guard" in bb["special_rules"], "Master of the Fleet ship loads with Ld 10, 2 re-rolls, flagship, honour guard")
check(any(x["name"] == "Prow Torps" for x in sc["weapons"]) and sc["shields_max"] == 2, "variant strike cruiser loads with torps and 2 shields")
print("RESULT:", "ALL OK" if not failures else f"FAILURES: {failures}")
