from __future__ import annotations
import random
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence
from .arrangement import Arrangement, BEATS_PER_BAR, DEFAULT_BARS_PER_LOOP, arrangement_from_template
from .cellular_automaton import ElementaryCellularAutomaton, features_for_step
from .composition import Composition, CompositionParameters, NoteEvent
from .config import build_scale_pitches, clamp
from .grooves import GrooveProfile, get_groove
from .harmony import HarmonyPlan, harmony_plan_for_genome
from .loops import LoopPattern, quantize

@dataclass(frozen=True)
class LeadMotifFamily:
    scale: str
    root_note: str
    main: LoopPattern
    alternate: LoopPattern
    teaser: LoopPattern
    breakdown: LoopPattern
    climax: LoopPattern
    final_climax: LoopPattern
    harmonic_centers: List[int]
    phrase_boundaries: List[float]
    hook_notes: List[int]
    cadence_notes: List[int]
    tension_release: List[float]

    def as_patterns(self) -> Dict[str, LoopPattern]:
        return {'main': self.main, 'alternate': self.alternate, 'teaser': self.teaser, 'breakdown': self.breakdown, 'climax': self.climax, 'final_climax': self.final_climax}

class LeadGenerator:

    def generate(self, parameters: CompositionParameters, rng: random.Random, arrangement: Arrangement | None=None, genome: object | None=None, riffs_enabled: bool=False, bass_enabled: bool=False, drums_enabled: bool=True, pads_enabled: bool=True) -> Composition:
        parameters.validate()
        arrangement = arrangement or arrangement_from_template('classic_trance', DEFAULT_BARS_PER_LOOP)
        plan = harmony_plan_for_genome(genome, arrangement) if genome is not None else None
        family = self.generate_motif_family(parameters, rng, genome, plan)
        leads = self.expand_leads_across_arrangement(family, arrangement, rng, genome)
        structure_map = build_lead_structure_map(parameters, arrangement, family, leads, riffs_enabled=riffs_enabled, bass_enabled=bass_enabled, drums_enabled=drums_enabled, pads_enabled=pads_enabled, plan=plan)
        composition = Composition(tempo=parameters.tempo, leads=sorted(leads, key=lambda event: (event.start, event.pitch)), metadata={'genre': arrangement.genre, 'style': arrangement.genre, 'duration_beats': arrangement.total_beats, 'bars_per_loop': arrangement.bars_per_loop, 'arrangement_template': arrangement.template, 'lead_motif_family': {key: [event.__dict__ for event in pattern.events] for key, pattern in family.as_patterns().items()}, 'harmonic_seed': plan.seed.name if plan else 'aeolian_pedal', 'enabled_layers': ['leads']}, structure_map=structure_map)
        return composition

    def extend_to_minimum_duration(self, composition: Composition, parameters: CompositionParameters, min_duration_seconds: float, rng: random.Random) -> Composition:
        return composition

    def generate_motif_family(self, parameters: CompositionParameters, rng: random.Random, genome: object | None=None, plan: HarmonyPlan | None=None) -> LeadMotifFamily:
        scale = parameters.lsystem.scale
        root_note = parameters.lsystem.root_note
        lead_pitches = build_scale_pitches(scale, root_note, parameters.lsystem.octave_range)
        center_index = len(lead_pitches) // 2
        hook_shape = int(getattr(genome, 'lead_hook_shape', 0)) if genome is not None else 0
        variation_amount = float(getattr(genome, 'lead_variation_amount', 0.25)) if genome is not None else 0.25
        hook_repetition = float(getattr(genome, 'lead_hook_repetition', 0.75)) if genome is not None else 0.75
        loop_density = float(getattr(genome, 'loop_density', parameters.rhythm_density)) if genome is not None else parameters.rhythm_density
        drop_density = float(getattr(genome, 'drop_density', 0.88)) if genome is not None else 0.88
        rule_set = str(getattr(genome, 'lsystem_rules', parameters.lsystem.rules and 'balanced' or 'balanced'))
        ca_grid = ElementaryCellularAutomaton(parameters.ca).generate(rng)
        degree_progressions = _degree_progressions_for_rule_set(rule_set)
        groove = get_groove(str(getattr(genome, 'groove', ''))) if getattr(genome, 'groove', None) else None
        phrase_cells = groove.lead_cells if groove is not None else _phrase_cells_for_rule_set(rule_set)
        note_length = groove.lead_note_length if groove is not None else 0.45
        if plan is not None:
            progression = _seed_degree_progression(plan)
            harmonic_degree_centers = progression[::2]
        else:
            progression = degree_progressions[hook_shape % len(degree_progressions)]
            harmonic_degree_centers = _harmonic_centers_for_rule_set(rule_set)
        harmonic_centers = [_pitch_by_degree(lead_pitches, center_index, degree) for degree in harmonic_degree_centers]
        phrase_boundaries = [0.0, 8.0, 16.0, 24.0, 32.0]
        main_events = _make_main_hook(lead_pitches, center_index, progression, rng, density=loop_density, repetition=hook_repetition, velocity_base=82, phrase_cells=phrase_cells, ca_grid=ca_grid, note_length=note_length, groove=groove)
        alternate_events = _vary_events(main_events, lead_pitches, rng, variation_amount, velocity_shift=-4)
        teaser_events = _teaser_from(main_events, keep_every=5, velocity_shift=-18, duration_scale=1.35)
        breakdown_events = _teaser_from(main_events, keep_every=2, velocity_shift=-12, duration_scale=1.65)
        climax_events = _densify_events(main_events, lead_pitches, rng, amount=drop_density, velocity_shift=10)
        final_events = _densify_events(_vary_events(main_events, lead_pitches, rng, variation_amount * 0.7, octave_bias=12), lead_pitches, rng, amount=drop_density, velocity_shift=14)
        cadence_notes = [_nearest_event_pitch(main_events, boundary - 0.001) for boundary in phrase_boundaries[1:]]
        hook_notes = [event.pitch for event in main_events if event.velocity >= 88][:12]
        tension_release = [0.25, 0.42, 0.6, 0.38, 0.8, 1.0, 0.45, 1.0, 0.2]
        return LeadMotifFamily(scale=scale, root_note=root_note, main=LoopPattern('lead_main_8bar', events=main_events, motif_id='main_hook', variation_level=0.0, source='lead'), alternate=LoopPattern('lead_alt_8bar', events=alternate_events, motif_id='alternate_hook', variation_level=variation_amount, source='lead'), teaser=LoopPattern('lead_teaser_8bar', events=teaser_events, motif_id='teaser', variation_level=0.15, source='lead'), breakdown=LoopPattern('lead_breakdown_8bar', events=breakdown_events, motif_id='breakdown', variation_level=0.25, source='lead'), climax=LoopPattern('lead_climax_8bar', events=climax_events, motif_id='climax_hook', variation_level=0.35, source='lead'), final_climax=LoopPattern('lead_final_climax_8bar', events=final_events, motif_id='final_climax_hook', variation_level=0.45, source='lead'), harmonic_centers=harmonic_centers, phrase_boundaries=phrase_boundaries, hook_notes=hook_notes, cadence_notes=cadence_notes, tension_release=tension_release)

    def expand_leads_across_arrangement(self, family: LeadMotifFamily, arrangement: Arrangement, rng: random.Random, genome: object | None=None) -> List[NoteEvent]:
        events: List[NoteEvent] = []
        breakdown_sparsity = float(getattr(genome, 'breakdown_sparsity', 0.72)) if genome is not None else 0.72
        transition_amount = float(getattr(genome, 'transition_fill_amount', 0.45)) if genome is not None else 0.45
        for block in arrangement.loop_blocks():
            section = arrangement.section_by_name(block.section_name)
            pattern, velocity_scale, octave_shift = _pattern_for_lead_role(section.lead_role, family, block.section_loop_index, rng, breakdown_sparsity)
            block_events = pattern.shifted(block.start_beat, velocity_scale=velocity_scale, octave_shift=octave_shift)
            block_events = _section_gate_leads(block_events, section.lead_role, block.start_beat, rng, breakdown_sparsity)
            events.extend(block_events)
            if block.index > 0 and rng.random() < transition_amount and (section.lead_role in {'compressed', 'full_hook', 'final_hook'}):
                events.extend(_lead_transition_fill(family, block.start_beat, rng, intensity=section.energy))
        return sorted(events, key=lambda event: (event.start, event.pitch))

def build_lead_structure_map(parameters: CompositionParameters, arrangement: Arrangement, family: LeadMotifFamily, leads: Sequence[NoteEvent], riffs_enabled: bool=False, bass_enabled: bool=False, drums_enabled: bool=True, pads_enabled: bool=True, plan: HarmonyPlan | None=None) -> Dict[str, object]:
    base_map = arrangement.to_structure_map(riffs_enabled=riffs_enabled, bass_enabled=bass_enabled, drums_enabled=drums_enabled, pads_enabled=pads_enabled)
    loop_beats = arrangement.bars_per_loop * BEATS_PER_BAR
    centers_by_loop = plan.harmonic_centers_by_loop(parameters.lsystem.octave_range) if plan is not None else [family.harmonic_centers for _ in range(arrangement.loop_count)]
    phrases: List[Dict[str, object]] = []
    motifs: List[Dict[str, object]] = []
    density_profile: List[Dict[str, float]] = []
    harmonic_centers: List[Dict[str, object]] = []
    accent_positions: List[float] = []
    cadence_points: List[float] = []
    for block in arrangement.loop_blocks():
        section = arrangement.section_by_name(block.section_name)
        loop_events = [event for event in leads if block.start_beat <= event.start < block.end_beat]
        density = len(loop_events) / max(1.0, loop_beats)
        local_harmonic_centers = centers_by_loop[block.index % len(centers_by_loop)]
        for phrase_index in range(4):
            phrase_start = block.start_beat + phrase_index * 8.0
            phrase_end = phrase_start + 8.0
            phrase_events = [event for event in loop_events if phrase_start <= event.start < phrase_end]
            center = local_harmonic_centers[phrase_index % len(local_harmonic_centers)]
            phrase_id = len(phrases)
            motif_id = f'{block.section_name}:{block.index}:{phrase_index}'
            phrase_density = len(phrase_events) / 8.0
            cadence = phrase_end
            accents = [round(event.start, 3) for event in phrase_events if event.velocity >= 88 or abs(event.start % 4.0) < 0.001]
            phrases.append({'id': phrase_id, 'start': phrase_start, 'end': phrase_end, 'motif_id': phrase_id, 'motif_label': motif_id, 'section': section.name, 'loop_block': block.index, 'section_loop_index': block.section_loop_index, 'lead_role': section.lead_role, 'lead_contour_direction': _phrase_direction(phrase_events), 'harmonic_center': center, 'density': phrase_density, 'cadence': cadence, 'accent_positions': accents})
            motifs.append({'id': phrase_id, 'label': motif_id, 'shape': _contour_sequence(phrase_events), 'pitches': [event.pitch for event in phrase_events[:8]], 'durations': [event.duration for event in phrase_events[:8]], 'source': 'lead', 'section': section.name})
            harmonic_centers.append({'phrase_id': phrase_id, 'start': phrase_start, 'pitch': center, 'section': section.name})
            cadence_points.append(cadence)
            accent_positions.extend(accents)
        density_profile.append({'loop_block': block.index, 'section': section.name, 'start': block.start_beat, 'end': block.end_beat, 'density': density, 'energy': section.energy})
    base_map.update({'scale': parameters.lsystem.scale, 'root_note': parameters.lsystem.root_note, 'octave_range': parameters.lsystem.octave_range, 'tempo': parameters.tempo, 'phrases': phrases, 'motifs': motifs, 'lead_contour': _contour_sequence(list(leads)), 'implied_harmonic_centers': harmonic_centers, 'harmonic_centers_by_loop': centers_by_loop, 'harmony': plan.describe() if plan is not None else {}, 'harmonic_seed': plan.seed.name if plan is not None else '', 'accent_positions': sorted(set((round(value, 3) for value in accent_positions))), 'density_profile': density_profile, 'cadence_points': cadence_points, 'hook_notes': family.hook_notes, 'cadence_notes': family.cadence_notes, 'tension_release_map': list(arrangement.section_energy_curve()), 'duration_beats': arrangement.total_beats, 'scale_pitches': build_scale_pitches(parameters.lsystem.scale, parameters.lsystem.root_note, parameters.lsystem.octave_range)})
    return base_map

def _make_main_hook(scale_pitches: Sequence[int], center_index: int, progression: Sequence[int], rng: random.Random, density: float, repetition: float, velocity_base: int, phrase_cells: Sequence[Sequence[float]], ca_grid: Sequence[Sequence[int]], note_length: float=0.45, groove: GrooveProfile | None=None) -> List[NoteEvent]:
    events: List[NoteEvent] = []
    grid = 0.125 if groove is not None and groove.swing > 0.0 else 0.25
    for phrase in range(4):
        phrase_start = phrase * 8.0
        cell = phrase_cells[phrase % len(phrase_cells)]
        center_degree = progression[phrase * 2 % len(progression)]
        for index, local in enumerate(cell):
            step = phrase * len(cell) + index
            features = features_for_step(list(ca_grid), step)
            ca_density_bias = (features.density - 0.5) * 0.18
            if index not in (0, len(cell) - 1) and rng.random() > clamp(density + 0.18 + ca_density_bias, 0.28, 0.98):
                continue
            degree_offset = progression[(phrase * 2 + index) % len(progression)] - center_degree
            if rng.random() < repetition:
                degree_offset = [0, 2, 4, 2, 5, 4, 2, 0, -1][index % 9]
            if features.accent_bit:
                degree_offset += 1 if index % 2 == 0 else -1
            elif features.active_bit == 0 and index not in (0, len(cell) - 1):
                degree_offset -= 1
            pitch = _pitch_by_degree(scale_pitches, center_index, center_degree + degree_offset)
            if phrase >= 2 and index % 4 == 1:
                pitch = _pitch_by_degree(scale_pitches, center_index, center_degree + degree_offset + 2)
            duration = note_length * (0.72 if features.duration_index == 0 else 1.0 if local % 1.0 else 1.45)
            if index == len(cell) - 1:
                duration = min(max(1.4, note_length * 3.0), 8.0 - local)
            velocity = velocity_base + (12 if index in (0, len(cell) - 1) else 0) + phrase * 2 + features.velocity_value + rng.randint(-4, 4)
            onset = groove.swung(local) if groove is not None else local
            events.append(NoteEvent(quantize(phrase_start + onset, grid), max(0.1, duration), pitch, int(clamp(velocity, 46, 118))))
    return sorted(events, key=lambda event: (event.start, event.pitch))

def _seed_degree_progression(plan: HarmonyPlan) -> tuple[int, ...]:
    from .config import scale_pattern
    pattern = scale_pattern(plan.seed.mode)
    degrees: List[int] = []
    for chord in plan.seed.progression[:4]:
        semitone = chord.root_offset % 12
        degree = min(range(len(pattern)), key=lambda index: abs(pattern[index] - semitone))
        degrees.extend((degree, degree + 2))
    while len(degrees) < 8:
        degrees.extend(degrees[:2] or [0, 2])
    return tuple(degrees[:8])

def _degree_progressions_for_rule_set(rule_set: str) -> Sequence[Sequence[int]]:
    if rule_set.startswith('ebm'):
        return ((0, 0, 3, 0, -1, 0, 3, 0), (0, 2, 0, -1, 0, 2, 3, 0), (0, -2, 0, 3, 0, -1, 0, 2), (0, 0, 1, 0, 3, 0, 1, 0))
    if rule_set.startswith('berlin'):
        return ((0, 2, 3, 5, 3, 2, 0, -1), (0, 1, 3, 4, 6, 4, 3, 1), (0, 2, 4, 5, 7, 5, 4, 2), (0, -1, 1, 3, 5, 6, 5, 3))
    return ((0, 2, 4, 3, 5, 4, 2, 0), (0, 3, 5, 4, 2, 4, 3, 1), (0, 2, 5, 7, 5, 4, 2, 0), (0, -1, 2, 4, 5, 4, 2, 0))

def _phrase_cells_for_rule_set(rule_set: str) -> Sequence[Sequence[float]]:
    if rule_set.startswith('ebm'):
        return ((0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0), (0.0, 0.5, 1.5, 2.5, 3.0, 4.0, 5.0, 7.0))
    if rule_set.startswith('berlin'):
        return ((0.0, 0.75, 1.5, 2.25, 3.0, 4.5, 6.0, 7.5), (0.0, 1.0, 1.75, 2.5, 4.0, 5.25, 6.5, 7.25), (0.0, 0.5, 1.25, 2.0, 3.5, 4.25, 5.75, 7.0))
    return ((0.0, 0.5, 1.0, 1.5, 2.5, 3.0, 4.0, 5.0, 6.5), (0.0, 0.75, 1.5, 2.0, 3.0, 4.0, 5.5, 6.0))

def _harmonic_centers_for_rule_set(rule_set: str) -> Sequence[int]:
    if rule_set.startswith('ebm'):
        return (0, 0, 3, 0)
    if rule_set.startswith('berlin'):
        return (0, 2, 4, 5)
    return (0, 5, 3, 4)

def _vary_events(events: Sequence[NoteEvent], scale_pitches: Sequence[int], rng: random.Random, amount: float, velocity_shift: int=0, octave_bias: int=0) -> List[NoteEvent]:
    varied: List[NoteEvent] = []
    for index, event in enumerate(events):
        pitch = event.pitch + octave_bias
        if rng.random() < amount:
            pitch = _scale_shift(pitch, scale_pitches, rng.choice((-2, -1, 1, 2)))
        if index % 7 == 4:
            pitch = _scale_shift(pitch, scale_pitches, 1)
        start = event.start
        if index % 5 == 2 and rng.random() < amount * 0.5:
            start = quantize(start + 0.25, 0.25)
        varied.append(NoteEvent(start, event.duration, _nearest_scale_pitch(pitch, scale_pitches), int(clamp(event.velocity + velocity_shift, 30, 124))))
    return sorted(varied, key=lambda event: (event.start, event.pitch))

def _teaser_from(events: Sequence[NoteEvent], keep_every: int, velocity_shift: int, duration_scale: float) -> List[NoteEvent]:
    teaser = []
    for index, event in enumerate(events):
        if index % keep_every == 0 or abs((event.start + event.duration) % 8.0) < 0.1:
            teaser.append(NoteEvent(start=event.start, duration=min(2.0, max(0.5, event.duration * duration_scale)), pitch=event.pitch, velocity=int(clamp(event.velocity + velocity_shift, 24, 110))))
    return teaser

def _densify_events(events: Sequence[NoteEvent], scale_pitches: Sequence[int], rng: random.Random, amount: float, velocity_shift: int) -> List[NoteEvent]:
    dense = list(events)
    for event in events:
        if event.duration >= 0.45 and rng.random() < amount * 0.38:
            echo_start = quantize(event.start + 0.5, 0.25)
            if echo_start < DEFAULT_BARS_PER_LOOP * BEATS_PER_BAR:
                dense.append(NoteEvent(start=echo_start, duration=max(0.25, event.duration * 0.5), pitch=_scale_shift(event.pitch, scale_pitches, rng.choice((-1, 1, 2))), velocity=int(clamp(event.velocity + velocity_shift - 12, 36, 124))))
    return sorted(dense, key=lambda event: (event.start, event.pitch))

def _pattern_for_lead_role(role: str, family: LeadMotifFamily, loop_index: int, rng: random.Random, breakdown_sparsity: float) -> tuple[LoopPattern, float, int]:
    if role == 'teaser':
        return (family.teaser, 0.7, 0)
    if role == 'hints':
        return (family.teaser if loop_index == 0 else family.alternate, 0.78, 0)
    if role == 'fragments':
        return (family.alternate if loop_index % 2 else family.teaser, 0.88, 0)
    if role == 'breakdown':
        return (family.breakdown, 0.76, 0)
    if role == 'compressed':
        return (family.climax, 0.92, 0)
    if role == 'full_hook':
        return (family.climax if loop_index % 2 else family.main, 1.02, 0)
    if role == 'variation_sparse':
        return (family.breakdown, 0.7 * (1.0 - breakdown_sparsity * 0.15), 0)
    if role == 'final_hook':
        return (family.final_climax if loop_index % 2 else family.climax, 1.08, 12 if loop_index >= 2 else 0)
    if role == 'echo':
        return (family.teaser, 0.62, 0)
    return (family.teaser, 0.5, 0)

def _section_gate_leads(events: Sequence[NoteEvent], role: str, block_start: float, rng: random.Random, breakdown_sparsity: float) -> List[NoteEvent]:
    if role in {'full_hook', 'final_hook', 'compressed'}:
        return list(events)
    gated: List[NoteEvent] = []
    for event in events:
        local = event.start - block_start
        keep = True
        if role == 'teaser':
            keep = local >= 16.0 and int(local) % 4 in (0, 2)
        elif role == 'hints':
            keep = int(local // 8) in (1, 3) or local >= 24.0
        elif role == 'fragments':
            keep = int(local // 4) % 2 == 0 or event.velocity > 84
        elif role in {'breakdown', 'variation_sparse'}:
            keep = rng.random() > breakdown_sparsity * 0.28 or event.velocity >= 84
        elif role == 'echo':
            keep = local < 16.0 and (event.velocity >= 84 or int(local) % 8 == 0)
        if keep:
            gated.append(event)
    return gated

def _lead_transition_fill(family: LeadMotifFamily, block_start: float, rng: random.Random, intensity: float) -> List[NoteEvent]:
    fill_start = block_start - 2.0
    if fill_start < 0:
        return []
    source = family.climax.events[-6:] or family.main.events[-6:]
    events: List[NoteEvent] = []
    for index, event in enumerate(source):
        start = fill_start + index * 0.25
        if start >= block_start:
            break
        pitch = event.pitch + (12 if index > 3 and intensity > 0.75 else 0)
        events.append(NoteEvent(start, 0.18, pitch, int(clamp(72 + index * 6 + intensity * 20, 50, 124))))
    return events

def _pitch_by_degree(scale_pitches: Sequence[int], center_index: int, degree_offset: int) -> int:
    index = int(clamp(center_index + degree_offset, 0, len(scale_pitches) - 1))
    return scale_pitches[index]

def _scale_shift(pitch: int, scale_pitches: Sequence[int], steps: int) -> int:
    nearest_index = min(range(len(scale_pitches)), key=lambda idx: abs(scale_pitches[idx] - pitch))
    shifted_index = int(clamp(nearest_index + steps, 0, len(scale_pitches) - 1))
    return scale_pitches[shifted_index]

def _nearest_scale_pitch(pitch: int, scale_pitches: Sequence[int]) -> int:
    return min(scale_pitches, key=lambda candidate: abs(candidate - pitch))

def _nearest_event_pitch(events: Sequence[NoteEvent], before: float) -> int:
    previous = [event for event in events if event.start <= before]
    if previous:
        return previous[-1].pitch
    return events[0].pitch if events else 60

def _contour_sequence(events: Sequence[NoteEvent]) -> List[int]:
    ordered = sorted(events, key=lambda event: (event.start, event.pitch))
    return [1 if b.pitch > a.pitch else -1 if b.pitch < a.pitch else 0 for a, b in zip(ordered, ordered[1:])]

def _phrase_direction(events: Sequence[NoteEvent]) -> int:
    ordered = sorted(events, key=lambda event: (event.start, event.pitch))
    if len(ordered) < 2:
        return 0
    return 1 if ordered[-1].pitch > ordered[0].pitch else -1 if ordered[-1].pitch < ordered[0].pitch else 0
