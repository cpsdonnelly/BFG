"""BFG:XR Simulator - Main Entry Point"""
import sys
import os
import tkinter as tk
from tkinter import filedialog
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import Phenomenon
from src.game_state import GameState
from src.board_view import BoardView
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.fleet_loader import (load_fleet_file, fleet_to_ships,
                               get_available_fleets, get_fleet_info,
                               find_unofficial_ships)
from src.fleet_builder import FleetBuilderWindow





def _apply_rules(gs, setup):
    """Apply optional rule settings from setup dict to GameState."""
    for key in ("rule_fighting_sunward", "rule_solar_flares", "rule_radiation_bursts",
                 "rule_boarding", "rule_ramming", "rule_teleport", "rule_hit_and_run",
                 "rule_turret_suppression_remastered", "allow_movement_pass",
                 "turn_limit", "ftl_available_turn", "scenario_mode",
                 "scenario_attacker", "artefact_submode",
                 "ai_player", "ai_difficulty"):
        if key in setup:
            setattr(gs, key, setup[key])
    # Place artefact token at board centre for race mode
    if setup.get("scenario_mode") == "capture_artefact" and setup.get("artefact_submode") == "race":
        gs.artefact_token_pos = (gs.table_width / 2, gs.table_height / 2)


def _load_fleet_checked(path: str, player: int, root):
    """Load fleet and warn via messagebox if any ship classes are not in the catalog."""
    from tkinter import messagebox
    fleet_data = load_fleet_file(path)
    unofficial = find_unofficial_ships(fleet_data)
    if unofficial:
        messagebox.showwarning(
            "Unofficial Ships Detected",
            f"The following ship class(es) in player {player}'s fleet are not in "
            f"the official catalog or homebrew catalog:\n\n"
            + "\n".join(f"  • {sc}" for sc in unofficial)
            + "\n\nThey will be loaded with default stats.",
            parent=root,
        )
    return fleet_to_ships(fleet_data, player)


def main():
    # Launch setup dialog
    root = tk.Tk()
    root.withdraw()  # hide main window during setup

    setup = _show_setup_dialog(root)
    if setup is None:
        root.destroy()
        return

    if setup["mode"] == "demo":
        p1_info = get_fleet_info(setup["p1_fleet"])
        p2_info = get_fleet_info(setup["p2_fleet"])
        gs = GameState(
            game_name="fleet_battle",
            table_width=setup.get("width", 120),
            table_height=setup.get("height", 120),
            player1_name=p1_info["fleet_name"],
            player2_name=p2_info["fleet_name"],
            player1_faction=p1_info["faction"],
            player2_faction=p2_info["faction"],
            player1_color="red",
            player2_color="blue",
            points_limit=int(p1_info["total_points"]) if p1_info["total_points"].isdigit() else 800,
            dice_mode=setup.get("dice_mode", "mixed"),
            sunward_edge=setup.get("sunward", "north"),
        )
        _apply_rules(gs, setup)
        for ship in _load_fleet_checked(setup["p1_fleet"], 1, root):
            gs.add_ship(ship)
        for ship in _load_fleet_checked(setup["p2_fleet"], 2, root):
            gs.add_ship(ship)

        if setup.get("terrain") == "random":
            from .map_maker import generate_random_map
            dice = DiceRoller(mode="auto")
            phenomena = generate_random_map(
                gs.table_width, gs.table_height,
                setup.get("battlezone", 4), dice)
            for p in phenomena:
                gs.add_phenomenon(Phenomenon.from_dict(p))
        elif setup.get("terrain") == "demo":
            gs.add_phenomenon(Phenomenon(
                id="asteroid1", phenomenon_type="asteroid_field",
                x=25, y=60, width=20, height=15))
            gs.add_phenomenon(Phenomenon(
                id="dust1", phenomenon_type="gas_dust_cloud",
                x=95, y=55, width=18, height=12))
            gs.add_phenomenon(Phenomenon(
                id="planet1", phenomenon_type="planet_medium",
                x=60, y=60, radius=5))
        # else: blank board

    elif setup["mode"] == "blank":
        p1_info = get_fleet_info(setup["p1_fleet"])
        p2_info = get_fleet_info(setup["p2_fleet"])
        gs = GameState(
            game_name="custom_game",
            table_width=setup.get("width", 120),
            table_height=setup.get("height", 120),
            player1_name=p1_info["fleet_name"],
            player2_name=p2_info["fleet_name"],
            player1_faction=p1_info["faction"],
            player2_faction=p2_info["faction"],
            player1_color="red",
            player2_color="blue",
            dice_mode=setup.get("dice_mode", "mixed"),
            sunward_edge=setup.get("sunward", "north"),
        )
        _apply_rules(gs, setup)
        for ship in _load_fleet_checked(setup["p1_fleet"], 1, root):
            gs.add_ship(ship)
        for ship in _load_fleet_checked(setup["p2_fleet"], 2, root):
            gs.add_ship(ship)

    elif setup["mode"] == "editor":
        # Launch map editor first
        editor_root = tk.Toplevel(root)
        from .map_editor import MapEditor
        editor = MapEditor(
            editor_root,
            table_width=setup.get("width", 120),
            table_height=setup.get("height", 120),
            sunward=setup.get("sunward", "north"))
        editor_root.mainloop()

        # Get map from editor
        map_phenomena = editor.get_phenomena()
        map_settings = editor.get_map_settings()
        editor_root.destroy()

        # Create game with editor map
        p1_info = get_fleet_info(setup["p1_fleet"])
        p2_info = get_fleet_info(setup["p2_fleet"])
        gs = GameState(
            game_name="custom_game",
            table_width=map_settings["table_width"],
            table_height=map_settings["table_height"],
            player1_name=p1_info["fleet_name"],
            player2_name=p2_info["fleet_name"],
            player1_faction=p1_info["faction"],
            player2_faction=p2_info["faction"],
            player1_color="red",
            player2_color="blue",
            points_limit=int(p1_info["total_points"]) if p1_info["total_points"].isdigit() else 800,
            dice_mode=setup.get("dice_mode", "mixed"),
            sunward_edge=map_settings["sunward_edge"],
        )
        _apply_rules(gs, setup)
        for ship in _load_fleet_checked(setup["p1_fleet"], 1, root):
            gs.add_ship(ship)
        for ship in _load_fleet_checked(setup["p2_fleet"], 2, root):
            gs.add_ship(ship)
        for p in map_phenomena:
            gs.add_phenomenon(Phenomenon.from_dict(p))

    else:
        gs = GameState(
            game_name="custom_game",
            table_width=120, table_height=120,
            dice_mode="mixed",
        )
        p1_fleet = setup.get("p1_fleet")
        p2_fleet = setup.get("p2_fleet")
        if p1_fleet:
            for ship in _load_fleet_checked(p1_fleet, 1, root):
                gs.add_ship(ship)
        if p2_fleet:
            for ship in _load_fleet_checked(p2_fleet, 2, root):
                gs.add_ship(ship)

    # Create turn controller and dice
    dice = DiceRoller(mode=gs.dice_mode)
    tc = TurnController(gs, dice)

    # Show main window
    root.deiconify()
    board = BoardView(root, gs)

    game_frame = tk.Frame(board.side_panel, bg="#1a1a2e")
    game_frame.pack(fill=tk.BOTH, expand=True)
    board.info_text.config(height=10)

    from .game_panel import GamePanel
    game_panel = GamePanel(game_frame, tc, board, root)

    root.mainloop()


def _show_setup_dialog(root) -> Optional[dict]:
    """Show game setup dialog. Returns config dict or None if cancelled."""
    result = [None]

    dialog = tk.Toplevel(root)
    dialog.title("BFG:XR - Game Setup")
    dialog.geometry("540x680")
    dialog.protocol("WM_DELETE_WINDOW", lambda: (result.__setitem__(0, None), dialog.destroy()))

    tk.Label(dialog, text="BATTLEFLEET GOTHIC: XR",
             font=("Consolas", 14, "bold")).pack(pady=10)
    tk.Label(dialog, text="Game Setup",
             font=("Consolas", 10)).pack()

    # Board size
    size_frame = tk.Frame(dialog)
    size_frame.pack(pady=5, padx=20, fill=tk.X)
    tk.Label(size_frame, text="Board size (cm):", font=("Consolas", 9)).pack(side=tk.LEFT)
    width_var = tk.StringVar(value="120")
    height_var = tk.StringVar(value="120")
    tk.Entry(size_frame, textvariable=width_var, width=5, font=("Consolas", 10)).pack(side=tk.LEFT, padx=3)
    tk.Label(size_frame, text="x", font=("Consolas", 9)).pack(side=tk.LEFT)
    tk.Entry(size_frame, textvariable=height_var, width=5, font=("Consolas", 10)).pack(side=tk.LEFT, padx=3)

    # Sunward edge
    sun_frame = tk.Frame(dialog)
    sun_frame.pack(pady=3, padx=20, fill=tk.X)
    tk.Label(sun_frame, text="Sunward edge:", font=("Consolas", 9)).pack(side=tk.LEFT)
    sunward_var = tk.StringVar(value="north")
    for edge in ["north", "south", "east", "west"]:
        tk.Radiobutton(sun_frame, text=edge.capitalize(), variable=sunward_var,
                       value=edge, font=("Consolas", 8)).pack(side=tk.LEFT, padx=3)

    # Dice mode
    dice_frame = tk.Frame(dialog)
    dice_frame.pack(pady=3, padx=20, fill=tk.X)
    tk.Label(dice_frame, text="Dice mode:", font=("Consolas", 9)).pack(side=tk.LEFT)
    dice_var = tk.StringVar(value="mixed")
    for mode in [("Mixed", "mixed"), ("Auto", "auto"), ("Manual", "manual")]:
        tk.Radiobutton(dice_frame, text=mode[0], variable=dice_var,
                       value=mode[1], font=("Consolas", 8)).pack(side=tk.LEFT, padx=3)

    # Terrain
    terrain_frame = tk.Frame(dialog)
    terrain_frame.pack(pady=5, padx=20, fill=tk.X)
    tk.Label(terrain_frame, text="Terrain:", font=("Consolas", 9, "bold")).pack(anchor=tk.W)
    terrain_var = tk.StringVar(value="demo")
    for label, val in [("Demo terrain (asteroid, dust, planet)", "demo"),
                       ("Random generation", "random"),
                       ("Blank board", "blank")]:
        tk.Radiobutton(terrain_frame, text=label, variable=terrain_var,
                       value=val, font=("Consolas", 8)).pack(anchor=tk.W)

    # Battlezone (for random)
    bz_frame = tk.Frame(dialog)
    bz_frame.pack(pady=3, padx=20, fill=tk.X)
    tk.Label(bz_frame, text="Battlezone (for random):", font=("Consolas", 9)).pack(side=tk.LEFT)
    bz_var = tk.StringVar(value="4")
    for i, name in [(1, "Flare"), (2, "Mercurial"), (3, "Inner"),
                    (4, "Primary"), (5, "Outer"), (6, "Deep Space")]:
        tk.Radiobutton(bz_frame, text=name, variable=bz_var,
                       value=str(i), font=("Consolas", 7)).pack(side=tk.LEFT)

    # Fleet selection
    fleets_frame = tk.Frame(dialog)
    fleets_frame.pack(pady=5, padx=20, fill=tk.X)
    tk.Label(fleets_frame, text="Fleet Lists:", font=("Consolas", 9, "bold")).pack(anchor=tk.W)

    available_fleets = get_available_fleets("data/fleets")
    fleet_labels = {p: get_fleet_info(p)["fleet_name"] for p in available_fleets}
    fleet_display = [fleet_labels.get(p, os.path.basename(p)) for p in available_fleets]

    _imp_default = next((p for p in available_fleets if "imperial" in os.path.basename(p).lower()),
                        available_fleets[0] if available_fleets else "")
    _tau_default = next((p for p in available_fleets if "tau" in os.path.basename(p).lower()),
                        available_fleets[-1] if available_fleets else "")

    p1_fleet_var = tk.StringVar(value=_imp_default)
    p2_fleet_var = tk.StringVar(value=_tau_default)

    def _make_fleet_row(parent, label_text, fleet_var):
        row = tk.Frame(parent)
        row.pack(fill=tk.X, pady=2)
        tk.Label(row, text=label_text, font=("Consolas", 9), width=10, anchor=tk.W).pack(side=tk.LEFT)
        if available_fleets:
            opt = tk.OptionMenu(row, fleet_var, *available_fleets,
                                command=lambda _: None)
            opt.config(font=("Consolas", 8), width=28)
            opt["menu"].config(font=("Consolas", 8))
            # Update OptionMenu display to show fleet_name not path
            for i, path in enumerate(available_fleets):
                opt["menu"].entryconfig(i, label=fleet_labels.get(path, os.path.basename(path)))
            opt.pack(side=tk.LEFT, padx=3)
        else:
            tk.Label(row, text="No fleet files found in data/fleets/",
                     font=("Consolas", 8), fg="#cc4444").pack(side=tk.LEFT)

        def _browse(fv=fleet_var):
            path = filedialog.askopenfilename(
                parent=dialog, title="Select Fleet File",
                initialdir="data/fleets",
                filetypes=[("Fleet JSON", "*.json"), ("All Files", "*")])
            if path:
                fv.set(path)
        tk.Button(row, text="Browse...", font=("Consolas", 8),
                  command=_browse).pack(side=tk.LEFT, padx=3)

        def _open_builder(fv=fleet_var):
            def on_save(_data, saved_path):
                fv.set(saved_path)
            FleetBuilderWindow.open(dialog, on_save=on_save)
        tk.Button(row, text="Build...", font=("Consolas", 8),
                  command=_open_builder).pack(side=tk.LEFT, padx=3)

    _make_fleet_row(fleets_frame, "Player 1:", p1_fleet_var)
    _make_fleet_row(fleets_frame, "Player 2:", p2_fleet_var)
    tk.Label(fleets_frame,
             text="Fleet files live in data/fleets/ — copy or create JSON files there to add fleets.",
             font=("Consolas", 7), fg="#888888", wraplength=480, justify=tk.LEFT).pack(anchor=tk.W)

    # Optional rules
    rules_frame = tk.Frame(dialog)
    rules_frame.pack(pady=5, padx=20, fill=tk.X)
    tk.Label(rules_frame, text="Optional Rules:", font=("Consolas", 9, "bold")).pack(anchor=tk.W)

    rule_vars = {}
    rules_list = [
        ("fighting_sunward", "Fighting Sunward (double range shifts)", False),
        ("solar_flares", "Solar Flares", False),
        ("radiation_bursts", "Radiation Bursts", False),
        ("boarding", "Boarding Actions", False),
        ("ramming", "Ramming", False),
        ("teleport", "Teleport Attacks (not Tau)", False),
        ("hit_and_run", "Hit and Run Raids", False),
        ("turret_suppression_remastered",
         "Turret Suppression: Remastered mode (default: XR — fighters give 3 fixed attacks)", False),
    ]
    for key, label, default in rules_list:
        var = tk.BooleanVar(value=default)
        rule_vars[key] = var
        tk.Checkbutton(rules_frame, text=label, variable=var,
                       font=("Consolas", 8)).pack(anchor=tk.W)

    # Movement enforcement setting
    movement_frame = tk.Frame(dialog)
    movement_frame.pack(pady=5, padx=20, fill=tk.X)
    tk.Label(movement_frame, text="Movement Enforcement:",
             font=("Consolas", 9, "bold")).pack(anchor=tk.W)
    allow_pass_var = tk.BooleanVar(value=False)
    tk.Checkbutton(movement_frame,
                   text="Allow movement pass (players may skip moving ships without penalty)",
                   variable=allow_pass_var,
                   font=("Consolas", 8)).pack(anchor=tk.W)
    tk.Label(movement_frame,
             text="Default OFF: ending the movement phase with unmoved ships is blocked.",
             font=("Consolas", 7), fg="#888888").pack(anchor=tk.W)

    # Turn limit and FTL charge
    turn_frame = tk.Frame(dialog)
    turn_frame.pack(pady=4, padx=20, fill=tk.X)
    tk.Label(turn_frame, text="Game Options:", font=("Consolas", 9, "bold")).pack(anchor=tk.W)

    tl_row = tk.Frame(turn_frame)
    tl_row.pack(anchor=tk.W)
    tk.Label(tl_row, text="Turn Limit:", font=("Consolas", 8)).pack(side=tk.LEFT)
    turn_limit_var = tk.StringVar(value="5")
    tk.Entry(tl_row, textvariable=turn_limit_var, width=4,
             font=("Consolas", 9)).pack(side=tk.LEFT, padx=3)
    tk.Label(tl_row, text="(blank = unlimited, default 5)",
             font=("Consolas", 7), fg="#888888").pack(side=tk.LEFT)

    ftl_row = tk.Frame(turn_frame)
    ftl_row.pack(anchor=tk.W)
    tk.Label(ftl_row, text="FTL Charge Turn:", font=("Consolas", 8)).pack(side=tk.LEFT)
    ftl_turn_var = tk.StringVar(value="")
    tk.Entry(ftl_row, textvariable=ftl_turn_var, width=4,
             font=("Consolas", 9)).pack(side=tk.LEFT, padx=3)
    tk.Label(ftl_row, text="(blank = FTL always available)",
             font=("Consolas", 7), fg="#888888").pack(side=tk.LEFT)

    # Scenario mode
    scen_frame = tk.LabelFrame(dialog, text="Scenario Mode", font=("Consolas", 9, "bold"),
                                padx=8, pady=4)
    scen_frame.pack(fill=tk.X, padx=20, pady=4)
    scenario_var = tk.StringVar(value="standard")

    scenario_options = [
        ("standard",          "Standard (all ships / turn limit)"),
        ("kill_admiral",      "Kill the Admiral (destroy enemy flagship)"),
        ("destroy_ship",      "Destroy / Protect a Ship"),
        ("capture_artefact",  "Capture the Artefact"),
    ]
    for val, lbl in scenario_options:
        tk.Radiobutton(scen_frame, text=lbl, variable=scenario_var, value=val,
                       font=("Consolas", 8)).pack(anchor=tk.W)

    tk.Label(scen_frame,
             text="For Destroy/Protect and Capture modes, set objective ship ID in-game\n"
                  "via the settings panel after starting.",
             font=("Consolas", 7), fg="#888888", justify=tk.LEFT).pack(anchor=tk.W)

    # Capture artefact sub-options
    artefact_frame = tk.Frame(scen_frame)
    artefact_frame.pack(anchor=tk.W, padx=10)
    artefact_submode_var = tk.StringVar(value="race")
    tk.Label(artefact_frame, text="Sub-mode:", font=("Consolas", 7)).pack(side=tk.LEFT)
    tk.Radiobutton(artefact_frame, text="Race (neutral token)",
                   variable=artefact_submode_var, value="race",
                   font=("Consolas", 7)).pack(side=tk.LEFT)
    tk.Radiobutton(artefact_frame, text="Carrier Escape",
                   variable=artefact_submode_var, value="carrier_escape",
                   font=("Consolas", 7)).pack(side=tk.LEFT)

    scenario_attacker_var = tk.StringVar(value="1")
    att_row = tk.Frame(scen_frame)
    att_row.pack(anchor=tk.W, padx=10)
    tk.Label(att_row, text="Attacker:", font=("Consolas", 7)).pack(side=tk.LEFT)
    tk.Radiobutton(att_row, text="Player 1", variable=scenario_attacker_var,
                   value="1", font=("Consolas", 7)).pack(side=tk.LEFT)
    tk.Radiobutton(att_row, text="Player 2", variable=scenario_attacker_var,
                   value="2", font=("Consolas", 7)).pack(side=tk.LEFT)

    # AI opponent
    ai_frame = tk.LabelFrame(dialog, text="AI Opponent", font=("Consolas", 9, "bold"),
                              padx=8, pady=4)
    ai_frame.pack(fill=tk.X, padx=20, pady=4)
    ai_enabled_var = tk.BooleanVar(value=False)
    tk.Checkbutton(ai_frame, text="Enable AI opponent (controls Player 2)",
                   variable=ai_enabled_var,
                   font=("Consolas", 8)).pack(anchor=tk.W)
    diff_row = tk.Frame(ai_frame)
    diff_row.pack(anchor=tk.W, padx=10)
    tk.Label(diff_row, text="Difficulty:", font=("Consolas", 8)).pack(side=tk.LEFT)
    ai_diff_var = tk.StringVar(value="normal")
    for lbl, val in [("Easy", "easy"), ("Normal", "normal"), ("Hard", "hard")]:
        tk.Radiobutton(diff_row, text=lbl, variable=ai_diff_var, value=val,
                       font=("Consolas", 8)).pack(side=tk.LEFT, padx=4)
    tk.Label(ai_frame,
             text="Easy: random targets, no orders  "
                  "Normal: weakest target, situational orders  "
                  "Hard: focus-fire crippled ships",
             font=("Consolas", 7), fg="#888888", justify=tk.LEFT,
             wraplength=440).pack(anchor=tk.W)

    def _get_rules():
        rules = {f"rule_{k}": v.get() for k, v in rule_vars.items()}
        rules["allow_movement_pass"] = allow_pass_var.get()
        tl = turn_limit_var.get().strip()
        rules["turn_limit"] = int(tl) if tl.isdigit() else None
        ftl = ftl_turn_var.get().strip()
        rules["ftl_available_turn"] = int(ftl) if ftl.isdigit() else None
        rules["scenario_mode"] = scenario_var.get()
        rules["scenario_attacker"] = int(scenario_attacker_var.get())
        rules["artefact_submode"] = artefact_submode_var.get()
        # In carrier_escape mode, enforce FTL charge of at least 3 if not set
        if (rules["scenario_mode"] == "capture_artefact"
                and rules["artefact_submode"] == "carrier_escape"
                and rules["ftl_available_turn"] is None):
            rules["ftl_available_turn"] = 3
        rules["ai_player"] = 2 if ai_enabled_var.get() else None
        rules["ai_difficulty"] = ai_diff_var.get()
        return rules

    def _get_fleets():
        return {"p1_fleet": p1_fleet_var.get(), "p2_fleet": p2_fleet_var.get()}

    # Buttons
    def start_demo():
        result[0] = {
            "mode": "demo",
            "width": float(width_var.get()),
            "height": float(height_var.get()),
            "sunward": sunward_var.get(),
            "dice_mode": dice_var.get(),
            "terrain": terrain_var.get(),
            "battlezone": int(bz_var.get()),
            **_get_rules(),
            **_get_fleets(),
        }
        dialog.destroy()

    def start_blank():
        result[0] = {
            "mode": "blank",
            "width": float(width_var.get()),
            "height": float(height_var.get()),
            "sunward": sunward_var.get(),
            "dice_mode": dice_var.get(),
            **_get_rules(),
            **_get_fleets(),
        }
        dialog.destroy()

    def start_editor():
        result[0] = {
            "mode": "editor",
            "width": float(width_var.get()),
            "height": float(height_var.get()),
            "sunward": sunward_var.get(),
            "dice_mode": dice_var.get(),
            **_get_rules(),
            **_get_fleets(),
        }
        dialog.destroy()

    btn_frame = tk.Frame(dialog)
    btn_frame.pack(pady=15)
    tk.Button(btn_frame, text="Start Game (Demo Fleets)",
              command=start_demo,
              bg="#336633", fg="white",
              font=("Consolas", 10, "bold")).pack(pady=3, fill=tk.X)
    tk.Button(btn_frame, text="Open Map Editor",
              command=start_editor,
              bg="#335533", fg="white",
              font=("Consolas", 9)).pack(pady=3, fill=tk.X)
    tk.Button(btn_frame, text="Start Blank (Demo Fleets, No Terrain)",
              command=start_blank,
              font=("Consolas", 9)).pack(pady=3, fill=tk.X)
    tk.Button(btn_frame, text="Cancel",
              command=lambda: (result.__setitem__(0, None), dialog.destroy()),
              font=("Consolas", 9)).pack(pady=3)

    root.wait_window(dialog)
    return result[0]


if __name__ == "__main__":
    main()
