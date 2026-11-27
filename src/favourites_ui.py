"""The favourites prompt (To do 27; a minimal Tk version, owner: the full one
is built once, in the browser)."""
import tkinter as tk


def offer_favourites(root, files: dict, names: dict, on_done=None) -> None:
    """Ask which of the fleets played to save to the favourites, then call
    on_done(). files {player: path}, names {player: fleet name}."""
    from .favourites import to_offer, save_favourite
    offer = to_offer(files)
    if not offer:
        if on_done:
            on_done()
        return
    dlg = tk.Toplevel(root)
    dlg.title("Favourite fleets")
    dlg.transient(root)
    tk.Label(dlg, text="Save fleets to your favourites?", font=("Consolas", 10, "bold")
             ).pack(padx=12, pady=6)
    picks = {}
    for p, path in offer.items():
        picks[p] = tk.BooleanVar(value=False)
        tk.Checkbutton(dlg, text=f"Player {p}: {names.get(p) or path}", variable=picks[p],
                       font=("Consolas", 9)).pack(anchor=tk.W, padx=14)

    def finish(save: bool):
        saved = [save_favourite(offer[p]) for p, v in picks.items() if save and v.get()]
        dlg.destroy()
        if saved:
            print("Saved to favourites:", ", ".join(saved))
        if on_done:
            on_done()
    row = tk.Frame(dlg)
    row.pack(pady=8)
    tk.Button(row, text="Save", command=lambda: finish(True),
              font=("Consolas", 9)).pack(side=tk.LEFT, padx=4)
    tk.Button(row, text="Don't save", command=lambda: finish(False),
              font=("Consolas", 9)).pack(side=tk.LEFT, padx=4)
    dlg.protocol("WM_DELETE_WINDOW", lambda: finish(False))
