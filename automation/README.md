# Mind-Blaining Explainers — daily automation

Produces + publishes **2 episodes/day** (09:00 and 17:00 local) fully unattended,
straight from `projects/memory-explainer/queue.json` (60 topics ≈ 30 days).

## Pieces

| File | Role |
|------|------|
| `queue.json` (`projects/memory-explainer/`) | the 60-topic backlog, each with `status` |
| `run_slot.sh` | launchd entrypoint: kill-switch, single-instance lock, env, logging |
| `run_slot.py` | one slot: pick next queued ep → author plan → build → publish LIVE |
| `build_episode.py` | `plan.json` → `renders/final_captioned.mp4` + `exports/<slug>/` |
| `publish_episode.py` | LIVE to Telegram (Anaella) + YouTube (Stand For AI) |
| `com.openmontage.mindblaining.{9am,5pm}.plist` | the two launchd timers |
| `logs/` | one `slot-<ts>.log` per run + launchd out/err |

Each slot grabs the **earliest still-`queued`** episode, so a missed run is just
picked up next time — production and drain both run 2/day and stay in sync.
If a topic has no `plan.json` yet, a headless `claude -p` authors one (creative
step only) which `run_slot.py` validates before building.

**Fail-safe:** any failure marks that episode `failed` and exits without
publishing — worst case is a missed slot (logged), never a broken live post.

## Install (load the timers)

```bash
cp automation/com.openmontage.mindblaining.9am.plist ~/Library/LaunchAgents/
cp automation/com.openmontage.mindblaining.5pm.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.openmontage.mindblaining.9am.plist
launchctl load ~/Library/LaunchAgents/com.openmontage.mindblaining.5pm.plist
launchctl list | grep openmontage   # confirm both loaded
```

launchd fires at 09:00/17:00; if the Mac was asleep then, it runs on next wake.
The Mac must be on and logged in — this is where ffmpeg / the venv / Modal creds /
Remotion live, so it only works on this machine.

## Controls

```bash
# Pause everything (no rebuild of jobs needed):
touch automation/DISABLE      # any queued run sees this and skips
rm automation/DISABLE         # resume

# Run a slot right now (foreground, real publish):
bash automation/run_slot.sh

# Build the next queued ep but DON'T publish (proving run):
bash automation/run_slot.sh --no-publish

# Uninstall the timers:
launchctl unload ~/Library/LaunchAgents/com.openmontage.mindblaining.9am.plist
launchctl unload ~/Library/LaunchAgents/com.openmontage.mindblaining.5pm.plist
```

## Watch it

```bash
tail -f automation/logs/slot-*.log            # newest run
python -c "import json;q=json.load(open('projects/memory-explainer/queue.json'));\
from collections import Counter;print(Counter(e['status'] for e in q['episodes']))"
```

Statuses: `queued` → `in_progress` → `published` (or `failed`, left for a manual look).
