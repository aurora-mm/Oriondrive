from __future__ import annotations
from dataclasses import dataclass, field, replace
from typing import Iterable, List
from .arrangement import BEATS_PER_BAR, DEFAULT_BARS_PER_LOOP
from .composition import NoteEvent
MusicalEvent = NoteEvent

@dataclass
class LoopPattern:
    id: str
    bars: int = DEFAULT_BARS_PER_LOOP
    events: List[MusicalEvent] = field(default_factory=list)
    motif_id: str = 'main'
    variation_level: float = 0.0
    source: str = 'lead'

    @property
    def beats(self) -> float:
        return float(self.bars * BEATS_PER_BAR)

    def shifted(self, start_beat: float, velocity_scale: float=1.0, octave_shift: int=0) -> List[MusicalEvent]:
        shifted_events: List[MusicalEvent] = []
        for event in self.events:
            shifted_events.append(MusicalEvent(start=start_beat + event.start, duration=event.duration, pitch=max(0, min(127, event.pitch + octave_shift)), velocity=int(max(1, min(127, round(event.velocity * velocity_scale))))))
        return shifted_events

    def clipped(self) -> 'LoopPattern':
        end = self.beats
        clipped_events = [replace(event, duration=max(0.03125, min(event.duration, end - event.start))) for event in self.events if 0 <= event.start < end]
        return replace(self, events=clipped_events)

def quantize(value: float, grid: float=0.25) -> float:
    if grid <= 0:
        return value
    return round(value / grid) * grid

def events_in_range(events: Iterable[MusicalEvent], start: float, end: float) -> List[MusicalEvent]:
    return [event for event in events if start <= event.start < end]

def loop_signature(events: Iterable[MusicalEvent], bars: int=DEFAULT_BARS_PER_LOOP) -> tuple[tuple[float, int], ...]:
    events = sorted(events, key=lambda event: (event.start, event.pitch))
    if not events:
        return tuple()
    base_pitch = events[0].pitch
    loop_beats = bars * BEATS_PER_BAR
    return tuple(((round(event.start % loop_beats, 3), int(event.pitch - base_pitch)) for event in events[:32]))
