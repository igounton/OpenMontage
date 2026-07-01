# Memory Explainer Series Director

## When to Use

Read this skill at the start of any memory-explainer / mind-blaining episode. It encodes every production rule and quality bar learned from episodes 1 and 2 — read it once, then all downstream decisions follow the established format without re-discovery.

## Mandatory Production Rules

### TTS Provider
- **MUST use `preferred_provider: "mediakit"`** for all narration segments.
- Voice: `af_nova` (Kokoro, female, clear explainer tone). Speed: 1.0.
- Cost: $0. Time cost: ~60 sec per 6-segment batch.
- Handle the 2-step download: TTS returns `file_id` → poll `/api/v1/media/storage/{file_id}/status` until `"ready"` → GET to download.

### Hero Titles (absolute — from episode 2 feedback)
- **MUST be split across 2 lines** using pipe `|` separator.
- Example: `"YOU CAN'T | TICKLE YOURSELF"` renders as 2 animated lines with per-character spring.
- The first line gets accent-color glow. Second line is white.
- Use `type: "hero_title"` with `text` field containing the `|` format.
- Single-line hero titles are forbidden — they cause text redundancy with captions.

### Scene Types & Visuals
- **7+ stock video clips minimum** — each visual section must have video (Pexels portrait, 9:16). Not images. Never stingy with clips.
- Use Pexels free portrait stock footage (`pexels_video` tool, `orientation: "portrait"`, `min_duration: 5`).
- Cut structure: 15-20 cuts, avg 2-4 seconds each. Longest single scene: 6 seconds max.
- Videos should rotate generously — every 2-5 seconds a new visual.

### Text Card Composition Rules (absolute — from episode 1/2 feedback)
- Every `text_card` MUST have both `text` and `subtitle` fields — plain text alone is redundant with captions.
- Text cards require: accent bar animation, glass-card container (`borderRadius: 20`, gradient bg), `boxShadow` glow, slide-up entrance.
- Use 2-line text format with `|` where appropriate (e.g., `"Your brain predicts | your own moves..."`).
- Stat cards (`stat_card`) MUST have both `stat` (the number) and `subtitle` (the explanation).
- Callout cards (`callout`) MUST have `text` (the quote) and `title` (the speaker).

### Accent Color
- Rotate per episode. Episode 1 was indigo (`#6366f1`). Episode 2 was coral (`#f97316`).
- Set via `accentColor` in the Explainer props.
- Avoid repeating the same accent in consecutive episodes.

### Audio Mix
- Concat all narration WAVs into one file (`narration_concat.wav`) using FFmpeg concat demuxer.
- Download music via `pixabay_music` tool or use `music_library/` free tracks. Trim to match video duration.
- Mix: narration at 1.0 volume + music at 0.13 volume. `amix=inputs=2:duration=first:normalize=0` — NO sidechain duck, NO normalize.
- Fade in music over 1s, fade out over 2s.
- Audio mixed in post — Remotion render is silent. Final mux: `ffmpeg -i final.mp4 -i final_mix.wav -c:v copy -c:a aac -map 0:v:0 -map 1:a:0 -shortest final_sound.mp4`

### Captions
- Generate 27+ cue SRT from narration timing. Each utterance should break into 2-3 subtitle cues.
- Burn using FFmpeg libass: `subtitles=path/to/subtitles.srt:force_style='FontName=Helvetica,FontSize=18,PrimaryCol=&H00FFFFFF,OutlineCol=&H40000000,BorderStyle=3,Outline=1,MarginV=40,Alignment=2'`
- Output: `final_captioned.mp4`.

### Cost Budget
- TTS: $0 (Mediakit Kokoro)
- Images: ~$0.002 each (Together AI FLUX). For stock images: $0.
- Stock video: $0 (Pexels free tier).
- Music: $0 (Pixabay free or music_library/).
- Total per episode: ~$0.006-0.010 for AI images. $0 for everything else.

### Render Pipeline
1. Build `edit_decisions.json` with all cuts, audio config, subtitles config
2. Build `props` for Remotion: cuts + audio (narration_concat.wav as single src)
3. Symlink project assets into `remotion-composer/public/assets/`
4. Render: `npx remotion render src/index.tsx Explainer final.mp4 --props=props.json --width 1080 --height 1920`
5. Remove symlink
6. Mux audio with ffmpeg
7. Burn captions with ffmpeg libass

### Publish
- Use `anaella.com` API: upload resource → create post → PUT with channel + media → PATCH publish
- YouTube channel: Stand For AI (`i7yex41sdut2epp8z1a0ldfp`)
- Auth: `Authorization: Bearer $ANAELLA_API_KEY`
