from __future__ import annotations
import json
from pathlib import Path
from typing import Optional
from .evolutionary_selector import SelectionResult

def default_fitness_report_path(output_path: str) -> Path:
    output = Path(output_path)
    return output.with_name(f'{output.stem}_fitness.json')

def default_candidate_output_dir(output_path: str) -> Path:
    output = Path(output_path)
    return output.with_name(f'{output.stem}_candidates')

def write_fitness_report(result: SelectionResult, output_path: Optional[str]=None) -> Path:
    path = Path(output_path) if output_path else Path('fitness_report.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {'winner': result.winner.candidate_id, 'winner_score': result.winner.final_score, 'winner_generation': result.winner.generation, 'winner_harmonic_seed': result.winner.harmonic_seed, 'candidate_count': result.candidate_count, 'generations': result.generations_ran, 'ga_settings': result.ga_settings, 'history': result.history, 'seed_pool': list(result.seed_pool), 'seed_variations': [{'harmonic_seed': candidate.harmonic_seed, 'mode': getattr(candidate.genome, 'scale', ''), 'final_score': candidate.final_score, 'generation': candidate.generation, 'random_seed': candidate.random_seed, 'harmony': dict(candidate.structure_map.get('harmony', {}))} for candidate in result.variations()], 'candidates': [candidate.to_report_dict() for candidate in result.ranked_candidates]}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding='utf-8')
    return path
