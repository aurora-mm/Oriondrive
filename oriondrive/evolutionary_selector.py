from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import Any, List, Optional
from .arrangement import Arrangement, arrangement_from_template
from .candidate import CandidateComposition
from .composition import playback_duration_seconds
from .config import DEFAULT_CANDIDATE_COUNT, DEFAULT_GENERATIONS, DEFAULT_MIN_DURATION_SECONDS, VALID_GENRES, available_scales, root_pitch_class, validate_choice, validate_positive_int, validate_probability
from .fitness import DiversityContext, candidate_fingerprint, evaluate_candidate
from .grooves import VALID_GROOVE_NAMES, groove_allocation, validate_groove_pool
from .harmonic_seeds import VALID_SEED_NAMES, species_allocation, validate_seed_pool
from .genetic_algorithm import EvolutionConfig, Genome, arrange_layers_for_genome, crossover_genomes, genome_to_parameters, mutate_genome, normalize_genre, random_genome
from .lead_generator import LeadGenerator

@dataclass(frozen=True)
class SelectionConfig:
    seed: int = 42
    candidates: int = DEFAULT_CANDIDATE_COUNT
    generations: int = DEFAULT_GENERATIONS
    min_duration_seconds: float = DEFAULT_MIN_DURATION_SECONDS
    enable_riffs: bool = False
    enable_bass: bool = False
    enable_drums: bool = True
    enable_pads: bool = True
    harmonic_seed: Optional[str] = None
    seed_pool: Optional[tuple[str, ...]] = None
    groove: Optional[str] = None
    groove_pool: Optional[tuple[str, ...]] = None
    groove_mutation_rate: float = 0.1
    follow_seed_mode: bool = True
    seed_mutation_rate: float = 0.06
    cross_seed_crossover_rate: float = 0.1
    protect_species: bool = True
    fixed_harmonic_rhythm_bars: Optional[int] = None
    fixed_pedal_strength: Optional[float] = None
    fixed_voicing_openness: Optional[float] = None
    fixed_suspension_amount: Optional[float] = None
    pad_density: Optional[float] = None
    pad_air_amount: Optional[float] = None
    pad_voice_count: Optional[int] = None
    allow_small_population: bool = False
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
    fixed_octave_range: Optional[tuple[int, int]] = None
    tempo_center: Optional[int] = None
    tempo_drift: int = 0
    target_duration_seconds: Optional[float] = None
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

    def validate(self) -> None:
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
        validate_positive_int('candidates', self.candidates)
        validate_positive_int('generations', self.generations)
        if self.candidates < DEFAULT_CANDIDATE_COUNT and (not self.allow_small_population):
            raise ValueError(f'--candidates must be at least {DEFAULT_CANDIDATE_COUNT}; pass --allow-small-population for debugging runs.')
        if self.candidates < 2:
            raise ValueError('candidates must be at least 2.')
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
        validate_choice('genre', self.resolved_genre, VALID_GENRES)
        validate_choice('arrangement_template', self.arrangement_template, VALID_GENRES)
        if self.bars_per_loop != 8:
            raise ValueError('--bars-per-loop must be 8 for the current Oriondrive loop generators.')
        if self.target_duration_seconds is not None and self.target_duration_seconds <= 0:
            raise ValueError('--length must be greater than zero seconds.')
        validate_probability('drum_intensity', self.drum_intensity)
        validate_probability('drop_intensity', self.drop_intensity)
        validate_probability('breakdown_sparsity', self.breakdown_sparsity)
        for name in ('rhythm_density', 'accompaniment_density', 'loop_density', 'lead_hook_repetition', 'lead_variation_amount', 'riff_density', 'riff_rhythmic_variation', 'riff_motif_mutation_amount', 'bass_density', 'bass_rhythmic_activity', 'bass_harmonic_strictness', 'drum_fill_probability', 'snare_roll_intensity', 'transition_fill_amount', 'elite_fraction', 'mutation_rate_min', 'mutation_rate_max', 'mutation_strength', 'crossover_rate', 'random_immigrant_fraction', 'diversity_weight'):
            value = getattr(self, name)
            if value is not None:
                validate_probability(name, float(value))
        validate_positive_int('tournament_size', self.tournament_size)
        if self.mutation_rate_min > self.mutation_rate_max:
            raise ValueError('mutation_rate_min must be <= mutation_rate_max.')
        if self.max_generations_without_improvement is not None and self.max_generations_without_improvement < 1:
            raise ValueError('max_generations_without_improvement must be positive.')

    def evolution_config(self) -> EvolutionConfig:
        return EvolutionConfig(seed=self.seed, generations=self.generations, population_size=self.candidates, fixed_tempo=self.fixed_tempo, fixed_scale=self.fixed_scale, fixed_root_note=self.fixed_root_note, fixed_ca_rule=self.fixed_ca_rule, fixed_ca_width=self.fixed_ca_width, fixed_ca_steps=self.fixed_ca_steps, fixed_ca_seed_density=self.fixed_ca_seed_density, fixed_ca_wrap_edges=self.fixed_ca_wrap_edges, fixed_lsystem_rules=self.fixed_lsystem_rules, fixed_lsystem_iterations=self.fixed_lsystem_iterations, fixed_phrase_length=self.fixed_phrase_length, fixed_octave_range=self.fixed_octave_range, tempo_center=self.tempo_center, tempo_drift=self.tempo_drift, min_duration_seconds=self.min_duration_seconds, target_duration_seconds=self.target_duration_seconds, enable_riffs=self.enable_riffs, enable_bass=self.enable_bass, enable_drums=self.enable_drums, enable_pads=self.enable_pads, harmonic_seed=self.harmonic_seed, seed_pool=self.seed_pool, groove=self.groove, groove_pool=self.groove_pool, groove_mutation_rate=self.groove_mutation_rate, follow_seed_mode=self.follow_seed_mode, seed_mutation_rate=self.seed_mutation_rate, cross_seed_crossover_rate=self.cross_seed_crossover_rate, fixed_harmonic_rhythm_bars=self.fixed_harmonic_rhythm_bars, fixed_pedal_strength=self.fixed_pedal_strength, fixed_voicing_openness=self.fixed_voicing_openness, fixed_suspension_amount=self.fixed_suspension_amount, pad_density=self.pad_density, pad_air_amount=self.pad_air_amount, pad_voice_count=self.pad_voice_count, genre=self.resolved_genre, style=None, bars_per_loop=self.bars_per_loop, arrangement_template=self.arrangement_template, arrangement=self.arrangement, drum_intensity=self.drum_intensity, drum_steadiness=self.drum_steadiness, drop_intensity=self.drop_intensity, breakdown_sparsity=self.breakdown_sparsity, rhythm_density=self.rhythm_density, accompaniment_density=self.accompaniment_density, loop_density=self.loop_density, lead_hook_shape=self.lead_hook_shape, lead_hook_repetition=self.lead_hook_repetition, lead_variation_amount=self.lead_variation_amount, riff_density=self.riff_density, riff_rhythmic_variation=self.riff_rhythmic_variation, riff_motif_mutation_amount=self.riff_motif_mutation_amount, bass_density=self.bass_density, bass_rhythmic_activity=self.bass_rhythmic_activity, bass_harmonic_strictness=self.bass_harmonic_strictness, drum_fill_probability=self.drum_fill_probability, snare_roll_intensity=self.snare_roll_intensity, transition_fill_amount=self.transition_fill_amount, elite_fraction=self.elite_fraction, tournament_size=self.tournament_size, mutation_rate_min=self.mutation_rate_min, mutation_rate_max=self.mutation_rate_max, mutation_strength=self.mutation_strength, crossover_rate=self.crossover_rate, random_immigrant_fraction=self.random_immigrant_fraction, diversity_weight=self.diversity_weight, max_generations_without_improvement=self.max_generations_without_improvement)

    def legacy_evolution_config(self) -> EvolutionConfig:
        return self.evolution_config()

@dataclass
class SelectionResult:
    winner: CandidateComposition
    ranked_candidates: List[CandidateComposition]
    generations_ran: int
    candidate_count: int
    history: List[float] = field(default_factory=list)
    ga_settings: dict[str, Any] = field(default_factory=dict)
    seed_winners: dict[str, CandidateComposition] = field(default_factory=dict)
    seed_pool: List[str] = field(default_factory=list)

    def variations(self) -> List[CandidateComposition]:
        return sorted(self.seed_winners.values(), key=lambda candidate: candidate.final_score, reverse=True)

class EvolutionarySelector:

    def __init__(self, config: SelectionConfig):
        self.config = config
        self.config.validate()
        self.rng = random.Random(config.seed)
        self.evolution_config = config.evolution_config()
        self.lead_generator = LeadGenerator()
        self.arrangement = config.arrangement or arrangement_from_template(config.arrangement_template, config.bars_per_loop)
        self.seed_pool = self.evolution_config.resolved_seed_pool
        self.groove_pool = self.evolution_config.resolved_groove_pool

    def run(self) -> SelectionResult:
        allocation = species_allocation(self.seed_pool, self.config.candidates, self.config.resolved_genre)
        grooves = groove_allocation(self.groove_pool, self.config.candidates, self.config.resolved_genre)
        genomes = [random_genome(self.rng, self.evolution_config, harmonic_seed=name, groove=grooves[index]) for index, name in enumerate(allocation)]
        evaluated = self._evaluate_population(genomes, generation=0)
        history = [evaluated[0].final_score]
        best_score = evaluated[0].final_score
        stalled = 0
        seed_winners: dict[str, CandidateComposition] = {}
        self._record_seed_winners(seed_winners, evaluated)
        for generation in range(1, self.config.generations + 1):
            genomes = self._next_generation_genomes(evaluated)
            evaluated = self._evaluate_population(genomes, generation=generation)
            self._record_seed_winners(seed_winners, evaluated)
            history.append(evaluated[0].final_score)
            if evaluated[0].final_score > best_score:
                best_score = evaluated[0].final_score
                stalled = 0
            else:
                stalled += 1
            if self.config.max_generations_without_improvement and stalled >= self.config.max_generations_without_improvement:
                break
        ranked = sorted(evaluated, key=lambda candidate: candidate.final_score, reverse=True)
        overall = max([ranked[0]] + list(seed_winners.values()), key=lambda candidate: candidate.final_score)
        return SelectionResult(winner=overall, ranked_candidates=ranked, generations_ran=self.config.generations, candidate_count=self.config.candidates, history=history, ga_settings=self._ga_settings(), seed_winners=seed_winners, seed_pool=list(self.seed_pool))

    def _record_seed_winners(self, seed_winners: dict[str, CandidateComposition], evaluated: List[CandidateComposition]) -> None:
        for candidate in evaluated:
            name = candidate.harmonic_seed
            current = seed_winners.get(name)
            if current is None or candidate.final_score > current.final_score:
                seed_winners[name] = candidate

    def _evaluate_population(self, genomes: List[Genome], generation: int) -> List[CandidateComposition]:
        candidates = [self._generate_candidate(genome, generation, index) for index, genome in enumerate(genomes)]
        fingerprints = {candidate.candidate_id: candidate_fingerprint(candidate) for candidate in candidates}
        diversity_context = DiversityContext(fingerprints=fingerprints, diversity_weight=self.config.diversity_weight)
        for candidate in candidates:
            candidate.set_fitness(evaluate_candidate(candidate, genre=self.config.resolved_genre, min_duration_seconds=self.config.target_duration_seconds or self.config.min_duration_seconds, enable_riffs=self.config.enable_riffs, enable_bass=self.config.enable_bass, enable_drums=self.config.enable_drums, diversity_context=diversity_context))
        candidates.sort(key=lambda candidate: candidate.final_score, reverse=True)
        return candidates

    def _generate_candidate(self, genome: Genome, generation: int, index: int) -> CandidateComposition:
        render_seed = self.config.seed + generation * 1000003 + index * 10007
        parameters = genome_to_parameters(genome)
        lead = self.lead_generator.generate(parameters, random.Random(render_seed), arrangement=self.arrangement, genome=genome, riffs_enabled=self.config.enable_riffs, bass_enabled=self.config.enable_bass, drums_enabled=self.config.enable_drums, pads_enabled=self.config.enable_pads)
        arrangement = arrange_layers_for_genome(lead, genome, enable_riffs=self.config.enable_riffs, enable_bass=self.config.enable_bass, rng=random.Random(render_seed + 2), arrangement=self.arrangement, enable_drums=self.config.enable_drums, drum_intensity=self.config.drum_intensity, enable_pads=self.config.enable_pads, drum_steadiness=self.config.drum_steadiness)
        duration = playback_duration_seconds(arrangement)
        candidate = CandidateComposition(candidate_id=f'candidate_{index + 1:02d}', generation=generation, genome=genome, composition=arrangement, random_seed=render_seed, duration_seconds=duration)
        return candidate

    def _next_generation_genomes(self, evaluated: List[CandidateComposition]) -> List[Genome]:
        next_genomes = self._elite_genomes(evaluated)
        immigrant_target = int(round(self.config.candidates * self.config.random_immigrant_fraction))
        immigrant_index = 0
        while len(next_genomes) < self.config.candidates:
            if immigrant_target > 0 and len(next_genomes) >= self.config.candidates - immigrant_target:
                seed_name = self.seed_pool[immigrant_index % len(self.seed_pool)]
                groove_name = self.groove_pool[immigrant_index * 3 % len(self.groove_pool)]
                immigrant_index += 1
                next_genomes.append(random_genome(self.rng, self.evolution_config, harmonic_seed=seed_name, groove=groove_name))
                continue
            parent_a = self._tournament_select(evaluated)
            parent_b = self._tournament_select(evaluated, prefer_seed=parent_a.harmonic_seed)
            if self.rng.random() < self.config.crossover_rate:
                child = crossover_genomes(parent_a.genome, parent_b.genome, self.rng, self.evolution_config)
            else:
                child = parent_a.genome
            child = mutate_genome(child, self.rng, self.evolution_config)
            next_genomes.append(child)
        return next_genomes[:self.config.candidates]

    def _elite_genomes(self, evaluated: List[CandidateComposition]) -> List[Genome]:
        elite_count = max(1, min(len(evaluated), int(round(self.config.candidates * self.config.elite_fraction))))
        elites: List[Genome] = []
        if self.config.protect_species and len(self.seed_pool) > 1:
            best_by_seed: dict[str, CandidateComposition] = {}
            for candidate in evaluated:
                current = best_by_seed.get(candidate.harmonic_seed)
                if current is None or candidate.final_score > current.final_score:
                    best_by_seed[candidate.harmonic_seed] = candidate
            for candidate in sorted(best_by_seed.values(), key=lambda item: item.final_score, reverse=True):
                if len(elites) >= self.config.candidates:
                    break
                elites.append(candidate.genome)
        for candidate in evaluated[:elite_count]:
            if len(elites) >= self.config.candidates:
                break
            if candidate.genome not in elites:
                elites.append(candidate.genome)
        return elites

    def _tournament_select(self, evaluated: List[CandidateComposition], prefer_seed: Optional[str]=None) -> CandidateComposition:
        pool = evaluated
        if prefer_seed is not None and self.rng.random() > self.config.cross_seed_crossover_rate:
            same_species = [candidate for candidate in evaluated if candidate.harmonic_seed == prefer_seed]
            if len(same_species) >= 2:
                pool = same_species
        size = self.config.tournament_size
        competitors = self.rng.sample(pool, k=min(size, len(pool)))
        competitors.sort(key=lambda candidate: candidate.final_score, reverse=True)
        return competitors[0]

    def _ga_settings(self) -> dict[str, Any]:
        return {'elite_fraction': self.config.elite_fraction, 'tournament_size': self.config.tournament_size, 'mutation_rate_min': self.config.mutation_rate_min, 'mutation_rate_max': self.config.mutation_rate_max, 'mutation_strength': self.config.mutation_strength, 'crossover_rate': self.config.crossover_rate, 'random_immigrant_fraction': self.config.random_immigrant_fraction, 'diversity_weight': self.config.diversity_weight, 'max_generations_without_improvement': self.config.max_generations_without_improvement, 'seed_pool': list(self.seed_pool), 'groove_pool': list(self.groove_pool), 'groove': self.config.groove, 'groove_mutation_rate': self.config.groove_mutation_rate, 'harmonic_seed': self.config.harmonic_seed, 'follow_seed_mode': self.config.follow_seed_mode, 'seed_mutation_rate': self.config.seed_mutation_rate, 'cross_seed_crossover_rate': self.config.cross_seed_crossover_rate, 'protect_species': self.config.protect_species}
