from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple
from .arrangement import Arrangement, BEATS_PER_BAR
from .config import build_scale_pitches, clamp, root_pitch_class
from .harmonic_seeds import HarmonicSeed, get_harmonic_seed
PHRASES_PER_LOOP = 4
BEATS_PER_PHRASE = 8.0

@dataclass(frozen=True)
class ChordSlot:
    index: int
    start_bar: int
    length_bars: int
    label: str
    root_pitch_class: int
    bass_pitch_class: int
    pitch_classes: Tuple[int, ...]
    is_cadence: bool
    section_name: str

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
class PadVoicing:
    slot: ChordSlot
    bass: int
    body: Tuple[int, ...]
    air: Tuple[int, ...]

    @property
    def all_pitches(self) -> Tuple[int, ...]:
        return (self.bass,) + self.body + self.air

class HarmonyPlan:

    def __init__(self, seed: HarmonicSeed | str, root_note: str, arrangement: Arrangement, suspension: Optional[float]=None, voicing_openness: Optional[float]=None, harmonic_rhythm_bars: Optional[int]=None, pedal_strength: float=1.0):
        self.seed = seed if isinstance(seed, HarmonicSeed) else get_harmonic_seed(str(seed))
        self.root_note = root_note
        self.tonic_pitch_class = root_pitch_class(root_note)
        self.arrangement = arrangement
        self.suspension = self.seed.suspension if suspension is None else clamp(float(suspension), 0.0, 1.0)
        self.voicing_openness = self.seed.voicing_openness if voicing_openness is None else clamp(float(voicing_openness), 0.0, 1.0)
        self.harmonic_rhythm_bars = int(harmonic_rhythm_bars or self.seed.harmonic_rhythm_bars)
        if self.harmonic_rhythm_bars <= 0:
            raise ValueError('harmonic_rhythm_bars must be positive.')
        self.pedal_strength = clamp(float(pedal_strength), 0.0, 1.0)
        self.slots: List[ChordSlot] = self._build_slots()

    def _build_slots(self) -> List[ChordSlot]:
        slots: List[ChordSlot] = []
        total_bars = self.arrangement.total_bars
        index = 0
        start_bar = 0
        while start_bar < total_bars:
            length = min(self.harmonic_rhythm_bars, total_bars - start_bar)
            chord = self.seed.chord_at(index)
            is_cadence = (index + 1) % self.seed.cadence_every == 0
            pedal_active = self.seed.pedal and self.pedal_strength > 0.0
            bass_offset = chord.sounding_bass_offset(pedal_active)
            slots.append(ChordSlot(index=index, start_bar=start_bar, length_bars=length, label=chord.label, root_pitch_class=(self.tonic_pitch_class + chord.root_offset) % 12, bass_pitch_class=(self.tonic_pitch_class + bass_offset) % 12, pitch_classes=tuple(sorted({(self.tonic_pitch_class + offset) % 12 for offset in chord.pitch_class_offsets(self.suspension)})), is_cadence=is_cadence, section_name=self.arrangement.section_for_bar(start_bar).name))
            index += 1
            start_bar += length
        return slots

    def slot_for_bar(self, bar: int) -> ChordSlot:
        for slot in self.slots:
            if slot.start_bar <= bar < slot.end_bar:
                return slot
        return self.slots[-1]

    def slot_for_beat(self, beat: float) -> ChordSlot:
        return self.slot_for_bar(int(beat // BEATS_PER_BAR))

    def scale_pitches(self, octave_range: Tuple[int, int]) -> List[int]:
        return build_scale_pitches(self.seed.mode, self.root_note, octave_range)

    def harmonic_centers_by_loop(self, octave_range: Tuple[int, int]=(3, 5)) -> List[List[int]]:
        pitches = self.scale_pitches(octave_range)
        low, high = (min(pitches), max(pitches))
        centers: List[List[int]] = []
        bars_per_phrase = max(1, self.arrangement.bars_per_loop // PHRASES_PER_LOOP)
        for block in self.arrangement.loop_blocks():
            block_centers: List[int] = []
            for phrase in range(PHRASES_PER_LOOP):
                bar = block.start_bar + phrase * bars_per_phrase
                slot = self.slot_for_bar(min(bar, self.arrangement.total_bars - 1))
                center = _nearest_pitch_with_class(slot.root_pitch_class, pitches)
                if center is None:
                    center = _chromatic_pitch_with_class(slot.root_pitch_class, low, high)
                block_centers.append(center)
            centers.append(block_centers)
        return centers

    def chord_tones_for_beat(self, beat: float, pitches: Sequence[int]) -> List[int]:
        slot = self.slot_for_beat(beat)
        tones = [pitch for pitch in pitches if pitch % 12 in slot.pitch_classes]
        return tones or list(pitches)

    def cadence_beats(self) -> List[float]:
        return [slot.start_beat for slot in self.slots if slot.is_cadence]

    def pad_voicings(self, register: Optional[Tuple[int, int]]=None, voice_count: int=4) -> List[PadVoicing]:
        low, high = register or self.seed.pad_register
        voice_count = max(2, min(6, voice_count))
        voicings: List[PadVoicing] = []
        previous: Optional[List[int]] = None
        for slot in self.slots:
            bass = _nearest_pitch_with_class(slot.bass_pitch_class, range(max(24, low - 24), low + 1)) or low
            body = _voice_lead(previous, slot.pitch_classes, low, high, voice_count, self.seed.max_voice_motion)
            if self.voicing_openness > 0.5:
                fifth = _nearest_pitch_with_class((slot.bass_pitch_class + 7) % 12, range(bass, bass + 13))
                if fifth is not None and fifth not in body:
                    body = tuple(sorted(set(body) | {fifth}))
            air_low, air_high = self.seed.air_register
            air: Tuple[int, ...] = ()
            if body:
                top = max(body)
                candidate = top + 12
                while candidate < air_low:
                    candidate += 12
                if air_low <= candidate <= air_high:
                    air = (candidate,)
            voicings.append(PadVoicing(slot=slot, bass=bass, body=tuple(body), air=air))
            previous = list(body)
        return voicings

    def describe(self) -> Dict[str, object]:
        return {'harmonic_seed': self.seed.name, 'harmonic_seed_label': self.seed.label, 'mode': self.seed.mode, 'root_note': self.root_note, 'pedal': self.seed.pedal and self.pedal_strength > 0.0, 'cadence_kind': self.seed.cadence_kind, 'harmonic_rhythm_bars': self.harmonic_rhythm_bars, 'suspension': round(self.suspension, 4), 'voicing_openness': round(self.voicing_openness, 4), 'progression': [chord.label for chord in self.seed.progression], 'chord_plan': [{'index': slot.index, 'start_bar': slot.start_bar, 'length_bars': slot.length_bars, 'label': slot.label, 'root_pitch_class': slot.root_pitch_class, 'bass_pitch_class': slot.bass_pitch_class, 'pitch_classes': list(slot.pitch_classes), 'is_cadence': slot.is_cadence, 'section': slot.section_name} for slot in self.slots], 'cadence_beats': self.cadence_beats()}

def harmony_plan_for_genome(genome: object, arrangement: Arrangement) -> HarmonyPlan:
    return HarmonyPlan(seed=str(getattr(genome, 'harmonic_seed', 'aeolian_pedal')), root_note=str(getattr(genome, 'root_note', 'C')), arrangement=arrangement, suspension=float(getattr(genome, 'suspension_amount', 0.6)), voicing_openness=float(getattr(genome, 'voicing_openness', 0.5)), harmonic_rhythm_bars=int(getattr(genome, 'harmonic_rhythm_bars', 2)), pedal_strength=float(getattr(genome, 'pedal_strength', 1.0)))

def _nearest_pitch_with_class(pitch_class: int, candidates: Sequence[int] | range) -> Optional[int]:
    matches = [pitch for pitch in candidates if pitch % 12 == pitch_class % 12]
    if not matches:
        return None
    middle = (min(candidates) + max(candidates)) / 2 if len(candidates) else 60
    return min(matches, key=lambda pitch: abs(pitch - middle))

def _chromatic_pitch_with_class(pitch_class: int, low: int, high: int) -> int:
    middle = (low + high) // 2
    pitch = middle - middle % 12 + pitch_class % 12
    while pitch < low:
        pitch += 12
    while pitch > high and pitch - 12 >= low:
        pitch -= 12
    return int(clamp(pitch, 0, 127))

def _voice_lead(previous: Optional[Sequence[int]], pitch_classes: Sequence[int], low: int, high: int, voice_count: int, max_voice_motion: int) -> Tuple[int, ...]:
    available = [pitch for pitch in range(low, high + 1) if pitch % 12 in set(pitch_classes)]
    if not available:
        return tuple()
    if previous is None:
        return _spread_voicing(available, voice_count)
    limit = max(2, max_voice_motion * 3)
    used: List[int] = []
    for voice in sorted(previous):
        if voice in available and voice not in used:
            used.append(voice)
            continue
        reachable = [pitch for pitch in available if pitch not in used and abs(pitch - voice) <= limit]
        pool = reachable or [pitch for pitch in available if pitch not in used]
        if not pool:
            continue
        used.append(min(pool, key=lambda pitch: (abs(pitch - voice), pitch)))
    while len(used) < voice_count:
        remaining = [pitch for pitch in available if pitch not in used]
        if not remaining:
            break
        used.append(remaining[len(used) % len(remaining)])
    return tuple(sorted(set(used))[:voice_count])

def _spread_voicing(available: Sequence[int], voice_count: int) -> Tuple[int, ...]:
    if len(available) <= voice_count:
        return tuple(available)
    step = (len(available) - 1) / max(1, voice_count - 1)
    return tuple(sorted({available[int(round(index * step))] for index in range(voice_count)}))
