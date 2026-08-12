from __future__ import annotations
import random
from dataclasses import dataclass
from typing import List
from .arrangement import Arrangement, BEATS_PER_BAR
from .composition import NoteEvent
from .config import clamp, validate_probability
from .harmony import HarmonyPlan, PadVoicing
PAD_ROLE_SETTINGS = {'pedal': (0.52, 0, False, True, 0), 'soft': (0.68, 3, False, True, 0), 'air': (0.62, 3, True, False, 12), 'chorale': (0.86, 4, False, True, 0), 'full': (1.0, 5, True, True, 0)}

@dataclass(frozen=True)
class PadConfig:
    density: float = 0.7
    voice_count: int = 4
    air_amount: float = 0.45
    pedal_strength: float = 0.85
    swell_amount: float = 0.35
    base_velocity: int = 64

    def validate(self) -> None:
        validate_probability('pad_density', self.density)
        validate_probability('pad_air_amount', self.air_amount)
        validate_probability('pad_pedal_strength', self.pedal_strength)
        validate_probability('pad_swell_amount', self.swell_amount)
        if self.voice_count < 2 or self.voice_count > 6:
            raise ValueError('pad_voice_count must be between 2 and 6.')
        if self.base_velocity < 1 or self.base_velocity > 110:
            raise ValueError('pad_base_velocity must be between 1 and 110.')

class PadGenerator:

    def __init__(self, config: PadConfig):
        self.config = config
        self.config.validate()

    def generate(self, plan: HarmonyPlan, arrangement: Arrangement, rng: random.Random) -> List[NoteEvent]:
        voicings = plan.pad_voicings(voice_count=self.config.voice_count)
        events: List[NoteEvent] = []
        for voicing in voicings:
            section = arrangement.section_for_bar(voicing.slot.start_bar)
            role = section.pad_role or 'chorale'
            if role == 'off':
                continue
            events.extend(self._events_for_voicing(voicing, role, section.energy, rng))
        events.extend(self._pedal_events(plan, arrangement))
        return sorted(events, key=lambda event: (event.start, event.pitch))

    def _events_for_voicing(self, voicing: PadVoicing, role: str, energy: float, rng: random.Random) -> List[NoteEvent]:
        velocity_scale, body_voices, air_on, _pedal_on, register_shift = PAD_ROLE_SETTINGS.get(role, PAD_ROLE_SETTINGS['chorale'])
        if body_voices <= 0:
            return []
        start = voicing.slot.start_beat
        length = voicing.slot.length_bars * BEATS_PER_BAR
        duration = length + (0.5 if self.config.swell_amount > 0.2 else 0.0)
        base = self.config.base_velocity * velocity_scale * (0.72 + energy * 0.42)
        events: List[NoteEvent] = []
        body = list(voicing.body)[:body_voices]
        for index, pitch in enumerate(body):
            shifted = _clamp_pitch(pitch + register_shift)
            velocity = base * (1.0 - index * 0.06)
            if voicing.slot.is_cadence:
                velocity *= 1.06
            events.append(NoteEvent(start, duration, shifted, _velocity(velocity)))
        if air_on and voicing.air and (rng.random() < clamp(self.config.air_amount + 0.25, 0.0, 1.0)):
            for pitch in voicing.air:
                events.append(NoteEvent(start, duration, _clamp_pitch(pitch), _velocity(base * 0.55)))
        return events

    def _pedal_events(self, plan: HarmonyPlan, arrangement: Arrangement) -> List[NoteEvent]:
        if self.config.pedal_strength <= 0.0:
            return []
        pedal_bars = max(1, plan.seed.pedal_bars)
        total_bars = arrangement.total_bars
        events: List[NoteEvent] = []
        bar = 0
        while bar < total_bars:
            section = arrangement.section_for_bar(bar)
            role = section.pad_role or 'chorale'
            settings = PAD_ROLE_SETTINGS.get(role, PAD_ROLE_SETTINGS['chorale'])
            length_bars = min(pedal_bars, total_bars - bar)
            if role != 'off' and settings[3]:
                slot = plan.slot_for_bar(bar)
                root = _clamp_pitch(slot.bass_pitch_class + 24)
                fifth = _clamp_pitch(root + 7)
                velocity = _velocity(self.config.base_velocity * self.config.pedal_strength * (0.62 + section.energy * 0.3))
                start = float(bar * BEATS_PER_BAR)
                duration = float(length_bars * BEATS_PER_BAR)
                events.append(NoteEvent(start, duration, root, velocity))
                if plan.voicing_openness > 0.35:
                    events.append(NoteEvent(start, duration, fifth, _velocity(velocity * 0.82)))
            bar += length_bars
        return events

def pad_config_from_genome(genome: object) -> PadConfig:
    return PadConfig(density=float(getattr(genome, 'pad_density', 0.7)), voice_count=int(getattr(genome, 'pad_voice_count', 4)), air_amount=float(getattr(genome, 'pad_air_amount', 0.45)), pedal_strength=float(getattr(genome, 'pedal_strength', 0.85)), swell_amount=float(getattr(genome, 'suspension_amount', 0.35)))

def _velocity(value: float) -> int:
    return int(clamp(round(value), 24, 112))

def _clamp_pitch(pitch: int) -> int:
    return int(clamp(pitch, 21, 108))
