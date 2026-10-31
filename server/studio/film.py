"""Film Studio: one project carried from script to screen.

  Script  → write from a logline, or paste/upload a screenplay; parsed into scenes, action and dialogue (Fountain)
  Cast    → every speaking role is cast (headshot candidates) and locked as a character Element with a voice
  Scenes  → each scene is broken into shots; key frames keep the cast's locked faces, then image-to-video,
            dialogue is voiced per character and laid on the scene's own audio
  Score   → a cue sheet per scene (mood, BPM, key, instruments) becomes a music cue the length of the scene, plus SFX
  Final   → title card, scenes, credits, score ducked under dialogue, subtitles (SRT + optional burn-in)

The project lives in DATA/studio/films/<id>.json (see api.Store); each stage is a normal Studio tool, so it runs as a
job with progress and history, and the Film Studio page shows the project between stages.
"""
from __future__ import annotations

import json, re
from pathlib import Path

from PIL import Image

from . import media as M
from .providers import ProviderError
from .tools import (CAST_STYLES, GEMINI_VOICES, MOVES, VIDEO_STYLES, C, F, J, S, T, ToolError, fdx, model_field, route, srt, tool, write_ass)

FILM = F("film", "Film project", "film", required=True)
GENRES = ["Drama", "Thriller", "Comedy", "Horror", "Action", "Romance", "Sci-Fi", "Fantasy", "Crime", "Mystery", "Family", "Documentary", "Musical", "Microdrama"]


# ---------- Fountain ----------

HEADING = re.compile(r"^(?:\.(?!\.)|(?:INT|EXT|EST|INT\./EXT|INT/EXT|I/E)[ .])", re.I)


def parse_fountain(text: str) -> list[dict]:
    """Scenes from a Fountain (or plain) screenplay: heading, action, dialogue [{character, line, paren}]."""
    scenes, cur = [], None
    text = text.replace("\r", "")
    if re.match(r"^\s*[A-Za-z ]+:\s", text):  # Fountain title page: key: value lines up to the first blank line
        text = text.split("\n\n", 1)[1] if "\n\n" in text else ""
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        ln = lines[i].strip()
        if HEADING.match(ln):
            cur = {"n": len(scenes) + 1, "heading": ln.lstrip(".").upper(), "action": [], "dialogue": []}; scenes.append(cur)
        elif cur is None and ln:
            cur = {"n": 1, "heading": "INT. UNKNOWN - DAY", "action": [], "dialogue": []}; scenes.append(cur); continue
        elif ln and cur is not None and re.fullmatch(r"@?[A-Z][A-Z0-9 .'\-]{1,30}(?: \(.*\))?\^?", ln) and i + 1 < len(lines) and lines[i + 1].strip():
            name = re.sub(r"\s*\(.*\)|\^|^@", "", ln).strip(); paren = ""; i += 1; said = []
            while i < len(lines) and lines[i].strip():
                t = lines[i].strip()
                if t.startswith("(") and t.endswith(")"): paren = t
                else: said.append(t)
                i += 1
            if said: cur["dialogue"].append({"character": name, "line": " ".join(said), "paren": paren, "order": len(cur["action"]) + len(cur["dialogue"])})
            continue
        elif ln and cur is not None and not ln.startswith(("Title:", "Credit:", "Author:", "Draft date:", "=", "#", "[[")):
            cur["action"].append(ln)
        i += 1
    for s in scenes:
        s["action"] = " ".join(s["action"])
    return scenes


def to_fountain(title: str, scenes: list[dict]) -> str:
    out = [f"Title: {title}", "Credit: Written with Pulse Studio", ""]
    for s in scenes:
        out += ["", s["heading"], "", s.get("action", "")]
        for d in s.get("dialogue", []):
            out += ["", d["character"].upper()] + ([d["paren"]] if d.get("paren") else []) + [d["line"]]
    return "\n".join(out) + "\n"


def _mock_screenplay(logline: str, genre: str, n: int) -> str:
    beats = ["We meet ANNA, alone, in a world that is about to change.", "A stranger, RAVI, brings news that cannot be ignored.", "Anna makes a choice and pays for it.",
             "Everything falls apart; the truth comes out.", "Anna stands in the same place, changed."]
    places = ["INT. ANNA'S APARTMENT - NIGHT", "EXT. RAILWAY PLATFORM - DAWN", "INT. OLD CINEMA - DAY", "EXT. ROOFTOP - NIGHT", "INT. ANNA'S APARTMENT - MORNING"]
    lines = [("ANNA", "I knew this day would come."), ("RAVI", "Then you know why I'm here."), ("ANNA", "Not like this."), ("RAVI", "There's no other way."), ("ANNA", "Then we start again.")]
    body = []
    for k in range(n):
        body.append(f"{places[k % 5]}\n\n{beats[k % 5]} {logline[:120] if k == 0 else ''}\n\n{lines[k % 5][0]}\n{lines[k % 5][1]}\n")
    return "Title: " + (" ".join(logline.split()[:4]).title() or "Untitled") + "\n\n" + "\n".join(body)


@tool("film_script", "1 · Script", "film", "📜", "Write or import the screenplay; it becomes scenes, action and dialogue",
      "Writes a screenplay from a logline (in Fountain), or reads one you paste or upload (.fountain, .txt, .fdx text, .pdf). Parsed into scenes with headings, action and dialogue per character; the next stages read it from the project.",
      [FILM, S("mode", "Start from", ["Write from logline", "Paste or upload a script", "Rewrite with notes"]),
       F("logline", "Logline / premise", "textarea", showIf={"mode": ["Write from logline"]}, placeholder="A night-shift nurse in Mumbai discovers her patient is her missing father."),
       F("script", "Screenplay", "textarea", showIf={"mode": ["Paste or upload a script"]}), F("script_file", "…or upload", "media", showIf={"mode": ["Paste or upload a script"]}),
       F("notes", "Rewrite notes", "textarea", showIf={"mode": ["Rewrite with notes"]}, placeholder="Tighten scene 2; give Ravi a secret"),
       S("genre", "Genre", GENRES), F("scenes", "Scenes", "slider", min=1, max=30, default=5), F("runtime", "Runtime", default="3 min"),
       F("language", "Dialogue language", default="English"), model_field("llm")],
      ["text", "json", "file"], ["llm"])
def film_script(ctx, film, mode, logline, script, script_file, notes, genre, scenes, runtime, language, model):
    f = ctx.store.film(film)
    if mode.startswith("Paste"):
        from .tools import read_text
        text = (script or "") + ("\n" + read_text(script_file) if script_file else "")
        if not text.strip():
            raise ToolError("Paste or upload a screenplay")
    else:
        base = f.get("script", "") if mode.startswith("Rewrite") else ""
        if mode.startswith("Rewrite") and not base:
            raise ToolError("This project has no script yet")
        logline = logline or f.get("logline") or f.get("title")
        ctx.progress("Writing the screenplay" if not base else "Rewriting")
        prompt = (f"Rewrite this screenplay applying these notes: {notes}\n\n{base}" if base else
                  f"Write a {genre.lower()} short screenplay, {int(scenes)} scenes, about {runtime}, from this logline: {logline}\n")
        text = ctx.router.llm(prompt + f"\nDialogue in {language}. Output ONLY the screenplay in Fountain format: scene headings (INT./EXT. PLACE - TIME), "
                              "action paragraphs, CHARACTER cues in caps followed by their dialogue. Every speaking character gets a clear first-appearance description in action (age, look, wardrobe).",
                              "You are a produced screenwriter. Visual, economical, playable scenes.", mock=_mock_screenplay(logline or "", genre, int(scenes)), **route(model))
        text = re.sub(r"^```\w*|```$", "", text.strip(), flags=re.M).strip()
    parsed = parse_fountain(text)
    if not parsed:
        raise ToolError("No scenes found. Use scene headings like INT. KITCHEN - NIGHT")
    title = (re.search(r"^Title:\s*(.+)$", text, re.M) or [None, f.get("title")])[1] or f.get("title")
    f.update(script=text, scenes=parsed, title=f.get("title") if f.get("title") not in (None, "", "Untitled film") else title, genre=genre, logline=logline or f.get("logline", ""), final=None)
    ctx.store.save_film(f)
    speakers = sorted({d["character"] for s in parsed for d in s["dialogue"]})
    rows = [{"#": s["n"], "Scene": s["heading"], "Action": s["action"][:140], "Lines": len(s["dialogue"]), "Speakers": ", ".join(sorted({d["character"] for d in s["dialogue"]}))} for s in parsed]
    return [J({"Title": f["title"], "Scenes": len(parsed), "Speaking roles": speakers}, "Script parsed", next={"tool": "film_cast", "set": {"film": film}, "label": "Next: cast it →"}),
            J(rows, "Scenes"), T(text, "Screenplay (Fountain)", copy=True),
            ("script.fountain", ctx.text_file(text, ".fountain")),
            ("script.fdx", ctx.text_file(fdx({"scenes": [{"heading": s["heading"], "action": s["action"], "summary": s["action"], "dialogue": s["dialogue"]} for s in parsed]}), ".fdx"))]


@tool("film_cast", "2 · Cast", "film", "🎭", "Cast every speaking role and lock it",
      "Finds every speaking role in the script, writes a casting description from the action lines, renders headshot candidates in your visual style and locks one per role as a character Element with a voice. Re-run a role with a different pick or description any time.",
      [FILM, S("style", "Visual style", CAST_STYLES, "Cinematic Realism"), F("candidates", "Candidates per role", "slider", min=1, max=4, default=2),
       F("picks", "Lock which candidate", help="e.g. ANNA=2, RAVI=1 (default: candidate 1)"), F("only", "Only these roles", placeholder="ANNA, RAVI"),
       F("notes", "Casting notes", "textarea", placeholder="ANNA: late 20s, short curly hair, olive raincoat"),
       F("turnaround", "Build a turnaround sheet for each lock (¾ left, profile, ¾ right)", "toggle", default=True), model_field("image")],
      ["image", "json"], ["llm", "image"])
def film_cast(ctx, film, style, candidates, picks, only, notes, turnaround, model):
    f = ctx.store.film(film)
    if not f.get("scenes"):
        raise ToolError("Write the script first (stage 1)")
    speakers = list(dict.fromkeys(d["character"] for s in f["scenes"] for d in s["dialogue"]))
    if not speakers:
        raise ToolError("The script has no dialogue cues to cast")
    want = {x.strip().upper() for x in (only or "").split(",") if x.strip()}
    pick = {k.strip().upper(): int(v) for k, v in re.findall(r"([^,=]+)=(\d+)", picks or "")}
    ctx.progress("Reading the script for character descriptions")
    action = " ".join(s["action"] for s in f["scenes"])[:6000]
    mock = {"roles": [{"name": n, "description": f"{['late 20s', '40s', '30s', 'teen', '60s'][i % 5]}, expressive eyes, {['curly dark hair', 'grey stubble', 'sharp bob', 'messy fringe', 'silver hair'][i % 5]}",
                       "wardrobe": ["olive raincoat", "linen shirt, worn jacket", "black turtleneck", "school hoodie", "shawl and spectacles"][i % 5], "gender": "female" if i % 2 == 0 else "male",
                       "voice_style": "warm, measured"} for i, n in enumerate(speakers)]}
    r = ctx.router.llm_json(f"Script action lines:\n{action}\nSpeaking roles: {speakers}\nCasting notes: {notes or '-'}\n"
                            "For each role give a visual casting description (age, ethnicity if stated, face, hair, build), wardrobe, gender and voice style. "
                            "JSON: {\"roles\":[{\"name\":\"\",\"description\":\"\",\"wardrobe\":\"\",\"gender\":\"female|male|other\",\"voice_style\":\"\"}]}", "You are a casting director.", mock=mock)
    roles = {x["name"].upper(): x for x in r.get("roles", [])}
    fem = [v for v in GEMINI_VOICES if v in ("Kore", "Aoede", "Leda", "Despina", "Autonoe", "Erinome", "Achernar", "Sulafat", "Pulcherrima", "Callirrhoe")]
    mal = [v for v in GEMINI_VOICES if v in ("Puck", "Charon", "Fenrir", "Orus", "Schedar", "Achird", "Algenib", "Iapetus", "Enceladus", "Umbriel")]
    cast = {c["name"]: c for c in f.get("cast", [])}
    out = []
    sty = "" if style == "Auto" else f"{style}. "
    for i, name in enumerate(speakers):
        if want and name.upper() not in want:
            continue
        role = roles.get(name.upper(), {"description": "", "wardrobe": ""})
        imgs = []
        for k in range(int(candidates)):
            ctx.progress(f"Casting {name} · candidate {k + 1}")
            imgs.append(ctx.router.image(f"{sty}Casting headshot of {name}: {role.get('description', '')}, wearing {role.get('wardrobe', '')}. Front-facing, neutral backdrop, soft even light, "
                                         f"genre: {f.get('genre', '')}. Candidate {k + 1}: a distinct face.", aspect="4:5", seed=101 * k + i, **route(model))[0])
        chosen = imgs[min(len(imgs), max(1, pick.get(name.upper(), 1))) - 1]
        voice = (fem if role.get("gender") == "female" else mal)[i % 10]
        prev = cast.get(name, {})
        char = ctx.store.save_character({"id": prev.get("characterId"), "name": name.title().replace(" ", ""), "description": role.get("description", ""),
                                         "wardrobe": role.get("wardrobe", ""), "voice": voice, "role": "Character", "personality": role.get("voice_style", ""), "film": film}, [chosen], front=True)
        if turnaround:  # extra angles on neutral grey make the identity lock far more robust across shots
            views = []
            for v in ("three-quarter left", "left profile", "three-quarter right"):
                ctx.progress(f"{name}: {v} view")
                views.append(ctx.router.image(f"Same person as the reference, identical face, hair and wardrobe. {v} view, head and shoulders, neutral grey background, even soft light.",
                                              aspect="4:5", refs=[chosen])[0])
            char = ctx.store.save_character({"id": char["id"]}, views)
            out.append({"path": ctx.save_img(M.grid([Image.open(p) for p in [chosen] + views], 4, (300, 375), captions=["front", "¾ left", "profile", "¾ right"])), "label": f"{name} · turnaround sheet"})
        cast[name] = {"name": name, "characterId": char["id"], "voice": voice, "description": role.get("description", ""), "wardrobe": role.get("wardrobe", ""), "ref": char["refs"][0]}
        for k, p in enumerate(imgs):
            out.append({"path": p, "label": f"{name} · candidate {k + 1}" + (" · locked" if p == chosen else "")})
    f["cast"] = list(cast.values()); f["final"] = None
    ctx.store.save_film(f)
    return [J([{"Role": c["name"], "Element": f"@{c['name'].title().replace(' ', '')}", "Voice": c["voice"], "Look": c["description"], "Wardrobe": c["wardrobe"]} for c in f["cast"]], "Cast & locks",
              next={"tool": "film_scenes", "set": {"film": film}, "label": "Next: shoot the scenes →"})] + out


def _sel(spec: str, n: int) -> list[int]:
    if not spec or spec.strip().lower() == "all":
        return list(range(1, n + 1))
    out = []
    for part in spec.split(","):
        a, _, b = part.strip().partition("-")
        if a.isdigit():
            out += list(range(int(a), int(b or a) + 1))
    return [k for k in out if 1 <= k <= n]


@tool("film_scenes", "3 · Scenes", "film", "🎬", "Shoot every scene with the locked cast",
      "Breaks each scene into shots (size, angle, movement, duration), draws key frames that keep each actor's locked face and wardrobe, animates them image-to-video with your camera grammar, voices the dialogue in each character's voice and cuts the scene.",
      [FILM, F("which", "Scenes", default="all", help="all, or 1,3-4"), F("shots", "Shots per scene", "slider", min=1, max=8, default=3),
       F("seconds", "Seconds per shot", "slider", min=2, max=10, default=4), F("animate", "Animate shots (image-to-video)", "toggle", default=True),
       F("dialogue", "Voice the dialogue", "toggle", default=True), F("lipsync", "Lip-sync close-ups", "toggle", default=False),
       S("look", "Look", VIDEO_STYLES, "Cinematic realism"), C("moves", "Preferred camera moves", MOVES, default=["Slow Push In", "Dolly In", "Static"]),
       F("restart", "Start these scenes over", "toggle", default=False, help="Off: finished shots are kept and the run continues where it stopped"),
       model_field("video", "Video model")],
      ["video", "image", "json", "text"], ["llm", "image", "video", "tts", "lipsync"])
def film_scenes(ctx, film, which, shots, seconds, animate, dialogue, lipsync, look, moves, model, restart=False):
    f = ctx.store.film(film)
    if not f.get("scenes"):
        raise ToolError("Write the script first (stage 1)")
    cast = {c["name"].upper(): c for c in f.get("cast", [])}
    ar = f.get("aspect", "16:9"); W, H = {"9:16": (1080, 1920), "1:1": (1080, 1080), "4:5": (1080, 1350), "21:9": (1920, 822)}.get(ar, (1920, 1080))
    out, cuts, notes = [], [], []
    for n in _sel(which, len(f["scenes"])):
        sc = f["scenes"][n - 1]
        ids = [cast[d["character"].upper()]["characterId"] for d in sc["dialogue"] if d["character"].upper() in cast]
        ids += [c["characterId"] for k, c in cast.items() if re.search(rf"\b{re.escape(k)}\b", sc["action"].upper()) and c["characterId"] not in ids]
        wip = sc.get("wip") or {}
        if restart or wip.get("shots") != int(shots) or wip.get("seconds") != seconds:
            wip = {"shots": int(shots), "seconds": seconds, "plan": None, "done": {}}
        if wip["plan"]:
            r = wip["plan"]; ctx.progress(f"Scene {n}: continuing from saved shots")
        else:
            ctx.progress(f"Scene {n}: shot breakdown")
            sents = [x for x in re.split(r"(?<=[.!?])\s+", sc["action"]) if x.strip()] or [sc["heading"]]
            mock = {"shots": [{"shot": ["Wide Establishing Shot", "Medium Shot", "Close-Up", "Over-the-Shoulder", "Two-Shot", "Insert Shot"][k % 6], "description": sents[k % len(sents)],
                               "camera": moves[k % len(moves)] if moves else "Static", "characters": [d["character"] for d in sc["dialogue"]][:2], "seconds": seconds} for k in range(int(shots))]}
            r = ctx.router.llm_json(f"Scene {sc['heading']}\nAction: {sc['action']}\nDialogue: {json.dumps(sc['dialogue'], ensure_ascii=False)}\n"
                                    f"Break into exactly {int(shots)} shots for a {f.get('genre', '')} film, {look}. Respect the 180° rule; open wide, cover dialogue with singles/OTS. "
                                    f"Prefer these moves: {', '.join(moves)}. JSON: {{\"shots\":[{{\"shot\":\"size/angle\",\"description\":\"what we see\",\"camera\":\"movement\",\"characters\":[\"NAME\"],\"seconds\":n}}]}}",
                                    "You are a director of photography.", mock=mock)
            wip["plan"] = r
        sc["wip"] = wip; ctx.store.save_film(f)  # every finished step is saved, so a failed run can continue
        clips, shot_rows = [], []
        for k, s in enumerate(r["shots"][: int(shots)]):
            ctx.progress(f"Scene {n} · shot {k + 1}/{len(r['shots'])}")
            dur = float(s.get("seconds") or seconds)
            d = wip["done"].get(str(k), {})
            frame, clip = _saved(ctx, d.get("frame")), _saved(ctx, d.get("clip"))
            if not clip or (animate and not d.get("animated")):
                who = [cast[c.upper()]["characterId"] for c in s.get("characters", []) if c.upper() in cast] or ids
                prompt, refs = ctx.cast(f"{s['shot']}. {sc['heading']}. {s['description']}. {look}, {f.get('genre', '')} film, cinematic lighting, consistent production design.", who[:3])
                if not frame:
                    try:
                        frame = ctx.router.image(prompt, aspect=ar, refs=refs or None, seed=n * 100 + k)[0]
                    except ProviderError as e:
                        raise ToolError(f"Scene {n} shot {k + 1}: could not draw the key frame ({e}). Your finished shots are saved: press Generate again later to continue from here.")
                    d = {"frame": ctx.url_of(frame)}; wip["done"][str(k)] = d; ctx.store.save_film(f)
                animated = False
                if animate:
                    try:
                        v = ctx.router.video(prompt + f". Camera: {s.get('camera', 'Static')}.", image=frame, aspect=ar, duration=max(2, round(dur)), audio=False, **route(model))[0]
                        clip = M.norm_clip(v, ctx.file(".mp4"), W, H, dur=dur); animated = True
                    except ProviderError as e:  # free video quota used up: keep going with a moving still, animate later
                        notes.append(f"Scene {n} shot {k + 1}: {str(e)[:160]}")
                        ctx.progress(f"Scene {n} · shot {k + 1}: video unavailable, using a moving still")
                if not animated:
                    clip = _drift(ctx, frame, W, H, dur)
                d.update(clip=ctx.url_of(clip), animated=animated); wip["done"][str(k)] = d; ctx.store.save_film(f)
            clips.append(clip)
            shot_rows.append({**s, "frame": d.get("frame"), "animated": d.get("animated", False)})
            out.append((f"Scene {n} · shot {k + 1} · {s['shot']}" + ("" if d.get("animated") or not animate else " (still)"), frame))
        cut = M.concat(clips, ctx.file(".mp4"))
        lines = []
        if dialogue and sc["dialogue"]:
            ctx.progress(f"Scene {n}: voicing dialogue")
            t = 0.6; tracks = []
            for d in sc["dialogue"]:
                c = cast.get(d["character"].upper(), {})
                a = ctx.router.tts(d["line"] + (f" {d['paren']}" if d.get("paren") else ""), voice=c.get("voice", ""))[0]
                L = M.probe(a)["duration"] or 1.5
                tracks.append((t, a)); lines.append({"start": round(t, 2), "end": round(t + L, 2), "character": d["character"], "text": d["line"]}); t += L + 0.35
            vo = _lay(ctx, tracks, max(t, M.probe(cut)["duration"]))
            if t > M.probe(cut)["duration"]:  # dialogue runs longer than the shots: hold the last frame
                cut = _extend(ctx, cut, t + 0.5)
            cut = M.mix(cut, ctx.file(".mp4"), voice=vo)
            if lipsync:
                ctx.progress(f"Scene {n}: lip sync")
                cut = ctx.router.lipsync(cut, vo)[0]
        sc.update(shots=shot_rows, cut=ctx.url_of(cut), lines=lines, duration=round(M.probe(cut)["duration"], 2))
        cuts.append((f"Scene {n} · {sc['heading']}", cut))
    f["final"] = None
    ctx.store.save_film(f)
    if notes:
        cuts.insert(0, T(f"{len(notes)} shot(s) use a moving still because video generation was unavailable (usually the free daily GPU quota). "
                         "Everything is saved: run Scenes again later with the same settings and only those shots are animated.\n\n" + "\n".join(notes), "Note"))
    return cuts + out + [J([{"#": s["n"], "Scene": s["heading"], "Cut": "✓" if s.get("cut") else "—", "Seconds": s.get("duration", "")} for s in f["scenes"]], "Scene status",
                    next={"tool": "film_score", "set": {"film": film}, "label": "Next: score it →"})]


def _saved(ctx, url):
    """A saved file from an earlier run, or None if it is missing."""
    if not url:
        return None
    try:
        return ctx.path_of(url)
    except Exception:
        return None


def _drift(ctx, img: Path, w: int, h: int, dur: float) -> Path:
    """A key frame with a slow push-in, standing in for a video clip."""
    out = ctx.file(".mp4"); fr = max(2, int(dur * 30))
    M.sh(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(img), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{dur:.3f}",
          "-vf", f"scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,crop={w * 2}:{h * 2},zoompan=z='1+0.06*on/{fr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={fr}:s={w}x{h}:fps=30,setsar=1,format=yuv420p",
          "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", "-ar", "48000", "-ac", "2", "-shortest", str(out)])
    return out


def _lay(ctx, tracks: list[tuple[float, Path]], total: float) -> Path:
    """Place audio clips at offsets on one track."""
    ins, parts = [], []
    for k, (t, p) in enumerate(tracks):
        ins += ["-i", str(p)]; parts.append(f"[{k}:a]adelay={int(t * 1000)}|{int(t * 1000)},aformat=channel_layouts=stereo[a{k}]")
    out = ctx.file(".m4a")
    M.sh(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", ";".join(parts) + ";" + "".join(f"[a{k}]" for k in range(len(tracks))) +
          f"amix=inputs={len(tracks)}:normalize=0,apad,atrim=0:{total:.2f}[o]", "-map", "[o]", "-c:a", "aac", str(out)])
    return out


def _extend(ctx, video: Path, total: float) -> Path:
    out = ctx.file(".mp4"); pad = max(0.0, total - M.probe(video)["duration"])
    M.sh(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", f"tpad=stop_mode=clone:stop_duration={pad:.2f}", "-af", f"apad=pad_dur={pad:.2f}",
          "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", str(out)])
    return out


SCORE_GUIDE = {  # music-for-picture heuristics (docs/tool-research.md §11)
    "tension": "60-90 BPM, minor, pedal tones and ostinato, low string tremolo", "action": "120-170 BPM, minor or modal, driving percussion, staccato brass",
    "sadness": "50-75 BPM, minor, sparse legato piano or strings", "joy": "110-140 BPM, major, pizzicato and bright winds", "romance": "60-85 BPM, major or Lydian, warm strings",
    "wonder": "70-100 BPM, major/Lydian, swelling pads and choir", "horror": "free time, atonal clusters, sub drones", "ad": "100-128 BPM, major, 4-bar phrases, sting on the CTA"}


@tool("film_score", "4 · Score", "film", "🎼", "A cue sheet and score for every scene, plus sound design",
      "Reads each scene's emotion and pacing into a cue sheet (mood, BPM, key, instrumentation, dynamics), generates a music cue the exact length of the cut, and adds sound-effect beds from the action.",
      [FILM, S("approach", "Approach", ["One theme, varied per scene", "Independent cue per scene", "Single track for the whole film"]),
       F("palette", "Musical palette", placeholder="Hindustani strings, analog synth pads, sparse piano"), F("reference", "Reference (sounds like)", placeholder="Hans Zimmer – Interstellar"),
       F("sfx", "Sound design (SFX beds)", "toggle", default=True), model_field("music", "Music model")],
      ["audio", "json"], ["llm", "music", "sfx"])
def film_score(ctx, film, approach, palette, reference, sfx, model):
    f = ctx.store.film(film)
    cut = [s for s in f.get("scenes", []) if s.get("cut")]
    if not cut:
        raise ToolError("Shoot at least one scene first (stage 3)")
    ctx.progress("Writing the cue sheet")
    moods = ["tense, low strings", "warm, hopeful piano", "suspenseful pulse", "driving percussion, rising", "bittersweet resolution"]
    mock = {"theme": f"{f.get('genre', 'Drama')} theme, {palette or 'orchestral'}", "cues": [{"scene": s["n"], "mood": moods[i % 5], "bpm": [72, 84, 96, 120, 68][i % 5], "key": ["D minor", "F major", "A minor", "E minor", "C major"][i % 5],
            "instruments": palette or "strings, piano, pads", "dynamics": "builds" if i % 2 else "sustains", "sfx": "room tone, distant traffic" if "INT" in s["heading"] else "wind, city ambience"} for i, s in enumerate(cut)]}
    r = ctx.router.llm_json(f"Scoring guide (emotion → BPM, mode, texture): {SCORE_GUIDE}. Score under dialogue, keep 1-4 kHz clear.\n"
                            f"Film: {f.get('title')} ({f.get('genre')}). Approach: {approach}. Palette: {palette or 'composer’s choice'}. Reference: {reference or '-'}.\n"
                            + "\n".join(f"Scene {s['n']} {s['heading']} ({s.get('duration', 0)}s): {s['action'][:300]} Dialogue: {' / '.join(d['line'] for d in s['dialogue'])[:200]}" for s in cut) +
                            "\nWrite a cue sheet. JSON: {\"theme\":\"\",\"cues\":[{\"scene\":n,\"mood\":\"\",\"bpm\":n,\"key\":\"\",\"instruments\":\"\",\"dynamics\":\"\",\"sfx\":\"ambience and spot effects\"}]}",
                            "You are a film composer and supervising sound editor.", mock=mock)
    cues = {c["scene"]: c for c in r.get("cues", [])}
    out = []
    if approach.startswith("Single"):
        total = sum(s.get("duration", 5) for s in cut)
        ctx.progress("Scoring the whole film")
        track = ctx.router.music(f"Film score, {r.get('theme')}, evolving across {len(cut)} scenes, instrumental, no vocals.", total, **route(model))[0]
        f["score"] = [{"scene": "all", "url": ctx.url_of(track), "prompt": r.get("theme")}]
        out.append(("Score · whole film", track))
    else:
        f["score"] = []
        for s in cut:
            c = cues.get(s["n"], {}); ctx.progress(f"Scene {s['n']}: cue")
            theme = f"Main theme: {r.get('theme')}. " if approach.startswith("One theme") else ""
            p = (f"Cinematic underscore. {c.get('instruments', '')}. {c.get('bpm', 90)} BPM, in {c.get('key', '')}. Mood: {c.get('mood', '')}. "
                 f"Structure: {c.get('dynamics', 'sustains')}, {int(s.get('duration', 5))} seconds. {theme}Instrumental only, leaves room for dialogue.")
            m = ctx.router.music(p, max(5, s.get("duration", 5)), **route(model))[0]
            s["score"] = ctx.url_of(m); f["score"].append({"scene": s["n"], "url": s["score"], "prompt": p})
            out.append((f"Scene {s['n']} cue · {c.get('mood', '')}", m))
            if sfx and c.get("sfx"):
                e = ctx.router.sfx(c["sfx"], min(22, max(2, s.get("duration", 5))))[0]
                s["sfx"] = ctx.url_of(e); out.append((f"Scene {s['n']} SFX · {c['sfx']}", e))
    f["final"] = None
    ctx.store.save_film(f)
    return [J(r.get("cues", []), "Cue sheet", next={"tool": "film_final", "set": {"film": film}, "label": "Next: final cut →"})] + out


@tool("film_final", "5 · Final cut", "film", "🏁", "Title, scenes, credits, mix and subtitles: the finished film",
      "Assembles the title card, every scene in order and the end credits, mixes the score under the dialogue (and SFX), writes subtitles from the dialogue timings and optionally burns them in. Exports MP4, SRT and Fountain/FDX.",
      [FILM, F("title_card", "Title card", "toggle", default=True), F("credits", "End credits", "toggle", default=True), F("music_db", "Score level (dB)", "slider", min=-30, max=-4, default=-16),
       F("sfx_db", "SFX level (dB)", "slider", min=-36, max=-6, default=-22), F("burn", "Burn in subtitles", "toggle", default=False), F("director", "Directed by", placeholder="Your name"),
       S("loudness", "Loudness target", ["-14 LUFS (YouTube, social)", "-23 LUFS (broadcast, EBU R128)", "-27 LUFS (streaming, dialogue-gated)"])],
      ["video", "file"], [])
def film_final(ctx, film, title_card, credits, music_db, sfx_db, burn, director, loudness):
    f = ctx.store.film(film)
    scenes = [s for s in f.get("scenes", []) if s.get("cut")]
    if not scenes:
        raise ToolError("Shoot at least one scene first (stage 3)")
    ar = f.get("aspect", "16:9"); W, H = {"9:16": (1080, 1920), "1:1": (1080, 1080), "4:5": (1080, 1350), "21:9": (1920, 822)}.get(ar, (1920, 1080))
    whole = next((x for x in f.get("score", []) if x.get("scene") == "all"), None)
    parts, t, cues = [], 0.0, []
    if title_card:
        card = M.overlay_title(Image.new("RGB", (W, H), (8, 8, 12)), f.get("title", ""), f"A film by {director}" if director else f.get("logline", "")[:80], where="center")
        parts.append(M.still_clip(ctx.save_img(card), ctx.file(".mp4"), W, H, 3.5)); t += 3.5
    for s in scenes:
        ctx.progress(f"Mixing scene {s['n']}")
        clip = M.norm_clip(ctx.path_of(s["cut"]), ctx.file(".mp4"), W, H)
        if s.get("score") and not whole:
            clip = M.mix(clip, ctx.file(".mp4"), music=ctx.path_of(s["score"]), music_db=music_db)
        if s.get("sfx"):
            clip = M.mix(clip, ctx.file(".mp4"), music=ctx.path_of(s["sfx"]), music_db=sfx_db)
        parts.append(clip)
        cues += [{"start": t + l["start"], "end": t + l["end"], "text": l["text"]} for l in s.get("lines", [])]
        t += M.probe(clip)["duration"]
    if credits:
        lines = [f"Directed by {director}" if director else "", "", "CAST"] + [f"{c['name'].title()} …… @{c['name'].title().replace(' ', '')}" for c in f.get("cast", [])] + ["", "Made with Pulse Studio"]
        im = Image.new("RGB", (W, H), (8, 8, 12)); from PIL import ImageDraw
        d = ImageDraw.Draw(im); fnt = M.font(int(H * 0.04), bold=False); y = H * 0.2
        for ln in lines:
            d.text(((W - d.textlength(ln, font=fnt)) / 2, y), ln, font=fnt, fill=(230, 230, 235)); y += fnt.size * 1.6
        parts.append(M.still_clip(ctx.save_img(im), ctx.file(".mp4"), W, H, 5))
    ctx.progress("Assembling")
    movie = M.concat(parts, ctx.file(".mp4"))
    if whole:
        movie = M.mix(movie, ctx.file(".mp4"), music=ctx.path_of(whole["url"]), music_db=music_db)
    ctx.progress("Loudness")
    movie = M.loudnorm(movie, ctx.file(".mp4"), float(loudness.split()[0]))
    sub = ctx.text_file(srt(cues), ".srt")
    if burn and cues:
        ctx.progress("Burning in subtitles")
        ass = ctx.text_file(write_ass(cues, "Cinema Standard", W, H, False), ".ass"); burned = ctx.file(".mp4")
        M.sh(["ffmpeg", "-v", "error", "-y", "-i", str(movie), "-vf", f"ass={ass}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "copy", "-movflags", "+faststart", str(burned)], timeout=7200)
        movie = burned
    f["final"] = {"url": ctx.url_of(movie), "srt": ctx.url_of(sub), "duration": round(M.probe(movie)["duration"], 1)}
    ctx.store.save_film(f)
    slug = re.sub(r"\W+", "-", f.get("title", "film")).strip("-").lower() or "film"
    ctx.progress("Writing the NLE hand-off")
    handoff = nle_package(ctx, f, parts, slug, W, H, sub)
    return [(f"{f.get('title')} · {f['final']['duration']}s", movie), (f"{slug}.srt", sub), (f"{slug}.fountain", ctx.text_file(to_fountain(f.get("title", ""), f["scenes"]), ".fountain")),
            (f"{slug}-nle-handoff.zip", handoff)]


def tc(sec: float, fps: int = 30) -> str:
    fr = int(round(sec * fps)); return f"{fr // (3600 * fps):02}:{fr // (60 * fps) % 60:02}:{fr // fps % 60:02}:{fr % fps:02}"


def nle_package(ctx, f: dict, parts: list[Path], slug: str, W: int, H: int, sub: Path, fps: int = 30) -> Path:
    """Zip with the cut as CMX3600 EDL and FCPXML (Final Cut Pro, DaVinci Resolve; Premiere imports both), the media and subtitles."""
    import zipfile
    from xml.sax.saxutils import escape as e
    names = [f"{k:02d}_{'title' if k == 0 and len(parts) > len(f['scenes']) else 'clip'}.mp4" for k in range(len(parts))]
    durs = [M.probe(p)["duration"] for p in parts]
    edl, rec = [f"TITLE: {f.get('title', slug).upper()}", "FCM: NON-DROP FRAME", ""], 0.0
    for k, (n, d) in enumerate(zip(names, durs), 1):
        edl += [f"{k:03d}  {('AX' + str(k))[:8]:<8} AA/V  C        {tc(0)} {tc(d)} {tc(rec)} {tc(rec + d)}", f"* FROM CLIP NAME: {n}", ""]; rec += d
    fd = f"{1}/{fps}s"
    assets = "".join(f'<asset id="r{k + 2}" name="{e(n)}" start="0s" duration="{round(d * fps)}/{fps}s" hasVideo="1" hasAudio="1" format="r1">'
                     f'<media-rep kind="original-media" src="media/{e(n)}"/></asset>' for k, (n, d) in enumerate(zip(names, durs)))
    off, clips = 0, ""
    for k, (n, d) in enumerate(zip(names, durs)):
        fr = round(d * fps); clips += f'<asset-clip ref="r{k + 2}" name="{e(n)}" offset="{off}/{fps}s" start="0s" duration="{fr}/{fps}s"/>'; off += fr
    fcp = (f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n<fcpxml version="1.10"><resources><format id="r1" name="FFVideoFormat{H}p{fps}" frameDuration="{fd}" width="{W}" height="{H}"/>'
           f'{assets}</resources><library><event name="{e(f.get("title", slug))}"><project name="{e(f.get("title", slug))}"><sequence format="r1" duration="{off}/{fps}s" tcStart="0s">'
           f'<spine>{clips}</spine></sequence></project></event></library></fcpxml>\n')
    z = ctx.file(".zip")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr(f"{slug}.edl", "\n".join(edl) + "\n"); zf.writestr(f"{slug}.fcpxml", fcp); zf.write(sub, f"{slug}.srt")
        for p, n in zip(parts, names):
            zf.write(p, f"media/{n}")
        zf.writestr("README.txt", "Import the .fcpxml into Final Cut Pro or DaVinci Resolve, or the .edl into Premiere Pro / Resolve, and relink to the media/ folder.\n")
    return z


DUB_LANGS = ["Hindi", "English", "Spanish", "Portuguese", "French", "German", "Italian", "Arabic", "Indonesian", "Japanese", "Korean", "Chinese", "Turkish", "Russian",
             "Tamil", "Telugu", "Bengali", "Marathi", "Malayalam", "Kannada", "Gujarati", "Punjabi", "Urdu", "Thai", "Vietnamese", "Filipino", "Swahili", "Polish", "Dutch"]


@tool("contextual_dubbing", "Contextual Dubbing", "post", "🌐", "Dub a finished video into another language, in context",
      "Transcribes the dialogue (or reads your SRT), adapts each line idiomatically for the target culture while keeping its length close to the original timing and its emotional beat, voices it per speaker, ducks the original dialogue under the dub and optionally re-syncs the lips. Exports the dubbed MP4 and the translated subtitles.",
      [F("video", "Video", "video", required=True), F("srt", "Source subtitles (skips transcription)", "media"), S("target", "Dub into", DUB_LANGS),
       F("context", "Context for the adaptation", "textarea", placeholder="Western microdrama, teen leads, keep slang playful"), F("voices", "Voice per speaker", placeholder="default: Kore"),
       F("keep_bg", "Original audio level (dB)", "slider", min=-40, max=0, default=-18, help="The original track stays underneath as ambience."),
       F("fit", "Fit each line to its original timing", "toggle", default=True), F("lipsync", "Lip-sync the result", "toggle", default=False)],
      ["video", "file", "json"], ["llm", "tts", "lipsync"])
def contextual_dubbing(ctx, video, srt, target, context, voices, keep_bg, fit, lipsync):
    from .tools import parse_srt, cues_from_words
    if srt:
        cues = parse_srt(srt.read_text(errors="replace"))
    else:
        if not ctx.transcribe:
            raise ToolError("Transcription is not installed on this server; upload the source SRT instead")
        ctx.progress("Transcribing")
        wav = ctx.file(".wav"); M.sh(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", str(wav)])
        cues = cues_from_words(ctx.transcribe(wav, None)["words"], "Sentence", 84)
    if not cues:
        raise ToolError("No dialogue found")
    ctx.progress(f"Adapting into {target}")
    src = [c["text"] for c in cues]
    r = ctx.router.llm_json(f"Adapt these dubbing lines into {target}. Context: {context or '-'}. Keep meaning, emotion and register; use natural local idioms, not literal translation; "
                            f"keep each line speakable in about the same time as the original (durations in seconds given). JSON: {{\"lines\":[...]}}\n"
                            + json.dumps([{"text": c["text"], "seconds": round(c["end"] - c["start"], 1)} for c in cues], ensure_ascii=False),
                            "You are a dubbing adaptation writer.", mock={"lines": [f"[{target}] {t}" for t in src]})
    lines = (r.get("lines") or []) + src[len(r.get("lines") or []):]
    total = M.probe(video)["duration"]; tracks = []
    for k, (c, line) in enumerate(zip(cues, lines)):
        ctx.progress(f"Voicing line {k + 1}/{len(cues)}")
        a = ctx.router.tts(line, voice=(voices or "Kore").split(",")[0].strip())[0]
        L, slot = M.probe(a)["duration"], max(0.4, c["end"] - c["start"])
        if fit and L > slot * 1.05:  # speed the line up (atempo ≤ 2 per pass) so it ends with the original
            fast = ctx.file(".m4a"); M.sh(["ffmpeg", "-v", "error", "-y", "-i", str(a), "-filter:a", f"atempo={min(2.0, L / slot):.3f}", str(fast)]); a = fast
        tracks.append((c["start"], a))
    dub = _lay(ctx, tracks, total)
    ctx.progress("Mixing")
    out = ctx.file(".mp4")
    M.sh(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-i", str(dub), "-filter_complex",
          f"[0:a]volume={10 ** (keep_bg / 20):.3f}[bg];[1:a]volume=1.3[d];[bg][d]amix=inputs=2:duration=first:normalize=0[a]", "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", str(out)])
    if lipsync:
        ctx.progress("Lip sync"); out = ctx.router.lipsync(out, dub)[0]
    tr = [{**c, "text": t} for c, t in zip(cues, lines)]
    return [(f"Dubbed · {target}", out), (f"{target.lower()}.srt", ctx.text_file(srt_fmt(tr), ".srt")),
            J([{"Start": round(c["start"], 2), "Original": o, target: t} for c, o, t in zip(cues, src, lines)][:200], "Adaptation")]


def srt_fmt(cues):
    return srt(cues)
