"""The Free provider: every capability at no cost, for the starting phase.

Media runs on public Hugging Face ZeroGPU Spaces through gradio_client (they spend Hugging Face's free daily GPU
quota, the Space owner's when HF_TOKEN is set as a Space secret); text and image understanding run on Qwen3-VL-4B
on this Space's own ZeroGPU (or CPU when there is no GPU); voice is the local Kokoro model. All model licences
below allow commercial use (LTX-Video: free under $10M annual revenue; Stable Audio Open: free under $1M).

  image      evalstate/flux1_schnell (10 s GPU), then black-forest-labs/FLUX.1-schnell   Apache-2.0
  edit       mcp-tools/FLUX.1-Kontext-Dev (about 30 s GPU), then Qwen/Qwen-Image-Edit
             (also inpaint, try-on, face swap via panels). Kontext weights are non-commercial but BFL lets you use outputs commercially.
  video      zerogpu-aoti/wan2-2-fp8da-aoti-faster (Wan 2.2 I2V, about 20-30 s GPU; text-to-video makes a FLUX first frame),
             then Lightricks/ltx-video-distilled                                          Apache-2.0 / LTXV open weights
  music      ACE-Step/ACE-Step                         Apache-2.0
  sfx        declare-lab/TangoFlux (15 s GPU), then artificialguybr/Stable-Audio-Open-Zero   Stability community licence
  upscale    finegrain/finegrain-image-enhancer        refiners (MIT)
  bg_remove  not-lain/background-removal (BiRefNet)    MIT
  lipsync    fffiloni/LatentSync                       Apache-2.0
  llm/vision Qwen/Qwen3-VL-4B-Instruct (in-process)    Apache-2.0
  tts        Kokoro-82M (in-process)                   Apache-2.0

Spaces change; each one is a single entry in SPACES and one small method, so swapping a dead Space is a one-line fix.
"""
from __future__ import annotations

import os, shutil, threading
from pathlib import Path

# The first Space of each capability asks ZeroGPU for the least GPU time (a free account gets about 3 minutes a day and each
# call reserves its declared duration up front), the second is the fallback.
SPACES = {"image": "evalstate/flux1_schnell", "edit": "mcp-tools/FLUX.1-Kontext-Dev", "video": "zerogpu-aoti/wan2-2-fp8da-aoti-faster",
          "music": "ACE-Step/ACE-Step", "sfx": "declare-lab/TangoFlux", "upscale": "finegrain/finegrain-image-enhancer",
          "bg_remove": "not-lain/background-removal", "lipsync": "fffiloni/LatentSync"}
FALLBACK = {"image": "black-forest-labs/FLUX.1-schnell", "edit": "Qwen/Qwen-Image-Edit", "video": "Lightricks/ltx-video-distilled",
            "sfx": "artificialguybr/Stable-Audio-Open-Zero"}
LLM_MODEL = os.environ.get("OPENCAP_FREE_LLM", "Qwen/Qwen3-VL-4B-Instruct")
LOCAL_TTS = None  # set by main.py: (text, voice, speed) -> Path (Kokoro)

_clients: dict = {}
_lock = threading.Lock()


def enabled() -> bool:
    return os.environ.get("OPENCAP_FREE", "1") != "0"


def client(space: str):
    from gradio_client import Client
    with _lock:
        if space not in _clients:
            import inspect
            tok = os.environ.get("HF_TOKEN") or None
            arg = "token" if "token" in inspect.signature(Client.__init__).parameters else "hf_token"  # renamed in gradio_client 2.x
            _clients[space] = Client(space, **{arg: tok}, verbose=False)
        return _clients[space]


def call(space: str, api: str, **kw):
    from .providers import ProviderError
    try:
        return client(space).predict(api_name=api, **kw)
    except Exception as e:  # quota, a sleeping or changed Space: say so plainly
        msg = str(e)
        if "quota" in msg.lower() or "GPU" in msg:
            hint = ("try again after it refills, upgrade the Hugging Face account to PRO for more daily GPU time, or add a provider key"
                    if os.environ.get("HF_TOKEN") else "try later, add HF_TOKEN as a Space secret, or add a provider key")
            msg = f"the free GPU quota is used up for now (it refills daily); {hint} [{msg[:160]}]"
        raise ProviderError(f"free {space}: {msg[:300]}")


def first_ok(*attempts):
    """Run (fn, args) pairs in turn; return the first result, raise the first error if all fail."""
    first = None
    for fn in attempts:
        try:
            return fn()
        except Exception as e:
            first = first or e
    raise first


def path_of(res) -> str:
    """gradio returns a path, a {path|video|image} dict, or a tuple with one of those first."""
    if isinstance(res, (list, tuple)):
        for x in res:
            p = path_of(x)
            if p: return p
        return ""
    if isinstance(res, dict):
        for k in ("path", "video", "image", "value", "name"):
            if res.get(k):
                return path_of(res[k])
        return ""
    return res if isinstance(res, str) and os.path.exists(res) else ""


def keep(r, src: str, ext: str | None = None) -> Path:
    from .providers import ProviderError
    if not src:
        raise ProviderError("the free Space returned no file")
    dst = r.out.path(ext or Path(src).suffix or ".bin"); shutil.copy(src, dst); return dst


# ---------- background removal on CPU (BiRefNet lite, MIT): no GPU quota at all ----------

_bg = {"sess": None}


def bg_remove_cpu(src: Path, dst: Path) -> Path:
    import numpy as np
    from PIL import Image
    if _bg["sess"] is None:
        import onnxruntime as ort
        from huggingface_hub import hf_hub_download
        _bg["sess"] = ort.InferenceSession(hf_hub_download("onnx-community/BiRefNet_lite-ONNX", "onnx/model.onnx"), providers=["CPUExecutionProvider"])
    im = Image.open(src).convert("RGB")
    x = (np.asarray(im.resize((1024, 1024)), dtype=np.float32) / 255 - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
    y = _bg["sess"].run(None, {"input_image": x.transpose(2, 0, 1)[None].astype(np.float32)})[0][0, 0]
    y = 1 / (1 + np.exp(-y)) if y.min() < 0 or y.max() > 1 else y  # logits on some exports
    alpha = Image.fromarray((y * 255).clip(0, 255).astype("uint8")).resize(im.size)
    out = im.convert("RGBA"); out.putalpha(alpha); out.save(dst); return dst


# ---------- in-process LLM (Qwen3-VL-4B on ZeroGPU, else CPU) ----------

_llm = {"model": None, "proc": None, "device": "cpu", "error": None}


def load_llm():
    """Call once at startup (before ZeroGPU starts) so the weights can be placed on the GPU."""
    if not enabled() or os.environ.get("OPENCAP_LOCAL_LLM", "1") == "0" or _llm["model"] is not None:
        return
    try:
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor
        proc = AutoProcessor.from_pretrained(LLM_MODEL)
        model = AutoModelForImageTextToText.from_pretrained(LLM_MODEL, dtype=torch.bfloat16)
        try:
            import spaces  # noqa: F401  ZeroGPU: .to("cuda") at startup is deferred until a GPU call
            model.to("cuda"); _llm["device"] = "cuda"
        except ImportError:
            pass
        _llm.update(model=model, proc=proc)
    except Exception as e:
        _llm["error"] = f"{type(e).__name__}: {e}"


def _gpu_seconds(messages: list, max_new_tokens: int) -> int:
    """Reserve only what the answer needs (about 40 tokens/s on a 4B model) so short calls cost little free quota."""
    images = sum(1 for m in messages for c in m["content"] if c.get("type") == "image")
    return int(min(90, 8 + max_new_tokens / 40 + 3 * images))


def _generate(messages: list, max_new_tokens: int) -> str:
    model, proc = _llm["model"], _llm["proc"]
    enc = proc.apply_chat_template(messages, add_generation_prompt=True, tokenize=True, return_dict=True, return_tensors="pt").to(model.device)
    out = model.generate(**enc, max_new_tokens=max_new_tokens, do_sample=False)
    return proc.batch_decode(out[:, enc["input_ids"].shape[1]:], skip_special_tokens=True)[0]


try:  # on a ZeroGPU Space the generate call borrows a GPU for its duration
    import spaces
    _generate = spaces.GPU(duration=_gpu_seconds)(_generate)
except Exception:
    pass


def chat(prompt: str, system: str = "", images: list[Path] | None = None, max_new_tokens: int = 1200) -> str:
    from .providers import ProviderError
    if _llm["model"] is None:
        load_llm()
    if _llm["model"] is None:
        raise ProviderError(f"free text model unavailable: {_llm['error'] or 'disabled'}")
    from PIL import Image
    content = [{"type": "image", "image": Image.open(p).convert("RGB")} for p in (images or [])[:6]] + [{"type": "text", "text": prompt}]
    msgs = ([{"role": "system", "content": [{"type": "text", "text": system}]}] if system else []) + [{"role": "user", "content": content}]
    return _generate(msgs, max_new_tokens)


def status() -> dict:
    return {"enabled": enabled(), "llm": LLM_MODEL, "llm_loaded": _llm["model"] is not None, "llm_device": _llm["device"],
            "llm_error": _llm["error"], "hf_token": bool(os.environ.get("HF_TOKEN")), "spaces": SPACES, "fallback": FALLBACK, "kokoro": LOCAL_TTS is not None}
