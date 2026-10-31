"""End-to-end run of the whole site against itself, through the same HTTP API the UI uses.

Makes a random film from logline to final cut, then runs every other tool with real inputs it generates on the way
(a portrait, a garment, a voice line, a short clip). Each step records status, seconds, providers used and the error.
Started by GET /api/studio/e2e?token=… (OPENCAP_SELFTEST), read with GET /api/studio/e2e/status?token=….
"""
from __future__ import annotations

import base64, json, os, random, subprocess, threading, time, urllib.error, urllib.request
from pathlib import Path

state: dict = {"running": False, "started": None, "finished": None, "film": None, "steps": []}
LOGLINES = [
    "A lighthouse keeper on a drowned coast receives letters from a ship that sank forty years ago.",
    "Two rival street-food vendors in Old Delhi must cook together to win back their family's stolen recipe book.",
    "A night-shift drone pilot discovers the city she patrols is a simulation that is slowly shutting down.",
    "A retired astronaut teaches her granddaughter to see the stars again after the city's lights go out.",
]


def _base() -> str:
    return f"http://127.0.0.1:{os.environ.get('PORT', '7860')}/api/studio"


def _headers() -> dict:
    pw = os.environ.get("OPENCAP_PASSWORD")
    return {"Authorization": "Basic " + base64.b64encode(f"studio:{pw}".encode()).decode()} if pw else {}


def _get(path):
    return json.loads(urllib.request.urlopen(urllib.request.Request(_base() + path, headers=_headers()), timeout=60).read())


def _post_json(path, body):
    r = urllib.request.Request(_base() + path, data=json.dumps(body).encode(), method="POST", headers={"content-type": "application/json", **_headers()})
    return json.loads(urllib.request.urlopen(r, timeout=60).read())


def _run(tool, fields, files=None, limit=1500):
    b = "e2eBOUNDARYe2e"; body = bytearray()
    for k, v in fields.items():
        for x in (v if isinstance(v, list) else [v]):
            body += f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{x}\r\n".encode()
    for k, ps in (files or {}).items():
        for p in ps:
            body += f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{p.name}\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode() + p.read_bytes() + b"\r\n"
    body += f"--{b}--\r\n".encode()
    r = urllib.request.Request(f"{_base()}/tools/{tool}/run", data=bytes(body), method="POST",
                               headers={"Content-Type": f"multipart/form-data; boundary={b}", **_headers()})
    try:
        j = json.loads(urllib.request.urlopen(r, timeout=120).read())
    except urllib.error.HTTPError as e:
        return {"status": "error", "error": f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}", "outputs": [], "usage": []}
    t0 = time.time()
    while j.get("id") and j["status"] == "running":
        if time.time() - t0 > limit:
            return {**j, "status": "error", "error": f"still running after {limit} s (gave up waiting)"}
        time.sleep(3); j = _get(f"/jobs/{j['id']}")
    return j


def _step(name, tool, fields, files=None, stage="tools"):
    t0 = time.time(); state["current"] = name
    try:
        j = _run(tool, fields, files)
    except Exception as e:
        j = {"status": "error", "error": f"{type(e).__name__}: {e}", "outputs": [], "usage": []}
    outs = j.get("outputs") or []
    notes = [o.get("text", "")[:300] for o in outs if o.get("kind") == "text" and (o.get("label") or "").lower() == "note"]
    rec = {"stage": stage, "step": name, "tool": tool, "ok": j.get("status") == "done", "seconds": round(time.time() - t0, 1),
           "providers": sorted({f"{u['cap']}:{u['provider']}" for u in j.get("usage", [])}), "outputs": len(outs),
           "first_output": next((o.get("url") for o in outs if o.get("url")), None), "error": (j.get("error") or "")[:600], "notes": notes,
           "job": j.get("id")}
    state["steps"].append(rec)
    return j, rec


def _media(j, kind=None):
    for o in j.get("outputs") or []:
        if o.get("url") and (kind is None or o.get("kind") == kind):
            return o["url"]


def _fetch(url, dst: Path):
    if not url:
        return None
    full = url if url.startswith("http") else f"http://127.0.0.1:{os.environ.get('PORT', '7860')}{url}"
    dst.write_bytes(urllib.request.urlopen(urllib.request.Request(full, headers=_headers()), timeout=120).read()); return dst


def run(work: Path):
    state.update(running=True, started=time.time(), finished=None, steps=[], film=None, current=None)
    try:
        _all(work)
    except Exception as e:
        state["steps"].append({"stage": "runner", "step": "runner crashed", "ok": False, "error": f"{type(e).__name__}: {e}"})
    state.update(running=False, finished=time.time(), current=None)


def _all(work: Path):
    from PIL import Image, ImageDraw
    work.mkdir(parents=True, exist_ok=True)
    # ---------- the film, top to bottom ----------
    logline = random.choice(LOGLINES)
    f = _post_json("/films", {"title": "E2E " + time.strftime("%H:%M"), "genre": "Drama", "logline": logline})
    fid = f["id"]; state["film"] = {"id": fid, "logline": logline}
    _step("1 Script (write from logline)", "film_script", {"film": fid, "mode": "Write from logline", "logline": logline, "scenes": "3"}, stage="film")
    _step("2 Cast", "film_cast", {"film": fid, "candidates": "2", "turnaround": "true"}, stage="film")
    _step("3 Scenes", "film_scenes", {"film": fid, "shots": "2", "seconds": "3"}, stage="film")
    _step("4 Score", "film_score", {"film": fid}, stage="film")
    fin, _ = _step("5 Final cut", "film_final", {"film": fid, "burn": "true", "director": "E2E"}, stage="film")
    film = _get(f"/films/{fid}")
    char_id = next((c.get("characterId") for c in film.get("cast", []) if c.get("characterId")), None)

    # ---------- inputs for the other tools, made with the site's own tools ----------
    pj, _ = _step("Image generation (portrait for later tools)", "image_generation", {"prompt": "studio portrait of a woman in her 30s, soft light, plain background", "count": "1"})
    person = _fetch(_media(pj, "image"), work / "person.jpg")
    gj, _ = _step("Image generation (garment)", "image_generation", {"prompt": "a red denim jacket laid flat on white, product photo", "count": "1"})
    garment = _fetch(_media(gj, "image"), work / "garment.jpg")
    if not person or not garment:  # keep going with plain stand-ins so the rest still runs
        person = person or work / "person.png"; garment = garment or work / "garment.png"
        Image.new("RGB", (768, 1024), (180, 150, 130)).save(person) if not person.exists() else None
        Image.new("RGB", (768, 768), (200, 40, 40)).save(garment) if not garment.exists() else None
    W, H = Image.open(person).size
    mask = work / "mask.png"; m = Image.new("L", (W, H), 0); ImageDraw.Draw(m).ellipse((W // 3, H // 6, 2 * W // 3, H // 2), fill=255); m.save(mask)
    vj, _ = _step("Voice", "voice", {"script": "Every ending is a door you have not opened yet.", "engine": "Auto (routed)"})
    voice = _fetch(_media(vj, "audio"), work / "voice.wav")
    clip = work / "clip.mp4"
    final_url = _media(fin, "video")
    if final_url:
        _fetch(final_url, work / "final.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(work / "final.mp4"), "-t", "8", "-c:v", "libx264", "-c:a", "aac", str(clip)])
    if not clip.exists():
        aud = ["-i", str(voice)] if voice else ["-f", "lavfi", "-i", "sine=frequency=220:duration=6"]
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(person), *aud, "-t", "6", "-vf", "scale=720:-2,format=yuv420p", "-c:v", "libx264", "-c:a", "aac", "-shortest", str(clip)])
    sheet = work / "sheet.csv"; sheet.write_text("product_name,brand,specification\nSteel Water Bottle,Acme,Keeps drinks cold for 24 hours\n")
    subs = work / "subs.srt"; subs.write_text("1\n00:00:00,000 --> 00:00:02,500\nEvery ending is a door.\n")
    img = person

    cases = [
        ("prompt_assistant", {"prompt": "a detective in rain", "medium": "video"}, {}),
        ("prompt_studio", {"template": "Product hero shot", "subject": "a watch", "details": "surface: marble, mood: luxe"}, {}),
        ("reverse_prompt", {"target": "video"}, {"media": [img]}),
        ("quality_analyzer", {"brief": "a portrait", "threshold": "7"}, {"media": [img]}),
        ("story_builder", {"brief": logline, "stage": "outline"}, {}),
        ("script_doctor", {"script": "INT. HOUSE - DAY\nANNA\nHello.\nEXT. ROAD - NIGHT\nAn explosion.", "dimensions": "Script Score"}, {}),
        ("storyboard_builder", {"story": "A man walks in. He sees a ghost. He runs.", "stage": "plan", "max_shots": "4"}, {}),
        ("budget_estimator", {"episodes": "4", "minutes": "3", "dub_langs": "1", "currency": "INR"}, {}),
        ("casting_director", {"character": "Ananya, 28, curly hair, red kurta", "count": "2", "name": "Ananya"}, {}),
        ("multi_angles", {"angles": "Front"}, {"image": [img]}),
        ("multi_shots", {"prompt": "kitchen argument", "shots": "Close-Up"}, {}),
        ("relight", {}, {"image": [img]}),
        ("age_progression", {"ages": "8"}, {"image": [img]}),
        ("reimagine_scene", {"world": "1920s Bombay"}, {"image": [img]}),
        ("skin_realism", {}, {"image": [img]}),
        ("palette_studio", {}, {"references": [garment], "target": [img]}),
        ("background_change", {"mode": "Use a background image"}, {"image": [img], "background": [garment]}),
        ("upscale", {"scale": "2"}, {"image": [garment]}),
        ("inpaint", {"prompt": "add round glasses"}, {"image": [img], "mask": [mask]}),
        ("face_swap", {"consent": "true"}, {"target": [img], "face": [img]}),
        ("virtual_try_on", {}, {"person": [person], "garments": [garment]}),
        ("model_photoshoot", {"count": "1"}, {"person": [person], "apparel": [garment]}),
        ("draw_to_paint", {}, {"sketch": [mask]}),
        ("color_grading", {"preset": "16mm Film", "temp": "20"}, {"image": [img]}),
        ("video_generation", {"prompt": "she turns and smiles", "duration": "3", "movement": "Slow Push In"}, {"image": [img]}),
        ("music", {"prompt": "calm piano, instrumental", "duration": "10"}, {}),
        ("sound_effects", {"prompt": "wooden door creaks open", "duration": "2", "variations": "1"}, {}),
        ("lip_sync", {}, {"video": [clip], "audio": [voice or clip]}),
        ("micro_ad_factory", {"product": "Air Purifier 800i", "brand": "Acme", "price": "₹9,999", "duration": "8", "aspects": "9:16"}, {"images": [garment]}),
        ("ecommerce_image_studio", {"scenario": "Flat lay", "count": "1"}, {"images": [garment]}),
        ("ecommerce_video_studio", {"scenario": "Product 360° Studio", "duration": "3"}, {"images": [garment]}),
        ("ugc_ads_studio", {"product": "Electric kettle", "duration": "6"}, {"images": [garment]}),
        ("video_batch", {"aspects": "1:1", "qc": "false", "limit": "1"}, {"sheet": [sheet]}),
        ("subtitle_creator", {"exports": ["Burned-in MP4", "SRT"], "translate": "Hindi"}, {"media": [clip]}),
        ("video_intelligence", {"mode": "Teaser", "length": "15", "keyframes": "4", "aspect": "9:16"}, {"video": [clip]}),
        ("thumbnail_creator", {"topic": logline[:60], "title": "THE LAST DOOR", "style": "Reaction Close-Up"}, {}),
        ("poster_creation", {"title": "THE LAST DOOR", "tagline": "Some endings open", "formats": ["Theatrical 2:3"]}, {"video": [clip]}),
        ("resize_adapt", {"sizes": ["Stories 9:16 (1080×1920)", "Square 1:1 (1080×1080)"], "method": "Extend canvas"}, {"image": [img]}),
        ("video_reframe", {"ratios": ["9:16"], "resolution": "480p"}, {"video": [clip]}),
        ("comics_generator", {"story": "A cat becomes king. The dogs revolt. Peace returns.", "pages": "1", "stage": "plan"}, {}),
        ("visual_explainer", {"mode": "Topic", "topic": "photosynthesis", "command": "Mind Map"}, {}),
    ]
    if char_id:
        cases.insert(9, ("expression_sheet", {"character": char_id, "expressions": ["Joy", "Anger"]}, {}))
    for tool, fields, files in cases:
        _step(tool, tool, fields, files)


def start(work: Path) -> bool:
    if state["running"]:
        return False
    threading.Thread(target=run, args=(work,), daemon=True).start()
    return True


def report() -> dict:
    steps = state["steps"]
    return {"running": state["running"], "current": state.get("current"), "film": state["film"],
            "elapsed": round((state["finished"] or time.time()) - state["started"], 1) if state["started"] else 0,
            "passed": sum(1 for s in steps if s.get("ok")), "failed": sum(1 for s in steps if not s.get("ok")), "steps": steps}
