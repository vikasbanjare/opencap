"""Pulse by aifloh backend: upload, probe, transcribe (faster-whisper), audio tools, SRT.

Run:  .venv/bin/uvicorn main:app --port 8787 --reload
Everything is local and free: ffmpeg + faster-whisper (CTranslate2) on CPU/Metal-less int8.
"""
from __future__ import annotations

import json, os, re, shutil, socket, subprocess, threading, time, uuid

# Some networks silently drop IPv6. Python then waits a full timeout on every IPv6 address before trying
# IPv4 (curl races both), so model and language-pack downloads hang for minutes. Try IPv4 first; IPv6 stays
# as a fallback. ponytail: process-wide patch; drop it if this ever runs where only IPv6 works.
_getaddrinfo = socket.getaddrinfo
socket.getaddrinfo = lambda *a, **k: sorted(_getaddrinfo(*a, **k), key=lambda r: r[0] != socket.AF_INET)
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("OPENCAP_DATA", ROOT / "data"))
DATA.mkdir(parents=True, exist_ok=True)
WHISPER_MODEL = os.environ.get("OPENCAP_WHISPER", "large-v3-turbo")  # cached locally already
WHISPER_COMPUTE = os.environ.get("OPENCAP_COMPUTE", "int8")

app = FastAPI(title="Pulse API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/media", StaticFiles(directory=DATA), name="media")  # range requests supported


def run(cmd: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def probe(path: Path) -> dict:
    out = run(["ffprobe", "-v", "error", "-show_entries",
               "stream=codec_type,width,height,r_frame_rate,duration,sample_rate,channels:format=duration",
               "-of", "json", str(path)]).stdout
    j = json.loads(out or "{}")
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in j.get("streams", []) if s.get("codec_type") == "audio"), {})
    fps = 30.0
    if v.get("r_frame_rate"):
        n, d = v["r_frame_rate"].split("/"); fps = float(n) / float(d or 1)
    return dict(width=int(v.get("width", 0)), height=int(v.get("height", 0)), fps=round(fps, 3),
                duration=float(j.get("format", {}).get("duration", 0) or 0),
                hasAudio=bool(a), sampleRate=int(a.get("sample_rate", 0) or 0))


def project_dir(pid: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{12}", pid):
        raise HTTPException(400, "bad project id")
    d = DATA / pid
    if not d.exists():
        raise HTTPException(404, "project not found")
    return d


_meta_lock = threading.Lock()   # background transcriptions and requests both update meta.json


def write_meta(d: Path, **kw):
    with _meta_lock:
        meta = json.loads((d / "meta.json").read_text()) if (d / "meta.json").exists() else {}
        meta.update(kw)
        (d / "meta.json").write_text(json.dumps(meta, indent=1))
        return meta


# ---------- projects ----------

@app.post("/api/projects")
async def create_project(file: UploadFile = File(...)):
    pid = uuid.uuid4().hex[:12]
    d = DATA / pid
    d.mkdir()
    ext = Path(file.filename or "upload.mp4").suffix.lower() or ".mp4"
    src = d / f"source{ext}"
    with src.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    info = probe(src)
    # browsers play H.264/AAC mp4 reliably; transcode anything else (mov/mkv/webm/hevc) once
    play = d / "play.mp4"
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(src)])
    vcodec = (r.stdout or "").strip()
    if ext == ".mp4" and vcodec == "h264":
        os.symlink(src.name, play)
    else:
        run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(play)], timeout=1800)
        info = probe(play)
    # 16 kHz mono wav for whisper + a waveform for the timeline
    run(["ffmpeg", "-v", "error", "-y", "-i", str(play), "-vn", "-ac", "1", "-ar", "16000", str(d / "audio16k.wav")])
    peaks = waveform_peaks(d / "audio16k.wav")
    (d / "peaks.json").write_text(json.dumps(peaks))
    meta = write_meta(d, id=pid, name=file.filename, created=time.time(), **info,
                      playUrl=f"/media/{pid}/play.mp4", peaksUrl=f"/media/{pid}/peaks.json",
                      transcribeStatus="running", transcribeError=None)  # set before replying so the editor knows to wait
    threading.Thread(target=transcribe_job, args=(pid,), daemon=True).start()
    return meta


def waveform_peaks(wav: Path, buckets_per_sec: int = 20) -> list[float]:
    """Max-abs per 50 ms bucket, 0..1. Raw PCM via ffmpeg so no numpy needed on the hot path."""
    import array
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(wav), "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                         capture_output=True).stdout
    a = array.array("h"); a.frombytes(raw[: len(raw) // 2 * 2])
    step = 16000 // buckets_per_sec
    peaks = []
    for i in range(0, len(a), step):
        chunk = a[i:i + step]
        peaks.append(round(max((abs(x) for x in chunk), default=0) / 32768, 3))
    return peaks


@app.get("/api/projects/{pid}")
def get_project(pid: str):
    d = project_dir(pid)
    meta = json.loads((d / "meta.json").read_text())
    if (d / "transcript.json").exists():
        meta["transcript"] = json.loads((d / "transcript.json").read_text())
    return meta


@app.get("/api/projects")
def list_projects():
    out = []
    for d in sorted(DATA.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if (d / "meta.json").exists():
            m = json.loads((d / "meta.json").read_text()); m.pop("transcript", None); out.append(m)
    return out


@app.patch("/api/projects/{pid}")
def rename_project(pid: str, payload: dict):
    name = str(payload.get("name", "")).strip()[:120]
    if not name:
        raise HTTPException(400, "name required")
    return write_meta(project_dir(pid), name=name)


@app.delete("/api/projects/{pid}")
def delete_project(pid: str):
    shutil.rmtree(project_dir(pid))
    return {"ok": True}


# ---------- transcription ----------

_model = None
_model_lock = threading.Lock()


def get_model():
    global _model
    with _model_lock:
        if _model is None:
            from faster_whisper import WhisperModel
            # Cached copy first, with no network: a hung update check to huggingface.co used to stall
            # every transcription silently. Download only when nothing is cached yet.
            try:
                _model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type=WHISPER_COMPUTE, local_files_only=True)
            except Exception:
                _model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type=WHISPER_COMPUTE)
        return _model


def transcribe_wav(wav: Path, language: Optional[str] = None) -> dict:
    """Word-level transcript of a 16 kHz mono wav."""
    model = get_model()
    # decode the wav ourselves: avoids faster-whisper's PyAV path, which breaks on newer av releases
    import wave, numpy as np
    with wave.open(str(wav), "rb") as wf:
        pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    segments, info = model.transcribe(pcm, word_timestamps=True, vad_filter=True, language=language, beam_size=5,
                                      vad_parameters=dict(min_silence_duration_ms=300))
    words, segs = [], []
    for s in segments:
        segs.append(dict(start=round(s.start, 3), end=round(s.end, 3), text=s.text.strip()))
        for w in (s.words or []):
            t = w.word.strip()
            if t:
                words.append(dict(text=t, start=round(w.start, 3), end=round(w.end, 3), p=round(w.probability, 3)))
    return dict(language=info.language, languageProb=round(info.language_probability, 3), words=words, segments=segs, model=WHISPER_MODEL)


def transcribe_job(pid: str, language: Optional[str] = None):
    d = DATA / pid
    write_meta(d, transcribeStatus="running", transcribeError=None)
    try:
        tr = transcribe_wav(d / "audio16k.wav", language)
        (d / "transcript.json").write_text(json.dumps(tr, ensure_ascii=False))
        write_meta(d, transcribeStatus="done", language=tr["language"])
    except Exception as e:  # keep the error visible in the UI
        write_meta(d, transcribeStatus="error", transcribeError=str(e))


@app.on_event("startup")
def warm_up():
    # Load Whisper once at boot (about a minute on first use) so the first upload is not stuck
    # at "running" for that long, and re-queue jobs a restart left behind. ponytail: polls on
    # boot only; a real queue if jobs ever outlive the process on purpose.
    def go():
        for d in DATA.iterdir():
            m = d / "meta.json"
            if m.is_file() and json.loads(m.read_text()).get("transcribeStatus") == "running":
                threading.Thread(target=transcribe_job, args=(d.name,), daemon=True).start()
        get_model()
    threading.Thread(target=go, daemon=True).start()


@app.post("/api/projects/{pid}/transcribe")
def retranscribe(pid: str, language: Optional[str] = Form(None)):
    write_meta(project_dir(pid), transcribeStatus="running", transcribeError=None)
    threading.Thread(target=transcribe_job, args=(pid, language or None), daemon=True).start()
    return {"ok": True}


@app.get("/api/projects/{pid}/status")
def status(pid: str):
    d = project_dir(pid)
    m = json.loads((d / "meta.json").read_text())
    return {"transcribeStatus": m.get("transcribeStatus"), "transcribeError": m.get("transcribeError")}


# ---------- subtitles ----------

def fmt_srt(t: float) -> str:
    ms = int(round(t * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


@app.post("/api/subtitles/srt", response_class=PlainTextResponse)
async def make_srt(payload: dict):
    """payload: {cards:[{start,end,text}], format:'srt'|'vtt'}"""
    cards = payload.get("cards", []); vtt = payload.get("format") == "vtt"
    lines = ["WEBVTT", ""] if vtt else []
    for i, c in enumerate(cards, 1):
        a, b = fmt_srt(c["start"]), fmt_srt(c["end"])
        if vtt:
            a, b = a.replace(",", "."), b.replace(",", ".")
        lines += ([] if vtt else [str(i)]) + [f"{a} --> {b}", c["text"], ""]
    return "\n".join(lines)


# ---------- audio tools (ffmpeg only, all free) ----------

@app.post("/api/projects/{pid}/audio/{tool}")
def audio_tool(pid: str, tool: str):
    """tool: denoise | normalize | enhance. Writes <tool>.m4a and returns its URL."""
    d = project_dir(pid)
    filters = {
        "denoise": "afftdn=nf=-25:tn=1",
        "normalize": "loudnorm=I=-16:TP=-1.5:LRA=11",
        "enhance": "highpass=f=80,afftdn=nf=-22,acompressor=threshold=-18dB:ratio=3:attack=5:release=80,loudnorm=I=-16:TP=-1.5",
    }
    if tool not in filters:
        raise HTTPException(400, "unknown tool")
    out = d / f"{tool}.m4a"
    r = run(["ffmpeg", "-v", "error", "-y", "-i", str(d / "play.mp4"), "-vn", "-af", filters[tool], "-c:a", "aac", "-b:a", "192k", str(out)], timeout=1800)
    if r.returncode:
        raise HTTPException(500, r.stderr[-800:])
    return {"url": f"/media/{pid}/{tool}.m4a"}


# ---------- server-side export (fallback when WebCodecs is unavailable) ----------

@app.post("/api/projects/{pid}/export")
def export_server(pid: str, payload: dict):
    """payload: {cuts:[{start,end}], audioUrl?: str}. Applies cuts with ffmpeg; captions are burned client-side
    in the normal path, so this fallback only cuts and remuxes. ponytail: no caption burn here, add PIL frames if needed."""
    d = project_dir(pid)
    meta = json.loads((d / "meta.json").read_text())
    cuts = sorted(payload.get("cuts", []), key=lambda c: c["start"])
    keep, t = [], 0.0
    for c in cuts:
        if c["start"] > t:
            keep.append((t, c["start"]))
        t = max(t, c["end"])
    if t < meta["duration"]:
        keep.append((t, meta["duration"]))
    parts = []
    for i, (a, b) in enumerate(keep):
        parts.append(f"[0:v]trim=start={a}:end={b},setpts=PTS-STARTPTS[v{i}];[0:a]atrim=start={a}:end={b},asetpts=PTS-STARTPTS[a{i}]")
    concat = "".join(f"[v{i}][a{i}]" for i in range(len(keep))) + f"concat=n={len(keep)}:v=1:a=1[v][a]"
    out = d / "export.mp4"
    r = run(["ffmpeg", "-v", "error", "-y", "-i", str(d / "play.mp4"), "-filter_complex", ";".join(parts + [concat]),
             "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", "-b:a", "192k",
             "-movflags", "+faststart", str(out)], timeout=3600)
    if r.returncode:
        raise HTTPException(500, r.stderr[-800:])
    return {"url": f"/media/{pid}/export.mp4"}


# ---------- project state (edits) ----------

@app.put("/api/projects/{pid}/state")
async def put_state(pid: str, payload: dict):
    d = project_dir(pid)
    (d / "state.json").write_text(json.dumps(payload, ensure_ascii=False))
    return {"ok": True}


@app.get("/api/projects/{pid}/state")
def get_state(pid: str):
    d = project_dir(pid)
    return json.loads((d / "state.json").read_text()) if (d / "state.json").exists() else None


# ---------- assets: B-roll clips, images, music ----------

@app.post("/api/projects/{pid}/assets")
async def upload_asset(pid: str, file: UploadFile = File(...)):
    d = project_dir(pid)
    (d / "assets").mkdir(exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", file.filename or "asset")
    name = f"{uuid.uuid4().hex[:6]}-{safe}"
    dst = d / "assets" / name
    with dst.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    kind = "image" if dst.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".gif") else "audio" if dst.suffix.lower() in (".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac") else "video"
    info = {}
    if kind == "video":
        # browser-safe proxy (H.264/AAC mp4, max 1280 tall) so preview and export can seek it
        proxy = dst.with_suffix(".proxy.mp4")
        run(["ffmpeg", "-v", "error", "-y", "-i", str(dst), "-vf", "scale='min(1280,iw)':-2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(proxy)], timeout=1800)
        info = probe(proxy); name = proxy.name
    elif kind == "audio":
        info = probe(dst)
    return {"url": f"/media/{pid}/assets/{name}", "kind": kind, "name": safe, **info}


# ---------- text to speech (Kokoro-82M, ONNX, offline) ----------

_kokoro = None
KOKORO_VOICES = ["af_heart", "af_bella", "af_nicole", "af_sarah", "af_sky", "am_adam", "am_michael", "bf_emma", "bf_isabella", "bm_george", "bm_lewis"]


def get_kokoro():
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro
        m = ROOT / "models"
        if not (m / "kokoro-v1.0.onnx").exists():
            raise HTTPException(503, "Kokoro model missing: download kokoro-v1.0.onnx and voices-v1.0.bin into server/models/")
        _kokoro = Kokoro(str(m / "kokoro-v1.0.onnx"), str(m / "voices-v1.0.bin"))
    return _kokoro


@app.get("/api/tts/voices")
def tts_voices():
    return {"voices": KOKORO_VOICES, "ready": (ROOT / "models" / "kokoro-v1.0.onnx").exists(), "clone": clone_cli() is not None}


@app.post("/api/tts")
def tts(payload: dict):
    """payload: {text, voice='af_heart', speed=1.0, lang='en-us'} -> wav url (cached by content hash)."""
    import hashlib, wave, numpy as np
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "empty text")
    voice = payload.get("voice", "af_heart"); speed = float(payload.get("speed", 1.0)); lang = payload.get("lang", "en-us")
    key = hashlib.sha1(f"{text}|{voice}|{speed}|{lang}".encode()).hexdigest()[:16]
    out_dir = DATA / "_tts"; out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{key}.wav"
    if not out.exists():
        samples, sr = get_kokoro().create(text, voice=voice, speed=speed, lang=lang)
        pcm = (np.clip(samples, -1, 1) * 32767).astype(np.int16)
        with wave.open(str(out), "wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr); wf.writeframes(pcm.tobytes())
    info = probe(out)
    return {"url": f"/media/_tts/{out.name}", "duration": info["duration"]}


# ---------- voice cloning (F5-TTS, optional plugin) ----------
# Runs the f5-tts_infer-cli from a separate venv so the API venv stays torch-free.
# Install: uv venv server/.venv-clone && uv pip install --python server/.venv-clone/bin/python f5-tts
# (or symlink server/.venv-clone to any venv that already has torch + f5-tts). First run downloads ~1.4 GB.

def clone_cli() -> Path | None:
    for c in [os.environ.get("OPENCAP_CLONE_CLI"), ROOT / ".venv-clone" / "bin" / "f5-tts_infer-cli", shutil.which("f5-tts_infer-cli")]:
        if c and Path(c).exists():
            return Path(c)
    return None


@app.post("/api/clone")
def clone(payload: dict):
    """payload: {projectId, text, refStart, refEnd, speed=1.0} -> wav url in the cloned voice.
    Reference = project audio16k.wav cut to [refStart, refEnd] (keep it 3..15 s of clean speech);
    its transcript words are passed as ref_text so F5 does not need its own ASR model."""
    import hashlib
    cli = clone_cli()
    if not cli:
        raise HTTPException(503, "voice cloning not installed: see README 'Optional: voice cloning'")
    d = project_dir(payload.get("projectId", ""))
    text = (payload.get("text") or "").strip()
    a, b = float(payload.get("refStart", 0)), float(payload.get("refEnd", 10))
    speed = float(payload.get("speed", 1.0))
    if not text:
        raise HTTPException(400, "empty text")
    if not (0 <= a < b):
        raise HTTPException(400, "refEnd must be after refStart")
    b = min(b, a + 15)  # ponytail: F5 degrades past ~15 s of reference; clamp instead of erroring
    key = hashlib.sha1(f"{d.name}|{a}|{b}|{text}|{speed}".encode()).hexdigest()[:16]
    out_dir = DATA / "_tts"; out_dir.mkdir(exist_ok=True)
    out = out_dir / f"clone-{key}.wav"
    if not out.exists():
        ref = out_dir / f"ref-{key}.wav"
        run(["ffmpeg", "-v", "error", "-y", "-i", str(d / "audio16k.wav"), "-ss", str(a), "-t", str(b - a), "-ar", "24000", str(ref)])
        words = []
        if (d / "transcript.json").exists():
            words = [w["text"] for w in json.loads((d / "transcript.json").read_text()).get("words", []) if w["start"] >= a and w["end"] <= b]
        r = run([str(cli), "-m", "F5TTS_v1_Base", "-r", str(ref), "-s", " ".join(words), "-t", text, "--speed", str(speed),
                 "--remove_silence", "-o", str(out_dir), "-w", out.name], timeout=1800)
        ref.unlink(missing_ok=True)
        if r.returncode != 0 or not out.exists():
            raise HTTPException(500, "clone failed: " + (r.stderr or r.stdout)[-800:])
    info = probe(out)
    return {"url": f"/media/_tts/{out.name}", "duration": info["duration"]}


# ---------- translation (Argos packs on CTranslate2, offline after first download) ----------

@app.get("/api/translate/languages")
def translate_languages():
    import translate as T
    try:
        avail = T.available_targets("en")
        return {"ready": bool(avail), "available": avail, "installed": sorted(p.name.split("_") for p in (ROOT / "models" / "argos").glob("*_*"))}
    except Exception as e:
        return {"ready": False, "error": str(e), "available": [], "installed": []}


@app.post("/api/translate")
def translate(payload: dict):
    """payload: {texts:[str], source:'en', target:'es'}. First use of a pair downloads its pack (~100 MB)."""
    import translate as T
    try:
        return {"texts": T.translate_texts(ROOT / "models", payload.get("texts", []), payload.get("source", "en"), payload["target"])}
    except FileNotFoundError as e:
        raise HTTPException(400, str(e))


@app.post("/api/projects/{pid}/renders")
async def save_render(pid: str, file: UploadFile = File(...)):
    """The browser renders the MP4 itself; this keeps a copy in the project so it can be re-downloaded or shared."""
    d = project_dir(pid)
    (d / "renders").mkdir(exist_ok=True)
    name = f"render-{time.strftime('%Y%m%d-%H%M%S')}.mp4"
    with (d / "renders" / name).open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"url": f"/media/{pid}/renders/{name}", "name": name, "info": probe(d / "renders" / name)}


@app.get("/api/projects/{pid}/renders")
def list_renders(pid: str):
    d = project_dir(pid) / "renders"
    if not d.exists():
        return []
    return [{"url": f"/media/{pid}/renders/{p.name}", "name": p.name, "size": p.stat().st_size} for p in sorted(d.iterdir(), reverse=True)]


@app.get("/api/health")
def health():
    return {"ok": True, "whisper": WHISPER_MODEL, "ffmpeg": run(["ffmpeg", "-version"]).stdout.split("\n")[0]}


# ---------- multiple clips + transitions ----------
# A project is a list of segments, each a [in, out] range of one clip, optionally entered through a transition.
# Every change re-renders play.mp4 (and its 16 kHz audio + waveform), so preview and export keep working on one file.
# ponytail: full re-render per edit; fine for shorts, switch to per-segment proxies + concat if long videos get slow.

XFADE = {"fade": "fade", "black": "fadeblack", "white": "fadewhite", "dissolve": "dissolve", "slide": "slideleft",
         "slideup": "slideup", "wipe": "wipeleft", "circle": "circleopen", "zoom": "zoomin", "blur": "hblur", "pixel": "pixelize"}


def source_file(d: Path) -> Path:
    return next(p for p in sorted(d.glob("source.*")))


def clips_of(d: Path, meta: dict) -> list[dict]:
    """The clip list, starting with the original upload."""
    clips = meta.get("clips")
    if clips:
        return clips
    info = probe(source_file(d))
    return [dict(id="source", file=source_file(d).name, name=meta.get("name"), duration=info["duration"],
                 hasAudio=info["hasAudio"], transcribeStatus="done")]


def clip_transcribe_job(pid: str, cid: str):
    d = DATA / pid
    def mark(**kw):
        with _meta_lock:
            meta = json.loads((d / "meta.json").read_text())
            for c in meta.get("clips", []):
                if c["id"] == cid:
                    c.update(kw)
            (d / "meta.json").write_text(json.dumps(meta, indent=1))
    try:
        tr = transcribe_wav(d / f"clip_{cid}.wav")
        (d / f"clip_{cid}.transcript.json").write_text(json.dumps(tr, ensure_ascii=False))
        mark(transcribeStatus="done")
    except Exception as e:
        mark(transcribeStatus="error", transcribeError=str(e))


@app.post("/api/projects/{pid}/clips")
async def add_clip(pid: str, file: UploadFile = File(...)):
    d = project_dir(pid)
    cid = uuid.uuid4().hex[:8]
    ext = Path(file.filename or "clip.mp4").suffix.lower() or ".mp4"
    dst = d / f"clip_{cid}{ext}"
    with dst.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    info = probe(dst)
    if not info["duration"]:
        dst.unlink(missing_ok=True)
        raise HTTPException(400, "could not read that video")
    run(["ffmpeg", "-v", "error", "-y", "-i", str(dst), "-vn", "-ac", "1", "-ar", "16000", str(d / f"clip_{cid}.wav")])
    meta = json.loads((d / "meta.json").read_text())
    clip = dict(id=cid, file=dst.name, name=file.filename, duration=info["duration"], hasAudio=info["hasAudio"],
                transcribeStatus="running" if info["hasAudio"] else "done")
    write_meta(d, clips=[*clips_of(d, meta), clip])
    if info["hasAudio"]:
        threading.Thread(target=clip_transcribe_job, args=(pid, cid), daemon=True).start()
    else:
        (d / f"clip_{cid}.transcript.json").write_text(json.dumps(dict(language=None, words=[], segments=[])))
    return clip


@app.get("/api/projects/{pid}/clips/{cid}/transcript")
def clip_transcript(pid: str, cid: str):
    d = project_dir(pid)
    if cid == "source":
        return json.loads((d / "transcript.json").read_text())
    f = d / f"clip_{re.sub(r'[^a-f0-9]', '', cid)}.transcript.json"
    if not f.exists():
        raise HTTPException(404, "not transcribed yet")
    return json.loads(f.read_text())


@app.post("/api/projects/{pid}/assemble")
def assemble(pid: str, payload: dict):
    d = project_dir(pid)
    meta = json.loads((d / "meta.json").read_text())
    clips = {c["id"]: c for c in clips_of(d, meta)}
    segs = payload.get("segments") or []
    if not segs or any(s.get("clip") not in clips for s in segs):
        raise HTTPException(400, "unknown clip in segments")
    W, H, FPS = meta["width"], meta["height"], meta.get("fps") or 30
    W, H = W - W % 2, H - H % 2
    args, fg, out = ["ffmpeg", "-v", "error", "-y"], [], []
    for k, s in enumerate(segs):
        c = clips[s["clip"]]
        s["in"] = max(0.0, float(s["in"])); s["out"] = min(float(c["duration"]), float(s["out"]))
        if s["out"] - s["in"] < 0.1:
            raise HTTPException(400, "segment too short")
        args += ["-ss", f"{s['in']:.3f}", "-t", f"{s['out'] - s['in']:.3f}", "-i", str(d / c["file"])]
        L = s["out"] - s["in"]
        fg.append(f"[{k}:v]scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,"
                  f"setsar=1,fps={FPS},format=yuv420p,setpts=PTS-STARTPTS,trim=duration={L:.3f}[v{k}]")
        fg.append(f"[{k}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,asetpts=PTS-STARTPTS,apad,atrim=duration={L:.3f}[a{k}]"
                  if c.get("hasAudio") else f"anullsrc=r=48000:cl=stereo,atrim=duration={L:.3f}[a{k}]")
    cv, ca, total, starts = "v0", "a0", segs[0]["out"] - segs[0]["in"], [0.0]
    for k in range(1, len(segs)):
        s, L = segs[k], segs[k]["out"] - segs[k]["in"]
        t = XFADE.get(s.get("transition") or "none")
        # ffmpeg fails when concat and xfade are mixed in one graph, so a plain cut is a one-frame crossfade
        dur = min(float(s.get("tdur") or 0.5), L / 2, total / 2) if t else 1 / FPS
        fg.append(f"[{cv}][v{k}]xfade=transition={t or 'fade'}:duration={dur:.3f}:offset={total - dur:.3f}[cv{k}]")
        fg.append(f"[{ca}][a{k}]acrossfade=d={dur:.3f}[ca{k}]")
        starts.append(total - dur); total += L - dur
        cv, ca = f"cv{k}", f"ca{k}"
    tmp = d / "play.build.mp4"
    r = run(args + ["-filter_complex", ";".join(fg), "-map", f"[{cv}]", "-map", f"[{ca}]", "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(tmp)], timeout=1800)
    if r.returncode != 0 or not tmp.exists():
        raise HTTPException(500, f"render failed: {(r.stderr or '')[-400:]}")
    os.replace(tmp, d / "play.mp4")   # replaces a symlink itself, never the original upload it pointed to
    run(["ffmpeg", "-v", "error", "-y", "-i", str(d / "play.mp4"), "-vn", "-ac", "1", "-ar", "16000", str(d / "audio16k.wav")])
    (d / "peaks.json").write_text(json.dumps(waveform_peaks(d / "audio16k.wav")))
    v = int(time.time() * 1000)
    out_segs = [dict(id=s["id"], clip=s["clip"], **{"in": round(s["in"], 3), "out": round(s["out"], 3)}, transition=s.get("transition") or "none",
                     tdur=float(s.get("tdur") or 0.5), start=round(starts[k], 3)) for k, s in enumerate(segs)]
    return write_meta(d, segments=out_segs, clips=list(clips.values()), duration=round(probe(d / "play.mp4")["duration"], 3),
                      playUrl=f"/media/{pid}/play.mp4?v={v}", peaksUrl=f"/media/{pid}/peaks.json?v={v}")


# ---------- Studio: the Spark Station-style tool suite (server/studio) ----------

def _studio_tts(text: str, voice: str, speed: float) -> Path:
    r = tts({"text": text, "voice": voice, "speed": speed})
    return DATA / r["url"].removeprefix("/media/")


from studio.api import make_router  # noqa: E402

app.include_router(make_router(DATA, transcribe=transcribe_wav, local_tts=_studio_tts))


# Built frontend (Docker / Hugging Face Space). Mounted last so every /api route above wins.
DIST = ROOT.parent / "dist"
if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="web")
