"""Adeptus Mechanicus Gifts at game start (bfgxr/rules/02_adeptus-mechanicus.md).

Vault of Technology: "At the start of the game, roll a D6; the ship gains the
corresponding Gift from this table for free. If a 6 is rolled, you may instead
choose one of the above refits to apply." The Gift is free (CHANGES update 19).
"""
from typing import Callable, List, Optional


def apply_gift(ship_dict: dict, number: int) -> str:
    """Give a ship dict the Gift numbered 1-5 (its effects only; no cost)."""
    from .booklet_options import MECHANICUS_GIFTS
    from .ship_catalog import apply_upgrade_effect
    _, name, _, effect = next(g for g in MECHANICUS_GIFTS if g[0] == number)
    apply_upgrade_effect(ship_dict, effect)
    return name


def roll_vault_of_technology(gs, dice, ai_dice=None,
                             choose_fn: Optional[Callable[[dict], int]] = None) -> List[str]:
    """Each ship with a Vault of Technology rolls a D6 for a free Gift. On a 6
    the owner chooses Gifts 1-5 (choose_fn(ship_dict) -> 1-5; the AI and a
    missing chooser take Advanced Shields). Returns log lines."""
    logs = []
    for s in gs.ships:
        if "vault_of_technology" not in s.get("special_rules", []):
            continue
        ai = gs.ai_spectator or gs.ai_player == s["player"]
        roller = ai_dice if (ai and ai_dice is not None) else dice
        roll = roller.roll_d6(1, f"{s['name']} Vault of Technology (D6 for a Gift)")[0]
        number = roll
        if roll == 6:
            number = 4                 # AI choice: Advanced Shields
            if choose_fn is not None and not ai:
                number = choose_fn(s) or 4
        name = apply_gift(s, number)
        s["special_rules"] = [r for r in s["special_rules"] if r != "vault_of_technology"]
        logs.append(f"{s['name']}: Vault of Technology rolled {roll}: "
                    f"{name}{' (chosen)' if roll == 6 else ''}")
    return logs
