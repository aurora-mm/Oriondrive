from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional
BEATS_PER_BAR = 4
DEFAULT_BARS_PER_LOOP = 8
VALID_ARRANGEMENT_TEMPLATES = ('classic_trance', 'ebm', 'berlin_school')
PAD_ROLES = ('off', 'pedal', 'soft', 'chorale', 'air', 'full')

@dataclass(frozen=True)
class ArrangementSectionSpec:
    name: str
    length_bars: int
    energy: float
    lead_role: str
    riff_role: str
    bass_role: str
    drum_role: str
    pad_role: str = ''

@dataclass(frozen=True)
class ArrangementSection:
    name: str
    start_bar: int
    length_bars: int
    energy: float
    lead_role: str
    riff_role: str
    bass_role: str
    drum_role: str
    pad_role: str = 'chorale'

    @property
    def end_bar(self) -> int:
        return self.start_bar + self.length_bars

    @property
    def start_beat(self) -> float:
        return float(self.start_bar * BEATS_PER_BAR)

    @property
    def end_beat(self) -> float:
        return float(self.end_bar * BEATS_PER_BAR)

@dataclass(frozen=True)
class LoopBlock:
    index: int
    start_bar: int
    section_name: str
    section_loop_index: int
    energy: float
    length_bars: int = DEFAULT_BARS_PER_LOOP

    @property
    def start_beat(self) -> float:
        return float(self.start_bar * BEATS_PER_BAR)

    @property
    def end_bar(self) -> int:
        return self.start_bar + self.length_bars

    @property
    def end_beat(self) -> float:
        return float(self.end_bar * BEATS_PER_BAR)

class Arrangement:

    def __init__(self, sections: Iterable[ArrangementSection], bars_per_loop: int=DEFAULT_BARS_PER_LOOP, genre: str='classic_trance', template: Optional[str]=None):
        self.sections = list(sections)
        self.bars_per_loop = bars_per_loop
        self.genre = genre
        self.template = template or genre
        self._validate()

    def _validate(self) -> None:
        if self.bars_per_loop <= 0:
            raise ValueError('bars_per_loop must be positive.')
        if self.bars_per_loop != DEFAULT_BARS_PER_LOOP:
            raise ValueError('bars_per_loop must be 8 for the current Oriondrive loop generators.')
        if not self.sections:
            raise ValueError('Arrangement requires at least one section.')
        expected_start = 0
        for index, section in enumerate(self.sections):
            if not section.name.strip():
                raise ValueError(f'Section {index + 1} must have a non-empty name.')
            if section.start_bar != expected_start:
                raise ValueError(f"Section '{section.name}' starts at bar {section.start_bar}, but bar {expected_start} was expected.")
            if section.length_bars <= 0:
                raise ValueError(f"Section '{section.name}' length_bars must be positive.")
            if section.length_bars % self.bars_per_loop != 0:
                raise ValueError(f"Section '{section.name}' length_bars={section.length_bars} must be a multiple of bars_per_loop={self.bars_per_loop}.")
            if section.energy < 0.0 or section.energy > 1.0:
                raise ValueError(f"Section '{section.name}' energy must be between 0.0 and 1.0.")
            expected_start = section.end_bar

    @property
    def total_bars(self) -> int:
        return max((section.end_bar for section in self.sections))

    @property
    def total_beats(self) -> int:
        return self.total_bars * BEATS_PER_BAR

    @property
    def loop_count(self) -> int:
        return self.total_bars // self.bars_per_loop

    @property
    def section_names(self) -> List[str]:
        return [section.name for section in self.sections]

    def loop_blocks(self) -> List[LoopBlock]:
        blocks: List[LoopBlock] = []
        absolute_index = 0
        for section in self.sections:
            for local_index, start_bar in enumerate(range(section.start_bar, section.end_bar, self.bars_per_loop)):
                blocks.append(LoopBlock(index=absolute_index, start_bar=start_bar, section_name=section.name, section_loop_index=local_index, energy=section.energy, length_bars=self.bars_per_loop))
                absolute_index += 1
        return blocks

    def section_for_bar(self, bar: int) -> ArrangementSection:
        for section in self.sections:
            if section.start_bar <= bar < section.end_bar:
                return section
        return self.sections[-1]

    def loop_block_index_for_bar(self, bar: int) -> int:
        return max(0, min(self.loop_count - 1, bar // self.bars_per_loop))

    def section_start_end_bars(self) -> Dict[str, tuple[int, int]]:
        return {section.name: (section.start_bar, section.end_bar) for section in self.sections}

    def active_layers_for_section(self, section_name: str, riffs_enabled: bool, bass_enabled: bool, drums_enabled: bool, pads_enabled: bool=True) -> Dict[str, bool]:
        section = self.section_by_name(section_name)
        return {'leads': section.lead_role != 'off', 'riffs': riffs_enabled and section.riff_role != 'off', 'bass': bass_enabled and section.bass_role != 'off', 'drums': drums_enabled and section.drum_role != 'off', 'pads': pads_enabled and section.pad_role != 'off'}

    def section_by_name(self, name: str) -> ArrangementSection:
        for section in self.sections:
            if section.name == name:
                return section
        raise KeyError(f'Unknown arrangement section: {name}')

    def energy_curve(self) -> List[float]:
        return [section.energy for section in self.sections for _ in range(section.length_bars)]

    def section_energy_curve(self) -> tuple[float, ...]:
        return tuple((section.energy for section in self.sections))

    def riff_density_curve(self) -> tuple[float, ...]:
        return tuple((_role_density(section.riff_role, section.energy) for section in self.sections))

    def bass_activity_curve(self) -> tuple[float, ...]:
        return tuple((_role_density(section.bass_role, section.energy) for section in self.sections))

    def phrase_boundaries(self) -> List[int]:
        boundaries = set(range(0, self.total_bars + 1, 2))
        boundaries.update(range(0, self.total_bars + 1, self.bars_per_loop))
        boundaries.update((section.start_bar for section in self.sections))
        boundaries.update((section.end_bar for section in self.sections))
        return sorted((boundary for boundary in boundaries if 0 <= boundary <= self.total_bars))

    def cadence_points(self) -> List[int]:
        cadences = set(range(self.bars_per_loop, self.total_bars + 1, self.bars_per_loop))
        cadences.update((section.end_bar for section in self.sections))
        return sorted((cadence for cadence in cadences if 0 < cadence <= self.total_bars))

    def transition_bars(self) -> List[int]:
        return [section.start_bar for section in self.sections[1:]]

    def pad_density_curve(self) -> tuple[float, ...]:
        return tuple((_role_density(section.pad_role, section.energy) for section in self.sections))

    def to_structure_map(self, riffs_enabled: bool=False, bass_enabled: bool=False, drums_enabled: bool=True, pads_enabled: bool=True) -> Dict[str, object]:
        return {'genre': self.genre, 'style': self.genre, 'arrangement_template': self.template, 'bars_per_loop': self.bars_per_loop, 'beats_per_bar': BEATS_PER_BAR, 'total_bars': self.total_bars, 'total_beats': self.total_beats, 'loop_count': self.loop_count, 'sections': [section.__dict__ | {'end_bar': section.end_bar} for section in self.sections], 'section_bars': self.section_start_end_bars(), 'loop_blocks': [block.__dict__ | {'end_bar': block.end_bar} for block in self.loop_blocks()], 'energy_curve': self.energy_curve(), 'section_energy_curve': self.section_energy_curve(), 'phrase_boundaries': self.phrase_boundaries(), 'cadence_points': self.cadence_points(), 'transition_bars': self.transition_bars(), 'active_layers': {section.name: self.active_layers_for_section(section.name, riffs_enabled, bass_enabled, drums_enabled, pads_enabled) for section in self.sections}}

def arrangement_from_sections(sections: Iterable[ArrangementSectionSpec | Mapping[str, Any] | Any], bars_per_loop: int=DEFAULT_BARS_PER_LOOP, genre: str='custom', template: Optional[str]='custom') -> Arrangement:
    arrangement_sections: List[ArrangementSection] = []
    start_bar = 0
    for index, raw in enumerate(sections):
        spec = _coerce_section_spec(raw, index)
        arrangement_sections.append(ArrangementSection(name=spec.name, start_bar=start_bar, length_bars=spec.length_bars, energy=spec.energy, lead_role=spec.lead_role, riff_role=spec.riff_role, bass_role=spec.bass_role, drum_role=spec.drum_role, pad_role=spec.pad_role or default_pad_role(spec.lead_role, spec.energy)))
        start_bar += spec.length_bars
    return Arrangement(arrangement_sections, bars_per_loop=bars_per_loop, genre=genre, template=template)

def arrangement_from_ori_project(project: Any, bars_per_loop: int=DEFAULT_BARS_PER_LOOP) -> Arrangement:
    genre = str(getattr(project, 'genre', 'custom'))
    title = str(getattr(project, 'title', 'custom'))
    return arrangement_from_sections(getattr(project, 'sections'), bars_per_loop=bars_per_loop, genre=genre, template=title)

def classic_trance_arrangement(bars_per_loop: int=DEFAULT_BARS_PER_LOOP) -> Arrangement:
    return arrangement_from_template('classic_trance', bars_per_loop=bars_per_loop)

def arrangement_from_template(template: str='classic_trance', bars_per_loop: int=DEFAULT_BARS_PER_LOOP) -> Arrangement:
    if template not in VALID_ARRANGEMENT_TEMPLATES:
        choices = ', '.join(VALID_ARRANGEMENT_TEMPLATES)
        raise ValueError(f"Unknown arrangement template '{template}'. Choose one of: {choices}.")
    return arrangement_from_sections(_template_specs(template), bars_per_loop=bars_per_loop, genre=template, template=template)

def default_pad_role(lead_role: str, energy: float) -> str:
    if lead_role in {'breakdown', 'variation_sparse'}:
        return 'air'
    if lead_role == 'echo':
        return 'soft'
    if energy < 0.25:
        return 'pedal'
    if energy < 0.5:
        return 'soft'
    if energy < 0.8:
        return 'chorale'
    return 'full'

def _coerce_section_spec(raw: ArrangementSectionSpec | Mapping[str, Any] | Any, index: int) -> ArrangementSectionSpec:
    if isinstance(raw, ArrangementSectionSpec):
        spec = raw
    elif isinstance(raw, Mapping):
        spec = ArrangementSectionSpec(name=str(raw.get('name', '')), length_bars=int(raw.get('length_bars', 0)), energy=float(raw.get('energy', 0.0)), lead_role=str(raw.get('lead_role', 'off')), riff_role=str(raw.get('riff_role', 'off')), bass_role=str(raw.get('bass_role', 'off')), drum_role=str(raw.get('drum_role', 'off')), pad_role=str(raw.get('pad_role', '') or ''))
    else:
        spec = ArrangementSectionSpec(name=str(getattr(raw, 'name')), length_bars=int(getattr(raw, 'length_bars')), energy=float(getattr(raw, 'energy')), lead_role=str(getattr(raw, 'lead_role')), riff_role=str(getattr(raw, 'riff_role')), bass_role=str(getattr(raw, 'bass_role')), drum_role=str(getattr(raw, 'drum_role')), pad_role=str(getattr(raw, 'pad_role', '') or ''))
    if not spec.name.strip():
        raise ValueError(f'Section {index + 1} must have a non-empty name.')
    return spec

def _role_density(role: str, energy: float) -> float:
    role_defaults = {'off': 0.0, 'minimal': 0.22, 'sparse': 0.22, 'pedal': 0.2, 'air': 0.3, 'soft': 0.42, 'chorale': 0.7, 'teaser': 0.28, 'hints': 0.36, 'muted': 0.4, 'pulse': 0.45, 'echo': 0.34, 'fade': 0.3, 'atmospheric': 0.34, 'reduced': 0.38, 'breakdown': 0.4, 'fragments': 0.55, 'repeating': 0.62, 'active': 0.66, 'groove': 0.66, 'compressed': 0.74, 'rising': 0.76, 'tension': 0.78, 'snare_roll': 0.8, 'full': 0.92, 'full_hook': 0.92, 'rolling': 0.92, 'full_variation': 0.95, 'final_hook': 0.96, 'outro': 0.36, 'variation_sparse': 0.36}
    return max(0.0, min(1.0, role_defaults.get(role, energy)))

def _template_specs(template: str) -> List[ArrangementSectionSpec]:
    specs_by_template = {'classic_trance': [('Intro', 16, 0.22, 'teaser', 'off', 'minimal', 'sparse', 'pedal'), ('Early Groove / Buildup', 16, 0.42, 'hints', 'muted', 'pulse', 'groove', 'soft'), ('Main Buildup', 16, 0.58, 'fragments', 'repeating', 'active', 'buildup', 'chorale'), ('Breakdown', 16, 0.32, 'breakdown', 'atmospheric', 'off', 'reduced', 'air'), ('Pre-Drop Build', 8, 0.78, 'compressed', 'rising', 'tension', 'snare_roll', 'chorale'), ('Climax / Drop', 32, 0.97, 'full_hook', 'full', 'rolling', 'full', 'full'), ('Second Breakdown', 16, 0.38, 'variation_sparse', 'echo', 'minimal', 'reduced', 'air'), ('Final Climax', 32, 1.0, 'final_hook', 'full_variation', 'rolling', 'full', 'full'), ('Outro', 16, 0.26, 'echo', 'fade', 'minimal', 'outro', 'pedal')], 'ebm': [('Machine Intro', 8, 0.35, 'teaser', 'muted', 'pulse', 'sparse', 'pedal'), ('Verse / Command A', 16, 0.62, 'fragments', 'repeating', 'active', 'groove', 'soft'), ('Body Chorus A', 8, 0.84, 'full_hook', 'full', 'rolling', 'full', 'chorale'), ('Verse / Command B', 16, 0.68, 'fragments', 'repeating', 'active', 'groove', 'soft'), ('Factory Bridge', 8, 0.5, 'breakdown', 'atmospheric', 'pulse', 'reduced', 'air'), ('Body Chorus B', 8, 0.88, 'full_hook', 'full_variation', 'rolling', 'full', 'chorale'), ('Industrial Breakdown', 8, 0.42, 'variation_sparse', 'echo', 'minimal', 'reduced', 'air'), ('Final Body', 16, 0.96, 'final_hook', 'full_variation', 'rolling', 'full', 'full'), ('Hard Stop Outro', 8, 0.28, 'echo', 'fade', 'minimal', 'outro', 'pedal')], 'berlin_school': [('Drone / Tape Echo Opening', 16, 0.18, 'teaser', 'atmospheric', 'off', 'off', 'pedal'), ('Sequencer Fade-In', 16, 0.34, 'hints', 'muted', 'pulse', 'off', 'soft'), ('Primary Sequence Evolution', 32, 0.52, 'fragments', 'repeating', 'active', 'off', 'chorale'), ('Filter Motion / Harmonic Drift', 32, 0.62, 'compressed', 'rising', 'tension', 'off', 'chorale'), ('Space Lead Improvisation', 32, 0.7, 'full_hook', 'atmospheric', 'rolling', 'off', 'air'), ('Drone Break / Reset', 16, 0.26, 'breakdown', 'echo', 'minimal', 'off', 'pedal'), ('Second Sequencer Layer', 32, 0.76, 'variation_sparse', 'full', 'rolling', 'off', 'chorale'), ('Polyrhythmic Climax', 32, 0.9, 'final_hook', 'full_variation', 'rolling', 'off', 'full'), ('Dissolve / Echo Outro', 16, 0.2, 'echo', 'fade', 'minimal', 'off', 'air')]}
    return [ArrangementSectionSpec(*values) for values in specs_by_template[template]]
