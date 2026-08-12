from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Sequence, Tuple
VALID_GROOVE_NAMES: Tuple[str, ...] = ('four_on_floor', 'offbeat_pulse', 'machine_gallop', 'broken_syncopation', 'triplet_swing', 'sequencer_drift', 'half_time_sparse', 'polymetric_five')
AUTO_GROOVE = 'auto'
BEATS_PER_BAR = 4.0
BEATS_PER_PHRASE = 8.0

@dataclass(frozen=True)
class GrooveProfile:
    name: str
    label: str
    summary: str
    lead_cells: Tuple[Tuple[float, ...], ...]
    lead_note_length: float = 0.42
    riff_cell: Tuple[float, ...] = (0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5)
    riff_note_length: float = 0.16
    bass_style: str = 'pulse'
    bass_step: float = 0.5
    bass_note_length: float = 0.34
    kick_cell: Tuple[float, ...] = (0.0, 1.0, 2.0, 3.0)
    snare_cell: Tuple[float, ...] = (1.0, 3.0)
    hat_step: float = 0.5
    hat_offset: float = 0.5
    ride_instead_of_hat: bool = False
    swing: float = 0.0
    tempo_bias: int = 0
    accent_every: int = 4
    genre_affinity: Mapping[str, float] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.lead_cells:
            raise ValueError(f"Groove '{self.name}' needs at least one lead cell.")
        if self.bass_step <= 0 or self.hat_step <= 0:
            raise ValueError(f"Groove '{self.name}' step sizes must be positive.")
        if not 0.0 <= self.swing < 0.5:
            raise ValueError(f"Groove '{self.name}' swing must be in [0.0, 0.5).")

    def affinity(self, genre: str) -> float:
        return float(self.genre_affinity.get(genre, 0.5))

    def swung(self, beat: float) -> float:
        if self.swing <= 0.0:
            return beat
        index = int(round(beat / self.hat_step))
        return beat + (self.swing * self.hat_step if index % 2 else 0.0)

    def lead_cell_for_phrase(self, phrase: int) -> Tuple[float, ...]:
        return self.lead_cells[phrase % len(self.lead_cells)]

    def bar_grid(self, step: float, bars: int=1) -> List[float]:
        total = BEATS_PER_BAR * bars
        onsets: List[float] = []
        beat = 0.0
        while beat < total - 1e-06:
            onsets.append(round(self.swung(beat), 4))
            beat += step
        return onsets

def _groove_registry() -> Dict[str, GrooveProfile]:
    grooves = (GrooveProfile(name='four_on_floor', label='Four On The Floor', summary='Kick on every beat, offbeat hats, continuous sixteenth riff. The default trance surface.', lead_cells=((0.0, 0.5, 1.0, 1.5, 2.5, 3.0, 4.0, 5.0, 6.5), (0.0, 0.75, 1.5, 2.0, 3.0, 4.0, 5.5, 6.0)), riff_cell=(0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5), riff_note_length=0.16, bass_style='offbeat', bass_step=0.5, kick_cell=(0.0, 1.0, 2.0, 3.0), snare_cell=(1.0, 3.0), hat_step=0.5, hat_offset=0.5, genre_affinity={'classic_trance': 1.0, 'ebm': 0.8, 'berlin_school': 0.3}), GrooveProfile(name='offbeat_pulse', label='Offbeat Pulse', summary='Kick on one and three, everything else pushed off the beat. Lighter, more suspended.', lead_cells=((0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 7.0), (0.0, 1.5, 2.5, 4.0, 5.5, 6.5)), lead_note_length=0.5, riff_cell=(0.5, 1.0, 1.5, 2.5, 3.0, 3.5), riff_note_length=0.2, bass_style='pulse', bass_step=1.0, kick_cell=(0.0, 2.0), snare_cell=(1.0, 3.0), hat_step=0.5, hat_offset=0.5, genre_affinity={'classic_trance': 0.8, 'ebm': 0.6, 'berlin_school': 0.7}), GrooveProfile(name='machine_gallop', label='Machine Gallop', summary='Sixteenth-note gallop bass under a rigid body-music kick. Tight and mechanical.', lead_cells=((0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0), (0.0, 0.5, 1.5, 2.5, 3.0, 4.0, 5.0, 7.0)), lead_note_length=0.3, riff_cell=(0.0, 0.25, 0.75, 1.0, 1.25, 1.75, 2.0, 2.25, 2.75, 3.0, 3.25, 3.75), riff_note_length=0.12, bass_style='gallop', bass_step=0.25, bass_note_length=0.2, kick_cell=(0.0, 0.75, 2.0, 2.75), snare_cell=(1.0, 3.0), hat_step=0.25, hat_offset=0.0, tempo_bias=-4, genre_affinity={'classic_trance': 0.6, 'ebm': 1.0, 'berlin_school': 0.4}), GrooveProfile(name='broken_syncopation', label='Broken Syncopation', summary='Dotted-eighth phrasing across the bar line, so the pattern lands differently each bar.', lead_cells=((0.0, 0.75, 1.5, 2.25, 3.0, 3.75, 4.5, 5.25, 6.0, 7.5), (0.0, 0.75, 1.5, 3.0, 3.75, 5.25, 6.0, 6.75)), lead_note_length=0.36, riff_cell=(0.0, 0.75, 1.5, 2.25, 3.0, 3.75), riff_note_length=0.18, bass_style='stab', bass_step=0.75, kick_cell=(0.0, 1.5, 2.0, 3.5), snare_cell=(1.0, 3.0), hat_step=0.25, hat_offset=0.25, genre_affinity={'classic_trance': 0.7, 'ebm': 0.9, 'berlin_school': 0.6}), GrooveProfile(name='triplet_swing', label='Triplet Swing', summary='A shuffled twelve-eight feel. The same chords stop marching and start leaning.', lead_cells=((0.0, 0.667, 1.333, 2.0, 2.667, 4.0, 4.667, 6.0, 6.667), (0.0, 1.333, 2.0, 3.333, 4.0, 5.333, 6.0, 7.333)), lead_note_length=0.44, riff_cell=(0.0, 0.667, 1.333, 2.0, 2.667, 3.333), riff_note_length=0.22, bass_style='walking', bass_step=0.667, bass_note_length=0.4, kick_cell=(0.0, 1.333, 2.0, 3.333), snare_cell=(1.0, 3.0), hat_step=0.667, hat_offset=0.667, ride_instead_of_hat=True, swing=0.12, tempo_bias=-6, genre_affinity={'classic_trance': 0.5, 'ebm': 0.5, 'berlin_school': 0.9}), GrooveProfile(name='sequencer_drift', label='Sequencer Drift', summary='Unbroken sixteenths with no kick emphasis. The sequencer carries the pulse instead of the drums.', lead_cells=((0.0, 0.75, 1.5, 2.25, 3.0, 4.5, 6.0, 7.5), (0.0, 1.0, 1.75, 2.5, 4.0, 5.25, 6.5, 7.25), (0.0, 0.5, 1.25, 2.0, 3.5, 4.25, 5.75, 7.0)), lead_note_length=0.5, riff_cell=(0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 3.25, 3.5, 3.75), riff_note_length=0.14, bass_style='drone', bass_step=2.0, bass_note_length=1.6, kick_cell=(0.0,), snare_cell=(), hat_step=0.25, hat_offset=0.0, tempo_bias=-8, accent_every=8, genre_affinity={'classic_trance': 0.4, 'ebm': 0.5, 'berlin_school': 1.0}), GrooveProfile(name='half_time_sparse', label='Half-Time Sparse', summary='Half the drum events, twice the note lengths. Space becomes the main texture.', lead_cells=((0.0, 2.0, 3.0, 4.0, 6.0), (0.0, 1.5, 4.0, 5.0, 6.5)), lead_note_length=0.9, riff_cell=(0.0, 1.0, 2.0, 3.0), riff_note_length=0.4, bass_style='drone', bass_step=2.0, bass_note_length=1.8, kick_cell=(0.0, 2.5), snare_cell=(2.0,), hat_step=1.0, hat_offset=0.5, tempo_bias=-6, accent_every=8, genre_affinity={'classic_trance': 0.5, 'ebm': 0.4, 'berlin_school': 0.9}), GrooveProfile(name='polymetric_five', label='Polymetric Five', summary='A five-beat riff cycle turning over a four-beat drum grid, so the pattern realigns every five bars.', lead_cells=((0.0, 1.25, 2.5, 3.75, 5.0, 6.25, 7.5), (0.0, 0.625, 1.875, 2.5, 3.75, 5.0, 6.25)), lead_note_length=0.4, riff_cell=(0.0, 0.8, 1.6, 2.4, 3.2), riff_note_length=0.2, bass_style='pulse', bass_step=0.8, kick_cell=(0.0, 1.0, 2.0, 3.0), snare_cell=(1.0, 3.0), hat_step=0.5, hat_offset=0.25, genre_affinity={'classic_trance': 0.5, 'ebm': 0.7, 'berlin_school': 0.8}))
    for groove in grooves:
        groove.validate()
    return {groove.name: groove for groove in grooves}
GROOVES: Dict[str, GrooveProfile] = _groove_registry()

def available_grooves() -> List[str]:
    return list(VALID_GROOVE_NAMES)

def get_groove(name: str) -> GrooveProfile:
    if name not in GROOVES:
        choices = ', '.join(available_grooves())
        raise ValueError(f"Unknown groove '{name}'. Choose one of: {choices}.")
    return GROOVES[name]

def validate_groove_pool(pool: Sequence[str]) -> List[str]:
    if not pool:
        raise ValueError('A groove pool must contain at least one groove.')
    unknown = [name for name in pool if name not in GROOVES]
    if unknown:
        choices = ', '.join(available_grooves())
        raise ValueError(f"Unknown grooves: {', '.join(unknown)}. Choose from: {choices}.")
    return [name for name in VALID_GROOVE_NAMES if name in set(pool)]

def default_groove_pool(genre: str) -> List[str]:
    return sorted(VALID_GROOVE_NAMES, key=lambda name: (-GROOVES[name].affinity(genre), VALID_GROOVE_NAMES.index(name)))

def groove_allocation(pool: Sequence[str], population_size: int, genre: str='classic_trance') -> List[str]:
    ordered = validate_groove_pool(pool)
    if population_size <= 0:
        return []
    ranked = sorted(ordered, key=lambda name: (-GROOVES[name].affinity(genre), ordered.index(name)))
    stride = 3 if len(ranked) % 3 else 5
    if len(ranked) % stride == 0:
        stride = 1
    return [ranked[index * stride % len(ranked)] for index in range(population_size)]

def groove_summary_rows(genre: str='classic_trance') -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for name in default_groove_pool(genre):
        groove = GROOVES[name]
        rows.append({'name': groove.name, 'label': groove.label, 'summary': groove.summary, 'bass_style': groove.bass_style, 'hat_step': groove.hat_step, 'swing': groove.swing, 'kick': ', '.join((f'{beat:g}' for beat in groove.kick_cell)) or 'none', 'affinity': round(groove.affinity(genre), 2)})
    return rows
