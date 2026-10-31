"""Model-agnostic provider layer for Studio.

Every tool asks for a *capability* (llm, image, video, tts, ...) and the router picks a provider:
the one set in Settings for that capability, else the first provider with an API key, else `mock`
(placeholder outputs, so every tool works end to end with no keys). Providers talk plain HTTPS through
urllib, so no SDKs are needed. Add a key in the environment (or Settings) to switch a capability on:

  FAL_KEY, OPENAI_API_KEY, GEMINI_API_KEY, ELEVENLABS_API_KEY, REPLICATE_API_TOKEN,
  CLOUDFLARE_API_TOKEN (+ CLOUDFLARE_ACCOUNT_ID; free 10,000 Neurons a day, no card)

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

MODELS: dict[str, dict[str, list[str]]] = {  # verified 2026-10-28, see docs/provider-contracts.md
    "fal": {
        "image": ["fal-ai/flux/dev", "fal-ai/nano-banana-2", "fal-ai/flux-pro/v1.1-ultra", "fal-ai/flux-2-pro", "fal-ai/bytedance/seedream/v4.5/text-to-image"],
        "edit": ["fal-ai/nano-banana-2/edit", "fal-ai/bytedance/seedream/v4/edit", "fal-ai/flux-pro/kontext"],
        "video": ["fal-ai/kling-video/v3/pro", "fal-ai/veo3.1", "fal-ai/veo3.1/fast", "bytedance/seedance-2.0", "fal-ai/bytedance/seedance/v1/pro", "fal-ai/minimax/hailuo-02/standard"],
        "tts": ["fal-ai/elevenlabs/tts/multilingual-v2"],
        "music": ["fal-ai/stable-audio", "fal-ai/lyria2"],
        "sfx": ["fal-ai/stable-audio"],
        "upscale": ["fal-ai/clarity-upscaler", "fal-ai/esrgan"],
        "video_upscale": ["fal-ai/video-upscaler"],
        "faceswap": ["easel-ai/advanced-face-swap"],
        "tryon": ["fal-ai/kling/v1-5/kolors-virtual-try-on"],
        "inpaint": ["fal-ai/flux-pro/v1/fill"],
        "bg_remove": ["fal-ai/birefnet"],
        "lipsync": ["fal-ai/sync-lipsync"],
    },
    # Sora / the Videos API was shut down 2026-09-24, so OpenAI has no video capability
    "openai": {"llm": ["gpt-6-luna", "gpt-6.1-terra", "gpt-6.1-sol"], "vision": ["gpt-6.1-terra", "gpt-6-luna"],
               "image": ["gpt-image-2.5-flare", "gpt-image-2.5-sunburst", "gpt-image-2"], "edit": ["gpt-image-2.5-sunburst", "gpt-image-2.5-flare", "gpt-image-2"],
               "inpaint": ["gpt-image-2.5-sunburst", "gpt-image-2"], "tts": ["gpt-4o-mini-tts"]},
    "gemini": {"llm": ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-3.1-pro-preview"], "vision": ["gemini-3.8-flash"],
               "image": ["gemini-3.1-flash-image", "gemini-3-pro-image"], "edit": ["gemini-3.1-flash-image", "gemini-3-pro-image"],
               "video": ["gemini-omni-1.1-flash"], "tts": ["gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts"]},
    "elevenlabs": {"tts": ["eleven_multilingual_v2", "eleven_v3", "eleven_flash_v2_5"], "music": ["music_v2_5", "music_v2", "music_v1"], "sfx": ["eleven_text_to_sound_v2"]},
    "replicate": {"image": ["black-forest-labs/flux-schnell", "black-forest-labs/flux-1.1-pro"], "video": ["kwaivgi/kling-v3-video", "minimax/hailuo-2.3", "kwaivgi/kling-v2.1"],
                  "upscale": ["nightmareai/real-esrgan"], "bg_remove": ["bria/remove-background", "recraft-ai/recraft-remove-background"]},
    # cloudflare: Workers AI free allocation (10,000 Neurons/day: about 170 FLUX images or 80 edits, or ~300 long LLM answers)
    "cloudflare": {"llm": ["@cf/google/gemma-4-26b-a4b-it", "@cf/zai-org/glm-4.7-flash"], "vision": ["@cf/google/gemma-4-26b-a4b-it"],
                   "image": ["@cf/black-forest-labs/flux-1-schnell", "@cf/black-forest-labs/flux-2-klein-4b"],
                   "edit": ["@cf/black-forest-labs/flux-2-klein-4b"], "inpaint": ["@cf/black-forest-labs/flux-2-klein-4b"],
                   "tryon": ["@cf/black-forest-labs/flux-2-klein-4b"], "faceswap": ["@cf/black-forest-labs/flux-2-klein-4b"]},
    # free: public ZeroGPU Spaces + in-process Qwen3-VL and Kokoro (see free.py); no key, daily GPU quota
    "free": {"llm": ["Qwen3-VL-4B (this Space)"], "vision": ["Qwen3-VL-4B (this Space)"], "image": ["FLUX.1-schnell"], "edit": ["FLUX.1 Kontext / Qwen-Image-Edit"],
             "inpaint": ["Kontext + mask"], "tryon": ["Kontext panels"], "faceswap": ["Kontext panels"], "video": ["Wan 2.2 I2V / LTX-Video"],
             "music": ["ACE-Step"], "sfx": ["TangoFlux / Stable Audio Open"], "upscale": ["Finegrain enhancer"], "bg_remove": ["BiRefNet"], "lipsync": ["LatentSync"],
             "tts": ["Kokoro-82M (this Space)"], "video_upscale": ["ffmpeg lanczos (local)"]},
    "mock": {c: ["placeholder"] for c in CAPS},
}
KEY_ENV = {"free": "HF_TOKEN", "cloudflare": "CLOUDFLARE_API_TOKEN", "fal": "FAL_KEY", "openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY", "elevenlabs": "ELEVENLABS_API_KEY", "replicate": "REPLICATE_API_TOKEN"}
ORDER = ["fal", "openai", "gemini", "elevenlabs", "replicate", "cloudflare", "free"]  # free ones last: paid keys win when present
FREE_PROVIDERS = ("mock", "free", "cloudflare")
# which provider is preferred per capability when several are configured
PREFER = {"llm": ["openai", "gemini", "fal"], "vision": ["openai", "gemini"], "tts": ["elevenlabs", "gemini", "fal", "openai"],
          "music": ["elevenlabs", "fal"], "sfx": ["elevenlabs", "fal"], "image": ["fal", "openai", "gemini", "replicate"],
          "edit": ["fal", "gemini", "openai"], "video": ["fal", "gemini", "replicate"]}


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
        if provider == "free":  # needs no key; HF_TOKEN only raises the GPU quota
            from . import free
            return "on" if free.enabled() else None
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
        return {"providers": [{"id": p, "env": KEY_ENV[p], "configured": bool(self.key(p)), "fromEnv": bool(os.environ.get(KEY_ENV[p])) or p == "free",
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
        try:
            res = fn(self, mdl, *a, **kw)
        except ProviderError:
            # Cloudflare's daily free Neurons ran out (or it is down): fall through to the free Spaces
            alt = getattr(Free, fn_name, None)
            if prov != "cloudflare" or not alt or not self.s.key("free") or cap not in MODELS["free"]:
                raise
            prov, mdl, res = "free", MODELS["free"][cap][0], alt(self, MODELS["free"][cap][0], *a, **kw)
        self.last = {"cap": cap, "provider": prov, "model": mdl, "seconds": round(time.time() - t, 2), "usd": 0 if prov in FREE_PROVIDERS else COST[cap]}
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
# Each fal video family has its own duration enum and field names (docs/provider-contracts.md D4–D12).
FAL_DUR = {"veo3": ([4, 6, 8], lambda s: f"{s}s"), "kling-video/v2": ([5, 10], str), "kling-video/v3": (list(range(3, 16)), str),
           "kling-video/o3": (list(range(3, 16)), str), "seedance/v1": (list(range(2, 13)), str), "seedance-2": (list(range(4, 16)), str), "hailuo": ([6, 10], str)}
FAL_NO_ASPECT = ("hailuo",)        # Hailuo takes no aspect_ratio
FAL_I2V_NO_ASPECT = ("kling-video/",)  # Kling image-to-video follows the image


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
            if st.get("status") == "COMPLETED":  # fal reports failures as COMPLETED + error
                if st.get("error"):
                    raise ProviderError(f"fal {model}: {st.get('error_type', '')} {st['error']}")
                return http("GET", resp_url, h)
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
        args = {"prompt": prompt, "num_images": max(1, min(4, int(n)))}
        if any(k in model for k in ("flux/dev", "flux/schnell", "seedream", "flux-2")):
            args["image_size"] = {"width": w, "height": h}
        else:
            args["aspect_ratio"] = aspect if aspect in ("21:9", "16:9", "4:3", "3:2", "1:1", "2:3", "3:4", "9:16") or "nano-banana" in model else "1:1"
        if negative:
            args["prompt"] += f"\nAvoid: {negative}"
        if seed is not None: args["seed"] = int(seed)
        return Fal._files(r, Fal._run(r, model, args), kinds=("images", "image"))

    @staticmethod
    def edit(r, model, prompt, refs, aspect, n):
        uris = [data_uri(p) for p in refs]
        args = {"prompt": prompt, "num_images": max(1, min(4, int(n)))}
        if "kontext" in model: args["image_url"] = uris[0]
        else: args["image_urls"] = uris
        if "nano-banana" in model: args["aspect_ratio"] = aspect
        return Fal._files(r, Fal._run(r, model, args), kinds=("images", "image"))

    @staticmethod
    def video(r, model, prompt, image, aspect, duration, end_image, audio):
        m = model.rstrip("/")
        allowed, fmt = next((v for k, v in FAL_DUR.items() if k in m), ([5], str))
        args = {"prompt": prompt, "duration": fmt(min(allowed, key=lambda s: abs(s - duration)))}
        if not any(k in m for k in FAL_NO_ASPECT) and not (image and any(k in m for k in FAL_I2V_NO_ASPECT)):
            args["aspect_ratio"] = aspect if aspect in ("16:9", "9:16", "1:1", "21:9", "4:3", "3:4") else "16:9"
            if "veo3" in m and args["aspect_ratio"] not in ("16:9", "9:16"):
                args["aspect_ratio"] = "16:9"
        if any(k in m for k in ("veo3", "kling-video/v3", "kling-video/o3", "seedance-2")):
            args["generate_audio"] = bool(audio)
        if image:
            img = data_uri(image)
            if "veo3.1" in m and end_image:
                m += "/first-last-frame-to-video"; args["first_frame_url"] = img; args["last_frame_url"] = data_uri(end_image)
            else:
                m += "/image-to-video"
                args["start_image_url" if any(k in m for k in ("kling-video/v3", "kling-video/o3")) else "image_url"] = img
                if end_image and not any(k in m for k in ("veo3", "kling-video/v2")):
                    args["end_image_url"] = data_uri(end_image)
        elif "veo3" not in m:
            m += "/text-to-video"
        return Fal._files(r, Fal._run(r, m, args), ".mp4", kinds=("video",))

    @staticmethod
    def tts(r, model, text, voice, speed):
        args = {"text": text, "speed": max(0.7, min(1.2, speed))}
        if voice: args["voice"] = voice  # default voices are being retired; let the model pick when none is set
        return Fal._files(r, Fal._run(r, model, args), ".mp3", kinds=("audio",))

    @staticmethod
    def music(r, model, prompt, duration):
        args = {"prompt": prompt}
        if "stable-audio" in model: args["seconds_total"] = max(1, min(47, int(duration)))
        return Fal._files(r, Fal._run(r, model, args), kinds=("audio_file", "audio"))

    sfx = music

    @staticmethod
    def upscale(r, model, image, scale):
        return Fal._files(r, Fal._run(r, model, {"image_url": data_uri(image), "scale": scale, "upscale_factor": scale}), kinds=("image",))

    @staticmethod
    def video_upscale(r, model, video, scale):
        return Fal._files(r, Fal._run(r, model, {"video_url": data_uri(video), "scale": scale}), ".mp4", kinds=("video",))

    @staticmethod
    def faceswap(r, model, target, face, gender="non-binary"):
        args = {"face_image_0": data_uri(face), "gender_0": gender, "target_image": data_uri(target), "workflow_type": "target_hair", "upscale": True}
        return Fal._files(r, Fal._run(r, model, args), kinds=("image",))

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

OPENAI_VOICES = {"alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer", "verse", "marin", "cedar"}


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
    def _size(aspect):  # GPT Image 2.x takes exact sizes (edges multiples of 16)
        return {"16:9": "1536x864", "9:16": "864x1536", "1:1": "1024x1024", "4:5": "1024x1280", "3:4": "960x1280", "4:3": "1280x960",
                "21:9": "1680x720", "2:3": "1024x1536", "3:2": "1536x1024"}.get(aspect, "auto")

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
        # mask and image must share format and size; transparent = paint here
        from PIL import Image, ImageOps
        src_im = Image.open(image).convert("RGB"); src = r.out.path(".png"); src_im.save(src)
        m = ImageOps.invert(Image.open(mask).convert("L").resize(src_im.size))
        rgba = src_im.convert("RGBA"); rgba.putalpha(m)
        mp = r.out.path(".png"); rgba.save(mp)
        return OpenAI.edit(r, model, prompt, [src], "auto", 1, mask=mp)

    @staticmethod
    def tts(r, model, text, voice, speed):
        v = voice.lower() if voice and voice.lower() in OPENAI_VOICES else "marin"
        return [r.out.save(http("POST", f"{OpenAI.B}/audio/speech", OpenAI._h(r), {"model": model, "input": text, "voice": v, "speed": speed}, raw=True), ".mp3")]


# ---------- Google Gemini (generateContent + Interactions) ----------

GEMINI_VOICES = {"Zephyr", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", "Aoede", "Callirrhoe", "Autonoe", "Enceladus", "Iapetus", "Umbriel", "Algieba", "Despina",
                 "Erinome", "Algenib", "Rasalgethi", "Laomedeia", "Achernar", "Alnilam", "Schedar", "Gacrux", "Pulcherrima", "Achird", "Zubenelgenubi", "Vindemiatrix",
                 "Sadachbia", "Sadaltager", "Sulafat"}


class Gemini:
    B = "https://generativelanguage.googleapis.com/v1beta"

    @staticmethod
    def _h(r):
        return {"x-goog-api-key": r.s.key("gemini")}

    @staticmethod
    def _gen(r, model, parts, cfg=None, system=""):
        body = {"contents": [{"role": "user", "parts": parts}], **({"generationConfig": cfg} if cfg else {})}
        if system: body["systemInstruction"] = {"parts": [{"text": system}]}
        return http("POST", f"{Gemini.B}/models/{model}:generateContent", Gemini._h(r), body)

    @staticmethod
    def _inline(p: Path):
        return {"inline_data": {"mime_type": mimetypes.guess_type(p.name)[0] or "image/png", "data": base64.b64encode(p.read_bytes()).decode()}}

    @staticmethod
    def llm(r, model, prompt, system, json_mode, images):
        parts = [{"text": prompt}] + [Gemini._inline(p) for p in images]
        res = Gemini._gen(r, model, parts, {"responseMimeType": "application/json"} if json_mode else None, system)
        return "".join(p.get("text", "") for p in res["candidates"][0]["content"]["parts"])

    @staticmethod
    def edit(r, model, prompt, refs, aspect, n):
        cfg = {"responseModalities": ["TEXT", "IMAGE"],
               "imageConfig": {"aspectRatio": aspect if aspect in ("1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9") else "1:1"}}
        out = []
        for _ in range(n):
            res = Gemini._gen(r, model, [{"text": prompt}] + [Gemini._inline(p) for p in refs], cfg)
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
    def _interact(r, body, timeout_polls=900):
        h = Gemini._h(r)
        it = http("POST", f"{Gemini.B}/interactions", h, body)
        for _ in range(timeout_polls):
            if it.get("status") in (None, "completed", "failed", "cancelled", "incomplete"):
                break
            time.sleep(5); it = http("GET", f"{Gemini.B}/interactions/{it['id']}", h)
        if it.get("status") not in (None, "completed"):
            raise ProviderError(f"gemini: {it.get('status')} {json.dumps(it)[:300]}")
        return it

    @staticmethod
    def video(r, model, prompt, image, aspect, duration, end_image, audio):
        """Gemini Omni on the Interactions API (Veo's predictLongRunning is retired)."""
        parts = [{"type": "image", "data": base64.b64encode(p.read_bytes()).decode(), "mime_type": mimetypes.guess_type(p.name)[0] or "image/png"}
                 for p in (image, end_image) if p]
        text = prompt + (f" The clip is about {int(duration)} seconds long." if duration else "")
        if not audio: text += " No dialogue, no music."
        if image: text = ("<FIRST_FRAME> <LAST_FRAME> " if end_image else "<FIRST_FRAME> ") + text
        parts.append({"type": "text", "text": text})
        it = Gemini._interact(r, {"model": model, "input": parts, "background": True,
                                  "response_format": {"type": "video", "aspect_ratio": "9:16" if aspect in ("9:16", "4:5", "3:4", "2:3") else "16:9", "delivery": "uri"}})
        for step in it.get("steps", []):
            if step.get("type") != "model_output": continue
            for c in step.get("content", []):
                if c.get("type") == "video":
                    if c.get("data"): return [r.out.save(base64.b64decode(c["data"]), ".mp4")]
                    if c.get("uri"):
                        for _ in range(60):  # the file can take a moment to become downloadable
                            try:
                                return [r.out.fetch(c["uri"], ".mp4", headers=Gemini._h(r))]
                            except urllib.error.HTTPError:
                                time.sleep(3)
        raise ProviderError("gemini omni returned no video")

    @staticmethod
    def tts(r, model, text, voice, speed):
        style = "speaking slowly" if speed < 0.9 else "speaking quickly" if speed > 1.15 else "natural, clear"
        it = Gemini._interact(r, {"model": model, "response_format": {"type": "audio"},
                                  "input": [{"type": "user_input", "content": [{"type": "text", "text": text, "annotations": [{"type": "speech_metadata", "style": style}]}]}],
                                  "generation_config": {"speech_config": [{"voice": voice if (voice in GEMINI_VOICES or str(voice).startswith("voice_")) else "Kore"}]}})
        for step in it.get("steps", []):
            for c in step.get("content", []):
                if c.get("type") == "audio" and c.get("data"):
                    return [r.out.save(base64.b64decode(c["data"]), ".wav")]
        raise ProviderError("gemini tts returned no audio")


# ---------- ElevenLabs ----------

class ElevenLabs:
    B = "https://api.elevenlabs.io/v1"

    @staticmethod
    def _h(r):
        return {"xi-api-key": r.s.key("elevenlabs")}

    @staticmethod
    def _voice(r, voice):
        """A voice id, or a voice name looked up on the account (default voices are being retired)."""
        if voice and len(voice) > 15:
            return voice
        vs = http("GET", "https://api.elevenlabs.io/v2/voices?page_size=100", ElevenLabs._h(r)).get("voices", [])
        hit = next((v for v in vs if voice and v.get("name", "").lower() == voice.lower()), None) or (vs[0] if vs else None)
        if not hit:
            raise ProviderError("no ElevenLabs voices on this account; add one or pass a voice_id")
        return hit["voice_id"]

    @staticmethod
    def tts(r, model, text, voice, speed):
        return [r.out.save(http("POST", f"{ElevenLabs.B}/text-to-speech/{ElevenLabs._voice(r, voice)}", ElevenLabs._h(r),
                                {"text": text, "model_id": model, "voice_settings": {"speed": max(0.7, min(1.2, speed))}}, raw=True), ".mp3")]

    @staticmethod
    def music(r, model, prompt, duration):
        return [r.out.save(http("POST", f"{ElevenLabs.B}/music", ElevenLabs._h(r),
                                {"prompt": prompt, "model_id": model, "music_length_ms": max(3000, min(600000, int(duration * 1000)))}, raw=True), ".mp3")]

    @staticmethod
    def sfx(r, model, prompt, duration):
        return [r.out.save(http("POST", f"{ElevenLabs.B}/sound-generation", ElevenLabs._h(r),
                                {"text": prompt, "model_id": model, "duration_seconds": max(0.5, min(30, float(duration)))}, raw=True), ".mp3")]


# ---------- Replicate ----------

class Replicate:
    @staticmethod
    def _h(r):
        return {"Authorization": f"Bearer {r.s.key('replicate')}"}

    @staticmethod
    def _file(r, p: Path) -> str:
        """Data URI for small files, the Files API for big ones (Replicate recommends data URIs under 1 MB)."""
        if p.stat().st_size < 900_000:
            return data_uri(p)
        body, ct = multipart({}, {"content": [p]})
        return http("POST", "https://api.replicate.com/v1/files", {**Replicate._h(r), "Content-Type": ct}, body)["urls"]["get"]

    @staticmethod
    def _run(r, model, inp):
        h = {**Replicate._h(r), "Prefer": "wait"}
        # official models run by name; community models need owner/name:version
        url, body = (("https://api.replicate.com/v1/predictions", {"version": model.split(":", 1)[1], "input": inp}) if ":" in model
                     else (f"https://api.replicate.com/v1/models/{model}/predictions", {"input": inp}))
        p = http("POST", url, h, body)
        while p.get("status") not in ("succeeded", "failed", "canceled"):
            time.sleep(2); p = http("GET", p["urls"]["get"], h)
        if p["status"] != "succeeded":
            raise ProviderError(f"replicate {model}: {p.get('error')}")
        return [r.out.fetch(u) for u in first_url(p.get("output"))]

    @staticmethod
    def image(r, model, prompt, aspect, n, negative, seed):
        base = {"prompt": prompt + (f"\nAvoid: {negative}" if negative else ""), "aspect_ratio": aspect, **({"seed": int(seed)} if seed is not None else {})}
        if "schnell" in model or "flux-dev" in model:
            return Replicate._run(r, model, {**base, "num_outputs": max(1, min(4, int(n)))})
        return [p for _ in range(int(n)) for p in Replicate._run(r, model, base)]

    @staticmethod
    def video(r, model, prompt, image, aspect, duration, end_image, audio):
        if model.startswith("minimax/"):
            inp = {"prompt": prompt, **({"first_frame_image": Replicate._file(r, image)} if image else {})}
            if "hailuo" in model: inp["duration"] = 10 if duration > 8 else 6
        else:  # kwaivgi/kling-*
            v3 = "v3" in model
            inp = {"prompt": prompt, "duration": max(3, min(15, int(duration))) if v3 else (10 if duration > 7 else 5)}
            if image: inp["start_image"] = Replicate._file(r, image)
            elif not v3: raise ProviderError("kling-v2.1 on Replicate needs a start image")
            if end_image and v3: inp["end_image"] = Replicate._file(r, end_image)
            if v3:
                inp["generate_audio"] = bool(audio)
                if not image: inp["aspect_ratio"] = aspect if aspect in ("16:9", "9:16", "1:1") else "16:9"
        return Replicate._run(r, model, inp)

    @staticmethod
    def upscale(r, model, image, scale):
        return Replicate._run(r, model, {"image": Replicate._file(r, image), "scale": scale})

    @staticmethod
    def bg_remove(r, model, image):
        return Replicate._run(r, model, {"image": Replicate._file(r, image), **({"preserve_alpha": True} if model.startswith("bria/") else {})})


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


class Cloudflare:
    """Workers AI on the free allocation: FLUX images and FLUX.2 klein edits, Gemma 4 for text and vision.
    Set CLOUDFLARE_API_TOKEN (Workers AI permission) and CLOUDFLARE_ACCOUNT_ID, or save the key as "ACCOUNT_ID:TOKEN"."""

    @staticmethod
    def _base(r):
        import re
        clean = lambda v: re.sub(r"[^\x21-\x7e]", "", v or "")  # pasted secrets often carry spaces, newlines or U+2028
        key = clean(r.s.key("cloudflare"))
        acct, tok = key.split(":", 1) if ":" in key else (clean(os.environ.get("CLOUDFLARE_ACCOUNT_ID")), key)
        if not acct:
            raise ProviderError("Cloudflare needs CLOUDFLARE_ACCOUNT_ID (or save the key as ACCOUNT_ID:TOKEN)")
        return f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai", {"Authorization": f"Bearer {tok}"}

    @staticmethod
    def _run(r, model, body=None, form=None, files=None):
        base, h = Cloudflare._base(r)
        if form is not None:
            data, ct = multipart(form, files or {})
            res = http("POST", f"{base}/run/{model}", {**h, "Content-Type": ct}, data)
        else:
            res = http("POST", f"{base}/run/{model}", h, body)
        if not res.get("success", True):
            raise ProviderError(f"cloudflare {model}: {res.get('errors')}")
        return res.get("result", res)

    @staticmethod
    def llm(r, model, prompt, system, json_mode, images):
        import re
        base, h = Cloudflare._base(r)
        content: list | str = prompt + ("\nReturn valid JSON only." if json_mode else "")
        if images:
            content = [{"type": "text", "text": content}] + [{"type": "image_url", "image_url": {"url": data_uri(Cloudflare._small(r, p, 1024))}} for p in images[:6]]
        body = {"model": model, "max_tokens": 4096, "messages": ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": content}]}
        res = http("POST", f"{base}/v1/chat/completions", h, body)
        txt = res["choices"][0]["message"].get("content") or ""
        return re.sub(r"<think>.*?</think>", "", txt, flags=re.S).strip()

    @staticmethod
    def _small(r, p: Path, edge: int) -> Path:
        """Workers AI image inputs must be small (FLUX.2 klein: under 512x512)."""
        from PIL import Image
        im = Image.open(p).convert("RGB"); im.thumbnail((edge, edge)); q = r.out.path(".png"); im.save(q); return q

    @staticmethod
    def _dims(aspect, cap=1024):
        w, h = ASPECTS.get(aspect, (1024, 1024)); s = min(1.0, cap / max(w, h))
        return int(w * s) // 16 * 16, int(h * s) // 16 * 16

    @staticmethod
    def image(r, model, prompt, aspect, n, negative, seed):
        p = prompt + (f". Avoid: {negative}" if negative else "")
        out = []
        for i in range(max(1, min(4, int(n)))):
            if "klein" in model:
                w, h = Cloudflare._dims(aspect)
                res = Cloudflare._run(r, model, form={"prompt": p, "width": w, "height": h})
            else:  # flux-1-schnell: square 1024, up to 8 steps; crop to the aspect locally
                res = Cloudflare._run(r, model, {"prompt": p, "steps": 4, **({"seed": int(seed) + i} if seed is not None else {})})
            img = r.out.save(base64.b64decode(res["image"]), ".jpg")
            if "klein" not in model and aspect not in ("1:1", None):
                from PIL import Image
                im = Image.open(img); w, h = ASPECTS.get(aspect, (1024, 1024)); W, H = im.size
                cw, ch = (W, int(W * h / w)) if w >= h else (int(H * w / h), H)
                im.crop(((W - cw) // 2, (H - ch) // 2, (W + cw) // 2, (H + ch) // 2)).save(img)
            out.append(img)
        return out

    @staticmethod
    def edit(r, model, prompt, refs, aspect, n):
        from PIL import Image
        src = Image.open(refs[0]); w, h = src.size; s = 1024 / max(w, h)
        W, H = max(256, int(w * s) // 16 * 16), max(256, int(h * s) // 16 * 16)
        files = {f"input_image_{i}": [Cloudflare._small(r, p, 504)] for i, p in enumerate(refs[:4])}
        lead = "Edit image 0" + (f" using images 1-{len(refs[:4]) - 1} as references" if len(refs) > 1 else "") + ": "
        return [r.out.save(base64.b64decode(Cloudflare._run(r, model, form={"prompt": lead + prompt, "width": W, "height": H}, files=files)["image"]), ".jpg")
                for _ in range(max(1, min(4, int(n))))]

    @staticmethod
    def inpaint(r, model, image, mask, prompt):
        from PIL import Image, ImageFilter
        res = Cloudflare.edit(r, model, f"{prompt}. Change only what the instruction asks; keep everything else identical.", [image], "1:1", 1)[0]
        src = Image.open(image).convert("RGB"); new = Image.open(res).convert("RGB").resize(src.size)
        m = Image.open(mask).convert("L").resize(src.size).filter(ImageFilter.GaussianBlur(6))
        src.paste(new, (0, 0), m); p = r.out.path(".png"); src.save(p); return [p]

    @staticmethod
    def tryon(r, model, person, garment):
        return Cloudflare.edit(r, model, "dress the person from image 0 in the garment from image 1, matching its colour, fabric and cut; keep the face, pose and background", [person, garment], "3:4", 1)

    @staticmethod
    def faceswap(r, model, target, face):
        return Cloudflare.edit(r, model, "give the person in image 0 the face of the person in image 1; keep the lighting, pose, expression and hair of image 0", [target, face], "1:1", 1)


class Free:
    """No-cost provider: public ZeroGPU Spaces for media, in-process Qwen3-VL for text/vision, Kokoro for voice."""

    @staticmethod
    def _dims(aspect, cap=1024, mult=32):
        w, h = ASPECTS.get(aspect, (1024, 1024)); s = min(1.0, cap / max(w, h))
        return int(w * s) // mult * mult, int(h * s) // mult * mult

    @staticmethod
    def llm(r, model, prompt, system, json_mode, images):
        from . import free
        return free.chat(prompt + ("\nReturn valid JSON only." if json_mode else ""), system, images)

    @staticmethod
    def image(r, model, prompt, aspect, n, negative, seed):
        from . import free
        w, h = Free._dims(aspect)
        out = []
        for i in range(max(1, min(4, int(n)))):
            kw = dict(prompt=prompt + (f". Avoid: {negative}" if negative else ""), seed=int(seed or 0) + i, randomize_seed=seed is None,
                      width=w, height=h, num_inference_steps=4)
            res = free.first_ok(lambda: free.call(free.SPACES["image"], "/infer", **kw), lambda: free.call(free.FALLBACK["image"], "/infer", **kw))
            out.append(free.keep(r, free.path_of(res)))
        return out

    @staticmethod
    def _panels(r, paths: list[Path]) -> tuple[Path, list[tuple[int, int, int, int]]]:
        """Several references side by side in one image (Qwen-Image-Edit takes one); returns the boxes."""
        from PIL import Image
        ims = [Image.open(p).convert("RGB") for p in paths]
        H = 768; ims = [im.resize((max(1, int(im.width * H / im.height)), H)) for im in ims]
        W = sum(im.width for im in ims); sheet = Image.new("RGB", (W, H), "white"); boxes, x = [], 0
        for im in ims:
            sheet.paste(im, (x, 0)); boxes.append((x, 0, x + im.width, H)); x += im.width
        p = r.out.path(".png"); sheet.save(p); return p, boxes

    @staticmethod
    def _edit_one(r, image: Path, prompt: str) -> Path:
        from gradio_client import handle_file
        from . import free
        res = free.first_ok(
            lambda: free.call(free.SPACES["edit"], "/infer", input_image=handle_file(str(image)), prompt=prompt, seed=0, randomize_seed=True,
                              guidance_scale=2.5, steps=16),  # Kontext: 16 steps keeps the GPU reservation small
            lambda: free.call(free.FALLBACK["edit"], "/infer", image=handle_file(str(image)), prompt=prompt, seed=0, randomize_seed=True,
                              true_guidance_scale=4.0, num_inference_steps=30, rewrite_prompt=False))
        return free.keep(r, free.path_of(res))

    @staticmethod
    def edit(r, model, prompt, refs, aspect, n):
        from PIL import Image
        if len(refs) == 1:
            return [Free._edit_one(r, refs[0], prompt) for _ in range(max(1, min(4, int(n))))]
        sheet, boxes = Free._panels(r, refs)
        out = []
        for _ in range(max(1, min(4, int(n)))):
            res = Free._edit_one(r, sheet, f"The image is {len(refs)} panels side by side: the leftmost is the base to edit, the others are references. "
                                         f"Edit only the leftmost panel: {prompt}. Keep every panel's layout.")
            im = Image.open(res); sx = im.width / Image.open(sheet).width; x0, y0, x1, y1 = boxes[0]
            crop = im.crop((int(x0 * sx), 0, int(x1 * sx), im.height)); p = r.out.path(".png"); crop.save(p); out.append(p)
        return out

    @staticmethod
    def inpaint(r, model, image, mask, prompt):
        from PIL import Image, ImageFilter
        res = Free._edit_one(r, image, f"{prompt}. Change only what the instruction asks; keep everything else identical.")
        src = Image.open(image).convert("RGB"); new = Image.open(res).convert("RGB").resize(src.size)
        m = Image.open(mask).convert("L").resize(src.size).filter(ImageFilter.GaussianBlur(6))
        src.paste(new, (0, 0), m); p = r.out.path(".png"); src.save(p); return [p]

    @staticmethod
    def tryon(r, model, person, garment):
        return Free.edit(r, model, "dress the person in the garment shown in the second panel, matching its colour, fabric and cut; keep the face, pose and background", [person, garment], "3:4", 1)

    @staticmethod
    def faceswap(r, model, target, face):
        return Free.edit(r, model, "replace the face of the person with the face shown in the second panel; keep the scene's lighting, pose, expression and hair", [target, face], "1:1", 1)

    @staticmethod
    def _ltx(r, prompt, image, aspect, duration):
        from gradio_client import handle_file
        from . import free
        w, h = {"16:9": (768, 448), "9:16": (448, 768), "1:1": (576, 576), "4:5": (512, 640), "21:9": (896, 384), "4:3": (640, 480), "3:4": (480, 640)}.get(aspect, (768, 448))
        kw = dict(prompt=prompt, negative_prompt="worst quality, inconsistent motion, blurry, jittery, distorted", input_video_filepath=None,
                  height_ui=h, width_ui=w, duration_ui=max(0.5, min(8.5, float(duration))), ui_frames_to_use=9, seed_ui=42, randomize_seed=True,
                  ui_guidance_scale=1, improve_texture_flag=True)
        if image:
            return free.call(free.FALLBACK["video"], "/image_to_video", input_image_filepath=handle_file(str(image)), mode="image-to-video", **kw)
        return free.call(free.FALLBACK["video"], "/text_to_video", input_image_filepath=None, mode="text-to-video", **kw)

    @staticmethod
    def video(r, model, prompt, image, aspect, duration, end_image, audio):
        """Wan 2.2 image-to-video (small GPU reservation). With no start image, FLUX draws the first frame."""
        from gradio_client import handle_file
        from PIL import Image
        from . import free
        def wan():
            start = image or Free.image(r, model, prompt + ", cinematic film still", aspect, 1, "", None)[0]
            src = Path(start)
            if src.suffix.lower() not in (".png", ".jpg", ".jpeg"):
                src = r.out.path(".png"); Image.open(start).convert("RGB").save(src)
            return free.call(free.SPACES["video"], "/generate_video", input_image=handle_file(str(src)), prompt=prompt,
                             steps=4, duration_seconds=max(0.5, min(5.0, float(duration))), guidance_scale=1, guidance_scale_2=1,
                             seed=42, randomize_seed=True)
        res = free.first_ok(wan, lambda: Free._ltx(r, prompt, image, aspect, duration))
        return [free.keep(r, free.path_of(res), ".mp4")]

    @staticmethod
    def music(r, model, prompt, duration):
        from . import free
        instrumental = "instrumental" in prompt.lower() and "lyrics:" not in prompt.lower()
        lyrics = prompt.split("Lyrics:", 1)[1].strip() if "Lyrics:" in prompt else "[instrumental]"
        res = free.call(free.SPACES["music"], "/__call__", audio_duration=float(max(5, min(240, duration))), prompt=prompt.split("Lyrics:", 1)[0][:600],
                        lyrics="[instrumental]" if instrumental else lyrics, infer_step=27, guidance_scale=15.0, scheduler_type="euler", cfg_type="apg",
                        omega_scale=10.0, manual_seeds=None, guidance_interval=0.5, guidance_interval_decay=0.0, min_guidance_scale=3.0,
                        use_erg_tag=True, use_erg_lyric=False, use_erg_diffusion=True, oss_steps=None, guidance_scale_text=0.0,
                        guidance_scale_lyric=0.0, audio2audio_enable=False, ref_audio_strength=0.5, ref_audio_input=None, lora_name_or_path="none")
        return [free.keep(r, free.path_of(res))]

    @staticmethod
    def sfx(r, model, prompt, duration):
        from . import free
        res = free.first_ok(
            lambda: free.call(free.SPACES["sfx"], "/predict", prompt=prompt, steps=25, guidance=4.5, duration=float(max(1, min(30, round(duration))))),
            lambda: free.call(free.FALLBACK["sfx"], "/predict", prompt=prompt, seconds_total=float(max(1, min(47, duration))), steps=60, cfg_scale=7))
        return [free.keep(r, free.path_of(res))]

    @staticmethod
    def upscale(r, model, image, scale):
        from gradio_client import handle_file
        from . import free
        res = free.call(free.SPACES["upscale"], "/process", input_image=handle_file(str(image)), prompt="", negative_prompt="", seed=42,
                        upscale_factor=float(max(1, min(4, scale))), controlnet_scale=0.6, controlnet_decay=1.0, condition_scale=6,
                        tile_width=112, tile_height=144, denoise_strength=0.35, num_inference_steps=18, solver="DDIM")
        after = res[1] if isinstance(res, (list, tuple)) and len(res) > 1 else res
        return [free.keep(r, free.path_of(after))]

    @staticmethod
    def bg_remove(r, model, image):
        from gradio_client import handle_file
        from . import free
        try:  # CPU first: no GPU quota, a few seconds per image
            return [free.bg_remove_cpu(Path(image), r.out.path(".png"))]
        except Exception:
            return [free.keep(r, free.path_of(free.call(free.SPACES["bg_remove"], "/png", f=handle_file(str(image)))), ".png")]

    @staticmethod
    def lipsync(r, model, video, audio):
        from gradio_client import handle_file
        from . import free
        res = free.call(free.SPACES["lipsync"], "/generate_lip_sync_video", input_video_path=handle_file(str(video)), input_audio_path=handle_file(str(audio)))
        return [free.keep(r, free.path_of(res), ".mp4")]

    @staticmethod
    def tts(r, model, text, voice, speed):
        from . import free
        if not free.LOCAL_TTS:
            raise ProviderError("Kokoro voice model is not installed on this server")
        kv = voice if voice in ("af_heart", "af_bella", "af_nicole", "af_sarah", "af_sky", "am_adam", "am_michael", "bf_emma", "bf_isabella", "bm_george", "bm_lewis") else \
            ["af_heart", "am_michael", "bf_emma", "bm_george", "af_bella", "am_adam"][sum(map(ord, voice or "x")) % 6]
        return [free.LOCAL_TTS(text, kv, speed)]

    video_upscale = None  # falls back to the local ffmpeg upscale


PROVIDERS = {"free": Free, "cloudflare": Cloudflare, "fal": Fal, "openai": OpenAI, "gemini": Gemini, "elevenlabs": ElevenLabs, "replicate": Replicate, "mock": Mock}
