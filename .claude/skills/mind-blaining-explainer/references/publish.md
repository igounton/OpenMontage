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

## Anaella API — channels list works; posting flow NOT yet verified
Base `ANAELLA_BASE_URL=https://api.anaella.com`, auth `Authorization: Bearer $ANAELLA_API_KEY`.
- `GET /` → `{"status":"ok","name":"anaella.com API"}`
- `GET /channels` → 200, `data[]` of connected channels. Confirmed: YouTube **Stand For AI**
  `id=i7yex41sdut2epp8z1a0ldfp`, `platform:"youtube"`, `url:https://youtube.com/@standforai`,
  `status:"active"`. (Telegram is also connected in Anaella per the user, but we publish
  Telegram directly via the Bot API above — simpler and confirmed working.)
- `/api/*`, `/api/channels`, `/integrations` → 404. The upload→create-post→publish endpoints
  were NOT discovered/verified in ep3. **Do not guess** — probe `GET /channels`-style paths and
  confirm the resource-upload + post-create endpoints before pushing to YouTube via Anaella.
  Prior episodes (memory, tickling) only ever `status:"exported"` locally — never hit Anaella.
- The Griot MCP `postiz` tools return `{"result":"Invalid host header"}` in this environment —
  not a usable path here.

## YouTube Shorts (Stand For AI)
No verified programmatic upload yet (Anaella post-endpoints unconfirmed). For now: export
package + `publish_log` `status:"draft"`, and upload manually, OR finish verifying the Anaella
posting endpoints. Channel id `i7yex41sdut2epp8z1a0ldfp`.
