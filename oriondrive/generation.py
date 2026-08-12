from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from .arrangement import arrangement_from_ori_project
from .config import DEFAULT_MIN_DURATION_SECONDS
from .evolutionary_selector import EvolutionarySelector, SelectionConfig, SelectionResult
from .grooves import AUTO_GROOVE
from .harmonic_seeds import AUTO_SEED
from .midi_writer import MidiWriteResult, write_midi
from .ori_format import OriProject

@dataclass(frozen=True)
class GeneratedMidi:
    selection: SelectionResult
    midi: MidiWriteResult

def selection_config_from_project(project: OriProject, allow_small_population: bool=False, min_duration_seconds: float=DEFAULT_MIN_DURATION_SECONDS) -> SelectionConfig:
    parameters = project.parameters
    ca = project.ca
    lsystem = project.lsystem
    ga = project.ga
    musical = project.musical
    harmony = project.harmony
    variation = project.variation
    explore_ca = variation.explore_ca if variation else False
    explore_rules = variation.explore_rule_sets if variation else False
    explore_phrase = variation.explore_phrase_length if variation else False
    explore_octaves = variation.explore_octave_range if variation else False
    tempo_drift = variation.tempo_drift_bpm if variation else 0
    return SelectionConfig(seed=parameters.seed if parameters.seed is not None else 42, candidates=ga.candidates if ga else parameters.candidates, generations=ga.generations if ga else parameters.generations, min_duration_seconds=min_duration_seconds, target_duration_seconds=parameters.generation_length_seconds, enable_riffs=parameters.enable_riffs, enable_bass=parameters.enable_bass, enable_drums=parameters.enable_drums, enable_pads=parameters.enable_pads, harmonic_seed=None if harmony is None or harmony.harmonic_seed == AUTO_SEED else harmony.harmonic_seed, seed_pool=tuple(harmony.seed_pool) if harmony else None, follow_seed_mode=harmony.follow_seed_mode if harmony else True, protect_species=harmony.protect_species if harmony else True, seed_mutation_rate=harmony.seed_mutation_rate if harmony else 0.06, cross_seed_crossover_rate=harmony.cross_seed_crossover_rate if harmony else 0.1, fixed_harmonic_rhythm_bars=harmony.harmonic_rhythm_bars if harmony else None, fixed_pedal_strength=harmony.pedal_strength if harmony else None, fixed_voicing_openness=harmony.voicing_openness if harmony else None, fixed_suspension_amount=harmony.suspension_amount if harmony else None, pad_density=harmony.pad_density if harmony else None, pad_air_amount=harmony.pad_air_amount if harmony else None, pad_voice_count=harmony.pad_voice_count if harmony else None, allow_small_population=allow_small_population, fixed_tempo=None if tempo_drift > 0 else parameters.bpm, tempo_center=parameters.bpm, tempo_drift=tempo_drift, fixed_scale=parameters.scale, fixed_root_note=parameters.key, fixed_ca_rule=None if explore_ca else ca.rule if ca else None, fixed_ca_width=None if explore_ca else ca.width if ca else None, fixed_ca_steps=None if explore_ca else ca.steps if ca else None, fixed_ca_seed_density=None if explore_ca else ca.seed_density if ca else None, fixed_ca_wrap_edges=ca.wrap_edges if ca else None, fixed_lsystem_rules=None if explore_rules else lsystem.rule_set if lsystem else None, fixed_lsystem_iterations=lsystem.iterations if lsystem else None, fixed_phrase_length=None if explore_phrase else lsystem.phrase_length if lsystem else None, fixed_octave_range=None if explore_octaves else (lsystem.octave_low, lsystem.octave_high) if lsystem else None, groove=None if variation is None or variation.groove == AUTO_GROOVE else variation.groove, groove_pool=tuple(variation.groove_pool) if variation else None, groove_mutation_rate=variation.groove_mutation_rate if variation else 0.1, genre=project.genre, arrangement_template=project.genre, arrangement=arrangement_from_ori_project(project), drum_intensity=musical.drum_intensity if musical else 0.78, drum_steadiness=variation.drum_steadiness if variation else 'steady', drop_intensity=musical.drop_density if musical else 0.9, breakdown_sparsity=musical.breakdown_sparsity if musical else 0.72, rhythm_density=musical.rhythm_density if musical else None, accompaniment_density=musical.accompaniment_density if musical else None, loop_density=musical.loop_density if musical else None, lead_hook_shape=musical.lead_hook_shape if musical else None, lead_hook_repetition=musical.lead_hook_repetition if musical else None, lead_variation_amount=musical.lead_variation_amount if musical else None, riff_density=musical.riff_density if musical else None, riff_rhythmic_variation=musical.riff_rhythmic_variation if musical else None, riff_motif_mutation_amount=musical.riff_motif_mutation_amount if musical else None, bass_density=musical.bass_density if musical else None, bass_rhythmic_activity=musical.bass_rhythmic_activity if musical else None, bass_harmonic_strictness=musical.bass_harmonic_strictness if musical else None, drum_fill_probability=musical.drum_fill_probability if musical else None, snare_roll_intensity=musical.snare_roll_intensity if musical else None, transition_fill_amount=musical.transition_fill_amount if musical else None, elite_fraction=ga.elite_fraction if ga else 0.2, tournament_size=ga.tournament_size if ga else 3, mutation_rate_min=ga.mutation_rate_min if ga else 0.04, mutation_rate_max=ga.mutation_rate_max if ga else 0.16, mutation_strength=ga.mutation_strength if ga else 0.08, crossover_rate=ga.crossover_rate if ga else 0.75, random_immigrant_fraction=ga.random_immigrant_fraction if ga else 0.1, diversity_weight=ga.diversity_weight if ga else 0.2, max_generations_without_improvement=ga.max_generations_without_improvement if ga else None)

def generate_project(project: OriProject, allow_small_population: bool=False, min_duration_seconds: float=DEFAULT_MIN_DURATION_SECONDS) -> SelectionResult:
    return EvolutionarySelector(selection_config_from_project(project, allow_small_population=allow_small_population, min_duration_seconds=min_duration_seconds)).run()

def generate_and_write_project(project: OriProject, output_path: str | Path, allow_small_population: bool=False, min_duration_seconds: float=DEFAULT_MIN_DURATION_SECONDS) -> GeneratedMidi:
    selection = generate_project(project, allow_small_population=allow_small_population, min_duration_seconds=min_duration_seconds)
    midi = write_midi(selection.winner.composition, output_path, min_duration_seconds=min_duration_seconds)
    return GeneratedMidi(selection=selection, midi=midi)

def write_seed_variations(selection: SelectionResult, directory: str | Path, min_duration_seconds: float | None=None) -> list[MidiWriteResult]:
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    results: list[MidiWriteResult] = []
    for rank, candidate in enumerate(selection.variations(), start=1):
        path = target / f'{rank:02d}_{candidate.harmonic_seed}.mid'
        results.append(write_midi(candidate.composition, path, min_duration_seconds=min_duration_seconds))
    return results

def default_midi_filename(genre: str, now: datetime | None=None) -> str:
    timestamp = (now or datetime.now()).strftime('%Y%m%d_%H%M%S')
    return f'oriondrive_{genre}_{timestamp}.mid'

def default_variations_dir(output_path: str | Path) -> Path:
    path = Path(output_path)
    return path.parent / f'{path.stem}_seed_variations'
