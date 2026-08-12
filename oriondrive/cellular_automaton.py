from __future__ import annotations
import random
from dataclasses import dataclass
from typing import List
from .config import VALID_CA_RULES, validate_choice, validate_positive_int, validate_probability

@dataclass(frozen=True)
class CellularAutomatonConfig:
    rule: int = 90
    width: int = 16
    steps: int = 64
    seed_density: float = 0.35
    wrap_edges: bool = True

    def validate(self) -> None:
        validate_choice('ca_rule', self.rule, VALID_CA_RULES)
        validate_positive_int('ca_width', self.width)
        validate_positive_int('ca_steps', self.steps)
        validate_probability('ca_seed_density', self.seed_density)

@dataclass(frozen=True)
class StepFeatures:
    active_bit: int
    duration_index: int
    velocity_value: int
    accompaniment_bit: int
    accent_bit: int
    density: float

class ElementaryCellularAutomaton:

    def __init__(self, config: CellularAutomatonConfig):
        self.config = config
        self.config.validate()

    def generate(self, rng: random.Random) -> List[List[int]]:
        row = [1 if rng.random() < self.config.seed_density else 0 for _ in range(self.config.width)]
        if not any(row):
            row[self.config.width // 2] = 1
        grid = [row]
        for _ in range(1, self.config.steps):
            row = self._next_row(row)
            grid.append(row)
        return grid

    def _next_row(self, row: List[int]) -> List[int]:
        next_row = []
        width = len(row)
        for index, center in enumerate(row):
            if self.config.wrap_edges:
                left = row[(index - 1) % width]
                right = row[(index + 1) % width]
            else:
                left = row[index - 1] if index > 0 else 0
                right = row[index + 1] if index < width - 1 else 0
            neighborhood = left << 2 | center << 1 | right
            next_row.append(self.config.rule >> neighborhood & 1)
        return next_row

def features_for_step(grid: List[List[int]], step: int) -> StepFeatures:
    if not grid:
        raise ValueError('Cellular automaton grid cannot be empty.')
    row = grid[step % len(grid)]
    width = len(row)
    if width < 4:
        raise ValueError('Cellular automaton rows must contain at least four cells.')
    density = sum(row) / width
    duration_index = row[(step + 1) % width] << 1 | row[(step + 3) % width]
    velocity_value = sum((row[(step + offset) % width] for offset in range(0, width, 3)))
    return StepFeatures(active_bit=row[step * 3 % width], duration_index=duration_index, velocity_value=velocity_value, accompaniment_bit=row[(step * 5 + 1) % width], accent_bit=row[(step * 7 + 2) % width], density=density)
