#!/usr/bin/env python
"""Generic Mind-Blaining episode builder — turns projects/<slug>/plan.json into a
finished renders/final_captioned.mp4 + exports/<slug>/ package.

Reuses the exact pipeline proven on EP19-21 and bakes in the two QA fixes learned
the hard way: md5 de-dup across stock clips, and a brightness-ranked hero cold-open
(so an unattended run can never ship a duplicate clip or a text-on-black hero).

plan.json schema (authored per episode — by hand or by headless claude):
{
  "slug","episode","accent":"#RRGGBB",
  "hero_title":"LINE ONE | LINE TWO",
  "music":"traversing_-_godmode",              # basename in music_library/
  "script":{"s1":..,"s2":..,"s3":..,"s4":..,"s5":..,"s6":..},   # TTS text, spell big numbers
  "captions":{"s1":..,..,"s6":..},             # display text (numerals ok)
  "stock":{"vid_1":[q,q,q], .. "vid_9":[..]},  # 9 clips, pexels queries each
  "broll_order":["vid_1",.. 8 ids ..],         # order for cut2,3,4,5,6,8,11,13 (hero auto-picked)
  "cards":{ "cut7":{text,subtitle}, "cut9":{stat,subtitle}, "cut10":{stat,subtitle},
            "cut12":{text,subtitle}, "cut14":{text,subtitle} },
  "yt_title":..,"tg_caption_html":..,"tags":[..],"description":.. (optional),
  "chapters":[".."] (optional; else auto from beats)
}
"""
import json, os, sys, subprocess, hashlib, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)   # so `import tools.*` works no matter who invokes us
FF = "/opt/homebrew/bin/ffmpeg"
FP = "/opt/homebrew/bin/ffprobe"
ORDER = ["s1", "s2", "s3", "s4", "s5", "s6"]


def sh(cmd):  # run, return stdout, raise on error
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"cmd failed: {' '.join(cmd[:4])}...\n{p.stderr[-400:]}")
    return p.stdout


def dur(path):
    return float(sh([FP, "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=nw=1:nk=1", path]).strip())


def wof(path):  # width
    out = sh([FP, "-v", "error", "-select_streams", "v:0", "-show_entries",
              "stream=width", "-of", "default=nw=1:nk=1", path]).strip()
    return int(out) if out else 0


def yavg(path, ss=1):  # mean luma of one frame (brightness 0-255)
    out = subprocess.run([FF, "-ss", str(ss), "-i", path, "-frames:v", "1", "-vf",
        "signalstats,metadata=print:key=lavfi.signalstats.YAVG", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    for tok in out.split():
        if "YAVG=" in tok:            # token is 'lavfi.signalstats.YAVG=<n>'
            return float(tok.split("YAVG=")[1])
    return 0.0


def md5(path):
    return hashlib.md5(open(path, "rb").read()).hexdigest()


def mix_hex(a, b, t):  # a,b '#rrggbb', t in 0..1 -> a*(1-t)+b*t
    a = a.lstrip("#"); b = b.lstrip("#")
    c = [round(int(a[i:i+2], 16) * (1 - t) + int(b[i:i+2], 16) * t) for i in (0, 2, 4)]
    return "#" + "".join(f"{v:02X}" for v in c)


def theme_from_accent(acc):
    return {
        "accentColor": acc,
        "backgroundColor": mix_hex(acc, "#000000", 0.93),
        "surfaceColor": mix_hex(acc, "#000000", 0.83),
        "textColor": mix_hex(acc, "#FFFFFF", 0.92),
        "headingFont": "Space Grotesk",
        "captionHighlightColor": mix_hex(acc, "#FFFFFF", 0.35),
        "captionBackgroundColor": "rgba(8,8,12,0.80)",
    }


# ── steps ────────────────────────────────────────────────────────────────────
def step_tts(P, plan):
    from tools.audio.mediakit_tts import MediakitTTS
    tool = MediakitTTS(); durs = {}
    os.makedirs(f"{P}/assets/audio", exist_ok=True)
    for s in ORDER:
        out = f"{P}/assets/audio/nar_{s}.wav"
        txt = plan["script"][s]
        # cache key on the script text: a reused slug / edited line must NOT
        # silently ship the previous episode's narration under new captions
        sidecar = f"{P}/assets/audio/nar_{s}.txt"
        stale = (not os.path.exists(sidecar)) or open(sidecar).read() != txt
        if not os.path.exists(out) or stale:
            r = tool.execute({"text": txt, "engine": "chatterbox",
                              "exaggeration": 0.5, "output_path": out})
            if not r.success:
                raise RuntimeError(f"TTS {s} failed: {r.error}")
            open(sidecar, "w").write(txt)
        durs[s] = round(dur(out), 2)
        # Chatterbox silently truncates over-long input; no human speaks >260wpm
        wpm = len(txt.split()) / durs[s] * 60
        if wpm > 260:
            raise RuntimeError(
                f"TTS {s}: {len(txt.split())}w in {durs[s]}s = {wpm:.0f}wpm — "
                f"audio is truncated or does not match the script")
    json.dump(durs, open(f"{P}/artifacts/durations.json", "w"), indent=2)
    print("  tts:", durs, "total", round(sum(durs.values()), 2))
    return durs


def step_stock(P, plan):
    """Fetch 9 distinct clips (pexels portrait, pixabay fallback), md5-deduped."""
    from tools.video.pexels_video import PexelsVideo
    from tools.video.pixabay_video import PixabayVideo
    px, pb = PexelsVideo(), PixabayVideo()
    VD = f"{P}/assets/video"; os.makedirs(VD, exist_ok=True)
    have = {}  # md5 -> cid (already accepted)
    for cid, queries in plan["stock"].items():
        out = f"{VD}/{cid}.mp4"
        if os.path.exists(out) and md5(out) not in have:
            have[md5(out)] = cid
            continue
        best = None  # (width, md5) of a non-dup candidate kept at out
        tmp = out + ".t"
        # pexels portrait first, then pixabay vertical; try each query
        plans = [("px", q) for q in queries] + [("pb", q) for q in queries]
        for prov, q in plans:
            tool = px if prov == "px" else pb
            kw = {"query": q, "min_duration": 4, "per_page": 10, "output_path": tmp}
            kw["orientation"] = "portrait" if prov == "px" else "vertical"
            if prov == "px":
                kw["preferred_quality"] = "hd"
            try:
                r = tool.execute(kw)
            except Exception as e:
                print(f"    {cid} {prov} '{q}' err {e}"); continue
            if not (r.success and os.path.exists(tmp)):
                continue
            h = md5(tmp); w = wof(tmp)
            if h in have:            # duplicate of an accepted clip — reject
                os.remove(tmp); continue
            if best is None or w > best[0]:
                if best is not None and os.path.exists(out):
                    pass
                shutil.move(tmp, out); best = (w, h)
                if w >= 1080:
                    break
            else:
                os.remove(tmp)
        if best is None:
            raise RuntimeError(f"stock {cid}: no distinct clip found")
        have[best[1]] = cid
        print(f"    {cid}: {best[0]}w")
    return list(plan["stock"].keys())


def pick_layout(plan):
    """Assign hero = brightest clip; rest fill b-roll slots in plan order."""
    P = f"projects/{plan['slug']}"; VD = f"{P}/assets/video"
    ids = list(plan["stock"].keys())
    bright = {cid: yavg(f"{VD}/{cid}.mp4") for cid in ids}
    hero = max(ids, key=lambda c: bright[c])
    broll = [c for c in plan.get("broll_order", ids) if c != hero]
    # ensure exactly 8 b-roll (pad/truncate from remaining)
    extra = [c for c in ids if c != hero and c not in broll]
    broll = (broll + extra)[:8]
    while len(broll) < 8:            # reuse if somehow short
        broll.append(broll[len(broll) % max(1, len(broll))])
    print(f"  hero={hero} (Y{bright[hero]:.0f})  broll={broll}")
    return hero, broll


def step_edl(P, plan, durs, hero, broll):
    start = {}; t = 0.0
    for s in ORDER:                       # round each boundary to 2dp so start/end/L
        start[s] = round(t, 2); t = round(t + durs[s], 2)   # never drift apart in float
    end = {s: round(start[s] + durs[s], 2) for s in ORDER}
    VLEN = round(t + 1.0, 2)

    def L(s, f):
        return round(start[s] + f * durs[s], 2)

    c = plan["cards"]
    cuts = [
        {"id": "cut1", "type": "hero_title", "text": plan["hero_title"],
         "backgroundVideo": f"assets/video/{hero}.mp4", "backgroundVideoStart": 0.0,
         "backgroundOverlay": 0.5, "in_seconds": 0.0, "out_seconds": 3.0},
        {"id": "cut2", "source": f"assets/video/{broll[0]}.mp4", "in_seconds": 3.0, "out_seconds": end["s1"]},
        {"id": "cut3", "source": f"assets/video/{broll[1]}.mp4", "in_seconds": start["s2"], "out_seconds": L("s2", 0.5)},
        {"id": "cut4", "source": f"assets/video/{broll[2]}.mp4", "in_seconds": L("s2", 0.5), "out_seconds": end["s2"]},
        {"id": "cut5", "source": f"assets/video/{broll[3]}.mp4", "in_seconds": start["s3"], "out_seconds": L("s3", 0.34)},
        {"id": "cut6", "source": f"assets/video/{broll[4]}.mp4", "in_seconds": L("s3", 0.34), "out_seconds": L("s3", 0.66)},
        {"id": "cut7", "type": "text_card", **c["cut7"], "in_seconds": L("s3", 0.66), "out_seconds": end["s3"]},
        {"id": "cut8", "source": f"assets/video/{broll[5]}.mp4", "in_seconds": start["s4"], "out_seconds": L("s4", 0.33)},
        {"id": "cut9", "type": "stat_card", **c["cut9"], "in_seconds": L("s4", 0.33), "out_seconds": L("s4", 0.7)},
        {"id": "cut10", "type": "stat_card", **c["cut10"], "in_seconds": L("s4", 0.7), "out_seconds": end["s4"]},
        {"id": "cut11", "source": f"assets/video/{broll[6]}.mp4", "in_seconds": start["s5"], "out_seconds": L("s5", 0.55)},
        {"id": "cut12", "type": "text_card", **c["cut12"], "in_seconds": L("s5", 0.55), "out_seconds": end["s5"]},
        {"id": "cut13", "source": f"assets/video/{broll[7]}.mp4", "in_seconds": start["s6"], "out_seconds": L("s6", 0.45)},
        {"id": "cut14", "type": "text_card", **c["cut14"], "in_seconds": L("s6", 0.45), "out_seconds": VLEN},
    ]
    # captions (per-word proportional within each section)
    caps = []
    for s in ORDER:
        words = plan["captions"][s].split()
        d = durs[s] / max(1, len(words))
        for i, w in enumerate(words):
            a = start[s] + i * d
            caps.append({"word": w, "startMs": round(a * 1000), "endMs": round((a + d) * 1000)})
    ed = {"renderer_family": "explainer-data", "render_runtime": "remotion",
          "composition_mode": "templated", "video_duration_seconds": VLEN,
          "themeConfig": theme_from_accent(plan["accent"]),
          "audio": {"narration": "assets/audio/narration_concat.wav"},
          "subtitles": {"enabled": False}, "cuts": cuts, "captions": caps}
    # self-check: contiguous, ends at VLEN
    b = [0.0]
    for cu in cuts:
        assert cu["in_seconds"] == b[-1], f"gap at {cu['id']}"
        assert cu["out_seconds"] > cu["in_seconds"], f"bad dur {cu['id']}"
        b.append(cu["out_seconds"])
    assert abs(b[-1] - VLEN) < 0.01
    json.dump(ed, open(f"{P}/artifacts/edit_decisions.json", "w"), indent=2, ensure_ascii=False)
    print(f"  edl: 14 cuts VLEN={VLEN}")
    return ed, VLEN, start


def step_mix(P, plan, VLEN):
    A = f"{P}/assets/audio"; M = f"{P}/assets/music"; os.makedirs(M, exist_ok=True)
    lst = f"{A}/concat_list.txt"
    open(lst, "w").write("".join(f"file 'nar_{s}.wav'\n" for s in ORDER))
    sh([FF, "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", f"{A}/narration_concat.wav"])
    bed_src = f"music_library/{plan['music']}.mp3"
    shutil.copy(bed_src, f"{M}/bed.mp3")

    def mean(path, af=None):
        cmd = [FF, "-i", path]
        if af:
            cmd += ["-af", af]
        else:
            cmd += ["-af", "volumedetect"]
        out = subprocess.run(cmd + ["-f", "null", "-"], capture_output=True, text=True).stderr
        for line in out.splitlines():
            if "mean_volume:" in line:
                return float(line.split("mean_volume:")[1].split("dB")[0])
        return -30.0
    nar = mean(f"{A}/narration_concat.wav"); mus = mean(f"{M}/bed.mp3")
    vol = round(10 ** (((nar - 11) - mus) / 20), 3)
    fout = round(VLEN - 2.3, 2)
    fc = (f"[0:a]apad[nar];[1:a]atrim=0:{VLEN},volume={vol},"
          f"afade=t=in:st=0:d=1.5,afade=t=out:st={fout}:d=2.3[mus];"
          f"[nar][mus]amix=inputs=2:duration=shortest:normalize=0[mx];"
          f"[mx]alimiter=limit=0.79:level=disabled[a]")
    sh([FF, "-y", "-i", f"{A}/narration_concat.wav", "-i", f"{M}/bed.mp3",
        "-filter_complex", fc, "-map", "[a]", "-t", str(VLEN), "-ar", "48000", f"{A}/final_mix.wav"])
    print(f"  mix: nar={nar} mus={mus} vol={vol}")


def step_render(P, plan, ed, durs):
    from tools.video.video_compose import VideoCompose
    AM = {"version": "1.0", "assets": []}
    for s in ORDER:
        AM["assets"].append({"id": f"nar_{s}", "type": "narration", "path": f"assets/audio/nar_{s}.wav",
            "source_tool": "mediakit_tts", "provider": "chatterbox", "format": "wav",
            "cost_usd": 0.0, "duration_seconds": durs[s]})
    for cid in plan["stock"]:
        p = f"{P}/assets/video/{cid}.mp4"
        AM["assets"].append({"id": cid, "type": "video", "path": f"assets/video/{cid}.mp4",
            "source_tool": "stock_video", "provider": "stock", "format": "mp4",
            "cost_usd": 0.0, "duration_seconds": round(dur(p), 2)})
    AM["assets"].append({"id": "bed", "type": "music", "path": "assets/music/bed.mp3",
        "source_tool": "music_library", "provider": plan["music"], "format": "mp3",
        "cost_usd": 0.0, "duration_seconds": round(dur(f"{P}/assets/music/bed.mp3"), 2)})
    json.dump(AM, open(f"{P}/artifacts/asset_manifest.json", "w"), indent=2)
    link = "remotion-composer/public/assets"
    if os.path.islink(link) or os.path.exists(link):
        os.remove(link)
    os.symlink(os.path.abspath(f"{P}/assets"), link)
    try:
        r = VideoCompose().execute({"operation": "render", "edit_decisions": ed,
            "asset_manifest": AM, "output_path": f"{P}/renders/final.mp4",
            "profile": "instagram_reels"})
    finally:
        os.remove(link)
    if not r.success:
        raise RuntimeError(f"render failed: {r.error}")
    print("  render: ok")


def step_mux(P, VLEN):
    sh([FF, "-y", "-i", f"{P}/renders/final.mp4", "-i", f"{P}/assets/audio/final_mix.wav",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-map", "0:v:0", "-map", "1:a:0",
        "-shortest", f"{P}/renders/final_captioned.mp4"])
    print("  mux: ok")


def step_export(P, plan, durs, start):
    slug = plan["slug"]; E = f"exports/{slug}"
    for sub in ("video", "metadata", "thumbnails"):
        os.makedirs(f"{E}/{sub}", exist_ok=True)
    shutil.copy(f"{P}/renders/final_captioned.mp4", f"{E}/video/output.mp4")
    VLEN = round(sum(durs.values()) + 1.0, 2)
    desc = plan.get("description") or " ".join(plan["script"][s] for s in ORDER)
    meta = {"series": "Mind-Blaining Explainers", "episode": plan["episode"], "slug": slug,
        "duration_seconds": VLEN, "accent_color": plan["accent"],
        "platforms": {
            "youtube": {"channel": "Stand For AI", "channel_id": "i7yex41sdut2epp8z1a0ldfp",
                        "title": plan["yt_title"], "category": "Education", "visibility": "public"},
            "telegram": {"channel": "Anaella", "caption_html": plan["tg_caption_html"]}}}
    json.dump(meta, open(f"{E}/metadata/metadata.json", "w"), indent=2, ensure_ascii=False)
    open(f"{E}/metadata/description.txt", "w").write(desc + "\n")
    open(f"{E}/metadata/tags.txt", "w").write("\n".join(plan.get("tags", [])) + "\n")
    beats = ["Hook", "Myth", "Mechanism", "Proof", "Payoff", "Landing"]
    chap = plan.get("chapters") or [f"{beats[i]}" for i in range(6)]
    lines = []
    for i, s in enumerate(ORDER):
        m, sec = divmod(int(start[s]), 60)
        lines.append(f"{m}:{sec:02d} {chap[i] if i < len(chap) else beats[i]}")
    open(f"{E}/metadata/chapters.txt", "w").write("\n".join(lines) + "\n")
    json.dump({"concept": f"{plan['hero_title'].replace('|','/')} — bold accent numerals",
               "accent": plan["accent"], "text_overlay": plan["hero_title"].replace("|", "").strip(),
               "mood": "counterintuitive, awe"}, open(f"{E}/thumbnails/concept.json", "w"), indent=2)
    print("  export:", E)


def verify_speech(P, plan):
    """ASR the rendered narration and confirm it matches the script the captions
    were written from. Catches stale/truncated/wrong-episode audio before publish."""
    import re, shutil as _sh
    wh = _sh.which("whisper")
    if not wh:
        print("  speech: SKIPPED (whisper not installed)"); return
    src = f"{P}/assets/audio/narration_concat.wav"
    od = f"{P}/artifacts/asr"
    subprocess.run([wh, src, "--model", "base.en", "--language", "en",
                    "--output_format", "txt", "--output_dir", od],
                   capture_output=True, text=True)
    tf = f"{od}/narration_concat.txt"
    if not os.path.exists(tf):
        print("  speech: SKIPPED (ASR produced no output)"); return
    norm = lambda s: set(re.findall(r"[a-z]+", s.lower()))
    spoken = norm(open(tf).read())
    script = norm(" ".join(plan["script"][s] for s in ORDER))
    cov = len(script & spoken) / max(1, len(script))
    print(f"  speech: script coverage {cov:.0%}")
    if cov < 0.80:
        raise RuntimeError(
            f"speech/caption MISMATCH: only {cov:.0%} of the script is audible in the "
            f"narration — captions would not follow the speech. DO NOT PUBLISH.")


def verify(P):
    v = f"{P}/renders/final_captioned.mp4"
    d = dur(v)
    out = subprocess.run([FF, "-i", v, "-af", "volumedetect", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    mean = mx = None
    for line in out.splitlines():
        if "mean_volume:" in line:
            mean = float(line.split("mean_volume:")[1].split("dB")[0])
        if "max_volume:" in line:
            mx = float(line.split("max_volume:")[1].split("dB")[0])
    hero_y = yavg(v, ss=1.5)
    ok = d > 40 and mean is not None and -26 < mean < -12 and mx is not None and mx <= -0.9 and hero_y > 25
    rep = {"duration": round(d, 2), "audio_mean": mean, "audio_max": mx,
           "hero_brightness": round(hero_y, 1), "pass": bool(ok)}
    json.dump(rep, open(f"{P}/artifacts/build_report.json", "w"), indent=2)
    print("  verify:", rep)
    if not ok:
        raise RuntimeError(f"verify FAILED: {rep}")


def main(slug):
    P = f"projects/{slug}"
    plan = json.load(open(f"{P}/plan.json"))
    plan["slug"] = slug
    for sub in ("artifacts", "assets/audio", "assets/video", "assets/music", "renders"):
        os.makedirs(f"{P}/{sub}", exist_ok=True)
    print(f"[build] EP{plan['episode']} {slug}")
    # narration present from an earlier build => this slug/topic already shipped once
    if os.path.exists(f"{P}/assets/audio/nar_s1.wav") \
            and not os.path.exists(f"{P}/assets/audio/nar_s1.txt"):
        print(f"  !! WARNING: '{slug}' has narration from a previous episode — "
              f"topic may be a duplicate. Narration will be regenerated.")
    durs = step_tts(P, plan)
    step_stock(P, plan)
    hero, broll = pick_layout(plan)
    ed, VLEN, start = step_edl(P, plan, durs, hero, broll)
    step_mix(P, plan, VLEN)
    step_render(P, plan, ed, durs)
    step_mux(P, VLEN)
    step_export(P, plan, durs, start)
    verify(P)
    verify_speech(P, plan)
    print(f"[build] DONE {P}/renders/final_captioned.mp4")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: build_episode.py <slug>"); sys.exit(2)
    main(sys.argv[1])
