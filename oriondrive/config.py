from __future__ import annotations
from typing import Dict, Iterable, List, Sequence, Tuple
DEFAULT_OUTPUT = 'output/oriondrive_composition.mid'
DEFAULT_TICKS_PER_BEAT = 480
DEFAULT_MIN_DURATION_SECONDS = 180.0
DEFAULT_CANDIDATE_COUNT = 20
DEFAULT_GENERATIONS = 30
SUGGESTED_CA_RULES = (30, 90, 110)
VALID_CA_RULES = tuple(range(256))
VALID_GENRES = ('classic_trance', 'ebm', 'berlin_school')
FITNESS_WEIGHTS: Dict[str, float] = {'loop_coherence_score': 1.35, 'section_contrast_score': 1.25, 'genre_arrangement_score': 1.45, 'lead_hook_strength_score': 1.35, 'arrival_energy_score': 1.3, 'drum_groove_score': 1.1, 'transition_quality_score': 1.05, 'duration': 1.15, 'melodic_coherence': 0.8, 'layer_alignment': 0.95}
PENALTY_WEIGHTS: Dict[str, float] = {'below_min_duration': 2.8, 'out_of_scale_ratio_too_high': 1.6, 'pitch_range_too_wide': 0.9, 'pitch_range_too_narrow': 0.9, 'too_many_large_leaps': 1.1, 'too_many_repeated_notes': 0.7, 'too_much_silence': 1.0, 'too_dense': 1.0, 'layer_register_collision': 1.2, 'riff_duplicates_lead': 1.1, 'bass_ignores_harmony': 1.2, 'no_phrase_structure': 1.4, 'no_dynamic_variation': 0.9}
SCALE_PATTERNS: Dict[str, Tuple[int, ...]] = {'major': (0, 2, 4, 5, 7, 9, 11), 'natural_minor': (0, 2, 3, 5, 7, 8, 10), 'harmonic_minor': (0, 2, 3, 5, 7, 8, 11), 'dorian': (0, 2, 3, 5, 7, 9, 10), 'phrygian': (0, 1, 3, 5, 7, 8, 10), 'lydian': (0, 2, 4, 6, 7, 9, 11), 'mixolydian': (0, 2, 4, 5, 7, 9, 10), 'minor_pentatonic': (0, 3, 5, 7, 10), 'major_pentatonic': (0, 2, 4, 7, 9)}
NOTE_TO_PITCH_CLASS = {'C': 0, 'C#': 1, 'DB': 1, 'D': 2, 'D#': 3, 'EB': 3, 'E': 4, 'F': 5, 'F#': 6, 'GB': 6, 'G': 7, 'G#': 8, 'AB': 8, 'A': 9, 'A#': 10, 'BB': 10, 'B': 11}

def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))

def available_scales() -> List[str]:
    return sorted(SCALE_PATTERNS)

def available_root_notes() -> List[str]:
    return ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']

def validate_scale(scale: str) -> None:
    if scale not in SCALE_PATTERNS:
        choices = ', '.join(available_scales())
        raise ValueError(f"Unknown scale '{scale}'. Choose one of: {choices}.")

def scale_pattern(scale: str) -> Tuple[int, ...]:
    validate_scale(scale)
    return SCALE_PATTERNS[scale]

def root_pitch_class(root_note: str) -> int:
    normalized = root_note.strip().replace('♯', '#').replace('♭', 'b').upper()
    if normalized not in NOTE_TO_PITCH_CLASS:
        choices = ', '.join(sorted(NOTE_TO_PITCH_CLASS))
        raise ValueError(f"Unknown root note '{root_note}'. Choose one of: {choices}.")
    return NOTE_TO_PITCH_CLASS[normalized]

def validate_octave_range(octave_range: Tuple[int, int]) -> None:
    low, high = octave_range
    if low > high:
        raise ValueError('octave_range must be ordered as (low, high).')
    if low < 0 or high > 8:
        raise ValueError('octave_range must stay within MIDI-friendly octaves 0..8.')

def build_scale_pitches(scale: str, root_note: str, octave_range: Tuple[int, int]) -> List[int]:
    validate_scale(scale)
    validate_octave_range(octave_range)
    root = root_pitch_class(root_note)
    pattern = scale_pattern(scale)
    low_octave, high_octave = octave_range
    min_midi = (low_octave + 1) * 12
    max_midi = (high_octave + 1) * 12 + 11
    pitches = set()
    for octave in range(low_octave, high_octave + 1):
        octave_base = (octave + 1) * 12
        for interval in pattern:
            pitch = octave_base + root + interval
            if min_midi <= pitch <= max_midi and 0 <= pitch <= 127:
                pitches.add(pitch)
    if not pitches:
        raise ValueError('Scale and octave range produced no valid MIDI pitches.')
    return sorted(pitches)

def validate_positive_int(name: str, value: int) -> None:
    if value <= 0:
        raise ValueError(f'{name} must be a positive integer.')

def validate_probability(name: str, value: float) -> None:
    if value < 0.0 or value > 1.0:
        raise ValueError(f'{name} must be between 0.0 and 1.0.')

def validate_choice(name: str, value: object, choices: Sequence[object]) -> None:
    if value not in choices:
        readable = ', '.join((str(choice) for choice in choices))
        raise ValueError(f'{name} must be one of: {readable}.')

def mean(values: Iterable[float]) -> float:
    values = list(values)
    if not values:
        return 0.0
    return sum(values) / len(values)
