"""Hugging Face Space entry (Gradio SDK, free ZeroGPU tier). Pulse runs on CPU: one uvicorn on 7860 serves the API and the built web app."""
import os, sys, threading, urllib.request
from pathlib import Path

os.environ.setdefault("OPENCAP_WHISPER", "small")  # ponytail: small keeps CPU transcription quick; set the Space variable for large-v3-turbo
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "server"))

try:  # ZeroGPU wants at least one GPU function before it will start a Space
    import spaces

    @spaces.GPU
    def _gpu_probe():
        return "ok"

    # Studio's free text/vision model registers its GPU function and places its weights before ZeroGPU starts
    from studio import free as _free
    _free.load_llm()

    if hasattr(spaces, "zero") and hasattr(spaces.zero, "startup"):
        spaces.zero.startup()  # normally run by gr.Blocks.launch, which we skip; reports the GPU function to ZeroGPU
except ImportError:
    pass


def fetch_kokoro():  # TTS model (~330 MB) is not in the repo; fetched in the background so the site comes up at once
    models = ROOT / "server" / "models"
    models.mkdir(exist_ok=True)
    for name in ["voices-v1.0.bin", "kokoro-v1.0.onnx"]:  # onnx last: its presence is the "ready" flag
        if not (models / name).exists():
            tmp = models / (name + ".part")
            urllib.request.urlretrieve(f"https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/{name}", tmp)
            tmp.rename(models / name)


threading.Thread(target=fetch_kokoro, daemon=True).start()

import uvicorn
from main import app

uvicorn.run(app, host="0.0.0.0", port=7860)
