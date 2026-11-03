# Hyperframes Composition Brief: LegalOS

## Objective
Create a 66-second Apple-style product film for LegalOS from real screens of the running app.

## Output
- Composition directory: `brag-output/composition/`
- Rendered video: `brag-output/brag.mp4`
- Format: landscape — 1920x1080, 30 fps
- Duration: 66 seconds (explicitly requested 60-75 s)

## Source Material
- Project root: `legalos/` (frontend `legalos/frontend`, React + Tailwind)
- Screens captured from http://localhost:5173 at 1568x745 (demo company Kulkarni Textiles), in `composition/assets/screens/`:
  home, contract_before, contract_after, vendor_partial, vendor_full, vendor_result, notice_strip, notice_steps, notice_reply, compliance, docs_empty, docs_answer, docs_source
- Product name: LegalOS
- Tagline / strongest claim: "Every answer shows its evidence." / "Read it before you sign it."
- Key UI moments: the red clause bloom with Suggested change; GSTIN cells turning green and the live registry card; the deadline strip with "11 days left"; the reply draft with yellow blanks; the planner's month strip; the citation chip opening the quoted passage.
- Copy that must appear verbatim (all from the product): "Read it before you sign it." · "Check a supplier before you pay" · "What do you want to know?" · "Quote found word for word" · "Live registry" · "Safe to proceed"

## Creative Direction
- Tone preset: cinematic, with polished restraint
- Creative direction: Apple product film, luxurious, slow, lots of air, one idea per shot
- Interpretation: long holds, slow push-ins and gentle parallax on real screenshots, 0.8-1.0 s crossfades, serif captions that fade in a beat after the visual, one quiet music bed, silence under the logo
- Angle: the product's own screens are the hero; the claim that every answer shows its evidence carries the film
- Hook: "Every business signs things it has not read."
- Outro: the LegalOS mark and "Legal and compliance, run as a system."
- Avoid: generic SaaS language, abstract filler, stock footage, fast cuts, neon, emojis, invented features or numbers

## Visual Identity
- Frame background: #f6f5f1; sheet #ffffff; card tint #f6f4f0
- Text: #1f1f1e; secondary #55534e; muted #8a877f
- Accent: teal #1f5f5b; peach #fdf3e8; lavender #f1e9fb; critical #d03b3b
- Display font: Instrument Serif (Google Fonts); Body: Figtree; Document text: Newsreader
- Visual references: the warm frame + white rounded sheet with soft shadow; serif greeting; red clause highlight; green GSTIN cells

## Storyboard
See `brag-output/brag-plan.md` (10 scenes, 66 s).

## Audio
- Audio role: cinematic support, very restrained
- Audio arc: music fades in under the hook, breathes under long holds, lifts gently at the proof beat, fades to silence under the logo
- Music: `assets/music/happy-beats-business-moves-vol-12-by-ende-dot-app.mp3` (the calmest bundled track; requested piano/strings are not in the library)
- Music treatment: volume 0.22, fade-in 1 s, fade-out 2.5 s ending at 64.5 s; the logo lands in silence
- Music cue guidance: preset at `<skill-dir>/assets/music/cues/happy-beats-business-moves-vol-12-by-ende-dot-app.music-cues.md` (about 110 BPM). Bias only the hook line, the clause bloom and the logo; no beat-grid snapping of readable text.
- Audio-reactive treatment: none (the composition is image-based; stillness is the design)
- SFX (soft, sparse): `assets/sfx/drop_001.ogg` on caption arrivals; `assets/sfx/mouseclick1.ogg` on the two simulated clicks; `assets/sfx/impactSoft_medium_000.ogg` on the clause bloom and the registry reveal; `assets/sfx/impactBell_heavy_000.ogg` once on the logo
- Exact timestamps are decided in the composition.

## Hyperframes Instructions
- Plain HTML composition with GSAP timelines registered on `window.__timelines["root"]`, paused, absolute positions.
- Screens are `<img>` elements scaled to 1920 wide (1920x912) centred on the canvas with a subtle rounded-corner sheet shadow, slow scale 1.0 to 1.06 push-ins, crossfades between states.
- A simulated cursor (small dark arrow) moves to the critical finding card and clicks; the before/after screenshots crossfade on the click.
- Captions: Instrument Serif, 44-60 px, bottom-left on screens, centred on title cards, fade in 0.6 s after the visual settles, hold to the reading floor.
- Run `npx hyperframes check` before render; render with `--quality high`.
