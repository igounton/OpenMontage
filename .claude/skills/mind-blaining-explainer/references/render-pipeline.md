# Render Pipeline — exact, tested steps (Episode 3 "You Never Touch Anything")

Follow top to bottom. Every command here was run and verified. Paths assume repo root
`/Users/isaacgounton/Desktop/DEV/Videos/OpenMontage` and project
`projects/<slug>/`. Always run Python as `PYTHONPATH=. .venv/bin/python` (see
[[openmontage-venv-setup]] — Homebrew PEP 668).

## 0. Scaffold
```
mkdir -p projects/<slug>/artifacts projects/<slug>/assets/{images,video,audio,music} projects/<slug>/renders
```

## 1. Narration (mediakit_tts, af_nova, $0)
`tools.audio.mediakit_tts.MediakitTTS().execute({...})`. Env `MEDIAKIT_BASE_URL`,
`MEDIAKIT_AUTH_TOKEN` (in .env). One call per script section, writing to
`assets/audio/nar_sN.wav`:
```python
tool.execute({"text": TEXT, "voice": "af_nova", "speed": 1.0,
              "engine": "kokoro", "output_path": "projects/<slug>/assets/audio/nar_s1.wav"})
```
- `result.data["output"]` is the wav path. **`result.duration_seconds` is WALL-CLOCK, not audio length** — get real duration with ffprobe:
  `ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 <wav>`
- Cold-start: the tool now polls readiness up to 90s before download (fixed; early download 404s).
- Keep TTS text kokoro-friendly: spell big numbers ("ninety nine point nine nine…"), no SSML tags (read literally).

## 2. Timeline from real durations
Lay narration segments back-to-back (no gaps, like cant-tickle). Cumulative starts =
running sum of durations. Video length = last card `out_seconds` + 1s (Remotion
`calculateMetadata` adds 1s). Keep single scenes ≤6s, 15-20 cuts, new visual every 2-5s.

## 3. Stock video (Pexels portrait, $0)
`tools.video.pexels_video.PexelsVideo().execute({...})`, env `PEXELS_API_KEY`. Downloads
the TOP match to `output_path`. 7+ clips minimum.
```python
tool.execute({"query": "finger touching phone screen close up", "orientation": "portrait",
              "min_duration": 4, "per_page": 10, "preferred_quality": "hd",
              "output_path": "projects/<slug>/assets/video/vid_touch.mp4"})
```
Fallback: retry without `orientation` if portrait returns none. `pixabay_video` is the alt provider.

## 4. Audio: concat narration + mix music (post — Remotion renders SILENT)
```
# concat back-to-back
printf "file 'nar_s1.wav'\n...file 'nar_s6.wav'\n" > assets/audio/concat_list.txt
ffmpeg -y -f concat -safe 0 -i assets/audio/concat_list.txt -c copy assets/audio/narration_concat.wav
# copy chosen music_library track
cp "music_library/<track>.mp3" assets/music/bed.mp3
# mix: narration 1.0 + music 0.13, fade in 1s / out 2s, NO ducking, normalize=0. VIDEO_LEN = e.g. 64
ffmpeg -y -i assets/audio/narration_concat.wav -i assets/music/bed.mp3 -filter_complex \
"[0:a]apad=whole_dur=64[nar];[1:a]atrim=0:64,volume=0.13,afade=t=in:st=0:d=1,afade=t=out:st=62:d=2[mus];[nar][mus]amix=inputs=2:duration=first:normalize=0[a]" \
-map "[a]" -ar 48000 assets/audio/final_mix.wav
```

## 5. edit_decisions.json — the Remotion props (⚠ NOT the stale schema)
`video_compose` passes `edit_decisions` straight through as Remotion props.
**`schemas/artifacts/edit_decisions.schema.json` is STALE** — it requires `source` on
every cut and forbids `type`/`text`/`stat`/`subtitle`. Ignore it; mirror
`projects/cant-tickle-yourself/artifacts/edit_decisions.json`. Real cut shapes:
- hero_title: `{"id","type":"hero_title","text":"LINE ONE | LINE TWO","in_seconds","out_seconds"}`
- text_card: `{... "type":"text_card","text":"A | B","subtitle":"…"}` (BOTH text+subtitle)
- stat_card: `{... "type":"stat_card","stat":"8,000,000,000 → 1","subtitle":"…"}`
- callout: `{... "type":"callout","text":"quote","title":"— Speaker"}`
- video cut: `{"id","source":"assets/video/vid_x.mp4","in_seconds","out_seconds", ...}`

Top-level: `"renderer_family":"explainer-data"`, `"render_runtime":"remotion"`,
`"composition_mode":"templated"`, `"subtitles":{"enabled":false}` (captions burned in post).

**Accent color:** include a full `themeConfig` object and DO NOT set `playbook`/`theme`
(`resolveTheme` in Root.tsx prefers a named THEMES entry over themeConfig). Teal ep3:
```json
"themeConfig": {"accentColor":"#0D9488","backgroundColor":"#0A0F14","surfaceColor":"#111A22",
"textColor":"#F1F5F9","headingFont":"Space Grotesk","captionHighlightColor":"#2DD4BF",
"captionBackgroundColor":"rgba(10,15,20,0.78)"}
```
Accent rotation: ep1 indigo #6366f1, ep2 coral #f97316, ep3 teal #0D9488, ep4 green #22C55E.

## 6. asset_manifest.json (REQUIRED by video_compose render)
`video_compose` errors "asset_manifest required for render" without it. Build a list of
`{id,type,path,source_tool,provider,format,cost_usd,duration_seconds}` for every narration
wav, video, and the music bed. `type` ∈ narration|video|music. Paths project-relative.

## 7. Render (silent) via video_compose → Remotion
⚠ **Video sources resolve against Remotion `public/`, not file://.** Before rendering:
```
ln -s "$(pwd)/projects/<slug>/assets" remotion-composer/public/assets
```
Set cut `source` to `assets/video/X.mp4` (public-relative). Then:
```python
from tools.video.video_compose import VideoCompose
VideoCompose().execute({"operation":"render","edit_decisions":ED,"asset_manifest":AM,
  "output_path":"projects/<slug>/renders/final.mp4","profile":"instagram_reels"})
```
- Runs `npx remotion render … Explainer … --width 1080 --height 1920`. ~2.5 min for ~1920
  frames — **run in background** (foreground 2-min bash limit kills it) and wait on the file.
- Output is SILENT (has an empty audio track). `final_review.status:"revise"` due to silence is EXPECTED.
- After render: `rm remotion-composer/public/assets` (remove symlink).

## 8. Captions SRT (42 cues for ~64s) — burned in post
Split each narration segment into phrase chunks (~5 words), allocate time proportional to
word count within the segment's [start,end]. Use display-friendly numerals ("99.9999999%",
"8 billion") not the spelled-out TTS text. Write `assets/audio/subtitles.srt`.

## 9. Mux audio + burn captions (ffmpeg)
```
R=projects/<slug>/renders
ffmpeg -y -i $R/final.mp4 -i projects/<slug>/assets/audio/final_mix.wav -c:v copy -c:a aac -b:a 192k -map 0:v:0 -map 1:a:0 -shortest $R/final_sound.mp4
cd projects/<slug> && ffmpeg -y -i renders/final_sound.mp4 -vf "subtitles=assets/audio/subtitles.srt:force_style='FontName=Helvetica,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H40000000,BorderStyle=3,Outline=1,MarginV=40,Alignment=2'" -c:a copy renders/final_captioned.mp4
```
**Deliverable = `renders/final_captioned.mp4`.** Verify: `ffmpeg -i … -af volumedetect -f null -`
(mean ≈ -30 dB healthy, not -91 dB silent) and sample 2-3 frames to eyeball accent/captions.

## Artifact validation
research_brief / proposal_packet / decision_log / script / scene_plan / render_report /
publish_log all validate against `schemas/artifacts/*`. `edit_decisions` does NOT (schema
stale — see §5). Enum quirks hit in ep3: proposal `renderer_family` ∈ explainer-data…;
`delivery_promise` is an OBJECT (promise_type/motion_required/tone_mode/quality_floor∈draft|presentable|broadcast);
scene `narrative_role` ∈ establish_context|introduce_subject|build_tension|deliver_payload|transition|emotional_beat|evidence|comparison|resolution|call_to_action;
required_assets `source` ∈ generate|source|provided|record; publish `visibility` ∈ public|private|unlisted (use private for drafts).
