#!/usr/bin/env python
"""One automation slot: take the next queued episode all the way to LIVE.

Called by run_slot.sh (which owns the env, the kill-switch and the lock).
Self-heals gaps: always grabs the EARLIEST still-queued episode, so a missed
slot is simply picked up by the next run — production and drain both run 2/day.

Steps: pick -> (author plan.json if missing, via headless claude) -> validate
-> build (idempotent) -> publish LIVE -> mark published.

Fail-safe: any failure marks the episode "failed" and exits non-zero WITHOUT
publishing. Worst case is a missed slot (logged), never a broken live post.

usage: run_slot.py            # next queued episode, build + publish live
       run_slot.py --no-publish   # build only (proving runs)
"""
import json, os, sys, subprocess, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
QUEUE = "projects/memory-explainer/queue.json"
PY = ".venv/bin/python"
REQUIRED = ["slug", "episode", "accent", "hero_title", "music", "script",
            "captions", "stock", "broll_order", "cards", "yt_title",
            "tg_caption_html", "tags"]


def load_queue():
    return json.load(open(QUEUE))


def save_queue(q):
    json.dump(q, open(QUEUE, "w"), indent=2)


def set_status(slug, status):
    q = load_queue()
    for e in q["episodes"]:
        if e["slug"] == slug:
            e["status"] = status
    save_queue(q)


def pick():
    q = load_queue()
    # earliest queued by (date, slot) — episodes are already in order
    for e in q["episodes"]:
        if e["status"] == "queued":
            return e
    return None


def author_plan(entry):
    """Headless claude writes projects/<slug>/plan.json. Creative step only —
    no building, no rendering, no publishing."""
    slug = entry["slug"]
    music = sorted(os.path.splitext(f)[0] for f in os.listdir("music_library")
                   if f.endswith(".mp3"))
    prompt = f"""You are authoring ONE data file and nothing else.

Write the file `projects/{slug}/plan.json` for this Mind-Blaining Explainer episode:
- episode: {entry['episode']}
- slug: {slug}
- title (hook idea): {entry['title']}
- one-line hook: {entry.get('hook','')}
- accent color (use EXACTLY this): {entry['accent']}

STRICT RULES:
1. ONLY write projects/{slug}/plan.json. Do NOT build, render, mux, publish, or
   run build_episode.py / any pipeline. Do NOT create any other file.
2. Read `automation/build_episode.py` (top docstring) for the exact schema, and
   read `projects/you-are-taller-in-the-morning/plan.json` as a worked example to
   copy the shape/quality of.
3. The science MUST be accurate. 6 sections s1..s6 following the beat formula
   (Hook, Myth, Mechanism, Proof, Payoff, Landing). script.* is TTS text — spell
   big numbers in words. captions.* is the on-screen text — numerals are fine.
4. hero_title: two punchy lines separated by " | ".
5. "music": pick ONE basename (no .mp3) from this list that fits the mood:
   {', '.join(music)}
6. stock: 9 clip ids, each with 3 Pexels portrait search queries (concrete,
   visual, likely to return real vertical footage). broll_order: 8 clip ids for
   the b-roll cuts (the brightest clip is auto-picked as the hero, don't worry
   about ordering the hero).
7. cards: cut7/cut12/cut14 are {{text, subtitle}}; cut9/cut10 are {{stat, subtitle}}
   (stat = a short punchy number/word).
8. yt_title <= 100 chars ending in " #Shorts". tg_caption_html is Telegram HTML.
   tags: 12-15 lowercase tags.

Write valid JSON only. Then stop."""
    print(f"[run_slot] authoring plan for {slug} via headless claude ...", flush=True)
    p = subprocess.run(
        ["claude", "-p", prompt, "--dangerously-skip-permissions"],
        capture_output=True, text=True, timeout=900)
    if p.returncode != 0:
        print(p.stdout[-800:]); print(p.stderr[-800:])
        raise RuntimeError(f"plan authoring failed rc={p.returncode}")


def validate_plan(slug):
    path = f"projects/{slug}/plan.json"
    if not os.path.exists(path):
        raise RuntimeError(f"no plan.json at {path}")
    plan = json.load(open(path))  # raises on invalid JSON
    missing = [k for k in REQUIRED if k not in plan]
    if missing:
        raise RuntimeError(f"plan.json missing keys: {missing}")
    if plan["slug"] != slug:
        raise RuntimeError(f"plan slug {plan['slug']} != {slug}")
    if len(plan["stock"]) != 9:
        raise RuntimeError(f"expected 9 stock clips, got {len(plan['stock'])}")
    return plan


def run(cmd, timeout):
    print(f"[run_slot] $ {' '.join(cmd)}", flush=True)
    p = subprocess.run(cmd, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"{cmd[1]} exited {p.returncode}")


def main(publish=True):
    entry = pick()
    if not entry:
        print("[run_slot] queue drained — nothing to do."); return 0
    slug = entry["slug"]
    print(f"[run_slot] EP{entry['episode']} {slug} ({entry['date']} {entry['slot_local']})")
    set_status(slug, "in_progress")
    try:
        if not os.path.exists(f"projects/{slug}/plan.json"):
            author_plan(entry)
        validate_plan(slug)
        # build (idempotent: skip if already rendered)
        if not os.path.exists(f"projects/{slug}/renders/final_captioned.mp4"):
            run([PY, "automation/build_episode.py", slug], timeout=1800)
        else:
            print("[run_slot] render exists, skipping build")
        if not publish:
            set_status(slug, "queued")  # proving run: leave it for the real slot
            print("[run_slot] --no-publish: built only, left queued"); return 0
        run([PY, "automation/publish_episode.py", slug], timeout=1200)
        # publish_episode marks it "published"
        print(f"[run_slot] DONE EP{entry['episode']} {slug} — LIVE")
        return 0
    except Exception as e:
        set_status(slug, "failed")
        print(f"[run_slot] FAILED {slug}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(publish="--no-publish" not in sys.argv))
