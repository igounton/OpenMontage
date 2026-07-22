#!/usr/bin/env python
"""Publish a built episode to Telegram (Anaella) + YouTube (Stand For AI), LIVE now.
Reuses the proven EP19-21 paths. Writes projects/<slug>/artifacts/publish_log.json.

usage: publish_episode.py <slug> [--dry]   (--dry skips outward calls, prints what it would do)
"""
import os, sys, json, time, subprocess, requests
from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
load_dotenv(".env")


def telegram(slug, meta):
    cap = meta["platforms"]["telegram"]["caption_html"]
    tok = os.environ["TELEGRAM_BOT_TOKEN"]; chat = os.environ["TELEGRAM_CHANNEL_ID"]
    path = f"projects/{slug}/renders/final_captioned.mp4"
    with open(path, "rb") as f:
        r = requests.post(f"https://api.telegram.org/bot{tok}/sendVideo",
            data={"chat_id": chat, "caption": cap, "parse_mode": "HTML", "supports_streaming": "true"},
            files={"video": (f"{slug}.mp4", f, "video/mp4")}, timeout=600)
    j = r.json()
    if not j.get("ok"):
        raise RuntimeError(f"telegram: {json.dumps(j)[:300]}")
    mid = j["result"]["message_id"]
    url = f"https://t.me/c/3260495410/{mid}"
    print("  telegram:", url)
    return {"platform": "telegram", "status": "published", "visibility": "public",
            "url": url, "video_id": str(mid), "timestamp": None}


def youtube(slug, meta):
    BASE = os.environ["ANAELLA_BASE_URL"].rstrip("/"); KEY = os.environ["ANAELLA_API_KEY"]
    H = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
    yt = meta["platforms"]["youtube"]; TITLE = yt["title"]
    DESC = open(f"exports/{slug}/metadata/description.txt").read().strip()
    CH_ID = yt["channel_id"]; CH_NAME = yt["channel"]
    FILE = f"projects/{slug}/renders/final_captioned.mp4"
    assert 0 < len(TITLE) <= 100, f"bad title len {len(TITLE)}"
    r = requests.post(f"{BASE}/resources/presign", headers=H, json={
        "fileName": f"{slug}.mp4", "contentType": "video/mp4", "isPrivate": False}, timeout=60)
    r.raise_for_status(); pj = r.json(); res = pj["resource"]; upload_url = pj["uploadUrl"]; rid = res["id"]
    for attempt in range(3):
        p = subprocess.run(["curl", "-sS", "--fail", "-X", "PUT", "--max-time", "300",
            "-H", "Content-Type: video/mp4", "--data-binary", f"@{FILE}", "-w", "%{http_code}", upload_url],
            capture_output=True, text=True)
        if p.returncode == 0 and p.stdout.strip()[-3:] == "200":
            break
        time.sleep(3)
    else:
        raise RuntimeError("youtube upload failed: " + p.stderr[-300:])
    r = requests.post(f"{BASE}/resources/{rid}/complete", headers=H, json={}, timeout=60)
    r.raise_for_status(); resource = r.json()
    r = requests.post(f"{BASE}/posts/", headers=H, json={"type": "reel", "name": TITLE}, timeout=60)
    r.raise_for_status(); post = r.json(); pid = post["id"]; created = post.get("createdAt")
    attach = {"id": pid, "type": "reel", "name": TITLE, "description": DESC, "status": "draft",
        "scheduledAt": None, "firstComment": None,
        "channels": [{"id": CH_ID, "platform": "youtube", "name": CH_NAME, "imageUrl": None,
            "scheduledPost": {"id": "_new", "status": "draft", "scheduledAt": None, "publishedAt": None,
            "startedAt": None, "failedAt": None, "failureReason": None, "parentPostId": None,
            "parentPostSettings": None, "repostSettings": None, "settings": None}}],
        "totalLikes": 0, "totalImpressions": 0, "totalComments": 0, "totalShares": 0,
        "createdAt": created, "resource": resource}
    r = requests.put(f"{BASE}/posts/", headers=H, json=attach, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"youtube attach: {r.status_code} {r.text[:300]}")
    r = requests.patch(f"{BASE}/posts/{pid}/publish", headers=H, json={}, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"youtube publish: {r.text[:300]}")
    final = None
    for _ in range(20):
        time.sleep(5)
        g = requests.get(f"{BASE}/posts/{pid}", headers=H, timeout=60).json()
        sp = g["channels"][0]["scheduledPost"]; final = sp
        if sp["status"] in ("published", "failed"):
            break
    if final and final["status"] == "failed":
        raise RuntimeError(f"youtube failed: {final.get('failureReason')}")
    print("  youtube:", pid, final and final["status"])
    return {"platform": "youtube", "status": final["status"] if final else "unknown",
            "url": None, "video_id": pid, "channel": CH_NAME,
            "published_at": (final or {}).get("publishedAt"), "timestamp": None}


def update_queue(slug, status):
    qp = "projects/memory-explainer/queue.json"
    q = json.load(open(qp))
    for e in q["episodes"]:
        if e["slug"] == slug:
            e["status"] = status
    json.dump(q, open(qp, "w"), indent=2)


def main(slug, dry):
    meta = json.load(open(f"exports/{slug}/metadata/metadata.json"))
    entries = [{"platform": "export", "status": "exported", "visibility": "private",
                "export_path": f"exports/{slug}/"}]
    if dry:
        print("[publish --dry] would post TG + YT for", slug); return
    entries.append(telegram(slug, meta))
    entries.append(youtube(slug, meta))
    log = {"version": "1.0", "series": "Mind-Blaining Explainers", "episode": meta["episode"],
           "slug": slug, "entries": entries}
    json.dump(log, open(f"projects/{slug}/artifacts/publish_log.json", "w"), indent=2)
    update_queue(slug, "published")
    print("[publish] DONE", slug)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: publish_episode.py <slug> [--dry]"); sys.exit(2)
    main(sys.argv[1], "--dry" in sys.argv)
