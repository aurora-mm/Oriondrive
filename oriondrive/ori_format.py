from __future__ import annotations
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping
from .arrangement import DEFAULT_BARS_PER_LOOP, PAD_ROLES
from .config import DEFAULT_CANDIDATE_COUNT, DEFAULT_GENERATIONS, VALID_GENRES, available_scales, root_pitch_class, validate_choice
from .drum_generator import VALID_STEADINESS
from .grooves import AUTO_GROOVE, VALID_GROOVE_NAMES, default_groove_pool, validate_groove_pool
from .harmonic_seeds import AUTO_SEED, VALID_SEED_NAMES, default_seed_pool, validate_seed_pool
from .lsystem import available_rule_sets
ORI_FORMAT = 'oriondrive-ori'
ORI_VERSION = 3
SUPPORTED_ORI_VERSIONS = (1, 2, 3)
HARMONIC_RHYTHM_CHOICES = (1, 2, 4)

@dataclass(frozen=True)
class OriParameters:
    generation_length_seconds: float = 420.0
    bpm: int = 138
    key: str = 'C'
    scale: str = 'dorian'
    seed: int | None = 42
    candidates: int = DEFAULT_CANDIDATE_COUNT
    generations: int = DEFAULT_GENERATIONS
    enable_riffs: bool = True
    enable_bass: bool = True
    enable_drums: bool = True
    enable_pads: bool = True

@dataclass(frozen=True)
class OriHarmonyConfig:
    harmonic_seed: str = AUTO_SEED
    seed_pool: tuple[str, ...] = VALID_SEED_NAMES
    follow_seed_mode: bool = True
    protect_species: bool = True
    seed_mutation_rate: float = 0.06
    cross_seed_crossover_rate: float = 0.1
    harmonic_rhythm_bars: int | None = None
    pedal_strength: float | None = None
    voicing_openness: float | None = None
    suspension_amount: float | None = None
    pad_density: float = 0.7
    pad_air_amount: float = 0.45
    pad_voice_count: int = 4

@dataclass(frozen=True)
class OriVariationConfig:
    groove: str = AUTO_GROOVE
    groove_pool: tuple[str, ...] = VALID_GROOVE_NAMES
    groove_mutation_rate: float = 0.1
    explore_rule_sets: bool = True
    explore_ca: bool = True
    explore_phrase_length: bool = True
    explore_octave_range: bool = False
    tempo_drift_bpm: int = 2
    drum_steadiness: str = 'steady'

@dataclass(frozen=True)
class OriCAConfig:
    rule: int = 90
    width: int = 16
    steps: int = 64
    seed_density: float = 0.35
    wrap_edges: bool = True

@dataclass(frozen=True)
class OriLSystemConfig:
    rule_set: str = 'balanced'
    iterations: int = 4
    phrase_length: int = 8
    octave_low: int = 3
    octave_high: int = 5

@dataclass(frozen=True)
class OriGAConfig:
    candidates: int = DEFAULT_CANDIDATE_COUNT
    generations: int = DEFAULT_GENERATIONS
    elite_fraction: float = 0.2
    tournament_size: int = 3
    mutation_rate_min: float = 0.04
    mutation_rate_max: float = 0.16
    mutation_strength: float = 0.08
    crossover_rate: float = 0.75
    random_immigrant_fraction: float = 0.1
    diversity_weight: float = 0.2
    max_generations_without_improvement: int | None = None

@dataclass(frozen=True)
class OriMusicalControls:
    rhythm_density: float = 0.62
    accompaniment_density: float = 0.25
    loop_density: float = 0.68
    lead_hook_shape: int = 0
    lead_hook_repetition: float = 0.78
    lead_variation_amount: float = 0.28
    riff_density: float = 0.55
    riff_rhythmic_variation: float = 0.45
    riff_motif_mutation_amount: float = 0.35
    bass_density: float = 0.62
    bass_rhythmic_activity: float = 0.55
    bass_harmonic_strictness: float = 0.78
    drum_intensity: float = 0.78
    drum_fill_probability: float = 0.42
    snare_roll_intensity: float = 0.72
    transition_fill_amount: float = 0.45
    breakdown_sparsity: float = 0.72
    drop_density: float = 0.88

@dataclass(frozen=True)
class OriSection:
    name: str
    length_bars: int
    energy: float
    lead_role: str
    riff_role: str
    bass_role: str
    drum_role: str
    pad_role: str = ''

@dataclass(frozen=True)
class OriProject:
    title: str
    genre: str
    parameters: OriParameters
    sections: tuple[OriSection, ...]
    ca: OriCAConfig | None = None
    lsystem: OriLSystemConfig | None = None
    ga: OriGAConfig | None = None
    musical: OriMusicalControls | None = None
    harmony: OriHarmonyConfig | None = None
    variation: OriVariationConfig | None = None
    format: str = ORI_FORMAT
    version: int = ORI_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, 'ca', self.ca or default_ca_for_genre(self.genre))
        object.__setattr__(self, 'lsystem', self.lsystem or default_lsystem_for_genre(self.genre))
        object.__setattr__(self, 'ga', self.ga or default_ga_for_genre(self.genre, self.parameters.candidates, self.parameters.generations))
        object.__setattr__(self, 'musical', self.musical or default_musical_for_genre(self.genre))
        object.__setattr__(self, 'harmony', self.harmony or default_harmony_for_genre(self.genre))
        object.__setattr__(self, 'variation', self.variation or default_variation_for_genre(self.genre))

    def to_dict(self) -> dict[str, Any]:
        ga = self.ga or default_ga_for_genre(self.genre, self.parameters.candidates, self.parameters.generations)
        harmony = asdict(self.harmony or default_harmony_for_genre(self.genre))
        harmony['seed_pool'] = list(harmony['seed_pool'])
        variation = asdict(self.variation or default_variation_for_genre(self.genre))
        variation['groove_pool'] = list(variation['groove_pool'])
        parameters = asdict(self.parameters)
        parameters['candidates'] = ga.candidates
        parameters['generations'] = ga.generations
        return {'format': self.format, 'version': ORI_VERSION, 'title': self.title, 'genre': self.genre, 'parameters': parameters, 'harmony': harmony, 'variation': variation, 'ca': asdict(self.ca or default_ca_for_genre(self.genre)), 'lsystem': asdict(self.lsystem or default_lsystem_for_genre(self.genre)), 'ga': asdict(ga), 'musical': asdict(self.musical or default_musical_for_genre(self.genre)), 'sections': [asdict(section) for section in self.sections]}

def load_ori(path: str | Path) -> OriProject:
    source = Path(path)
    try:
        data = json.loads(source.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        raise ValueError(f'{source} is not valid JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}.') from exc
    except OSError as exc:
        raise ValueError(f'Could not read {source}: {exc}') from exc
    if not isinstance(data, Mapping):
        raise ValueError(f'{source} must contain a JSON object.')
    return project_from_dict(data, source=str(source))

def save_ori(project: OriProject, path: str | Path) -> None:
    validated = project_from_dict(project.to_dict(), source='project')
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(validated.to_dict(), indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

def project_from_dict(data: Mapping[str, Any], source: str='project') -> OriProject:
    if data.get('format') != ORI_FORMAT:
        raise ValueError(f"{source}: format must be '{ORI_FORMAT}'.")
    version = data.get('version')
    if version not in SUPPORTED_ORI_VERSIONS:
        raise ValueError(f'{source}: version must be one of {SUPPORTED_ORI_VERSIONS}.')
    title = _required_string(data, 'title', source)
    genre = _required_string(data, 'genre', source)
    validate_choice(f'{source}.genre', genre, VALID_GENRES)
    parameters_data = data.get('parameters')
    if not isinstance(parameters_data, Mapping):
        raise ValueError(f'{source}.parameters must be an object.')
    ga = _parse_ga(_optional_mapping(data, 'ga'), source, genre, parameters_data)
    parameters = _parse_parameters(parameters_data, source, ga)
    ca = _parse_ca(_optional_mapping(data, 'ca'), source, genre)
    lsystem = _parse_lsystem(_optional_mapping(data, 'lsystem'), source, genre)
    musical = _parse_musical(_optional_mapping(data, 'musical'), source, genre)
    harmony = _parse_harmony(_optional_mapping(data, 'harmony'), source, genre)
    variation = _parse_variation(_optional_mapping(data, 'variation'), source, genre)
    sections_data = data.get('sections')
    if not isinstance(sections_data, list) or not sections_data:
        raise ValueError(f'{source}.sections must be a non-empty array.')
    sections = tuple((_parse_section(section, index, source) for index, section in enumerate(sections_data)))
    return OriProject(title=title, genre=genre, parameters=parameters, ca=ca, lsystem=lsystem, ga=ga, musical=musical, harmony=harmony, variation=variation, sections=sections, version=ORI_VERSION)

def default_ca_for_genre(genre: str) -> OriCAConfig:
    if genre == 'ebm':
        return OriCAConfig(rule=30, width=16, steps=64, seed_density=0.42, wrap_edges=True)
    if genre == 'berlin_school':
        return OriCAConfig(rule=90, width=24, steps=96, seed_density=0.28, wrap_edges=True)
    return OriCAConfig(rule=110, width=16, steps=64, seed_density=0.35, wrap_edges=True)

def default_lsystem_for_genre(genre: str) -> OriLSystemConfig:
    if genre == 'ebm':
        return OriLSystemConfig(rule_set='ebm_machine', iterations=3, phrase_length=4, octave_low=2, octave_high=4)
    if genre == 'berlin_school':
        return OriLSystemConfig(rule_set='berlin_sequence', iterations=5, phrase_length=16, octave_low=3, octave_high=6)
    return OriLSystemConfig(rule_set='trance_hook', iterations=4, phrase_length=8, octave_low=3, octave_high=5)

def default_ga_for_genre(genre: str, candidates: int=DEFAULT_CANDIDATE_COUNT, generations: int=DEFAULT_GENERATIONS) -> OriGAConfig:
    if genre == 'ebm':
        return OriGAConfig(candidates=candidates, generations=generations, elite_fraction=0.16, mutation_strength=0.07, random_immigrant_fraction=0.12, diversity_weight=0.28)
    if genre == 'berlin_school':
        return OriGAConfig(candidates=candidates, generations=generations, elite_fraction=0.14, mutation_rate_min=0.06, mutation_rate_max=0.22, mutation_strength=0.12, random_immigrant_fraction=0.16, diversity_weight=0.34)
    return OriGAConfig(candidates=candidates, generations=generations, elite_fraction=0.2, mutation_strength=0.08, random_immigrant_fraction=0.1, diversity_weight=0.2)

def default_harmony_for_genre(genre: str) -> OriHarmonyConfig:
    pool = tuple(default_seed_pool(genre))
    if genre == 'ebm':
        return OriHarmonyConfig(seed_pool=pool, pad_density=0.52, pad_air_amount=0.22, pad_voice_count=3, seed_mutation_rate=0.05)
    if genre == 'berlin_school':
        return OriHarmonyConfig(seed_pool=pool, pad_density=0.88, pad_air_amount=0.68, pad_voice_count=5, seed_mutation_rate=0.09)
    return OriHarmonyConfig(seed_pool=pool)

def default_variation_for_genre(genre: str) -> OriVariationConfig:
    pool = tuple(default_groove_pool(genre))
    if genre == 'ebm':
        return OriVariationConfig(groove_pool=pool, tempo_drift_bpm=3, groove_mutation_rate=0.08, drum_steadiness='steady')
    if genre == 'berlin_school':
        return OriVariationConfig(groove_pool=pool, tempo_drift_bpm=8, groove_mutation_rate=0.14, explore_octave_range=True, drum_steadiness='free')
    return OriVariationConfig(groove_pool=pool, tempo_drift_bpm=2, drum_steadiness='steady')

def default_musical_for_genre(genre: str) -> OriMusicalControls:
    if genre == 'ebm':
        return OriMusicalControls(rhythm_density=0.74, accompaniment_density=0.22, loop_density=0.76, lead_hook_shape=4, lead_hook_repetition=0.9, lead_variation_amount=0.18, riff_density=0.7, riff_rhythmic_variation=0.34, riff_motif_mutation_amount=0.2, bass_density=0.82, bass_rhythmic_activity=0.78, bass_harmonic_strictness=0.9, drum_intensity=0.84, drum_fill_probability=0.28, snare_roll_intensity=0.26, transition_fill_amount=0.3, breakdown_sparsity=0.42, drop_density=0.72)
    if genre == 'berlin_school':
        return OriMusicalControls(rhythm_density=0.54, accompaniment_density=0.42, loop_density=0.62, lead_hook_shape=8, lead_hook_repetition=0.82, lead_variation_amount=0.46, riff_density=0.76, riff_rhythmic_variation=0.7, riff_motif_mutation_amount=0.48, bass_density=0.62, bass_rhythmic_activity=0.54, bass_harmonic_strictness=0.72, drum_intensity=0.18, drum_fill_probability=0.08, snare_roll_intensity=0.08, transition_fill_amount=0.44, breakdown_sparsity=0.64, drop_density=0.58)
    return OriMusicalControls()

def _parse_parameters(data: Mapping[str, Any], source: str, ga: OriGAConfig) -> OriParameters:
    generation_length_seconds = _number(data, 'generation_length_seconds', source, default=420.0)
    if generation_length_seconds <= 0:
        raise ValueError(f'{source}.parameters.generation_length_seconds must be greater than zero.')
    bpm = _int(data, 'bpm', source, default=138)
    if bpm < 40 or bpm > 240:
        raise ValueError(f'{source}.parameters.bpm must be between 40 and 240.')
    key = str(data.get('key', 'C')).strip()
    try:
        root_pitch_class(key)
    except ValueError as exc:
        raise ValueError(f'{source}.parameters.key: {exc}') from exc
    scale = str(data.get('scale', 'dorian')).strip()
    validate_choice(f'{source}.parameters.scale', scale, available_scales())
    seed_value = data.get('seed', 42)
    try:
        seed = None if seed_value in (None, '') else int(seed_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{source}.parameters.seed must be an integer or null.') from exc
    return OriParameters(generation_length_seconds=float(generation_length_seconds), bpm=bpm, key=key, scale=scale, seed=seed, candidates=ga.candidates, generations=ga.generations, enable_riffs=_bool(data, 'enable_riffs', source, default=True), enable_bass=_bool(data, 'enable_bass', source, default=True), enable_drums=_bool(data, 'enable_drums', source, default=True), enable_pads=_bool(data, 'enable_pads', source, default=True))

def _parse_ca(data: Mapping[str, Any] | None, source: str, genre: str) -> OriCAConfig:
    defaults = default_ca_for_genre(genre)
    data = data or {}
    rule = _int(data, 'rule', f'{source}.ca', default=defaults.rule)
    if rule < 0 or rule > 255:
        raise ValueError(f'{source}.ca.rule must be between 0 and 255.')
    width = _int(data, 'width', f'{source}.ca', default=defaults.width)
    steps = _int(data, 'steps', f'{source}.ca', default=defaults.steps)
    if width < 4:
        raise ValueError(f'{source}.ca.width must be at least 4.')
    if steps < 1:
        raise ValueError(f'{source}.ca.steps must be positive.')
    seed_density = _number(data, 'seed_density', f'{source}.ca', default=defaults.seed_density)
    _validate_probability(f'{source}.ca.seed_density', seed_density)
    return OriCAConfig(rule=rule, width=width, steps=steps, seed_density=float(seed_density), wrap_edges=_bool(data, 'wrap_edges', f'{source}.ca', default=defaults.wrap_edges))

def _parse_lsystem(data: Mapping[str, Any] | None, source: str, genre: str) -> OriLSystemConfig:
    defaults = default_lsystem_for_genre(genre)
    data = data or {}
    rule_set = str(data.get('rule_set', defaults.rule_set)).strip()
    validate_choice(f'{source}.lsystem.rule_set', rule_set, available_rule_sets())
    iterations = _int(data, 'iterations', f'{source}.lsystem', default=defaults.iterations)
    if iterations < 0 or iterations > 7:
        raise ValueError(f'{source}.lsystem.iterations must be between 0 and 7.')
    phrase_length = _int(data, 'phrase_length', f'{source}.lsystem', default=defaults.phrase_length)
    if phrase_length <= 0:
        raise ValueError(f'{source}.lsystem.phrase_length must be positive.')
    octave_low = _int(data, 'octave_low', f'{source}.lsystem', default=defaults.octave_low)
    octave_high = _int(data, 'octave_high', f'{source}.lsystem', default=defaults.octave_high)
    if octave_low > octave_high or octave_low < 0 or octave_high > 8:
        raise ValueError(f'{source}.lsystem octave range must be ordered and stay within 0..8.')
    return OriLSystemConfig(rule_set=rule_set, iterations=iterations, phrase_length=phrase_length, octave_low=octave_low, octave_high=octave_high)

def _parse_ga(data: Mapping[str, Any] | None, source: str, genre: str, parameters_data: Mapping[str, Any]) -> OriGAConfig:
    param_candidates = _int(parameters_data, 'candidates', f'{source}.parameters', default=DEFAULT_CANDIDATE_COUNT)
    param_generations = _int(parameters_data, 'generations', f'{source}.parameters', default=DEFAULT_GENERATIONS)
    defaults = default_ga_for_genre(genre, param_candidates, param_generations)
    data = data or {}
    candidates = _int(data, 'candidates', f'{source}.ga', default=defaults.candidates)
    generations = _int(data, 'generations', f'{source}.ga', default=defaults.generations)
    if candidates < 2:
        raise ValueError(f'{source}.ga.candidates must be at least 2.')
    if generations < 1:
        raise ValueError(f'{source}.ga.generations must be at least 1.')
    elite_fraction = _prob(data, 'elite_fraction', f'{source}.ga', defaults.elite_fraction)
    if elite_fraction <= 0:
        raise ValueError(f'{source}.ga.elite_fraction must be greater than zero.')
    tournament_size = _int(data, 'tournament_size', f'{source}.ga', default=defaults.tournament_size)
    if tournament_size < 2:
        raise ValueError(f'{source}.ga.tournament_size must be at least 2.')
    mutation_rate_min = _prob(data, 'mutation_rate_min', f'{source}.ga', defaults.mutation_rate_min)
    mutation_rate_max = _prob(data, 'mutation_rate_max', f'{source}.ga', defaults.mutation_rate_max)
    if mutation_rate_min > mutation_rate_max:
        raise ValueError(f'{source}.ga.mutation_rate_min must be <= mutation_rate_max.')
    max_stall_value = data.get('max_generations_without_improvement', defaults.max_generations_without_improvement)
    max_stall = None if max_stall_value in (None, '') else int(max_stall_value)
    if max_stall is not None and max_stall < 1:
        raise ValueError(f'{source}.ga.max_generations_without_improvement must be positive or null.')
    return OriGAConfig(candidates=candidates, generations=generations, elite_fraction=elite_fraction, tournament_size=tournament_size, mutation_rate_min=mutation_rate_min, mutation_rate_max=mutation_rate_max, mutation_strength=_prob(data, 'mutation_strength', f'{source}.ga', defaults.mutation_strength), crossover_rate=_prob(data, 'crossover_rate', f'{source}.ga', defaults.crossover_rate), random_immigrant_fraction=_prob(data, 'random_immigrant_fraction', f'{source}.ga', defaults.random_immigrant_fraction), diversity_weight=_prob(data, 'diversity_weight', f'{source}.ga', defaults.diversity_weight), max_generations_without_improvement=max_stall)

def _parse_musical(data: Mapping[str, Any] | None, source: str, genre: str) -> OriMusicalControls:
    defaults = default_musical_for_genre(genre)
    data = data or {}
    lead_hook_shape = _int(data, 'lead_hook_shape', f'{source}.musical', default=defaults.lead_hook_shape)
    if lead_hook_shape < 0 or lead_hook_shape > 12:
        raise ValueError(f'{source}.musical.lead_hook_shape must be between 0 and 12.')
    return OriMusicalControls(rhythm_density=_prob(data, 'rhythm_density', f'{source}.musical', defaults.rhythm_density), accompaniment_density=_prob(data, 'accompaniment_density', f'{source}.musical', defaults.accompaniment_density), loop_density=_prob(data, 'loop_density', f'{source}.musical', defaults.loop_density), lead_hook_shape=lead_hook_shape, lead_hook_repetition=_prob(data, 'lead_hook_repetition', f'{source}.musical', defaults.lead_hook_repetition), lead_variation_amount=_prob(data, 'lead_variation_amount', f'{source}.musical', defaults.lead_variation_amount), riff_density=_prob(data, 'riff_density', f'{source}.musical', defaults.riff_density), riff_rhythmic_variation=_prob(data, 'riff_rhythmic_variation', f'{source}.musical', defaults.riff_rhythmic_variation), riff_motif_mutation_amount=_prob(data, 'riff_motif_mutation_amount', f'{source}.musical', defaults.riff_motif_mutation_amount), bass_density=_prob(data, 'bass_density', f'{source}.musical', defaults.bass_density), bass_rhythmic_activity=_prob(data, 'bass_rhythmic_activity', f'{source}.musical', defaults.bass_rhythmic_activity), bass_harmonic_strictness=_prob(data, 'bass_harmonic_strictness', f'{source}.musical', defaults.bass_harmonic_strictness), drum_intensity=_prob(data, 'drum_intensity', f'{source}.musical', defaults.drum_intensity), drum_fill_probability=_prob(data, 'drum_fill_probability', f'{source}.musical', defaults.drum_fill_probability), snare_roll_intensity=_prob(data, 'snare_roll_intensity', f'{source}.musical', defaults.snare_roll_intensity), transition_fill_amount=_prob(data, 'transition_fill_amount', f'{source}.musical', defaults.transition_fill_amount), breakdown_sparsity=_prob(data, 'breakdown_sparsity', f'{source}.musical', defaults.breakdown_sparsity), drop_density=_prob(data, 'drop_density', f'{source}.musical', defaults.drop_density))

def _parse_harmony(data: Mapping[str, Any] | None, source: str, genre: str) -> OriHarmonyConfig:
    defaults = default_harmony_for_genre(genre)
    data = data or {}
    harmonic_seed = str(data.get('harmonic_seed', defaults.harmonic_seed)).strip() or AUTO_SEED
    if harmonic_seed != AUTO_SEED:
        validate_choice(f'{source}.harmony.harmonic_seed', harmonic_seed, VALID_SEED_NAMES)
    raw_pool = data.get('seed_pool', defaults.seed_pool)
    if isinstance(raw_pool, str):
        raw_pool = [item.strip() for item in raw_pool.split(',') if item.strip()]
    if not isinstance(raw_pool, (list, tuple)):
        raise ValueError(f'{source}.harmony.seed_pool must be an array of seed names.')
    try:
        seed_pool = tuple(validate_seed_pool([str(item) for item in raw_pool]))
    except ValueError as exc:
        raise ValueError(f'{source}.harmony.seed_pool: {exc}') from exc
    harmonic_rhythm = data.get('harmonic_rhythm_bars', defaults.harmonic_rhythm_bars)
    if harmonic_rhythm not in (None, ''):
        harmonic_rhythm = int(harmonic_rhythm)
        validate_choice(f'{source}.harmony.harmonic_rhythm_bars', harmonic_rhythm, HARMONIC_RHYTHM_CHOICES)
    else:
        harmonic_rhythm = None
    pad_voice_count = _int(data, 'pad_voice_count', f'{source}.harmony', default=defaults.pad_voice_count)
    if pad_voice_count < 2 or pad_voice_count > 6:
        raise ValueError(f'{source}.harmony.pad_voice_count must be between 2 and 6.')
    return OriHarmonyConfig(harmonic_seed=harmonic_seed, seed_pool=seed_pool, follow_seed_mode=_bool(data, 'follow_seed_mode', f'{source}.harmony', default=defaults.follow_seed_mode), protect_species=_bool(data, 'protect_species', f'{source}.harmony', default=defaults.protect_species), seed_mutation_rate=_prob(data, 'seed_mutation_rate', f'{source}.harmony', defaults.seed_mutation_rate), cross_seed_crossover_rate=_prob(data, 'cross_seed_crossover_rate', f'{source}.harmony', defaults.cross_seed_crossover_rate), harmonic_rhythm_bars=harmonic_rhythm, pedal_strength=_optional_prob(data, 'pedal_strength', f'{source}.harmony', defaults.pedal_strength), voicing_openness=_optional_prob(data, 'voicing_openness', f'{source}.harmony', defaults.voicing_openness), suspension_amount=_optional_prob(data, 'suspension_amount', f'{source}.harmony', defaults.suspension_amount), pad_density=_prob(data, 'pad_density', f'{source}.harmony', defaults.pad_density), pad_air_amount=_prob(data, 'pad_air_amount', f'{source}.harmony', defaults.pad_air_amount), pad_voice_count=pad_voice_count)

def _parse_variation(data: Mapping[str, Any] | None, source: str, genre: str) -> OriVariationConfig:
    defaults = default_variation_for_genre(genre)
    data = data or {}
    groove = str(data.get('groove', defaults.groove)).strip() or AUTO_GROOVE
    if groove != AUTO_GROOVE:
        validate_choice(f'{source}.variation.groove', groove, VALID_GROOVE_NAMES)
    raw_pool = data.get('groove_pool', defaults.groove_pool)
    if isinstance(raw_pool, str):
        raw_pool = [item.strip() for item in raw_pool.split(',') if item.strip()]
    if not isinstance(raw_pool, (list, tuple)):
        raise ValueError(f'{source}.variation.groove_pool must be an array of groove names.')
    try:
        groove_pool = tuple(validate_groove_pool([str(item) for item in raw_pool]))
    except ValueError as exc:
        raise ValueError(f'{source}.variation.groove_pool: {exc}') from exc
    tempo_drift = _int(data, 'tempo_drift_bpm', f'{source}.variation', default=defaults.tempo_drift_bpm)
    if tempo_drift < 0 or tempo_drift > 60:
        raise ValueError(f'{source}.variation.tempo_drift_bpm must be between 0 and 60.')
    steadiness = str(data.get('drum_steadiness', defaults.drum_steadiness)).strip() or defaults.drum_steadiness
    validate_choice(f'{source}.variation.drum_steadiness', steadiness, VALID_STEADINESS)
    return OriVariationConfig(groove=groove, groove_pool=groove_pool, drum_steadiness=steadiness, groove_mutation_rate=_prob(data, 'groove_mutation_rate', f'{source}.variation', defaults.groove_mutation_rate), explore_rule_sets=_bool(data, 'explore_rule_sets', f'{source}.variation', default=defaults.explore_rule_sets), explore_ca=_bool(data, 'explore_ca', f'{source}.variation', default=defaults.explore_ca), explore_phrase_length=_bool(data, 'explore_phrase_length', f'{source}.variation', default=defaults.explore_phrase_length), explore_octave_range=_bool(data, 'explore_octave_range', f'{source}.variation', default=defaults.explore_octave_range), tempo_drift_bpm=tempo_drift)

def _parse_section(data: Any, index: int, source: str) -> OriSection:
    label = f'{source}.sections[{index}]'
    if not isinstance(data, Mapping):
        raise ValueError(f'{label} must be an object.')
    name = _required_string(data, 'name', label)
    length_bars = _int(data, 'length_bars', label)
    if length_bars <= 0:
        raise ValueError(f'{label}.length_bars must be positive.')
    if length_bars % DEFAULT_BARS_PER_LOOP != 0:
        raise ValueError(f'{label}.length_bars={length_bars} must be a multiple of {DEFAULT_BARS_PER_LOOP}; the current Oriondrive loop engine renders 8-bar blocks.')
    energy = _number(data, 'energy', label)
    if energy < 0.0 or energy > 1.0:
        raise ValueError(f'{label}.energy must be between 0.0 and 1.0.')
    pad_role = str(data.get('pad_role', '') or '').strip()
    if pad_role:
        validate_choice(f'{label}.pad_role', pad_role, PAD_ROLES)
    return OriSection(name=name, length_bars=length_bars, energy=float(energy), lead_role=_required_string(data, 'lead_role', label), riff_role=_required_string(data, 'riff_role', label), bass_role=_required_string(data, 'bass_role', label), drum_role=_required_string(data, 'drum_role', label), pad_role=pad_role)

def _optional_mapping(data: Mapping[str, Any], key: str) -> Mapping[str, Any] | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError(f'{key} must be an object.')
    return value

def _required_string(data: Mapping[str, Any], key: str, source: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{source}.{key} must be a non-empty string.')
    return value.strip()

def _number(data: Mapping[str, Any], key: str, source: str, default: float | None=None) -> float:
    value = data.get(key, default)
    if value is None or isinstance(value, bool):
        raise ValueError(f'{source}.{key} must be a number.')
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{source}.{key} must be a number.') from exc

def _int(data: Mapping[str, Any], key: str, source: str, default: int | None=None) -> int:
    value = data.get(key, default)
    if value is None or isinstance(value, bool):
        raise ValueError(f'{source}.{key} must be an integer.')
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{source}.{key} must be an integer.') from exc
    if float(parsed) != float(value):
        raise ValueError(f'{source}.{key} must be an integer.')
    return parsed

def _bool(data: Mapping[str, Any], key: str, source: str, default: bool) -> bool:
    value = data.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f'{source}.{key} must be true or false.')
    return value

def _prob(data: Mapping[str, Any], key: str, source: str, default: float) -> float:
    value = _number(data, key, source, default)
    _validate_probability(f'{source}.{key}', value)
    return float(value)

def _optional_prob(data: Mapping[str, Any], key: str, source: str, default: float | None) -> float | None:
    value = data.get(key, default)
    if value in (None, ''):
        return None
    number = _number(data, key, source, default if default is not None else 0.0)
    _validate_probability(f'{source}.{key}', number)
    return float(number)

def _validate_probability(name: str, value: float) -> None:
    if value < 0.0 or value > 1.0:
        raise ValueError(f'{name} must be between 0.0 and 1.0.')
