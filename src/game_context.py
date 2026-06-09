"""BFG:XR — GameContext: shared state and helper methods for all panels."""
import tkinter as tk
from typing import Optional, TYPE_CHECKING

from .models import Ship

if TYPE_CHECKING:
    from .movement_panel import MovementPanel
    from .ordnance_panel import OrdnancePanel


class GameContext:
    """
    Shared state and helper methods injected into each panel via composition.
    Holds all cross-panel dependencies so panels never import each other directly.
    """

    def __init__(self, tc, gs, dice, board, root, log_widget: tk.Text):
        self.tc = tc
        self.gs = gs
        self.dice = dice
        self.board = board
        self.root = root
        self._log_widget = log_widget

        # Panel references — wired by GamePanel after construction
        self.movement: Optional["MovementPanel"] = None
        self.ordnance: Optional["OrdnancePanel"] = None

        # LAN multiplayer transport (GameServer or GameClient, or None for local play)
        self.network = None
        # Local player number for multiplayer (1 or 2); None for local/AI play
        self.local_player: Optional[int] = None

    # ── Logging ──────────────────────────────────────────────────────────────

    def log(self, text: str):
        """Append one line to the game log widget."""
        self._log_widget.config(state=tk.NORMAL)
        self._log_widget.insert(tk.END, text + "\n")
        self._log_widget.see(tk.END)
        self._log_widget.config(state=tk.DISABLED)

    def log_lines(self, lines):
        """Append multiple lines to the game log widget."""
        for line in lines:
            self.log(line)

    # ── Ship destruction ──────────────────────────────────────────────────────

    def check_destruction(self, ship: Ship):
        """Handle ship destruction: escorts place blast markers, capitals roll catastrophic."""
        ship = self.gs.get_ship_by_id(ship.id)
        if not ship or ship.hits_remaining > 0:
            return
        from .combat import resolve_catastrophic
        result = resolve_catastrophic(ship, self.dice, self.gs)
        self.log(f"  {ship.name}: {result}")
        self.board.redraw()

    # ── Ship picker ───────────────────────────────────────────────────────────

    def pick_ship(self, ships: list, title: str) -> Optional[Ship]:
        """Show a modal list dialog and return the selected Ship, or None."""
        if len(ships) == 1:
            return ships[0]

        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("350x400")
        dialog.transient(self.root)

        tk.Label(dialog, text=title,
                 font=("Consolas", 10, "bold")).pack(pady=5)

        selected = [None]
        listbox = tk.Listbox(dialog, font=("Consolas", 9), height=15)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        for s in ships:
            status = " [CRIPPLED]" if s.is_crippled else ""
            order = f" ({s.special_order})" if s.special_order != "none" else ""
            listbox.insert(tk.END, f"{s.name} ({s.ship_class}){status}{order}")

        def on_select():
            sel = listbox.curselection()
            if sel:
                selected[0] = ships[sel[0]]
            dialog.destroy()

        listbox.bind("<Double-Button-1>", lambda e: on_select())
        tk.Button(dialog, text="Select", command=on_select,
                  font=("Consolas", 10)).pack(pady=5)

        self.root.wait_window(dialog)
        return selected[0]
