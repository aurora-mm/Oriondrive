from __future__ import annotations
import random
from dataclasses import dataclass, field, replace
from typing import Any, Dict, Iterable, List
from .cellular_automaton import CellularAutomatonConfig, ElementaryCellularAutomaton, features_for_step
from .config import DEFAULT_TICKS_PER_BEAT, build_scale_pitches, clamp, validate_positive_int, validate_probability
from .lsystem import LSystem, LSystemConfig

@dataclass(frozen=True)
class NoteEvent:
    start: float
    duration: float
    pitch: int
    velocity: int

@dataclass
class Composition:
    tempo: int
    leads: List[NoteEvent]
    riffs: List[NoteEvent] = field(default_factory=list)
    bass: List[NoteEvent] = field(default_factory=list)
    drums: List[NoteEvent] = field(default_factory=list)
    pads: List[NoteEvent] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    structure_map: Dict[str, Any] = field(default_factory=dict)

    @property
    def melody(self) -> List[NoteEvent]:
        return self.leads

    @property
    def accompaniment(self) -> List[NoteEvent]:
        return self.riffs + self.bass

    def layer_events(self) -> Dict[str, List[NoteEvent]]:
        return {'leads': self.leads, 'riffs': self.riffs, 'bass': self.bass, 'drums': self.drums, 'pads': self.pads}

@dataclass(frozen=True)
class CompositionParameters:
    lsystem: LSystemConfig
    ca: CellularAutomatonConfig
    tempo: int = 110
    rhythm_density: float = 0.6
    accompaniment_density: float = 0.25

    def validate(self) -> None:
        self.lsystem.validate()
        self.ca.validate()
        if self.tempo < 40 or self.tempo > 240:
            raise ValueError('tempo must be between 40 and 240 BPM.')
        validate_probability('rhythm_density', self.rhythm_density)
        validate_probability('accompaniment_density', self.accompaniment_density)

def compose(parameters: CompositionParameters, rng: random.Random) -> Composition:
    parameters.validate()
    lsystem = LSystem(parameters.lsystem)
    actions = lsystem.actions()
    if not actions:
        raise ValueError('L-system generated no musical action symbols.')
    ca_steps = max(parameters.ca.steps, len(actions) + 8)
    ca_config = replace(parameters.ca, steps=ca_steps)
    grid = ElementaryCellularAutomaton(ca_config).generate(rng)
    scale_pitches = build_scale_pitches(parameters.lsystem.scale, parameters.lsystem.root_note, parameters.lsystem.octave_range)
    pitch_index = len(scale_pitches) // 2
    melody: List[NoteEvent] = []
    lead_support: List[NoteEvent] = []
    motif: List[int] = []
    phrase_lengths: List[int] = []
    phrase_note_count = 0
    phrase_depth = 0
    current_time = 0.0
    musical_step = 0
    rest_steps = 0
    for action in actions:
        if action == 'start_phrase':
            phrase_depth += 1
            if phrase_note_count:
                phrase_lengths.append(phrase_note_count)
                phrase_note_count = 0
            continue
        if action == 'end_phrase':
            phrase_depth = max(0, phrase_depth - 1)
            if phrase_note_count:
                phrase_lengths.append(phrase_note_count)
                phrase_note_count = 0
            current_time += 0.5
            continue
        features = features_for_step(grid, musical_step)
        duration = _duration_from_features(features.duration_index, features.density)
        velocity = _velocity_from_features(features.velocity_value, features.accent_bit, features.density, rng)
        active = _is_active(parameters.rhythm_density, features.active_bit, features.accent_bit, rng)
        if action == 'rest':
            active = False
        step_start_time = current_time
        if action == 'repeat_motif' and motif and active:
            emitted, current_time = _emit_motif(melody, motif[-4:], current_time, duration, velocity, scale_pitches, variation=rng.choice((-1, 0, 1)) if features.accent_bit else 0)
            phrase_note_count += emitted
        elif action == 'invert_motif' and motif and active:
            inverted = _invert_motif(motif[-4:], scale_pitches[pitch_index], scale_pitches)
            emitted, current_time = _emit_motif(melody, inverted, current_time, duration, velocity, scale_pitches, variation=0)
            phrase_note_count += emitted
            motif.extend(inverted)
            motif = motif[-8:]
        else:
            pitch_index = _move_pitch_index(action, pitch_index, len(scale_pitches), rng)
            if active:
                pitch = scale_pitches[pitch_index]
                melody.append(NoteEvent(current_time, duration, pitch, velocity))
                motif.append(pitch)
                motif = motif[-8:]
                phrase_note_count += 1
            else:
                rest_steps += 1
            current_time += duration
        if melody and rng.random() < _accompaniment_probability(parameters.accompaniment_density, features.accompaniment_bit, features.accent_bit):
            lead_support.append(_make_accompaniment_note(scale_pitches, pitch_index, step_start_time, duration, velocity))
        musical_step += 1
        if musical_step % parameters.lsystem.phrase_length == 0:
            if phrase_note_count:
                phrase_lengths.append(phrase_note_count)
                phrase_note_count = 0
            current_time += 0.25
    if phrase_note_count:
        phrase_lengths.append(phrase_note_count)
    leads = sorted(melody + lead_support, key=lambda event: (event.start, event.pitch))
    metadata = {'actions': actions, 'grid': grid, 'phrase_lengths': phrase_lengths, 'rest_steps': rest_steps, 'musical_steps': musical_step, 'phrase_depth_final': phrase_depth, 'duration_beats': current_time, 'lead_melody_count': len(melody), 'lead_support_count': len(lead_support)}
    composition = Composition(parameters.tempo, leads, metadata=metadata)
    composition.structure_map = build_structure_map(composition, parameters)
    return composition

def build_structure_map(composition: Composition, parameters: CompositionParameters) -> Dict[str, Any]:
    leads = sorted(composition.leads, key=lambda event: (event.start, event.pitch))
    scale_pitches = build_scale_pitches(parameters.lsystem.scale, parameters.lsystem.root_note, parameters.lsystem.octave_range)
    if not leads:
        return {'scale': parameters.lsystem.scale, 'root_note': parameters.lsystem.root_note, 'phrases': [], 'motifs': [], 'lead_contour': [], 'implied_harmonic_centers': [], 'accent_positions': [], 'density_profile': [], 'cadence_points': [], 'rhythmic_density': parameters.rhythm_density, 'duration_beats': 0.0}
    duration_beats = max(float(composition.metadata.get('duration_beats', 0.0)), _events_end_beat(leads))
    phrase_length_beats = max(2.0, parameters.lsystem.phrase_length * 0.5)
    phrase_count = max(1, int((duration_beats + phrase_length_beats - 0.001) // phrase_length_beats))
    phrases: List[Dict[str, Any]] = []
    motifs: List[Dict[str, Any]] = []
    density_profile: List[Dict[str, float]] = []
    harmonic_centers: List[Dict[str, float]] = []
    cadence_points: List[float] = []
    accent_positions = sorted({round(event.start, 3) for event in leads if event.velocity >= 84 or abs(event.start - round(event.start)) < 0.001})
    for phrase_index in range(phrase_count):
        start = phrase_index * phrase_length_beats
        end = min(duration_beats, start + phrase_length_beats)
        if end <= start:
            end = start + phrase_length_beats
        events = [event for event in leads if start <= event.start < end]
        motif_events = events[:min(6, len(events))]
        motif_shape = _contour_sequence(motif_events)
        harmonic_center = _phrase_harmonic_center(events, scale_pitches)
        density = len(events) / max(0.25, end - start)
        direction = _phrase_direction(events)
        cadence = end
        phrases.append({'id': phrase_index, 'start': start, 'end': end, 'motif_id': phrase_index, 'lead_contour_direction': direction, 'harmonic_center': harmonic_center, 'density': density, 'cadence': cadence, 'accent_positions': [position for position in accent_positions if start <= position < end]})
        motifs.append({'id': phrase_index, 'shape': motif_shape, 'pitches': [event.pitch for event in motif_events], 'durations': [event.duration for event in motif_events]})
        harmonic_centers.append({'phrase_id': phrase_index, 'start': start, 'pitch': harmonic_center})
        density_profile.append({'phrase_id': phrase_index, 'start': start, 'end': end, 'density': density})
        cadence_points.append(cadence)
    return {'scale': parameters.lsystem.scale, 'root_note': parameters.lsystem.root_note, 'octave_range': parameters.lsystem.octave_range, 'tempo': composition.tempo, 'phrases': phrases, 'motifs': motifs, 'lead_contour': _contour_sequence(leads), 'implied_harmonic_centers': harmonic_centers, 'accent_positions': accent_positions, 'density_profile': density_profile, 'cadence_points': cadence_points, 'rhythmic_density': parameters.rhythm_density, 'duration_beats': duration_beats, 'scale_pitches': scale_pitches}

def _contour_sequence(events: List[NoteEvent]) -> List[int]:
    return [1 if b.pitch > a.pitch else -1 if b.pitch < a.pitch else 0 for a, b in zip(events, events[1:])]

def _phrase_direction(events: List[NoteEvent]) -> int:
    if len(events) < 2:
        return 0
    return 1 if events[-1].pitch > events[0].pitch else -1 if events[-1].pitch < events[0].pitch else 0

def _phrase_harmonic_center(events: List[NoteEvent], scale_pitches: List[int]) -> int:
    if not events:
        return scale_pitches[len(scale_pitches) // 2]
    weighted = sum((event.pitch * max(0.125, event.duration) for event in events))
    total_duration = sum((max(0.125, event.duration) for event in events))
    return _nearest_scale_pitch(int(round(weighted / total_duration)), scale_pitches)

def ensure_minimum_duration(composition: Composition, parameters: CompositionParameters, min_duration_seconds: float, rng: random.Random, ticks_per_beat: int=DEFAULT_TICKS_PER_BEAT) -> Composition:
    if min_duration_seconds <= 0:
        raise ValueError('min_duration must be greater than zero seconds.')
    extended = Composition(tempo=composition.tempo, leads=list(composition.leads), riffs=[], bass=[], metadata=dict(composition.metadata), structure_map=dict(composition.structure_map))
    extended.metadata.setdefault('extension_sections', [])
    extended.metadata['requested_min_duration_seconds'] = min_duration_seconds
    extended.metadata['initial_duration_seconds'] = playback_duration_seconds(extended, ticks_per_beat)
    attempts = 0
    while playback_duration_seconds(extended, ticks_per_beat) + 0.001 < min_duration_seconds:
        attempts += 1
        if attempts > 256:
            raise RuntimeError('Could not extend the composition to the requested minimum duration after 256 generated sections.')
        varied_parameters = _varied_extension_parameters(parameters, rng, attempts)
        section = compose(varied_parameters, rng)
        if not section.leads:
            continue
        offset = _timeline_end_beat(extended) + rng.choice((0.25, 0.5, 0.75, 1.0))
        rhythm_scale = rng.choice((0.85, 1.0, 1.15, 1.25))
        transformed_leads, lead_technique = _transform_events(section.leads, offset, rhythm_scale, rng, attempts, accompaniment=False)
        if not transformed_leads:
            continue
        extended.leads.extend(transformed_leads)
        extended.leads.sort(key=lambda event: (event.start, event.pitch))
        section_duration = float(section.metadata.get('duration_beats', _events_end_beat(section.leads)))
        extended.metadata['duration_beats'] = max(_timeline_end_beat(extended), offset + section_duration * rhythm_scale)
        extended.metadata['musical_steps'] = int(extended.metadata.get('musical_steps', 0)) + int(section.metadata.get('musical_steps', 0))
        extended.metadata['rest_steps'] = int(extended.metadata.get('rest_steps', 0)) + int(section.metadata.get('rest_steps', 0))
        extended.metadata.setdefault('phrase_lengths', [])
        extended.metadata['phrase_lengths'].extend(section.metadata.get('phrase_lengths', []))
        extended.metadata['extension_sections'].append({'section': attempts, 'offset_beats': offset, 'rhythm_scale': rhythm_scale, 'lead_technique': lead_technique, 'duration_seconds_after_section': playback_duration_seconds(extended, ticks_per_beat)})
        extended.structure_map = build_structure_map(extended, parameters)
    extended.metadata['final_duration_seconds'] = playback_duration_seconds(extended, ticks_per_beat)
    extended.structure_map = build_structure_map(extended, parameters)
    return extended

def playback_duration_seconds(composition: Composition, ticks_per_beat: int=DEFAULT_TICKS_PER_BEAT) -> float:
    return _ticks_to_seconds(_playback_end_ticks(composition, ticks_per_beat), composition.tempo, ticks_per_beat)

def timeline_duration_seconds(composition: Composition, ticks_per_beat: int=DEFAULT_TICKS_PER_BEAT) -> float:
    ticks = int(round(_timeline_end_beat(composition) * ticks_per_beat))
    return _ticks_to_seconds(ticks, composition.tempo, ticks_per_beat)

def _playback_end_ticks(composition: Composition, ticks_per_beat: int) -> int:
    end_beat = max((_events_end_beat(events) for events in composition.layer_events().values()))
    return int(round(end_beat * ticks_per_beat))

def _timeline_end_beat(composition: Composition) -> float:
    return max(_events_end_beat(composition.leads), _events_end_beat(composition.riffs), _events_end_beat(composition.bass), _events_end_beat(composition.drums), _events_end_beat(composition.pads), float(composition.metadata.get('duration_beats', 0.0)))

def _events_end_beat(events: Iterable[NoteEvent]) -> float:
    return max((event.start + event.duration for event in events), default=0.0)

def _ticks_to_seconds(ticks: int, tempo: int, ticks_per_beat: int) -> float:
    if tempo <= 0:
        raise ValueError('tempo must be greater than zero.')
    return ticks / ticks_per_beat * (60.0 / tempo)

def _varied_extension_parameters(parameters: CompositionParameters, rng: random.Random, section_index: int) -> CompositionParameters:
    lsystem = parameters.lsystem
    ca = parameters.ca
    lsystem_variation = replace(lsystem, iterations=int(clamp(lsystem.iterations + rng.choice((-1, 0, 1, 1)), 2, 7)), phrase_length=int(clamp(lsystem.phrase_length + rng.choice((-2, 0, 2, 4)), 4, 16)))
    ca_variation = replace(ca, steps=max(ca.steps, int(ca.steps * rng.uniform(0.9, 1.45))), seed_density=clamp(ca.seed_density + rng.uniform(-0.14, 0.14), 0.08, 0.78))
    return replace(parameters, lsystem=lsystem_variation, ca=ca_variation, rhythm_density=clamp(parameters.rhythm_density + rng.uniform(-0.16, 0.16), 0.22, 0.94), accompaniment_density=clamp(parameters.accompaniment_density + rng.uniform(-0.18, 0.24) + (0.03 if section_index % 3 == 0 else 0.0), 0.0, 0.86))

def _transform_events(events: List[NoteEvent], offset: float, rhythm_scale: float, rng: random.Random, section_index: int, accompaniment: bool) -> tuple[List[NoteEvent], str]:
    if not events:
        return ([], 'none')
    center = int(round(sum((event.pitch for event in events)) / len(events)))
    register_shift = rng.choice((-12, -7, -5, 0, 5, 7, 12))
    invert = section_index % 4 == 2 or rng.random() < 0.24
    velocity_shift = rng.randint(-14, 14) + (section_index % 5 - 2) * 3
    accent_every = rng.choice((3, 4, 5, 6))
    duration_mutation = rng.choice((0.85, 1.0, 1.1, 1.2))
    transformed: List[NoteEvent] = []
    for index, event in enumerate(events):
        pitch = event.pitch + register_shift
        if invert:
            pitch = center - (pitch - center)
        if index % 7 == 0:
            pitch += rng.choice((-2, 0, 2))
        if accompaniment:
            pitch -= 12 if index % 2 == 0 else 5
        velocity = event.velocity + velocity_shift
        if index % accent_every == 0:
            velocity += 8
        if accompaniment:
            velocity -= 8
        local_start = event.start * rhythm_scale
        local_duration = event.duration * rhythm_scale * (duration_mutation if index % 5 == 0 else 1.0)
        transformed.append(NoteEvent(start=offset + local_start, duration=max(0.125, local_duration), pitch=_clamp_midi_pitch(pitch), velocity=int(clamp(velocity, 24, 124))))
    technique = 'inversion' if invert else 'contour-preserving'
    technique += f', register_shift={register_shift}, rhythm_scale={rhythm_scale:.2f}'
    return (transformed, technique)

def _clamp_midi_pitch(pitch: int) -> int:
    return int(clamp(pitch, 0, 127))

def _duration_from_features(duration_index: int, density: float) -> float:
    durations = (0.25, 0.5, 0.75, 1.0)
    index = duration_index
    if density < 0.25:
        index = min(3, index + 1)
    elif density > 0.7:
        index = max(0, index - 1)
    return durations[index]

def _velocity_from_features(velocity_value: int, accent_bit: int, density: float, rng: random.Random) -> int:
    velocity = 46 + int(density * 38) + velocity_value * 4 + accent_bit * 18
    velocity += rng.randint(-5, 5)
    return int(clamp(velocity, 32, 122))

def _is_active(rhythm_density: float, active_bit: int, accent_bit: int, rng: random.Random) -> bool:
    gate = 1.0 if active_bit else 0.28
    probability = clamp(rhythm_density * gate + (0.12 if accent_bit else 0.0), 0.02, 0.98)
    return rng.random() < probability

def _accompaniment_probability(accompaniment_density: float, accompaniment_bit: int, accent_bit: int) -> float:
    gate = 1.0 if accompaniment_bit else 0.22
    accent_boost = 0.08 if accent_bit else 0.0
    return clamp(accompaniment_density * gate + accent_boost, 0.0, 0.9)

def _move_pitch_index(action: str, index: int, pitch_count: int, rng: random.Random) -> int:
    if pitch_count <= 0:
        raise ValueError('Cannot move pitch index without scale pitches.')
    if action == 'step_up':
        index += 1
    elif action == 'step_down':
        index -= 1
    elif action == 'leap_up':
        index += rng.choice((2, 3, 4))
    elif action == 'leap_down':
        index -= rng.choice((2, 3, 4))
    elif action == 'hold':
        index += 0
    return int(clamp(index, 0, pitch_count - 1))

def _emit_motif(melody: List[NoteEvent], motif: List[int], start: float, duration: float, velocity: int, scale_pitches: List[int], variation: int) -> tuple[int, float]:
    if not motif:
        return (0, start + duration)
    note_duration = max(0.25, duration / len(motif))
    current_time = start
    emitted = 0
    for pitch in motif:
        varied_pitch = _nearest_scale_pitch(pitch + variation, scale_pitches)
        melody.append(NoteEvent(current_time, note_duration, varied_pitch, velocity))
        current_time += note_duration
        emitted += 1
    return (emitted, current_time)

def _invert_motif(motif: List[int], center: int, scale_pitches: List[int]) -> List[int]:
    return [_nearest_scale_pitch(center - (pitch - center), scale_pitches) for pitch in motif]

def _nearest_scale_pitch(pitch: int, scale_pitches: List[int]) -> int:
    return min(scale_pitches, key=lambda candidate: abs(candidate - pitch))

def _make_accompaniment_note(scale_pitches: List[int], pitch_index: int, start: float, duration: float, melody_velocity: int) -> NoteEvent:
    validate_positive_int('scale pitch count', len(scale_pitches))
    lower_index = max(0, pitch_index - 7)
    pitch = scale_pitches[lower_index]
    return NoteEvent(start=max(0.0, start), duration=max(0.5, duration * 1.5), pitch=pitch, velocity=int(clamp(melody_velocity - 22, 28, 96)))
