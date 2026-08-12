from __future__ import annotations
import random
from dataclasses import dataclass
from typing import Dict, List
from .arrangement import Arrangement
from .composition import NoteEvent
from .config import clamp, validate_probability
from .grooves import GrooveProfile
KICK = 36
SNARE = 38
CLAP = 39
CLOSED_HAT = 42
OPEN_HAT = 46
CRASH = 49
RIDE = 51
VALID_STEADINESS = ('steady', 'groove', 'free')
MAX_HATS_PER_BAR = 8

@dataclass(frozen=True)
class DrumConfig:
    intensity: float = 0.78
    fill_probability: float = 0.42
    snare_roll_intensity: float = 0.72
    transition_fill_amount: float = 0.45
    groove: GrooveProfile | None = None
    steadiness: str = 'steady'

    def validate(self) -> None:
        validate_probability('drum_intensity', self.intensity)
        validate_probability('drum_fill_probability', self.fill_probability)
        validate_probability('snare_roll_intensity', self.snare_roll_intensity)
        validate_probability('transition_fill_amount', self.transition_fill_amount)
        if self.steadiness not in VALID_STEADINESS:
            raise ValueError(f"drum steadiness must be one of: {', '.join(VALID_STEADINESS)}.")

    def kick_cell(self, sparse: bool=False) -> tuple:
        groove_cell = tuple(self.groove.kick_cell) if self.groove is not None else (0.0, 1.0, 2.0, 3.0)
        if self.steadiness == 'free':
            return groove_cell
        if self.steadiness == 'steady':
            return (0.0, 2.0) if sparse or len(groove_cell) <= 2 else (0.0, 1.0, 2.0, 3.0)
        snapped = sorted({round(onset * 2) / 2 for onset in groove_cell} | {0.0})
        return tuple(snapped)

    def backbeat_cell(self) -> tuple:
        if self.steadiness == 'free':
            return tuple(self.groove.snare_cell) if self.groove is not None else (1.0, 3.0)
        return (1.0, 3.0)

    def hat_step(self) -> float:
        base = self.groove.hat_step if self.groove is not None else 0.5
        if self.steadiness == 'free':
            return base
        return max(0.25, base)

class DrumGenerator:

    def __init__(self, config: DrumConfig):
        self.config = config
        self.config.validate()

    def generate(self, arrangement: Arrangement, rng: random.Random) -> List[NoteEvent]:
        events: List[NoteEvent] = []
        transition_bars = set(arrangement.transition_bars())
        fill_windows: List[tuple[float, float]] = []
        for block in arrangement.loop_blocks():
            section = arrangement.section_by_name(block.section_name)
            role = section.drum_role
            if role == 'off':
                continue
            block_events = self._block_pattern(role, section.energy, rng)
            for event in block_events:
                events.append(NoteEvent(start=block.start_beat + event.start, duration=event.duration, pitch=event.pitch, velocity=event.velocity))
            if block.start_bar in transition_bars:
                events.append(NoteEvent(block.start_beat, 0.25, CRASH, int(clamp(80 + section.energy * 32, 70, 118))))
            last_block = block.index + 1 >= arrangement.loop_count
            wants_fill = role in {'snare_roll', 'buildup'} or (not last_block and rng.random() < self.config.fill_probability * self.config.transition_fill_amount)
            if wants_fill:
                start = block.start_beat + 30.0
                events.extend(self._transition_fill(start, section.energy, rng))
                fill_windows.append((start, block.start_beat + 32.0))
        events = _duck_under_fills(events, fill_windows)
        events = _resolve_collisions(events)
        events = _thin_hats(events)
        events = _humanise(events, rng)
        return sorted(events, key=lambda event: (event.start, event.pitch))

    def _block_pattern(self, role: str, energy: float, rng: random.Random) -> List[NoteEvent]:
        groove = self.config.groove
        events: List[NoteEvent] = []
        if role == 'reduced':
            for bar in range(8):
                if bar in (0, 4):
                    events.append(NoteEvent(bar * 4.0, 0.15, CRASH if bar == 0 else OPEN_HAT, 46 + int(26 * energy)))
                if bar % 2 == 1:
                    events.append(NoteEvent(bar * 4.0 + 2.0, 0.12, CLOSED_HAT, 38 + int(20 * energy)))
            return events
        if role == 'snare_roll':
            events.extend(_kick_pattern(energy * self.config.intensity, bars=8, subdued=True, cell=self.config.kick_cell()))
            events.extend(_offbeat_hats(energy * self.config.intensity, bars=8, sparse=False, groove=groove, step=self.config.hat_step()))
            events.extend(_snare_roll(self.config.snare_roll_intensity, bars=8))
            return events
        thin = role in {'sparse', 'outro'}
        events.extend(_kick_pattern(energy * self.config.intensity, bars=8, subdued=thin, thin=thin, cell=self.config.kick_cell(sparse=thin)))
        events.extend(_offbeat_hats(energy * self.config.intensity, bars=8, sparse=role == 'sparse', groove=groove, step=self.config.hat_step()))
        if role in {'groove', 'buildup', 'full', 'outro'}:
            events.extend(_claps(energy * self.config.intensity, bars=8, every_bar=role != 'sparse', cell=self.config.backbeat_cell()))
        if role in {'buildup', 'full'}:
            events.extend(_closed_hat_drive(energy * self.config.intensity, bars=8, sixteenths=role == 'full', groove=groove, step=self.config.hat_step()))
        if role == 'full':
            events.extend(_ride_pattern(energy * self.config.intensity, bars=8, groove=groove))
        if role == 'outro':
            events = [event for event in events if event.start < 24.0 or event.pitch in {KICK, OPEN_HAT}]
        return events

    def _transition_fill(self, start: float, energy: float, rng: random.Random) -> List[NoteEvent]:
        events: List[NoteEvent] = []
        steps = (0.5, 0.5, 0.25, 0.25, 0.25, 0.25) if energy < 0.75 else (0.5, 0.25, 0.25, 0.25, 0.125, 0.125, 0.125, 0.125)
        beat = 2.0 - sum(steps)
        for index, step in enumerate(steps):
            ramp = index / max(1, len(steps) - 1)
            velocity = int(clamp(52 + ramp * 46 + energy * 18 + rng.randint(-3, 3), 40, 118))
            events.append(NoteEvent(start + beat, min(0.1, step * 0.6), SNARE, velocity))
            beat += step
        return events
CYMBALS = (CRASH, OPEN_HAT, RIDE, CLOSED_HAT)
CYMBAL_PRIORITY = {CRASH: 0, OPEN_HAT: 1, RIDE: 2, CLOSED_HAT: 3}
MAX_SIMULTANEOUS = 3

def _resolve_collisions(events: List[NoteEvent]) -> List[NoteEvent]:
    by_tick: Dict[float, List[NoteEvent]] = {}
    for event in events:
        by_tick.setdefault(round(event.start, 4), []).append(event)
    kept: List[NoteEvent] = []
    for tick in sorted(by_tick):
        group = by_tick[tick]
        cymbals = [event for event in group if event.pitch in CYMBAL_PRIORITY]
        others = [event for event in group if event.pitch not in CYMBAL_PRIORITY]
        if cymbals:
            best = min(cymbals, key=lambda event: CYMBAL_PRIORITY[event.pitch])
            cymbals = [best]
        seen: set[int] = set()
        unique: List[NoteEvent] = []
        for event in others + cymbals:
            if event.pitch in seen:
                continue
            seen.add(event.pitch)
            unique.append(event)
        if len(unique) > MAX_SIMULTANEOUS:
            unique.sort(key=lambda event: -event.velocity)
            unique = unique[:MAX_SIMULTANEOUS]
        kept.extend(unique)
    return kept

def _thin_hats(events: List[NoteEvent]) -> List[NoteEvent]:
    by_bar: Dict[int, List[NoteEvent]] = {}
    for event in events:
        by_bar.setdefault(int(event.start // 4.0), []).append(event)
    kept: List[NoteEvent] = []
    for bar in sorted(by_bar):
        group = by_bar[bar]
        hats = [event for event in group if event.pitch in (CLOSED_HAT, OPEN_HAT, RIDE)]
        rest = [event for event in group if event.pitch not in (CLOSED_HAT, OPEN_HAT, RIDE)]
        if len(hats) > MAX_HATS_PER_BAR:
            hats.sort(key=lambda event: event.start)
            stride = len(hats) / MAX_HATS_PER_BAR
            hats = [hats[int(index * stride)] for index in range(MAX_HATS_PER_BAR)]
        kept.extend(rest + hats)
    return kept

def _duck_under_fills(events: List[NoteEvent], windows: List[tuple[float, float]]) -> List[NoteEvent]:
    if not windows:
        return events
    quiet = {CLOSED_HAT, OPEN_HAT, RIDE, CLAP}
    kept: List[NoteEvent] = []
    for event in events:
        inside = any((start <= event.start < end for start, end in windows))
        if inside and event.pitch in quiet:
            continue
        kept.append(event)
    return kept

def _humanise(events: List[NoteEvent], rng: random.Random) -> List[NoteEvent]:
    shaped: List[NoteEvent] = []
    for event in events:
        position = round(event.start % 4.0, 4)
        if position == 0.0:
            accent = 1.1
        elif position in (1.0, 3.0):
            accent = 1.02
        elif position == 2.0:
            accent = 1.05
        elif abs(position - round(position)) < 0.01:
            accent = 0.96
        elif abs(position * 2 - round(position * 2)) < 0.01:
            accent = 0.9
        else:
            accent = 0.82
        if event.pitch in (KICK, CRASH):
            accent = max(accent, 1.0)
        velocity = event.velocity * accent + rng.randint(-4, 4)
        shaped.append(NoteEvent(start=event.start, duration=event.duration, pitch=event.pitch, velocity=int(clamp(velocity, 26, 124))))
    return shaped

def _kick_pattern(intensity: float, bars: int, subdued: bool, thin: bool=False, cell: tuple=(0.0, 1.0, 2.0, 3.0)) -> List[NoteEvent]:
    if not cell:
        return []
    events: List[NoteEvent] = []
    for bar in range(bars):
        for index, offset in enumerate(cell):
            if thin and index % 2:
                continue
            velocity = int(clamp((68 if subdued else 88) + intensity * 30, 50, 124))
            events.append(NoteEvent(bar * 4.0 + offset, 0.12, KICK, velocity))
    return events

def _offbeat_hats(intensity: float, bars: int, sparse: bool, groove: GrooveProfile | None=None, step: float | None=None) -> List[NoteEvent]:
    events: List[NoteEvent] = []
    step = step if step is not None else groove.hat_step if groove is not None else 1.0
    offset = groove.hat_offset if groove is not None else 0.5
    pitch = RIDE if groove is not None and groove.ride_instead_of_hat else OPEN_HAT
    for bar in range(bars):
        beat = offset
        index = 0
        while beat < 4.0:
            if not (sparse and index % 2):
                onset = groove.swung(beat) if groove is not None else beat
                events.append(NoteEvent(bar * 4.0 + onset, 0.12, pitch, int(clamp(48 + intensity * 42, 42, 112))))
            beat += max(0.5, step * 2.0)
            index += 1
    return events

def _claps(intensity: float, bars: int, every_bar: bool, cell: tuple=(1.0, 3.0)) -> List[NoteEvent]:
    events: List[NoteEvent] = []
    if not cell:
        return events
    for bar in range(bars):
        if not every_bar and bar % 2:
            continue
        for beat in cell:
            events.append(NoteEvent(bar * 4.0 + beat, 0.1, CLAP, int(clamp(58 + intensity * 38, 50, 116))))
    return events

def _closed_hat_drive(intensity: float, bars: int, sixteenths: bool, groove: GrooveProfile | None=None, step: float | None=None) -> List[NoteEvent]:
    events: List[NoteEvent] = []
    base = step if step is not None else groove.hat_step if groove is not None else 0.5
    step = max(0.25, base * 0.5) if sixteenths else base
    beat = 0.0
    while beat < bars * 4.0:
        if abs(beat % 1.0) > 0.001:
            onset = groove.swung(beat % 4.0) + (beat - beat % 4.0) if groove is not None else beat
            events.append(NoteEvent(onset, 0.06, CLOSED_HAT, int(clamp(34 + intensity * 36, 30, 92))))
        beat += step
    return events

def _ride_pattern(intensity: float, bars: int, groove: GrooveProfile | None=None) -> List[NoteEvent]:
    offset = 2.5 if groove is None else (groove.hat_offset + 2.0) % 4.0
    return [NoteEvent(bar * 4.0 + offset, 0.15, RIDE, int(clamp(40 + intensity * 35, 36, 100))) for bar in range(bars)]

def _snare_roll(intensity: float, bars: int) -> List[NoteEvent]:
    events: List[NoteEvent] = []
    total = bars * 4.0
    beat = 0.0
    while beat < total:
        step = 1.0 if beat < 16.0 else 0.5 if beat < 24.0 else 0.25 if beat < 30.0 else 0.125
        velocity = int(clamp(38 + beat / total * 62 + intensity * 16, 34, 120))
        events.append(NoteEvent(beat, min(0.1, step * 0.5), SNARE, velocity))
        beat += step
    return events
