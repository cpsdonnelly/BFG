"""BFG:XR Simulator - Main Entry Point"""
import sys
import os
import tkinter as tk
from tkinter import filedialog
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.models import Ship, Phenomenon
from src.game_state import GameState
from src.board_view import BoardView
from src.dice import DiceRoller
from src.turn_controller import TurnController
from src.fleet_loader import load_fleet_file, fleet_to_ships, get_available_fleets, get_fleet_info


def create_demo_imperial_fleet(gs: GameState):
    """Create the Imperial Navy 800pt fleet"""

    # INS Throne Eternal - Mars Class Battlecruiser (Flagship)
    mars = Ship(
        id="imp_mars", name="INS Throne Eternal",
        ship_class="Mars Class Battlecruiser", faction="imperial_navy",
        player=1, ship_type="cruiser", base_size="small",
        x=60, y=15, heading=90,
        speed=20, turn_angle=45, shields_max=2,
        armor_prow="6+", armor_side="5+", turrets=2, hits_max=8,
        leadership=8, is_flagship=True, admiral_type="Vice Admiral",
        rerolls_remaining=1,
        points_value=350,
        weapons=[
            {"name": "Port Weapons Battery", "weapon_type": "battery",
             "range_cm": 45, "strength": 6, "arcs": ["left"]},
            {"name": "Starboard Weapons Battery", "weapon_type": "battery",
             "range_cm": 45, "strength": 6, "arcs": ["right"]},
            {"name": "Port Launch Bays", "weapon_type": "launch_bay",
             "range_cm": 30, "strength": 2, "arcs": [],
             "craft_types": ["fury_fighter", "starhawk_bomber"], "craft_speed": 30},
            {"name": "Starboard Launch Bays", "weapon_type": "launch_bay",
             "range_cm": 30, "strength": 2, "arcs": [],
             "craft_types": ["fury_fighter", "starhawk_bomber"], "craft_speed": 30},
            {"name": "Prow Nova Cannon", "weapon_type": "nova_cannon",
             "range_cm": 150, "strength": 0, "arcs": ["front"]},
            {"name": "Dorsal Lance Battery", "weapon_type": "lance",
             "range_cm": 60, "strength": 2, "arcs": ["left", "front", "right"]},
        ],
        upgrades=["targeting_matrix"],
        special_rules=["targeting_matrix"],
    )
    gs.add_ship(mars)

    # INS Sword of Bakka - Lunar Class Cruiser
    lunar1 = Ship(
        id="imp_lunar1", name="INS Sword of Bakka",
        ship_class="Lunar Class Cruiser", faction="imperial_navy",
        player=1, ship_type="cruiser", base_size="small",
        x=40, y=15, heading=90,
        speed=20, turn_angle=45, shields_max=2,
        armor_prow="6+", armor_side="5+", turrets=2, hits_max=8,
        leadership=7,
        points_value=180,
        weapons=[
            {"name": "Port Weapons Battery", "weapon_type": "battery",
             "range_cm": 45, "strength": 6, "arcs": ["left"]},
            {"name": "Starboard Weapons Battery", "weapon_type": "battery",
             "range_cm": 45, "strength": 6, "arcs": ["right"]},
            {"name": "Port Lance Battery", "weapon_type": "lance",
             "range_cm": 30, "strength": 2, "arcs": ["left"]},
            {"name": "Starboard Lance Battery", "weapon_type": "lance",
             "range_cm": 30, "strength": 2, "arcs": ["right"]},
            {"name": "Prow Torpedoes", "weapon_type": "torpedo",
             "range_cm": 0, "strength": 6, "arcs": ["front"],
             "torpedo_speed": 30, "torpedo_type": "standard"},
        ],
    )
    gs.add_ship(lunar1)

    # INS Vigilance Undying - Lunar Class Cruiser
    lunar2 = Ship(
        id="imp_lunar2", name="INS Vigilance Undying",
        ship_class="Lunar Class Cruiser", faction="imperial_navy",
        player=1, ship_type="cruiser", base_size="small",
        x=80, y=15, heading=90,
        speed=20, turn_angle=45, shields_max=2,
        armor_prow="6+", armor_side="5+", turrets=2, hits_max=8,
        leadership=8,
        points_value=180,
        weapons=[
            {"name": "Port Weapons Battery", "weapon_type": "battery",
             "range_cm": 45, "strength": 6, "arcs": ["left"]},
            {"name": "Starboard Weapons Battery", "weapon_type": "battery",
             "range_cm": 45, "strength": 6, "arcs": ["right"]},
            {"name": "Port Lance Battery", "weapon_type": "lance",
             "range_cm": 30, "strength": 2, "arcs": ["left"]},
            {"name": "Starboard Lance Battery", "weapon_type": "lance",
             "range_cm": 30, "strength": 2, "arcs": ["right"]},
            {"name": "Prow Torpedoes", "weapon_type": "torpedo",
             "range_cm": 0, "strength": 6, "arcs": ["front"],
             "torpedo_speed": 30, "torpedo_type": "standard"},
        ],
    )
    gs.add_ship(lunar2)

    # Cobras
    for i, name in enumerate(["INS Fervent", "INS Wrathful", "INS Pious"]):
        cobra = Ship(
            id=f"imp_cobra{i+1}", name=name,
            ship_class="Cobra Class Destroyer", faction="imperial_navy",
            player=1, ship_type="escort", base_size="small",
            x=95 + i * 5, y=15, heading=90,
            speed=30, turn_angle=90, shields_max=1,
            armor_prow="5+", armor_side="5+", turrets=1, hits_max=1,
            leadership=7,
            points_value=30,
            weapons=[
                {"name": "Prow Torpedoes", "weapon_type": "torpedo",
                 "range_cm": 0, "strength": 2, "arcs": ["front"],
                 "torpedo_speed": 30, "torpedo_type": "standard"},
            ],
        )
        gs.add_ship(cobra)

    # Dictator Class Cruiser — mine launcher replaces launch bays
    dictator = Ship(
        id="imp_dictator", name="INS Hammer of Fate",
        ship_class="Dictator Class Cruiser", faction="imperial_navy",
        player=1, ship_type="cruiser", base_size="small",
        x=110, y=15, heading=90,
        speed=20, turn_angle=45, shields_max=2,
        armor_prow="6+", armor_side="5+", turrets=2, hits_max=8,
        leadership=7,
        points_value=220,
        weapons=[
            {"name": "Port Weapons Battery", "weapon_type": "battery",
             "range_cm": 45, "strength": 6, "arcs": ["left"]},
            {"name": "Starboard Weapons Battery", "weapon_type": "battery",
             "range_cm": 45, "strength": 6, "arcs": ["right"]},
            {"name": "Prow Torpedoes", "weapon_type": "torpedo",
             "range_cm": 0, "strength": 6, "arcs": ["front"],
             "torpedo_speed": 30, "torpedo_type": "standard"},
            {"name": "Mine Launcher", "weapon_type": "mine_launcher",
             "range_cm": 0, "strength": 4, "arcs": [], "mine_speed": 10},
        ],
    )
    gs.add_ship(dictator)


def create_demo_tau_fleet(gs: GameState):
    """Create the Tau Kor'or'vesh 800pt fleet"""

    # Custodian Class Battleship (Flagship)
    custodian = Ship(
        id="tau_custodian", name="O'Shi'ur",
        ship_class="Custodian Class Battleship", faction="tau_kororvesh",
        player=2, ship_type="battleship", base_size="large",
        x=60, y=105, heading=270,
        speed=20, turn_angle=45, shields_max=3,
        armor_prow="6+", armor_side="5+", turrets=4, hits_max=10,
        leadership=9, is_flagship=True, admiral_type="Kor'O",
        rerolls_remaining=2,
        points_value=425,
        weapons=[
            {"name": "Port Railgun Battery", "weapon_type": "battery",
             "range_cm": 45, "strength": 6, "arcs": ["left", "front"]},
            {"name": "Starboard Railgun Battery", "weapon_type": "battery",
             "range_cm": 45, "strength": 6, "arcs": ["right", "front"]},
            {"name": "Port Ion Cannon", "weapon_type": "lance",
             "range_cm": 45, "strength": 1, "arcs": ["left", "front"]},
            {"name": "Starboard Ion Cannon", "weapon_type": "lance",
             "range_cm": 45, "strength": 1, "arcs": ["right", "front"]},
            {"name": "Port Launch Bays", "weapon_type": "launch_bay",
             "range_cm": 25, "strength": 3, "arcs": [],
             "craft_types": ["manta", "barracuda"], "craft_speed": 25},
            {"name": "Starboard Launch Bays", "weapon_type": "launch_bay",
             "range_cm": 25, "strength": 3, "arcs": [],
             "craft_types": ["manta", "barracuda"], "craft_speed": 25},
            {"name": "Prow Gravitic Launcher", "weapon_type": "gravitic_launcher",
             "range_cm": 40, "strength": 8, "arcs": ["front"],
             "torpedo_speed": 40, "torpedo_type": "guided"},
        ],
        special_rules=["ponderous", "deflector", "tracking_systems_20"],
        towed_escorts=["tau_warden1", "tau_warden2", "tau_warden3"],
    )
    gs.add_ship(custodian)

    # Emissary Class Light Cruisers (Bor'kan refit + deflector)
    for i, (eid, name, ld) in enumerate([
        ("tau_emissary1", "Anukla'esavon", 8),
        ("tau_emissary2", "Bork'sha", 6),
    ]):
        emissary = Ship(
            id=eid, name=name,
            ship_class="Emissary Class Light Cruiser", faction="tau_kororvesh",
            player=2, ship_type="cruiser", base_size="small",
            x=45 + i * 30, y=105, heading=270,
            speed=20, turn_angle=90, shields_max=2,
            armor_prow="5+", armor_side="5+", turrets=2, hits_max=4,
            leadership=ld,
            points_value=120,
            weapons=[
                {"name": "Port Railgun Battery", "weapon_type": "battery",
                 "range_cm": 45, "strength": 4, "arcs": ["left", "front"]},
                {"name": "Starboard Railgun Battery", "weapon_type": "battery",
                 "range_cm": 45, "strength": 4, "arcs": ["right", "front"]},
                {"name": "Port Ion Cannon", "weapon_type": "lance",
                 "range_cm": 30, "strength": 1, "arcs": ["left", "front"]},
                {"name": "Starboard Ion Cannon", "weapon_type": "lance",
                 "range_cm": 30, "strength": 1, "arcs": ["right", "front"]},
                {"name": "Prow Gravitic Launcher", "weapon_type": "gravitic_launcher",
                 "range_cm": 40, "strength": 3, "arcs": ["front"],
                 "torpedo_speed": 40, "torpedo_type": "guided"},
            ],
            special_rules=["deflector"],
        )
        gs.add_ship(emissary)

    # Wardens (towed by Custodian)
    for i, name in enumerate(["Kor'vre Kais", "Kor'vre Y'he", "Kor'vre Lar'shi"]):
        warden = Ship(
            id=f"tau_warden{i+1}", name=name,
            ship_class="Warden Class Gunship", faction="tau_kororvesh",
            player=2, ship_type="escort", base_size="small",
            x=55 + i * 5, y=100, heading=270,
            speed=25, turn_angle=90, shields_max=1,
            armor_prow="5+", armor_side="5+", turrets=1, hits_max=1,
            leadership=7,
            points_value=30,
            weapons=[
                {"name": "Railgun Battery", "weapon_type": "battery",
                 "range_cm": 30, "strength": 2, "arcs": ["front"]},
                {"name": "Ion Cannon", "weapon_type": "lance",
                 "range_cm": 30, "strength": 1, "arcs": ["left", "front", "right"]},
            ],
        )
        gs.add_ship(warden)

    # Castellan
    castellan = Ship(
        id="tau_castellan", name="Anukla'esavon",
        ship_class="Castellan Class Escort", faction="tau_kororvesh",
        player=2, ship_type="escort", base_size="small",
        x=60, y=98, heading=270,
        speed=25, turn_angle=90, shields_max=1,
        armor_prow="5+", armor_side="5+", turrets=2, hits_max=1,
        leadership=8,
        points_value=45,
        weapons=[
            {"name": "Railgun Battery", "weapon_type": "battery",
             "range_cm": 45, "strength": 2, "arcs": ["left", "front", "right"]},
            {"name": "Gravitic Launcher", "weapon_type": "gravitic_launcher",
             "range_cm": 40, "strength": 2, "arcs": ["front"],
             "torpedo_speed": 40, "torpedo_type": "guided"},
        ],
    )
    gs.add_ship(castellan)


def _apply_rules(gs, setup):
    """Apply optional rule settings from setup dict to GameState."""
    for key in ("rule_fighting_sunward", "rule_solar_flares", "rule_radiation_bursts",
                 "rule_boarding", "rule_ramming", "rule_teleport", "rule_hit_and_run",
                 "rule_turret_suppression_remastered", "allow_movement_pass"):
        if key in setup:
            setattr(gs, key, setup[key])


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
        for ship in fleet_to_ships(load_fleet_file(setup["p1_fleet"]), 1):
            gs.add_ship(ship)
        for ship in fleet_to_ships(load_fleet_file(setup["p2_fleet"]), 2):
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
        for ship in fleet_to_ships(load_fleet_file(setup["p1_fleet"]), 1):
            gs.add_ship(ship)
        for ship in fleet_to_ships(load_fleet_file(setup["p2_fleet"]), 2):
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
        for ship in fleet_to_ships(load_fleet_file(setup["p1_fleet"]), 1):
            gs.add_ship(ship)
        for ship in fleet_to_ships(load_fleet_file(setup["p2_fleet"]), 2):
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
            for ship in fleet_to_ships(load_fleet_file(p1_fleet), 1):
                gs.add_ship(ship)
        if p2_fleet:
            for ship in fleet_to_ships(load_fleet_file(p2_fleet), 2):
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

    def _get_rules():
        rules = {f"rule_{k}": v.get() for k, v in rule_vars.items()}
        rules["allow_movement_pass"] = allow_pass_var.get()
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
