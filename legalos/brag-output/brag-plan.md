# Brag Plan: LegalOS

## What is this app?
LegalOS is a legal and compliance operating system for Indian small and medium businesses: five workspaces (Contracts, Vendors, Notices, Compliance, Documents) that take a real document or number and give a verdict with its evidence, a quote from the document, a section of Indian law, or the government registry's reply. When it does not know, it says so.

## The angle
An Apple-style product film. Slow, confident, generous air. One idea per shot. The product's own screens are the hero; captions in a serif face land a beat after the visual. The claim that carries the whole film: every answer shows its evidence.

## Hook (first 3 seconds)
Warm white. One serif line: "Every business signs things it has not read." Then the Home sheet pushes in slowly: "Good evening, Ramesh." and four large numerals.

## Key moments (the middle)
- The contract reading room: a critical finding card on the right; the clause on the paper blooms in a soft red tint; "Suggested change" wording appears below it.
- A GSTIN typed into the vendor desk; the monospace cells turn green one by one; the live registry card reveals TATA MOTORS, Active, "Live registry".
- The notice response desk: a large serif "11 days left", a timeline from received to reply-by, the two dates weighed with the earliest marked; then the four steps and the reply draft with yellow blanks.
- The compliance planner: twelve months of dots, the Next-up card with a large number of days.
- The documents chat: a Hinglish question, a structured answer, a citation chip that opens the exact passage, "found word for word".

## Outro / punchline
A quiet proof beat on warm white (604 automated tests; 32 of 33 retrieval questions correct; 24 contract rules, 30 compliance rules, every one with its source), then the LegalOS mark and wordmark: "Legal and compliance, run as a system."

## User flow worth showing
Open a contract -> click a finding -> the clause highlights with a suggested change. Type a GSTIN -> cells validate live -> the registry answers. Open a notice -> the deadline is computed and explained -> the reply draft waits for a lawyer. Ask the handbook a question in Hinglish -> a cited answer -> the passage opens.

## Tone
- Preset: cinematic (with polished restraint)
- Creative direction: Apple product film; luxurious, slow, lots of air, no fast cuts, no stock footage
- Interpretation: long holds (4-9 s), slow push-ins and gentle parallax on real screenshots, crossfades of 0.8-1.0 s, serif captions that fade in a beat after the visual, one quiet music bed with a single swell near the end.

## Format: landscape — 1920x1080
## Duration: 66 seconds (user asked for 60-75; the /brag 15-25 s law is overridden on explicit request)

## Visual identity (from the project)
- Background (frame): #f6f5f1
- Sheet: #ffffff; card tint: #f6f4f0
- Text: #1f1f1e; secondary #55534e
- Accent: teal #1f5f5b; tints peach #fdf3e8 and lavender #f1e9fb; critical #d03b3b
- Display font: Instrument Serif (Google Fonts)
- Body font: Figtree (Google Fonts); document text Newsreader
- Strongest visual element: the white rounded sheet on the warm frame with the serif greeting and the red clause highlight in the contract reading room

## Source material (real screens captured from the running app, demo company Kulkarni Textiles)
- Home, contract reading room (before/after clicking a finding), vendor desk (partial GSTIN, full GSTIN, live result), notice desk (deadline strip, steps, reply editor), compliance planner, documents chat (question, answer, source sheet). Captured at 1568x745 from http://localhost:5173, placed on the 1920x1080 canvas with a slow push-in.
- Nothing invented: every number and line on screen is the product's own output.

## Share copy (draft)
LegalOS. Legal and compliance for Indian SMEs, where every answer shows its evidence: a quote from your document, a section of the law, or the government registry's reply.

## Audio direction
- Role: cinematic support, very restrained
- Music: happy-beats-business-moves-vol-12-by-ende-dot-app.mp3 (the calmest bundled track; the brief asked for piano and strings, which the library does not have; vol-12 at a low level is the closest)
- Music treatment: starts at 0 under a 1 s fade-in, volume 0.22, one gentle rise to 0.30 at the proof beat, fades out over the final 2.5 s so the logo lands in near silence
- Music cue guidance: preset read (about 110 BPM). Strong cues used only to bias three moments: the hook line, the contract clause bloom, and the logo landing (within 0.15 s). Sequential text is never snapped to the beat grid; holds come first.
- Audio-reactive treatment: subtle; the warm background glow behind the screens may breathe with RMS. No waveforms, no pulsing text.
- SFX posture: sparse, soft. drop_001 under caption arrivals (0.35), mouseclick1 on the simulated clicks (0.4), impactSoft_medium_000 for the clause bloom and registry reveal (0.45), impactBell_heavy_000 once at the logo (0.5).
- Audio-coupled moments: GSTIN cells turning green (soft ticks, optional), the clause bloom, the logo.
- Restraint rule: nothing louder than the captions feel; no sound on every element; silence for the last second before the mark.

## Storyboard (66 s)

### Scene 1 — Hook — 5 s
Warm white frame, grain. Serif line fades in: "Every business signs things it has not read." Holds 3.5 s, fades.
Sequential/interaction: none. Audio: music fades in under. Transition: soft crossfade -> 2

### Scene 2 — Home — 6 s
The Home sheet pushes in slowly from 1.04 to 1.0 scale. Visible: "Good evening, Ramesh." and the four numerals. Caption (bottom left, serif): "One system. Five workspaces."
Sequential: none. Transition: soft crossfade -> 3

### Scene 3 — Contracts, title — 3 s
Warm white. Serif: "Read it before you sign it." Transition: crossfade -> 4

### Scene 4 — Contracts, the finding — 9 s
Reading-room screenshot before the click (0-3 s), simulated cursor moves to the critical card, click, crossfade to the after-click screenshot (clause blooms red, suggested change visible), slow push-in on the highlighted clause. Caption at 5 s: "Every clause that could hurt you, quoted." Caption at 7.5 s: "With what to ask for instead."
Sequential/interaction: yes, a cursor click. Audio: click, then a soft impact on the bloom. Transition: crossfade -> 5

### Scene 5 — Vendors — 9 s
Title card 2.5 s: "Check a supplier before you pay." Then the vendor desk: partial GSTIN shot crossfades to the full GSTIN shot (cells green), a soft tick as the cells complete, then the result screenshot (TATA MOTORS, Active, Live registry). Caption: "The government registry, live."
Sequential/interaction: yes, typed number then Enter. Transition: crossfade -> 6

### Scene 6 — Notices — 11 s
Title card 2.5 s: "A legal notice arrived." Then the deadline strip screenshot with a push-in on the large "11 DAYS LEFT" and the timeline (3 s), crossfade to the steps screenshot (3 s), crossfade to the reply editor with yellow blanks (2.5 s). Caption: "Nothing invented. A lawyer reviews it."
Transition: crossfade -> 7

### Scene 7 — Compliance — 7 s
Title card 2 s: "Never miss a filing." Then the planner screenshot with a slow push-in on the Next-up number. Caption: "Thirty rules, each with its source."
Transition: crossfade -> 8

### Scene 8 — Documents — 9 s
Title card 2 s: "Ask your own papers." Then the chat: question shot crossfades to the answer shot (structured bullets with citation chips), then to the source sheet ("found word for word"). Caption: "Hindi, Hinglish or English. Always cited."
Transition: crossfade -> 9

### Scene 9 — Proof — 5 s
Warm white. Three lines arrive one by one, 1 s apart, held together: "604 automated tests." "32 of 33 retrieval questions correct." "Every rule with its source." Music lifts slightly.
Sequential: yes, three lines, each held to the reading floor. Transition: crossfade -> 10

### Scene 10 — Logo — 5 s
The LegalOS mark (a balance in one stroke) draws in, the wordmark fades beside it, then the line "Legal and compliance, run as a system." Music fades out; one soft bell on the mark; one second of silence; fade to warm white.

**Music mood for this video:** calm cinematic bed, low
**Audio summary:** a quiet bed that breathes under long holds, three soft accents, one lift at the proof beat, and silence under the logo.
