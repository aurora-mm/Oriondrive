from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List
from .composition import Composition, NoteEvent
from .genetic_algorithm import Genome

@dataclass
class CandidateComposition:
    candidate_id: str
    generation: int
    genome: Genome
    composition: Composition
    random_seed: int
    duration_seconds: float
    fitness_breakdown: Dict[str, Any] = field(default_factory=dict)
    final_score: float = 0.0

    @property
    def leads(self) -> List[NoteEvent]:
        return self.composition.leads

    @property
    def riffs(self) -> List[NoteEvent]:
        return self.composition.riffs

    @property
    def bass(self) -> List[NoteEvent]:
        return self.composition.bass

    @property
    def drums(self) -> List[NoteEvent]:
        return self.composition.drums

    @property
    def pads(self) -> List[NoteEvent]:
        return self.composition.pads

    @property
    def harmonic_seed(self) -> str:
        return str(getattr(self.genome, 'harmonic_seed', 'aeolian_pedal'))

    @property
    def groove(self) -> str:
        return str(getattr(self.genome, 'groove', 'four_on_floor'))

    @property
    def structure_map(self) -> Dict[str, Any]:
        return self.composition.structure_map

    @property
    def tempo(self) -> int:
        return self.composition.tempo

    @property
    def layers(self) -> List[str]:
        return list(self.composition.metadata.get('enabled_layers', ['leads']))

    def set_fitness(self, breakdown: Dict[str, Any]) -> None:
        self.fitness_breakdown = breakdown
        self.final_score = float(breakdown['final_score'])
        self.composition.metadata['fitness_breakdown'] = breakdown
        self.composition.metadata['fitness'] = self.final_score

    def to_report_dict(self) -> Dict[str, Any]:
        return {'id': self.candidate_id, 'generation': self.generation, 'genre': self.fitness_breakdown.get('genre', self.structure_map.get('genre', 'classic_trance')), 'duration_seconds': self.duration_seconds, 'tempo': self.tempo, 'layers': self.layers, 'random_seed': self.random_seed, 'final_score': self.final_score, 'aesthetic_score': self.fitness_breakdown.get('aesthetic_score', 0.0), 'diversity_score': self.fitness_breakdown.get('diversity_score', 0.0), 'nearest_candidate_distance': self.fitness_breakdown.get('nearest_candidate_distance', 0.0), 'subscores': dict(self.fitness_breakdown.get('subscores', {})), 'weighted_subscores': dict(self.fitness_breakdown.get('weighted_subscores', {})), 'penalties': dict(self.fitness_breakdown.get('penalties', {})), 'weighted_penalties': dict(self.fitness_breakdown.get('weighted_penalties', {})), 'fitness_profile': dict(self.fitness_breakdown.get('fitness_profile', {})), 'genome': asdict(self.genome), 'ca': {'rule': self.genome.ca_rule, 'width': self.genome.ca_width, 'steps': self.genome.ca_steps, 'seed_density': self.genome.ca_seed_density, 'wrap_edges': self.genome.ca_wrap_edges}, 'lsystem': {'rule_set': self.genome.lsystem_rules, 'iterations': self.genome.iterations, 'phrase_length': self.genome.phrase_length, 'octave_range': self.genome.pitch_range}, 'musical_fingerprint': dict(self.fitness_breakdown.get('musical_fingerprint', {})), 'section_density_profile': list(self.fitness_breakdown.get('musical_fingerprint', {}).get('density_by_section', [])), 'layer_density_profile': dict(self.fitness_breakdown.get('musical_fingerprint', {}).get('layer_activity_by_section', {})), 'harmonic_seed': self.harmonic_seed, 'groove': self.groove, 'harmony': dict(self.structure_map.get('harmony', {})), 'event_counts': {'leads': len(self.leads), 'riffs': len(self.riffs), 'bass': len(self.bass), 'drums': len(self.drums), 'pads': len(self.pads)}}
