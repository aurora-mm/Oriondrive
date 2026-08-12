from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Tuple
from .composition import Composition, NoteEvent
from .config import DEFAULT_MIN_DURATION_SECONDS, DEFAULT_TICKS_PER_BEAT
DEFAULT_LEAD_PROGRAM = 80
DEFAULT_RIFF_PROGRAM = 28
DEFAULT_BASS_PROGRAM = 38
DEFAULT_PAD_PROGRAM = 89

@dataclass(frozen=True)
class MidiWriteResult:
    path: Path
    duration_seconds: float

@dataclass
class _SimpleMidiTrack:
    name: str
    channel: int
    events: List[Tuple[int, int, bytes]] = field(default_factory=list)
    program: int | None = None
    tempo_microseconds: int | None = None

@dataclass
class _SimpleMidiFile:
    ticks_per_beat: int
    tempo: int
    tracks: List[_SimpleMidiTrack]

    @property
    def length(self) -> float:
        last_tick = 0
        for track in self.tracks:
            if track.events:
                last_tick = max(last_tick, max((tick for tick, _, _ in track.events)))
        return last_tick / self.ticks_per_beat * (60.0 / self.tempo)

    def save(self, path: str | Path) -> None:
        target = Path(path)
        header = b'MThd' + 6 .to_bytes(4, 'big') + 1 .to_bytes(2, 'big') + len(self.tracks).to_bytes(2, 'big') + self.ticks_per_beat.to_bytes(2, 'big')
        tracks = b''.join((_serialize_simple_track(track) for track in self.tracks))
        target.write_bytes(header + tracks)

def write_midi(composition: Composition, output_path: str | Path, min_duration_seconds: Optional[float]=DEFAULT_MIN_DURATION_SECONDS, lead_program: int=DEFAULT_LEAD_PROGRAM, riff_program: int=DEFAULT_RIFF_PROGRAM, bass_program: int=DEFAULT_BASS_PROGRAM, pad_program: int=DEFAULT_PAD_PROGRAM) -> MidiWriteResult:
    midi = _build_midi(composition, lead_program, riff_program, bass_program, pad_program)
    duration_seconds = midi_playback_duration_seconds(midi)
    if min_duration_seconds is not None and duration_seconds + 0.001 < min_duration_seconds:
        raise ValueError(f'Rendered MIDI duration is {duration_seconds:.2f}s, shorter than the requested minimum of {min_duration_seconds:.2f}s.')
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    midi.save(path)
    return MidiWriteResult(path=path, duration_seconds=duration_seconds)

def midi_playback_duration_seconds(midi) -> float:
    return float(midi.length)

def _build_midi(composition: Composition, lead_program: int=DEFAULT_LEAD_PROGRAM, riff_program: int=DEFAULT_RIFF_PROGRAM, bass_program: int=DEFAULT_BASS_PROGRAM, pad_program: int=DEFAULT_PAD_PROGRAM):
    try:
        from mido import Message, MetaMessage, MidiFile, MidiTrack, bpm2tempo
    except ImportError:
        return _build_simple_midi(composition, lead_program, riff_program, bass_program, pad_program)
    _validate_program('lead_program', lead_program)
    _validate_program('riff_program', riff_program)
    _validate_program('bass_program', bass_program)
    _validate_program('pad_program', pad_program)
    midi = MidiFile(ticks_per_beat=DEFAULT_TICKS_PER_BEAT)
    leads_track = MidiTrack()
    leads_track.append(MetaMessage('track_name', name='Oriondrive Leads', time=0))
    leads_track.append(MetaMessage('set_tempo', tempo=bpm2tempo(composition.tempo), time=0))
    leads_track.append(Message('program_change', program=lead_program, channel=0, time=0))
    _append_note_events(leads_track, composition.leads, channel=0)
    midi.tracks.append(leads_track)
    if composition.pads:
        pads_track = MidiTrack()
        pads_track.append(MetaMessage('track_name', name='Oriondrive Pads', time=0))
        pads_track.append(Message('program_change', program=pad_program, channel=3, time=0))
        _append_note_events(pads_track, composition.pads, channel=3)
        midi.tracks.append(pads_track)
    if composition.riffs:
        riffs_track = MidiTrack()
        riffs_track.append(MetaMessage('track_name', name='Oriondrive Riffs', time=0))
        riffs_track.append(Message('program_change', program=riff_program, channel=1, time=0))
        _append_note_events(riffs_track, composition.riffs, channel=1)
        midi.tracks.append(riffs_track)
    if composition.bass:
        bass_track = MidiTrack()
        bass_track.append(MetaMessage('track_name', name='Oriondrive Bass', time=0))
        bass_track.append(Message('program_change', program=bass_program, channel=2, time=0))
        _append_note_events(bass_track, composition.bass, channel=2)
        midi.tracks.append(bass_track)
    if composition.drums:
        drums_track = MidiTrack()
        drums_track.append(MetaMessage('track_name', name='Oriondrive Drums', time=0))
        _append_note_events(drums_track, composition.drums, channel=9)
        midi.tracks.append(drums_track)
    return midi

def _validate_program(name: str, program: int) -> None:
    if program < 0 or program > 127:
        raise ValueError(f'{name} must be a MIDI program number between 0 and 127.')

def _build_simple_midi(composition: Composition, lead_program: int=DEFAULT_LEAD_PROGRAM, riff_program: int=DEFAULT_RIFF_PROGRAM, bass_program: int=DEFAULT_BASS_PROGRAM, pad_program: int=DEFAULT_PAD_PROGRAM) -> _SimpleMidiFile:
    _validate_program('lead_program', lead_program)
    _validate_program('riff_program', riff_program)
    _validate_program('bass_program', bass_program)
    _validate_program('pad_program', pad_program)
    tempo_microseconds = int(round(60000000 / composition.tempo))
    tracks = [_simple_track('Oriondrive Leads', composition.leads, channel=0, program=lead_program, tempo_microseconds=tempo_microseconds)]
    if composition.pads:
        tracks.append(_simple_track('Oriondrive Pads', composition.pads, channel=3, program=pad_program))
    if composition.riffs:
        tracks.append(_simple_track('Oriondrive Riffs', composition.riffs, channel=1, program=riff_program))
    if composition.bass:
        tracks.append(_simple_track('Oriondrive Bass', composition.bass, channel=2, program=bass_program))
    if composition.drums:
        tracks.append(_simple_track('Oriondrive Drums', composition.drums, channel=9))
    return _SimpleMidiFile(DEFAULT_TICKS_PER_BEAT, composition.tempo, tracks)

def _simple_track(name: str, events: Iterable[NoteEvent], channel: int, program: int | None=None, tempo_microseconds: int | None=None) -> _SimpleMidiTrack:
    track = _SimpleMidiTrack(name=name, channel=channel, program=program, tempo_microseconds=tempo_microseconds)
    absolute_events: List[Tuple[int, int, bytes]] = []
    if program is not None:
        absolute_events.append((0, 1, bytes([192 | channel, program])))
    for event in events:
        start_tick = _beats_to_ticks(event.start)
        end_tick = _beats_to_ticks(event.start + event.duration)
        pitch = max(0, min(127, int(event.pitch)))
        velocity = max(1, min(127, int(event.velocity)))
        absolute_events.append((start_tick, 2, bytes([144 | channel, pitch, velocity])))
        absolute_events.append((max(start_tick + 1, end_tick), 3, bytes([128 | channel, pitch, 0])))
    track.events = sorted(absolute_events, key=lambda item: (item[0], item[1]))
    return track

def _serialize_simple_track(track: _SimpleMidiTrack) -> bytes:
    data = bytearray()
    name_bytes = track.name.encode('utf-8')
    data.extend(_varlen(0) + bytes([255, 3]) + _varlen(len(name_bytes)) + name_bytes)
    if track.tempo_microseconds is not None:
        data.extend(_varlen(0) + bytes([255, 81, 3]) + int(track.tempo_microseconds).to_bytes(3, 'big'))
    previous_tick = 0
    for tick, _, message in track.events:
        data.extend(_varlen(max(0, tick - previous_tick)))
        data.extend(message)
        previous_tick = tick
    data.extend(_varlen(0) + bytes([255, 47, 0]))
    return b'MTrk' + len(data).to_bytes(4, 'big') + bytes(data)

def _varlen(value: int) -> bytes:
    if value < 0:
        raise ValueError('Variable-length MIDI values must be non-negative.')
    buffer = value & 127
    value >>= 7
    bytes_out = [buffer]
    while value:
        buffer = value & 127 | 128
        bytes_out.insert(0, buffer)
        value >>= 7
    return bytes(bytes_out)

def _append_note_events(track, events: Iterable[NoteEvent], channel: int) -> None:
    from mido import Message, MetaMessage
    absolute_events: List[Tuple[int, int, str, NoteEvent]] = []
    for event in events:
        start_tick = _beats_to_ticks(event.start)
        end_tick = _beats_to_ticks(event.start + event.duration)
        absolute_events.append((start_tick, 0, 'note_on', event))
        absolute_events.append((max(start_tick + 1, end_tick), 1, 'note_off', event))
    absolute_events.sort(key=lambda item: (item[0], item[1]))
    previous_tick = 0
    for tick, _, message_type, event in absolute_events:
        delta = max(0, tick - previous_tick)
        previous_tick = tick
        velocity = event.velocity if message_type == 'note_on' else 0
        track.append(Message(message_type, note=event.pitch, velocity=velocity, channel=channel, time=delta))
    track.append(MetaMessage('end_of_track', time=0))

def _beats_to_ticks(beats: float) -> int:
    return int(round(beats * DEFAULT_TICKS_PER_BEAT))
