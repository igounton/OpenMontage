# Publish — tested distribution paths

The deliverable is `projects/<slug>/renders/final_captioned.mp4`. Always package the export
first, then push to the channels below. Publishing is a human-approval gate — confirm intent
(live vs draft) before any outward call.

## Export package (always do this)
```
exports/<slug>/
  video/output.mp4          # copy of final_captioned.mp4
  metadata/metadata.json    # per-platform titles/captions, channel ids, hashtags
  metadata/description.txt   metadata/chapters.txt   metadata/tags.txt
  thumbnails/concept.json
```
Then write `artifacts/publish_log.json` (validates against schema). Entry fields:
`platform, status(published|exported|failed|draft|pending_review), visibility(public|private|unlisted),
url, video_id, timestamp, export_path, metadata_used`. Use `visibility:"private"` for drafts.

## Telegram — WORKS (Telegram Bot API, direct) ✅ tested ep3
Creds in `.env` (gitignored): `TELEGRAM_BOT_TOKEN` (bot @anaellabot), `TELEGRAM_CHANNEL_ID`
(`-1003260495410`, channel "Anaella", invite https://t.me/+QGjsOmzwogk0YjJh). Bot must be an
admin of the channel. `sendVideo` file limit ~50 MB (our Shorts are ~14 MB).
```python
import os, requests
from dotenv import load_dotenv; load_dotenv(".env")
tok=os.environ["TELEGRAM_BOT_TOKEN"]; chat=os.environ["TELEGRAM_CHANNEL_ID"]
with open("projects/<slug>/renders/final_captioned.mp4","rb") as f:
    r=requests.post(f"https://api.telegram.org/bot{tok}/sendVideo",
        data={"chat_id":chat,"caption":CAPTION,"parse_mode":"HTML","supports_streaming":"true"},
        files={"video":("<slug>.mp4", f, "video/mp4")}, timeout=180)
# r.json()["result"]["message_id"]; private-channel link = https://t.me/c/3260495410/<message_id>
```
Posting to the channel is LIVE (no draft state via bot). Confirm before sending.

## Anaella API — YouTube/social — VERIFIED WORKING (ep3, draft on Stand For AI) ✅
Base `ANAELLA_BASE_URL=https://api.anaella.com`, auth `Authorization: Bearer $ANAELLA_API_KEY`.
Source of truth: `/Users/isaacgounton/Desktop/DEV/DAHO/anaella` (API in `apps/api/src/modules`).
Docs live at `GET /openapi.json`. Channels: `GET /channels` → YouTube **Stand For AI**
`i7yex41sdut2epp8z1a0ldfp`.

**⚠ Never POST the file to `/resources/` directly — it proxies to MinIO and Cloudflare 524s
on anything nontrivial.** Use the presign flow (PUT straight to storage):

1. `POST /resources/presign` json `{"fileName","contentType":"video/mp4","isPrivate":false}`
   → `{"resource":{id,type,location,url,...}, "uploadUrl":"<minio presigned>"}`
2. `PUT <uploadUrl>` with raw file bytes, header `Content-Type: video/mp4` (goes to MinIO, fast).
3. `POST /resources/{id}/complete` json `{}` → resource object. Metadata (size/dims/duration)
   populates async — poll `GET /resources/{id}` a few times if you need it.
4. `POST /posts/` json `{"type":"reel","name":"<title>"}` → post shell, `status:"draft"`, empty channels.
5. `PUT /posts/` (attach — the whole object) json:
   ```json
   {"id":"<post_id>","type":"reel","name":"<title>","description":"<caption ≤5000>",
    "status":"draft","scheduledAt":null,"firstComment":null,
    "channels":[{"id":"i7yex41sdut2epp8z1a0ldfp","platform":"youtube","name":"Stand For AI",
      "imageUrl":null,"scheduledPost":{"id":"_new","status":"draft","scheduledAt":null,
      "publishedAt":null,"startedAt":null,"failedAt":null,"failureReason":null,
      "parentPostId":null,"parentPostSettings":null,"repostSettings":null,"settings":null}}],
    "totalLikes":0,"totalImpressions":0,"totalComments":0,"totalShares":0,
    "createdAt":"<from step 4>","resource":<full resource object from step 3>}
   ```
   Leaves it a DRAFT. Gotchas: reels REQUIRE a non-null `resource`; ≥1 channel; new-channel
   attach needs `scheduledPost.id:"_new"` (server assigns real id); YouTube description ≤5000.
   On 400 the body carries `value.data.errors` (per-platform) — read it.
6. **Publish** (only when told to go live): `PATCH /posts/{id}/publish` json `{}`. Schedule
   instead by setting `scheduledAt` (ISO) in step 5 then calling publish. Undo: `PATCH /posts/{id}/return-to-draft`, delete: `DELETE /posts/{id}`.

Working tested script: reproduce the steps above with `requests`; ep3 draft = post
`qoe8p1t0unxq56tgh2gpwq9p`. The Griot MCP `postiz` tools return "Invalid host header" — don't use them.
