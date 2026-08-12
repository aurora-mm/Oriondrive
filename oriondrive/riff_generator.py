from __future__ import annotations
import random
from dataclasses import dataclass
from typing import List, Sequence
from .arrangement import Arrangement
from .composition import Composition, NoteEvent
from .config import build_scale_pitches, clamp, validate_probability
from .grooves import GrooveProfile
from .loops import LoopPattern, quantize

@dataclass(frozen=True)
class RiffConfig:
    density: float = 0.45
    register: int = 4
    rhythmic_variation: float = 0.45
    motif_mutation_amount: float = 0.35
    density_by_section: float = 0.65
    groove: GrooveProfile | None = None

    def validate(self) -> None:
        validate_probability('riff_density', self.density)
        validate_probability('riff_rhythmic_variation', self.rhythmic_variation)
        validate_probability('riff_motif_mutation_amount', self.motif_mutation_amount)
        validate_probability('riff_density_by_section', self.density_by_section)
        if self.register < 2 or self.register > 6:
            raise ValueError('riff_register must be between octaves 2 and 6.')

class RiffGenerator:

    def __init__(self, config: RiffConfig):
        self.config = config
        self.config.validate()

    def generate(self, lead_composition: Composition, arrangement: Arrangement, rng: random.Random) -> List[NoteEvent]:
        structure = lead_composition.structure_map
        scale = structure.get('scale', 'dorian')
        root_note = structure.get('root_note', 'C')
        riff_pitches = build_scale_pitches(scale, root_note, (self.config.register, min(7, self.config.register + 1)))
        loop_centers = structure.get('harmonic_centers_by_loop', [])
        hook_notes = structure.get('hook_notes', []) or [riff_pitches[len(riff_pitches) // 2]]
        events: List[NoteEvent] = []
        for block in arrangement.loop_blocks():
            section = arrangement.section_by_name(block.section_name)
            role = section.riff_role
            if role == 'off':
                continue
            centers = loop_centers[block.index % len(loop_centers)] if loop_centers else [riff_pitches[len(riff_pitches) // 2]] * 4
            pattern = self._pattern_for_role(role, centers, hook_notes, riff_pitches, rng, section.energy)
            gated = _gate_role(pattern.shifted(block.start_beat, velocity_scale=0.72 + section.energy * 0.42), role, block.start_beat, rng)
            events.extend(gated)
        return sorted(events, key=lambda event: (event.start, event.pitch))

    def _pattern_for_role(self, role: str, centers: Sequence[int], hook_notes: Sequence[int], riff_pitches: Sequence[int], rng: random.Random, energy: float) -> LoopPattern:
        groove = self.config.groove
        if role == 'atmospheric':
            events = _atmospheric_echoes(centers, riff_pitches, groove=groove)
        elif role == 'rising':
            events = _rising_gated_cell(centers, riff_pitches, rng, self.config.rhythmic_variation, groove=groove)
        elif role in {'full', 'full_variation'}:
            events = _full_riff_cell(hook_notes, centers, riff_pitches, rng, density=clamp(self.config.density + energy * 0.32, 0.35, 1.0), variation=role == 'full_variation', groove=groove)
        elif role == 'echo':
            events = _atmospheric_echoes(centers, riff_pitches, short=True, groove=groove)
        elif role == 'fade':
            events = _full_riff_cell(hook_notes, centers, riff_pitches, rng, density=self.config.density * 0.45, variation=False, groove=groove)
        else:
            events = _muted_pluck_cell(centers, riff_pitches, density=clamp(self.config.density, 0.1, 0.8), groove=groove)
        return LoopPattern(id=f'riff_{role}_8bar', events=events, motif_id=f'riff_{role}', variation_level=self.config.motif_mutation_amount, source='riff').clipped()

def _riff_cell(groove: GrooveProfile | None, fallback: Sequence[float]) -> Sequence[float]:
    return groove.riff_cell if groove is not None else fallback

def _riff_length(groove: GrooveProfile | None, fallback: float) -> float:
    return groove.riff_note_length if groove is not None else fallback

def _muted_pluck_cell(centers: Sequence[int], riff_pitches: Sequence[int], density: float, groove: GrooveProfile | None=None) -> List[NoteEvent]:
    events: List[NoteEvent] = []
    cell = list(_riff_cell(groove, (0.5, 1.5, 2.5, 3.5)))[::2] or [0.5]
    length = _riff_length(groove, 0.18)
    for bar in range(8):
        center = _nearest_scale_pitch(centers[bar // 2 % len(centers)], riff_pitches)
        for i, offset in enumerate(cell):
            if i == 0 or density > 0.48 or (bar + i) % 3 == 0:
                pitch = _scale_shift(center, riff_pitches, [0, 2, -1, 3][i % 4])
                events.append(NoteEvent(bar * 4.0 + offset, length, pitch, 56 + i * 4))
    return events

def _full_riff_cell(hook_notes: Sequence[int], centers: Sequence[int], riff_pitches: Sequence[int], rng: random.Random, density: float, variation: bool, groove: GrooveProfile | None=None) -> List[NoteEvent]:
    events: List[NoteEvent] = []
    rhythm = list(_riff_cell(groove, (0.25, 0.75, 1.25, 1.75, 2.5, 3.0, 3.5)))
    length = _riff_length(groove, 0.16)
    keep_always = {0, len(rhythm) // 2, max(0, len(rhythm) - 2)}
    for bar in range(8):
        center = _nearest_scale_pitch(centers[bar // 2 % len(centers)], riff_pitches)
        for index, offset in enumerate(rhythm):
            if index not in keep_always and rng.random() > density:
                continue
            hook = hook_notes[(bar + index) % len(hook_notes)]
            pitch = _nearest_scale_pitch(hook - 12, riff_pitches)
            if index % 2 == 0:
                pitch = _scale_shift(center, riff_pitches, index % 5)
            if variation and (bar + index) % 5 == 0:
                pitch = _scale_shift(pitch, riff_pitches, rng.choice((-2, 1, 2)))
            events.append(NoteEvent(bar * 4.0 + offset, length, pitch, 66 + int(20 * density)))
    return events

def _rising_gated_cell(centers: Sequence[int], riff_pitches: Sequence[int], rng: random.Random, rhythmic_variation: float, groove: GrooveProfile | None=None) -> List[NoteEvent]:
    events: List[NoteEvent] = []
    if groove is not None:
        step = groove.hat_step
        length = groove.riff_note_length
    else:
        step = 0.5 if rhythmic_variation < 0.62 else 0.25
        length = max(0.12, step * 0.55)
    beat = 0.0
    index = 0
    root = _nearest_scale_pitch(centers[0], riff_pitches)
    while beat < 32.0:
        pitch = _scale_shift(root, riff_pitches, min(10, index // 3))
        onset = groove.swung(beat % 4.0) + (beat - beat % 4.0) if groove is not None else beat
        events.append(NoteEvent(quantize(onset, 0.125), max(0.12, length), pitch, int(clamp(54 + beat * 1.9, 50, 116))))
        beat += step
        index += 1
    return events

def _atmospheric_echoes(centers: Sequence[int], riff_pitches: Sequence[int], short: bool=False, groove: GrooveProfile | None=None) -> List[NoteEvent]:
    events: List[NoteEvent] = []
    offsets = [0.0, 2.0] if short else [0.0, 2.0, 4.0, 6.0]
    push = 0.5 if groove is None else max(0.25, groove.hat_step)
    for phrase in range(4):
        center = _nearest_scale_pitch(centers[phrase % len(centers)], riff_pitches)
        for offset in offsets:
            events.append(NoteEvent(phrase * 8.0 + offset + push, 0.35 if short else 0.75, center, 46 if short else 52))
    return events

def _gate_role(events: Sequence[NoteEvent], role: str, block_start: float, rng: random.Random) -> List[NoteEvent]:
    if role in {'full', 'full_variation', 'rising'}:
        return list(events)
    gated: List[NoteEvent] = []
    for event in events:
        local = event.start - block_start
        keep = True
        if role == 'muted':
            keep = local >= 8.0 or int(local // 4) % 2 == 0
        elif role == 'repeating':
            keep = local >= 4.0
        elif role in {'atmospheric', 'echo'}:
            keep = int(local // 8) % 2 == 0 or event.velocity > 54
        elif role == 'fade':
            keep = local < 20.0
        if keep:
            gated.append(event)
    return gated

def _nearest_scale_pitch(pitch: int, scale_pitches: Sequence[int]) -> int:
    return min(scale_pitches, key=lambda candidate: abs(candidate - pitch))

def _scale_shift(pitch: int, scale_pitches: Sequence[int], steps: int) -> int:
    nearest_index = min(range(len(scale_pitches)), key=lambda idx: abs(scale_pitches[idx] - pitch))
    shifted_index = int(clamp(nearest_index + steps, 0, len(scale_pitches) - 1))
    return scale_pitches[shifted_index]
