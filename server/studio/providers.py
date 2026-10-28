"""Model-agnostic provider layer for Studio.

Every tool asks for a *capability* (llm, image, video, tts, ...) and the router picks a provider:
the one set in Settings for that capability, else the first provider with an API key, else `mock`
(placeholder outputs, so every tool works end to end with no keys). Providers talk plain HTTPS through
urllib, so no SDKs are needed. Add a key in the environment (or Settings) to switch a capability on:

  FAL_KEY, OPENAI_API_KEY, GEMINI_API_KEY, ELEVENLABS_API_KEY, REPLICATE_API_TOKEN

Model ids drift; each provider's defaults live in MODELS and can be overridden per capability in Settings.
"""
from __future__ import annotations

import base64, json, mimetypes, os, subprocess, time, urllib.error, urllib.request, uuid
from pathlib import Path
from typing import Callable

CAPS = ["llm", "vision", "image", "edit", "video", "tts", "music", "sfx", "upscale", "video_upscale",
        "faceswap", "tryon", "inpaint", "bg_remove", "lipsync"]

CAP_LABEL = {"llm": "Text & scripts", "vision": "Image/video understanding", "image": "Image generation",
             "edit": "Image editing (reference images)", "video": "Video generation", "tts": "Voice / text to speech",
             "music": "Music", "sfx": "Sound effects", "upscale": "Image upscale", "video_upscale": "Video upscale",
             "faceswap": "Face swap", "tryon": "Virtual try-on", "inpaint": "Inpaint / erase", "bg_remove": "Background removal",
             "lipsync": "Lip sync"}

# Rough USD per call, only for the usage page. ponytail: static table; read real prices from provider invoices if it matters.
COST = {"llm": 0.002, "vision": 0.004, "image": 0.04, "edit": 0.04, "video": 0.5, "tts": 0.01, "music": 0.05, "sfx": 0.02,
        "upscale": 0.02, "video_upscale": 0.2, "faceswap": 0.02, "tryon": 0.05, "inpaint": 0.04, "bg_remove": 0.01, "lipsync": 0.3}

MODELS: dict[str, dict[str, list[str]]] = {
    "fal": {
        "image": ["fal-ai/flux/dev", "fal-ai/flux-pro/v1.1-ultra", "fal-ai/imagen4/preview", "fal-ai/bytedance/seedream/v4/text-to-image", "fal-ai/nano-banana"],
        "edit": ["fal-ai/nano-banana/edit", "fal-ai/bytedance/seedream/v4/edit", "fal-ai/flux-pro/kontext"],
        "video": ["fal-ai/kling-video/v2.1/master", "fal-ai/veo3", "fal-ai/bytedance/seedance/v1/pro", "fal-ai/minimax/hailuo-02/standard"],
        "tts": ["fal-ai/elevenlabs/tts/multilingual-v2"],
        "music": ["fal-ai/stable-audio", "fal-ai/lyria2"],
        "sfx": ["fal-ai/stable-audio"],
        "upscale": ["fal-ai/clarity-upscaler", "fal-ai/esrgan"],
        "video_upscale": ["fal-ai/video-upscaler"],
        "faceswap": ["fal-ai/face-swap"],
        "tryon": ["fal-ai/kling/v1-5/kolors-virtual-try-on"],
        "inpaint": ["fal-ai/flux-pro/v1/fill"],
        "bg_remove": ["fal-ai/birefnet"],
        "lipsync": ["fal-ai/sync-lipsync"],
    },
    "openai": {"llm": ["gpt-5-mini", "gpt-5", "gpt-4.1"], "vision": ["gpt-5-mini", "gpt-4.1"], "image": ["gpt-image-1"],
               "edit": ["gpt-image-1"], "inpaint": ["gpt-image-1"], "video": ["sora-2", "sora-2-pro"], "tts": ["gpt-4o-mini-tts"]},
    "gemini": {"llm": ["gemini-2.5-flash", "gemini-2.5-pro"], "vision": ["gemini-2.5-flash"], "image": ["gemini-2.5-flash-image"],
               "edit": ["gemini-2.5-flash-image"], "video": ["veo-3.0-generate-001", "veo-3.0-fast-generate-001"]},
    "elevenlabs": {"tts": ["eleven_multilingual_v2", "eleven_turbo_v2_5"], "music": ["music_v1"], "sfx": ["eleven_text_to_sound_v2"]},
    "replicate": {"image": ["black-forest-labs/flux-schnell", "black-forest-labs/flux-1.1-pro"], "video": ["kwaivgi/kling-v2.1", "minimax/video-01"],
                  "upscale": ["nightmareai/real-esrgan"], "bg_remove": ["851-labs/background-remover"]},
    "mock": {c: ["placeholder"] for c in CAPS},
}
KEY_ENV = {"fal": "FAL_KEY", "openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY", "elevenlabs": "ELEVENLABS_API_KEY", "replicate": "REPLICATE_API_TOKEN"}
ORDER = ["fal", "openai", "gemini", "elevenlabs", "replicate"]
# which provider is preferred per capability when several are configured
PREFER = {"llm": ["openai", "gemini", "fal"], "vision": ["openai", "gemini"], "tts": ["elevenlabs", "openai", "fal"],
          "music": ["elevenlabs", "fal"], "sfx": ["elevenlabs", "fal"], "image": ["fal", "openai", "gemini", "replicate"],
          "edit": ["fal", "gemini", "openai"], "video": ["fal", "gemini", "openai", "replicate"]}


class ProviderError(Exception):
    pass


class Out:
    """Where generated files land: a directory plus the public URL prefix it is served under."""
    def __init__(self, directory: Path, url_prefix: str):
        self.dir, self.url = directory, url_prefix
        directory.mkdir(parents=True, exist_ok=True)

    def path(self, ext: str) -> Path:
        return self.dir / f"{uuid.uuid4().hex[:10]}{ext}"

    def save(self, data: bytes, ext: str) -> Path:
        p = self.path(ext); p.write_bytes(data); return p

    def fetch(self, url: str, ext: str | None = None, headers: dict | None = None) -> Path:
        if url.startswith("data:"):
            head, b64 = url.split(",", 1)
            return self.save(base64.b64decode(b64), ext or mimetypes.guess_extension(head[5:].split(";")[0]) or ".bin")
        req = urllib.request.Request(url, headers={"User-Agent": "pulse-studio", **(headers or {})})
        with urllib.request.urlopen(req, timeout=600) as r:
            ct = (r.headers.get("content-type") or "").split(";")[0]
            ext = ext or Path(url.split("?")[0]).suffix or mimetypes.guess_extension(ct) or ".bin"
            return self.save(r.read(), ext)


# ---------- settings ----------

class Settings:
    def __init__(self, file: Path):
        self.file = file

    def load(self) -> dict:
        try:
            return json.loads(self.file.read_text())
        except Exception:
            return {"keys": {}, "routes": {}}

    def save(self, s: dict):
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(json.dumps(s, indent=1))

    def key(self, provider: str) -> str | None:
        return self.load().get("keys", {}).get(provider) or os.environ.get(KEY_ENV.get(provider, "_"))

    def configured(self) -> list[str]:
        return [p for p in ORDER if self.key(p)]

    def route(self, cap: str) -> tuple[str, str]:
        """(provider, model) for a capability."""
        r = self.load().get("routes", {}).get(cap) or {}
        prov, model = r.get("provider"), r.get("model")
        if prov and prov != "auto" and (prov == "mock" or self.key(prov)) and cap in MODELS.get(prov, {}):
            return prov, model or MODELS[prov][cap][0]
        for p in PREFER.get(cap, []) + ORDER:
            if self.key(p) and cap in MODELS.get(p, {}):
                return p, MODELS[p][cap][0]
        return "mock", "placeholder"

    def public(self) -> dict:
        s = self.load()
        return {"providers": [{"id": p, "env": KEY_ENV[p], "configured": bool(self.key(p)), "fromEnv": bool(os.environ.get(KEY_ENV[p])),
                               "caps": list(MODELS[p])} for p in ORDER],
                "caps": [{"id": c, "label": CAP_LABEL[c], "route": s.get("routes", {}).get(c) or {"provider": "auto"},
                          "active": dict(zip(["provider", "model"], self.route(c))),
                          "options": {p: MODELS[p][c] for p in ORDER + ["mock"] if c in MODELS[p]}} for c in CAPS]}


# ---------- http helpers ----------

def http(method: str, url: str, headers: dict | None = None, body: dict | bytes | None = None, timeout: int = 600, raw: bool = False):
    data = None; h = {"User-Agent": "pulse-studio", **(headers or {})}
    if isinstance(body, dict):
        data = json.dumps(body).encode(); h.setdefault("Content-Type", "application/json")
    elif body is not None:
        data = body
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            b = r.read()
            return b if raw else json.loads(b or b"{}")
    except urllib.error.HTTPError as e:
        raise ProviderError(f"{url.split('?')[0]} → {e.code}: {e.read().decode(errors='replace')[:600]}")
    except urllib.error.URLError as e:
        raise ProviderError(f"{url.split('?')[0]} unreachable: {e.reason}")


def multipart(fields: dict, files: dict[str, list[Path]]) -> tuple[bytes, str]:
    b = uuid.uuid4().hex; out = bytearray()
    for k, v in fields.items():
        out += f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    for k, paths in files.items():
        for p in paths:
            ct = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
            out += f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{p.name}\"\r\nContent-Type: {ct}\r\n\r\n".encode()
            out += p.read_bytes() + b"\r\n"
    out += f"--{b}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={b}"


def data_uri(p: Path) -> str:
    ct = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    return f"data:{ct};base64,{base64.b64encode(p.read_bytes()).decode()}"


def first_url(obj, kinds=("video", "image", "audio", "audio_file", "images", "output", "file")) -> list[str]:
    """Pull media URLs out of an arbitrary provider response."""
    urls: list[str] = []
    def walk(o):
        if isinstance(o, str) and (o.startswith("http") or o.startswith("data:")):
            urls.append(o)
        elif isinstance(o, dict):
            if isinstance(o.get("url"), str):
                urls.append(o["url"]); return
            for k in kinds:
                if k in o: walk(o[k])
            if not urls:
                for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(obj)
    return list(dict.fromkeys(urls))


def run(cmd: list[str], timeout: int = 600):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise ProviderError(r.stderr[-600:])
    return r


ASPECTS = {"16:9": (1344, 768), "9:16": (768, 1344), "1:1": (1024, 1024), "4:5": (896, 1120), "3:4": (896, 1152), "4:3": (1152, 896), "21:9": (1536, 640), "2:3": (832, 1248), "3:2": (1248, 832)}


# ---------- the router ----------

class Router:
    """Each method takes generic arguments, dispatches to the routed provider and returns text or file paths.
    `log` receives one usage record per provider call."""

    def __init__(self, settings: Settings, out: Out, log: Callable[[dict], None]):
        self.s, self.out, self.log = settings, out, log

    def _call(self, cap: str, fn_name: str, *a, provider: str | None = None, model: str | None = None, **kw):
        prov, mdl = self.s.route(cap)
        if provider and provider != "auto" and (provider == "mock" or self.s.key(provider)) and cap in MODELS.get(provider, {}):
            prov, mdl = provider, MODELS[provider][cap][0]
        if model and model != "auto" and prov != "mock":
            mdl = model
        impl = PROVIDERS[prov]
        fn = getattr(impl, fn_name, None)
        if fn is None:
            prov, mdl, fn = "mock", "placeholder", getattr(Mock, fn_name)
        t = time.time()
        res = fn(self, mdl, *a, **kw)
        self.last = {"cap": cap, "provider": prov, "model": mdl, "seconds": round(time.time() - t, 2), "usd": 0 if prov == "mock" else COST[cap]}
        self.log(dict(self.last))
        return res

    # text
    def llm(self, prompt: str, system: str = "", json_mode: bool = False, images: list[Path] | None = None, mock=None, **kw) -> str:
        cap = "vision" if images else "llm"
        if self.s.route(cap)[0] == "mock" and mock is not None:
            self.log({"cap": cap, "provider": "mock", "model": "placeholder", "seconds": 0, "usd": 0})
            return mock if isinstance(mock, str) else json.dumps(mock)
        return self._call(cap, "llm", prompt, system, json_mode, images or [], **kw)

    def llm_json(self, prompt: str, system: str = "", images=None, mock=None, **kw):
        txt = self.llm(prompt, system + "\nRespond with JSON only, no prose, no code fences.", True, images, mock=mock, **kw)
        txt = txt.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            return json.loads(txt)
        except json.JSONDecodeError:
            s, e = min([i for i in (txt.find("{"), txt.find("[")) if i >= 0], default=0), max(txt.rfind("}"), txt.rfind("]"))
            return json.loads(txt[s:e + 1])

    # media: each returns a list of Paths
    def image(self, prompt, aspect="1:1", n=1, refs=None, negative="", seed=None, **kw) -> list[Path]:
        if refs:
            return self._call("edit", "edit", prompt, refs, aspect, n, **kw)
        return self._call("image", "image", prompt, aspect, n, negative, seed, **kw)

    def video(self, prompt, image: Path | None = None, aspect="16:9", duration=5, end_image: Path | None = None, audio=False, **kw) -> list[Path]:
        return self._call("video", "video", prompt, image, aspect, duration, end_image, audio, **kw)

    def tts(self, text, voice="", speed=1.0, **kw) -> list[Path]:
        return self._call("tts", "tts", text, voice, speed, **kw)

    def music(self, prompt, duration=30, **kw) -> list[Path]:
        return self._call("music", "music", prompt, duration, **kw)

    def sfx(self, prompt, duration=5, **kw) -> list[Path]:
        return self._call("sfx", "sfx", prompt, duration, **kw)

    def upscale(self, image: Path, scale=2, **kw) -> list[Path]:
        return self._call("upscale", "upscale", image, scale, **kw)

    def video_upscale(self, video: Path, scale=2, **kw) -> list[Path]:
        return self._call("video_upscale", "video_upscale", video, scale, **kw)

    def faceswap(self, target: Path, face: Path, **kw) -> list[Path]:
        return self._call("faceswap", "faceswap", target, face, **kw)

    def tryon(self, person: Path, garment: Path, **kw) -> list[Path]:
        return self._call("tryon", "tryon", person, garment, **kw)

    def inpaint(self, image: Path, mask: Path, prompt: str, **kw) -> list[Path]:
        return self._call("inpaint", "inpaint", image, mask, prompt, **kw)

    def bg_remove(self, image: Path, **kw) -> list[Path]:
        return self._call("bg_remove", "bg_remove", image, **kw)

    def lipsync(self, video: Path, audio: Path, **kw) -> list[Path]:
        return self._call("lipsync", "lipsync", video, audio, **kw)


# ---------- fal.ai (queue API) ----------

class Fal:
    @staticmethod
    def _run(r: Router, model: str, args: dict) -> dict:
        h = {"Authorization": f"Key {r.s.key('fal')}"}
        sub = http("POST", f"https://queue.fal.run/{model}", h, args)
        status_url, resp_url = sub.get("status_url"), sub.get("response_url")
        if not status_url:
            return sub
        for _ in range(900):
            st = http("GET", status_url, h)
            if st.get("status") == "COMPLETED":
                return http("GET", resp_url, h)
            if st.get("status") in ("FAILED", "ERROR"):
                raise ProviderError(f"fal {model}: {st}")
            time.sleep(2)
        raise ProviderError(f"fal {model}: timed out")

    @staticmethod
    def _files(r: Router, res: dict, ext: str | None = None, kinds=None) -> list[Path]:
        urls = first_url(res, kinds) if kinds else first_url(res)
        if not urls:
            raise ProviderError(f"no media in response: {json.dumps(res)[:400]}")
        return [r.out.fetch(u, ext) for u in urls]

    @staticmethod
    def image(r, model, prompt, aspect, n, negative, seed):
        w, h = ASPECTS.get(aspect, (1024, 1024))
        args = {"prompt": prompt, "num_images": n, "image_size": {"width": w, "height": h}, "aspect_ratio": aspect}
        if negative: args["negative_prompt"] = negative
        if seed is not None: args["seed"] = int(seed)
        return Fal._files(r, Fal._run(r, model, args), kinds=("images", "image"))

    @staticmethod
    def edit(r, model, prompt, refs, aspect, n):
        uris = [data_uri(p) for p in refs]
        args = {"prompt": prompt, "image_urls": uris, "image_url": uris[0], "num_images": n, "aspect_ratio": aspect}
        return Fal._files(r, Fal._run(r, model, args), kinds=("images", "image"))

    @staticmethod
    def video(r, model, prompt, image, aspect, duration, end_image, audio):
        args = {"prompt": prompt, "aspect_ratio": aspect, "duration": str(int(duration)) if "veo" not in model else f"{int(duration)}s"}
        if "veo" in model: args["generate_audio"] = bool(audio)
        if image:
            args["image_url"] = data_uri(image); model = model.rstrip("/") + "/image-to-video"
            if end_image: args["tail_image_url"] = args["end_image_url"] = data_uri(end_image)
        elif "veo3" not in model:
            model = model.rstrip("/") + "/text-to-video"
        return Fal._files(r, Fal._run(r, model, args), ".mp4", kinds=("video",))

    @staticmethod
    def tts(r, model, text, voice, speed):
        return Fal._files(r, Fal._run(r, model, {"text": text, "voice": voice or "Rachel", "speed": speed}), ".mp3", kinds=("audio",))

    @staticmethod
    def music(r, model, prompt, duration):
        return Fal._files(r, Fal._run(r, model, {"prompt": prompt, "seconds_total": int(duration), "duration": int(duration)}), kinds=("audio_file", "audio"))

    sfx = music

    @staticmethod
    def upscale(r, model, image, scale):
        return Fal._files(r, Fal._run(r, model, {"image_url": data_uri(image), "scale": scale, "upscale_factor": scale}), kinds=("image",))

    @staticmethod
    def video_upscale(r, model, video, scale):
        return Fal._files(r, Fal._run(r, model, {"video_url": data_uri(video), "scale": scale}), ".mp4", kinds=("video",))

    @staticmethod
    def faceswap(r, model, target, face):
        return Fal._files(r, Fal._run(r, model, {"base_image_url": data_uri(target), "swap_image_url": data_uri(face)}), kinds=("image",))

    @staticmethod
    def tryon(r, model, person, garment):
        return Fal._files(r, Fal._run(r, model, {"human_image_url": data_uri(person), "garment_image_url": data_uri(garment)}), kinds=("image",))

    @staticmethod
    def inpaint(r, model, image, mask, prompt):
        return Fal._files(r, Fal._run(r, model, {"image_url": data_uri(image), "mask_url": data_uri(mask), "prompt": prompt}), kinds=("images", "image"))

    @staticmethod
    def bg_remove(r, model, image):
        return Fal._files(r, Fal._run(r, model, {"image_url": data_uri(image)}), ".png", kinds=("image",))

    @staticmethod
    def lipsync(r, model, video, audio):
        return Fal._files(r, Fal._run(r, model, {"video_url": data_uri(video), "audio_url": data_uri(audio)}), ".mp4", kinds=("video",))


# ---------- OpenAI ----------

class OpenAI:
    B = "https://api.openai.com/v1"

    @staticmethod
    def _h(r):
        return {"Authorization": f"Bearer {r.s.key('openai')}"}

    @staticmethod
    def llm(r, model, prompt, system, json_mode, images):
        content: list | str = prompt
        if images:
            content = [{"type": "text", "text": prompt}] + [{"type": "image_url", "image_url": {"url": data_uri(p)}} for p in images]
        body = {"model": model, "messages": ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": content}]}
        if json_mode: body["response_format"] = {"type": "json_object"}
        return http("POST", f"{OpenAI.B}/chat/completions", OpenAI._h(r), body)["choices"][0]["message"]["content"]

    @staticmethod
    def _size(aspect):
        return "1536x1024" if aspect in ("16:9", "3:2", "4:3", "21:9") else "1024x1536" if aspect in ("9:16", "2:3", "3:4", "4:5") else "1024x1024"

    @staticmethod
    def image(r, model, prompt, aspect, n, negative, seed):
        res = http("POST", f"{OpenAI.B}/images/generations", OpenAI._h(r), {"model": model, "prompt": prompt + (f"\nAvoid: {negative}" if negative else ""), "n": n, "size": OpenAI._size(aspect)})
        return [r.out.save(base64.b64decode(d["b64_json"]), ".png") if d.get("b64_json") else r.out.fetch(d["url"]) for d in res["data"]]

    @staticmethod
    def edit(r, model, prompt, refs, aspect, n, mask: Path | None = None):
        files = {"image[]": refs}
        if mask: files["mask"] = [mask]
        body, ct = multipart({"model": model, "prompt": prompt, "n": n, "size": OpenAI._size(aspect)}, files)
        res = http("POST", f"{OpenAI.B}/images/edits", {**OpenAI._h(r), "Content-Type": ct}, body)
        return [r.out.save(base64.b64decode(d["b64_json"]), ".png") for d in res["data"]]

    @staticmethod
    def inpaint(r, model, image, mask, prompt):
        # OpenAI masks are transparent where to paint; convert a white-on-black mask to that
        from PIL import Image, ImageOps
        m = ImageOps.invert(Image.open(mask).convert("L").resize(Image.open(image).size))
        rgba = Image.open(image).convert("RGBA"); rgba.putalpha(m)
        mp = r.out.path(".png"); rgba.save(mp)
        return OpenAI.edit(r, model, prompt, [image], "1:1", 1, mask=mp)

    @staticmethod
    def video(r, model, prompt, image, aspect, duration, end_image, audio):
        size = "720x1280" if aspect in ("9:16", "4:5", "3:4", "2:3") else "1280x720"
        fields = {"model": model, "prompt": prompt, "seconds": str(min([4, 8, 12], key=lambda s: abs(s - duration))), "size": size}
        body, ct = multipart(fields, {"input_reference": [image]} if image else {})
        job = http("POST", f"{OpenAI.B}/videos", {**OpenAI._h(r), "Content-Type": ct}, body)
        for _ in range(900):
            job = http("GET", f"{OpenAI.B}/videos/{job['id']}", OpenAI._h(r))
            if job.get("status") == "completed":
                return [r.out.save(http("GET", f"{OpenAI.B}/videos/{job['id']}/content", OpenAI._h(r), raw=True), ".mp4")]
            if job.get("status") == "failed":
                raise ProviderError(f"sora: {job.get('error')}")
            time.sleep(3)
        raise ProviderError("sora: timed out")

    @staticmethod
    def tts(r, model, text, voice, speed):
        return [r.out.save(http("POST", f"{OpenAI.B}/audio/speech", OpenAI._h(r), {"model": model, "input": text, "voice": voice or "alloy", "speed": speed}, raw=True), ".mp3")]


# ---------- Google Gemini / Veo ----------

class Gemini:
    B = "https://generativelanguage.googleapis.com/v1beta"

    @staticmethod
    def _gen(r, model, parts, cfg=None):
        return http("POST", f"{Gemini.B}/models/{model}:generateContent?key={r.s.key('gemini')}", None,
                    {"contents": [{"parts": parts}], **({"generationConfig": cfg} if cfg else {})})

    @staticmethod
    def _inline(p: Path):
        return {"inline_data": {"mime_type": mimetypes.guess_type(p.name)[0] or "image/png", "data": base64.b64encode(p.read_bytes()).decode()}}

    @staticmethod
    def llm(r, model, prompt, system, json_mode, images):
        parts = ([{"text": system}] if system else []) + [{"text": prompt}] + [Gemini._inline(p) for p in images]
        res = Gemini._gen(r, model, parts, {"responseMimeType": "application/json"} if json_mode else None)
        return "".join(p.get("text", "") for p in res["candidates"][0]["content"]["parts"])

    @staticmethod
    def edit(r, model, prompt, refs, aspect, n):
        out = []
        for _ in range(n):
            res = Gemini._gen(r, model, [{"text": f"{prompt}\nAspect ratio {aspect}."}] + [Gemini._inline(p) for p in refs], {"responseModalities": ["IMAGE", "TEXT"]})
            for p in res["candidates"][0]["content"]["parts"]:
                d = p.get("inline_data") or p.get("inlineData")
                if d: out.append(r.out.save(base64.b64decode(d["data"]), ".png"))
        if not out:
            raise ProviderError("gemini returned no image")
        return out

    @staticmethod
    def image(r, model, prompt, aspect, n, negative, seed):
        return Gemini.edit(r, model, prompt + (f"\nAvoid: {negative}" if negative else ""), [], aspect, n)

    @staticmethod
    def video(r, model, prompt, image, aspect, duration, end_image, audio):
        inst = {"prompt": prompt}
        if image:
            inst["image"] = {"bytesBase64Encoded": base64.b64encode(image.read_bytes()).decode(), "mimeType": mimetypes.guess_type(image.name)[0] or "image/png"}
        op = http("POST", f"{Gemini.B}/models/{model}:predictLongRunning?key={r.s.key('gemini')}", None,
                  {"instances": [inst], "parameters": {"aspectRatio": "9:16" if aspect == "9:16" else "16:9"}})
        for _ in range(900):
            op = http("GET", f"{Gemini.B}/{op['name']}?key={r.s.key('gemini')}")
            if op.get("done"):
                if op.get("error"): raise ProviderError(f"veo: {op['error']}")
                urls = first_url(op.get("response", {}))
                return [r.out.fetch(u if "key=" in u else u + ("&" if "?" in u else "?") + f"key={r.s.key('gemini')}", ".mp4") for u in urls[:1]]
            time.sleep(5)
        raise ProviderError("veo: timed out")


# ---------- ElevenLabs ----------

class ElevenLabs:
    B = "https://api.elevenlabs.io/v1"

    @staticmethod
    def _h(r):
        return {"xi-api-key": r.s.key("elevenlabs")}

    @staticmethod
    def tts(r, model, text, voice, speed):
        vid = voice if voice and len(voice) > 15 else "21m00Tcm4TlvDq8ikWAM"  # Rachel
        return [r.out.save(http("POST", f"{ElevenLabs.B}/text-to-speech/{vid}", ElevenLabs._h(r),
                                {"text": text, "model_id": model, "voice_settings": {"speed": speed}}, raw=True), ".mp3")]

    @staticmethod
    def music(r, model, prompt, duration):
        return [r.out.save(http("POST", f"{ElevenLabs.B}/music", ElevenLabs._h(r), {"prompt": prompt, "music_length_ms": int(duration * 1000)}, raw=True), ".mp3")]

    @staticmethod
    def sfx(r, model, prompt, duration):
        return [r.out.save(http("POST", f"{ElevenLabs.B}/sound-generation", ElevenLabs._h(r), {"text": prompt, "duration_seconds": min(22, duration)}, raw=True), ".mp3")]


# ---------- Replicate ----------

class Replicate:
    @staticmethod
    def _run(r, model, inp):
        h = {"Authorization": f"Bearer {r.s.key('replicate')}", "Prefer": "wait"}
        p = http("POST", f"https://api.replicate.com/v1/models/{model}/predictions", h, {"input": inp})
        while p.get("status") not in ("succeeded", "failed", "canceled"):
            time.sleep(2); p = http("GET", p["urls"]["get"], h)
        if p["status"] != "succeeded":
            raise ProviderError(f"replicate {model}: {p.get('error')}")
        return [r.out.fetch(u) for u in first_url(p.get("output"))]

    @staticmethod
    def image(r, model, prompt, aspect, n, negative, seed):
        return Replicate._run(r, model, {"prompt": prompt, "aspect_ratio": aspect, "num_outputs": n, **({"seed": int(seed)} if seed is not None else {})})

    @staticmethod
    def video(r, model, prompt, image, aspect, duration, end_image, audio):
        return Replicate._run(r, model, {"prompt": prompt, "aspect_ratio": aspect, "duration": int(duration), **({"start_image": data_uri(image)} if image else {})})

    @staticmethod
    def upscale(r, model, image, scale):
        return Replicate._run(r, model, {"image": data_uri(image), "scale": scale})

    @staticmethod
    def bg_remove(r, model, image):
        return Replicate._run(r, model, {"image": data_uri(image)})


# ---------- mock: placeholders so every tool runs without keys ----------

class Mock:
    @staticmethod
    def _card(r, text: str, aspect="1:1", tint=0, base: Path | None = None) -> Path:
        from PIL import Image, ImageDraw, ImageFont
        w, h = ASPECTS.get(aspect, (1024, 1024))
        if base:
            im = Image.open(base).convert("RGB")
        else:
            hue = (abs(hash(text)) + tint * 47) % 360
            im = Image.new("RGB", (w, h))
            top, bot = _hsv(hue, .55, .55), _hsv((hue + 60) % 360, .7, .22)
            px = ImageDraw.Draw(im)
            for y in range(h):
                t = y / h; px.line([(0, y), (w, y)], fill=tuple(int(top[i] * (1 - t) + bot[i] * t) for i in range(3)))
        d = ImageDraw.Draw(im)
        from .media import font
        f, fs = font(max(18, im.width // 30)), font(max(14, im.width // 48), bold=False)
        words, lines, cur = text.split(), [], ""
        for wd in words:
            if len(cur) + len(wd) > 38: lines.append(cur); cur = wd
            else: cur = f"{cur} {wd}".strip()
        lines.append(cur)
        y = im.height * .38
        d.text((im.width * .06, y - im.width / 18), "PLACEHOLDER · add an API key in Studio Settings", font=fs, fill=(255, 255, 255, 180))
        for ln in lines[:8]:
            d.text((im.width * .06, y), ln, font=f, fill=(255, 255, 255)); y += f.size * 1.3
        p = r.out.path(".png"); im.save(p); return p

    @staticmethod
    def llm(r, model, prompt, system, json_mode, images):
        return json.dumps({"note": "mock response", "prompt": prompt[:200]}) if json_mode else f"[mock] {prompt[:400]}"

    @staticmethod
    def image(r, model, prompt, aspect, n, negative, seed):
        return [Mock._card(r, prompt, aspect, i) for i in range(n)]

    @staticmethod
    def edit(r, model, prompt, refs, aspect, n):
        return [Mock._card(r, prompt, aspect, i, base=refs[0] if refs else None) for i in range(n)]

    @staticmethod
    def video(r, model, prompt, image, aspect, duration, end_image, audio):
        frame = Mock._card(r, prompt, aspect, base=image)
        p = r.out.path(".mp4")
        w, h = ASPECTS.get(aspect, (1344, 768))
        run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(frame), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", str(duration),
             "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},zoompan=z='min(zoom+0.0015,1.25)':d=1:s={w}x{h}:fps=30,format=yuv420p",
             "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", "-shortest", "-movflags", "+faststart", str(p)], timeout=300)
        return [p]

    @staticmethod
    def _tone(r, duration, expr="0.2*sin(2*PI*220*t)*exp(-0.5*mod(t,1))") -> Path:
        p = r.out.path(".m4a")
        run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"aevalsrc={expr.replace(',', chr(92) + ',')}:s=44100:d={duration}", "-c:a", "aac", str(p)])
        return [p]

    @staticmethod
    def tts(r, model, text, voice, speed):
        return Mock._tone(r, max(1.5, len(text.split()) / 2.6 / speed), "0.15*sin(2*PI*180*t)*(0.5+0.5*sin(2*PI*4*t))")

    @staticmethod
    def music(r, model, prompt, duration):
        return Mock._tone(r, duration, "0.12*sin(2*PI*(220+110*floor(mod(t,4)))*t)*exp(-2*mod(t,0.5))")

    @staticmethod
    def sfx(r, model, prompt, duration):
        return Mock._tone(r, duration, "0.3*random(0)*exp(-3*t)")

    @staticmethod
    def upscale(r, model, image, scale):
        from PIL import Image
        im = Image.open(image); im = im.resize((im.width * int(scale), im.height * int(scale)), Image.LANCZOS)
        p = r.out.path(".png"); im.save(p); return [p]

    @staticmethod
    def video_upscale(r, model, video, scale):
        p = r.out.path(".mp4")
        run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", f"scale=iw*{scale}:-2:flags=lanczos,unsharp", "-c:v", "libx264", "-preset", "veryfast", "-c:a", "copy", str(p)], timeout=1800)
        return [p]

    @staticmethod
    def faceswap(r, model, target, face):
        return [Mock._card(r, "face swap preview", base=target)]

    @staticmethod
    def tryon(r, model, person, garment):
        from PIL import Image
        im = Image.open(person).convert("RGB"); g = Image.open(garment).convert("RGBA")
        g.thumbnail((im.width // 2, im.height // 2)); im.paste(g, (im.width // 4, im.height // 3), g)
        p = r.out.path(".png"); im.save(p); return [p]

    @staticmethod
    def inpaint(r, model, image, mask, prompt):
        from PIL import Image, ImageFilter
        im = Image.open(image).convert("RGB"); m = Image.open(mask).convert("L").resize(im.size)
        im.paste(im.filter(ImageFilter.GaussianBlur(24)), (0, 0), m)
        p = r.out.path(".png"); im.save(p); return [p]

    @staticmethod
    def bg_remove(r, model, image):
        # corner-colour key: good enough for studio shots on a plain backdrop
        from PIL import Image
        im = Image.open(image).convert("RGBA"); bg = im.getpixel((2, 2))
        im.putdata([(*px[:3], 0) if sum(abs(px[i] - bg[i]) for i in range(3)) < 60 else px for px in im.getdata()])
        p = r.out.path(".png"); im.save(p); return [p]

    @staticmethod
    def lipsync(r, model, video, audio):
        p = r.out.path(".mp4")
        run(["ffmpeg", "-v", "error", "-y", "-stream_loop", "-1", "-i", str(video), "-i", str(audio), "-map", "0:v", "-map", "1:a", "-shortest", "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", str(p)], timeout=900)
        return [p]


def _hsv(h, s, v):
    import colorsys
    return tuple(int(c * 255) for c in colorsys.hsv_to_rgb(h / 360, s, v))


PROVIDERS = {"fal": Fal, "openai": OpenAI, "gemini": Gemini, "elevenlabs": ElevenLabs, "replicate": Replicate, "mock": Mock}
