---
name: mind-blaining-explainer
description: >-
  Produce one episode of the "Mind-Blaining Explainers" short-form science
  series end to end. Use whenever the user asks to "create the next video",
  "make the next episode", "another mind-blaining/explainer Short", or names a
  counterintuitive science/psychology/space topic to explain (e.g. "you never
  touch anything", "why time speeds up as you age", "trees vs stars"). Encodes
  every production rule learned from prior episodes so the format is applied
  without re-discovery: pipeline = animated-explainer, 60-90s vertical Short
  (1080x1920), mediakit af_nova TTS ($0), 2-line hero titles, glass text cards
  with subtitles, 7+ Pexels portrait clips, 15-20 cuts, teal/rotating accent,
  Remotion render, ffmpeg audio mux + libass caption burn, Anaella publish.
  Not for avatar/talking-head, product launches, or captioning existing footage.
---

# Mind-Blaining Explainers — Series Director

Read this at the start of every episode. It encodes the full format and quality
bar learned from prior episodes; downstream decisions follow it without
re-discovery. It supersedes the loose `skills/series/memory-explainer/director.md`
and `projects/memory-explainer/SERIES_SKILL.md` notes.

## Premise
Counterintuitive ideas across science / psychology / space / history framed as
"the thing you thought you knew — wrong." Every episode overturns one common
assumption with **one mechanism + one killer stat**.

## Episode start checklist
1. This is the `animated-explainer` pipeline. Still honor OpenMontage Rule Zero
   (`AGENT_GUIDE.md`) — run preflight, present both composition runtimes at the
   proposal gate, log decisions. Runtime is **Remotion** by series precedent.
2. Pick the next topic from `projects/memory-explainer/SEED_TOPICS.md` and
   **rotate the accent color** (see table below).
3. Follow the 6-beat formula from `projects/memory-explainer/FORMAT_BIBLE.md`:
   Hook → Myth → Mechanism → Proof → Payoff → Landing.
4. Produce artifacts against `schemas/artifacts/` and validate each one.
5. Narration durations drive the final timeline — generate TTS first, then lock
   cut boundaries to real audio durations.

## Accent color rotation (never repeat consecutively)
| Ep | Topic | Accent |
|----|-------|--------|
| 1 | memory | indigo `#6366f1` |
| 2 | tickling | coral `#f97316` |
| 3 | touch (you never touch anything) | teal `#0D9488` |
| 4 | trees vs stars | green `#22C55E` |
Set via `accentColor` in the Explainer props.

## Mandatory production rules

### TTS — narration
- Use the `mediakit_tts` tool (`preferred_provider: "mediakit"`), voice
  `af_nova` (Kokoro, clear explainer tone), speed 1.0. Cost $0.
- 2-step download: TTS returns `file_id` → poll
  `/api/v1/media/storage/{file_id}/status` until `"ready"` → GET to download.
- One WAV per script section. Capture each `duration_seconds`.

### Hero titles (absolute)
- MUST split across 2 lines with a pipe `|` separator
  (e.g. `"YOU NEVER | TOUCH ANYTHING"`). Single-line hero titles are forbidden —
  they go redundant with burned captions.
- `type: "hero_title"`, `text` holds the `|` format. Line 1 gets accent glow,
  line 2 white; per-character spring entrance.

### Scene types & visuals
- **7+ Pexels portrait stock clips minimum** (9:16). Video, not stills. Never
  stingy. Use the stock video path (`orientation: "portrait"`, `min_duration: 5`).
- 15-20 cuts, avg 2-4s each, longest single scene 6s. New visual every 2-5s.
- Generated FLUX stills (`together_image`) only for hero/metaphor frames that
  stock can't cover (~$0.002 each).

### Card composition (absolute)
- `text_card`: MUST have BOTH `text` and `subtitle` (plain text alone is
  redundant with captions). Accent-bar animation, glass container
  (`borderRadius: 20`, gradient bg), `boxShadow` glow, slide-up entrance.
  Use 2-line `|` format where it reads well.
- `stat_card`: MUST have `stat` (the number) + `subtitle` (the explanation).
  Oversized numeral on the proof beat.
- `callout`: MUST have `text` (the quote) + `title` (the speaker).

### Audio mix (post — Remotion renders silent)
- Concat narration WAVs → `narration_concat.wav` (FFmpeg concat demuxer).
- Music from `music_library/` (free) or `pixabay_music`; trim to video duration.
- Mix: narration 1.0 + music 0.13, `amix=inputs=2:duration=first:normalize=0`
  (NO sidechain duck, NO normalize). Music fade in 1s / out 2s.
- Mux: `ffmpeg -i final.mp4 -i final_mix.wav -c:v copy -c:a aac -map 0:v:0 -map 1:a:0 -shortest final_sound.mp4`

### Captions (burned in post, not by Remotion)
- Generate a 27+ cue SRT from narration timing; each utterance breaks into 2-3
  cues. In `edit_decisions`, Remotion `subtitles.enabled: false` — captions are
  burned afterward with FFmpeg libass:
  `subtitles=subtitles.srt:force_style='FontName=Helvetica,FontSize=18,PrimaryCol=&H00FFFFFF,OutlineCol=&H40000000,BorderStyle=3,Outline=1,MarginV=40,Alignment=2'`
- Output `final_captioned.mp4`.

### Cost budget
TTS $0 · stock video $0 · music $0 · FLUX stills ~$0.002 each. Total per
episode ≈ $0-0.01. Stay within it; flag any paid step.

## Render pipeline
1. Build `edit_decisions.json` — cuts, audio config, subtitles config
   (`enabled: false`), `render_runtime: "remotion"`.
2. Build Remotion `props`: cuts + audio (`narration_concat.wav` as single src).
3. Symlink project assets into `remotion-composer/public/assets/`.
4. `npx remotion render src/index.tsx Explainer final.mp4 --props=props.json --width 1080 --height 1920`
5. Remove the symlink.
6. Mux audio (ffmpeg, above).
7. Burn captions (ffmpeg libass, above) → `final_captioned.mp4`.

## Publish (human-approval gate — confirm live vs draft first)
Full tested details in **`references/publish.md`**. Summary:
- **Telegram — WORKS** via Telegram Bot API `sendVideo` (bot @anaellabot, channel "Anaella"
  `-1003260495410`; creds in gitignored `.env` as `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHANNEL_ID`).
  Bot is a channel admin; ≤50 MB. Posting is LIVE — confirm before sending.
- **Anaella API** (`https://api.anaella.com`, `Bearer $ANAELLA_API_KEY`): `GET /channels`
  works and lists YouTube **Stand For AI** (`i7yex41sdut2epp8z1a0ldfp`). The upload/post/
  publish endpoints are NOT yet verified — do not guess; probe and confirm first.
- Always build the `exports/<slug>/` package + `publish_log.json` regardless of channel.

## References (read these — they remove all guesswork)
- **`references/render-pipeline.md`** — exact, tested end-to-end commands: TTS, stock, audio
  mix, edit_decisions (⚠ stale schema), themeConfig accent, asset_manifest, silent Remotion
  render + `public/assets` symlink, SRT gen, ffmpeg mux + libass burn, artifact enum quirks.
- **`references/publish.md`** — Telegram Bot path (works) + Anaella API discovery.
- `projects/memory-explainer/SEED_TOPICS.md` — topic backlog + hooks
- `projects/memory-explainer/FORMAT_BIBLE.md` — 6-beat formula + visual system
- Reference implementations: `projects/cant-tickle-yourself/` (ep2), `projects/never-touch-anything/` (ep3)
