from __future__ import annotations
import random
from dataclasses import dataclass
from typing import Dict, List, Sequence
from .arrangement import Arrangement, BEATS_PER_BAR
from .composition import Composition, NoteEvent
from .config import build_scale_pitches, clamp, validate_probability
from .grooves import GrooveProfile
from .loops import LoopPattern, quantize

@dataclass(frozen=True)
class BassConfig:
    density: float = 0.55
    register: int = 1
    rhythmic_activity: float = 0.45
    harmonic_strictness: float = 0.75
    activity_by_section: float = 0.7
    groove: GrooveProfile | None = None

    def validate(self) -> None:
        validate_probability('bass_density', self.density)
        validate_probability('bass_rhythmic_activity', self.rhythmic_activity)
        validate_probability('bass_harmonic_strictness', self.harmonic_strictness)
        validate_probability('bass_activity_by_section', self.activity_by_section)
        if self.register < 0 or self.register > 3:
            raise ValueError('bass_register must be between octaves 0 and 3.')

class BassGenerator:

    def __init__(self, config: BassConfig):
        self.config = config
        self.config.validate()

    def generate(self, lead_composition: Composition, arrangement: Arrangement, rng: random.Random) -> List[NoteEvent]:
        structure = lead_composition.structure_map
        scale = structure.get('scale', 'dorian')
        root_note = structure.get('root_note', 'C')
        bass_pitches = build_scale_pitches(scale, root_note, (self.config.register, min(4, self.config.register + 1)))
        loop_centers = structure.get('harmonic_centers_by_loop', [])
        events: List[NoteEvent] = []
        for block in arrangement.loop_blocks():
            section = arrangement.section_by_name(block.section_name)
            role = section.bass_role
            if role == 'off':
                continue
            centers = loop_centers[block.index % len(loop_centers)] if loop_centers else [bass_pitches[len(bass_pitches) // 2]] * 4
            pattern = self._pattern_for_role(role, section.energy, centers, bass_pitches, rng)
            velocity_scale = 0.68 + section.energy * 0.42
            if role in {'minimal', 'pulse'}:
                velocity_scale *= 0.82
            events.extend(pattern.shifted(block.start_beat, velocity_scale=velocity_scale))
        return sorted(events, key=lambda event: (event.start, event.pitch))

    def _pattern_for_role(self, role: str, energy: float, centers: Sequence[int], bass_pitches: Sequence[int], rng: random.Random) -> LoopPattern:
        groove = self.config.groove
        if role == 'minimal':
            events = _pedal_pattern(centers, bass_pitches, sparse=True, groove=groove)
        elif role == 'pulse':
            events = _groove_bass(centers, bass_pitches, rng, density=self.config.density * 0.68, groove=groove, intensity=0.5)
        elif role == 'active':
            events = _groove_bass(centers, bass_pitches, rng, density=clamp(self.config.density + 0.18, 0.2, 0.95), groove=groove, intensity=self.config.rhythmic_activity)
        elif role == 'tension':
            events = _rising_tension_bass(centers, bass_pitches, rng, intensity=self.config.activity_by_section, groove=groove)
        elif role == 'rolling':
            events = _groove_bass(centers, bass_pitches, rng, density=clamp(self.config.density + energy * 0.28, 0.35, 1.0), groove=groove, intensity=1.0)
        else:
            events = _pedal_pattern(centers, bass_pitches, sparse=True, groove=groove)
        return LoopPattern(id=f'bass_{role}_8bar', events=events, motif_id=f'bass_{role}', variation_level=self.config.rhythmic_activity, source='bass').clipped()

def _pedal_pattern(centers: Sequence[int], bass_pitches: Sequence[int], sparse: bool=True, groove: GrooveProfile | None=None) -> List[NoteEvent]:
    events: List[NoteEvent] = []
    hold = groove.bass_note_length * 3.0 if groove is not None else 1.5
    for phrase in range(4):
        center = _bass_root(centers[phrase % len(centers)], bass_pitches)
        start = phrase * 8.0
        events.append(NoteEvent(start=start, duration=max(0.75, hold if sparse else hold * 0.5), pitch=center, velocity=62))
        if not sparse:
            events.append(NoteEvent(start=start + 4.0, duration=0.75, pitch=center, velocity=58))
    return events

def _groove_bass(centers: Sequence[int], bass_pitches: Sequence[int], rng: random.Random, density: float, groove: GrooveProfile | None, intensity: float) -> List[NoteEvent]:
    if groove is None:
        return _root_fifth_pulse(centers, bass_pitches, density=density)
    style = groove.bass_style
    step = groove.bass_step
    length = groove.bass_note_length
    events: List[NoteEvent] = []
    for phrase in range(4):
        root = _bass_root(centers[phrase % len(centers)], bass_pitches)
        fifth = _nearest_scale_pitch(root + 7, bass_pitches)
        octave = _nearest_scale_pitch(root + 12, bass_pitches)
        third = _nearest_scale_pitch(root + rng.choice((3, 4)), bass_pitches)
        start = phrase * 8.0
        if style == 'drone':
            events.append(NoteEvent(start, max(2.0, length * 4.0), root, 64))
            if intensity > 0.6:
                events.append(NoteEvent(start + 4.0, max(1.5, length * 3.0), fifth, 58))
            continue
        beat = 0.0
        index = 0
        while beat < 8.0:
            on_downbeat = abs(beat % 1.0) < 1e-06
            keep = True
            pitch = root
            if style == 'offbeat':
                keep = not on_downbeat or density > 0.92
                if index % 8 == 5:
                    pitch = fifth
                elif index % 8 == 7:
                    pitch = octave
            elif style == 'pulse':
                keep = on_downbeat or (index % 2 == 1 and density > 0.55)
                pitch = root if index % 4 in (0, 1) else fifth if index % 4 == 2 else octave
            elif style == 'gallop':
                keep = index % 4 != 2 and (index % 4 != 3 or density > 0.7)
                pitch = root if index % 8 < 6 else octave
            elif style == 'walking':
                keep = True
                pitch = (root, third, fifth, octave)[index % 4]
            elif style == 'stab':
                keep = index % 2 == 0 or density > 0.8
                pitch = root if index % 4 < 2 else fifth
            if keep:
                onset = groove.swung(beat % 4.0) + (beat - beat % 4.0)
                velocity = 66 + (12 if on_downbeat else 0) + int(16 * density)
                events.append(NoteEvent(quantize(start + onset, 0.125), max(0.12, length), pitch, int(clamp(velocity, 40, 120))))
            beat += step
            index += 1
    return events

def _root_fifth_pulse(centers: Sequence[int], bass_pitches: Sequence[int], density: float, eighths: bool=False) -> List[NoteEvent]:
    events: List[NoteEvent] = []
    step = 0.5 if eighths else 1.0
    for phrase in range(4):
        root = _bass_root(centers[phrase % len(centers)], bass_pitches)
        fifth = _nearest_scale_pitch(root + 7, bass_pitches)
        octave = _nearest_scale_pitch(root + 12, bass_pitches)
        start = phrase * 8.0
        beat = 0.0
        pulse_index = 0
        while beat < 8.0:
            on_downbeat = abs(beat % 1.0) < 0.001
            if on_downbeat or (pulse_index % 2 == 1 and density > 0.55):
                pitch = root if pulse_index % 4 in (0, 1) else fifth if pulse_index % 4 == 2 else octave
                duration = 0.42 if step == 0.5 else 0.72
                events.append(NoteEvent(start + beat, duration, pitch, 66 + (12 if on_downbeat else 0)))
            beat += step
            pulse_index += 1
    return events

def _rising_tension_bass(centers: Sequence[int], bass_pitches: Sequence[int], rng: random.Random, intensity: float, groove: GrooveProfile | None=None) -> List[NoteEvent]:
    events: List[NoteEvent] = []
    root = _bass_root(centers[0], bass_pitches)
    if groove is not None:
        step = groove.bass_step if intensity < 0.65 else max(0.125, groove.bass_step * 0.5)
        length = groove.bass_note_length
    else:
        step = 0.5 if intensity < 0.65 else 0.25
        length = max(0.16, step * 0.72)
    beat = 0.0
    index = 0
    while beat < 32.0:
        pitch = _scale_shift(root, bass_pitches, min(8, index // 4))
        events.append(NoteEvent(quantize(beat, 0.125), max(0.12, length), pitch, int(clamp(58 + beat * 1.7, 48, 112))))
        beat += step
        index += 1
    return events

def _bass_root(center: int, bass_pitches: Sequence[int]) -> int:
    return _nearest_scale_pitch(center - 24, bass_pitches)

def _nearest_scale_pitch(pitch: int, scale_pitches: Sequence[int]) -> int:
    return min(scale_pitches, key=lambda candidate: abs(candidate - pitch))

def _scale_shift(pitch: int, scale_pitches: Sequence[int], steps: int) -> int:
    nearest_index = min(range(len(scale_pitches)), key=lambda idx: abs(scale_pitches[idx] - pitch))
    shifted_index = int(clamp(nearest_index + steps, 0, len(scale_pitches) - 1))
    return scale_pitches[shifted_index]
