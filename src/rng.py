"""Seeded randomness that isn't a dice roll (To do 17): the AI's random
choices (Easy's softmax, a random target, a secret formation) and cosmetic
values (a blast marker's heading). Each draw is a fresh generator from the
game seed, the stream's name and a counter kept in GameState, so it repeats
from the seed and survives saving, loading and phase undo; it never touches
the dice, so recorded dice replay unchanged around it."""
import random


def game_random(gs, stream: str = "ai") -> random.Random:
    """A generator for one random choice in this game."""
    gs.rng_counter = getattr(gs, "rng_counter", 0) + 1
    return random.Random(f"{getattr(gs, 'game_seed', 0)}:{stream}:{gs.rng_counter}")


def cosmetic_heading(gs) -> float:
    """A random-looking heading for a marker whose heading has no effect."""
    return game_random(gs, "cosmetic").uniform(0, 360)
