from __future__ import annotations
import statistics
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Sequence
from .candidate import CandidateComposition
from .composition import NoteEvent
from .config import PENALTY_WEIGHTS, clamp, mean, root_pitch_class, scale_pattern
from .drum_generator import CLAP, CLOSED_HAT, CRASH, KICK, OPEN_HAT, SNARE
from .harmonic_seeds import HARMONIC_SEEDS, get_harmonic_seed

@dataclass(frozen=True)
class FitnessProfile:
    genre: str
    weights: Mapping[str, float]
    penalty_weights: Mapping[str, float]
    diversity_weight: float = 0.2

@dataclass(frozen=True)
class DiversityContext:
    fingerprints: Mapping[str, Mapping[str, Any]]
    diversity_weight: float = 0.2

def evaluate_candidate(candidate: CandidateComposition, *, genre: str, min_duration_seconds: float, enable_riffs: bool, enable_bass: bool, enable_drums: bool=True, diversity_context: DiversityContext | None=None, fitness_profile: FitnessProfile | None=None) -> Dict[str, object]:
    genre = _normalize_genre(genre or _genre(candidate))
    profile = fitness_profile or fitness_profile_for_genre(genre, diversity_context.diversity_weight if diversity_context else None)
    subscores = _common_subscores(candidate, min_duration_seconds, enable_riffs, enable_bass, enable_drums)
    if genre == 'ebm':
        subscores.update(_ebm_subscores(candidate, enable_riffs, enable_bass, enable_drums))
    elif genre == 'berlin_school':
        subscores.update(_berlin_school_subscores(candidate, enable_riffs, enable_bass, enable_drums))
    else:
        subscores.update(_classic_trance_subscores(candidate, enable_riffs, enable_bass, enable_drums))
    penalties = penalty_scores(candidate, min_duration_seconds, enable_riffs, enable_bass, enable_drums)
    fingerprint = candidate_fingerprint(candidate)
    nearest_distance = nearest_fingerprint_distance(candidate.candidate_id, fingerprint, diversity_context)
    diversity_score = clamp(nearest_distance, 0.0, 1.0)
    weighted_subscores = {name: value * profile.weights.get(name, 1.0) for name, value in subscores.items()}
    weighted_penalties = {name: value * profile.penalty_weights.get(name, PENALTY_WEIGHTS.get(name, 1.0)) for name, value in penalties.items()}
    aesthetic_score = sum(weighted_subscores.values())
    penalty_total = sum(weighted_penalties.values())
    final_score = aesthetic_score + profile.diversity_weight * diversity_score - penalty_total
    return {'final_score': final_score, 'aesthetic_score': aesthetic_score, 'diversity_score': diversity_score, 'nearest_candidate_distance': nearest_distance, 'genre': genre, 'fitness_profile': {'genre': profile.genre, 'diversity_weight': profile.diversity_weight, 'weights': dict(profile.weights)}, 'subscores': subscores, 'weighted_subscores': weighted_subscores, 'penalties': penalties, 'weighted_penalties': weighted_penalties, 'musical_fingerprint': fingerprint}

def fitness_profile_for_genre(genre: str, diversity_weight: float | None=None) -> FitnessProfile:
    genre = _normalize_genre(genre)
    common = {'duration': 1.1, 'melodic_coherence': 0.7, 'scale_coherence_score': 0.7, 'section_contrast_score': 0.75, 'harmonic_seed_conformance_score': 1.3, 'voice_leading_score': 0.85}
    if genre == 'ebm':
        weights = {**common, 'loop_coherence_score': 1.25, 'genre_arrangement_score': 1.15, 'ebm_machine_pulse_score': 1.45, 'ebm_bass_sequence_score': 1.45, 'ebm_body_groove_score': 1.35, 'ebm_command_phrase_score': 1.05, 'ebm_dark_pitch_score': 0.9, 'ebm_controlled_repetition_score': 1.2, 'layer_alignment': 1.05}
        return FitnessProfile(genre, weights, PENALTY_WEIGHTS, 0.28 if diversity_weight is None else diversity_weight)
    if genre == 'berlin_school':
        weights = {**common, 'loop_coherence_score': 0.85, 'genre_arrangement_score': 1.15, 'berlin_longform_evolution_score': 1.45, 'berlin_sequencer_continuity_score': 1.35, 'berlin_atmosphere_score': 1.2, 'berlin_slow_arc_score': 1.3, 'berlin_low_drum_score': 1.1, 'berlin_mutation_score': 1.1, 'layer_alignment': 0.75}
        return FitnessProfile(genre, weights, PENALTY_WEIGHTS, 0.34 if diversity_weight is None else diversity_weight)
    weights = {**common, 'loop_coherence_score': 1.35, 'genre_arrangement_score': 1.45, 'classic_trance_drop_score': 1.35, 'classic_trance_hook_emergence_score': 1.35, 'classic_trance_drum_transition_score': 1.2, 'classic_trance_breakdown_contrast_score': 1.05, 'layer_alignment': 0.95}
    return FitnessProfile('classic_trance', weights, PENALTY_WEIGHTS, 0.2 if diversity_weight is None else diversity_weight)

def candidate_fingerprint(candidate: CandidateComposition) -> Dict[str, Any]:
    melodic = candidate.leads + candidate.riffs + candidate.bass
    pitch_hist = [0] * 12
    for event in melodic:
        pitch_hist[event.pitch % 12] += 1
    total_pitch = max(1, sum(pitch_hist))
    onset_hist = [0] * 16
    for event in _all_events(candidate):
        onset_hist[int(round(event.start % 8.0 * 2)) % 16] += 1
    total_onset = max(1, sum(onset_hist))
    sections = _sections(candidate)
    density_profile = [round(_section_density(candidate, section), 4) for section in sections]
    layer_profile = {'leads': _section_density_profile(candidate.leads, candidate), 'riffs': _section_density_profile(candidate.riffs, candidate), 'bass': _section_density_profile(candidate.bass, candidate), 'drums': _section_density_profile(candidate.drums, candidate), 'pads': _section_density_profile(candidate.pads, candidate)}
    genome = candidate.genome
    hook_shape = int(getattr(genome, 'lead_hook_shape', 0))
    return {'harmonic_seed': str(getattr(genome, 'harmonic_seed', '')), 'groove': str(getattr(genome, 'groove', '')), 'mode': str(getattr(genome, 'scale', '')), 'harmonic_rhythm_bars': int(getattr(genome, 'harmonic_rhythm_bars', 0)), 'pedal_strength': round(float(getattr(genome, 'pedal_strength', 0.0)), 4), 'voicing_openness': round(float(getattr(genome, 'voicing_openness', 0.0)), 4), 'suspension_amount': round(float(getattr(genome, 'suspension_amount', 0.0)), 4), 'pitch_class_histogram': [round(value / total_pitch, 4) for value in pitch_hist], 'rhythm_onset_histogram': [round(value / total_onset, 4) for value in onset_hist], 'density_by_section': density_profile, 'layer_activity_by_section': layer_profile, 'ca_rule': int(getattr(genome, 'ca_rule', -1)), 'ca_width': int(getattr(genome, 'ca_width', 0)), 'ca_steps': int(getattr(genome, 'ca_steps', 0)), 'lsystem_rule_set': str(getattr(genome, 'lsystem_rules', '')), 'phrase_length': int(getattr(genome, 'phrase_length', 0)), 'hook_shape': hook_shape, 'bass_density': round(float(getattr(genome, 'bass_density', 0.0)), 4), 'riff_density': round(float(getattr(genome, 'riff_density', 0.0)), 4), 'drum_density': round(len(candidate.drums) / max(1.0, candidate.duration_seconds), 4)}

def fingerprint_distance(a: Mapping[str, Any], b: Mapping[str, Any]) -> float:
    numeric = []
    numeric.extend(_sequence_distance(a.get('pitch_class_histogram', []), b.get('pitch_class_histogram', [])))
    numeric.extend(_sequence_distance(a.get('rhythm_onset_histogram', []), b.get('rhythm_onset_histogram', [])))
    numeric.extend(_sequence_distance(a.get('density_by_section', []), b.get('density_by_section', []), scale=1.6))
    for layer in ('leads', 'riffs', 'bass', 'drums', 'pads'):
        numeric.extend(_sequence_distance(a.get('layer_activity_by_section', {}).get(layer, []), b.get('layer_activity_by_section', {}).get(layer, []), scale=1.2))
    for key, scale in (('bass_density', 1.0), ('riff_density', 1.0), ('drum_density', 0.4), ('phrase_length', 16.0), ('hook_shape', 12.0), ('ca_width', 32.0), ('ca_steps', 128.0), ('pedal_strength', 1.0), ('voicing_openness', 1.0), ('suspension_amount', 1.0), ('harmonic_rhythm_bars', 4.0)):
        numeric.append(abs(float(a.get(key, 0.0)) - float(b.get(key, 0.0))) / scale)
    categorical = [0.0 if a.get('ca_rule') == b.get('ca_rule') else 0.2, 0.0 if a.get('lsystem_rule_set') == b.get('lsystem_rule_set') else 0.25, 0.0 if a.get('mode') == b.get('mode') else 0.45, 0.0 if a.get('harmonic_seed') == b.get('harmonic_seed') else 0.9, 0.0 if a.get('groove') == b.get('groove') else 0.7]
    values = numeric + categorical
    return clamp(mean(values) * 3.2 if values else 0.0, 0.0, 1.0)

def nearest_fingerprint_distance(candidate_id: str, fingerprint: Mapping[str, Any], diversity_context: DiversityContext | None) -> float:
    if diversity_context is None:
        return 0.0
    distances = [fingerprint_distance(fingerprint, other) for other_id, other in diversity_context.fingerprints.items() if other_id != candidate_id]
    return min(distances) if distances else 0.0

def _common_subscores(candidate: CandidateComposition, min_duration_seconds: float, enable_riffs: bool, enable_bass: bool, enable_drums: bool) -> Dict[str, float]:
    melodic = candidate.leads + candidate.riffs + candidate.bass
    return {'loop_coherence_score': loop_coherence_score(candidate), 'section_contrast_score': section_contrast_score(candidate, enable_riffs, enable_bass, enable_drums), 'duration': duration_score(candidate, min_duration_seconds), 'melodic_coherence': melodic_coherence_score(candidate), 'scale_coherence_score': _scale_membership_score(melodic, _scale_pitch_classes(candidate)) if melodic else 0.0, 'layer_alignment': layer_alignment_score(candidate, enable_riffs, enable_bass), 'harmonic_seed_conformance_score': harmonic_seed_conformance_score(candidate), 'voice_leading_score': voice_leading_score(candidate)}

def harmonic_seed_conformance_score(candidate: CandidateComposition) -> float:
    harmony = candidate.structure_map.get('harmony') or {}
    chord_plan = harmony.get('chord_plan') or []
    if not chord_plan:
        return 0.0
    seed_name = str(harmony.get('harmonic_seed', candidate.harmonic_seed))
    if seed_name not in HARMONIC_SEEDS:
        return 0.0
    seed = get_harmonic_seed(seed_name)
    sustained = candidate.pads
    melodic = candidate.leads + candidate.riffs
    chord_tone_hits = _chord_tone_ratio(melodic, chord_plan)
    pad_hits = _chord_tone_ratio(sustained, chord_plan) if sustained else chord_tone_hits
    bass_classes = [event.pitch % 12 for event in candidate.bass] or [int(slot['bass_pitch_class']) for slot in chord_plan]
    dominant_share = max((bass_classes.count(pc) for pc in set(bass_classes))) / len(bass_classes)
    pedal_score = dominant_share if seed.pedal else clamp(1.0 - abs(dominant_share - 0.45) * 1.6, 0.0, 1.0)
    return clamp(0.42 * chord_tone_hits + 0.34 * pad_hits + 0.24 * pedal_score, 0.0, 1.0)

def voice_leading_score(candidate: CandidateComposition) -> float:
    pads = candidate.pads
    if len(pads) < 4:
        return 0.0
    by_start: Dict[float, set[int]] = {}
    for event in pads:
        by_start.setdefault(round(event.start, 3), set()).add(event.pitch)
    chords = [pitches for _, pitches in sorted(by_start.items()) if len(pitches) >= 2]
    if len(chords) < 2:
        return 0.0
    scores: List[float] = []
    for previous, current in zip(chords, chords[1:]):
        changed = len(previous.symmetric_difference(current)) / 2.0
        held = len(previous & current)
        if held == 0 and changed == 0:
            continue
        scores.append(clamp(1.0 - abs(changed - 2.0) / 4.0, 0.0, 1.0))
    return mean(scores) if scores else 0.0

def _chord_tone_ratio(events: Sequence[NoteEvent], chord_plan: Sequence[Mapping[str, Any]]) -> float:
    if not events or not chord_plan:
        return 0.0
    ordered = sorted(chord_plan, key=lambda slot: int(slot['start_bar']))
    beats_per_bar = 4
    hits = 0
    counted = 0
    for event in events:
        bar = int(event.start // beats_per_bar)
        slot = next((item for item in ordered if int(item['start_bar']) <= bar < int(item['start_bar']) + int(item['length_bars'])), ordered[-1])
        counted += 1
        if event.pitch % 12 in set(slot['pitch_classes']):
            hits += 1
    return hits / max(1, counted)

def _classic_trance_subscores(candidate: CandidateComposition, enable_riffs: bool, enable_bass: bool, enable_drums: bool) -> Dict[str, float]:
    return {'genre_arrangement_score': classic_trance_arrangement_score(candidate, enable_riffs, enable_bass, enable_drums), 'classic_trance_drop_score': arrival_energy_score(candidate, enable_riffs, enable_bass, enable_drums), 'classic_trance_hook_emergence_score': lead_hook_strength_score(candidate), 'classic_trance_drum_transition_score': mean([drum_groove_score(candidate, enable_drums), transition_quality_score(candidate, enable_drums)]), 'classic_trance_breakdown_contrast_score': _classic_breakdown_contrast(candidate)}

def _ebm_subscores(candidate: CandidateComposition, enable_riffs: bool, enable_bass: bool, enable_drums: bool) -> Dict[str, float]:
    body_names = [str(section.get('name')) for section in _sections(candidate) if 'body' in str(section.get('name', '')).lower() or 'chorus' in str(section.get('name', '')).lower()]
    command_names = [str(section.get('name')) for section in _sections(candidate) if 'verse' in str(section.get('name', '')).lower() or 'command' in str(section.get('name', '')).lower()]
    body_drums = _events_in_named_sections(candidate.drums, candidate, body_names)
    command_leads = _events_in_named_sections(candidate.leads, candidate, command_names)
    body_bass = _events_in_named_sections(candidate.bass, candidate, body_names + command_names)
    return {'genre_arrangement_score': ebm_arrangement_score(candidate, enable_riffs, enable_bass, enable_drums), 'ebm_machine_pulse_score': _kick_grid_score(body_drums) if enable_drums else 0.7, 'ebm_bass_sequence_score': mean([_bass_downbeat_score(body_bass), _event_repetition_score(body_bass)]), 'ebm_body_groove_score': mean([_kick_grid_score(body_drums), _clap_score(body_drums), _offbeat_hat_score(body_drums)]) if enable_drums else 0.65, 'ebm_command_phrase_score': _short_phrase_score(command_leads), 'ebm_dark_pitch_score': _dark_pitch_score(candidate), 'ebm_controlled_repetition_score': _controlled_repetition_score(candidate)}

def _berlin_school_subscores(candidate: CandidateComposition, enable_riffs: bool, enable_bass: bool, enable_drums: bool) -> Dict[str, float]:
    return {'genre_arrangement_score': berlin_school_arrangement_score(candidate, enable_riffs, enable_bass, enable_drums), 'berlin_longform_evolution_score': clamp(float(candidate.structure_map.get('total_bars', 0)) / 224.0, 0.0, 1.0), 'berlin_sequencer_continuity_score': _sequencer_continuity_score(candidate), 'berlin_atmosphere_score': _berlin_atmosphere_score(candidate), 'berlin_slow_arc_score': _slow_arc_score(candidate), 'berlin_low_drum_score': 1.0 if not candidate.drums else 1.0 - clamp(len(candidate.drums) / max(1, len(candidate.leads + candidate.riffs + candidate.bass)) * 0.45, 0.0, 1.0), 'berlin_mutation_score': _slow_mutation_score(candidate)}

def _normalize_genre(value: str) -> str:
    normalized = value.strip().lower()
    return 'classic_trance' if normalized == 'trance' else normalized

def _section_density_profile(events: Sequence[NoteEvent], candidate: CandidateComposition) -> List[float]:
    profile = []
    for section in _sections(candidate):
        start = float(section.get('start_bar', 0)) * 4.0
        end = float(section.get('end_bar', 0)) * 4.0
        profile.append(round(len([event for event in events if start <= event.start < end]) / max(1.0, end - start), 4))
    return profile

def _sequence_distance(a: Sequence[Any], b: Sequence[Any], scale: float=1.0) -> List[float]:
    length = max(len(a), len(b))
    if length == 0:
        return [0.0]
    values = []
    for index in range(length):
        av = float(a[index]) if index < len(a) else 0.0
        bv = float(b[index]) if index < len(b) else 0.0
        values.append(abs(av - bv) / scale)
    return values

def _classic_breakdown_contrast(candidate: CandidateComposition) -> float:
    breakdowns = [section for section in _sections(candidate) if 'break' in str(section.get('name', '')).lower()]
    peaks = _highest_energy_sections(candidate, count=2)
    if not breakdowns or not peaks:
        return 0.0
    breakdown_density = mean((_section_density(candidate, section) for section in breakdowns))
    peak_density = mean((_section_density(candidate, section) for section in peaks))
    return 1.0 - clamp(breakdown_density / max(0.01, peak_density * 0.75), 0.0, 1.0)

def _event_repetition_score(events: Sequence[NoteEvent]) -> float:
    signatures = []
    for start in range(0, int(max((event.start for event in events), default=0)) + 1, 32):
        block_events = [event for event in events if start <= event.start < start + 32]
        signatures.append(_signature(block_events, 32))
    return _repeat_ratio(signatures)

def _short_phrase_score(events: Sequence[NoteEvent]) -> float:
    if not events:
        return 0.0
    short = sum((1 for event in events if event.duration <= 0.7)) / len(events)
    sparse = 1.0 - clamp(len(events) / 96.0, 0.0, 1.0)
    accents = sum((1 for event in events if event.velocity >= 86)) / len(events)
    return clamp(short * 0.45 + sparse * 0.25 + accents * 0.3, 0.0, 1.0)

def _dark_pitch_score(candidate: CandidateComposition) -> float:
    scale = str(candidate.structure_map.get('scale', ''))
    scale_score = 1.0 if scale in {'natural_minor', 'harmonic_minor', 'minor_pentatonic', 'dorian'} else 0.45
    root = str(candidate.structure_map.get('root_note', 'C')).upper()
    root_score = 1.0 if root in {'C', 'C#', 'D', 'D#', 'F', 'F#', 'G', 'G#', 'A'} else 0.6
    return mean([scale_score, root_score])

def _controlled_repetition_score(candidate: CandidateComposition) -> float:
    signatures = [_signature(_events_in_loop(candidate.leads + candidate.riffs + candidate.bass, block), 32) for block in _loop_blocks(candidate)]
    repeat = _repeat_ratio(signatures)
    unique_ratio = len({signature for signature in signatures if signature}) / max(1, len([signature for signature in signatures if signature]))
    variation = _target_score(unique_ratio, 0.35, 0.3)
    return clamp(repeat * 0.62 + variation * 0.38, 0.0, 1.0)

def _sequencer_continuity_score(candidate: CandidateComposition) -> float:
    events = candidate.riffs + candidate.bass
    signatures = [_signature(_events_in_loop(events, block), 32) for block in _loop_blocks(candidate)]
    repeat = _repeat_ratio(signatures)
    densities = [_section_density(candidate, section) for section in _sections(candidate)]
    smooth = 1.0 - clamp(max((abs(b - a) for a, b in zip(densities, densities[1:])), default=0.0) / max(0.01, mean(densities)), 0.0, 1.0)
    return clamp(repeat * 0.55 + smooth * 0.45, 0.0, 1.0)

def _berlin_atmosphere_score(candidate: CandidateComposition) -> float:
    sections = _sections(candidate)
    if not sections:
        return 0.0
    first, last = (sections[0], sections[-1])
    return mean([1.0 if float(first.get('energy', 0.0)) <= 0.35 else 0.4, 1.0 if float(last.get('energy', 0.0)) <= 0.35 else 0.4, 1.0 if first.get('drum_role') == 'off' else 0.25, 1.0 if last.get('drum_role') == 'off' else 0.25, 1.0 if first.get('riff_role') in {'atmospheric', 'echo', 'muted'} else 0.4, 1.0 if last.get('riff_role') in {'fade', 'echo', 'atmospheric'} else 0.4])

def _slow_arc_score(candidate: CandidateComposition) -> float:
    energies = [float(section.get('energy', 0.0)) for section in _sections(candidate)]
    if len(energies) < 3:
        return 0.0
    peak_index = max(range(len(energies)), key=lambda index: energies[index])
    return mean([1.0 if peak_index >= len(energies) // 2 else 0.3, _ordered_score(energies[:peak_index + 1]), 1.0 if energies[-1] < energies[peak_index] * 0.45 else 0.4])

def _slow_mutation_score(candidate: CandidateComposition) -> float:
    signatures = [_signature(_events_in_loop(candidate.riffs + candidate.bass, block), 32) for block in _loop_blocks(candidate)]
    non_empty = [signature for signature in signatures if signature]
    if len(non_empty) < 2:
        return 0.0
    distances = []
    for a, b in zip(non_empty, non_empty[1:]):
        shared = len(set(a) & set(b))
        total = max(1, len(set(a) | set(b)))
        distances.append(1.0 - shared / total)
    return _target_score(mean(distances), 0.28, 0.24)

def loop_coherence_score(candidate: CandidateComposition) -> float:
    blocks = _loop_blocks(candidate)
    if not blocks:
        return 0.0
    bars_per_loop = int(candidate.structure_map.get('bars_per_loop', 8))
    loop_beats = bars_per_loop * 4
    signatures = []
    phrase_end_hits = 0
    density_scores = []
    for block in blocks:
        start, end = (float(block['start_bar']) * 4.0, float(block['end_bar']) * 4.0)
        events = [event for event in candidate.leads if start <= event.start < end]
        signatures.append(_signature(events, loop_beats))
        density_scores.append(len(events) / max(1.0, loop_beats))
        phrase_end_hits += sum((1 for event in events if any((abs(event.start - start - boundary) < 0.501 for boundary in (8, 16, 24, 31.5)))))
    non_empty = [signature for signature in signatures if signature]
    if not non_empty:
        return 0.0
    repeat_ratio = _repeat_ratio(non_empty)
    variation = _target_score(len(set(non_empty)) / max(1, len(non_empty)), 0.45, 0.35)
    density_stability = 1.0 - clamp(statistics.pstdev(density_scores) / max(0.01, mean(density_scores)), 0.0, 1.0) if len(density_scores) > 1 else 0.5
    cadence = clamp(phrase_end_hits / max(1, len(candidate.leads) * 0.2), 0.0, 1.0)
    return clamp(repeat_ratio * 0.38 + variation * 0.26 + density_stability * 0.16 + cadence * 0.2, 0.0, 1.0)

def section_contrast_score(candidate: CandidateComposition, enable_riffs: bool, enable_bass: bool, enable_drums: bool) -> float:
    sections = _sections(candidate)
    if len(sections) < 2:
        return 0.0
    density_by_section = {section['name']: _section_density(candidate, section) for section in sections}
    densities = [density_by_section[section['name']] for section in sections]
    energies = [float(section.get('energy', 0.0)) for section in sections]
    first_density = densities[0]
    last_density = densities[-1]
    peak_density = max(densities)
    low_energy_density = mean((density for density, section in zip(densities, sections) if float(section.get('energy', 0.0)) <= 0.4))
    high_energy_density = mean((density for density, section in zip(densities, sections) if float(section.get('energy', 0.0)) >= 0.7))
    if high_energy_density <= 0.0:
        high_energy_density = peak_density
    range_score = clamp((peak_density - min(densities)) / max(0.01, peak_density), 0.0, 1.0)
    energy_rank_score = _rank_correlation_score(energies, densities)
    sparse_edges = 1.0 - clamp((first_density + last_density) / max(0.01, peak_density * 1.6), 0.0, 1.0)
    low_high_contrast = 1.0 - clamp(low_energy_density / max(0.01, high_energy_density), 0.0, 1.0)
    return clamp(range_score * 0.2 + energy_rank_score * 0.34 + sparse_edges * 0.2 + low_high_contrast * 0.26, 0.0, 1.0)

def genre_arrangement_score(candidate: CandidateComposition, genre: str, enable_riffs: bool, enable_bass: bool, enable_drums: bool) -> float:
    if genre == 'ebm':
        return ebm_arrangement_score(candidate, enable_riffs, enable_bass, enable_drums)
    if genre == 'berlin_school':
        return berlin_school_arrangement_score(candidate, enable_riffs, enable_bass, enable_drums)
    return classic_trance_arrangement_score(candidate, enable_riffs, enable_bass, enable_drums)

def classic_trance_arrangement_score(candidate: CandidateComposition, enable_riffs: bool, enable_bass: bool, enable_drums: bool) -> float:
    expected = ['Intro', 'Early Groove / Buildup', 'Main Buildup', 'Breakdown', 'Pre-Drop Build', 'Climax / Drop', 'Second Breakdown', 'Final Climax', 'Outro']
    names = [section.get('name') for section in _sections(candidate)]
    order_score = sum((1 for a, b in zip(names, expected) if a == b)) / len(expected)
    loop_count_score = _target_score(float(candidate.structure_map.get('loop_count', 0)), 21.0, 1.0)
    bars_per_loop_score = 1.0 if int(candidate.structure_map.get('bars_per_loop', 0)) == 8 else 0.0
    active_layers = candidate.structure_map.get('active_layers', {})
    choreography = 0.0
    if active_layers:
        intro = active_layers.get('Intro', {})
        breakdown = active_layers.get('Breakdown', {})
        drop = active_layers.get('Climax / Drop', {})
        outro = active_layers.get('Outro', {})
        choreography = mean([1.0 if intro.get('leads') and (not intro.get('riffs')) else 0.5, 1.0 if breakdown.get('leads') and (not breakdown.get('bass')) else 0.5, 1.0 if drop.get('leads') and (drop.get('drums') or not enable_drums) else 0.0, 1.0 if not outro.get('riffs', False) or not enable_riffs else 0.4])
    return clamp(order_score * 0.34 + loop_count_score * 0.24 + bars_per_loop_score * 0.18 + choreography * 0.24, 0.0, 1.0)

def trance_arrangement_score(candidate: CandidateComposition, enable_riffs: bool, enable_bass: bool, enable_drums: bool) -> float:
    return classic_trance_arrangement_score(candidate, enable_riffs, enable_bass, enable_drums)

def ebm_arrangement_score(candidate: CandidateComposition, enable_riffs: bool, enable_bass: bool, enable_drums: bool) -> float:
    sections = _sections(candidate)
    if len(sections) < 5:
        return 0.0
    names = [str(section.get('name', '')).lower() for section in sections]
    body_names = [str(section.get('name')) for section in sections if 'body' in str(section.get('name', '')).lower() or 'chorus' in str(section.get('name', '')).lower()]
    verse_names = [str(section.get('name')) for section in sections if 'verse' in str(section.get('name', '')).lower() or 'command' in str(section.get('name', '')).lower()]
    bridge_names = [str(section.get('name')) for section in sections if 'bridge' in str(section.get('name', '')).lower() or 'breakdown' in str(section.get('name', '')).lower()]
    body_density = mean((_section_density(candidate, _section(candidate, name)) for name in body_names))
    verse_density = mean((_section_density(candidate, _section(candidate, name)) for name in verse_names))
    bridge_density = mean((_section_density(candidate, _section(candidate, name)) for name in bridge_names))
    structure = mean([1.0 if 'intro' in names[0] or 'machine' in names[0] else 0.0, clamp(len(verse_names) / 2.0, 0.0, 1.0), clamp(len(body_names) / 2.0, 0.0, 1.0), 1.0 if bridge_names else 0.0, 1.0 if 'final' in names[-2] or 'outro' in names[-1] else 0.0])
    bass_pulse = _bass_downbeat_score(_events_in_named_sections(candidate.bass, candidate, verse_names + body_names)) if enable_bass else 1.0
    drum_body = mean([_kick_grid_score(_events_in_named_sections(candidate.drums, candidate, body_names)), _clap_score(_events_in_named_sections(candidate.drums, candidate, body_names)), _offbeat_hat_score(_events_in_named_sections(candidate.drums, candidate, body_names))]) if enable_drums else 0.6
    contrast = clamp((body_density + verse_density * 0.5 - bridge_density * 0.65) / max(0.01, body_density + verse_density), 0.0, 1.0)
    repetition = _repeat_ratio([_signature(_events_in_loop(candidate.bass + candidate.riffs, block), 32) for block in _loop_blocks(candidate)])
    return clamp(structure * 0.24 + bass_pulse * 0.24 + drum_body * 0.22 + contrast * 0.14 + repetition * 0.16, 0.0, 1.0)

def berlin_school_arrangement_score(candidate: CandidateComposition, enable_riffs: bool, enable_bass: bool, enable_drums: bool) -> float:
    sections = _sections(candidate)
    if len(sections) < 5:
        return 0.0
    energies = [float(section.get('energy', 0.0)) for section in sections]
    total_bars = float(candidate.structure_map.get('total_bars', 0))
    peak_index = max(range(len(energies)), key=lambda index: energies[index])
    first = sections[0]
    last = sections[-1]
    long_form = clamp(total_bars / 192.0, 0.0, 1.0)
    arc = mean([1.0 if peak_index >= len(sections) // 2 else 0.35, _ordered_score(energies[:peak_index + 1]), 1.0 if energies[-1] <= energies[peak_index] * 0.35 else 0.35])
    no_drums = 1.0 if not candidate.drums else 1.0 - clamp(len(candidate.drums) / max(1.0, len(candidate.leads + candidate.riffs + candidate.bass) * 0.2), 0.0, 1.0)
    first_last_atmosphere = mean([1.0 if float(first.get('energy', 0.0)) <= 0.3 and first.get('drum_role') == 'off' else 0.25, 1.0 if float(last.get('energy', 0.0)) <= 0.3 and last.get('drum_role') == 'off' else 0.25, 1.0 if first.get('riff_role') in {'atmospheric', 'echo', 'muted'} else 0.4, 1.0 if last.get('riff_role') in {'fade', 'echo', 'atmospheric'} else 0.4])
    sequencer_events = candidate.riffs + candidate.bass
    sequencer_repetition = _repeat_ratio([_signature(_events_in_loop(sequencer_events, block), 32) for block in _loop_blocks(candidate)])
    density_values = [_section_density(candidate, section) for section in sections]
    continuity = 1.0 - clamp(statistics.pstdev(density_values) / max(0.01, mean(density_values)) if len(density_values) > 1 else 0.0, 0.0, 1.0)
    return clamp(long_form * 0.18 + arc * 0.24 + no_drums * 0.18 + first_last_atmosphere * 0.16 + sequencer_repetition * 0.16 + continuity * 0.08, 0.0, 1.0)

def lead_hook_strength_score(candidate: CandidateComposition) -> float:
    if not candidate.leads:
        return 0.0
    hook_notes = candidate.structure_map.get('hook_notes', [])
    hook_classes = {int(note) % 12 for note in hook_notes}
    if not hook_classes:
        return 0.0
    sections = _sections(candidate)
    full_sections = _sections_with_roles(candidate, 'lead_role', {'full_hook', 'final_hook', 'compressed'})
    if not full_sections:
        full_sections = _highest_energy_sections(candidate, count=2)
    drop_name = str(full_sections[0].get('name')) if full_sections else str(sections[-1].get('name'))
    final_name = str(full_sections[-1].get('name')) if full_sections else drop_name
    intro_name = str(sections[0].get('name'))
    main_name = _section_before(candidate, drop_name).get('name', drop_name)
    drop_events = _events_in_section(candidate.leads, candidate, drop_name)
    final_events = _events_in_section(candidate.leads, candidate, final_name)
    intro_events = _events_in_section(candidate.leads, candidate, intro_name)
    main_events = _events_in_section(candidate.leads, candidate, str(main_name))
    hook_drop = _hook_ratio(drop_events, hook_classes)
    hook_final = _hook_ratio(final_events, hook_classes)
    gradual_intro = 1.0 - clamp(len(intro_events) / max(1, len(drop_events) * 0.25), 0.0, 1.0)
    buildup_presence = clamp(_hook_ratio(main_events, hook_classes) * 1.4, 0.0, 1.0)
    repetition = _repeat_ratio([_signature(_events_in_loop(candidate.leads, block), 32) for block in _loop_blocks(candidate) if block.get('section_name') in {drop_name, final_name}])
    return clamp(hook_drop * 0.28 + hook_final * 0.24 + gradual_intro * 0.18 + buildup_presence * 0.12 + repetition * 0.18, 0.0, 1.0)

def arrival_energy_score(candidate: CandidateComposition, enable_riffs: bool, enable_bass: bool, enable_drums: bool) -> float:
    arrival_section = _highest_energy_sections(candidate, count=1)[0]
    before_section = _section_before(candidate, str(arrival_section.get('name')))
    before_density = _section_density(candidate, before_section)
    arrival_density = _section_density(candidate, arrival_section)
    density_jump = clamp((arrival_density - before_density * 0.72) / max(0.01, arrival_density), 0.0, 1.0)
    arrival_name = str(arrival_section.get('name'))
    layers_at_arrival = [candidate.leads]
    if enable_riffs:
        layers_at_arrival.append(candidate.riffs)
    if enable_bass:
        layers_at_arrival.append(candidate.bass)
    if enable_drums:
        layers_at_arrival.append(candidate.drums)
    layer_presence = mean([1.0 if _events_in_section(layer, candidate, arrival_name) else 0.0 for layer in layers_at_arrival])
    velocity = _velocity_lift_between_sections(candidate, before_section, arrival_section)
    return clamp(density_jump * 0.35 + layer_presence * 0.4 + velocity * 0.25, 0.0, 1.0)

def drop_energy_score(candidate: CandidateComposition, enable_riffs: bool, enable_bass: bool, enable_drums: bool) -> float:
    return arrival_energy_score(candidate, enable_riffs, enable_bass, enable_drums)

def drum_groove_score(candidate: CandidateComposition, enable_drums: bool) -> float:
    if not enable_drums:
        return 1.0
    drums = candidate.drums
    if not drums:
        return 0.0
    high_sections = [str(section.get('name')) for section in _highest_energy_sections(candidate, count=2)]
    low_sections = [str(section.get('name')) for section in _sections(candidate) if float(section.get('energy', 0.0)) <= 0.45 or section.get('drum_role') in {'reduced', 'sparse', 'outro'}]
    high_events = _events_in_named_sections(drums, candidate, high_sections)
    low_events = _events_in_named_sections(drums, candidate, low_sections)
    build_sections = [str(section.get('name')) for section in _sections(candidate) if section.get('drum_role') in {'snare_roll', 'buildup'}]
    build_events = _events_in_named_sections(drums, candidate, build_sections)
    kick_score = _kick_grid_score(high_events)
    hat_score = _offbeat_hat_score(high_events)
    clap_score = _clap_score(high_events)
    roll_score = clamp(sum((1 for event in build_events if event.pitch == SNARE)) / 32.0, 0.0, 1.0)
    reduction = 1.0 - clamp(len(low_events) / max(1, len(high_events) * 0.7), 0.0, 1.0)
    return clamp(kick_score * 0.28 + hat_score * 0.2 + clap_score * 0.18 + roll_score * 0.18 + reduction * 0.16, 0.0, 1.0)

def transition_quality_score(candidate: CandidateComposition, enable_drums: bool) -> float:
    transition_bars = candidate.structure_map.get('transition_bars', [])
    if not transition_bars:
        return 0.0
    transition_beats = [bar * 4.0 for bar in transition_bars]
    crashes = 0
    fills = 0
    for beat in transition_beats:
        if enable_drums and any((event.pitch == CRASH and abs(event.start - beat) < 0.1 for event in candidate.drums)):
            crashes += 1
        if any((beat - 2.1 <= event.start < beat for event in candidate.leads + candidate.drums)):
            fills += 1
    crash_score = crashes / len(transition_beats) if enable_drums else 1.0
    fill_score = fills / len(transition_beats)
    arrival_section = _highest_energy_sections(candidate, count=1)[0]
    before_section = _section_before(candidate, str(arrival_section.get('name')))
    predrop_rise = _velocity_lift_between_sections(candidate, before_section, arrival_section)
    outro = _sections(candidate)[-1]
    outro_removal = 1.0 - clamp(_section_density(candidate, outro) / max(0.01, _section_density(candidate, arrival_section)), 0.0, 1.0)
    return clamp(crash_score * 0.24 + fill_score * 0.3 + predrop_rise * 0.24 + outro_removal * 0.22, 0.0, 1.0)

def duration_score(candidate: CandidateComposition, min_duration_seconds: float) -> float:
    if min_duration_seconds <= 0:
        return 1.0
    ratio = candidate.duration_seconds / min_duration_seconds
    if ratio < 1.0:
        return clamp(ratio * ratio, 0.0, 1.0)
    return clamp(1.0 - max(0.0, ratio - 1.9) * 0.15, 0.75, 1.0)

def melodic_coherence_score(candidate: CandidateComposition) -> float:
    melodic = candidate.leads + candidate.riffs + candidate.bass
    if not melodic:
        return 0.0
    scale_fit = _scale_membership_score(melodic, _scale_pitch_classes(candidate))
    intervals = [b.pitch - a.pitch for a, b in zip(candidate.leads, candidate.leads[1:])]
    if not intervals:
        return scale_fit * 0.7
    singable = sum((1 for interval in intervals if abs(interval) <= 12)) / len(intervals)
    leap_control = 1.0 - clamp(sum((1 for interval in intervals if abs(interval) > 14)) / len(intervals), 0.0, 1.0)
    return clamp(scale_fit * 0.48 + singable * 0.28 + leap_control * 0.24, 0.0, 1.0)

def layer_alignment_score(candidate: CandidateComposition, enable_riffs: bool, enable_bass: bool) -> float:
    scores = []
    phrases = candidate.structure_map.get('phrases', [])
    if enable_riffs:
        scores.append(_phrase_alignment(candidate.riffs, phrases))
        scores.append(1.0 - _duplication_ratio(candidate.leads, candidate.riffs))
        scores.append(_register_separation(candidate.leads, candidate.riffs, 8.0))
    if enable_bass:
        scores.append(_phrase_alignment(candidate.bass, phrases))
        scores.append(_bass_downbeat_score(candidate.bass))
        scores.append(_register_separation(candidate.leads, candidate.bass, 22.0))
    return clamp(mean(scores), 0.0, 1.0) if scores else 1.0

def penalty_scores(candidate: CandidateComposition, min_duration_seconds: float, enable_riffs: bool, enable_bass: bool, enable_drums: bool) -> Dict[str, float]:
    melodic = candidate.leads + candidate.riffs + candidate.bass
    scale_penalty = 0.0
    if melodic:
        scale_penalty = 1.0 - _scale_membership_score(melodic, _scale_pitch_classes(candidate))
    no_drums = 1.0 if enable_drums and (not candidate.drums) else 0.0
    no_bass = 1.0 if enable_bass and (not candidate.bass) else 0.0
    no_riffs = 1.0 if enable_riffs and (not candidate.riffs) else 0.0
    return {'below_min_duration': clamp(1.0 - candidate.duration_seconds / max(1.0, min_duration_seconds), 0.0, 1.0), 'out_of_scale_ratio_too_high': scale_penalty, 'no_phrase_structure': 0.0 if candidate.structure_map.get('phrases') else 1.0, 'missing_enabled_layers': clamp((no_drums + no_bass + no_riffs) / 3.0, 0.0, 1.0)}

def _sections(candidate: CandidateComposition) -> List[Dict[str, object]]:
    return list(candidate.structure_map.get('sections', []))

def _genre(candidate: CandidateComposition) -> str:
    genre = str(candidate.structure_map.get('genre') or candidate.structure_map.get('style') or 'classic_trance')
    return 'classic_trance' if genre == 'trance' else genre

def _section(candidate: CandidateComposition, name: str) -> Dict[str, object]:
    for section in _sections(candidate):
        if section.get('name') == name:
            return section
    return {'name': name, 'start_bar': 0, 'end_bar': 0, 'length_bars': 0}

def _section_before(candidate: CandidateComposition, name: str) -> Dict[str, object]:
    sections = _sections(candidate)
    for index, section in enumerate(sections):
        if section.get('name') == name:
            return sections[max(0, index - 1)]
    return sections[0] if sections else {'name': name, 'start_bar': 0, 'end_bar': 0, 'length_bars': 0}

def _sections_with_roles(candidate: CandidateComposition, role_key: str, roles: set[str]) -> List[Dict[str, object]]:
    return [section for section in _sections(candidate) if str(section.get(role_key, '')) in roles]

def _highest_energy_sections(candidate: CandidateComposition, count: int=1) -> List[Dict[str, object]]:
    sections = _sections(candidate)
    if not sections:
        return [{'name': '', 'start_bar': 0, 'end_bar': 0, 'length_bars': 0, 'energy': 0.0}]
    return sorted(sections, key=lambda section: float(section.get('energy', 0.0)), reverse=True)[:count]

def _loop_blocks(candidate: CandidateComposition) -> List[Dict[str, object]]:
    return list(candidate.structure_map.get('loop_blocks', []))

def _events_in_loop(events: Sequence[NoteEvent], block: Dict[str, object]) -> List[NoteEvent]:
    start = float(block['start_bar']) * 4.0
    end = float(block['end_bar']) * 4.0
    return [event for event in events if start <= event.start < end]

def _events_in_section(events: Sequence[NoteEvent], candidate: CandidateComposition, section_name: str) -> List[NoteEvent]:
    section = _section(candidate, section_name)
    start = float(section.get('start_bar', 0)) * 4.0
    end = float(section.get('end_bar', 0)) * 4.0
    return [event for event in events if start <= event.start < end]

def _events_in_named_sections(events: Sequence[NoteEvent], candidate: CandidateComposition, section_names: Sequence[str]) -> List[NoteEvent]:
    selected: List[NoteEvent] = []
    seen = set()
    for name in section_names:
        if name in seen:
            continue
        seen.add(name)
        selected.extend(_events_in_section(events, candidate, name))
    return selected

def _section_density(candidate: CandidateComposition, section: Dict[str, object]) -> float:
    start = float(section.get('start_bar', 0)) * 4.0
    end = float(section.get('end_bar', 0)) * 4.0
    if end <= start:
        return 0.0
    events = [event for event in _all_events(candidate) if start <= event.start < end]
    return len(events) / (end - start)

def _all_events(candidate: CandidateComposition) -> List[NoteEvent]:
    return candidate.leads + candidate.riffs + candidate.bass + candidate.drums

def _signature(events: Sequence[NoteEvent], loop_beats: int) -> tuple[tuple[float, int], ...]:
    ordered = sorted(events, key=lambda event: (event.start, event.pitch))
    if not ordered:
        return tuple()
    base = ordered[0].pitch
    return tuple(((round(event.start % loop_beats * 2) / 2, int(round((event.pitch - base) / 2))) for event in ordered[:24]))

def _repeat_ratio(signatures: Sequence[tuple]) -> float:
    signatures = [signature for signature in signatures if signature]
    if not signatures:
        return 0.0
    counts: Dict[tuple, int] = {}
    for signature in signatures:
        counts[signature] = counts.get(signature, 0) + 1
    repeated = sum((count for count in counts.values() if count > 1))
    return repeated / len(signatures)

def _ordered_score(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    wins = sum((1 for a, b in zip(values, values[1:]) if b >= a * 0.88))
    return wins / (len(values) - 1)

def _rank_correlation_score(expected: Sequence[float], observed: Sequence[float]) -> float:
    if len(expected) != len(observed) or len(expected) < 2:
        return 0.0
    wins = 0
    total = 0
    for i, expected_i in enumerate(expected):
        for j in range(i + 1, len(expected)):
            total += 1
            expected_order = expected[j] >= expected_i
            observed_order = observed[j] >= observed[i]
            if expected_order == observed_order:
                wins += 1
    return wins / total if total else 0.0

def _target_score(value: float, target: float, tolerance: float) -> float:
    if tolerance <= 0:
        return 1.0 if value == target else 0.0
    return clamp(1.0 - abs(value - target) / tolerance, 0.0, 1.0)

def _hook_ratio(events: Sequence[NoteEvent], hook_classes: set[int]) -> float:
    if not events:
        return 0.0
    return sum((1 for event in events if event.pitch % 12 in hook_classes)) / len(events)

def _velocity_lift(candidate: CandidateComposition, before: str, after: str) -> float:
    before_events = _events_in_section(_all_events(candidate), candidate, before)
    after_events = _events_in_section(_all_events(candidate), candidate, after)
    return _velocity_lift_for_events(before_events, after_events)

def _velocity_lift_between_sections(candidate: CandidateComposition, before: Dict[str, object], after: Dict[str, object]) -> float:
    before_events = _events_in_section(_all_events(candidate), candidate, str(before.get('name', '')))
    after_events = _events_in_section(_all_events(candidate), candidate, str(after.get('name', '')))
    return _velocity_lift_for_events(before_events, after_events)

def _velocity_lift_for_events(before_events: Sequence[NoteEvent], after_events: Sequence[NoteEvent]) -> float:
    if not before_events or not after_events:
        return 0.0
    before_v = mean((event.velocity for event in before_events))
    after_v = mean((event.velocity for event in after_events))
    return clamp((after_v - before_v + 8.0) / 24.0, 0.0, 1.0)

def _kick_grid_score(events: Sequence[NoteEvent]) -> float:
    kicks = [event for event in events if event.pitch == KICK]
    if not kicks:
        return 0.0
    downbeats = sum((1 for event in kicks if abs(event.start % 1.0) < 0.05))
    return clamp(downbeats / max(1, len(kicks)), 0.0, 1.0)

def _offbeat_hat_score(events: Sequence[NoteEvent]) -> float:
    hats = [event for event in events if event.pitch in {OPEN_HAT, CLOSED_HAT}]
    if not hats:
        return 0.0
    offbeats = sum((1 for event in hats if abs(event.start % 1.0 - 0.5) < 0.06 or abs(event.start % 1.0 - 0.25) < 0.06 or abs(event.start % 1.0 - 0.75) < 0.06))
    return clamp(offbeats / len(hats), 0.0, 1.0)

def _clap_score(events: Sequence[NoteEvent]) -> float:
    claps = [event for event in events if event.pitch == CLAP]
    if not claps:
        return 0.0
    good = sum((1 for event in claps if abs(event.start % 4.0 - 1.0) < 0.06 or abs(event.start % 4.0 - 3.0) < 0.06))
    return clamp(good / len(claps), 0.0, 1.0)

def _scale_pitch_classes(candidate: CandidateComposition) -> set[int]:
    scale = str(candidate.structure_map.get('scale', 'dorian'))
    root = str(candidate.structure_map.get('root_note', 'C'))
    root_pc = root_pitch_class(root)
    return {(root_pc + interval) % 12 for interval in scale_pattern(scale)}

def _scale_membership_score(events: Sequence[NoteEvent], allowed: set[int]) -> float:
    if not events:
        return 0.0
    return sum((1 for event in events if event.pitch % 12 in allowed)) / len(events)

def _phrase_alignment(events: Sequence[NoteEvent], phrases: Sequence[Dict[str, object]]) -> float:
    if not events or not phrases:
        return 0.0
    aligned = 0
    for event in events:
        if any((float(phrase['start']) <= event.start < float(phrase['end']) for phrase in phrases)):
            aligned += 1
    return aligned / len(events)

def _duplication_ratio(a: Sequence[NoteEvent], b: Sequence[NoteEvent]) -> float:
    if not a or not b:
        return 0.0
    a_points = {(round(event.start, 2), event.pitch) for event in a}
    duplicates = sum((1 for event in b if (round(event.start, 2), event.pitch) in a_points))
    return duplicates / len(b)

def _register_separation(a: Sequence[NoteEvent], b: Sequence[NoteEvent], target: float) -> float:
    if not a or not b:
        return 0.0
    center_a = mean((event.pitch for event in a))
    center_b = mean((event.pitch for event in b))
    return clamp(abs(center_a - center_b) / target, 0.0, 1.0)

def _bass_downbeat_score(events: Sequence[NoteEvent]) -> float:
    if not events:
        return 0.0
    return sum((1 for event in events if abs(event.start % 1.0) < 0.05 or abs(event.start % 1.0 - 0.5) < 0.05)) / len(events)
