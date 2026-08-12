from __future__ import annotations
import argparse
from pathlib import Path
from typing import Optional
from .arrangement import arrangement_from_ori_project, arrangement_from_template
from .config import DEFAULT_CANDIDATE_COUNT, DEFAULT_GENERATIONS, DEFAULT_MIN_DURATION_SECONDS, DEFAULT_OUTPUT, VALID_GENRES, available_scales
from .evolutionary_selector import EvolutionarySelector, SelectionConfig, SelectionResult
from .generation import default_variations_dir, write_seed_variations
from .genetic_algorithm import normalize_genre
from .grooves import AUTO_GROOVE, VALID_GROOVE_NAMES, groove_summary_rows, validate_groove_pool
from .harmonic_seeds import AUTO_SEED, VALID_SEED_NAMES, seed_summary_rows, validate_seed_pool
from .midi_writer import write_midi
from .ori_format import OriProject, load_ori
from .reports import default_candidate_output_dir, default_fitness_report_path, write_fitness_report

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='oriondrive', description='Generate deterministic, structured Oriondrive MIDI with a genre-aware genetic selection pipeline.')
    parser.add_argument('--ori', default=None, help='Load song structure and generation parameters from a .ori JSON project.')
    parser.add_argument('--seed', type=int, default=None, help='Deterministic random seed.')
    parser.add_argument('--genre', choices=VALID_GENRES, default=None, help='Composition genre.')
    parser.add_argument('--style', choices=('trance', 'classic_trance', 'ebm', 'berlin_school'), default=None, help="Legacy alias for --genre. 'trance' maps to classic_trance.")
    parser.add_argument('--bars-per-loop', type=int, default=8, help='Bars in each loop block. Default: 8.')
    parser.add_argument('--arrangement-template', choices=VALID_GENRES, default=None, help='Built-in song arrangement template.')
    parser.add_argument('--candidates', type=int, default=None, help='Number of complete candidates.')
    parser.add_argument('--generations', type=int, default=None, help='Number of genetic generations.')
    parser.add_argument('--allow-small-population', action='store_true', help='Allow fewer than 20 candidates for debugging.')
    parser.add_argument('--save-candidates', action='store_true', help='Save all final candidate MIDI files.')
    parser.add_argument('--fitness-report', action='store_true', help='Write a JSON fitness report.')
    parser.add_argument('--tempo', '--bpm', dest='tempo', type=int, default=None, help='Fix the tempo in BPM instead of evolving it.')
    parser.add_argument('--key', default=None, help='Fix the root note.')
    parser.add_argument('--output', default=DEFAULT_OUTPUT, help='Output MIDI file path for the winning candidate.')
    seeds = parser.add_argument_group('harmonic seeds')
    seeds.add_argument('--harmonic-seed', choices=VALID_SEED_NAMES, default=None, help='Spend the whole population inside one harmonic seed instead of stratifying across the pool.')
    seeds.add_argument('--seed-pool', default=None, help='Comma-separated harmonic seeds to explore. Defaults to all eight.')
    seeds.add_argument('--export-all-seeds', action='store_true', help='Write the best arrangement of every explored seed, not only the overall winner.')
    seeds.add_argument('--list-seeds', action='store_true', help='Print the sixteen harmonic seeds with their chord fields and exit.')
    seeds.add_argument('--groove', choices=VALID_GROOVE_NAMES, default=None, help='Pin the rhythmic identity of every candidate.')
    seeds.add_argument('--groove-pool', default=None, help='Comma-separated grooves to explore. Defaults to all eight.')
    seeds.add_argument('--groove-mutation-rate', type=float, default=None, help='Chance a genome drifts to a different groove.')
    seeds.add_argument('--list-grooves', action='store_true', help='Print the eight groove profiles and exit.')
    seeds.add_argument('--explore-rule-sets', dest='explore_rule_sets', action='store_true', default=None, help='Let the search pick L-system rule sets (default).')
    seeds.add_argument('--lock-rule-sets', dest='explore_rule_sets', action='store_false', help='Pin the project L-system rule set.')
    seeds.add_argument('--explore-ca', dest='explore_ca', action='store_true', default=None, help='Let the search pick cellular automaton settings (default).')
    seeds.add_argument('--lock-ca', dest='explore_ca', action='store_false', help='Pin the project cellular automaton settings.')
    seeds.add_argument('--explore-phrase-length', dest='explore_phrase_length', action='store_true', default=None, help='Let the search pick phrase lengths (default).')
    seeds.add_argument('--lock-phrase-length', dest='explore_phrase_length', action='store_false', help='Pin the project phrase length.')
    seeds.add_argument('--tempo-drift', type=int, default=None, help='BPM either side of the project tempo the search may use. 0 pins the tempo.')
    seeds.add_argument('--follow-seed-mode', dest='follow_seed_mode', action='store_true', default=None, help='Let each seed impose its own mode (default).')
    seeds.add_argument('--no-follow-seed-mode', dest='follow_seed_mode', action='store_false', help='Keep the project scale for every seed.')
    seeds.add_argument('--protect-species', dest='protect_species', action='store_true', default=None, help='Reserve an elite slot per seed (default).')
    seeds.add_argument('--no-protect-species', dest='protect_species', action='store_false', help='Use plain global elitism.')
    seeds.add_argument('--seed-mutation-rate', type=float, default=None, help='Chance a genome drifts to a different harmonic seed.')
    seeds.add_argument('--cross-seed-crossover-rate', type=float, default=None, help='Chance crossover mixes two different seeds.')
    seeds.add_argument('--harmonic-rhythm-bars', type=int, choices=(1, 2, 4), default=None, help="Fix bars per chord instead of using the seed's own harmonic rhythm.")
    seeds.add_argument('--pedal-strength', type=float, default=None, help='Fixed pedal/drone strength 0.0..1.0.')
    seeds.add_argument('--voicing-openness', type=float, default=None, help='Fixed open fourth/fifth/octave amount 0.0..1.0.')
    seeds.add_argument('--suspension-amount', type=float, default=None, help='Fixed add9/sus4/maj7 tension amount 0.0..1.0.')
    seeds.add_argument('--pads', dest='pads', action='store_true', default=None, help='Enable the chorale pad layer.')
    seeds.add_argument('--no-pads', dest='pads', action='store_false', help='Disable the chorale pad layer.')
    seeds.add_argument('--pad-density', type=float, default=None, help='Fixed pad density 0.0..1.0.')
    seeds.add_argument('--pad-air-amount', type=float, default=None, help='Fixed high air-layer amount 0.0..1.0.')
    seeds.add_argument('--pad-voice-count', type=int, default=None, help='Pad voice count, 2..6.')
    seeds.add_argument('--pad-program', type=int, default=89, help='MIDI program number for pads.')
    parser.add_argument('--riffs', dest='riffs', action='store_true', default=None, help='Enable the derived riffs layer.')
    parser.add_argument('--no-riffs', dest='riffs', action='store_false', help='Disable the derived riffs layer.')
    parser.add_argument('--bass', dest='bass', action='store_true', default=None, help='Enable the derived bass layer.')
    parser.add_argument('--no-bass', dest='bass', action='store_false', help='Disable the derived bass layer.')
    parser.add_argument('--drums', dest='drums', action='store_true', default=None, help='Enable the drum layer.')
    parser.add_argument('--no-drums', dest='drums', action='store_false', help='Disable the drum layer.')
    parser.add_argument('--drum-intensity', type=float, default=0.78, help='Drum layer intensity 0.0..1.0.')
    parser.add_argument('--drop-intensity', type=float, default=0.9, help='Drop/body/climax density target 0.0..1.0.')
    parser.add_argument('--breakdown-sparsity', type=float, default=0.72, help='Strip-back amount 0.0..1.0.')
    parser.add_argument('--lead-program', type=int, default=80, help='MIDI program number for leads.')
    parser.add_argument('--riff-program', type=int, default=28, help='MIDI program number for riffs.')
    parser.add_argument('--bass-program', type=int, default=38, help='MIDI program number for bass.')
    parser.add_argument('--length', type=float, default=None, help='Target generation length in seconds for fitness scoring. Section bars define rendered duration.')
    parser.add_argument('--min-duration', type=float, default=None, help='Hard minimum rendered MIDI duration in seconds. Default: 180.')
    parser.add_argument('--scale', choices=available_scales(), default=None, help='Fix the scale instead of evolving it.')
    parser.add_argument('--ca-rule', type=int, default=None, help='Fix the elementary cellular automaton rule, 0..255.')
    parser.add_argument('--ca-width', type=int, default=None, help='Fix cellular automaton width.')
    parser.add_argument('--ca-steps', type=int, default=None, help='Fix cellular automaton steps.')
    parser.add_argument('--ca-seed-density', type=float, default=None, help='Fix cellular automaton seed density 0.0..1.0.')
    parser.add_argument('--ca-wrap-edges', dest='ca_wrap_edges', action='store_true', default=None, help='Wrap cellular automaton edges.')
    parser.add_argument('--no-ca-wrap-edges', dest='ca_wrap_edges', action='store_false', help='Do not wrap cellular automaton edges.')
    parser.add_argument('--lsystem-rule-set', default=None, help='Fix L-system rule set.')
    parser.add_argument('--lsystem-iterations', type=int, default=None, help='Fix L-system iterations.')
    parser.add_argument('--phrase-length', type=int, default=None, help='Fix phrase length.')
    parser.add_argument('--octave-low', type=int, default=None, help='Fix low octave.')
    parser.add_argument('--octave-high', type=int, default=None, help='Fix high octave.')
    parser.add_argument('--elite-fraction', type=float, default=None, help='GA elite fraction 0.0..1.0.')
    parser.add_argument('--tournament-size', type=int, default=None, help='GA tournament size.')
    parser.add_argument('--mutation-rate-min', type=float, default=None, help='Minimum genome mutation rate.')
    parser.add_argument('--mutation-rate-max', type=float, default=None, help='Maximum genome mutation rate.')
    parser.add_argument('--mutation-strength', type=float, default=None, help='Mutation step size for numeric genome fields.')
    parser.add_argument('--crossover-rate', type=float, default=None, help='GA crossover rate.')
    parser.add_argument('--random-immigrant-fraction', type=float, default=None, help='Fraction of each generation replaced with random immigrants.')
    parser.add_argument('--diversity-weight', type=float, default=None, help='Novelty/diversity contribution to final score.')
    parser.add_argument('--rhythm-density', type=float, default=None, help='Fixed rhythm density 0.0..1.0.')
    parser.add_argument('--accompaniment-density', type=float, default=None, help='Fixed accompaniment density 0.0..1.0.')
    parser.add_argument('--loop-density', type=float, default=None, help='Fixed lead loop density 0.0..1.0.')
    parser.add_argument('--lead-hook-shape', type=int, default=None, help='Fixed lead hook shape index.')
    parser.add_argument('--lead-hook-repetition', type=float, default=None, help='Fixed lead hook repetition 0.0..1.0.')
    parser.add_argument('--lead-variation-amount', type=float, default=None, help='Fixed lead variation amount 0.0..1.0.')
    parser.add_argument('--riff-density', type=float, default=None, help='Fixed riff density 0.0..1.0.')
    parser.add_argument('--riff-rhythmic-variation', type=float, default=None, help='Fixed riff rhythmic variation 0.0..1.0.')
    parser.add_argument('--riff-motif-mutation-amount', type=float, default=None, help='Fixed riff motif mutation 0.0..1.0.')
    parser.add_argument('--bass-density', type=float, default=None, help='Fixed bass density 0.0..1.0.')
    parser.add_argument('--bass-rhythmic-activity', type=float, default=None, help='Fixed bass rhythmic activity 0.0..1.0.')
    parser.add_argument('--bass-harmonic-strictness', type=float, default=None, help='Fixed bass harmonic strictness 0.0..1.0.')
    parser.add_argument('--drum-fill-probability', type=float, default=None, help='Fixed drum fill probability 0.0..1.0.')
    parser.add_argument('--snare-roll-intensity', type=float, default=None, help='Fixed snare roll intensity 0.0..1.0.')
    parser.add_argument('--transition-fill-amount', type=float, default=None, help='Fixed transition fill amount 0.0..1.0.')
    return parser

def main(argv: Optional[list[str]]=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.list_seeds:
        _print_seed_catalogue(args.genre or 'classic_trance')
        return 0
    if args.list_grooves:
        _print_groove_catalogue(args.genre or 'classic_trance')
        return 0
    try:
        project = load_ori(args.ori) if args.ori else None
        selection_config, min_duration = _selection_config_from_args(args, project)
        result = EvolutionarySelector(selection_config).run()
        write_result = write_midi(result.winner.composition, args.output, min_duration_seconds=min_duration, lead_program=args.lead_program, riff_program=args.riff_program, bass_program=args.bass_program, pad_program=args.pad_program)
        candidate_dir = None
        if args.save_candidates:
            candidate_dir = _save_candidate_midis(result, args, min_duration)
        variations_dir = None
        if args.export_all_seeds:
            variations_dir = default_variations_dir(args.output)
            write_seed_variations(result, variations_dir, min_duration_seconds=min_duration)
        report_path = None
        if args.fitness_report:
            report_path = write_fitness_report(result, str(default_fitness_report_path(args.output)))
    except (RuntimeError, ValueError) as exc:
        parser.error(str(exc))
        return 2
    _print_summary(result, write_result.path, write_result.duration_seconds, report_path, candidate_dir, variations_dir)
    return 0

def _print_seed_catalogue(genre: str) -> None:
    print(f'Oriondrive harmonic seeds, ordered by {genre} affinity:\n')
    for row in seed_summary_rows(genre):
        pedal = 'pedal' if row['pedal'] else 'moving bass'
        print(f"{row['name']:<18} {row['label']}")
        print(f"{'':<18} {row['summary']}")
        print(f"{'':<18} {row['mode']} | {row['progression']} | {pedal} | {row['cadence']} cadence | {row['harmonic_rhythm_bars']} bars/chord\n")

def _print_groove_catalogue(genre: str) -> None:
    print(f'Oriondrive groove profiles, ordered by {genre} affinity:\n')
    for row in groove_summary_rows(genre):
        swing = f", swing {row['swing']:.2f}" if row['swing'] else ''
        print(f"{row['name']:<20} {row['label']}")
        print(f"{'':<20} {row['summary']}")
        print(f"{'':<20} {row['bass_style']} bass | kick on {row['kick']} | hat step {row['hat_step']:g}{swing}\n")

def _selection_config_from_args(args: argparse.Namespace, project: OriProject | None) -> tuple[SelectionConfig, float]:
    project_parameters = project.parameters if project else None
    project_ca = project.ca if project else None
    project_lsystem = project.lsystem if project else None
    project_ga = project.ga if project else None
    project_musical = project.musical if project else None
    requested_genre = args.genre or (normalize_genre(args.style) if args.style else None)
    genre = requested_genre or (project.genre if project else 'classic_trance')
    arrangement_template = args.arrangement_template or (project.genre if project else genre)
    arrangement = arrangement_from_ori_project(project, bars_per_loop=args.bars_per_loop) if project else arrangement_from_template(arrangement_template, args.bars_per_loop)
    seed = args.seed if args.seed is not None else project_parameters.seed if project_parameters and project_parameters.seed is not None else 42
    target_length = args.length if args.length is not None else project_parameters.generation_length_seconds if project_parameters else None
    min_duration = args.min_duration if args.min_duration is not None else DEFAULT_MIN_DURATION_SECONDS
    enable_drums_default = False if genre == 'berlin_school' else True
    project_harmony = project.harmony if project else None
    harmonic_seed = args.harmonic_seed
    if harmonic_seed is None and project_harmony and (project_harmony.harmonic_seed != AUTO_SEED):
        harmonic_seed = project_harmony.harmonic_seed
    if args.seed_pool is not None:
        seed_pool = tuple(validate_seed_pool([item.strip() for item in args.seed_pool.split(',') if item.strip()]))
    else:
        seed_pool = tuple(project_harmony.seed_pool) if project_harmony else None
    project_variation = project.variation if project else None
    groove = args.groove
    if groove is None and project_variation and (project_variation.groove != AUTO_GROOVE):
        groove = project_variation.groove
    if args.groove_pool is not None:
        groove_pool = tuple(validate_groove_pool([item.strip() for item in args.groove_pool.split(',') if item.strip()]))
    else:
        groove_pool = tuple(project_variation.groove_pool) if project_variation else None
    explore_ca = args.explore_ca if args.explore_ca is not None else project_variation.explore_ca if project_variation else False
    explore_rules = args.explore_rule_sets if args.explore_rule_sets is not None else project_variation.explore_rule_sets if project_variation else False
    explore_phrase = args.explore_phrase_length if args.explore_phrase_length is not None else project_variation.explore_phrase_length if project_variation else False
    tempo_drift = args.tempo_drift if args.tempo_drift is not None else project_variation.tempo_drift_bpm if project_variation else 0
    if args.tempo is not None:
        tempo_drift = 0
    tempo_center = args.tempo if args.tempo is not None else project_parameters.bpm if project_parameters else None
    return (SelectionConfig(seed=seed, candidates=args.candidates if args.candidates is not None else project_ga.candidates if project_ga else project_parameters.candidates if project_parameters else DEFAULT_CANDIDATE_COUNT, generations=args.generations if args.generations is not None else project_ga.generations if project_ga else project_parameters.generations if project_parameters else DEFAULT_GENERATIONS, min_duration_seconds=min_duration, target_duration_seconds=target_length, enable_riffs=args.riffs if args.riffs is not None else project_parameters.enable_riffs if project_parameters else False, enable_bass=args.bass if args.bass is not None else project_parameters.enable_bass if project_parameters else False, enable_drums=args.drums if args.drums is not None else project_parameters.enable_drums if project_parameters else enable_drums_default, enable_pads=args.pads if args.pads is not None else project_parameters.enable_pads if project_parameters else True, harmonic_seed=harmonic_seed, seed_pool=seed_pool, follow_seed_mode=args.follow_seed_mode if args.follow_seed_mode is not None else project_harmony.follow_seed_mode if project_harmony else True, protect_species=args.protect_species if args.protect_species is not None else project_harmony.protect_species if project_harmony else True, seed_mutation_rate=args.seed_mutation_rate if args.seed_mutation_rate is not None else project_harmony.seed_mutation_rate if project_harmony else 0.06, cross_seed_crossover_rate=args.cross_seed_crossover_rate if args.cross_seed_crossover_rate is not None else project_harmony.cross_seed_crossover_rate if project_harmony else 0.1, fixed_harmonic_rhythm_bars=args.harmonic_rhythm_bars if args.harmonic_rhythm_bars is not None else project_harmony.harmonic_rhythm_bars if project_harmony else None, fixed_pedal_strength=args.pedal_strength if args.pedal_strength is not None else project_harmony.pedal_strength if project_harmony else None, fixed_voicing_openness=args.voicing_openness if args.voicing_openness is not None else project_harmony.voicing_openness if project_harmony else None, fixed_suspension_amount=args.suspension_amount if args.suspension_amount is not None else project_harmony.suspension_amount if project_harmony else None, pad_density=args.pad_density if args.pad_density is not None else project_harmony.pad_density if project_harmony else None, pad_air_amount=args.pad_air_amount if args.pad_air_amount is not None else project_harmony.pad_air_amount if project_harmony else None, pad_voice_count=args.pad_voice_count if args.pad_voice_count is not None else project_harmony.pad_voice_count if project_harmony else None, allow_small_population=args.allow_small_population, fixed_tempo=args.tempo if args.tempo is not None else None if tempo_drift > 0 else project_parameters.bpm if project_parameters else None, tempo_center=tempo_center, tempo_drift=tempo_drift, fixed_scale=args.scale if args.scale is not None else project_parameters.scale if project_parameters else None, fixed_root_note=args.key if args.key is not None else project_parameters.key if project_parameters else None, fixed_ca_rule=args.ca_rule if args.ca_rule is not None else None if explore_ca else project_ca.rule if project_ca else None, fixed_ca_width=args.ca_width if args.ca_width is not None else None if explore_ca else project_ca.width if project_ca else None, fixed_ca_steps=args.ca_steps if args.ca_steps is not None else None if explore_ca else project_ca.steps if project_ca else None, fixed_ca_seed_density=args.ca_seed_density if args.ca_seed_density is not None else None if explore_ca else project_ca.seed_density if project_ca else None, fixed_ca_wrap_edges=args.ca_wrap_edges if args.ca_wrap_edges is not None else project_ca.wrap_edges if project_ca else None, fixed_lsystem_rules=args.lsystem_rule_set if args.lsystem_rule_set is not None else None if explore_rules else project_lsystem.rule_set if project_lsystem else None, fixed_lsystem_iterations=args.lsystem_iterations if args.lsystem_iterations is not None else project_lsystem.iterations if project_lsystem else None, fixed_phrase_length=args.phrase_length if args.phrase_length is not None else None if explore_phrase else project_lsystem.phrase_length if project_lsystem else None, fixed_octave_range=_octave_range_from_args(args, project_lsystem), groove=groove, groove_pool=groove_pool, groove_mutation_rate=args.groove_mutation_rate if args.groove_mutation_rate is not None else project_variation.groove_mutation_rate if project_variation else 0.1, genre=genre, style=None, bars_per_loop=args.bars_per_loop, arrangement_template=arrangement_template, arrangement=arrangement, drum_intensity=args.drum_intensity if args.drum_intensity != 0.78 or project_musical is None else project_musical.drum_intensity, drop_intensity=args.drop_intensity if args.drop_intensity != 0.9 or project_musical is None else project_musical.drop_density, breakdown_sparsity=args.breakdown_sparsity if args.breakdown_sparsity != 0.72 or project_musical is None else project_musical.breakdown_sparsity, rhythm_density=args.rhythm_density if args.rhythm_density is not None else project_musical.rhythm_density if project_musical else None, accompaniment_density=args.accompaniment_density if args.accompaniment_density is not None else project_musical.accompaniment_density if project_musical else None, loop_density=args.loop_density if args.loop_density is not None else project_musical.loop_density if project_musical else None, lead_hook_shape=args.lead_hook_shape if args.lead_hook_shape is not None else project_musical.lead_hook_shape if project_musical else None, lead_hook_repetition=args.lead_hook_repetition if args.lead_hook_repetition is not None else project_musical.lead_hook_repetition if project_musical else None, lead_variation_amount=args.lead_variation_amount if args.lead_variation_amount is not None else project_musical.lead_variation_amount if project_musical else None, riff_density=args.riff_density if args.riff_density is not None else project_musical.riff_density if project_musical else None, riff_rhythmic_variation=args.riff_rhythmic_variation if args.riff_rhythmic_variation is not None else project_musical.riff_rhythmic_variation if project_musical else None, riff_motif_mutation_amount=args.riff_motif_mutation_amount if args.riff_motif_mutation_amount is not None else project_musical.riff_motif_mutation_amount if project_musical else None, bass_density=args.bass_density if args.bass_density is not None else project_musical.bass_density if project_musical else None, bass_rhythmic_activity=args.bass_rhythmic_activity if args.bass_rhythmic_activity is not None else project_musical.bass_rhythmic_activity if project_musical else None, bass_harmonic_strictness=args.bass_harmonic_strictness if args.bass_harmonic_strictness is not None else project_musical.bass_harmonic_strictness if project_musical else None, drum_fill_probability=args.drum_fill_probability if args.drum_fill_probability is not None else project_musical.drum_fill_probability if project_musical else None, snare_roll_intensity=args.snare_roll_intensity if args.snare_roll_intensity is not None else project_musical.snare_roll_intensity if project_musical else None, transition_fill_amount=args.transition_fill_amount if args.transition_fill_amount is not None else project_musical.transition_fill_amount if project_musical else None, elite_fraction=args.elite_fraction if args.elite_fraction is not None else project_ga.elite_fraction if project_ga else 0.2, tournament_size=args.tournament_size if args.tournament_size is not None else project_ga.tournament_size if project_ga else 3, mutation_rate_min=args.mutation_rate_min if args.mutation_rate_min is not None else project_ga.mutation_rate_min if project_ga else 0.04, mutation_rate_max=args.mutation_rate_max if args.mutation_rate_max is not None else project_ga.mutation_rate_max if project_ga else 0.16, mutation_strength=args.mutation_strength if args.mutation_strength is not None else project_ga.mutation_strength if project_ga else 0.08, crossover_rate=args.crossover_rate if args.crossover_rate is not None else project_ga.crossover_rate if project_ga else 0.75, random_immigrant_fraction=args.random_immigrant_fraction if args.random_immigrant_fraction is not None else project_ga.random_immigrant_fraction if project_ga else 0.1, diversity_weight=args.diversity_weight if args.diversity_weight is not None else project_ga.diversity_weight if project_ga else 0.2, max_generations_without_improvement=project_ga.max_generations_without_improvement if project_ga else None), min_duration)

def _octave_range_from_args(args: argparse.Namespace, project_lsystem: object | None) -> tuple[int, int] | None:
    low = args.octave_low if args.octave_low is not None else project_lsystem.octave_low if project_lsystem else None
    high = args.octave_high if args.octave_high is not None else project_lsystem.octave_high if project_lsystem else None
    if low is None and high is None:
        return None
    if low is None or high is None:
        raise ValueError('--octave-low and --octave-high must be provided together.')
    return (int(low), int(high))

def _save_candidate_midis(result: SelectionResult, args: argparse.Namespace, min_duration: float) -> Path:
    candidate_dir = default_candidate_output_dir(args.output)
    candidate_dir.mkdir(parents=True, exist_ok=True)
    for rank, candidate in enumerate(result.ranked_candidates, start=1):
        candidate_path = candidate_dir / f'{rank:02d}_{candidate.candidate_id}.mid'
        write_midi(candidate.composition, str(candidate_path), min_duration_seconds=min_duration, lead_program=args.lead_program, riff_program=args.riff_program, bass_program=args.bass_program, pad_program=args.pad_program)
    return candidate_dir

def _print_summary(result: SelectionResult, output_path: Path, duration_seconds: float, report_path: Optional[Path], candidate_dir: Optional[Path], variations_dir: Optional[Path]=None) -> None:
    sections = ' -> '.join((str(section.get('name', '')) for section in result.winner.structure_map.get('sections', [])))
    print(f'Generated {result.candidate_count} candidates.')
    print(f'Ran {result.generations_ran} genetic generations.')
    print('Ranked candidates:')
    for rank, candidate in enumerate(result.ranked_candidates, start=1):
        layers = ', '.join(candidate.layers)
        print(f'{rank:02d}. {candidate.candidate_id} seed={candidate.harmonic_seed} groove={candidate.groove} score={candidate.final_score:.3f} duration={candidate.duration_seconds:.1f}s layers={layers}')
    variations = result.variations()
    if variations:
        print(f'Best per harmonic seed ({len(variations)} variations):')
        for rank, candidate in enumerate(variations, start=1):
            print(f'{rank:02d}. {candidate.harmonic_seed:<20} {candidate.groove:<20} score={candidate.final_score:.3f} mode={candidate.genome.scale} {candidate.genome.tempo}bpm')
    print(f'Best candidate: {result.winner.candidate_id}')
    print(f'Harmonic seed: {result.winner.harmonic_seed}')
    print(f'Groove: {result.winner.groove}')
    print(f'Best score: {result.winner.final_score:.3f}')
    print(f'Duration: {duration_seconds:.1f} seconds')
    print(f'Seed: {result.winner.random_seed}')
    print(f"Genre: {result.winner.structure_map.get('genre', 'classic_trance')}")
    print(f"Layers: {', '.join(result.winner.layers)}")
    print(f'Sections: {sections}')
    print(f'Saved: {output_path}')
    if report_path:
        print(f'Fitness report: {report_path}')
    if candidate_dir:
        print(f'Candidate MIDIs: {candidate_dir}')
    if variations_dir:
        print(f'Seed variations: {variations_dir}')
if __name__ == '__main__':
    raise SystemExit(main())
