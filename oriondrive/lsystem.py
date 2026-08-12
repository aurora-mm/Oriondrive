from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Mapping
from .config import validate_octave_range, validate_positive_int, validate_scale
SYMBOL_ACTIONS: Mapping[str, str] = {'U': 'step_up', 'D': 'step_down', 'L': 'leap_up', 'V': 'leap_down', 'H': 'hold', 'M': 'repeat_motif', 'I': 'invert_motif', 'R': 'rest', '[': 'start_phrase', ']': 'end_phrase'}

@dataclass(frozen=True)
class LSystemRuleSet:
    name: str
    axiom: str
    rules: Dict[str, str]

@dataclass(frozen=True)
class LSystemConfig:
    axiom: str = 'A'
    rules: Mapping[str, str] | None = None
    iterations: int = 4
    scale: str = 'dorian'
    root_note: str = 'C'
    octave_range: tuple[int, int] = (3, 5)
    phrase_length: int = 8

    def validate(self) -> None:
        if not self.axiom:
            raise ValueError('L-system axiom cannot be empty.')
        if self.rules is None or not self.rules:
            raise ValueError('L-system rules cannot be empty.')
        if self.iterations < 0 or self.iterations > 7:
            raise ValueError('L-system iterations must be between 0 and 7.')
        validate_scale(self.scale)
        validate_octave_range(self.octave_range)
        validate_positive_int('phrase_length', self.phrase_length)
DEFAULT_RULE_SETS: Dict[str, LSystemRuleSet] = {'balanced': LSystemRuleSet(name='balanced', axiom='A', rules={'A': '[UHDM]BIA', 'B': 'U[LDM]AR'}), 'lyrical': LSystemRuleSet(name='lyrical', axiom='A', rules={'A': '[UUHDM]BI', 'B': 'D[HUM]AV'}), 'angular': LSystemRuleSet(name='angular', axiom='A', rules={'A': '[LUVH]BMA', 'B': 'V[UHR]IL'}), 'restless': LSystemRuleSet(name='restless', axiom='A', rules={'A': '[URDU]BMR', 'B': '[LHRV]AI'}), 'trance_hook': LSystemRuleSet(name='trance_hook', axiom='A', rules={'A': '[UHDUM]BIA', 'B': 'U[LDMU]AR'}), 'ebm_command': LSystemRuleSet(name='ebm_command', axiom='A', rules={'A': '[UHR]B[DR]', 'B': 'M[HUR]A'}), 'ebm_machine': LSystemRuleSet(name='ebm_machine', axiom='A', rules={'A': '[HMHM]B', 'B': 'U[RHM]AD'}), 'berlin_sequence': LSystemRuleSet(name='berlin_sequence', axiom='A', rules={'A': '[UHDM]A[DLHM]B', 'B': 'M[UHD]A'}), 'berlin_drift': LSystemRuleSet(name='berlin_drift', axiom='A', rules={'A': '[HUMD]B[HDIM]', 'B': 'L[HDU]AR'})}

def available_rule_sets() -> List[str]:
    return sorted(DEFAULT_RULE_SETS)

def get_rule_set(name: str) -> LSystemRuleSet:
    if name not in DEFAULT_RULE_SETS:
        choices = ', '.join(available_rule_sets())
        raise ValueError(f"Unknown L-system rule set '{name}'. Choose one of: {choices}.")
    return DEFAULT_RULE_SETS[name]

class LSystem:

    def __init__(self, config: LSystemConfig):
        self.config = config
        self.config.validate()

    def expand(self) -> str:
        current = self.config.axiom
        rules = self.config.rules or {}
        for _ in range(self.config.iterations):
            current = ''.join((rules.get(symbol, symbol) for symbol in current))
        return current

    def actions(self) -> List[str]:
        expanded = self.expand()
        return [SYMBOL_ACTIONS[symbol] for symbol in expanded if symbol in SYMBOL_ACTIONS]
