"""Studio tool catalogue: every tool's inputs, outputs and pipeline, modelled on Spark Station (see docs/sparkstation-spec.md).

A tool is a function `fn(ctx, **params)` plus a field schema that the web app renders as a form. Tools return a
list of outputs: a Path (a generated file), a (label, Path) pair, a str (text), or a dict
({kind:'json', data, label} / {kind:'text', text, label}); `next` on a dict lets the UI feed it back as an input
("edit the plan, then render"). All model calls go through ctx.router, so each tool works with any provider, and
with none (mock placeholders).
"""
from __future__ import annotations

import csv, io, json, math, random, re, textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from PIL import Image

from . import media as M
from .providers import ASPECTS, MODELS, ORDER, Router


class ToolError(Exception):
    pass


@dataclass
class Ctx:
    router: Router
    out: object
    progress: Callable[[str], None]
    characters: Callable[[], list[dict]]
    url_of: Callable[[Path], str]
    path_of: Callable[[str], Path]
    data: Path
    transcribe: Callable | None = None
    local_tts: Callable | None = None
    store: object | None = None  # film projects + characters (api.Store)

    def file(self, ext: str) -> Path:
        return self.out.path(ext)

    def save_img(self, im: Image.Image, ext=".png") -> Path:
        p = self.file(ext); im.convert("RGB").save(p) if ext in (".jpg", ".jpeg") else im.save(p); return p

    def text_file(self, text: str, ext: str) -> Path:
        p = self.file(ext); p.write_text(text, encoding="utf-8"); return p

    def cast(self, prompt: str, ids: list[str] | None = None) -> tuple[str, list[Path]]:
        """Character continuity: selected characters and @Name mentions add their locked description and reference images."""
        chars = self.characters()
        picked = [c for c in chars if c["id"] in (ids or [])]
        for c in chars:
            if c not in picked and re.search(rf"@{re.escape(c['name'])}\b", prompt, re.I):
                picked.append(c)
        refs, notes = [], []
        for c in picked:
            prompt = re.sub(rf"@{re.escape(c['name'])}\b", c["name"], prompt, flags=re.I)
            bits = [c.get("description"), f"wardrobe: {c['wardrobe']}" if c.get("wardrobe") else None, f"manner: {c['personality']}" if c.get("personality") else None]
            notes.append(f"{c['name']} ({'; '.join(b for b in bits if b)})")
            refs += [self.path_of(u) for u in c.get("refs", [])[:3]]
        if notes:
            prompt += "\nKeep these characters identical to their reference images (face, hair, build, wardrobe): " + " | ".join(notes)
        return prompt, refs


@dataclass
class Tool:
    id: str; name: str; category: str; icon: str; tagline: str; description: str
    inputs: list[dict]; outputs: list[str]; caps: list[str]; fn: Callable | None = None; link: str | None = None

    def public(self):
        return {k: getattr(self, k) for k in ("id", "name", "category", "icon", "tagline", "description", "inputs", "outputs", "caps", "link")}

    def coerce(self, values: dict[str, list]) -> dict:
        out = {}
        for f in self.inputs:
            v = values.get(f["id"]); t = f["type"]
            if t in ("image", "video", "audio", "media", "mask", "sketch"):
                out[f["id"]] = v[0] if v else None
            elif t in ("images", "characters") or (t == "chips" and isinstance(f.get("default"), list)):
                out[f["id"]] = list(v) if v else list(f.get("default") or [])
            elif not v:
                out[f["id"]] = f.get("default", "" if t in ("text", "textarea", "select", "character", "film") else None)
            elif t in ("number", "slider"):
                out[f["id"]] = float(v[0]) if v[0] != "" else f.get("default")
            elif t == "toggle":
                out[f["id"]] = v[0] in ("true", "1", "on")
            else:
                out[f["id"]] = v[0]
            if f.get("required") and out[f["id"]] in (None, "", []):
                raise ToolError(f"{f['label']} is required")
        return out


TOOLS: dict[str, Tool] = {}


def tool(id, name, category, icon, tagline, description, inputs, outputs, caps, link=None):
    def deco(fn):
        TOOLS[id] = Tool(id, name, category, icon, tagline, description, inputs, outputs, caps, fn, link)
        return fn
    return deco


# ---------- field helpers ----------

def F(id, label, type="text", **kw): return {"id": id, "label": label, "type": type, **kw}
def S(id, label, options, default=None, **kw): return F(id, label, "select", options=options, default=default if default is not None else (options[0] if isinstance(options[0], str) else options[0]["value"]), **kw)
def C(id, label, options, default=None, **kw): return F(id, label, "chips", options=options, default=default if default is not None else options[0], **kw)


def model_field(cap: str, label="Model", **kw):
    opts = [{"value": "auto", "label": "Auto (best available)"}]
    for p in ORDER:
        for m in MODELS[p].get(cap, []):
            opts.append({"value": f"{p}:{m}", "label": f"{p} · {m}"})
    return S("model", label, opts, "auto", group="Model", **kw)


def route(v: str | None) -> dict:
    if not v or v == "auto" or ":" not in v:
        return {}
    p, m = v.split(":", 1)
    return {"provider": p, "model": m}


ASPECT = ["16:9", "9:16", "1:1", "4:5", "4:3", "3:4", "21:9", "2:3"]
CHARS = F("characters", "Locked characters", "characters", default=[], help="Or type @Name in the prompt. Faces, wardrobe and manner stay constant.", group="Continuity")
IMPROVE = F("improve", "Improve prompt first", "toggle", default=False, help="Rewrites the prompt with the missing camera, lighting and pacing details before spending a render.")
QC = F("qc", "Quality check results", "toggle", default=False, help="Scores each output against the brief and locked characters.", group="Quality")


def kind_of(p: Path) -> str:
    s = p.suffix.lower()
    return "image" if s in (".png", ".jpg", ".jpeg", ".webp", ".gif") else "video" if s in (".mp4", ".webm", ".mov") else \
        "audio" if s in (".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac") else "file"


def normalize(result, url_of) -> list[dict]:
    out = []
    for r in result if isinstance(result, list) else [result]:
        if isinstance(r, Path):
            out.append({"kind": kind_of(r), "url": url_of(r), "name": r.name})
        elif isinstance(r, tuple):
            label, p = r
            out.append({"kind": kind_of(p), "url": url_of(p), "name": p.name, "label": label})
        elif isinstance(r, str):
            out.append({"kind": "text", "text": r})
        elif isinstance(r, dict):
            if isinstance(r.get("path"), Path):
                p = r.pop("path"); r = {"kind": kind_of(p), "url": url_of(p), "name": p.name, **r}
            out.append(r)
    return out


def J(data, label, **kw): return {"kind": "json", "data": data, "label": label, **kw}
def T(text, label=None, **kw): return {"kind": "text", "text": text, "label": label, **kw}


def read_text(p: Path | None) -> str:
    if not p:
        return ""
    if p.suffix.lower() == ".pdf":
        try:
            import pypdf
            return "\n".join(pg.extract_text() or "" for pg in pypdf.PdfReader(str(p)).pages)
        except ImportError:
            raise ToolError("PDF upload needs `pypdf` installed; paste the text instead")
    return p.read_text(errors="replace")


# ---------- shared services: prompt improvement, reverse prompt, QC ----------

CAMERA_BODIES = ["Auto", "ARRI Alexa 35 (Cinema)", "RED V-Raptor (Crisp digital)", "Sony Venice 2 (Clean, filmic)", "16mm Bolex (Film grain)", "iPhone (Handheld, real)", "Super 8 (Home movie)", "IMAX 70mm (Epic scale)"]
LENSES = ["Auto", "Cooke S4 (Warm, gentle)", "Zeiss Master Prime (Clean, sharp)", "Anamorphic (Oval bokeh, flares)", "Vintage Helios (Swirly bokeh)", "Macro (Extreme detail)", "Fisheye (Distorted)"]
FOCALS = ["Auto", "14mm (Ultra wide)", "24mm (Wide, environmental)", "35mm (Natural cinematic)", "50mm (Human eye)", "85mm (Portrait)", "135mm (Compressed, intimate)", "200mm (Long lens, voyeur)"]
APERTURES = ["Auto", "f/1.4 (Dreamy, shallow)", "f/2.8 (Cinematic depth)", "f/5.6 (Balanced)", "f/11 (Deep focus)"]
MOVES = ["Static", "Pan", "Tilt", "Dolly In", "Dolly Out", "Push In", "Slow Push In", "Handheld Push In", "Pull Out", "Orbit", "Orbit + Crane", "Crane Up", "Crane Down",
         "Truck Left", "Truck Right", "Track + Whip Pan", "Whip Pan", "Push + Reveal", "Continuous Zoom", "Dolly Zoom (Vertigo, not supported by every model)", "Macro Drift", "FPV Drone",
         "Aerial Flyover", "Steadicam Follow", "Pedestal Up", "Pedestal Down", "Rack Focus", "Arc 180°", "Locked-off"]
VIDEO_STYLES = ["None", "Cinematic realism", "Documentary", "Anime", "Pixar-style 3D", "Claymation", "Noir", "Music video", "Commercial gloss", "Vintage film", "Bollywood drama", "K-drama soft light", "Nollywood", "Wes Anderson symmetry", "Cyberpunk", "Fantasy epic"]


def direct_shot(p: dict, duration: float = 5) -> tuple[str, str]:
    """Camera rig → (leading cinematography clause, timed segments). Video models read cinematography first and
    garble chained moves, so one move per segment of ~2-5 s (docs/tool-research.md §1)."""
    def word(v): return v.split(" (")[0] if v and v != "Auto" else ""
    def feel(v): return v.split("(")[-1].rstrip(")").lower() if v and "(" in v else ""
    moves = [m for m in (p.get("movement") or []) if m not in ("Static", "Locked-off")] or ([p["movement"][0]] if p.get("movement") else [])
    lens = " ".join(x for x in (word(p.get("focal")), word(p.get("lens"))) if x)
    lead = ", ".join(x for x in (
        (moves[0].lower() if moves else "locked-off static shot"),
        f"on a {lens} lens" + (f" ({feel(p.get('focal'))})" if feel(p.get("focal")) else "") if lens else "",
        f"{word(p.get('aperture'))} ({feel(p.get('aperture'))})" if word(p.get("aperture")) else "",
        f"shot on {word(p.get('camera'))}, {feel(p.get('camera'))}" if word(p.get("camera")) else "") if x)
    segs = ""
    if len(moves) > 1:
        step = max(2.0, duration / len(moves))
        segs = " " + " ".join(f"[{i * step:.0f}-{min(duration, (i + 1) * step):.0f}s] {m.lower()}." for i, m in enumerate(moves))
    style = f" Style: {p['style']}." if p.get("style") and p["style"] != "None" else ""
    return lead[:1].upper() + lead[1:], segs + style


def amount(v: float) -> str:
    """Models ignore percentages; say it in words."""
    return "very subtle" if v < 25 else "subtle" if v < 45 else "moderate" if v < 70 else "strong" if v < 90 else "dramatic"


BANNED = re.compile(r"\b(8k|4k|masterpiece|ultra[- ]detailed|highly detailed|best quality|trending on artstation)\b,?\s*", re.I)


def improve_prompt(ctx: Ctx, prompt: str, medium: str = "image") -> dict:
    """Structured slots (cinematography, subject, action beats, context, style, palette, audio, negatives), rendered in the
    order video/image models read best; generic quality tokens are stripped."""
    ctx.progress("Improving prompt")
    low = prompt.lower()
    missing = [k for k, words in {"cinematography": ["shot", "lens", "mm", "angle", "close-up", "wide", "dolly", "pan"], "lighting": ["light", "lit", "sun", "neon", "shadow", "glow"],
                                  "action": ["walk", "turn", "run", "look", "move", "then", "as "], "setting": [" in ", " at ", " on "]}.items() if not any(w in low for w in words)]
    fill = {"cinematography": "Medium shot, slow push in on a 35mm lens", "lighting": "soft motivated key light from a window, gentle rim light",
            "action": "a small deliberate gesture, then a held beat", "setting": "a lived-in, specific location with tactile materials"}
    mock = {"missing": missing, "slots": {"cinematography": fill["cinematography"] if "cinematography" in missing else "", "subject": prompt, "action_beats": [fill["action"]] if "action" in missing and medium == "video" else [],
            "context": {"light": fill["lighting"] if "lighting" in missing else "", "colour": "", "material": fill["setting"] if "setting" in missing else ""}, "style": "", "palette": [], "audio": {}, "negatives": []}}
    r = ctx.router.llm_json(
        f"Medium: {medium}. Raw prompt:\n{prompt}\n\nFill every slot a professional {medium} prompt needs. Be specific (lens mm, light source and direction, materials, 3-5 palette colours); "
        "no generic quality words (4k, 8k, masterpiece, ultra-detailed). One camera move. Negatives are nouns only."
        + (" Add audio: dialogue lines (SPEAKER says \"...\"), SFX, ambience." if medium == "video" else "") +
        ' JSON: {"missing":[...],"slots":{"cinematography":"","subject":"","action_beats":[],"context":{"colour":"","material":"","light":""},"style":"","palette":[],'
        '"audio":{"dialogue":[],"sfx":"","ambient":""},"negatives":[]}}', "You are a cinematographer and prompt engineer.", mock=mock)
    s = r.get("slots", {}); ctxs = s.get("context") or {}; au = s.get("audio") or {}
    parts = [s.get("cinematography"), s.get("subject"), ", then ".join(s.get("action_beats") or []), ", ".join(x for x in (ctxs.get("light"), ctxs.get("colour"), ctxs.get("material")) if x),
             s.get("style"), ("palette: " + ", ".join(s["palette"])) if s.get("palette") else ""]
    text = ". ".join(x.strip().rstrip(".") for x in parts if x and x.strip()) + "."
    if medium == "video" and au:
        text += "".join(f" {d}" for d in au.get("dialogue") or []) + (f" SFX: {au['sfx']}." if au.get("sfx") else "") + (f" Ambient noise: {au['ambient']}." if au.get("ambient") else "")
    return {"missing": r.get("missing", []), "improved": BANNED.sub("", text).strip(), "negatives": s.get("negatives") or [], "slots": s}


QC_AXES = ["Prompt adherence", "Visual quality", "Temporal consistency", "Physics & realism", "Brand & platform fit"]
QC_RUBRIC = ("Anchors: 2 = broken (melting faces/hands, wrong subject, unreadable); 5 = usable with obvious flaws; 8 = professional, minor nitpicks; 10 = flawless. "
             "Judge only what is visible; cite frame numbers for every issue.")


def qc_score(ctx: Ctx, path: Path, brief: str, char_ids: list[str] | None = None, platform: str = "") -> dict:
    """VLM-as-judge (docs/tool-research.md §12): several frames, the brief decomposed into yes/no checks, an identity gate
    against locked characters, an anchored rubric; any failed gate fails the verdict whatever the composite."""
    ctx.progress("Quality check")
    if kind_of(path) == "video":
        dur = M.probe(path)["duration"]
        frames = [M.frame_at(path, dur * f, ctx.file(".jpg")) for f in (0.02, 0.25, 0.5, 0.75, 0.97)]
    else:
        frames = [path]
    _, refs = ctx.cast("", char_ids)
    sharp = sorted(M.sharpness(f) for f in frames)[len(frames) // 2]
    if ctx.router.s.route("vision")[0] == "mock":  # no judge available: say so instead of approving
        base = round(min(9.0, 4 + sharp / 7), 1)
        return {"scores": {k: base for k in QC_AXES}, "composite": base, "gates": {}, "checks": [], "heuristic": True,
                "issues": ["No vision model configured: this is a sharpness heuristic, not QC."] + (["Soft image; consider an upscale pass"] if base < 6.5 else []),
                "summary": "Heuristic only"}
    checks = ctx.router.llm_json(f"Brief: {brief}\nDecompose it into at most 10 atomic yes/no visual questions (entities, attributes, actions, relations, counts, on-screen text). "
                                 'JSON: {"questions":[""]}', "You write visual test cases.").get("questions", [])[:10]
    r = ctx.router.llm_json(
        f"Brief: {brief}\nPlatform: {platform or 'any'}\nImages 1-{len(frames)} are frames of the output in time order"
        + (f"; images {len(frames) + 1}+ are locked character references the people must match" if refs else "") + ".\n"
        f"1) Answer each question yes/no from the frames: {json.dumps(checks)}\n"
        + ("2) identity_match: do the people match the references (same face, hair, build)? yes/no.\n" if refs else "")
        + f"3) Score 1-10 on {QC_AXES}. {QC_RUBRIC}\n"
        'JSON: {"answers":[{"q":"","yes":true}],"identity_match":true,"scores":{axis:n},"issues":[{"frame":n,"issue":"","fix":"prompt change that avoids it"}],"summary":""}',
        "You are a strict creative QC reviewer for film and ads. Be harsh; most AI output is not an 8.", images=frames + refs[:3])
    s = {k: float(v) for k, v in (r.get("scores") or {}).items()}
    answers = r.get("answers") or []
    passed = sum(1 for a in answers if a.get("yes"))
    gates = {"adherence": f"{passed}/{len(answers)}" if answers else "n/a"}
    if refs: gates["identity"] = "pass" if r.get("identity_match") else "FAIL"
    if answers: s["Prompt adherence"] = round((s.get("Prompt adherence", 5) + 10 * passed / len(answers)) / 2, 1)
    comp = round(sum(s.values()) / max(1, len(s)), 1)
    failed = gates.get("identity") == "FAIL" or (answers and passed / len(answers) < 0.6)
    issues = [f"frame {i.get('frame')}: {i.get('issue')} → {i.get('fix')}" if isinstance(i, dict) else str(i) for i in r.get("issues", [])]
    issues += [f"✗ {a.get('q')}" for a in answers if not a.get("yes")]
    return {"scores": s, "composite": min(comp, 6.9) if failed else comp, "gates": gates, "issues": issues, "summary": r.get("summary", ""),
            "fixes": [i.get("fix") for i in r.get("issues", []) if isinstance(i, dict) and i.get("fix")]}


@tool("prompt_assistant", "Prompt Assistant", "helpers", "✨", "Fix a raw prompt before it is spent on a render",
      "Reads an unpolished prompt, lists what it is missing (camera direction, lighting, pacing) and returns a rewritten version to accept, edit or reject.",
      [F("prompt", "Raw prompt", "textarea", required=True, placeholder="a detective in the rain"), S("medium", "For", ["image", "video", "music", "voice"])],
      ["text"], ["llm"])
def t_prompt(ctx, prompt, medium):
    r = improve_prompt(ctx, prompt, medium)
    return [T(r.get("improved", ""), "Improved prompt", copy=True), J({"Missing": r.get("missing", [])}, "What the prompt was missing")]


PROMPT_TEMPLATES = {  # five-part order: cinematography, subject, action, context (colour+material+light), style
    "Cinematic portrait": "Close-up on an 85mm lens at f/1.8, eye level. {subject}, {mood} expression. Soft window key from camera left, warm rim light; {palette} palette. Kodak Vision3 500T look, fine grain.",
    "Product hero shot": "Slow push in, 100mm macro, low angle. {subject} on a {surface}. Large softbox overhead, crisp specular edge highlights, seamless backdrop. {mood} brand feel, clean commercial grade.",
    "Establishing shot": "Wide static shot on a 24mm lens from a high vantage. {location} at {time}, {weather}. Atmospheric haze, practical lights in windows. Anamorphic flare, muted teal-amber palette.",
    "Action beat": "Low-angle tracking shot on a 24mm lens. {subject} {action}, in three beats: brace, burst, land. Wet asphalt, sodium streetlight, sparks. Handheld energy, motion blur on fast limbs. SFX: impact, debris.",
    "Talking head UGC": "Selfie-style medium close-up, shot on iPhone, handheld with slight sway. {subject} talks to camera about {product}. Natural window light, bedroom background. Authentic, jump cuts. Dialogue: {subject} says \"{line}\".",
    "Food close-up": "Macro slow dolly in, 100mm. {subject}, steam rising, sauce glistening. Warm backlight through steam, dark slate surface. Rich amber palette, shallow focus. SFX: sizzle.",
    "Fantasy world": "Crane up revealing the landscape, 18mm. {feature} at {time}. Volumetric god rays, mist in valleys, mossy stone and gold leaf. Painterly, epic scale; palette of jade, gold and deep blue.",
    "Music video": "Whip pan into a medium shot, 35mm. {subject} performs in {location}. Neon magenta and cyan wash, strobing practicals, haze. High-energy music video, cut on the beat.",
}


@tool("prompt_studio", "Prompt Studio", "helpers", "📚", "Production-ready prompt templates",
      "Pick a template, fill its blanks in plain words, and get a finished prompt to send to Image or Video.",
      [S("template", "Template", list(PROMPT_TEMPLATES)), F("subject", "Subject", placeholder="a weary detective"), F("details", "Other details", "textarea", placeholder="mood: tense, lighting: neon rain, location: Mumbai alley")],
      ["text"], ["llm"])
def t_prompt_studio(ctx, template, subject, details):
    tpl = PROMPT_TEMPLATES[template]
    filled = tpl.replace("{subject}", subject or "the subject")
    kv = dict(re.findall(r"(\w+)\s*:\s*([^,\n]+)", details or ""))
    filled = re.sub(r"\{(\w+)\}", lambda m: kv.get(m.group(1), m.group(1)), filled)
    return [T(filled, "Prompt", copy=True), J({"Template": tpl}, "Template")]


@tool("reverse_prompt", "Reverse Prompt Engineer", "helpers", "🔁", "Turn any reference image or video into a working prompt",
      "Upload a still or clip; get a prompt that recreates its subject, composition, lighting, lens and style for the model you choose.",
      [F("media", "Reference image or video", "media", required=True), S("target", "Write it for", ["image", "video"]), model_field("vision", "Vision model")],
      ["text"], ["vision"])
def t_reverse(ctx, media, target, model):
    look = media
    if kind_of(media) == "video":
        look = M.frame_at(media, M.probe(media)["duration"] / 2, ctx.file(".jpg"))
    im = Image.open(look).convert("RGB"); small = im.resize((64, 64)); px = list(small.getdata())
    bright = sum(sum(p) for p in px) / len(px) / 765
    cols = M.palette([im], 4)
    mock = {"prompt": f"{'Bright, airy' if bright > .55 else 'Moody, low-key'} {'landscape' if im.width > im.height else 'portrait'} frame, colour palette {', '.join(cols)}, "
                      f"{'wide' if im.width > im.height else 'vertical'} composition, cinematic lighting, high detail", "notes": "Heuristic description (no vision model configured)."}
    r = ctx.router.llm_json(f"Write a {target} generation prompt that recreates this reference: subject, composition, camera angle, lens, lighting, colour palette, style"
                            + (", camera movement and pacing" if target == "video" else "") + ". JSON: {\"prompt\":\"...\",\"notes\":\"...\"}",
                            "You reverse-engineer prompts from images.", images=[look], mock=mock, **route(model))
    return [T(r["prompt"], "Prompt", copy=True, next={"tool": "video_generation" if target == "video" else "image_generation", "set": {"prompt": r["prompt"]}}), T(r.get("notes", ""), "Notes")]


@tool("quality_analyzer", "Quality Analyzer", "helpers", "🔍", "Check any output against the brief and locked characters",
      "Scores an image or clip on five axes (prompt adherence, physics & realism, visual quality, brand alignment, platform fit) and flags consistency issues before you publish.",
      [F("media", "Image or video to check", "media", required=True), F("brief", "Brief", "textarea", required=True), CHARS,
       S("platform", "Platform", ["Any", "YouTube", "YouTube Shorts", "Instagram", "Instagram Reels", "TikTok", "Facebook", "Facebook Stories", "LinkedIn"]),
       F("threshold", "Pass threshold", "slider", min=0, max=10, step=0.1, default=7)],
      ["json"], ["vision"])
def t_qc(ctx, media, brief, characters, platform, threshold):
    r = qc_score(ctx, media, brief, characters, platform)
    r["verdict"] = "Heuristic only (no vision model)" if r.get("heuristic") else "Approved" if r["composite"] >= threshold else "Below threshold: regenerate"
    return [J({"Composite": f"{r['composite']}/10 · {r['verdict']}", "Gates": r.get("gates"), "Scores": r.get("scores"), "Issues": r.get("issues"), "Summary": r.get("summary")}, "QC report")]


# ---------- pre-production ----------

FORMS = ["Short film", "Feature screenplay", "TV episode / pilot", "Series bible", "Microdrama series", "Vertical short", "Documentary", "Ad film", "Brand film",
         "Music video", "Art / experimental film", "Flash fiction", "Short story", "Novella", "Novel", "Stage play", "Audio drama", "Podcast fiction", "Comic script",
         "Graphic novel", "Web series", "Explainer video", "Corporate film", "Trailer script"]
STRUCTURES = ["Auto (best for the form)", "Three acts", "Save the Cat beats", "Hero's journey", "Kishōtenketsu (no conflict needed)", "Two halves around an interval",
              "Five acts", "Episodic", "Cold open + 4 acts (TV)", "Problem → solution → proof (ad)", "Vignettes / non-linear", "Nothing needs to happen (slice of life)"]


def _mock_story(brief, form, runtime):
    words = re.findall(r"[A-Za-z']+", brief)
    title = " ".join(w.capitalize() for w in words[:3]) or "Untitled"
    scenes = [{"heading": h, "summary": s, "characters": ["LEAD", "RIVAL"] if i % 2 else ["LEAD"]} for i, (h, s) in enumerate([
        ("EXT. CITY STREET - NIGHT", f"We meet the lead in their world. {brief[:120]}"),
        ("INT. APARTMENT - NIGHT", "An inciting discovery forces a choice."),
        ("EXT. ROOFTOP - DAWN", "The lead confronts the rival; the stakes become personal."),
        ("INT. WAREHOUSE - DAY", "Everything goes wrong; the lead pays a price."),
        ("EXT. CITY STREET - DAY", "A changed lead returns to the opening image."),
    ])]
    return {"title": title, "logline": f"A {form.lower()} about {brief[:160]}", "runtime": runtime, "outline": [s["summary"] for s in scenes], "scenes": scenes,
            "cast": [{"name": "LEAD", "description": "30s, determined, guarded"}, {"name": "RIVAL", "description": "40s, charming, dangerous"}],
            "wardrobe": ["LEAD: worn leather jacket, dark jeans", "RIVAL: tailored charcoal suit"], "locations": ["City street", "Apartment", "Rooftop", "Warehouse"],
            "props": ["Old photograph", "Burner phone"], "lighting_palette": "Sodium-vapour orange vs. cold teal; dawn finale in pastel gold",
            "camera_lenses": "Handheld 35mm for intimacy; locked-off 24mm wides for isolation", "review": ["Mock draft: add an API key for a real writers' room."]}


def fountain(story: dict) -> str:
    """Fountain with a full title page, numbered scenes (#n#), parentheticals and transitions."""
    import datetime
    out = [f"Title: {story['title']}", "Credit: Written by", f"Author: {story.get('author', 'Pulse Studio')}", f"Draft date: {datetime.date.today():%d %B %Y}", ""]
    for n, s in enumerate(story.get("scenes", []), 1):
        head = s["heading"].upper()
        if not re.match(r"^(INT|EXT|EST|INT\./EXT|I/E)[ .]", head): head = "." + head
        out += ["", f"{head} #{n}#", "", s.get("action") or s.get("summary", "")]
        for d in s.get("dialogue", []):
            out += ["", d["character"].upper()] + ([d["paren"] if d["paren"].startswith("(") else f"({d['paren']})"] if d.get("paren") else []) + [d["line"]]
        if s.get("transition"): out += ["", s["transition"].upper().rstrip(":") + ":"]
    return "\n".join(out) + "\n"


def fdx(story: dict) -> str:
    """Final Draft XML: title page, numbered scene headings, parentheticals, transitions."""
    from xml.sax.saxutils import escape as e
    P = lambda typ, txt, extra="": f'<Paragraph Type="{typ}"{extra}><Text>{e(txt)}</Text></Paragraph>'
    paras = []
    for n, s in enumerate(story.get("scenes", []), 1):
        paras.append(P("Scene Heading", s["heading"].upper(), f' Number="{n}"'))
        paras.append(P("Action", s.get("action") or s.get("summary", "")))
        for d in s.get("dialogue", []):
            paras.append(P("Character", d["character"].upper()))
            if d.get("paren"): paras.append(P("Parenthetical", d["paren"] if d["paren"].startswith("(") else f"({d['paren']})"))
            paras.append(P("Dialogue", d["line"]))
        if s.get("transition"): paras.append(P("Transition", s["transition"].upper()))
    title = f"<TitlePage><Content>{P('Action', story.get('title', ''))}{P('Action', 'Written by')}</Content></TitlePage>"
    return f'<?xml version="1.0" encoding="UTF-8" standalone="no" ?>\n<FinalDraft DocumentType="Script" Template="No" Version="5">\n<Content>\n' + "\n".join(paras) + f"\n</Content>\n{title}\n</FinalDraft>\n"


STRUCTURE_BEATS = {  # beat: position as a share of runtime (docs/tool-research.md §4)
    "Three acts": [("Setup", 0.0), ("Inciting incident", 0.12), ("Plot point 1", 0.25), ("Midpoint", 0.5), ("Plot point 2", 0.75), ("Climax", 0.9), ("Resolution", 0.97)],
    "Save the Cat beats": [("Opening Image", 0.0), ("Theme Stated", 0.05), ("Set-up", 0.01), ("Catalyst", 0.10), ("Debate", 0.12), ("Break into Two", 0.20), ("B Story", 0.22),
                           ("Fun and Games", 0.25), ("Midpoint", 0.50), ("Bad Guys Close In", 0.55), ("All Is Lost", 0.75), ("Dark Night of the Soul", 0.77), ("Break into Three", 0.80),
                           ("Finale", 0.82), ("Final Image", 0.99)],
    "Hero's journey": [("Ordinary World", 0.0), ("Call to Adventure", 0.08), ("Refusal", 0.12), ("Mentor", 0.17), ("Crossing the Threshold", 0.25), ("Tests, Allies, Enemies", 0.3),
                       ("Approach", 0.45), ("Ordeal", 0.5), ("Reward", 0.6), ("The Road Back", 0.75), ("Resurrection", 0.88), ("Return with the Elixir", 0.97)],
    "Kishōtenketsu (no conflict needed)": [("Ki — introduction", 0.0), ("Shō — development", 0.25), ("Ten — twist", 0.5), ("Ketsu — reconciliation", 0.75)],
    "Five acts": [("Exposition", 0.0), ("Rising action", 0.2), ("Climax", 0.45), ("Falling action", 0.65), ("Denouement", 0.85)],
    "Cold open + 4 acts (TV)": [("Cold open", 0.0), ("Act 1", 0.08), ("Act 2", 0.3), ("Act 3", 0.55), ("Act 4", 0.78)],
    "Problem → solution → proof (ad)": [("Hook", 0.0), ("Problem", 0.15), ("Solution", 0.35), ("Proof", 0.65), ("Call to action", 0.85)],
    "Two halves around an interval": [("First half setup", 0.0), ("Interval twist", 0.48), ("Second half escalation", 0.52), ("Climax", 0.88)],
}


def runtime_minutes(text: str) -> float:
    m = re.search(r"([\d.]+)\s*(h|hr|hour|m|min|minute|s|sec|second)", text or "", re.I)
    if not m: return 10.0
    v, u = float(m.group(1)), m.group(2).lower()
    return v * 60 if u.startswith("h") else v / 60 if u.startswith("s") else v


def pack_md(story: dict) -> str:
    lines = [f"# {story['title']}", "", f"**Logline:** {story.get('logline', '')}", f"**Runtime:** {story.get('runtime', '')}", "", "## Cast"]
    lines += [f"- **{c['name']}**: {c.get('description', '')}" for c in story.get("cast", [])]
    for k, label in (("wardrobe", "Wardrobe"), ("locations", "Locations"), ("props", "Props")):
        lines += ["", f"## {label}"] + [f"- {x}" for x in story.get(k, [])]
    lines += ["", "## Lighting & palette", story.get("lighting_palette", ""), "", "## Camera & lenses", story.get("camera_lenses", ""), "", "## Scenes"]
    for i, s in enumerate(story.get("scenes", []), 1):
        lines += [f"### {i}. {s['heading']}", s.get("action") or s["summary"], ""] + [f"> **{d['character']}:** {d['line']}" for d in s.get("dialogue", [])]
    return "\n".join(lines)


@tool("story_builder", "Story Builder", "preproduction", "📝", "Lock your intent, then write the script to it",
      "Reads your brief and locks form, structure, what must happen and what must never happen before anything is written. Outline first, then a draft checked against intent, plus a production pack (cast, wardrobe, locations, props, lighting, lenses, scenes). Exports Fountain, FDX, CSV, Markdown and JSON.",
      [F("brief", "Brief", "textarea", required=True, placeholder="A night-shift nurse in Mumbai discovers her patient is the man who…"),
       F("brief_file", "…or read the brief from a file", "media", help=".txt, .md, .fountain or .pdf"),
       S("form", "Form", FORMS), S("structure", "Structure", STRUCTURES), F("runtime", "Length / runtime", default="10 min"),
       F("language", "Language", default="English"), F("must", "Must happen", "textarea", group="Intent locks"), F("never", "Must never happen", "textarea", group="Intent locks"),
       S("stage", "Step", [{"value": "outline", "label": "1 · Outline (editable)"}, {"value": "draft", "label": "2 · Draft + production pack"}], "outline"),
       F("outline", "Outline to draft from", "textarea", help="Filled in from step 1; edit freely.", showIf={"stage": ["draft"]}), model_field("llm")],
      ["text", "json", "file"], ["llm"])
def t_story(ctx, brief, brief_file, form, structure, runtime, language, must, never, stage, outline, model):
    brief = (brief or "") + ("\n" + read_text(brief_file) if brief_file else "")
    intent = f"Form: {form}\nStructure: {structure}\nRuntime: {runtime}\nLanguage: {language}\nMust happen: {must or '-'}\nMust never happen: {never or '-'}"
    T_min = runtime_minutes(runtime)
    beats = STRUCTURE_BEATS.get(structure) or STRUCTURE_BEATS["Three acts"]
    unit = "s" if T_min < 2 else "min"
    targets = [(b, round(p * T_min * (60 if unit == "s" else 1), 1)) for b, p in beats]
    if stage == "outline":
        ctx.progress("Reading your intent and outlining")
        mock = _mock_story(brief, form, runtime)
        mock["beats"] = [{"beat": b, "at": at, "summary": mock["outline"][i % len(mock["outline"])]} for i, (b, at) in enumerate(targets)]
        r = ctx.router.llm_json(f"{intent}\nBrief:\n{brief}\n\nRestate the locked intent and outline the story on these beats, landing each near its target ({unit}; one page ≈ one minute): {targets}. "
                                'JSON: {"intent":{...},"title":"","logline":"","beats":[{"beat":"","at":n,"summary":""}]}',
                                "You are a story editor. Respect the intent locks absolutely.", mock=mock, **route(model))
        text = "\n".join(f"{i}. [{b.get('beat')} @ {b.get('at')}{unit}] {b.get('summary')}" for i, b in enumerate(r.get("beats", []), 1)) or "\n".join(r.get("outline", []))
        return [J({"Title": r.get("title"), "Logline": r.get("logline"), "Locked intent": r.get("intent") or intent}, "Locked intent"),
                T(text, "Outline", next={"tool": "story_builder", "set": {"stage": "draft", "outline": text, "brief": brief}})]
    ctx.progress("Drafting scene by scene")
    schema = '{"title":"","logline":"","runtime":"","scenes":[{"heading":"INT. X - DAY","summary":"","action":"","characters":[],"dialogue":[{"character":"","paren":"","line":""}],"transition":""}],"setups":[{"setup":"","plant_scene":n,"payoff_scene":n}],"cast":[{"name":"","description":""}],"wardrobe":[],"locations":[],"props":[],"lighting_palette":"","camera_lenses":"","review":["what to fix"]}'
    story = ctx.router.llm_json(f"{intent}\nBrief:\n{brief}\nOutline:\n{outline or '(write one)'}\n\nWrite the full draft, each scene with the earlier ones in context, then an independent review that checks every must/never line and every unpaid setup. About {T_min:.0f} pages total. JSON: {schema}",
                                f"You are a professional {form.lower()} writer. Write in {language}.", mock=_mock_story(brief, form, runtime), **route(model))
    ctx.progress("Building production pack and exports")
    rows = io.StringIO(); w = csv.writer(rows); w.writerow(["#", "Heading", "Summary", "Characters"])
    for i, s in enumerate(story.get("scenes", []), 1):
        w.writerow([i, s.get("heading"), s.get("summary"), ", ".join(s.get("characters", []))])
    slug = re.sub(r"\W+", "-", story.get("title", "story")).strip("-").lower() or "story"
    return [T(pack_md(story), "Draft & production pack", next={"tool": "storyboard_builder", "set": {"story": pack_md(story)}, "label": "Storyboard this"}),
            J({"Review — what to fix": story.get("review", [])}, "Independent review"),
            (f"{slug}.fountain", ctx.text_file(fountain(story), ".fountain")), (f"{slug}.fdx", ctx.text_file(fdx(story), ".fdx")),
            (f"{slug}.csv", ctx.text_file(rows.getvalue(), ".csv")), (f"{slug}.md", ctx.text_file(pack_md(story), ".md")),
            (f"{slug}.json", ctx.text_file(json.dumps(story, indent=1, ensure_ascii=False), ".json"))]


DIMENSIONS = ["Script Score", "Scoring Traceability", "Character Arc Integrity", "Setup / Payoff Ledger", "Story Timeline & Scene Utility", "Audience Retention",
              "Cliffhanger Analysis", "Emotional Heatmap", "Pacing Rhythm", "Dialogue / Action Balance", "Character Screen-Time", "Theme / Motif Consistency",
              "Genre-Convention Adherence", "Structural Beat-Mapping", "Production Footprint", "Casting Suggestions"]
GENRES = ["Drama", "Thriller", "Comedy", "Horror", "Action", "Romance", "Sci-Fi", "Fantasy", "Crime", "Documentary", "Family", "Microdrama", "Ad film"]


def script_stats(script: str) -> dict:
    """Measured, not guessed: pages, scene lengths in eighths, long scenes, dialogue/action balance, lines per character, INT/EXT, DAY/NIGHT."""
    from .film import parse_fountain
    scenes = parse_fountain(script)
    total_lines = max(1, len([l for l in script.splitlines() if l.strip()]))
    pages = script_pages(script)
    rows, per_char = [], {}
    for s in scenes:
        weight = (len(s["action"].split()) + sum(len(d["line"].split()) for d in s["dialogue"])) / max(1, len(script.split()))
        eighths = max(1, round(weight * pages * 8))
        rows.append({"#": s["n"], "scene": s["heading"], "eighths": f"{eighths // 8} {eighths % 8}/8".replace("0 ", "") if eighths % 8 else f"{eighths // 8}",
                     "int_ext": "INT" if s["heading"].startswith("INT") else "EXT" if s["heading"].startswith("EXT") else "INT/EXT",
                     "day_night": "NIGHT" if "NIGHT" in s["heading"] else "DAY" if any(k in s["heading"] for k in ("DAY", "MORNING", "AFTERNOON", "DAWN")) else "—",
                     "speakers": sorted({d["character"] for d in s["dialogue"]}), "_e": eighths})
        for d in s["dialogue"]:
            per_char[d["character"]] = per_char.get(d["character"], 0) + 1
    dw = sum(len(d["line"].split()) for s in scenes for d in s["dialogue"]); aw = sum(len(s["action"].split()) for s in scenes)
    return {"pages": pages, "scenes": len(scenes), "long_scenes (>3 pages)": [r["scene"] for r in rows if r["_e"] > 24],
            "dialogue_vs_action_words": f"{dw / max(1, dw + aw):.0%} dialogue / {aw / max(1, dw + aw):.0%} action", "lines_per_character": dict(sorted(per_char.items(), key=lambda x: -x[1])),
            "INT/EXT": {k: sum(1 for r in rows if r["int_ext"] == k) for k in ("INT", "EXT", "INT/EXT")},
            "DAY/NIGHT": {k: sum(1 for r in rows if r["day_night"] == k) for k in ("DAY", "NIGHT", "—")},
            "locations": len({re.sub(r"\s+-\s+.*$", "", r["scene"]) for r in rows}), "breakdown": [{k: v for k, v in r.items() if k != "_e"} for r in rows]}


def _mock_doctor(script: str, dims: list[str], stats: dict):
    axes = {"Structure": 72, "Pacing": 68, "Originality": 61, "Character Depth": 58, "Dialogue": 66, "Theme": 64}
    first = (stats["breakdown"] or [{"scene": "(no scenes)"}])[0]["scene"]
    return {"logline": "(add an API key for a written logline)", "synopsis": "", "grid": {k: "Fair" for k in ("Premise", "Structure", "Characterization", "Dialogue", "Production value")},
            "blacklist_style": {"overall": 6, "premise": 6, "plot": 6, "character": 5, "dialogue": 6, "setting": 6}, "verdict_script": "Consider", "verdict_writer": "Consider",
            "score": round(sum(axes.values()) / 6), "axes": [{"axis": k, "score": v, "weight": 1 / 6, "confidence": "low (heuristic)", "evidence": first, "fix": "Add an API key for line-cited notes."} for k, v in axes.items()],
            "dimensions": {d: "Heuristic only." for d in dims}, "comments": {"strengths": [], "problems": []},
            "setup_payoff": [{"thread": "Opening image", "status": "UNRESOLVED", "note": "Check that the first scene pays off by the end."}]}


@tool("script_doctor", "Script Doctor", "preproduction", "🩺", "Industry-format coverage with evidence-cited scores",
      "Studio coverage: logline, synopsis, a Poor-to-Excellent grid, Pass / Consider / Recommend for script and writer, Black List-style 1–10 scores, plus a score out of 100 on six weighted axes with cited lines (highest-leverage rewrite first), up to 16 analysis dimensions, a setup/payoff ledger, and measured stats: pages, scene lengths in eighths, dialogue/action balance, lines per character, INT/EXT and DAY/NIGHT breakdown.",
      [F("script", "Script", "textarea", placeholder="Paste a screenplay…"), F("script_file", "…or upload", "media", help=".fountain, .txt, .fdx or .pdf"),
       S("genre", "Genre", GENRES), C("dimensions", "Analysis dimensions", DIMENSIONS, default=["Script Score", "Setup / Payoff Ledger", "Pacing Rhythm", "Production Footprint"]), model_field("llm")],
      ["json"], ["llm"])
def t_doctor(ctx, script, script_file, genre, dimensions, model):
    script = (script or "") + ("\n" + read_text(script_file) if script_file else "")
    if not script.strip():
        raise ToolError("Paste or upload a script")
    stats = script_stats(script)
    ctx.progress("Reading the script")
    r = ctx.router.llm_json(
        f"Genre: {genre}\nMeasured stats: {json.dumps({k: v for k, v in stats.items() if k != 'breakdown'})}\nRun these dimensions: {', '.join(dimensions)}\nScript:\n{script[:60000]}\n\n"
        "Write studio coverage. The Black List-style overall is a holistic judgement, NOT the mean of the sub-scores. Cite quoted lines (with scene numbers) as evidence. "
        'JSON: {"logline":"","synopsis":"(about 250 words)","grid":{"Premise":"Excellent|Good|Fair|Poor","Structure":"","Characterization":"","Dialogue":"","Production value":""},'
        '"blacklist_style":{"overall":1-10,"premise":1-10,"plot":1-10,"character":1-10,"dialogue":1-10,"setting":1-10},"verdict_script":"Pass|Consider|Recommend","verdict_writer":"Pass|Consider|Recommend",'
        '"comments":{"strengths":[],"problems":[{"note":"","evidence":"scene N: quoted line","fix":""}]},'
        '"score":0-100,"axes":[{"axis":"Structure|Pacing|Originality|Character Depth|Dialogue|Theme","score":0-100,"weight":0-1,"confidence":"high|med|low","evidence":"quoted line","fix":""}],'
        '"dimensions":{name:finding},"setup_payoff":[{"thread":"","plant_scene":n,"payoff_scene":n,"status":"EARNED|UNEARNED|UNRESOLVED","note":""}]}',
        "You are a senior studio script reader.", mock=_mock_doctor(script, dimensions, stats), **route(model))
    r["axes"] = sorted(r.get("axes", []), key=lambda a: -(100 - a.get("score", 0)) * a.get("weight", 1))
    r["measured"] = stats
    return [J({"Logline": r.get("logline"), "Verdict (script / writer)": f"{r.get('verdict_script')} / {r.get('verdict_writer')}", "Grid": r.get("grid"),
               "Black List-style": r.get("blacklist_style"), "Script score": f"{r.get('score')}/100"}, "Coverage"),
            J({"Synopsis": r.get("synopsis"), "Strengths": (r.get("comments") or {}).get("strengths"), "Problems": (r.get("comments") or {}).get("problems")}, "Comments"),
            J(r.get("axes"), "Axes (highest-leverage fix first)"), J(r.get("dimensions", {}), "Dimensions"), J(r.get("setup_payoff", []), "Setup / payoff ledger"),
            J({k: v for k, v in stats.items() if k != "breakdown"}, "Measured stats", next={"tool": "budget_estimator", "set": {"description": f"{genre} script, {stats['pages']} pages, {stats['scenes']} scenes, {stats['locations']} locations"}, "label": "Budget this"}),
            J(stats["breakdown"], "Scene breakdown"), ("coverage.json", ctx.text_file(json.dumps(r, indent=1, ensure_ascii=False), ".json"))]


BOARD_STYLES = ["Pencil Sketch", "Watercolour", "Ink & Wash", "Graphic Novel", "Cinematic Photoreal"]
SHOT_TYPES = ["Wide Establishing Shot", "Medium Shot", "Close-Up", "Over-the-Shoulder", "Two-Shot", "Insert Shot", "Extreme Close-Up", "Low Angle", "High Angle", "POV"]


@tool("storyboard_builder", "Storyboard Builder", "preproduction", "🎞️", "Story → shot list → 9-panel board pages",
      "Breaks a story, script or bare concept into a shot list (cast and locations picked up automatically), draws one style frame that every panel follows, then boards one panel per shot. Redraw any panel. Export PDF, PNG pages and a CSV shot list.",
      [F("story", "Story, script or concept", "textarea", required=True), S("art_style", "Art style", BOARD_STYLES), S("aspect", "Board aspect", ["16:9", "2.39:1", "9:16", "1:1", "4:3"]),
       F("max_shots", "Max shots", "slider", min=3, max=36, default=9), CHARS,
       S("stage", "Step", [{"value": "plan", "label": "1 · Shot list (editable)"}, {"value": "board", "label": "2 · Style frame + board"}], "plan"),
       F("shots", "Shot list (JSON)", "textarea", showIf={"stage": ["board"]}, help="From step 1. Edit shots, or delete one to drop it."),
       F("redraw", "Redraw only panel #", "number", showIf={"stage": ["board"]}, help="Leave blank to draw every panel."), model_field("image", "Image model")],
      ["image", "file", "json"], ["llm", "image"])
def t_storyboard(ctx, story, art_style, aspect, max_shots, characters, stage, shots, redraw, model):
    n = int(max_shots)
    if stage == "plan" or not shots:
        ctx.progress("Breaking the story into shots")
        sizes = ["WS", "MS", "CU", "OTS", "MCU", "INSERT", "ECU", "FS"]
        mock = {"shots": [{"n": i + 1, "shot": SHOT_TYPES[i % len(SHOT_TYPES)], "shot_size": sizes[i % len(sizes)], "angle": "eye", "movement": "static" if i % 3 else "dolly in",
                           "lens_mm": [24, 35, 85, 50, 50, 100, 100, 28][i % 8], "duration_s": 3, "description": s.strip()[:160], "cast": [], "location": "", "axis_side": "A",
                           "screen_direction": "L→R" if i % 2 == 0 else "R→L", "purpose": ["establish", "react", "reveal", "insert"][i % 4]}
                          for i, s in enumerate([x for x in re.split(r"(?<=[.!?])\s+|\n+", story) if x.strip()][:n] or [story])]}
        r = ctx.router.llm_json(f"Story:\n{story}\n\nBreak into at most {n} shots. Open each scene with a wide master; cover dialogue with singles and OTS from the same side of the 180° line "
                                "(flag any deliberate crossing); consecutive shots of one subject differ by ≥30° or one shot size. "
                                'JSON: {"shots":[{"n":1,"shot":"","shot_size":"EWS|WS|FS|MS|MCU|CU|ECU|INSERT","angle":"eye|low|high|overhead|dutch|POV|OTS","movement":"static|pan|tilt|dolly in|…",'
                                '"lens_mm":35,"duration_s":3,"description":"","cast":[],"location":"","axis_side":"A|B","screen_direction":"L→R|R→L","purpose":"establish|react|reveal|insert"}]}',
                                "You are a storyboard artist and 1st AD.", mock=mock)
        txt = json.dumps(r["shots"], indent=1, ensure_ascii=False)
        return [J(r["shots"], "Shot list", next={"tool": "storyboard_builder", "set": {"stage": "board", "shots": txt}, "label": "Edit & board it"})]
    plan = json.loads(shots)
    ar = {"2.39:1": "21:9"}.get(aspect, aspect)
    ctx.progress("Drawing the style frame")
    look = f"{art_style} storyboard frame, consistent line and palette"
    base, refs = ctx.cast(story[:600], characters)
    style = ctx.router.image(f"Style frame for a film: {base}. {look}", aspect=ar, refs=refs or None, **route(model))[0]
    arts = []
    for i, s in enumerate(plan):
        if redraw and int(redraw) != i + 1:
            continue
        ctx.progress(f"Panel {i + 1}/{len(plan)}")
        geo = f" {s.get('shot_size', '')} {s.get('angle', '')} angle, {s.get('lens_mm', '')}mm, screen direction {s.get('screen_direction', '')}, camera on side {s.get('axis_side', 'A')} of the action line."
        p, r = ctx.cast(f"{s['shot']}: {s['description']}.{geo} {look}. Image 1 is the style frame: match it exactly.", characters)
        arts.append((i, ctx.router.image(p, aspect=ar, refs=[style] + r)[0]))
    imgs = [Image.open(a) for _, a in arts]
    caps = [f"{plan[i]['n']}. {plan[i]['shot']} — {plan[i]['description']}" for i, _ in arts]
    cw, chh = (480, int(480 / (ASPECTS.get(ar, (16, 9))[0] / ASPECTS.get(ar, (16, 9))[1])))
    pages = [M.grid(imgs[k:k + 9], 3, (cw, chh), captions=caps[k:k + 9]) for k in range(0, len(imgs), 9)]
    rows = io.StringIO(); w = csv.writer(rows); w.writerow(["#", "Shot", "Size", "Angle", "Movement", "Lens mm", "Duration s", "Axis", "Direction", "Description", "Cast", "Location"])
    for s in plan: w.writerow([s.get("n"), s.get("shot"), s.get("shot_size"), s.get("angle"), s.get("movement") or s.get("camera"), s.get("lens_mm"), s.get("duration_s"),
                               s.get("axis_side"), s.get("screen_direction"), s.get("description"), ", ".join(s.get("cast", [])), s.get("location")])
    return [("Style frame", style)] + [(f"Page {i + 1}", ctx.save_img(p)) for i, p in enumerate(pages)] + [(f"Panel {i + 1}", a) for i, a in arts] + \
           [("storyboard.pdf", M.to_pdf(pages, ctx.file(".pdf"))), ("shot-list.csv", ctx.text_file(rows.getvalue(), ".csv"))]


# Prices verified Oct 2026 (docs/tool-research.md §5). Compute is per generated second; labour is hours × rate.
PRICES_DATE = "2026-10"
QUALITY = {"Draft": ("Veo 3.1 Lite 720p", 0.05), "Standard": ("Veo 3.1 Fast 1080p", 0.12), "Premium": ("Kling 3.0 1080p + audio", 0.168), "Cinema": ("Veo 3.1 Standard 1080p", 0.40)}
KEEP = {"static / product": 0.6, "dialogue / lip-sync": 0.35, "action / hands / crowds": 0.25}  # share of generations that survive review
DUB = {"Standard (v1)": 0.50, "Voice + emotion kept (v2)": 2.20}  # USD per minute per language
LABOUR = {  # line: (stage, hours per finished minute, USD per hour)
    "Script & development": ("Pre-Production", 3.0, 40), "Storyboard & prompt design": ("Pre-Production", 2.0, 35), "Casting & character locks": ("Pre-Production", 0.5, 35),
    "Director / creative lead": ("People", 1.5, 60), "Editing": ("Post-Production", 2.0, 40), "Colour grading": ("Post-Production", 0.5, 45), "Sound mix": ("Post-Production", 0.75, 45),
}
FX = {"USD": 1, "INR": 83.5, "AED": 3.67, "GBP": 0.79, "EUR": 0.92}


def script_pages(text: str) -> float:
    """Screenplay pages: about 55 printed lines (≈200 words) per page; a page plays for about a minute."""
    lines = [l for l in text.splitlines() if l.strip()]
    return round(max(len(lines) * 1.6 / 55, len(text.split()) / 200), 1)


@tool("budget_estimator", "Budget Estimator", "preproduction", "💰", "Line-by-line AI production budget: compute and labour",
      "Prices generation per second by model tier, divided by the keep rate a usable shot really has (static 60%, dialogue 35%, action 25%), then adds key frames, voice, music, SFX, lip-sync, dubbing, subtitles and versions, plus labour hours (writing, boards, review of every generated clip, edit, grade, mix, direction) and contingency. Reads runtime from an uploaded script. Edit any line and recalc. CSV, Markdown and printable HTML.",
      [F("description", "Describe the project", "textarea", placeholder="8-episode microdrama, Hindi, premium look, recurring leads"), F("script_file", "…or upload the script (sets the runtime)", "media"),
       S("type", "Type", ["Film", "Ad", "Series", "Microdrama", "Music video", "Documentary"]), F("episodes", "Episodes", "number", default=1, min=1),
       F("minutes", "Minutes per episode", "number", default=5, min=0.25, step=0.25), S("quality", "Quality tier", [{"value": k, "label": f"{k} · {v[0]} · ${v[1]}/s"} for k, v in QUALITY.items()], "Standard"),
       F("dialogue_share", "Dialogue shots %", "slider", min=0, max=100, default=40), F("action_share", "Action shots %", "slider", min=0, max=100, default=10),
       F("recurring", "Recurring characters (identity drift costs retakes)", "toggle", default=True), F("lipsync", "Lip-synced dialogue", "toggle", default=False),
       F("dub_langs", "Dubbed languages", "number", default=0, min=0), S("dub_quality", "Dubbing", list(DUB)), F("sub_langs", "Subtitled languages", "number", default=1, min=0),
       F("sizes", "Extra sizes (9:16, 1:1…)", "number", default=1, min=0), F("trailers", "Trailers, teasers & recaps", "number", default=1, min=0),
       F("thumbs", "Thumbnails & posters", "number", default=3, min=0), F("review_min", "Review minutes per generated clip", "slider", min=0, max=10, default=2),
       F("contingency", "Contingency %", "slider", min=0, max=30, default=10), S("currency", "Currency", list(FX)),
       F("overrides", "Line overrides (JSON)", "textarea", help='{"Music": 500} replaces a line total; recalculates instantly.')],
      ["json", "file"], [])
def t_budget(ctx, description, script_file, type, episodes, minutes, quality, dialogue_share, action_share, recurring, lipsync, dub_langs, dub_quality, sub_langs, sizes,
             trailers, thumbs, review_min, contingency, currency, overrides):
    if script_file:
        pages = script_pages(read_text(script_file))
        minutes = pages / max(1, episodes); description = (description or "") + f" (script ≈ {pages} pages ≈ {pages:.0f} min)"
    T_min = float(episodes) * float(minutes); secs = T_min * 60
    tier, price = QUALITY[quality]
    d, a = dialogue_share / 100, min(action_share / 100, 1 - dialogue_share / 100); s = max(0.0, 1 - d - a)
    keep = s * KEEP["static / product"] + d * KEEP["dialogue / lip-sync"] + a * KEEP["action / hands / crowds"]
    keep *= 0.9 if recurring else 1
    gen_secs = secs / max(keep, 0.05)
    clips = math.ceil(gen_secs / 5)  # ~5 s per generation
    fx = FX[currency]; ov = json.loads(overrides) if overrides else {}
    rows = []
    def add(stage, kind, line, qty, unit, rate, note=""):
        amt = float(ov.get(line, qty * rate * fx))
        if qty: rows.append({"stage": stage, "type": kind, "line": line, "qty": round(qty, 2), "unit": unit, "rate": round(rate * fx, 3), "total": round(amt, 2), "note": note})
    add("Production", "compute", "AI video generation", gen_secs, "gen·s", price, f"{tier}; {secs:.0f} s finished ÷ keep {keep:.0%}")
    add("Production", "compute", "Key frames & refs", math.ceil(secs / 3.5) * 2, "image", 0.04, "2 candidates per shot")
    add("Production", "compute", "Voice-over (AI)", T_min * d + T_min * 0.2, "min", 0.08, "≈150 wpm")
    add("Production", "compute", "Music", T_min, "min", 0.15)
    add("Production", "compute", "Sound effects", T_min * 0.5, "min", 0.12)
    if lipsync: add("Production", "compute", "Lip-sync", secs * d / KEEP["dialogue / lip-sync"], "gen·s", 0.05, "estimate")
    add("Distribution", "compute", "Dubbing", T_min * dub_langs, "lang·min", DUB[dub_quality], dub_quality)
    add("Distribution", "compute", "Subtitles (STT + translation)", T_min * max(1, sub_langs), "lang·min", 0.012)
    add("Distribution", "compute", "Thumbnails & posters", thumbs * 4, "image", 0.04, "4 variants each")
    for line, (stage, h, rate) in LABOUR.items():
        add(stage, "labour", line, T_min * h, "h", rate)
    add("Post-Production", "labour", "Review of generated clips", clips * review_min / 60, "h", 36, f"{clips} clips × {review_min:.0f} min")
    add("Distribution", "labour", "Extra sizes (reframe + check)", sizes * T_min * 0.25, "h", 35, "reframing is local and free; labour only")
    add("Distribution", "labour", "Trailers, teasers & recaps", trailers * 3, "h", 40)
    labour = sum(r["total"] for r in rows if r["type"] == "labour")
    add("People", "labour", "Producer (10% of labour)", 1, "fee", labour * 0.1 / fx)
    sub = sum(r["total"] for r in rows)
    rows.append({"stage": "Contingency", "type": "", "line": f"Contingency {contingency:.0f}%", "qty": "", "unit": "", "rate": "", "total": round(sub * contingency / 100, 2), "note": ""})
    total = sum(r["total"] for r in rows); compute = sum(r["total"] for r in rows if r["type"] == "compute")
    by_stage = {st: round(sum(r["total"] for r in rows if r["stage"] == st), 2) for st in dict.fromkeys(r["stage"] for r in rows)}
    buf = io.StringIO(); w = csv.DictWriter(buf, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    md = [f"# Budget — {type} ({episodes:.0f} × {minutes:g} min, {quality})", "", f"**Total: {currency} {total:,.0f}** · compute {currency} {compute:,.0f} · prices as of {PRICES_DATE}", "",
          "| Stage | Type | Line | Qty | Unit | Rate | Total | Note |", "|---|---|---|---|---|---|---|---|"]
    md += [f"| {r['stage']} | {r['type']} | {r['line']} | {r['qty']} | {r['unit']} | {r['rate']} | {r['total']:,.0f} | {r['note']} |" for r in rows]
    html = "<html><meta charset=utf-8><style>body{font:14px system-ui;margin:40px}td,th{border-bottom:1px solid #ddd;padding:6px 10px;text-align:left}</style><body>" + \
           f"<h1>Budget — {type}</h1><p><b>Total {currency} {total:,.0f}</b> · {description or ''}</p><table><tr>" + "".join(f"<th>{k}</th>" for k in rows[0]) + "</tr>" + \
           "".join("<tr>" + "".join(f"<td>{v}</td>" for v in r.values()) + "</tr>" for r in rows) + "</table><script>print()</script></body></html>"
    return [J({"Total": f"{currency} {total:,.0f}", "Compute (models)": f"{currency} {compute:,.0f}", "Labour + contingency": f"{currency} {total - compute:,.0f}",
               "Per finished minute": f"{currency} {total / max(T_min, .01):,.0f}", "Keep rate": f"{keep:.0%} → {gen_secs:,.0f} s generated for {secs:,.0f} s used ({clips} clips)",
               "By stage": by_stage, "Prices as of": PRICES_DATE}, "Summary"),
            J(rows, "Line items"), ("budget.csv", ctx.text_file(buf.getvalue(), ".csv")), ("budget.md", ctx.text_file("\n".join(md), ".md")), ("budget-print.html", ctx.text_file(html, ".html"))]


# ---------- casting & continuity ----------

CAST_STYLES = ["Auto", "Realistic Casting", "Cinematic Realism", "Documentary Realism", "Editorial Fashion", "2D Animation", "3D Animation (Pixar-style)", "Anime", "Cartoon",
               "Comic-Book", "Storybook Illustration", "Fantasy", "Sci-Fi", "Mascot Design", "Creature Design", "Stop-Motion", "Claymation", "Concept Art", "Pixel Art", "Watercolour Portrait", "Noir"]


@tool("casting_director", "Casting Director", "casting", "🎭", "Cast a character, compare a lineup, lock your pick",
      "Describe the role (age, look, wardrobe, defining features) or give a reference; pick a style and 2, 4, 6 or 8 candidates. Review the lineup side by side, regenerate, then lock your pick as a reusable identity for every image and video.",
      [F("story", "Story or scene", "textarea"), F("character", "Character description", "textarea", required=True, placeholder="Ananya, 28, sharp eyes, short curly hair, olive raincoat…"),
       F("name", "Character name", placeholder="Ananya"), F("reference", "Reference image (optional)", "image"), S("style", "Visual style", CAST_STYLES),
       C("count", "Candidates", ["2", "4", "6", "8"], "4"), S("resolution", "Resolution", ["512", "1024", "2048"], "1024"), model_field("image")],
      ["image"], ["image", "edit"])
def t_casting(ctx, story, character, name, reference, style, count, resolution, model):
    n = int(count); out = []
    sty = "" if style == "Auto" else f"{style} style. "
    for i in range(n):
        ctx.progress(f"Candidate {i + 1}/{n}")
        p = (f"{sty}Casting headshot, front-facing, neutral background, even light. Character: {character}. Context: {story[:400]}. "
             f"Candidate {i + 1} of {n}: a distinct interpretation of the same brief.")
        img = ctx.router.image(p, aspect="4:5", refs=[reference] if reference else None, seed=i * 101, **route(model))[0]
        if int(resolution) > 1024:
            img = ctx.router.upscale(img, 2)[0]
        out.append({"path": img, "label": f"Candidate {i + 1}", "lock": {"name": name or "Character", "description": character}})
    return out


@tool("elements", "Characters & Elements", "casting", "🔒", "Five continuity locks: identity, expression, wardrobe, location, object",
      "Create named Elements with reference images (characters, wardrobe, locations, props, styles) and reference them with @Name in any prompt. They persist across projects.",
      [], [], [], link="characters")
def t_elements(ctx):
    return []


EXPRESSIONS = ["Neutral", "Joy", "Sadness", "Anger", "Fear", "Surprise", "Disgust", "Contempt", "Determination"]


@tool("expression_sheet", "Expression Continuity", "casting", "😶", "One face, nine emotional states",
      "Renders a locked character across an emotional range without reshaping the face. The sheet becomes part of the character's lock.",
      [F("character", "Character", "character", required=True), C("expressions", "Expressions", EXPRESSIONS, default=EXPRESSIONS), model_field("edit")],
      ["image"], ["edit"])
def t_expressions(ctx, character, expressions, model):
    p0, refs = ctx.cast("", [character])
    if not refs:
        raise ToolError("That character has no reference images yet")
    out = []
    for e in expressions:
        ctx.progress(e)
        out.append((e, ctx.router.image(f"Same person, identical face and wardrobe, close-up portrait expressing {e.lower()}. {p0}", aspect="1:1", refs=refs, **route(model))[0]))
    sheet = M.grid([Image.open(p) for _, p in out], 3, (400, 400), captions=[e for e, _ in out])
    return [("Expression sheet", ctx.save_img(sheet))] + out


# ---------- image suite ----------

IMG_STYLES = ["None", "Cinematic still", "Photoreal", "Editorial fashion", "Product photography", "Anime", "3D render", "Watercolour", "Oil painting", "Comic", "Concept art", "Pixel art", "Vintage film", "Noir"]
RES = ["512", "1024", "2048", "4K"]


def finish(ctx, paths: list[Path], resolution: str = "1024", fmt: str = "png") -> list[Path]:
    out = []
    for p in paths:
        if kind_of(p) != "image":
            out.append(p); continue
        im = Image.open(p)
        target = {"512": 512, "1024": 1024, "2048": 2048, "4K": 3840}.get(str(resolution), 1024)
        if max(im.size) < target * 0.9:
            p = ctx.router.upscale(p, 4 if target / max(im.size) > 2 else 2)[0]; im = Image.open(p)
        if max(im.size) > target * 1.1:
            im.thumbnail((target, target), Image.LANCZOS)
        ext = {"jpg": ".jpg", "webp": ".webp"}.get(fmt, ".png")
        if ext != p.suffix or max(im.size) != max(Image.open(p).size):
            p = ctx.save_img(im if ext == ".png" else im.convert("RGB"), ext)
        out.append(p)
    return out


@tool("image_generation", "Image Generation", "image", "🖼️", "Cinematic stills from text, references or an existing frame",
      "Text, reference image or existing frame to image across GPT Image, Flux, Imagen, Seedream, Gemini and more. @mention locked characters, pick 512px to 4K, export PNG, JPG or WEBP, and hand any result straight to Video as a first frame.",
      [F("prompt", "Prompt", "textarea", required=True, placeholder="A weary detective at dusk, neon rain, 35mm."), IMPROVE, F("negative", "Negative prompt", group="More"),
       F("references", "Reference images", "images"), CHARS, S("style", "Style preset", IMG_STYLES), S("aspect", "Aspect", ASPECT, "16:9"), S("resolution", "Resolution", RES, "1024"),
       F("count", "Images", "slider", min=1, max=4, default=2), F("seed", "Seed", "number", group="More"), S("format", "Format", ["png", "jpg", "webp"], group="More"), model_field("image"), QC],
      ["image"], ["image", "edit"])
def t_image(ctx, prompt, improve, negative, references, characters, style, aspect, resolution, count, seed, format, model, qc):
    if improve:
        prompt = improve_prompt(ctx, prompt, "image").get("improved", prompt)
    if style != "None":
        prompt += f". Style: {style}"
    prompt, refs = ctx.cast(prompt, characters)
    refs = list(references) + refs
    ctx.progress("Generating")
    imgs = finish(ctx, ctx.router.image(prompt, aspect=aspect, n=int(count), refs=refs or None, negative=negative, seed=seed, **route(model)), resolution, format)
    out: list = [{"path": p, "label": f"Take {i + 1}"} for i, p in enumerate(imgs)]
    if qc:
        for o in out:
            o["qc"] = qc_score(ctx, o["path"], prompt, characters)
    return out + [T(prompt, "Prompt used", copy=True)]


ANGLES = ["Front", "Three-quarter left", "Three-quarter right", "Profile left", "Profile right", "Back", "High angle", "Low angle", "Top-down"]


@tool("multi_angles", "Multi-Angles", "image", "🔄", "Same subject, every camera angle, identity kept",
      "One face or product, front · three-quarter · profile and more, holding identity so you can build coverage or turnaround sheets.",
      [F("image", "Subject image", "image", required=True), C("angles", "Angles", ANGLES, default=["Front", "Three-quarter left", "Profile left"]), F("notes", "Notes"), model_field("edit")],
      ["image"], ["edit"])
def t_angles(ctx, image, angles, notes, model):
    out = []
    for a in angles:
        ctx.progress(a)
        out.append((a, ctx.router.image(f"Same subject, identical identity, details and lighting, seen from a {a.lower()} camera angle. {notes or ''}", aspect="1:1", refs=[image], **route(model))[0]))
    return [("Turnaround sheet", ctx.save_img(M.grid([Image.open(p) for _, p in out], min(len(out), 3), (420, 420), captions=angles)))] + out


COVERAGE = ["Wide Establishing Shot", "Medium Shot", "Close-Up", "Over-the-Shoulder", "Two-Shot", "Insert Shot", "Extreme Close-Up", "Low Angle", "High Angle", "POV"]


@tool("multi_shots", "Multi-Shots", "image", "🎬", "Full coverage of one scene from a single prompt",
      "Generates multiple framed shots of the same scene — wide, medium, close-up, over-the-shoulder, insert — keeping cast, set and light continuous.",
      [F("prompt", "Scene", "textarea", required=True), F("image", "Key frame (optional)", "image"), CHARS, C("shots", "Coverage", COVERAGE, default=COVERAGE[:5]), S("aspect", "Aspect", ASPECT, "16:9"), model_field("image")],
      ["image"], ["image", "edit"])
def t_shots(ctx, prompt, image, characters, shots, aspect, model):
    """Wide master first; every other size uses it as Image 1, from the same side of the action line."""
    prompt, refs = ctx.cast(prompt, characters); out = []
    order = sorted(shots, key=lambda s: 0 if "Wide" in s else 1)
    master = image
    if not master:
        ctx.progress("Wide master")
        master = ctx.router.image(f"Wide establishing shot, 24mm, eye level: {prompt}. Clear geography of the set and where each character stands.", aspect=aspect, refs=refs or None, **route(model))[0]
        if "Wide Establishing Shot" in order: out.append(("Wide Establishing Shot", master)); order = [s for s in order if s != "Wide Establishing Shot"]
    for s in order:
        ctx.progress(s)
        p = ctx.router.image(f"{s} of this exact scene. Image 1 is the wide master: same set, wardrobe, props and lighting; camera stays on the same side of the action line. {prompt}",
                             aspect=aspect, refs=[master] + refs, **route(model))[0]
        out.append((s, p))
    return out


LIGHTS = ["Golden hour", "Blue hour", "Overcast soft", "Hard noon sun", "Neon night", "Candlelight", "Studio three-point", "Rembrandt", "Rim / backlight", "Moonlight", "Fluorescent office", "Firelight", "Stage spotlight"]


@tool("relight", "Relight", "image", "💡", "Daylight to golden hour with one slider",
      "Change the lighting direction, colour and mood of any frame while keeping subject, pose and composition.",
      [F("image", "Image", "image", required=True), S("light", "Lighting", LIGHTS), S("direction", "Direction", ["Auto", "Left", "Right", "Front", "Back", "Top", "Below"]),
       F("intensity", "Intensity", "slider", min=0, max=100, default=60), S("color", "Light colour", ["Neutral white", "Warm tungsten", "Golden", "Cool daylight blue", "Moonlight blue", "Neon magenta", "Teal", "Firelight orange"]), model_field("edit")],
      ["image"], ["edit"])
def t_relight(ctx, image, light, direction, intensity, color, model):
    p = f"Relight this exact image with {light.lower()} lighting{'' if direction == 'Auto' else f' from the {direction.lower()}'}, {color.lower()} light, {amount(intensity)} intensity. Keep subject, pose, composition and identity unchanged."
    return [("Relit", ctx.router.image(p, aspect=_aspect_of(image), refs=[image], **route(model))[0]), ("Original", image)]


def _aspect_of(p: Path) -> str:
    im = Image.open(p); r = im.width / im.height
    return min(ASPECTS, key=lambda a: abs(ASPECTS[a][0] / ASPECTS[a][1] - r))


@tool("age_progression", "Age Progression", "image", "⏳", "Same character, age 8 → 60",
      "Ages or de-ages a face while preserving identity: bone structure, eyes and distinguishing marks.",
      [F("image", "Portrait", "image", required=True), C("ages", "Ages", ["8", "16", "25", "40", "60", "80"], default=["8", "25", "60"]), model_field("edit")], ["image"], ["edit"])
def t_age(ctx, image, ages, model):
    out = []
    for a in ages:
        ctx.progress(f"Age {a}")
        out.append((f"Age {a}", ctx.router.image(f"The same person at age {a}. Preserve identity, bone structure, eye colour and distinguishing features; same framing and light.", aspect=_aspect_of(image), refs=[image], **route(model))[0]))
    return out


@tool("reimagine_scene", "Reimagine Scene", "image", "🌍", "Same blocking, new world",
      "Restyles a frame into a new world, era or genre while keeping composition, blocking and poses.",
      [F("image", "Image", "image", required=True), F("world", "New world", "textarea", required=True, placeholder="1920s Bombay, art deco, monsoon"),
       F("strength", "How far to push", "slider", min=10, max=100, default=60), model_field("edit")], ["image"], ["edit"])
def t_reimagine(ctx, image, world, strength, model):
    return [ctx.router.image(f"Reimagine this scene as: {world}. Keep the exact composition, camera, blocking and poses. Make a {amount(strength)} transformation.", aspect=_aspect_of(image), refs=[image], **route(model))[0]]


@tool("skin_realism", "Skin Realism", "image", "🧬", "Pore-level detail, no plastic sheen",
      "Restores natural skin texture, micro-detail and subsurface light on AI portraits without changing the face.",
      [F("image", "Portrait", "image", required=True), F("strength", "Strength", "slider", min=0, max=100, default=50), model_field("edit")], ["image"], ["edit"])
def t_skin(ctx, image, strength, model):
    return [("Realistic skin", ctx.router.image(f"Retouch for photographic realism: natural skin pores, fine hair, subtle imperfections, subsurface scattering, no plastic sheen; a {amount(strength)} retouch. Do not change identity, expression or lighting.", aspect=_aspect_of(image), refs=[image], **route(model))[0]), ("Original", image)]


@tool("palette_studio", "Palette Studio", "image", "🎨", "Establish a palette and keep every frame on it",
      "Extracts a colour palette from reference frames, and optionally re-grades a target image onto that palette.",
      [F("references", "Reference images", "images", required=True), F("colors", "Colours", "slider", min=3, max=10, default=6), F("target", "Apply to (optional)", "image"), model_field("edit")],
      ["image", "json"], ["edit"])
def t_palette(ctx, references, colors, target, model):
    cols = M.palette([Image.open(p) for p in references], int(colors))
    out = [("Palette", ctx.save_img(M.swatches(cols))), J({"Colours": cols}, "Hex codes")]
    if target:
        out.append(("Re-graded", ctx.router.image(f"Re-grade this image so its colours sit on this exact palette: {', '.join(cols)}. Keep content identical.", aspect=_aspect_of(target), refs=[target], **route(model))[0]))
    return out


@tool("background_change", "Background Change", "image", "🏞️", "Swap or remove the background",
      "Cut the subject out (transparent PNG), or place it in a new scene described in words or given as an image.",
      [F("image", "Image", "image", required=True), S("mode", "Mode", ["Remove (transparent)", "Describe a new background", "Use a background image"]),
       F("prompt", "New background", showIf={"mode": ["Describe a new background"]}), F("background", "Background image", "image", showIf={"mode": ["Use a background image"]})],
      ["image"], ["bg_remove", "edit"])
def t_bg(ctx, image, mode, prompt, background):
    cut = ctx.router.bg_remove(image)[0]
    if mode.startswith("Remove"):
        return [("Cut-out", cut)]
    if mode.startswith("Use") and background:
        bg = Image.open(background).convert("RGB"); fg = Image.open(cut).convert("RGBA")
        bg = M.smart_crop(bg, fg.width, fg.height); bg.paste(fg, (0, 0), fg)
        return [("Composite", ctx.save_img(bg))]
    return [ctx.router.image(f"Place this exact subject into a new background: {prompt}. Match perspective, light and shadows.", aspect=_aspect_of(image), refs=[image])[0]]


@tool("upscale", "Upscale", "image", "🔍", "SD frame → 4K, no artefacts",
      "2x for a quick bump or 4x for print-ready, high-DPI output, with several variations per run.",
      [F("image", "Image", "image", required=True), C("scale", "Output size", ["2", "4"], "2"), F("variations", "Variations", "slider", min=1, max=4, default=1), model_field("upscale")],
      ["image"], ["upscale"])
def t_upscale(ctx, image, scale, variations, model):
    return [(f"{scale}x · v{i + 1}", ctx.router.upscale(image, int(scale), **route(model))[0]) for i in range(int(variations))]


@tool("inpaint", "Inpaint", "image", "🖌️", "Paint a mask, describe the fix",
      "Remove wires, add a clock, place a rose: paint over the area and write a short prompt; lighting and perspective are matched.",
      [F("image", "Image", "image", required=True), F("mask", "Paint the area to change", "mask", required=True, help="Paint in white over what should change."),
       F("prompt", "What goes there", required=True, placeholder="Remove it, continue the brick wall"), model_field("inpaint")], ["image"], ["inpaint"])
def t_inpaint(ctx, image, mask, prompt, model):
    return [("Result", ctx.router.inpaint(image, mask, prompt, **route(model))[0]), ("Original", image)]


@tool("face_swap", "Face Swap", "image", "🙂", "Swap a face, keep the scene's light and expression",
      "Target image plus a reference portrait; no manual masking. Use only with the rights and consent of everyone pictured.",
      [F("target", "Target image", "image", required=True), F("face", "Reference portrait", "image", required=True),
       F("consent", "I have the rights and consent of everyone pictured", "toggle", default=False, required=True)], ["image"], ["faceswap"])
def t_faceswap(ctx, target, face, consent):
    if not consent:
        raise ToolError("Confirm you have rights and consent for these faces")
    return [("Swapped", ctx.router.faceswap(target, face)[0])]


@tool("virtual_try_on", "Virtual Try-On", "image", "👗", "Same model, every wardrobe",
      "A character photo plus one or more garment images gives a full grid of outfit variations. Upscale the keepers.",
      [F("person", "Character photo", "image", required=True), F("garments", "Garments", "images", required=True), F("poses", "Poses per garment", "slider", min=1, max=3, default=1), model_field("tryon")],
      ["image"], ["tryon"])
def t_tryon(ctx, person, garments, poses, model):
    out = []
    for i, g in enumerate(garments):
        base = person
        for k in range(int(poses)):
            ctx.progress(f"Garment {i + 1}, pose {k + 1}")
            if k:
                base = ctx.router.image("Same person, same outfit, a different natural fashion pose, full body.", aspect="3:4", refs=[out[-1][1]])[0]
            out.append((f"Look {i + 1}" + (f" · pose {k + 1}" if poses > 1 else ""), ctx.router.tryon(base, g, **route(model))[0]))
    return [("Grid", ctx.save_img(M.grid([Image.open(p) for _, p in out], min(4, len(out)), (360, 480), captions=[l for l, _ in out])))] + out


SHOOT_STYLES = ["High fashion editorial", "Golden hour outdoor", "Neon night", "High contrast B&W", "Studio white seamless", "Street style", "Luxury interior", "Beach resort",
                "Minimal pastel", "Catalogue e-commerce", "Vintage film", "Athleisure in motion"]


@tool("model_photoshoot", "Model Photoshoot", "image", "📸", "Flat product → styled on-model shoot",
      "A person reference, optional apparel and location references, a style and a photo count gives a full styled shoot in one run.",
      [F("person", "Person reference", "image", required=True, help="A single, clear, well-lit face."), F("apparel", "Apparel references", "images"),
       F("locations", "Location references", "images", help="Overrides the preset environment."), S("style", "Style", SHOOT_STYLES),
       F("count", "Photos", "slider", min=1, max=8, default=4), S("aspect", "Aspect", ["3:4", "4:5", "2:3", "1:1", "9:16", "16:9"]), model_field("edit")],
      ["image"], ["edit"])
def t_photoshoot(ctx, person, apparel, locations, style, count, aspect, model):
    shots = ["full-body hero", "three-quarter walking", "close-up detail", "seated pose", "over-the-shoulder glance", "low-angle power pose", "candid laugh", "profile"]
    out = []
    for i in range(int(count)):
        ctx.progress(f"Photo {i + 1}")
        p = f"{style} fashion photoshoot, {shots[i % len(shots)]} of the same model (identical face). Wearing the reference apparel." + (" Set in the reference location." if locations else "")
        out.append((shots[i % len(shots)].capitalize(), ctx.router.image(p, aspect=aspect, refs=[person] + list(apparel) + list(locations[:1]), **route(model))[0]))
    return out


@tool("draw_to_paint", "Draw to Paint", "image", "✏️", "Napkin sketch → finished key frame",
      "Sketch, annotate and compose on a blank canvas or over an uploaded image; AI paints your vision.",
      [F("sketch", "Canvas", "sketch", required=True), F("prompt", "Describe it (optional)", "textarea"), S("style", "Finish", IMG_STYLES, "Cinematic still"), model_field("edit")],
      ["image"], ["edit"])
def t_draw(ctx, sketch, prompt, style, model):
    p = f"Turn this sketch into a finished {style.lower()} image. Follow its composition, shapes and any written annotations exactly. {prompt or ''}"
    return [("Painted", ctx.router.image(p, aspect=_aspect_of(sketch), refs=[sketch], **route(model))[0]), ("Sketch", sketch)]


@tool("color_grading", "Color Grading", "image", "🎚️", "Teal-orange, noir, pastel and film looks",
      "Presets plus a Color Correct panel (temp, hue, saturation, contrast, split tone) and toggleable soften, bloom, halation, exposure and film grain, with a before/after compare. Optional lens instructions run an AI pass.",
      [F("image", "Image", "image", required=True), S("preset", "Preset", list(M.GRADE_PRESETS), "Cinematic"),
       F("temp", "Temp", "slider", min=-100, max=100, default=0, group="Color correct"), F("hue", "Hue", "slider", min=-100, max=100, default=0, group="Color correct"),
       F("saturation", "Saturation", "slider", min=-100, max=100, default=0, group="Color correct"), F("contrast", "Contrast", "slider", min=-100, max=100, default=0, group="Color correct"),
       F("split", "Split tone", "slider", min=0, max=100, default=0, group="Color correct"),
       F("exposure", "Exposure (stops)", "slider", min=-2, max=2, step=0.1, default=0, group="Effects"), F("soften", "Soften details", "slider", min=0, max=100, default=0, group="Effects"),
       F("bloom", "Bloom", "slider", min=0, max=100, default=0, group="Effects"), F("halation", "Halation", "slider", min=0, max=100, default=0, group="Effects"),
       F("grain", "Film grain", "slider", min=0, max=100, default=0, group="Effects"), F("vignette", "Vignette", "slider", min=0, max=100, default=0, group="Effects"),
       F("bypass", "Bleach bypass", "slider", min=0, max=100, default=0, group="Effects"), F("skin_protect", "Protect skin tones", "toggle", default=True, group="Color correct"),
       F("lens", "Lens instructions (AI pass)", placeholder="Anamorphic flare from the left window", group="Effects")],
      ["image"], ["edit"])
def t_grade(ctx, image, preset, lens, **sliders):
    base = dict(M.GRADE_PRESETS.get(preset, {}))
    for k, v in sliders.items():
        if k == "skin_protect": base[k] = 1 if v else 0
        elif v: base[k] = base.get(k, 0) + v
    src = Image.open(image)
    graded = M.grade(src, **base); gp = ctx.save_img(graded)
    if lens:
        gp = ctx.router.image(f"Apply this lens effect without changing anything else: {lens}", aspect=_aspect_of(gp), refs=[gp])[0]; graded = Image.open(gp)
    return [("Graded", gp), ("Before / after", ctx.save_img(M.side_by_side(src, graded))), J({"Applied": base}, "Grade settings")]


# ---------- video ----------

VIDEO_RES = ["480p", "720p", "1080p", "4K"]


@tool("video_generation", "Video Generation", "video", "🎥", "Directed cinematic clips across every leading video model",
      "Prompt, or prompt plus a start frame (and optional end frame or reference clip), to a clip of up to 15 s. Camera rig (body, lens, focal length, aperture), a cinematic movement library, style presets, native audio, and a multi-model run to pick the best take. Locked characters carry in.",
      [F("prompt", "Prompt", "textarea", required=True, placeholder="She turns from the window as the train passes; rain on glass.",
         snippets=["Dialogue: NAME says, \"…\"", "SFX: ", "Ambient noise: ", "golden-hour backlight", "shallow depth of field"]), IMPROVE,
       F("image", "Start frame", "image"), F("end_image", "End frame", "image"), F("ref_video", "Reference clip (style & motion)", "video"), CHARS,
       S("camera", "Camera body", CAMERA_BODIES, group="Camera rig"), S("lens", "Lens character", LENSES, group="Camera rig"), S("focal", "Focal length", FOCALS, group="Camera rig"),
       S("aperture", "Aperture", APERTURES, group="Camera rig"), C("movement", "Camera movement", MOVES, default=["Slow Push In"], group="Camera rig"), S("style", "Style preset", VIDEO_STYLES),
       S("aspect", "Aspect", ["16:9", "9:16", "21:9", "4:3", "1:1", "3:4"]), F("duration", "Duration (s)", "slider", min=2, max=15, default=5), S("resolution", "Resolution", VIDEO_RES, "1080p"),
       F("audio", "Generate audio", "toggle", default=True), model_field("video"),
       C("compare", "Multi-model run (pick the take)", [o["value"] for o in model_field("video")["options"][1:]], default=[], group="Model", help="Runs the same shot on each selected model."), QC],
      ["video"], ["video", "vision"])
def t_video(ctx, prompt, improve, image, end_image, ref_video, characters, aspect, duration, resolution, audio, model, compare, qc, **rig):
    if improve:
        prompt = improve_prompt(ctx, prompt, "video").get("improved", prompt)
    if ref_video:
        ctx.progress("Reading the reference clip")
        d = M.probe(ref_video)["duration"]
        fr = [M.frame_at(ref_video, d * f, ctx.file(".jpg")) for f in (0.1, 0.35, 0.6, 0.9)]
        prompt += ". Match the reference clip's " + ctx.router.llm("These are frames of a reference clip in order. In one sentence describe what should transfer: camera motion, edit pacing, lighting and grade. "
                                                                  "Do not describe identities, text or logos.", images=fr, mock="slow handheld drift, moody low-key light and teal-amber grade")
    lead, segs = direct_shot(rig, duration)
    prompt = f"{lead}. {prompt.rstrip('.')}.{segs}"  # cinematography first; resolution is a setting, not prose
    prompt, refs = ctx.cast(prompt, characters)
    if refs and not image:
        ctx.progress("Locking the character into a first frame")
        image = ctx.router.image(prompt, aspect=aspect, refs=refs)[0]
    runs = compare or [model]
    out = []
    for m in runs:
        ctx.progress(f"Rendering {m if m != 'auto' else ''}".strip())
        v = ctx.router.video(prompt, image=image, aspect=aspect, duration=duration, end_image=end_image, audio=audio, **route(m))[0]
        used = ctx.router.last
        o = {"path": v, "label": f"{used['provider']} · {used['model']}" if len(runs) > 1 or used["provider"] != "mock" else "Take"}
        if qc:
            o["qc"] = qc_score(ctx, v, prompt, characters)
        out.append(o)
    return out + [T(prompt, "Directed prompt", copy=True)]


# ---------- audio ----------

GEMINI_VOICES = ["Achernar", "Achird", "Algenib", "Algieba", "Alnilam", "Aoede", "Autonoe", "Callirrhoe", "Charon", "Despina", "Enceladus", "Erinome", "Fenrir", "Gacrux", "Iapetus",
                 "Kore", "Laomedeia", "Leda", "Orus", "Puck", "Pulcherrima", "Rasalgethi", "Sadachbia", "Sadaltager", "Schedar", "Sulafat", "Umbriel", "Vindemiatrix", "Zephyr", "Zubenelgenubi"]
KOKORO_VOICES = ["af_heart", "af_bella", "af_nicole", "af_sarah", "af_sky", "am_adam", "am_michael", "bf_emma", "bf_isabella", "bm_george", "bm_lewis"]
VOICE_STYLES = {"Measured": "Read in a calm, measured, evenly paced tone", "Ad Voice": "Read like an upbeat, confident commercial voice-over", "Documentary": "Read like a warm, authoritative documentary narrator",
                "News Anchor": "Read like a crisp, neutral news anchor", "Casual": "Read casually, like talking to a friend", "ASMR": "Whisper softly and slowly, close to the mic"}


@tool("voice", "Voice", "audio", "🎙️", "Studio voice-over from a script",
      "Script, voice, language and style instructions to an audio clip. 30 named voices on Gemini TTS; ElevenLabs and OpenAI voices when routed there; Kokoro runs locally for free.",
      [F("script", "Script", "textarea", required=True), S("engine", "Engine", ["Auto (routed)", "Gemini TTS", "Kokoro (local, free)"]),
       S("voice", "Voice", GEMINI_VOICES, "Kore", showIf={"engine": ["Auto (routed)", "Gemini TTS"]}), S("kvoice", "Voice", KOKORO_VOICES, showIf={"engine": ["Kokoro (local, free)"]}),
       F("language", "Language", default="English (US)"), C("preset", "Style preset", list(VOICE_STYLES), "Measured"),
       F("style", "Style instructions", default="Read aloud in a warm, welcoming tone"), F("speed", "Speed", "slider", min=0.5, max=2, step=0.05, default=1),
       S("gmodel", "Gemini model", ["gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts"], showIf={"engine": ["Gemini TTS"]})],
      ["audio"], ["tts"])
def t_voice(ctx, script, engine, voice, kvoice, language, preset, style, speed, gmodel):
    instr = f"{style or VOICE_STYLES[preset]}. Language: {language}."
    if engine.startswith("Kokoro"):
        if not ctx.local_tts:
            raise ToolError("Kokoro is not installed on this server")
        return [ctx.local_tts(script, kvoice, speed)]
    # Gemini TTS takes style as natural language ahead of the text; other engines read the script as is
    if engine == "Gemini TTS" or (engine.startswith("Auto") and ctx.router.s.route("tts")[0] == "gemini"):
        return ctx.router.tts(f"{instr}\n\n{script}", voice=voice, speed=speed, provider="gemini", model=gmodel or "gemini-3.8-flash-tts")
    return ctx.router.tts(script, voice=voice, speed=speed)


@tool("music", "Music", "audio", "🎵", "Score, jingles and full songs with vocals",
      "Describe genre, mood, instruments, BPM and key (with [0:00-0:20] timestamp sections), choose instrumental or vocals with lyrics, fixed or random seed. 30 s clips to ~3 minute songs.",
      [F("prompt", "Prompt", "textarea", required=True, placeholder="[0:00-0:20]: lo-fi intro, warm bass; [0:20-0:45]: violin and flute melody, 84 BPM, D minor",
         snippets=["[0:00-0:20]: ", "90 BPM", "in D minor", "intensity: building", "instrumental", "drop to silence before the chorus"]),
       S("tier", "Model", [{"value": "clip", "label": "Clip · 30 s"}, {"value": "pro", "label": "Pro · up to ~3 min, structure, vocals"}], "pro"),
       F("duration", "Length (s)", "slider", min=10, max=180, default=60), F("negative", "Negative prompt", placeholder="no drums"),
       S("vocals", "Vocal mode", ["Instrumental", "With vocals"]), F("lyrics", "Vocal instructions / lyrics", "textarea", showIf={"vocals": ["With vocals"]},
       placeholder="e.g. verse & chorus lyrics, vocal style, language…", help="Folded into the prompt. You can set the language here (e.g. 'in Spanish')."),
       F("seed", "Fixed seed", "number", help="Blank = random."), model_field("music")],
      ["audio", "text"], ["music"])
def t_music(ctx, prompt, tier, duration, negative, vocals, lyrics, seed, model):
    dur = min(duration, 30) if tier == "clip" else duration
    # genre, instruments, BPM/key and mood lead; structure and timing cues follow; vocals last (docs/tool-research.md §11)
    p = prompt.strip().rstrip(".") + "." + (f" Leave out: {negative}." if negative else "") + (" Instrumental only." if vocals == "Instrumental" else f"\nLyrics:\n{lyrics}" if lyrics else " With vocals.")
    out = [(f"{'Vocals' if vocals != 'Instrumental' else 'Instrumental'} · {int(dur)} s", ctx.router.music(p, dur, **route(model))[0])]
    if vocals != "Instrumental" and lyrics:
        out.append(("lyrics.txt", ctx.text_file(lyrics, ".txt")))
    return out


@tool("sound_effects", "Sound Effects", "audio", "🔊", "Foley and SFX from a description",
      "Describe the sound — thunder roll, door creak, crowd gasp — and get a clip to drop on the timeline.",
      [F("prompt", "Sound", required=True, placeholder="Heavy wooden door creaks open in a stone hall"), F("duration", "Length (s)", "slider", min=1, max=22, default=5),
       F("variations", "Variations", "slider", min=1, max=4, default=2), model_field("sfx")], ["audio"], ["sfx"])
def t_sfx(ctx, prompt, duration, variations, model):
    return [(f"Take {i + 1}", ctx.router.sfx(prompt, duration, **route(model))[0]) for i in range(int(variations))]


@tool("lip_sync", "Lip Sync", "audio", "👄", "Make a character say your line",
      "Give a clip (or a still) and a voice track; the mouth is re-animated to match. Pair with Voice for dubbing.",
      [F("video", "Video or portrait image", "media", required=True), F("audio", "Voice track", "audio", required=True), model_field("lipsync")], ["video"], ["lipsync", "video"])
def t_lipsync(ctx, video, audio, model):
    if kind_of(video) == "image":
        video = ctx.router.video("The person speaks naturally to camera, subtle head movement.", image=video, duration=min(10, max(3, M.probe(audio)["duration"])))[0]
    return [ctx.router.lipsync(video, audio, **route(model))[0]]


# ---------- ad factory ----------

PLATFORMS = ["Instagram Reels", "YouTube Shorts", "TikTok", "Facebook", "Facebook Stories", "Instagram", "YouTube", "LinkedIn"]
CATEGORIES = ["Electronics", "Food & Beverage", "Fashion", "Apparels", "Beauty", "Home Decor", "Health", "Fintech", "Auto", "Travel", "Education", "Gaming"]
TONES = ["Energetic", "Premium", "Warm", "Playful", "Trustworthy", "Bold", "Minimal", "Emotional"]
AD_STEPS = ["Product understanding", "Audience mapping", "Script & dialogue", "Model & casting", "Costume & styling", "Location & set design", "Visual creation, shot by shot", "End plate creation"]


# UI reservations per platform, as fractions of height/width: (top, bottom, sides) — docs/tool-research.md §7
SAFE = {"Instagram Reels": (0.14, 0.35, 0.06), "Facebook Stories": (0.14, 0.35, 0.06), "TikTok": (0.06, 0.20, 0.11), "YouTube Shorts": (0.10, 0.30, 0.06)}


def ad_beats(duration: float) -> list[tuple[str, float]]:
    """Short-form structure: hook (≈15%), problem, solution/demo, proof, CTA + end card (≥1.5 s)."""
    end = max(1.5, 0.15 * duration)
    roles = [("HOOK", 0.15), ("PROBLEM", 0.2), ("SOLUTION", 0.3), ("PROOF", 0.2)] if duration > 8 else [("HOOK", 0.25), ("SOLUTION", 0.4), ("PROOF", 0.2)]
    body = duration - end; tot = sum(w for _, w in roles)
    return [(r, round(body * w / tot, 2)) for r, w in roles] + [("CTA", round(end, 2))]


def micro_ad(ctx, product: str, images: list[Path], specs: str, category: str, brand: str, audience: str, platform: str, tone: str, price: str, cta: str,
             duration: float, aspects: list[str], qc: bool, threshold: float, character: str | None, end_image: Path | None = None, tag: str = "") -> list:
    from .film import _lay
    log = []
    def step(i, extra=""):
        ctx.progress(f"{tag}{i + 1}/8 · {AD_STEPS[i]}{extra}")
    step(0)
    beats = ad_beats(duration)
    default_visual = {"HOOK": f"pattern-interrupt close-up: the {product} revealed in motion", "PROBLEM": "the everyday frustration it solves, relatable and quick",
                      "SOLUTION": f"the {product} in use, clearly visible and accurate", "PROOF": "the result: a satisfied reaction, a before/after or a stat on screen", "CTA": "product hero on a clean set"}
    default_vo = {"HOOK": f"Wait — you need to see this {product}.", "PROBLEM": "Tired of the same old hassle?", "SOLUTION": f"{product}. {specs.split('.')[0] if specs else 'It just works.'}",
                  "PROOF": "People can't stop talking about it.", "CTA": f"{cta or 'Shop now'}."}
    mock = {"usp": specs.split(".")[0] if specs else f"The {product} that just works", "emotion": "confidence", "audience": audience or "urban 25-34", "platform_norms": f"{platform}: hook in 1 s, captions on",
            "talent": "late-20s, friendly, natural look", "wardrobe": "smart casual in brand colours", "set": "bright modern apartment, soft morning light", "caption": f"{brand} {product}".strip(),
            "beats": [{"role": r, "seconds": s, "visual": default_visual[r], "camera": ["Push In", "Handheld", "Slow Dolly In", "Static", "Slow Push In"][i % 5], "vo": default_vo[r],
                       "caption": {"HOOK": "WAIT FOR IT", "PROBLEM": "SOUND FAMILIAR?", "SOLUTION": product.upper()[:20], "PROOF": "THE RESULT", "CTA": (cta or "SHOP NOW").upper()}[r]} for i, (r, s) in enumerate(beats)]}
    plan = ctx.router.llm_json(
        f"Product: {product}\nBrand: {brand}\nCategory: {category}\nSpecs: {specs}\nAudience: {audience}\nPlatform: {platform}\nTone: {tone}\nLength: {duration:.0f}s\n"
        f"Beat plan (role, seconds): {beats}\nRun the pipeline: product understanding (USP, emotion), audience mapping, casting, costume, set, then each beat. "
        "HOOK must be a pattern interrupt, result-first or a direct question, with motion or a face in the first second. Each VO line must fit its beat at about 2.5 words per second. "
        "Captions are at most 4 words. JSON: {\"usp\":\"\",\"emotion\":\"\",\"audience\":\"\",\"platform_norms\":\"\",\"talent\":\"\",\"wardrobe\":\"\",\"set\":\"\",\"caption\":\"\","
        "\"beats\":[{\"role\":\"HOOK\",\"seconds\":n,\"visual\":\"\",\"camera\":\"one move\",\"vo\":\"\",\"caption\":\"\"}]}",
        "You are an award-winning direct-response ad director.", images=images[:2] or None, mock=mock)
    shots = [b for b in plan["beats"] if b.get("role") != "CTA"]
    cta_s = next((float(b["seconds"]) for b in plan["beats"] if b.get("role") == "CTA"), max(1.5, duration * 0.15))
    for i in range(1, 6): step(i)
    log.append(J({k: plan.get(k) for k in ("usp", "emotion", "audience", "platform_norms", "talent", "wardrobe", "set")}, f"{tag}Creative plan"))
    log.append(J([{k: b.get(k) for k in ("role", "seconds", "visual", "camera", "vo", "caption")} for b in plan["beats"]], f"{tag}Beat sheet"))
    talent_ref = []
    if character:
        _, talent_ref = ctx.cast("", [character])
    # VO timed per beat, laid at each beat's start
    t0, tracks = 0.0, []
    for b in plan["beats"]:
        if b.get("vo"):
            tracks.append((t0 + 0.1, ctx.router.tts(b["vo"])[0]))
        t0 += float(b["seconds"])
    vo = _lay(ctx, tracks, duration) if tracks else None
    out = []

    def render(ar: str, attempt: int, fixes: list[str]) -> Path:
        w, h = (1080, 1920) if ar == "9:16" else (1920, 1080) if ar == "16:9" else (1080, 1080) if ar == "1:1" else (1080, 1350)
        clips, cues, t = [], [], 0.0
        avoid = (" Avoid: " + "; ".join(fixes[:3]) + ". Keep the camera steady and the action simple.") if fixes else ""
        for k, s in enumerate(shots):
            step(6, f" · {ar} {s['role'].lower()}" + (f" (retake {attempt})" if attempt else ""))
            sec = float(s["seconds"])
            p = (f"{s.get('camera', 'Slow push in')}. {s['visual']}. {plan.get('set', '')}. Talent: {plan.get('talent', '')}, wearing {plan.get('wardrobe', '')}. "
                 f"{tone} {category.lower()} commercial, product clearly visible and accurate to the reference.{avoid}")
            frame = ctx.router.image(p, aspect=ar, refs=(images[:2] + talent_ref) or None, seed=attempt * 977 + k)[0]
            v = ctx.router.video(p, image=frame, aspect=ar, duration=max(2, round(sec)), audio=False)[0]
            clips.append(M.norm_clip(v, ctx.file(".mp4"), w, h, dur=sec))
            if s.get("caption"): cues.append({"start": t, "end": t + sec - 0.05, "text": s["caption"].upper()})
            t += sec
        step(7, f" · {ar}")
        safe = SAFE.get(platform, (0.05, 0.08, 0.05)) if h > w else (0.05, 0.08, 0.05)
        plate = M.end_plate((w, h), f"{brand} {product}".strip(), price, plan.get("caption", ""), cta or "Shop now",
                            Image.open(end_image or images[0]) if (end_image or images) else None, safe=safe)
        clips.append(M.still_clip(ctx.save_img(plate), ctx.file(".mp4"), w, h, dur=cta_s))
        cut = M.concat(clips, ctx.file(".mp4"))
        if cues:  # burned captions, centred, clear of the platform UI
            ass = ctx.text_file(write_ass(cues, "Bold Pop", w, h, False, platform), ".ass"); cap = ctx.file(".mp4")
            M.sh(["ffmpeg", "-v", "error", "-y", "-i", str(cut), "-vf", f"ass={ass}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "copy", str(cap)]); cut = cap
        if vo: cut = M.mix(cut, ctx.file(".mp4"), voice=vo)
        return M.loudnorm(cut, ctx.file(".mp4"), -14)

    for ar in aspects:
        take = render(ar, 0, [])
        best = {"path": take, "label": f"{tag}{ar} · {duration:.0f}s"}
        if qc:
            best_r = None
            for attempt in range(1, 3):  # QC; below threshold, retake with the reviewer's fixes in the prompt; keep the best take
                r = qc_score(ctx, take, f"{product} ad for {platform}, {tone}: " + "; ".join(b.get("visual", "") for b in shots), [character] if character else None, platform)
                if best_r is None or r["composite"] > best_r["composite"]:
                    best_r, best["path"] = r, take
                if r.get("heuristic") or r["composite"] >= threshold or attempt == 2:
                    break
                ctx.progress(f"{tag}QC {r['composite']} < {threshold}: retaking {ar} with fixes")
                take = render(ar, attempt, r.get("fixes") or [])
            best_r["verdict"] = "Heuristic only (no vision model)" if best_r.get("heuristic") else "Approved" if best_r["composite"] >= threshold else "Best take, below threshold"
            best["qc"] = best_r
        out.append(best)
    return out + log + ([(f"{tag}voiceover", vo)] if vo else [])


AD_INPUTS = [F("product", "Product name", required=True, placeholder="Philips Air Purifier Series 800i"), F("images", "Product images", "images"),
             F("link", "…or product page URL", help="Name/specs are read from it when possible."), F("specs", "Key specs", "textarea"),
             S("category", "Category", CATEGORIES), F("brand", "Brand"), F("price", "Price on end plate", placeholder="₹9,999"), F("cta", "Call to action", default="Shop now"),
             F("audience", "Audience", placeholder="new parents in metro cities"), S("platform", "Platform", PLATFORMS), S("tone", "Tone", TONES),
             F("duration", "Length (s)", "slider", min=6, max=30, default=15), C("aspects", "Formats (rendered together)", ["9:16", "16:9", "1:1", "4:5"], default=["9:16", "16:9"]),
             F("character", "Spokesperson / model", "character", group="Continuity"), F("end_image", "End-plate image", "image"),
             F("qc", "QC + auto-regenerate", "toggle", default=True, group="Quality"), F("threshold", "QC threshold", "slider", min=0, max=10, step=0.1, default=7, group="Quality")]


def scrape(url: str) -> str:
    if not url:
        return ""
    import urllib.request, html as H
    try:
        raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read().decode(errors="replace")
    except Exception:
        return ""
    raw = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", raw)
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", raw)))[:4000]


@tool("micro_ad_factory", "Micro Ad Factory", "ads", "⚡", "Product data → finished 15 s ad, vertical and horizontal",
      "An 8-step agent pipeline: product understanding, audience mapping, script & dialogue, model & casting, costume & styling, location & set design, shot-by-shot visuals and an end plate (name, price, caption, CTA). Optional QC on five axes with auto-regeneration below your threshold.",
      AD_INPUTS, ["video", "json"], ["llm", "image", "video", "tts", "vision"])
def t_micro_ad(ctx, product, images, link, specs, category, brand, price, cta, audience, platform, tone, duration, aspects, character, end_image, qc, threshold):
    if link:
        specs = (specs or "") + "\nFrom product page: " + scrape(link)[:1500]
    return micro_ad(ctx, product, images, specs, category, brand, audience, platform, tone, price, cta, duration, aspects or ["9:16"], qc, threshold, character, end_image)


ECOM_IMAGE = {
    "Studio try-on": "flat clothing shown worn by a model on a clean studio background",
    "Lifestyle try-on": "clothing worn by a model in a natural lifestyle setting, matching any texture reference",
    "Accessories on-model": "the accessory (glasses, jewellery, hat or headphones) worn by a model, close and flattering",
    "Try-on with your own model": "the product worn by the supplied model photo, preserving the model's exact face",
    "Handheld display": "the product held naturally in a hand, shallow depth of field",
    "Usage demo": "the product being used for its purpose, clear and believable",
    "Scene composite": "the product placed naturally in a styled room scene with matching light and shadows",
    "Flat lay": "a styled top-down flat lay with complementary props",
    "360° multi-angle grid": "a grid of front, side, rear and sole/back views on white",
    "Outdoor lifestyle": "the product in an outdoor lifestyle setting (beach, café, park or street)",
    "Dynamic VFX poster": "a dramatic poster with splashes, particles and motion effects around the product",
    "Technical schematic": "a technical schematic with dimension arrows and a scale comparison object (coin, hand or phone)",
    "Promo banner": "a promotional banner with headline, CTA and price space",
    "Colorway variants": "the product shown in several colourways with swatches",
    "Gift packaging": "the product in premium gift packaging",
    "Technical infographic": "a blueprint-style infographic with callouts, part labels and a sketch title box",
    "Before & after": "a split before-and-after comparison showing the product's effect",
    "Zoom detail shot": "an extreme macro detail of materials and craftsmanship",
    "Ingredient explosion": "the product with its ingredients or components exploding outward dynamically",
    "Unboxing reveal": "an unboxing reveal moment with the box opening",
    "Clean hero shot": "a clean hero shot on a white or minimal studio background",
    "Seasonal campaign": "the product in a festive seasonal campaign setting",
    "Marketplace main image": "a marketplace-compliant main image: pure white background, product filling 85% of frame",
}


@tool("ecommerce_image_studio", "Ecommerce Image Studio", "ads", "🛍️", "23 product-photo scenarios, one click",
      "Pick a scenario — studio or lifestyle try-on, flat lay, 360° grid, schematic, infographic, unboxing, hero shot and more — upload product images and generate catalogue-ready photos.",
      [S("scenario", "Scenario", list(ECOM_IMAGE)), F("images", "Product images", "images", required=True), F("model_photo", "Model photo", "image", showIf={"scenario": ["Try-on with your own model", "Accessories on-model", "Studio try-on", "Lifestyle try-on"]}),
       F("texture", "Texture / style reference", "image"), F("product", "Product name"), F("notes", "Headline, price or notes"), S("aspect", "Aspect", ["1:1", "4:5", "3:4", "9:16", "16:9"]),
       F("count", "Images", "slider", min=1, max=4, default=2), model_field("edit")], ["image"], ["edit"])
def t_ecom_image(ctx, scenario, images, model_photo, texture, product, notes, aspect, count, model):
    p = f"E-commerce photo of {product or 'the product'}: {ECOM_IMAGE[scenario]}. Keep the product's shape, colour, logo and details exactly as in the reference. {notes or ''}"
    refs = list(images) + [x for x in (model_photo, texture) if x]
    return [(f"{scenario} {i + 1}", x) for i, x in enumerate(ctx.router.image(p, aspect=aspect, n=int(count), refs=refs, **route(model)))]


ECOM_VIDEO = {
    "Product 360° Studio": "a smooth 360° studio turntable rotation of the product",
    "360° + Interior Reveal": "a 360° exterior rotation that moves inside to reveal interior details",
    "180° + Texture Zoom": "a 180° arc ending in a slow macro zoom on the texture",
    "Clothing try-on": "a model wearing the garment, turning to show fit and drape",
    "Accessories try-on": "a model putting on the accessory and showing it from several angles",
    "Accessories action sequence": "the model wearing the accessory in an energetic action sequence",
    "Multi-angle fashion showcase": "one continuous showcase moving front, side and back around the model",
    "Handheld product display": "a hand presenting the product in a lifestyle setting",
    "Product ad storyboard": "a short storyboarded ad sequence between the two lifestyle moments",
    "Product usage demo": "the product being used, showing the benefit clearly",
    "Scene compositing": "the product placed in the room with the character interacting with it",
    "Before & after results": "a before-and-after transformation showing the result",
    "Remove elements": "the same footage with unwanted elements removed cleanly",
    "Unboxing": "hands unboxing the product with a satisfying reveal",
}


@tool("ecommerce_video_studio", "Ecommerce Video Studio", "ads", "📦", "14 product-video scenarios from still images",
      "360° spins, interior reveals, texture zooms, try-on, fashion showcases, usage demos, storyboards and before/after — product stills in, listing video out.",
      [S("scenario", "Scenario", list(ECOM_VIDEO)), F("images", "Product / angle images", "images", required=True), F("model_photo", "Model or character photo", "image"), F("character", "Locked model", "character"),
       F("source_video", "Source video", "video", showIf={"scenario": ["Remove elements"]}), F("remove", "What to remove", showIf={"scenario": ["Remove elements"]}),
       F("product", "Product name"), S("aspect", "Aspect", ["9:16", "1:1", "16:9", "4:5"]), F("duration", "Length (s)", "slider", min=3, max=15, default=6), model_field("video")],
      ["video"], ["video", "edit", "inpaint"])
def t_ecom_video(ctx, scenario, images, model_photo, character, source_video, remove, product, aspect, duration, model):
    _, crefs = ctx.cast("", [character] if character else [])
    if scenario == "Remove elements":
        if not source_video:
            raise ToolError("Upload the source video")
        p = f"The same video with {remove or 'unwanted elements'} removed cleanly; everything else identical."
        first = M.frame_at(source_video, 0, ctx.file(".jpg"))
        clean = ctx.router.image(f"Remove {remove or 'unwanted elements'} from this frame; keep everything else identical.", aspect=_aspect_of(first), refs=[first])[0]
        return [ctx.router.video(p, image=clean, aspect=aspect, duration=min(duration, M.probe(source_video)["duration"]), **route(model))[0]]
    p = f"Product video of {product or 'the product'}: {ECOM_VIDEO[scenario]}. Product accurate to the references; premium commercial lighting."
    start = ctx.router.image(p, aspect=aspect, refs=list(images) + ([model_photo] if model_photo else []) + crefs)[0]
    end = images[-1] if len(images) > 1 and "360" in scenario else None
    return [(scenario, ctx.router.video(p, image=start, end_image=end, aspect=aspect, duration=duration, **route(model))[0]), ("Start frame", start)]


UGC_BEATS = {  # per-format beat templates (docs/tool-research.md §7)
    "Selfie & Talking Head": ["direct-to-camera hook with a strong expression", "shows the {product} close to the lens", "uses it, genuine reaction", "points to camera: call to action"],
    "Testimonial & Story": ["'I was skeptical…' hook to camera", "the problem in their everyday life", "the result after using the {product}", "proof: close-up of the result", "call to action"],
    "Unboxing & Reveal": ["hands and box on a table, sound of tape", "lid opens: the {product} revealed", "first-use reaction", "close detail of the {product}", "call to action"],
    "Try-On": ["mirror selfie before", "putting on the {product}", "turn to show fit and detail", "walk toward camera, call to action"],
    "Tutorial & How-To": ["'here's the trick' hook", "step 1 with the {product}", "step 2, close-up", "the finished result", "call to action"],
    "Cinematic & Brand": ["dramatic hero reveal of the {product}", "fast montage of it in use", "signature brand moment", "logo and call to action"],
}
UGC_FORMATS = {
    "Selfie & Talking Head": ["UGC", "Direct-to-camera", "UGC Addiction"],
    "Testimonial & Story": ["This gadget saved me", "Couple sharing at home"],
    "Unboxing & Reveal": ["Unboxing", "Unboxing ASMR", "Reboxing", "Gift unboxing"],
    "Try-On": ["Virtual try-on sneakers", "UGC virtual try-on"],
    "Tutorial & How-To": ["Secret hack reveal", "Before and after", "Tutorial"],
    "Cinematic & Brand": ["Hyper Motion", "TV Spot", "Wild Card"],
}


@tool("ugc_ads_studio", "UGC Ads Studio", "ads", "🤳", "17 creator-style ad formats",
      "Pick a format — talking head, testimonial, unboxing (incl. ASMR), try-on, tutorial, hack reveal, Hyper Motion, TV spot — add product details and a creator, and get a social-native ad with script and voice.",
      [S("format", "Format", [{"value": f, "label": f"{g} · {f}"} for g, fs in UGC_FORMATS.items() for f in fs]), F("product", "Product", required=True), F("images", "Product images", "images"),
       F("details", "What to say", "textarea", placeholder="Key benefit, price, offer"), F("creator", "Creator", "character", help="A locked character; leave blank to cast one."),
       F("creator_look", "…or describe the creator", placeholder="Gen-Z woman, sunny bedroom"), S("language", "Language", ["English", "Hindi", "Hinglish", "Spanish", "Portuguese", "Arabic", "Indonesian"]),
       S("aspect", "Aspect", ["9:16", "1:1", "4:5", "16:9"]), F("duration", "Length (s)", "slider", min=6, max=30, default=15), F("voice", "Voiceover", "toggle", default=True)],
      ["video", "text"], ["llm", "image", "video", "tts"])
def t_ugc(ctx, format, product, images, details, creator, creator_look, language, aspect, duration, voice):
    group = next((g for g, fs in UGC_FORMATS.items() if format in fs), "Selfie & Talking Head")
    tpl = [b.format(product=product) for b in UGC_BEATS[group]]
    mock = {"script": f"Okay so I have to tell you about {product}. {details or 'It honestly changed my routine.'} Link's below!", "beats": tpl}
    plan = ctx.router.llm_json(f"Format: {format}\nProduct: {product}\nDetails: {details}\nLanguage: {language}\nLength: {duration:.0f}s\nWrite a UGC script in {language} (about 2.5 words per second, hook in the first line) and exactly these visual beats: {tpl}. JSON: {{\"script\":\"\",\"beats\":[\"\"]}}",
                               "You write high-converting creator ads that feel native to TikTok/Reels.", mock=mock)
    p0, refs = ctx.cast(f"{creator_look or 'a relatable creator'}", [creator] if creator else [])
    w, h = (1080, 1920) if aspect == "9:16" else (1080, 1080) if aspect == "1:1" else (1080, 1350) if aspect == "4:5" else (1920, 1080)
    clips = []; per = duration / len(plan["beats"])
    for i, b in enumerate(plan["beats"]):
        ctx.progress(f"Beat {i + 1}: {b}")
        p = f"Shot on iPhone, handheld, natural window light, slight exposure shifts. {format} UGC. {p0}. Beat: {b}. Product: {product}, accurate to the reference."
        f0 = ctx.router.image(p, aspect=aspect, refs=list(images[:2]) + refs or None)[0]
        clips.append(M.norm_clip(ctx.router.video(p, image=f0, aspect=aspect, duration=max(2, round(per)))[0], ctx.file(".mp4"), w, h, dur=per))
    cut = M.concat(clips, ctx.file(".mp4"))
    if voice:
        cut = M.mix(cut, ctx.file(".mp4"), voice=ctx.router.tts(plan["script"])[0])
    cut = M.loudnorm(cut, ctx.file(".mp4"), -14)
    return [(f"{format} · {aspect}", cut), T(plan["script"], "Script", copy=True)]


@tool("video_batch", "Video Batch Generation", "ads", "🗂️", "A spreadsheet of products → a queue of finished ads",
      "Upload CSV or Excel (product_name required; optional category, brand, specification, product image URLs, ad type, target audience, ad duration, end-plate image). Each row runs the Micro Ad Factory pipeline: queued → processing → QC → complete.",
      [F("sheet", "CSV or Excel file", "media", required=True), C("aspects", "Formats", ["9:16", "16:9", "1:1"], default=["9:16"]), S("platform", "Default platform", PLATFORMS),
       S("tone", "Default tone", TONES), F("qc", "QC + auto-regenerate", "toggle", default=True), F("threshold", "QC threshold", "slider", min=0, max=10, step=0.1, default=7),
       F("limit", "Max rows", "number", default=20, min=1)], ["video", "json", "file"], ["llm", "image", "video", "tts", "vision"])
def t_batch(ctx, sheet, aspects, platform, tone, qc, threshold, limit):
    if sheet.suffix.lower() in (".xlsx", ".xlsm"):
        try:
            import openpyxl
        except ImportError:
            raise ToolError("Excel needs `openpyxl`; upload CSV instead")
        ws = openpyxl.load_workbook(sheet, read_only=True).active; it = ws.iter_rows(values_only=True); head = [str(h or "").strip().lower() for h in next(it)]
        rows = [dict(zip(head, [str(c or "") for c in r])) for r in it]
    else:
        rows = [{k.strip().lower(): (v or "") for k, v in r.items()} for r in csv.DictReader(io.StringIO(sheet.read_text(errors="replace")))]
    rows = [r for r in rows if r.get("product_name")][: int(limit)]
    if not rows:
        raise ToolError("No rows with a product_name column")
    batch = f"B{random.randint(1000, 9999)}"; status = []; out = []
    for i, r in enumerate(rows):
        imgs = []
        for u in re.split(r"[,\s]+", r.get("product image urls", r.get("product_image_urls", ""))):
            if u.startswith("http"):
                try: imgs.append(ctx.out.fetch(u))
                except Exception: pass
        tag = f"[{batch}-{i + 1} {r['product_name'][:24]}] "
        try:
            res = micro_ad(ctx, r["product_name"], imgs, r.get("specification", ""), r.get("product category", r.get("category", "Electronics")), r.get("brand", ""),
                           r.get("target audience", ""), platform, r.get("ad type", tone) or tone, r.get("price", ""), r.get("cta", "Shop now"),
                           float(r.get("ad duration") or 15), aspects, qc, threshold, None, tag=tag)
            out += [o for o in res if isinstance(o, dict) and o.get("path")]
            status.append({"row": i + 1, "product": r["product_name"], "status": "complete", "qc": next((o.get("qc", {}).get("composite") for o in res if isinstance(o, dict) and o.get("qc")), None)})
        except Exception as e:
            status.append({"row": i + 1, "product": r["product_name"], "status": f"failed: {e}"})
    rep = io.StringIO(); w = csv.DictWriter(rep, fieldnames=["row", "product", "status", "qc"]); w.writeheader(); w.writerows(status)
    return [J({"Batch ID": batch, "Rows": status}, "Batch status"), (f"{batch}-report.csv", ctx.text_file(rep.getvalue(), ".csv"))] + out


# ---------- post-production ----------

@tool("video_editor", "Video Editor", "post", "✂️", "Multi-clip editor with text-based editing",
      "Pulse's editor: word-level transcript editing, filler and silence removal, clips and transitions, B-roll, text, emoji, music with ducking, TTS voice-over, reframing and in-browser MP4 export.",
      [], [], [], link="editor")
def t_editor(ctx):
    return []


SUB_PRESETS = {  # ASS styles: font, size % of height, primary, outline, back, bold, border style (1 outline, 3 box), alignment (2 bottom, 5 middle)
    "Cinema Standard": ("DejaVu Sans", 4.6, "&H00FFFFFF", "&H00000000", "&H64000000", 0, 1, 2),
    "Lower Third": ("DejaVu Sans", 4.0, "&H00FFFFFF", "&H00000000", "&HA0000000", 1, 3, 1),
    "Bold Pop": ("DejaVu Sans", 7.0, "&H00FFFFFF", "&H00000000", "&H00000000", 1, 1, 5),
    "Punch Green": ("DejaVu Sans", 7.0, "&H004EF2C6", "&H00000000", "&H00000000", 1, 1, 5),
    "Neon Glow": ("DejaVu Sans", 6.5, "&H00FFE14D", "&H00FF00E6", "&H00000000", 1, 1, 5),
    "Podcast Yellow": ("DejaVu Sans", 6.0, "&H0000E1FF", "&H00000000", "&H00000000", 1, 1, 2),
    "Karaoke Fill": ("DejaVu Sans", 6.5, "&H0000E1FF", "&H00000000", "&H00000000", 1, 1, 5),
    "Comic Punch": ("DejaVu Sans", 7.0, "&H00FFFFFF", "&H00000000", "&H00000000", 1, 1, 5),
    "Underline Beat": ("DejaVu Sans", 6.0, "&H00FFFFFF", "&H00000000", "&H00000000", 1, 1, 2),
    "Clean Broadcast": ("DejaVu Sans", 4.4, "&H00FFFFFF", "&H00202020", "&H00000000", 0, 1, 2),
    "Subtle Box": ("DejaVu Sans", 4.4, "&H00FFFFFF", "&H00000000", "&H96000000", 0, 3, 2),
    "Typewriter": ("DejaVu Sans Mono", 4.6, "&H00FFFFFF", "&H00000000", "&H00000000", 0, 1, 2),
}
LANGS = ["Hindi", "Tamil", "Telugu", "Malayalam", "Kannada", "Marathi", "Gujarati", "Bengali", "Punjabi", "Urdu", "Odia", "Assamese", "Nepali", "Sinhala", "Spanish", "French",
         "German", "Italian", "Portuguese", "Russian", "Ukrainian", "Chinese", "Japanese", "Korean", "Arabic", "Hebrew", "Persian", "Turkish", "Vietnamese", "Thai", "Indonesian",
         "Malay", "Filipino", "Swahili", "Dutch", "Polish", "Greek", "Swedish"]
SOUND_CUES = re.compile(r"\b(laughs?|laughter|applause|music)\b", re.I)
PROFANITY = re.compile(r"\b(fuck\w*|shit\w*|bitch\w*|asshole|bastard|damn)\b", re.I)


def ts(t: float, sep=",") -> str:
    ms = int(round(t * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02}{sep}{ms:03}"


NO_BREAK_AFTER = {"a", "an", "the", "my", "your", "his", "her", "our", "their", "its", "this", "that", "to", "of", "in", "on", "at", "for", "with", "and", "or", "but",
                  "i", "you", "we", "they", "he", "she", "it", "not", "don't", "can't", "will", "would", "is", "are", "was", "were", "be", "very", "so", "mr.", "mrs.", "dr."}


def break_lines(text: str, max_chars: int, max_lines: int = 2) -> str:
    """Netflix line breaking: one line if it fits; otherwise a bottom-heavy split after punctuation or before a
    conjunction/preposition, never between article+noun, pronoun+verb, etc. (docs/tool-research.md §8)."""
    if len(text) <= max_chars or max_lines < 2:
        return text
    words = text.split(); best, best_cost = None, 1e9
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        if len(a) > max_chars or (len(b) > max_chars and max_lines == 2):
            continue
        cost = abs(len(a) - len(b)) + (0 if len(b) >= len(a) else 6)  # bottom-heavy
        if words[i - 1].lower() in NO_BREAK_AFTER: cost += 40
        if re.search(r"[,.;:!?]$", words[i - 1]): cost -= 12
        if words[i].lower() in ("and", "but", "or", "because", "that", "which", "to", "of", "in", "on", "with"): cost -= 6
        if i == 1 or i == len(words) - 1: cost += 15  # avoid 1-word lines
        if cost < best_cost:
            best, best_cost = i, cost
    if best is None:
        return text
    rest = " ".join(words[best:])
    return " ".join(words[:best]) + "\n" + (break_lines(rest, max_chars, max_lines - 1) if max_lines > 2 and len(rest) > max_chars else rest)


def cues_from_words(words: list[dict], rhythm: str, max_chars: int, max_lines: int = 2, cps: float = 20, fps: float = 24) -> list[dict]:
    """Timed-text segmentation. Word-pop rhythms (1–6 words) are for social styles; Sentence/Line follow Netflix:
    ≤max_lines×max_chars, ≤cps reading speed, 0.833–7 s, out-time +0.5 s when free, 2-frame chained gaps."""
    n = {"1-word": 1, "2-word": 2, "3-word": 3, "4-word": 4, "6-word": 6}.get(rhythm)
    cap = max_chars * (1 if n else max_lines)
    cues, cur = [], []
    for k, w in enumerate(words):
        cur.append(w); text = " ".join(x["text"] for x in cur)
        nxt = words[k + 1] if k + 1 < len(words) else None
        pause = nxt is not None and nxt["start"] - w["end"] > 0.6
        too_long = cur[-1]["end"] - cur[0]["start"] > 6.5
        nxt_fits = nxt is not None and len(text) + 1 + len(nxt["text"]) <= cap
        end_sentence = re.search(r"[.!?]$", w["text"]) and (rhythm == "Sentence" or len(text) > cap * 0.5)
        if (n and len(cur) >= n) or not nxt_fits or end_sentence or pause or too_long or (rhythm == "Line" and len(text) >= max_chars * 0.85 and re.search(r"[,.;:!?]$", w["text"])):
            cues.append({"start": cur[0]["start"], "end": cur[-1]["end"], "text": text, "words": cur}); cur = []
    if cur:
        cues.append({"start": cur[0]["start"], "end": cur[-1]["end"], "text": " ".join(x["text"] for x in cur), "words": cur})
    gap2 = 2 / fps
    for i, c in enumerate(cues):
        nxt = cues[i + 1]["start"] if i + 1 < len(cues) else c["end"] + 10
        if not n:
            need = max(5 / 6, len(c["text"]) / cps)  # minimum duration and reading speed
            c["end"] = max(c["end"], min(c["start"] + need, c["start"] + 7))
            c["end"] = min(c["end"] + 0.5, c["start"] + 7)  # hang 0.5 s after speech
            c["text"] = break_lines(c["text"], max_chars, max_lines)
        if nxt - c["end"] < 0.5:  # chain short gaps to exactly 2 frames
            c["end"] = max(c["start"] + 0.3, nxt - gap2)
    return cues


def write_ass(cues: list[dict], style: str, w: int, h: int, karaoke: bool, platform: str = "") -> str:
    font_, size, prim, outl, back, bold, border, align = SUB_PRESETS[style]
    fs = int(h * size / 100)
    # bottom captions on vertical video sit above the app UI band (TikTok ~22% of height, Reels/Shorts ~36%)
    vertical = h > w * 1.3
    margin = (0.36 if platform in ("Instagram Reels", "YouTube Shorts", "Facebook Stories") else 0.22) if vertical and align in (1, 2, 3) else (0.08 if align in (1, 2, 3) else 0.04)
    head = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {w}\nPlayResY: {h}\nWrapStyle: 2\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            f"Style: Default,{font_},{fs},{prim},&H00FFFFFF,{outl},{back},{-1 if bold else 0},0,{1 if style == 'Underline Beat' else 0},0,100,100,0,0,{border},{max(2, fs // 14)},{1 if border == 1 else 0},{align},60,60,{int(h * margin)},1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    lines = []
    for c in cues:
        txt = c["text"].upper() if style in ("Bold Pop", "Punch Green", "Comic Punch") else c["text"]
        if karaoke and c.get("words"):
            # \k durations are cumulative: lead-in silence first, then each word lasts until the next one starts
            ws = c["words"]; parts = [f"{{\\k{max(0, int((ws[0]['start'] - c['start']) * 100))}}}"]
            for j, x in enumerate(ws):
                until = ws[j + 1]["start"] if j + 1 < len(ws) else x["end"]
                parts.append(f"{{\\kf{max(1, int((until - x['start']) * 100))}}}{x['text']} ")
            txt = "".join(parts).rstrip()
        lines.append(f"Dialogue: 0,{ts(c['start'], '.')[1:-1]},{ts(c['end'], '.')[1:-1]},Default,,0,0,0,,{txt.replace(chr(10), '\\N')}")
    return head + "\n".join(lines) + "\n"


def srt(cues, vtt=False) -> str:
    if vtt:
        return "WEBVTT\n\n" + "\n".join(f"{ts(c['start'], '.')} --> {ts(c['end'], '.')}\n{c['text']}\n" for c in cues)
    return "\n".join(f"{i}\n{ts(c['start'])} --> {ts(c['end'])}\n{c['text']}\n" for i, c in enumerate(cues, 1))


def parse_srt(text: str) -> list[dict]:
    def sec(t): h, m, s = t.replace(",", ".").split(":"); return int(h) * 3600 + int(m) * 60 + float(s)
    out = []
    for m in re.finditer(r"(\d+:\d\d:\d\d[,.]\d+)\s*-->\s*(\d+:\d\d:\d\d[,.]\d+)[^\n]*\n([\s\S]*?)(?:\n\s*\n|$)", text):
        out.append({"start": sec(m.group(1)), "end": sec(m.group(2)), "text": " ".join(m.group(3).split())})
    return out


@tool("subtitle_creator", "Subtitle Creator", "post", "💬", "Word-timed captions, 38 languages, burn-in or soft track",
      "Transcribe a video or audio file (or import SRT/VTT), set caption rhythm and line length, tag sound cues, censor profanity, shift timing, translate into many languages at once, style with 12 presets and export burned-in MP4, soft-track MP4, ASS (karaoke), SRT, VTT, TXT and JSON.",
      [F("media", "Video or audio", "media", required=True), F("srt", "Import SRT/VTT (skips transcription)", "media"), F("language", "Spoken language", placeholder="auto"),
       C("rhythm", "Caption rhythm", ["Sentence", "Line", "1-word", "2-word", "3-word", "4-word", "6-word"], "Line"), F("max_chars", "Max chars per line", "slider", min=20, max=60, default=42),
       F("vocab", "Custom vocabulary hint", placeholder="Spark Station, Ananya, Kochi"), F("cues", "Sound-cue tags", "toggle", default=True), F("censor", "Censor profanity", "toggle", default=False),
       F("shift", "Shift all cues (s)", "number", default=0, step=0.1), C("translate", "Translate to", LANGS, default=[]),
       S("style", "Style preset", list(SUB_PRESETS)), F("karaoke", "Karaoke word highlight", "toggle", default=False),
       C("exports", "Exports", ["Burned-in MP4", "Soft-track MP4", "ASS", "SRT", "VTT", "TXT", "JSON"], default=["Burned-in MP4", "SRT"]),
       S("quality", "Burn-in quality", ["Fast", "Balanced", "Best"], "Balanced")],
      ["video", "file"], ["llm"])
def t_subtitles(ctx, media, srt, language, rhythm, max_chars, vocab, cues, censor, shift, translate, style, karaoke, exports, quality):
    if srt:
        caps = parse_srt(srt.read_text(errors="replace")); lang = language or "source"
    else:
        if not ctx.transcribe:
            raise ToolError("Transcription (faster-whisper) is not installed on this server; import an SRT instead")
        ctx.progress("Extracting audio & transcribing")
        wav = ctx.file(".wav")
        M.sh(["ffmpeg", "-v", "error", "-y", "-i", str(media), "-vn", "-ac", "1", "-ar", "16000", str(wav)])
        tr = ctx.transcribe(wav, language or None, vocab or None)  # names and jargon spelled as you give them
        lang = tr.get("language", "")
        info0 = M.probe(media); vertical = info0["height"] > info0["width"] * 1.3
        caps = cues_from_words(tr["words"], rhythm, min(int(max_chars), 25) if vertical else int(max_chars), 3 if vertical else 2)
    for c in caps:
        c["start"] = max(0, c["start"] + shift); c["end"] = max(c["start"] + 0.2, c["end"] + shift)
        if cues: c["text"] = SOUND_CUES.sub(lambda m: f"({m.group(1).lower()})", c["text"])
        if censor: c["text"] = PROFANITY.sub(lambda m: m.group(0)[0] + "*" * (len(m.group(0)) - 1), c["text"])
    tracks = {lang or "source": caps}
    for L in translate:
        ctx.progress(f"Translating to {L}")
        texts = [c["text"].replace("\n", " ") for c in caps]
        mock = {"lines": [f"[{L}] {t}" for t in texts]}
        r = ctx.router.llm_json(f"Translate these subtitle lines into {L}, idiomatically. Keep proper nouns, numbers and speaker tags. Same count, same order. "
                                f"Keep each cue at or under 20 characters per second for its duration; condense rather than paraphrase. Vocabulary: {vocab or '-'}\nJSON: {{\"lines\":[...]}}\n"
                                + json.dumps([{"text": x, "seconds": round(c["end"] - c["start"], 2)} for x, c in zip(texts, caps)], ensure_ascii=False), "You are a subtitle translator.", mock=mock)
        tracks[L] = [{**c, "text": break_lines(t, 16 if L in ("Chinese", "Japanese", "Korean") else int(max_chars)), "words": None} for c, t in zip(caps, r["lines"] + texts[len(r["lines"]):])]
    info = M.probe(media); w, h = (info["width"] or 1920, info["height"] or 1080)
    out = [J([{"start": round(c["start"], 2), "end": round(c["end"], 2), "text": c["text"]} for c in caps[:200]], f"Cues ({len(caps)})")]
    for L, cs in tracks.items():
        rtl = L in ("Arabic", "Hebrew", "Persian", "Urdu")
        tag = L.lower().replace(" ", "-")
        if "SRT" in exports: out.append((f"{tag}.srt", ctx.text_file(globals()["srt"](cs), ".srt")))
        if "VTT" in exports: out.append((f"{tag}.vtt", ctx.text_file(globals()["srt"](cs, True), ".vtt")))
        if "TXT" in exports: out.append((f"{tag}.txt", ctx.text_file("\n".join(c["text"] for c in cs), ".txt")))
        if "JSON" in exports: out.append((f"{tag}.captions.json", ctx.text_file(json.dumps({"style": style, "rtl": rtl, "cues": [{k: v for k, v in c.items()} for c in cs]}, ensure_ascii=False, indent=1), ".json")))
        ass = ctx.text_file(write_ass(cs, style, w, h, karaoke and L == (lang or "source")), ".ass")
        if "ASS" in exports: out.append((f"{tag}.ass", ass))
        if kind_of(media) == "video" and "Burned-in MP4" in exports:
            ctx.progress(f"Burning in {L}")
            crf, preset = {"Fast": ("26", "ultrafast"), "Balanced": ("21", "veryfast"), "Best": ("18", "medium")}[quality]
            dst = ctx.file(".mp4")
            M.sh(["ffmpeg", "-v", "error", "-y", "-i", str(media), "-vf", f"ass={ass}", "-c:v", "libx264", "-preset", preset, "-crf", crf, "-c:a", "copy", "-movflags", "+faststart", str(dst)], timeout=7200)
            out.append((f"Burned-in · {L}", dst))
    if kind_of(media) == "video" and "Soft-track MP4" in exports:
        ctx.progress("Muxing soft subtitle tracks")
        dst = ctx.file(".mp4"); srts = []
        for L, cs in tracks.items():
            srts.append(ctx.text_file(globals()["srt"](cs), ".srt"))
        cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(media)] + sum([["-i", str(s)] for s in srts], []) + ["-map", "0"] + sum([["-map", str(i + 1)] for i in range(len(srts))], []) + ["-c", "copy", "-c:s", "mov_text"]
        for i, L in enumerate(tracks):
            cmd += [f"-metadata:s:s:{i}", f"title={L}"]
        M.sh(cmd + [str(dst)]); out.append(("Soft-track MP4", dst))
    return out


# ---------- distribution: intelligence, thumbnails, posters, resize, comics, explainers ----------

def key_frames(ctx, video: Path, n: int = 12) -> list[tuple[float, Path, float]]:
    """(time, frame, arousal): z(motion) + z(audio RMS) + z(cut density) + 0.3·z(sharpness), smoothed; at most one moment
    per shot, best n kept in time order (docs/tool-research.md §9)."""
    dur = M.probe(video)["duration"]
    every = max(0.5, dur / 120)
    fr = M.frames(video, ctx.out.dir / "frames", every=every, width=640)
    mo = M.motion_scores(fr); sh = [M.sharpness(p) for _, p in fr]
    rms = M.audio_energy(video, every); cuts = M.scene_cuts(video)
    au = [rms[min(i, len(rms) - 1)] if rms else 0.0 for i in range(len(fr))]
    dens = [float(sum(1 for c in cuts if abs(c - t) < 3)) for t, _ in fr]
    raw = [a + b + c + 0.3 * d for a, b, c, d in zip(M.zs(mo), M.zs(au), M.zs(dens), M.zs(sh))]
    sm = [sum(raw[max(0, i - 1): i + 2]) / len(raw[max(0, i - 1): i + 2]) for i in range(len(raw))]
    shot_of = lambda t: sum(1 for c in cuts if c <= t)
    picked, used = [], set()
    for i in sorted(range(len(fr)), key=lambda i: -sm[i]):
        t, p = fr[i]; sid = shot_of(t)
        if sid in used and len(cuts) >= n: continue
        if all(abs(t - q[0]) > dur / (n * 2) for q in picked):
            picked.append((t, p, round(sm[i], 2))); used.add(sid)
        if len(picked) >= n: break
    ctx.cuts = cuts  # reused when cutting on shot boundaries
    return sorted(picked)


REEL_MODES = {"Teaser": (15, 30, "A handful of moments. Withholds the story."), "Trailer": (60, 90, "Full beat arc, rising intensity."), "Reel": (15, 60, "Punchy highlight cut for social")}
AUDIENCES = ["Kids", "Gen-Z / Youth", "Young Adults", "Family / General Audience", "Mature / Older Audience"]
REEL_GENRES = ["Documentary", "Drama", "Horror", "Action", "Thriller", "Comedy", "Romance", "Sci-Fi", "Fantasy"]


@tool("video_intelligence", "Video Intelligence", "distribution", "🧠", "Long video → key moments → teaser, trailer or reel",
      "Frame extractor, key frames, key moments and highlights scored for narrative or excitement, then an AI editor cuts a Teaser (15–30 s), Trailer (60–90 s) or Reel (15–60 s) for your genre and audience, and hands key frames to Thumbnail and Poster.",
      [F("video", "Long-form video", "video", required=True), S("mode", "Mode", list(REEL_MODES)), S("genre", "Genre", REEL_GENRES), S("audience", "Target audience", AUDIENCES),
       F("length", "Length (s)", "slider", min=15, max=90, default=30), S("aspect", "Output aspect", ["source", "9:16", "16:9", "1:1"]), F("music", "Music bed", "audio"),
       F("keyframes", "Key frames to export", "slider", min=4, max=24, default=9)],
      ["video", "image", "json"], ["vision"])
def t_vi(ctx, video, mode, genre, audience, length, aspect, music, keyframes):
    lo, hi, _ = REEL_MODES[mode]; L = min(hi, max(lo, length))
    info = M.probe(video); dur = info["duration"]
    ctx.progress("Extracting frames")
    kf = key_frames(ctx, video, max(int(keyframes), 12))
    ctx.progress("Scoring key moments")
    mock = {"moments": [{"t": round(t, 2), "score": round(max(0, min(10, 5 + s * 1.5)), 1), "label": "high-energy moment" if s > 0.5 else "quiet beat"} for t, _, s in kf]}
    r = ctx.router.llm_json(f"These are key frames from a {genre} video at times {[round(t, 1) for t, _, _ in kf]} s. For a {mode.lower()} aimed at {audience}, score each 0-10 for "
                            f"{'excitement' if genre in ('Action', 'Thriller', 'Horror') else 'narrative value'} and label it. JSON: {{\"moments\":[{{\"t\":sec,\"score\":n,\"label\":\"\"}}]}}",
                            "You are a trailer editor.", images=[p for _, p, _ in kf[:16]], mock=mock)
    moments = sorted(r["moments"], key=lambda m: -m["score"])
    cuts = getattr(ctx, "cuts", [])
    if mode == "Teaser":  # a handful of moments, never the climax or ending
        pool = [m for m in moments if m["t"] < dur * 0.75] or moments
        plan = [(m, 2.2) for m in sorted(pool[: max(3, min(6, int(L / 2.2)))], key=lambda m: m["t"])]
    elif mode == "Trailer":  # cold open, intro (2.5 s cuts), escalation (1.5 s), climax (rapid 0.8 s)
        early = [m for m in moments if m["t"] < dur / 3]
        cold = early[:1]; rest = [m for m in moments if m not in cold]
        quiet = sorted(rest, key=lambda m: m["score"])[:3]; hot = [m for m in rest if m not in quiet]
        esc, clim = sorted(hot[3:7], key=lambda m: m["score"]), hot[:3]
        plan = [(m, 2.5) for m in cold] + [(m, 2.5) for m in sorted(quiet, key=lambda m: m["t"])] + [(m, 1.5) for m in esc] + [(m, 0.8) for m in clim]
    else:  # reel: punchy highlights in order
        plan = [(m, 2.0) for m in sorted(moments[: max(3, int(L / 2.0))], key=lambda m: m["t"])]
    while sum(s for _, s in plan) > L and len(plan) > 2: plan.pop(len(plan) // 2)
    def snap(t):  # start on a shot boundary when one is close
        before = [c for c in cuts if t - 1.2 <= c <= t]
        return before[-1] + 0.04 if before else t
    W, H = (info["width"], info["height"]) if aspect == "source" else (1080, 1920) if aspect == "9:16" else (1920, 1080) if aspect == "16:9" else (1080, 1080)
    W, H = W // 2 * 2, H // 2 * 2
    ctx.progress(f"Cutting the {mode.lower()}")
    clips = [M.norm_clip(video, ctx.file(".mp4"), W, H, start=max(0, min(dur - seg, snap(m["t"] - seg / 3))), dur=seg) for m, seg in plan]
    cut = M.concat(clips, ctx.file(".mp4"))
    if music:
        cut = M.mix(cut, ctx.file(".mp4"), music=music, music_db=-10)
    cut = M.loudnorm(cut, ctx.file(".mp4"), -14)
    frames_out = [(f"Key frame {t:.1f}s", p) for t, p, _ in kf[: int(keyframes)]]
    return [(f"{mode} · {genre} · {audience}", cut), J(moments, "Key moments & highlights",
            next={"tool": "thumbnail_creator", "set": {}, "label": "Make thumbnails"})] + frames_out


THUMB_STYLES = {
    "Face & Reaction": ["Auto (best fit for topic)", "Reaction Close-Up", "Curiosity Hook", "Vibrant Everyday"],
    "Object & Product": ["Hero Object", "Bright & Clean"],
    "Comparison & Proof": ["Before/After Split", "Versus Color-Block", "Big Number/Stat"],
    "Mood & Atmosphere": ["Minimalist Clean", "Cinematic Dark", "Neon Dark Mode"],
    "Collage & Multi-Frame": ["Grid Collage", "Overlapping Photo Stack", "Main + Inset"],
}
THUMB_SIZES = {"YouTube & Facebook 16:9": ("16:9", 1280, 720), "Shorts / Reels / Stories / TikTok 9:16": ("9:16", 1080, 1920), "Instagram & Facebook Feed 1:1": ("1:1", 1080, 1080),
               "LinkedIn Video 16:9 (mirrored safe zone)": ("16:9", 1920, 1080)}


@tool("thumbnail_creator", "Thumbnail Creator", "distribution", "🖼", "Click-worthy thumbnails in every size at once",
      "Topic in, 16 templates across face & reaction, product, comparison, mood and collage (collages use video key frames), all sizes generated together.",
      [F("topic", "What is the video about?", "textarea", required=True), F("title", "Thumbnail text", placeholder="I TRIED IT FOR 30 DAYS"),
       S("style", "Style", [{"value": s, "label": f"{g} · {s}"} for g, ss in THUMB_STYLES.items() for s in ss]), F("reference", "Reference image / face", "image"),
       F("frames", "Key frames (for collage styles)", "images"), F("video", "…or pull frames from a video", "video"), C("sizes", "Sizes", list(THUMB_SIZES), default=list(THUMB_SIZES)[:3]),
       F("overlay", "Draw the text myself (exact typography)", "toggle", default=True), model_field("image")],
      ["image"], ["image", "edit"])
def t_thumb(ctx, topic, title, style, reference, frames, video, sizes, overlay, model):
    words = len((title or "").split())
    out_warn = [T(f"Your text has {words} words; thumbnails that click use 4 or fewer.", "Tip")] if words > 4 else []
    frames = list(frames)
    if video and not frames:
        frames = [p for _, p, _ in key_frames(ctx, video, 6)]
    out = []
    for name in sizes:
        ar, W, H = THUMB_SIZES[name]
        ctx.progress(name)
        if style in ("Grid Collage", "Overlapping Photo Stack", "Main + Inset") and frames:
            ims = [Image.open(p) for p in frames[:6]]
            if style == "Grid Collage":
                im = M.grid(ims[:4], 2, (W // 2 - 18, H // 2 - 18), bg="black").resize((W, H))
            elif style == "Main + Inset":
                im = M.smart_crop(ims[0], W, H); inset = M.smart_crop(ims[1 % len(ims)], W // 3, H // 3); im.paste(inset, (W - inset.width - 30, 30))
            else:
                im = M.smart_crop(ims[0], W, H).filter(__import__("PIL.ImageFilter", fromlist=["x"]).GaussianBlur(8))
                for k, x in enumerate(ims[1:4]):
                    t = M.smart_crop(x, W // 3, H // 2).rotate([-8, 5, -3][k], expand=True, fillcolor="white"); im.paste(t, (int(W * (0.08 + k * 0.3)), int(H * 0.25)))
            p = ctx.save_img(im)
        else:
            sty = "best-fit YouTube style" if style.startswith("Auto") else style
            text = "" if overlay else f' with bold readable text "{title}"'
            p = ctx.router.image(f"YouTube thumbnail, {sty}, about: {topic}{text}. A face (if any) fills about a third of the frame on the left with a genuine, readable emotion; "
                                 "one focal point; clean background with strong figure-ground separation; empty right side for a 2-4 word hook; nothing important in the bottom-right corner (timestamp).", aspect=ar,
                                 refs=[reference] if reference else None, **route(model))[0]
            p = ctx.save_img(M.smart_crop(Image.open(p), W, H))
        if overlay and title:
            p = ctx.save_img(M.overlay_title(Image.open(p), title, where="bottom" if ar != "9:16" else "top"), ".jpg")
        out.append((name, p))
    return out + out_warn


POSTER_STYLES = {
    "Thriller & Drama": ["Auto (random each time)", "Neo-Noir", "High-Contrast Thriller", "Prestige Drama"],
    "Action & Sci-Fi": ["Blockbuster Action", "Sci-Fi / Tech-Noir", "Gritty Dystopian"],
    "Comedy & Feel-Good": ["Sun-Drenched Indie", "Bright Comedy", "Pastel Romance"],
    "Horror & Fantasy": ["Horror Minimalist", "Epic Fantasy", "Folk Horror"],
    "Documentary & Minimal": ["Documentary Realism", "Minimalist Art-House", "Retro Pulp"],
}
POSTER_FORMATS = {"Theatrical 2:3": ("2:3", 1400, 2100), "Vertical Social 9:16": ("9:16", 1080, 1920), "Square 1:1": ("1:1", 1080, 1080), "Landscape 16:9": ("16:9", 1920, 1080),
                  "Cover Banner": ("21:9", 1500, 500), "Print A4 portrait (1:1.414)": ("2:3", 2480, 3508), "One-sheet 27×40": ("2:3", 2700, 4000)}


@tool("poster_creation", "Poster Creation", "distribution", "🎬", "Key art from the strongest frames in your video",
      "Upload any video; Pulse finds its strongest key frames, then designs a poster in one of 16 genre styles (or random, or from your reference poster) in six formats at once: theatrical 2:3, 9:16, 1:1, 16:9, cover banner and A4 print.",
      [F("video", "Video", "video"), F("frame", "…or a key frame / still", "image"), F("title", "Title", required=True), F("tagline", "Tagline / credits"),
       S("style", "Style", [{"value": s, "label": f"{g} · {s}"} for g, ss in POSTER_STYLES.items() for s in ss]), F("reference", "Reference poster", "image"),
       C("formats", "Formats", list(POSTER_FORMATS), default=list(POSTER_FORMATS)[:4]), F("overlay", "Typeset title myself", "toggle", default=True),
       F("billing", "Billing block", "textarea", placeholder="A PULSE PICTURES presentation · ANNA ROY · RAVI DEV · music by … · edited by … · directed by …", help="Typeset small and condensed under the title."), model_field("edit")],
      ["image"], ["edit"])
def t_poster(ctx, video, frame, title, tagline, style, reference, formats, overlay, billing, model):
    if not (video or frame):
        raise ToolError("Upload a video or a still")
    if style.startswith("Auto"):
        style = random.choice([s for ss in POSTER_STYLES.values() for s in ss if not s.startswith("Auto")])
    key = frame or max(key_frames(ctx, video, 8), key=lambda x: x[2])[1]
    out = []
    for name in [f for f in formats if f in POSTER_FORMATS] or list(POSTER_FORMATS)[:4]:
        ar, W, H = POSTER_FORMATS[name]
        ctx.progress(name)
        text = "" if overlay else f' Title text "{title}"' + (f', tagline "{tagline}"' if tagline else "")
        p = ctx.router.image(f"{style} movie poster key art built from this frame: keep the subject recognisable, dramatic composition, cinematic grade; the lower quarter darker and uncluttered for title and credits.{text}",
                             aspect=ar, refs=[key] + ([reference] if reference else []), **route(model))[0]
        im = M.smart_crop(Image.open(p), W, H)
        if overlay:
            im = M.overlay_title(im, title, tagline)
        if billing and H > W:
            im = M.billing_block(im, billing)
        out.append((f"{name} · {style}", ctx.save_img(im, ".jpg")))
    return out


ADAPT_SIZES = {"Stories 9:16 (1080×1920)": (1080, 1920), "Square 1:1 (1080×1080)": (1080, 1080), "YouTube 16:9 (1920×1080)": (1920, 1080), "X post 16:9 (1600×900)": (1600, 900),
               "Link preview 1.91:1 (1200×628)": (1200, 628), "Portrait feed 4:5 (1080×1350)": (1080, 1350), "Pinterest 2:3 (1000×1500)": (1000, 1500),
               "LinkedIn post 1.91:1 (1200×627)": (1200, 627), "YouTube channel art (2560×1440)": (2560, 1440), "Facebook cover (1640×624)": (1640, 624),
               "X header (1500×500)": (1500, 500), "Skyscraper 4:15 (160×600)": (160, 600), "Rectangle 6:5 (300×250)": (300, 250), "Leaderboard 8.09:1 (728×90)": (728, 90),
               "TikTok cover 9:16 (1080×1920)": (1080, 1920), "Instagram profile 1:1 (320×320)": (320, 320)}


@tool("resize_adapt", "Resize & Repurpose · Adapt", "distribution", "📐", "One image → 16 platform sizes",
      "Pick sizes (or select all), choose Extend canvas (generative outpaint, keeps 100% of the original) or Smart crop, and the subject focus (left, centre, right).",
      [F("image", "Image", "image", required=True), C("sizes", "Sizes", list(ADAPT_SIZES), default=list(ADAPT_SIZES)[:6]), S("method", "Adaptation method", ["Extend canvas", "Smart crop"]),
       S("focus", "Subject focus", ["Left", "Center", "Right"], "Center")], ["image"], ["inpaint"])
def t_adapt(ctx, image, sizes, method, focus):
    src = Image.open(image); out = []
    for name in sizes:
        W, H = ADAPT_SIZES[name]; ctx.progress(name)
        if method == "Smart crop" or abs(W / H - src.width / src.height) < 0.03:
            im = M.smart_crop(src, W, H, focus); out.append((name, ctx.save_img(im)))
            continue
        canvas, mask = M.extend_canvas(src, W, H, focus)
        cp, mp = ctx.save_img(canvas), ctx.save_img(mask)
        res = Image.open(ctx.router.inpaint(cp, mp, "Extend the scene naturally into the empty area; seamless continuation, same light and style.")[0]).convert("RGB").resize((W, H))
        res.paste(canvas, (0, 0), Image.eval(mask, lambda v: 255 - v))  # keep the original pixels untouched
        out.append((name, ctx.save_img(res)))
    return out


REFRAME = {"9:16": 9 / 16, "4:5": 4 / 5, "1:1": 1, "2:3": 2 / 3, "3:4": 3 / 4, "16:9": 16 / 9, "4:3": 4 / 3, "3:2": 3 / 2, "5:4": 5 / 4, "1.85:1": 1.85, "1.9:1": 1.9, "2:1": 2, "21:9": 21 / 9, "2.39:1": 2.39}


@tool("video_reframe", "Resize & Repurpose · Video Reframe", "distribution", "📱", "One video → up to 14 aspect ratios",
      "Social (9:16, 4:5, 1:1, 2:3, 3:4), broadcast (16:9, 4:3, 3:2, 5:4) and cinema (1.85, 1.9, 2:1, 21:9, 2.39). Auto placement follows the subject; or centre, or a fixed custom position. 480p test or 720p delivery.",
      [F("video", "Video", "video", required=True, help="MP4, MOV, MKV, MXF, MTS"), C("ratios", "Ratios", list(REFRAME), default=["9:16", "1:1", "4:5"]),
       S("resolution", "Resolution", ["480p", "720p", "1080p"], "720p"), S("placement", "Placement", ["Auto", "Centre", "Custom"]),
       F("x", "Custom position (left → right)", "slider", min=0, max=100, default=50, showIf={"placement": ["Custom"]})], ["video"], [])
def t_reframe(ctx, video, ratios, resolution, placement, x):
    pos = 0.5 if placement == "Centre" else x / 100 if placement == "Custom" else None
    if pos is None:
        ctx.progress("Reading the scene"); pos = M.saliency_x(video, ctx.out.dir / "sal")
    lines = int(resolution[:-1])
    out = []
    for r in ratios:
        ctx.progress(r)
        ratio = REFRAME[r]
        # "720p" means the short side, so tall outputs are 720 wide
        height = lines if ratio >= 1 else int(lines / ratio)
        out.append((f"{r} · {resolution}", M.reframe(video, ctx.file(".mp4"), ratio, height, pos)))
    return out + [J({"Placement": placement, "Crop centre (0–1)": round(pos, 3)}, "Scene reading")]


COMIC_STYLES = {"Manga": "Japanese black-and-white manga ink with screen-tones", "Webtoon": "Korean full-colour webtoon, soft cel shading", "American Comics": "American comic book, Ben-Day dots, bold primary colours",
                "European BD": "European bande dessinée clear-line style (Tintin / Moebius)", "Graphic Novel": "painterly graphic novel", "Noir B&W": "high-contrast noir black-and-white",
                "Dark Fantasy": "dark fantasy illustration, gothic", "Sci-Fi Epic": "sci-fi epic, neon, widescreen panels", "Retro Pop Art": "retro pop art, Lichtenstein dots",
                "Watercolor": "watercolour comic", "Cartoon Adventure": "Saturday-morning cartoon, thick outlines", "Pixel Comic": "pixel-art comic"}


@tool("comics_generator", "Comics Generator", "distribution", "💥", "Story → editable panel plan → finished comic pages",
      "Pick one of 12 styles, page count, panels per page and orientation, optionally a character photo. Edit every page synopsis and panel (scene, characters, camera, SFX, dialogue) before rendering, then read as scroll or flipbook and export PDF.",
      [F("story", "Story, script or premise", "textarea", required=True), S("style", "Art style", list(COMIC_STYLES)), F("pages", "Pages", "number", default=2, min=1, max=40),
       C("panels", "Panels per page", ["3-4", "5-6", "7-8"], "3-4"), S("orientation", "Orientation", ["Portrait", "Landscape", "Vertical Scroll"]),
       F("character_photo", "Character reference photo", "image"), CHARS,
       S("stage", "Step", [{"value": "plan", "label": "1 · Plan (editable)"}, {"value": "render", "label": "2 · Render pages"}], "plan"),
       F("plan", "Panel plan (JSON)", "textarea", showIf={"stage": ["render"]}), model_field("image")], ["image", "file", "json"], ["llm", "image"])
def t_comics(ctx, story, style, pages, panels, orientation, character_photo, characters, stage, plan, model):
    lo, hi = map(int, panels.split("-"))
    if stage == "plan" or not plan:
        ctx.progress("Planning pages and panels")
        beats = [b for b in re.split(r"(?<=[.!?])\s+", story) if b.strip()] or [story]
        mock = {"title": " ".join(story.split()[:4]).title(), "pages": [{"title": f"Page {p + 1}", "synopsis": " ".join(beats[p::int(pages)])[:200],
                 "panels": [{"scene": beats[(p * lo + k) % len(beats)][:140], "characters": ["Hero"], "camera": ["Wide", "Medium", "Close-up", "Low angle"][k % 4],
                             "sfx": "KRA-BOOM!" if k == lo - 1 and p == int(pages) - 1 else "", "dialogue": [{"type": "speech", "speaker": "Hero", "text": "This is where it starts."}] if k == 0 else []}
                            for k in range(lo)]} for p in range(int(pages))]}
        r = ctx.router.llm_json(f"Story: {story}\nStyle: {style}\nPages: {pages:.0f}, {panels} panels per page.\nJSON: {{\"title\":\"\",\"pages\":[{{\"title\":\"\",\"synopsis\":\"\",\"panels\":[{{\"scene\":\"\",\"characters\":[],\"camera\":\"\",\"sfx\":\"\",\"dialogue\":[{{\"type\":\"speech|thought|caption\",\"speaker\":\"\",\"text\":\"\"}}]}}]}}]}}",
                                "You are a comic writer and layout artist.", mock=mock)
        return [J(r, "Panel plan", next={"tool": "comics_generator", "set": {"stage": "render", "plan": json.dumps(r, indent=1, ensure_ascii=False)}, "label": "Edit & render"})]
    pl = json.loads(plan)
    size = {"Portrait": (1600, 2300), "Landscape": (2300, 1600), "Vertical Scroll": (1080, 3600)}[orientation]
    _, refs = ctx.cast("", characters)
    refs = ([character_photo] if character_photo else []) + refs
    rendered = []
    for pi, page in enumerate(pl["pages"]):
        arts = []
        for k, pn in enumerate(page["panels"]):
            ctx.progress(f"Page {pi + 1}, panel {k + 1}")
            p = f"Comic panel, {COMIC_STYLES[style]}. {pn.get('camera', '')} shot. {pn['scene']}. Characters: {', '.join(pn.get('characters', []))}. No text or speech bubbles in the art."
            art = ctx.router.image(p, aspect="4:3" if orientation != "Vertical Scroll" else "4:5", refs=refs or None, **route(model))[0]
            lines = [(f"{d['speaker']}: " if d.get("speaker") and d.get("type") != "caption" else "") + d["text"] for d in pn.get("dialogue", [])]
            arts.append((Image.open(art), lines, pn.get("sfx", "")))
        rendered.append(M.comic_page(arts, size, page.get("title", "")))
    files = [(f"Page {i + 1}", ctx.save_img(p, ".jpg")) for i, p in enumerate(rendered)]
    slug = re.sub(r"\W+", "-", pl.get("title", "comic")).strip("-").lower() or "comic"
    return files + [(f"{slug}.pdf", M.to_pdf(rendered, ctx.file(".pdf")))]


EXPLAINERS = {
    "Study Formats": ["Cheat Sheet", "Blueprint", "Flashcards", "Mind Map"],
    "Visual Learning": ["Flowchart", "Infographic", "Roadmap", "Timeline", "Comic Explainer", "Classroom Poster", "Chart/Graph", "Dashboard", "Process Diagram", "Venn Diagram", "Pyramid", "Cycle Diagram"],
    "Notes & Study Styles": ["Handwritten Notes", "Sketchnote", "Whiteboard", "Blackboard/Chalkboard", "Doodle Notes", "Sticky Notes Wall", "Notebook Page", "Bullet Journal"],
    "Technical & Object Viz": ["X-Ray", "Cutaway", "Exploded View", "Cross-Section", "Isometric", "System Diagram", "Wireframe", "Schematic", "Anatomy Chart", "Assembly Instructions", "Layer Diagram", "Network Map", "Floor Plan", "Patent Drawing", "Specimen Plate"],
    "Comparison & Decision": ["Compare (A vs B)", "Pros & Cons", "Myth vs Fact", "Decision Tree", "Comparison Matrix", "SWOT Analysis", "Do vs Don't", "Before vs After", "Ranking"],
    "Planning": ["30-Day Plan", "Action Plan", "Step-by-Step", "Strategy Map", "Funnel", "Org Chart", "Kanban Board", "Gantt Chart"],
    "Creative Visualization": ["Comic Panel", "Storyboard", "Pencil Sketch", "Poster", "Diorama", "Miniature World", "Fantasy Map", "Album Cover", "Moodboard/Scrapbook", "Museum Exhibit", "Tarot Card"],
    "Photo Style Transform": ["Action Figure", "Anime", "Studio Ghibli-Style", "Toy", "Plushie", "Clay", "Claymation", "Building-Block", "Pixel Art", "8-Bit", "Manga", "Cartoon", "Stylized 3D", "Photorealistic",
                              "Cinematic", "Film Noir", "Cyberpunk", "Steampunk", "Fantasy World", "Medieval", "Vintage", "Polaroid", "Oil Painting", "Watercolor", "Macro", "Fisheye", "Sticker", "Emoji",
                              "Logo", "Colorize", "Restore", "Upscale", "Remove Background", "Change Background", "Vinyl Figure", "Collectible Doll Box", "Trading Card", "Caricature", "Royal Portrait",
                              "Vaporwave", "Double Exposure", "Historical Era", "Retro VHS Cover"],
}


@tool("visual_explainer", "Visual Explainer Studio", "distribution", "🧩", "Any topic or photo → a visual in one of 120+ formats",
      "Topic mode (type a topic, paste notes or upload a document) or Photo mode (restyle a photo): pick a command — cheat sheet, mind map, flowchart, exploded view, SWOT, sketchnote, action figure… — and get the image, or just the engineered prompt.",
      [S("mode", "Mode", ["Topic", "Photo"]), F("topic", "Topic or notes", "textarea", showIf={"mode": ["Topic"]}), F("doc", "…or a document", "media", showIf={"mode": ["Topic"]}),
       F("photo", "Photo", "image", showIf={"mode": ["Photo"]}), S("command", "Command", [{"value": c, "label": f"{g} · {c}"} for g, cs in EXPLAINERS.items() for c in cs]),
       S("aspect", "Aspect", ["1:1", "16:9", "9:16", "4:3", "3:4", "2:3"]), F("prompt_only", "Prompt only (copy it)", "toggle", default=False), model_field("image")],
      ["image", "text"], ["image", "edit"])
def t_explainer(ctx, mode, topic, doc, photo, command, aspect, prompt_only, model):
    if mode == "Topic":
        topic = (topic or "") + ("\n" + read_text(doc)[:3000] if doc else "")
        if not topic.strip():
            raise ToolError("Give a topic or notes")
        prompt = f'Turn "{topic.strip()[:1500]}" into a {command}. Clear hierarchy, legible labels, accurate content, clean layout suited to a {command.lower()}.'
    else:
        if not photo:
            raise ToolError("Upload a photo")
        prompt = f"Transform this photo into a {command} version. Keep the subject recognisable."
    if prompt_only:
        return [T(prompt, "Engineered prompt", copy=True)]
    return [(command, ctx.router.image(prompt, aspect=aspect, refs=[photo] if photo else None, **route(model))[0]), T(prompt, "Prompt", copy=True)]


# ---------- catalogue groups ----------

CATEGORIES = [
    {"id": "film", "name": "Film Studio", "blurb": "One project, script to screen: script → cast → scenes → score → final cut."},
    {"id": "preproduction", "name": "Pre-production", "blurb": "Story, coverage, boards and budget before a single credit is spent."},
    {"id": "casting", "name": "Casting & continuity", "blurb": "Cast once, lock face, wardrobe, location and props for every shot."},
    {"id": "image", "name": "Image suite", "blurb": "Generate, then edit, relight, regrade, upscale and retouch."},
    {"id": "video", "name": "Video", "blurb": "Directed clips with a real camera rig across every major model."},
    {"id": "audio", "name": "Voice, music & sound", "blurb": "Voice-over, scores, songs, SFX and lip sync."},
    {"id": "ads", "name": "Ad Factory", "blurb": "Product data in, QC'd ads out: micro ads, e-commerce, UGC and batches."},
    {"id": "post", "name": "Post-production", "blurb": "Edit, caption and translate."},
    {"id": "distribution", "name": "Package & distribute", "blurb": "Highlights, thumbnails, posters, every size, comics and explainers."},
    {"id": "helpers", "name": "Prompt & quality", "blurb": "Guardrails that catch problems before you pay for them."},
]

PERSONAS = [
    {"id": "filmmakers", "name": "Filmmakers", "icon": "🎬", "pitch": "Script to screen: write, cover, board, budget, cast and lock, generate, cut, caption and package.",
     "tools": ["story_builder", "script_doctor", "storyboard_builder", "budget_estimator", "casting_director", "image_generation", "video_generation", "video_editor", "subtitle_creator", "video_intelligence", "poster_creation"]},
    {"id": "marketers", "name": "Marketers & agencies", "icon": "📣", "pitch": "On-brand creative and ads at scale, with QC before anything ships.",
     "tools": ["image_generation", "video_generation", "casting_director", "micro_ad_factory", "ugc_ads_studio", "video_batch", "subtitle_creator", "thumbnail_creator", "resize_adapt", "video_reframe"]},
    {"id": "ecommerce", "name": "E-commerce brands", "icon": "🛒", "pitch": "Every SKU consistent: try-on, model shoots, product video and marketplace sizes.",
     "tools": ["virtual_try_on", "model_photoshoot", "ecommerce_image_studio", "ecommerce_video_studio", "upscale", "relight", "color_grading", "palette_studio", "micro_ad_factory", "video_batch", "resize_adapt"]},
    {"id": "creators", "name": "Social creators", "icon": "📱", "pitch": "Auto-cut shorts, B-roll, persona consistency and thumbnails that click.",
     "tools": ["video_intelligence", "video_generation", "casting_director", "video_editor", "subtitle_creator", "thumbnail_creator", "video_reframe"]},
    {"id": "influencers", "name": "Influencers", "icon": "⭐", "pitch": "UGC ads for every brand deal, your face locked, batch per partner.",
     "tools": ["ugc_ads_studio", "casting_director", "expression_sheet", "micro_ad_factory", "video_batch", "thumbnail_creator", "subtitle_creator", "video_reframe"]},
]
