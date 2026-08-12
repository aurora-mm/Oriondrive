from __future__ import annotations
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple
from ..arrangement import PAD_ROLES, VALID_ARRANGEMENT_TEMPLATES
from ..config import available_root_notes, available_scales
from ..grooves import AUTO_GROOVE, GROOVES, VALID_GROOVE_NAMES, get_groove
from ..harmonic_seeds import AUTO_SEED, HARMONIC_SEEDS, VALID_SEED_NAMES, get_harmonic_seed
from ..lsystem import available_rule_sets
from ..ori_format import OriProject, load_ori, project_from_dict
ROLE_OPTIONS: Dict[str, List[str]] = {'lead': ['off', 'teaser', 'hints', 'fragments', 'breakdown', 'compressed', 'full_hook', 'variation_sparse', 'final_hook', 'echo'], 'riff': ['off', 'muted', 'repeating', 'atmospheric', 'rising', 'full', 'echo', 'full_variation', 'fade'], 'bass': ['off', 'minimal', 'pulse', 'active', 'tension', 'rolling'], 'drum': ['off', 'sparse', 'groove', 'buildup', 'reduced', 'snare_roll', 'full', 'outro'], 'pad': list(PAD_ROLES)}
GENRE_OPTIONS: Tuple[str, ...] = ('classic_trance', 'ebm', 'berlin_school')
GENRE_LABELS: Dict[str, str] = {'classic_trance': 'Cathedral Trance', 'ebm': 'Body Machine', 'berlin_school': 'Long-Form Sequencer'}
GENRE_DESCRIPTIONS: Dict[str, str] = {'classic_trance': 'A long build to an opened-out climax. Intro, buildup, breakdown, drop, final climax, outro across 168 bars.', 'ebm': 'Tight, low and articulated. Verse and chorus body music with a rigid pulse and declamatory phrasing, across 96 bars.', 'berlin_school': 'Drumless long-form evolution. A sequencer carries the pulse while the harmony mutates slowly across 224 bars.'}
KEY_OPTIONS: Tuple[str, ...] = tuple(available_root_notes())
SCALE_OPTIONS: Tuple[str, ...] = tuple(available_scales())
SEED_CHOICE_OPTIONS: Tuple[str, ...] = (AUTO_SEED,) + VALID_SEED_NAMES
GROOVE_CHOICE_OPTIONS: Tuple[str, ...] = (AUTO_GROOVE,) + VALID_GROOVE_NAMES

@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    kind: str
    section: str
    choices: Tuple[str, ...] = ()
    hint: str = ''
    optional: bool = False

    @property
    def is_numeric(self) -> bool:
        return self.kind in {'int', 'float'}

@dataclass(frozen=True)
class FieldGroup:
    key: str
    title: str
    subtitle: str
    fields: Tuple[FieldSpec, ...] = field(default_factory=tuple)
HARMONY_FIELDS: Tuple[FieldSpec, ...] = (FieldSpec('harmonic_seed', 'Harmonic seed', 'choice', 'harmony', SEED_CHOICE_OPTIONS, 'Auto stratifies the population across the pool and returns one arrangement per seed.'), FieldSpec('follow_seed_mode', 'Each seed imposes its own mode', 'bool', 'harmony', hint='Off keeps every species in the project scale.'), FieldSpec('protect_species', 'Reserve an elite slot per seed', 'bool', 'harmony', hint='Off falls back to plain global elitism, which lets one seed take over.'), FieldSpec('seed_mutation_rate', 'Seed drift rate', 'float', 'harmony', hint='How readily a genome moves to a different harmonic seed.'), FieldSpec('cross_seed_crossover_rate', 'Cross-seed crossover', 'float', 'harmony', hint='How often two different seeds are allowed to breed.'), FieldSpec('harmonic_rhythm_bars', 'Bars per chord', 'choice', 'harmony', ('', '1', '2', '4'), "Blank uses each seed's own harmonic rhythm.", optional=True), FieldSpec('pedal_strength', 'Pedal strength', 'float', 'harmony', hint="Blank uses the seed's own pedal.", optional=True), FieldSpec('voicing_openness', 'Voicing openness', 'float', 'harmony', hint='Open fourths, fifths and octaves.', optional=True), FieldSpec('suspension_amount', 'Suspension', 'float', 'harmony', hint='add9, sus4 and maj7 held through bass changes.', optional=True), FieldSpec('pad_density', 'Pad density', 'float', 'harmony'), FieldSpec('pad_air_amount', 'Air layer', 'float', 'harmony'), FieldSpec('pad_voice_count', 'Pad voices', 'int', 'harmony'))
VARIATION_FIELDS: Tuple[FieldSpec, ...] = (FieldSpec('groove', 'Groove', 'choice', 'variation', GROOVE_CHOICE_OPTIONS, 'Auto pairs a different rhythmic identity with each harmonic seed.'), FieldSpec('groove_mutation_rate', 'Groove drift rate', 'float', 'variation', hint='How readily a genome moves to a different groove.'), FieldSpec('tempo_drift_bpm', 'Tempo drift (BPM)', 'int', 'variation', hint='How far either side of the project tempo the search may go. 0 pins it.'), FieldSpec('explore_rule_sets', 'Explore L-system rule sets', 'bool', 'variation', hint='Off pins the project rule set for every candidate.'), FieldSpec('explore_ca', 'Explore cellular automaton', 'bool', 'variation', hint='Off pins the project CA rule, width, steps and density.'), FieldSpec('explore_phrase_length', 'Explore phrase length', 'bool', 'variation'), FieldSpec('explore_octave_range', 'Explore octave range', 'bool', 'variation'))
CA_FIELDS: Tuple[FieldSpec, ...] = (FieldSpec('ca_rule', 'Rule', 'int', 'ca'), FieldSpec('ca_width', 'Width', 'int', 'ca'), FieldSpec('ca_steps', 'Steps', 'int', 'ca'), FieldSpec('ca_seed_density', 'Seed density', 'float', 'ca'), FieldSpec('ca_wrap_edges', 'Wrap edges', 'bool', 'ca'))
LSYSTEM_FIELDS: Tuple[FieldSpec, ...] = (FieldSpec('lsystem_rule_set', 'Rule set', 'choice', 'lsystem', tuple(available_rule_sets())), FieldSpec('lsystem_iterations', 'Iterations', 'int', 'lsystem'), FieldSpec('phrase_length', 'Phrase length', 'int', 'lsystem'), FieldSpec('octave_low', 'Octave low', 'int', 'lsystem'), FieldSpec('octave_high', 'Octave high', 'int', 'lsystem'))
GA_FIELDS: Tuple[FieldSpec, ...] = (FieldSpec('elite_fraction', 'Elite fraction', 'float', 'ga'), FieldSpec('tournament_size', 'Tournament size', 'int', 'ga'), FieldSpec('mutation_rate_min', 'Mutation rate min', 'float', 'ga'), FieldSpec('mutation_rate_max', 'Mutation rate max', 'float', 'ga'), FieldSpec('mutation_strength', 'Mutation strength', 'float', 'ga'), FieldSpec('crossover_rate', 'Crossover rate', 'float', 'ga'), FieldSpec('random_immigrant_fraction', 'Random immigrants', 'float', 'ga'), FieldSpec('diversity_weight', 'Diversity weight', 'float', 'ga'))
MUSICAL_FIELDS: Tuple[FieldSpec, ...] = (FieldSpec('rhythm_density', 'Rhythm density', 'float', 'musical'), FieldSpec('accompaniment_density', 'Accompaniment', 'float', 'musical'), FieldSpec('loop_density', 'Loop density', 'float', 'musical'), FieldSpec('lead_hook_shape', 'Hook shape', 'int', 'musical'), FieldSpec('lead_hook_repetition', 'Hook repetition', 'float', 'musical'), FieldSpec('lead_variation_amount', 'Lead variation', 'float', 'musical'), FieldSpec('riff_density', 'Riff density', 'float', 'musical'), FieldSpec('riff_rhythmic_variation', 'Riff rhythm', 'float', 'musical'), FieldSpec('riff_motif_mutation_amount', 'Riff mutation', 'float', 'musical'), FieldSpec('bass_density', 'Bass density', 'float', 'musical'), FieldSpec('bass_rhythmic_activity', 'Bass rhythm', 'float', 'musical'), FieldSpec('bass_harmonic_strictness', 'Bass strictness', 'float', 'musical'), FieldSpec('drum_intensity', 'Drum intensity', 'float', 'musical'), FieldSpec('drum_fill_probability', 'Drum fills', 'float', 'musical'), FieldSpec('snare_roll_intensity', 'Snare rolls', 'float', 'musical'), FieldSpec('transition_fill_amount', 'Transition fills', 'float', 'musical'), FieldSpec('breakdown_sparsity', 'Breakdown sparsity', 'float', 'musical'), FieldSpec('drop_density', 'Drop density', 'float', 'musical'))
FIELD_GROUPS: Tuple[FieldGroup, ...] = (FieldGroup('harmony', 'Harmonic seeds', 'Which of the sixteen modal worlds this run explores, and how they are voiced.', HARMONY_FIELDS), FieldGroup('variation', 'Variation', 'The rhythmic axis, and how far the search may roam from the values written in this project.', VARIATION_FIELDS), FieldGroup('ca', 'Cellular automaton', 'The deterministic time grid behind activation, accents and texture.', CA_FIELDS), FieldGroup('lsystem', 'L-system', 'The symbolic melodic material the lead motifs are built from.', LSYSTEM_FIELDS), FieldGroup('ga', 'Genetic algorithm', 'Selection pressure, mutation and novelty.', GA_FIELDS), FieldGroup('musical', 'Musical shaping', 'Per-layer density, variation and arrangement dynamics.', MUSICAL_FIELDS))
ALL_FIELDS: Tuple[FieldSpec, ...] = tuple((spec for group in FIELD_GROUPS for spec in group.fields))
FIELDS_BY_KEY: Dict[str, FieldSpec] = {spec.key: spec for spec in ALL_FIELDS}

def preset_project(template: str='classic_trance') -> OriProject:
    return load_ori(example_path(template))

def example_path(template: str) -> Path:
    if template not in VALID_ARRANGEMENT_TEMPLATES:
        raise ValueError(f'Unknown preset: {template}')
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))
    return base / 'examples' / f'{template}.ori'

def project_to_section_dicts(project: OriProject) -> List[Dict[str, Any]]:
    return [asdict(section) for section in project.sections]

def project_to_gui_state(project: OriProject) -> Dict[str, Any]:
    harmony = project.harmony
    state: Dict[str, Any] = {'title': project.title, 'genre': project.genre, 'generation_length_seconds': display_number(project.parameters.generation_length_seconds), 'bpm': str(project.parameters.bpm), 'key': project.parameters.key, 'scale': project.parameters.scale, 'seed': '' if project.parameters.seed is None else str(project.parameters.seed), 'candidates': str(project.parameters.candidates), 'generations': str(project.parameters.generations), 'enable_riffs': project.parameters.enable_riffs, 'enable_bass': project.parameters.enable_bass, 'enable_drums': project.parameters.enable_drums, 'enable_pads': project.parameters.enable_pads, 'seed_pool': list(harmony.seed_pool), 'groove_pool': list(project.variation.groove_pool), 'sections': project_to_section_dicts(project)}
    sources = {'harmony': harmony, 'variation': project.variation, 'ca': project.ca, 'lsystem': project.lsystem, 'ga': project.ga, 'musical': project.musical}
    for spec in ALL_FIELDS:
        source = sources[spec.section]
        value = getattr(source, _attribute_for(spec), None)
        state[spec.key] = _display_value(spec, value)
    return state

def gui_state_to_project(values: Dict[str, Any], sections: Sequence[Dict[str, Any]]) -> OriProject:
    data: Dict[str, Any] = {'format': 'oriondrive-ori', 'version': 3, 'title': values.get('title'), 'genre': values.get('genre'), 'parameters': {'generation_length_seconds': parse_float(values.get('generation_length_seconds'), 'Generation length'), 'bpm': parse_int(values.get('bpm'), 'BPM'), 'key': values.get('key'), 'scale': values.get('scale'), 'seed': None if not str(values.get('seed') or '').strip() else parse_int(values.get('seed'), 'Seed'), 'candidates': parse_int(values.get('candidates'), 'Candidates'), 'generations': parse_int(values.get('generations'), 'Generations'), 'enable_riffs': bool(values.get('enable_riffs')), 'enable_bass': bool(values.get('enable_bass')), 'enable_drums': bool(values.get('enable_drums')), 'enable_pads': bool(values.get('enable_pads'))}, 'harmony': {'seed_pool': list(values.get('seed_pool') or VALID_SEED_NAMES)}, 'variation': {'groove_pool': list(values.get('groove_pool') or VALID_GROOVE_NAMES)}, 'ca': {}, 'lsystem': {}, 'ga': {'candidates': parse_int(values.get('candidates'), 'Candidates'), 'generations': parse_int(values.get('generations'), 'Generations')}, 'musical': {}, 'sections': [dict(section) for section in sections]}
    for spec in ALL_FIELDS:
        parsed = _parse_value(spec, values.get(spec.key))
        if parsed is _OMIT:
            continue
        data[spec.section][_attribute_for(spec)] = parsed
    return project_from_dict(data, source='Oriondrive')

def seed_display_rows(genre: str, pool: Sequence[str]) -> List[Dict[str, Any]]:
    from ..harmonic_seeds import default_seed_pool
    included = set(pool)
    rows: List[Dict[str, Any]] = []
    for name in default_seed_pool(genre):
        seed = HARMONIC_SEEDS[name]
        rows.append({'name': name, 'label': seed.label, 'summary': seed.summary, 'mode': seed.mode, 'progression': ' | '.join((chord.label for chord in seed.progression)), 'cadence': seed.cadence_kind, 'pedal': seed.pedal, 'included': name in included})
    return rows

def groove_display_rows(genre: str, pool: Sequence[str]) -> List[Dict[str, Any]]:
    from ..grooves import default_groove_pool
    included = set(pool)
    rows: List[Dict[str, Any]] = []
    for name in default_groove_pool(genre):
        groove = GROOVES[name]
        rows.append({'name': name, 'label': groove.label, 'summary': groove.summary, 'bass': groove.bass_style, 'kick': ', '.join((f'{beat:g}' for beat in groove.kick_cell)) or 'none', 'hats': f'1/{int(round(1 / groove.hat_step))}' if groove.hat_step else '-', 'included': name in included})
    return rows

def groove_detail_text(name: str) -> str:
    if name == AUTO_GROOVE or name not in GROOVES:
        return 'Auto pairs each harmonic seed with a different groove, so two variations differ in surface rhythm as well as in chord field. Pin one to hear every seed over the same beat.'
    groove = get_groove(name)
    return '\n'.join([groove.label, groove.summary, '', f'Bass: {groove.bass_style}, step {groove.bass_step:g}', f"Kick: {', '.join((f'{beat:g}' for beat in groove.kick_cell)) or 'none'}", f"Snare/clap: {', '.join((f'{beat:g}' for beat in groove.snare_cell)) or 'none'}", f'Hats: every {groove.hat_step:g} beat from {groove.hat_offset:g}' + (f', swing {groove.swing:.2f}' if groove.swing else ''), f'Lead cells: {len(groove.lead_cells)}, riff onsets per bar: {len(groove.riff_cell)}', f'Tempo bias: {groove.tempo_bias:+d} BPM'])

def seed_detail_text(name: str) -> str:
    if name == AUTO_SEED or name not in HARMONIC_SEEDS:
        return 'Auto explores every seed in the pool at once. The population is split into one species per seed, each species keeps its own elite for the whole run, and the result is one finished arrangement per seed.'
    seed = get_harmonic_seed(name)
    lines = [seed.label, seed.summary, '', f'Mode: {seed.mode}', f"Chord field: {' | '.join((chord.label for chord in seed.progression))}", f'Cadence: {seed.cadence_chord.label} ({seed.cadence_kind}), every {seed.cadence_every} chords', f"Bass: {('tonic pedal' if seed.pedal else 'moving')}", f'Harmonic rhythm: {seed.harmonic_rhythm_bars} bars per chord, pedal held {seed.pedal_bars} bars', f'Voicing: openness {seed.voicing_openness:.2f}, suspension {seed.suspension:.2f}, max inner-voice motion {seed.max_voice_motion}']
    return '\n'.join(lines)

def new_section() -> Dict[str, Any]:
    return {'name': 'New Section', 'length_bars': 8, 'energy': 0.5, 'lead_role': 'fragments', 'riff_role': 'repeating', 'bass_role': 'pulse', 'drum_role': 'groove', 'pad_role': 'chorale'}

def default_project_filename(title: str) -> str:
    slug = ''.join((char.lower() if char.isalnum() else '_' for char in title)).strip('_') or 'oriondrive'
    return f'{slug}.ori'

def display_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)

def parse_int(value: Any, label: str) -> int:
    try:
        return int(str(value).strip())
    except ValueError as exc:
        raise ValueError(f'{label} must be an integer.') from exc

def parse_float(value: Any, label: str) -> float:
    try:
        return float(str(value).strip())
    except ValueError as exc:
        raise ValueError(f'{label} must be a number.') from exc

class _Omit:
    pass
_OMIT = _Omit()

def _attribute_for(spec: FieldSpec) -> str:
    renames = {'ca_rule': 'rule', 'ca_width': 'width', 'ca_steps': 'steps', 'ca_seed_density': 'seed_density', 'ca_wrap_edges': 'wrap_edges', 'lsystem_rule_set': 'rule_set', 'lsystem_iterations': 'iterations'}
    return renames.get(spec.key, spec.key)

def _display_value(spec: FieldSpec, value: Any) -> Any:
    if spec.kind == 'bool':
        return bool(value)
    if value is None:
        return ''
    if spec.kind == 'choice':
        return str(value)
    if spec.is_numeric:
        return display_number(value)
    return str(value)

def _parse_value(spec: FieldSpec, raw: Any) -> Any:
    if spec.kind == 'bool':
        return bool(raw)
    text = str(raw if raw is not None else '').strip()
    if not text:
        if spec.optional:
            return None
        return _OMIT
    if spec.kind == 'int':
        return parse_int(text, spec.label)
    if spec.kind == 'float':
        return parse_float(text, spec.label)
    return text
