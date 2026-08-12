# Oriondrive

Oriondrive is a macOS application for deterministic MIDI composition. It defines a search process: forty-eight harmonic seeds specify the modal worlds a run can explore, eight groove profiles supply surface rhythms, an [L-system](https://en.wikipedia.org/wiki/L-system) proposes symbolic melodic material, a [cellular automaton](https://en.wikipedia.org/wiki/Cellular_automaton) shapes rhythmic activation and texture, a [genetic algorithm](https://en.wikipedia.org/wiki/Genetic_algorithm) evolves one species per seed, and a form-aware [fitness function](https://en.wikipedia.org/wiki/Fitness_function) selects for the musical behavior the user has encoded. The result is one finished arrangement per seed.

Oriondrive is not a prompt-to-song AI model.

## Features

- Forty-eight harmonic seeds across three form profiles, each with its own mode, chord field, cadence type, pedal behavior and voicing rules.
- Eight groove profiles supplying surface rhythm independently of harmony.
- Per-seed evolution; the population stratifies across seed x groove pairs, evolving one species per seed side by side and returning one arrangement per seed rather than one winner and forty-seven near-copies.
- Chorale pad layer voicing the seed with minimal inner-voice motion, held suspensions, open fourths and fifths, and a pedal on its own slow grid.
- User-defined song structure with section name, bar length, energy and per-layer roles.
- Load and save `.ori` song-structure files.
- Primary controls: form, target length, BPM, key, scale, seed, candidate count, generation count and layer toggles (pads, riffs, bass, drums).
- Advanced controls: CA rule/shape, L-system rule sets, GA selection pressure, diversity weight, layer density/variation.
- Fitness reports with form subscores, seed conformance, penalties, musical fingerprints, diversity scores and nearest-neighbor distances.
- Full CLI, including generation directly from `.ori` files and batch export of every seed variation.

## Quick Start

Requires macOS 11 or later and Python 3.10+.

### Binary install

Download the latest release for Apple Silicon. The bundle is unsigned.

1. Open the `.dmg`.
2. Drag `Oriondrive.app` to `/Applications`.
3. On first launch, right-click the app and choose **Open**. Approve the Gatekeeper prompt. This is only required once.

### Run from source

```bash
python -m pip install -r requirements.txt
python -m oriondrive.gui
```

## How seeds shape the search

Seeds change selection itself, not just initialization:

- The starting population is split across the seed pool rather than sampled from it, so every seed is guaranteed at least one candidate.
- The best candidate of each surviving seed keeps an elite slot before the global elite is filled. Without this, one seed dominates every elite slot within a few generations and the run collapses to a single harmonic world.
- Crossover stays inside a species unless `cross_seed_crossover_rate` fires. Seed drift is rarer than ordinary gene mutation, so a species survives long enough to be optimized.
- Random immigrants cycle through the pool, which can reintroduce a species that died out.
- A candidate is scored on whether it actually sounds like its seed, so drifting toward the average costs fitness.
- The musical fingerprint treats a different seed as a large distance, so novelty pressure reinforces species rather than eroding them.

## Deterministic diversity

The GA includes deterministic novelty pressure. Each candidate receives a musical fingerprint built from pitch-class histograms, rhythm onset histograms, section density, layer activity, CA settings, L-system rule set, phrase length, hook shape, layer densities, harmonic seed, mode, pedal strength, voicing openness, and suspension. Nearest-neighbor distance within the same generation contributes through `diversity_weight`. Harmonic seeds are the primary defense against homogeneous output. The fingerprint is secondary, keeping candidates apart *within* a species.

If you aim for repeatable results, keep the same seed, `.ori`, and parameters. If you want intentional variation, keep all eight seeds in the pool, raise `diversity_weight`, widen mutation rates, increase `random_immigrant_fraction`, change CA rule/seed density, or switch L-system rule sets.

## Determinism and authorship

Given the same seed, `.ori` structure, and parameters, Oriondrive follows the same generation path. The L-system proposes symbolic melodic material. The cellular automaton shapes rhythmic activation, density, accents and texture. The genetic algorithm explores candidate parameter and genome combinations. The fitness function encodes the user's aesthetic judgment; what counts as coherent, tense, repetitive, evolving, danceable, spacious, or genre-appropriate.

The three form profiles encode distinct structural expectations:

- Trance rewards intro/build/breakdown/drop/final/outro behavior.
- EBM rewards tight bass pulse, rigid body groove, command/body contrast, repetition, and controlled variation.
- Berlin School rewards gradual evolution, sequencer mutation, atmospheric openings and dissolves, sparse or absent drums, and hypnotic continuity rather than drop-centered structure.

Authorship resides in the rules, constraints, structure grammar, deterministic seed, and fitness criteria that select one result from many possible candidates.

## History

Oriondrive began in 2020 as a collaborative project with Thomas Jackson Park ([Mystified](https://mystified.bandcamp.com)), exploring the intersection of algorithmic sound generation and emergent AI systems. The workflow integrated [GenerIter](https://pypi.org/project/GenerIter/) with an R Plumber API developed by LR Friberg to generate text using an early GPT model. The generated text was rendered to speech with Amazon Polly, then merged with GenerIter's audio output using FFmpeg.

The first two albums, *Sustainable Security* and *Healthy Growth*, simulated a hip-hop group without human performers, predating commercial LLM-based audio systems such as Suno. The third release, *3dd89f7d*, encoded cryptographic hashes into track titles and lyrics. The final installment, *The Matrix*, introduced a data science challenge in which listeners could extract numerical patterns from the music and fit a regression model to them.

That earlier project functioned as an experimental generative pipeline: GPT-powered text, text-to-speech, algorithmic audio and FFmpeg assembly produced slop-like output. As of now, Oriondrive is different. The authorial act has moved into the design of the deterministic system and the fitness function. The output is a transparent search process through a constrained musical design space.
