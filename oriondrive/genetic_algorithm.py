from __future__ import annotations
import math
import random
from dataclasses import dataclass, fields
from typing import Dict, List, Optional, Tuple
from .arrangement import Arrangement, arrangement_from_template
from .bass_generator import BassConfig, BassGenerator
from .cellular_automaton import CellularAutomatonConfig
from .composition import Composition, CompositionParameters, playback_duration_seconds
from .config import DEFAULT_CANDIDATE_COUNT, DEFAULT_GENERATIONS, DEFAULT_MIN_DURATION_SECONDS, VALID_GENRES, available_root_notes, available_scales, clamp, root_pitch_class, validate_choice, validate_positive_int, validate_probability
from .drum_generator import DrumConfig, DrumGenerator
from .grooves import GROOVES, VALID_GROOVE_NAMES, default_groove_pool, get_groove, validate_groove_pool
from .harmonic_seeds import HARMONIC_SEEDS, VALID_SEED_NAMES, default_seed_pool, get_harmonic_seed, validate_seed_pool
from .harmony import harmony_plan_for_genome
from .lsystem import LSystemConfig, available_rule_sets, get_rule_set
from .pad_generator import PadGenerator, pad_config_from_genome
from .riff_generator import RiffConfig, RiffGenerator
OCTAVE_RANGE_CHOICES: Tuple[Tuple[int, int], ...] = ((3, 5), (2, 5), (3, 6), (4, 5))
PHRASE_LENGTH_CHOICES = (8, 12, 16)
ROOT_CHOICES = tuple(available_root_notes())
HARMONIC_RHYTHM_CHOICES: Tuple[int, ...] = (1, 2, 4)

@dataclass(frozen=True)
class Genome:
    lsystem_rules: str
    iterations: int
    scale: str
    tempo: int
    ca_rule: int
    ca_width: int
    ca_steps: int
    ca_wrap_edges: bool
    rhythm_density: float
    pitch_range: Tuple[int, int]
    mutation_rate: float
    accompaniment_density: float
    phrase_length: int
    ca_seed_density: float
    riff_density: float
    riff_register: int
    riff_rhythmic_variation: float
    riff_motif_mutation_amount: float
    bass_density: float
    bass_register: int
    bass_rhythmic_activity: float
    bass_harmonic_strictness: float
    lead_hook_shape: int = 0
    lead_hook_repetition: float = 0.78
    lead_variation_amount: float = 0.28
    loop_density: float = 0.68
    section_energy_curve: Tuple[float, ...] = (0.22, 0.42, 0.58, 0.32, 0.78, 0.97, 0.38, 1.0, 0.26)
    breakdown_sparsity: float = 0.72
    drop_density: float = 0.88
    riff_density_by_section: Tuple[float, ...] = (0.0, 0.35, 0.58, 0.12, 0.72, 0.92, 0.18, 0.95, 0.25)
    bass_activity_by_section: Tuple[float, ...] = (0.15, 0.4, 0.6, 0.05, 0.7, 0.95, 0.2, 0.95, 0.25)
    drum_fill_probability: float = 0.42
    snare_roll_intensity: float = 0.72
    transition_fill_amount: float = 0.45
    root_note: str = 'C'
    harmonic_seed: str = 'aeolian_pedal'
    groove: str = 'four_on_floor'
    harmonic_rhythm_bars: int = 2
    pedal_strength: float = 0.85
    voicing_openness: float = 0.5
    suspension_amount: float = 0.6
    pad_density: float = 0.7
    pad_voice_count: int = 4
    pad_air_amount: float = 0.45

    def validate(self) -> None:
        validate_choice('lsystem_rules', self.lsystem_rules, available_rule_sets())
        validate_choice('harmonic_seed', self.harmonic_seed, VALID_SEED_NAMES)
        validate_choice('groove', self.groove, VALID_GROOVE_NAMES)
        validate_choice('harmonic_rhythm_bars', self.harmonic_rhythm_bars, HARMONIC_RHYTHM_CHOICES)
        if self.pad_voice_count < 2 or self.pad_voice_count > 6:
            raise ValueError('pad_voice_count must be between 2 and 6.')
        validate_choice('scale', self.scale, available_scales())
        if self.ca_rule < 0 or self.ca_rule > 255:
            raise ValueError('ca_rule must be between 0 and 255.')
        if self.ca_width < 4:
            raise ValueError('ca_width must be at least 4.')
        validate_positive_int('ca_steps', self.ca_steps)
        low_octave, high_octave = self.pitch_range
        if low_octave > high_octave or low_octave < 0 or high_octave > 8:
            raise ValueError('pitch_range must be ordered and stay within octaves 0..8.')
        validate_positive_int('phrase_length', self.phrase_length)
        root_pitch_class(self.root_note)
        if self.iterations < 2 or self.iterations > 6:
            raise ValueError('iterations must be between 2 and 6.')
        if self.tempo < 40 or self.tempo > 240:
            raise ValueError('tempo must be between 40 and 240 BPM.')
        if self.lead_hook_shape < 0 or self.lead_hook_shape > 12:
            raise ValueError('lead_hook_shape must be 0..12.')
        for name in ('rhythm_density', 'mutation_rate', 'accompaniment_density', 'ca_seed_density', 'lead_hook_repetition', 'lead_variation_amount', 'loop_density', 'breakdown_sparsity', 'drop_density', 'drum_fill_probability', 'snare_roll_intensity', 'transition_fill_amount', 'pedal_strength', 'voicing_openness', 'suspension_amount', 'pad_density', 'pad_air_amount'):
            validate_probability(name, float(getattr(self, name)))
        if not self.section_energy_curve:
            raise ValueError('section_energy_curve must contain at least one value.')
        if len(self.riff_density_by_section) != len(self.section_energy_curve):
            raise ValueError('riff_density_by_section must match section_energy_curve length.')
        if len(self.bass_activity_by_section) != len(self.section_energy_curve):
            raise ValueError('bass_activity_by_section must match section_energy_curve length.')
        for values_name in ('section_energy_curve', 'riff_density_by_section', 'bass_activity_by_section'):
            for value in getattr(self, values_name):
                validate_probability(values_name, float(value))
        RiffConfig(density=self.riff_density, register=self.riff_register, rhythmic_variation=self.riff_rhythmic_variation, motif_mutation_amount=self.riff_motif_mutation_amount).validate()
        BassConfig(density=self.bass_density, register=self.bass_register, rhythmic_activity=self.bass_rhythmic_activity, harmonic_strictness=self.bass_harmonic_strictness).validate()
        DrumConfig(fill_probability=self.drum_fill_probability, snare_roll_intensity=self.snare_roll_intensity, transition_fill_amount=self.transition_fill_amount).validate()

@dataclass(frozen=True)
class EvolutionConfig:
    seed: int = 42
    generations: int = DEFAULT_GENERATIONS
    population_size: int = DEFAULT_CANDIDATE_COUNT
    fixed_tempo: Optional[int] = None
    fixed_scale: Optional[str] = None
    fixed_root_note: Optional[str] = None
    fixed_ca_rule: Optional[int] = None
    fixed_ca_width: Optional[int] = None
    fixed_ca_steps: Optional[int] = None
    fixed_ca_seed_density: Optional[float] = None
    fixed_ca_wrap_edges: Optional[bool] = None
    fixed_lsystem_rules: Optional[str] = None
    fixed_lsystem_iterations: Optional[int] = None
    fixed_phrase_length: Optional[int] = None
    fixed_octave_range: Optional[Tuple[int, int]] = None
    tempo_center: Optional[int] = None
    tempo_drift: int = 0
    min_duration_seconds: float = DEFAULT_MIN_DURATION_SECONDS
    target_duration_seconds: Optional[float] = None
    enable_riffs: bool = False
    enable_bass: bool = False
    enable_drums: bool = True
    enable_pads: bool = True
    harmonic_seed: Optional[str] = None
    seed_pool: Optional[Tuple[str, ...]] = None
    groove: Optional[str] = None
    groove_pool: Optional[Tuple[str, ...]] = None
    groove_mutation_rate: float = 0.1
    follow_seed_mode: bool = True
    seed_mutation_rate: float = 0.06
    cross_seed_crossover_rate: float = 0.1
    fixed_harmonic_rhythm_bars: Optional[int] = None
    fixed_pedal_strength: Optional[float] = None
    fixed_voicing_openness: Optional[float] = None
    fixed_suspension_amount: Optional[float] = None
    pad_density: Optional[float] = None
    pad_air_amount: Optional[float] = None
    pad_voice_count: Optional[int] = None
    genre: str = 'classic_trance'
    style: Optional[str] = None
    bars_per_loop: int = 8
    arrangement_template: str = 'classic_trance'
    arrangement: Optional[Arrangement] = None
    drum_intensity: float = 0.78
    drum_steadiness: str = 'steady'
    drop_intensity: float = 0.9
    breakdown_sparsity: float = 0.72
    rhythm_density: Optional[float] = None
    accompaniment_density: Optional[float] = None
    loop_density: Optional[float] = None
    lead_hook_shape: Optional[int] = None
    lead_hook_repetition: Optional[float] = None
    lead_variation_amount: Optional[float] = None
    riff_density: Optional[float] = None
    riff_rhythmic_variation: Optional[float] = None
    riff_motif_mutation_amount: Optional[float] = None
    bass_density: Optional[float] = None
    bass_rhythmic_activity: Optional[float] = None
    bass_harmonic_strictness: Optional[float] = None
    drum_fill_probability: Optional[float] = None
    snare_roll_intensity: Optional[float] = None
    transition_fill_amount: Optional[float] = None
    elite_fraction: float = 0.2
    tournament_size: int = 3
    mutation_rate_min: float = 0.04
    mutation_rate_max: float = 0.16
    mutation_strength: float = 0.08
    crossover_rate: float = 0.75
    random_immigrant_fraction: float = 0.1
    diversity_weight: float = 0.2
    max_generations_without_improvement: Optional[int] = None

    @property
    def resolved_genre(self) -> str:
        return normalize_genre(self.genre if self.style is None else self.style)

    @property
    def resolved_seed_pool(self) -> List[str]:
        if self.harmonic_seed:
            return validate_seed_pool([self.harmonic_seed])
        if self.seed_pool:
            pool = validate_seed_pool(list(self.seed_pool))
            genre = self.resolved_genre
            return sorted(pool, key=lambda name: (-HARMONIC_SEEDS[name].affinity(genre), pool.index(name)))
        return default_seed_pool(self.resolved_genre)

    @property
    def resolved_groove_pool(self) -> List[str]:
        if self.groove:
            return validate_groove_pool([self.groove])
        if self.groove_pool:
            pool = validate_groove_pool(list(self.groove_pool))
            genre = self.resolved_genre
            return sorted(pool, key=lambda name: (-GROOVES[name].affinity(genre), pool.index(name)))
        return default_groove_pool(self.resolved_genre)

    def validate(self) -> None:
        validate_positive_int('generations', self.generations)
        if self.harmonic_seed is not None:
            validate_choice('harmonic_seed', self.harmonic_seed, VALID_SEED_NAMES)
        if self.seed_pool is not None:
            validate_seed_pool(list(self.seed_pool))
        if self.groove is not None:
            validate_choice('groove', self.groove, VALID_GROOVE_NAMES)
        if self.groove_pool is not None:
            validate_groove_pool(list(self.groove_pool))
        validate_probability('groove_mutation_rate', self.groove_mutation_rate)
        validate_probability('seed_mutation_rate', self.seed_mutation_rate)
        validate_probability('cross_seed_crossover_rate', self.cross_seed_crossover_rate)
        if self.fixed_harmonic_rhythm_bars is not None:
            validate_choice('harmonic_rhythm_bars', self.fixed_harmonic_rhythm_bars, HARMONIC_RHYTHM_CHOICES)
        if self.pad_voice_count is not None and (self.pad_voice_count < 2 or self.pad_voice_count > 6):
            raise ValueError('pad_voice_count must be between 2 and 6.')
        for name in ('fixed_pedal_strength', 'fixed_voicing_openness', 'fixed_suspension_amount', 'pad_density', 'pad_air_amount'):
            value = getattr(self, name)
            if value is not None:
                validate_probability(name, float(value))
        validate_positive_int('population', self.population_size)
        if self.population_size < 2:
            raise ValueError('population must be at least 2.')
        if self.min_duration_seconds <= 0:
            raise ValueError('--min-duration must be greater than zero seconds.')
        if self.fixed_tempo is not None and (self.fixed_tempo < 40 or self.fixed_tempo > 240):
            raise ValueError('--tempo must be between 40 and 240 BPM.')
        if self.fixed_scale is not None:
            validate_choice('scale', self.fixed_scale, available_scales())
        if self.fixed_root_note is not None:
            root_pitch_class(self.fixed_root_note)
        if self.fixed_ca_rule is not None and (self.fixed_ca_rule < 0 or self.fixed_ca_rule > 255):
            raise ValueError('--ca-rule must be between 0 and 255.')
        if self.fixed_ca_width is not None and self.fixed_ca_width < 4:
            raise ValueError('--ca-width must be at least 4.')
        if self.fixed_ca_steps is not None:
            validate_positive_int('ca_steps', self.fixed_ca_steps)
        if self.fixed_ca_seed_density is not None:
            validate_probability('ca_seed_density', self.fixed_ca_seed_density)
        if self.fixed_lsystem_rules is not None:
            validate_choice('lsystem_rule_set', self.fixed_lsystem_rules, available_rule_sets())
        if self.fixed_lsystem_iterations is not None and (self.fixed_lsystem_iterations < 0 or self.fixed_lsystem_iterations > 7):
            raise ValueError('--lsystem-iterations must be between 0 and 7.')
        if self.fixed_phrase_length is not None:
            validate_positive_int('phrase_length', self.fixed_phrase_length)
        if self.fixed_octave_range is not None:
            low, high = self.fixed_octave_range
            if low > high or low < 0 or high > 8:
                raise ValueError('octave range must be ordered and stay within 0..8.')
        validate_choice('genre', self.resolved_genre, VALID_GENRES)
        validate_choice('arrangement_template', self.arrangement_template, VALID_GENRES)
        if self.bars_per_loop != 8:
            raise ValueError('--bars-per-loop must be 8 for the current Oriondrive loop generators.')
        if self.target_duration_seconds is not None and self.target_duration_seconds <= 0:
            raise ValueError('--length must be greater than zero seconds.')
        validate_probability('drum_intensity', self.drum_intensity)
        validate_probability('drop_intensity', self.drop_intensity)
        validate_probability('breakdown_sparsity', self.breakdown_sparsity)
        for name in ('rhythm_density', 'accompaniment_density', 'loop_density', 'lead_hook_repetition', 'lead_variation_amount', 'riff_density', 'riff_rhythmic_variation', 'riff_motif_mutation_amount', 'bass_density', 'bass_rhythmic_activity', 'bass_harmonic_strictness', 'drum_fill_probability', 'snare_roll_intensity', 'transition_fill_amount'):
            value = getattr(self, name)
            if value is not None:
                validate_probability(name, float(value))
        if self.lead_hook_shape is not None and (self.lead_hook_shape < 0 or self.lead_hook_shape > 12):
            raise ValueError('lead_hook_shape must be 0..12.')
        if self.elite_fraction <= 0.0 or self.elite_fraction > 0.8:
            raise ValueError('elite_fraction must be greater than 0 and at most 0.8.')
        validate_positive_int('tournament_size', self.tournament_size)
        validate_probability('mutation_rate_min', self.mutation_rate_min)
        validate_probability('mutation_rate_max', self.mutation_rate_max)
        validate_probability('mutation_strength', self.mutation_strength)
        validate_probability('crossover_rate', self.crossover_rate)
        validate_probability('random_immigrant_fraction', self.random_immigrant_fraction)
        validate_probability('diversity_weight', self.diversity_weight)
        if self.mutation_rate_min > self.mutation_rate_max:
            raise ValueError('mutation_rate_min must be <= mutation_rate_max.')
        if self.max_generations_without_improvement is not None and self.max_generations_without_improvement < 1:
            raise ValueError('max_generations_without_improvement must be positive.')

@dataclass
class EvolutionResult:
    genome: Genome
    composition: Composition
    fitness: float
    history: List[float]

def genome_to_parameters(genome: Genome) -> CompositionParameters:
    genome.validate()
    rule_set = get_rule_set(genome.lsystem_rules)
    lsystem_config = LSystemConfig(axiom=rule_set.axiom, rules=rule_set.rules, iterations=genome.iterations, scale=genome.scale, root_note=genome.root_note, octave_range=genome.pitch_range, phrase_length=genome.phrase_length)
    ca_config = CellularAutomatonConfig(rule=genome.ca_rule, width=genome.ca_width, steps=genome.ca_steps, seed_density=genome.ca_seed_density, wrap_edges=genome.ca_wrap_edges)
    return CompositionParameters(lsystem=lsystem_config, ca=ca_config, tempo=genome.tempo, rhythm_density=genome.loop_density, accompaniment_density=genome.accompaniment_density)

def arrange_layers_for_genome(lead_composition: Composition, genome: Genome, enable_riffs: bool, enable_bass: bool, rng: random.Random, arrangement=None, enable_drums: bool=True, drum_intensity: float=0.78, enable_pads: bool=True, drum_steadiness: str='steady') -> Composition:
    genome.validate()
    arrangement = arrangement or arrangement_from_template('classic_trance', 8)
    arranged = Composition(tempo=lead_composition.tempo, leads=list(lead_composition.leads), riffs=[], bass=[], drums=[], pads=[], metadata=dict(lead_composition.metadata), structure_map=dict(lead_composition.structure_map))
    groove = get_groove(genome.groove)
    if enable_pads:
        plan = harmony_plan_for_genome(genome, arrangement)
        arranged.pads = PadGenerator(pad_config_from_genome(genome)).generate(plan, arrangement, rng)
    if enable_riffs:
        riff_config = RiffConfig(density=genome.riff_density, register=genome.riff_register, rhythmic_variation=genome.riff_rhythmic_variation, motif_mutation_amount=genome.riff_motif_mutation_amount, density_by_section=sum(genome.riff_density_by_section) / len(genome.riff_density_by_section), groove=groove)
        arranged.riffs = RiffGenerator(riff_config).generate(arranged, arrangement, rng)
    if enable_bass:
        bass_config = BassConfig(density=genome.bass_density, register=genome.bass_register, rhythmic_activity=genome.bass_rhythmic_activity, harmonic_strictness=genome.bass_harmonic_strictness, activity_by_section=sum(genome.bass_activity_by_section) / len(genome.bass_activity_by_section), groove=groove)
        arranged.bass = BassGenerator(bass_config).generate(arranged, arrangement, rng)
    if enable_drums:
        drum_config = DrumConfig(intensity=drum_intensity, fill_probability=genome.drum_fill_probability, snare_roll_intensity=genome.snare_roll_intensity, transition_fill_amount=genome.transition_fill_amount, groove=groove, steadiness=drum_steadiness)
        arranged.drums = DrumGenerator(drum_config).generate(arrangement, rng)
    arranged.metadata['enabled_layers'] = [name for name, enabled in (('leads', True), ('pads', enable_pads), ('riffs', enable_riffs), ('bass', enable_bass), ('drums', enable_drums)) if enabled]
    arranged.metadata['duration_seconds'] = playback_duration_seconds(arranged)
    arranged.metadata['genre'] = arrangement.genre
    arranged.metadata['arrangement_template'] = arrangement.template
    arranged.metadata['harmonic_seed'] = genome.harmonic_seed
    arranged.metadata['groove'] = genome.groove
    arranged.structure_map.setdefault('active_layers', arrangement.to_structure_map(enable_riffs, enable_bass, enable_drums, enable_pads)['active_layers'])
    return arranged

def random_genome(rng: random.Random, config: EvolutionConfig, harmonic_seed: Optional[str]=None, groove: Optional[str]=None) -> Genome:
    config.validate()
    genre = config.resolved_genre
    arrangement = config.arrangement or arrangement_from_template(config.arrangement_template, config.bars_per_loop)
    energy_curve = arrangement.section_energy_curve()
    riff_curve = arrangement.riff_density_curve()
    bass_curve = arrangement.bass_activity_curve()
    defaults = _genre_defaults(genre)
    seed_name = harmonic_seed or config.harmonic_seed or rng.choice(config.resolved_seed_pool)
    seed = get_harmonic_seed(seed_name)
    groove_name = groove or config.groove or rng.choice(config.resolved_groove_pool)
    groove_profile = get_groove(groove_name)
    pitch_ranges = defaults['pitch_ranges']
    fixed_octave = config.fixed_octave_range
    tempo_low, tempo_high = _tempo_window(config, seed, groove_profile, defaults)
    rule_sets = _preferred(seed.rule_sets, defaults['rule_sets'])
    ca_rules = _preferred(seed.ca_rules, defaults['ca_rules'])
    phrase_lengths = _preferred(seed.phrase_lengths, defaults['phrase_lengths'])
    return Genome(lsystem_rules=config.fixed_lsystem_rules or rng.choice(rule_sets), iterations=config.fixed_lsystem_iterations if config.fixed_lsystem_iterations is not None else rng.randint(defaults['iterations'][0], defaults['iterations'][1]), scale=_scale_for_seed(config, seed, rng, defaults), tempo=config.fixed_tempo or rng.randint(tempo_low, tempo_high), ca_rule=config.fixed_ca_rule if config.fixed_ca_rule is not None else rng.choice(ca_rules), ca_width=config.fixed_ca_width if config.fixed_ca_width is not None else int(rng.choice(defaults['ca_widths'])), ca_steps=config.fixed_ca_steps if config.fixed_ca_steps is not None else int(rng.choice(defaults['ca_steps'])), ca_wrap_edges=True if config.fixed_ca_wrap_edges is None else bool(config.fixed_ca_wrap_edges), rhythm_density=config.rhythm_density if config.rhythm_density is not None else rng.uniform(defaults['rhythm_density'][0], defaults['rhythm_density'][1]), pitch_range=fixed_octave or rng.choice(pitch_ranges), mutation_rate=rng.uniform(config.mutation_rate_min, config.mutation_rate_max), accompaniment_density=config.accompaniment_density if config.accompaniment_density is not None else rng.uniform(defaults['accompaniment_density'][0], defaults['accompaniment_density'][1]), phrase_length=config.fixed_phrase_length if config.fixed_phrase_length is not None else rng.choice(phrase_lengths), ca_seed_density=config.fixed_ca_seed_density if config.fixed_ca_seed_density is not None else rng.uniform(defaults['ca_seed_density'][0], defaults['ca_seed_density'][1]), riff_density=config.riff_density if config.riff_density is not None else rng.uniform(defaults['riff_density'][0], defaults['riff_density'][1]), riff_register=rng.choice((3, 4, 5)), riff_rhythmic_variation=config.riff_rhythmic_variation if config.riff_rhythmic_variation is not None else rng.uniform(defaults['riff_variation'][0], defaults['riff_variation'][1]), riff_motif_mutation_amount=config.riff_motif_mutation_amount if config.riff_motif_mutation_amount is not None else rng.uniform(defaults['riff_mutation'][0], defaults['riff_mutation'][1]), bass_density=config.bass_density if config.bass_density is not None else rng.uniform(defaults['bass_density'][0], defaults['bass_density'][1]), bass_register=rng.choice((1, 2)), bass_rhythmic_activity=config.bass_rhythmic_activity if config.bass_rhythmic_activity is not None else rng.uniform(defaults['bass_activity'][0], defaults['bass_activity'][1]), bass_harmonic_strictness=config.bass_harmonic_strictness if config.bass_harmonic_strictness is not None else rng.uniform(defaults['bass_strictness'][0], defaults['bass_strictness'][1]), lead_hook_shape=config.lead_hook_shape if config.lead_hook_shape is not None else rng.randint(defaults['hook_shape'][0], defaults['hook_shape'][1]), lead_hook_repetition=config.lead_hook_repetition if config.lead_hook_repetition is not None else rng.uniform(defaults['hook_repetition'][0], defaults['hook_repetition'][1]), lead_variation_amount=config.lead_variation_amount if config.lead_variation_amount is not None else rng.uniform(defaults['lead_variation'][0], defaults['lead_variation'][1]), loop_density=config.loop_density if config.loop_density is not None else rng.uniform(defaults['loop_density'][0], defaults['loop_density'][1]), section_energy_curve=_mutated_curve(rng, energy_curve, 0.06), breakdown_sparsity=clamp(config.breakdown_sparsity + rng.uniform(-0.12, 0.12), 0.35, 0.95), drop_density=clamp(config.drop_intensity + rng.uniform(-0.1, 0.08), 0.55, 1.0), riff_density_by_section=_mutated_curve(rng, riff_curve, 0.1), bass_activity_by_section=_mutated_curve(rng, bass_curve, 0.1), drum_fill_probability=config.drum_fill_probability if config.drum_fill_probability is not None else rng.uniform(defaults['drum_fill'][0], defaults['drum_fill'][1]), snare_roll_intensity=config.snare_roll_intensity if config.snare_roll_intensity is not None else rng.uniform(defaults['snare_roll'][0], defaults['snare_roll'][1]), transition_fill_amount=config.transition_fill_amount if config.transition_fill_amount is not None else rng.uniform(defaults['transition_fill'][0], defaults['transition_fill'][1]), root_note=config.fixed_root_note or rng.choice(ROOT_CHOICES), harmonic_seed=seed.name, groove=groove_profile.name, harmonic_rhythm_bars=config.fixed_harmonic_rhythm_bars or seed.harmonic_rhythm_bars, pedal_strength=_seed_float(config.fixed_pedal_strength, 1.0 if seed.pedal else 0.35, rng, 0.1), voicing_openness=_seed_float(config.fixed_voicing_openness, seed.voicing_openness, rng, 0.1), suspension_amount=_seed_float(config.fixed_suspension_amount, seed.suspension, rng, 0.1), pad_density=_seed_float(config.pad_density, 0.7, rng, 0.14), pad_voice_count=config.pad_voice_count or rng.choice((3, 4, 4, 5)), pad_air_amount=_seed_float(config.pad_air_amount, 0.45, rng, 0.16))

def _preferred(seed_values: Tuple, genre_values) -> Tuple:
    return tuple(seed_values) if seed_values else tuple(genre_values)

def _tempo_window(config: EvolutionConfig, seed, groove_profile, defaults: Dict[str, object]) -> Tuple[int, int]:
    if config.tempo_center is not None and config.tempo_drift > 0:
        bias = seed.tempo_bias + groove_profile.tempo_bias
        centre = config.tempo_center + max(-config.tempo_drift, min(config.tempo_drift, bias))
        low = int(clamp(centre - config.tempo_drift, 40, 240))
        high = int(clamp(max(low, centre + config.tempo_drift), 40, 240))
        return (low, high)
    low, high = defaults['tempo']
    bias = seed.tempo_bias + groove_profile.tempo_bias
    low = int(clamp(low + bias, 40, 240))
    high = int(clamp(max(low, high + bias), 40, 240))
    return (low, high)

def _scale_for_seed(config: EvolutionConfig, seed, rng: random.Random, defaults: Dict[str, object]) -> str:
    if config.follow_seed_mode:
        return seed.mode
    return config.fixed_scale or rng.choice(defaults['scales'])

def _seed_float(fixed: Optional[float], seed_value: float, rng: random.Random, spread: float) -> float:
    if fixed is not None:
        return clamp(float(fixed), 0.0, 1.0)
    return clamp(seed_value + rng.uniform(-spread, spread), 0.0, 1.0)

def crossover_genomes(parent_a: Genome, parent_b: Genome, rng: random.Random, config: EvolutionConfig) -> Genome:
    data: Dict[str, object] = {}
    for field in fields(parent_a):
        data[field.name] = getattr(parent_a if rng.random() < 0.5 else parent_b, field.name)
    harmony_donor = parent_a
    if parent_a.harmonic_seed != parent_b.harmonic_seed and rng.random() < config.cross_seed_crossover_rate:
        harmony_donor = parent_b
    for gene in ('harmonic_seed', 'harmonic_rhythm_bars', 'pedal_strength', 'voicing_openness', 'suspension_amount'):
        data[gene] = getattr(harmony_donor, gene)
    data['groove'] = (parent_a if rng.random() < 0.5 else parent_b).groove
    if config.groove is not None:
        data['groove'] = config.groove
    if config.follow_seed_mode:
        data['scale'] = get_harmonic_seed(str(data['harmonic_seed'])).mode
    if config.harmonic_seed is not None:
        data['harmonic_seed'] = config.harmonic_seed
    if config.fixed_scale is not None and (not config.follow_seed_mode):
        data['scale'] = config.fixed_scale
    if config.fixed_tempo is not None:
        data['tempo'] = config.fixed_tempo
    if config.fixed_ca_rule is not None:
        data['ca_rule'] = config.fixed_ca_rule
    if config.fixed_ca_width is not None:
        data['ca_width'] = config.fixed_ca_width
    if config.fixed_ca_steps is not None:
        data['ca_steps'] = config.fixed_ca_steps
    if config.fixed_ca_seed_density is not None:
        data['ca_seed_density'] = config.fixed_ca_seed_density
    if config.fixed_ca_wrap_edges is not None:
        data['ca_wrap_edges'] = config.fixed_ca_wrap_edges
    if config.fixed_lsystem_rules is not None:
        data['lsystem_rules'] = config.fixed_lsystem_rules
    if config.fixed_lsystem_iterations is not None:
        data['iterations'] = config.fixed_lsystem_iterations
    if config.fixed_phrase_length is not None:
        data['phrase_length'] = config.fixed_phrase_length
    if config.fixed_octave_range is not None:
        data['pitch_range'] = config.fixed_octave_range
    if config.fixed_root_note is not None:
        data['root_note'] = config.fixed_root_note
    return Genome(**data)

def mutate_genome(genome: Genome, rng: random.Random, config: EvolutionConfig) -> Genome:
    rate = genome.mutation_rate
    data = dict(genome.__dict__)
    defaults = _genre_defaults(config.resolved_genre)
    strength = config.mutation_strength
    float_fields = ('rhythm_density', 'mutation_rate', 'accompaniment_density', 'ca_seed_density', 'riff_density', 'riff_rhythmic_variation', 'riff_motif_mutation_amount', 'bass_density', 'bass_rhythmic_activity', 'bass_harmonic_strictness', 'lead_hook_repetition', 'lead_variation_amount', 'loop_density', 'breakdown_sparsity', 'drop_density', 'drum_fill_probability', 'snare_roll_intensity', 'transition_fill_amount', 'pedal_strength', 'voicing_openness', 'suspension_amount', 'pad_density', 'pad_air_amount')
    seed = get_harmonic_seed(genome.harmonic_seed)
    if config.harmonic_seed is None and rng.random() < config.seed_mutation_rate:
        pool = [name for name in config.resolved_seed_pool if name != genome.harmonic_seed]
        if pool:
            seed = get_harmonic_seed(rng.choice(pool))
            data['harmonic_seed'] = seed.name
            data['harmonic_rhythm_bars'] = config.fixed_harmonic_rhythm_bars or seed.harmonic_rhythm_bars
            data['pedal_strength'] = 1.0 if seed.pedal else 0.35
            data['voicing_openness'] = seed.voicing_openness
            data['suspension_amount'] = seed.suspension
            if config.follow_seed_mode:
                data['scale'] = seed.mode
    if config.groove is None and rng.random() < config.groove_mutation_rate:
        pool = [name for name in config.resolved_groove_pool if name != genome.groove]
        if pool:
            data['groove'] = rng.choice(pool)
    if rng.random() < rate and config.fixed_harmonic_rhythm_bars is None:
        data['harmonic_rhythm_bars'] = rng.choice(HARMONIC_RHYTHM_CHOICES)
    if rng.random() < rate and config.pad_voice_count is None:
        data['pad_voice_count'] = rng.choice((3, 4, 5))
    if rng.random() < rate and config.fixed_lsystem_rules is None:
        data['lsystem_rules'] = rng.choice(_preferred(seed.rule_sets, defaults['rule_sets']))
    if rng.random() < rate and config.fixed_lsystem_iterations is None:
        data['iterations'] = int(clamp(genome.iterations + rng.choice((-1, 1)), 2, 6))
    if rng.random() < rate and config.fixed_scale is None and (not config.follow_seed_mode):
        data['scale'] = rng.choice(defaults['scales'])
    if rng.random() < rate and config.fixed_tempo is None:
        low, high = _tempo_window(config, seed, get_groove(str(data['groove'])), defaults)
        data['tempo'] = int(clamp(genome.tempo + rng.randint(-2, 2), low, high))
    if rng.random() < rate and config.fixed_ca_rule is None:
        data['ca_rule'] = rng.choice(_preferred(seed.ca_rules, defaults['ca_rules']))
    if rng.random() < rate and config.fixed_ca_width is None:
        data['ca_width'] = rng.choice(defaults['ca_widths'])
    if rng.random() < rate and config.fixed_ca_steps is None:
        data['ca_steps'] = rng.choice(defaults['ca_steps'])
    if rng.random() < rate and config.fixed_octave_range is None:
        data['pitch_range'] = rng.choice(defaults['pitch_ranges'])
    if rng.random() < rate and config.fixed_phrase_length is None:
        data['phrase_length'] = rng.choice(_preferred(seed.phrase_lengths, defaults['phrase_lengths']))
    if rng.random() < rate:
        data['riff_register'] = rng.choice((3, 4, 5))
    if rng.random() < rate:
        data['bass_register'] = rng.choice((1, 2))
    if rng.random() < rate:
        data['lead_hook_shape'] = int(clamp(genome.lead_hook_shape + rng.choice((-1, 1)), defaults['hook_shape'][0], defaults['hook_shape'][1]))
    if rng.random() < rate and config.fixed_root_note is None:
        data['root_note'] = rng.choice(ROOT_CHOICES)
    for name in float_fields:
        if rng.random() < rate:
            spread = strength if name != 'mutation_rate' else max(0.01, strength * 0.32)
            data[name] = clamp(float(data[name]) + rng.uniform(-spread, spread), 0.0, 1.0)
    for name in ('section_energy_curve', 'riff_density_by_section', 'bass_activity_by_section'):
        if rng.random() < rate:
            data[name] = _mutated_curve(rng, tuple(data[name]), 0.07)
    if config.harmonic_seed is not None:
        data['harmonic_seed'] = config.harmonic_seed
    if config.groove is not None:
        data['groove'] = config.groove
    if config.follow_seed_mode:
        data['scale'] = get_harmonic_seed(str(data['harmonic_seed'])).mode
    elif config.fixed_scale is not None:
        data['scale'] = config.fixed_scale
    if config.fixed_harmonic_rhythm_bars is not None:
        data['harmonic_rhythm_bars'] = config.fixed_harmonic_rhythm_bars
    if config.fixed_pedal_strength is not None:
        data['pedal_strength'] = config.fixed_pedal_strength
    if config.fixed_voicing_openness is not None:
        data['voicing_openness'] = config.fixed_voicing_openness
    if config.fixed_suspension_amount is not None:
        data['suspension_amount'] = config.fixed_suspension_amount
    if config.pad_density is not None:
        data['pad_density'] = config.pad_density
    if config.pad_air_amount is not None:
        data['pad_air_amount'] = config.pad_air_amount
    if config.pad_voice_count is not None:
        data['pad_voice_count'] = config.pad_voice_count
    if config.fixed_tempo is not None:
        data['tempo'] = config.fixed_tempo
    if config.fixed_ca_rule is not None:
        data['ca_rule'] = config.fixed_ca_rule
    if config.fixed_ca_width is not None:
        data['ca_width'] = config.fixed_ca_width
    if config.fixed_ca_steps is not None:
        data['ca_steps'] = config.fixed_ca_steps
    if config.fixed_ca_seed_density is not None:
        data['ca_seed_density'] = config.fixed_ca_seed_density
    if config.fixed_ca_wrap_edges is not None:
        data['ca_wrap_edges'] = config.fixed_ca_wrap_edges
    if config.fixed_lsystem_rules is not None:
        data['lsystem_rules'] = config.fixed_lsystem_rules
    if config.fixed_lsystem_iterations is not None:
        data['iterations'] = config.fixed_lsystem_iterations
    if config.fixed_phrase_length is not None:
        data['phrase_length'] = config.fixed_phrase_length
    if config.fixed_octave_range is not None:
        data['pitch_range'] = config.fixed_octave_range
    if config.fixed_root_note is not None:
        data['root_note'] = config.fixed_root_note
    fixed_float_fields = ('rhythm_density', 'accompaniment_density', 'loop_density', 'lead_hook_repetition', 'lead_variation_amount', 'riff_density', 'riff_rhythmic_variation', 'riff_motif_mutation_amount', 'bass_density', 'bass_rhythmic_activity', 'bass_harmonic_strictness', 'drum_fill_probability', 'snare_roll_intensity', 'transition_fill_amount')
    for name in fixed_float_fields:
        value = getattr(config, name)
        if value is not None:
            data[name] = value
    if config.lead_hook_shape is not None:
        data['lead_hook_shape'] = config.lead_hook_shape
    data['breakdown_sparsity'] = config.breakdown_sparsity if config.breakdown_sparsity is not None else data['breakdown_sparsity']
    data['drop_density'] = config.drop_intensity if config.drop_intensity is not None else data['drop_density']
    data['mutation_rate'] = clamp(float(data['mutation_rate']), config.mutation_rate_min, config.mutation_rate_max)
    return Genome(**data)

def evolve(config: EvolutionConfig) -> EvolutionResult:
    from .candidate import CandidateComposition
    from .fitness import evaluate_candidate
    from .lead_generator import LeadGenerator
    from .harmonic_seeds import species_allocation
    config.validate()
    rng = random.Random(config.seed)
    arrangement = config.arrangement or arrangement_from_template(config.arrangement_template, config.bars_per_loop)
    allocation = species_allocation(config.resolved_seed_pool, config.population_size, config.resolved_genre)
    population = [random_genome(rng, config, harmonic_seed=name) for name in allocation]
    best: tuple[float, Genome, Composition] | None = None
    history: List[float] = []
    lead_generator = LeadGenerator()
    for generation in range(config.generations):
        evaluated: List[tuple[float, Genome, Composition]] = []
        for index, genome in enumerate(population):
            render_seed = config.seed + generation * 10000 + index * 137
            parameters = genome_to_parameters(genome)
            lead = lead_generator.generate(parameters, random.Random(render_seed), arrangement=arrangement, genome=genome, riffs_enabled=config.enable_riffs, bass_enabled=config.enable_bass, drums_enabled=config.enable_drums)
            composition = arrange_layers_for_genome(lead, genome, config.enable_riffs, config.enable_bass, random.Random(render_seed + 53911), arrangement=arrangement, enable_drums=config.enable_drums, drum_intensity=config.drum_intensity, enable_pads=config.enable_pads)
            candidate = CandidateComposition(f'candidate_{index + 1:02d}', generation, genome, composition, render_seed, playback_duration_seconds(composition))
            score = float(evaluate_candidate(candidate, genre=config.resolved_genre, min_duration_seconds=config.target_duration_seconds or config.min_duration_seconds, enable_riffs=config.enable_riffs, enable_bass=config.enable_bass, enable_drums=config.enable_drums)['final_score'])
            evaluated.append((score, genome, composition))
        evaluated.sort(key=lambda item: item[0], reverse=True)
        history.append(evaluated[0][0])
        if best is None or evaluated[0][0] > best[0]:
            best = evaluated[0]
        elites = [evaluated[0][1], evaluated[1][1]]
        population = elites[:]
        while len(population) < config.population_size:
            a = rng.choice(evaluated[:max(2, len(evaluated) // 2)])[1]
            b = rng.choice(evaluated[:max(2, len(evaluated) // 2)])[1]
            population.append(mutate_genome(crossover_genomes(a, b, rng, config), rng, config))
    if best is None:
        raise RuntimeError('Evolution failed to produce a composition.')
    best[2].metadata['fitness'] = best[0]
    best[2].metadata['fitness_history'] = history
    return EvolutionResult(best[1], best[2], best[0], history)

def _mutated_curve(rng: random.Random, values: Tuple[float, ...], amount: float) -> Tuple[float, ...]:
    return tuple((clamp(value + rng.uniform(-amount, amount), 0.0, 1.0) for value in values))

def normalize_genre(value: str) -> str:
    normalized = value.strip().lower()
    if normalized == 'trance':
        return 'classic_trance'
    return normalized

def _genre_defaults(genre: str) -> Dict[str, object]:
    if genre == 'ebm':
        return {'tempo': (118, 132), 'rule_sets': ('ebm_command', 'ebm_machine', 'angular'), 'iterations': (2, 4), 'phrase_lengths': (4, 8), 'ca_rules': (30, 45, 60, 90, 110, 150), 'ca_widths': (12, 16, 20), 'ca_steps': (48, 64, 80), 'ca_seed_density': (0.32, 0.55), 'scales': ('natural_minor', 'harmonic_minor', 'minor_pentatonic'), 'pitch_ranges': ((3, 5), (2, 5), (3, 6)), 'rhythm_density': (0.56, 0.84), 'accompaniment_density': (0.14, 0.42), 'riff_density': (0.38, 0.78), 'riff_variation': (0.16, 0.48), 'riff_mutation': (0.08, 0.3), 'bass_density': (0.56, 0.88), 'bass_activity': (0.52, 0.92), 'bass_strictness': (0.78, 0.98), 'hook_shape': (4, 7), 'hook_repetition': (0.72, 0.96), 'lead_variation': (0.08, 0.32), 'loop_density': (0.62, 0.88), 'drum_fill': (0.18, 0.48), 'snare_roll': (0.22, 0.62), 'transition_fill': (0.18, 0.54)}
    if genre == 'berlin_school':
        return {'tempo': (88, 124), 'rule_sets': ('berlin_sequence', 'berlin_drift', 'restless', 'balanced'), 'iterations': (4, 6), 'phrase_lengths': (8, 12, 16), 'ca_rules': (18, 22, 30, 54, 90, 105, 110, 126, 150), 'ca_widths': (16, 24, 32), 'ca_steps': (64, 96, 128), 'ca_seed_density': (0.18, 0.42), 'scales': ('dorian', 'natural_minor', 'mixolydian', 'minor_pentatonic'), 'pitch_ranges': ((3, 5), (3, 6), (2, 5)), 'rhythm_density': (0.42, 0.7), 'accompaniment_density': (0.2, 0.52), 'riff_density': (0.44, 0.82), 'riff_variation': (0.38, 0.82), 'riff_mutation': (0.28, 0.62), 'bass_density': (0.44, 0.78), 'bass_activity': (0.38, 0.76), 'bass_strictness': (0.58, 0.88), 'hook_shape': (8, 12), 'hook_repetition': (0.58, 0.88), 'lead_variation': (0.22, 0.58), 'loop_density': (0.46, 0.76), 'drum_fill': (0.02, 0.18), 'snare_roll': (0.05, 0.28), 'transition_fill': (0.22, 0.62)}
    return {'tempo': (136, 140), 'rule_sets': ('trance_hook', 'balanced', 'lyrical', 'restless'), 'iterations': (3, 5), 'phrase_lengths': PHRASE_LENGTH_CHOICES, 'ca_rules': (30, 90, 110), 'ca_widths': (16, 20), 'ca_steps': (64, 80), 'ca_seed_density': (0.2, 0.5), 'scales': ('dorian', 'natural_minor', 'harmonic_minor'), 'pitch_ranges': OCTAVE_RANGE_CHOICES, 'rhythm_density': (0.48, 0.76), 'accompaniment_density': (0.1, 0.4), 'riff_density': (0.28, 0.68), 'riff_variation': (0.2, 0.78), 'riff_mutation': (0.1, 0.5), 'bass_density': (0.38, 0.76), 'bass_activity': (0.35, 0.82), 'bass_strictness': (0.68, 0.96), 'hook_shape': (0, 3), 'hook_repetition': (0.62, 0.92), 'lead_variation': (0.12, 0.46), 'loop_density': (0.55, 0.82), 'drum_fill': (0.25, 0.7), 'snare_roll': (0.45, 0.95), 'transition_fill': (0.25, 0.75)}
