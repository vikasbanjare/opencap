# Pulse by aifloh

<img src="public/favicon.svg" width="56" alt="Pulse logo">


A free, local, open-source take on Captions.ai / Kapwing / VEED: upload or record a video, get word-level captions from Whisper, style them with animated presets reverse-engineered from Captions.ai, edit the video by editing the text, add B-roll, music, emoji and text, and export an MP4 **rendered in your own browser**. No accounts, no API keys, nothing leaves your machine.

## What it does

| Area | Features |
|---|---|
| Captions | faster-whisper (large-v3-turbo, CPU) word timestamps · 20 animated presets (word-fill karaoke, blur-pop, append, line-stack, pills, bars, moving highlight box, hollow inactive, keyword colour/size/glow) · full style editor · SRT/VTT export · offline translation to 30+ languages |
| Text-based editing | delete words to cut video · one-click filler removal (um, uh, like…) · silence cutter · **Auto edit** (fillers + silences + punch-ins) · manual cuts on the timeline |
| Visuals | auto zoom punch-ins on keyword cards · reframe to 9:16 / 1:1 / 4:5 / 16:9 with crop position · text, emoji, image stickers with pop-in · **B-roll clips** full-frame or picture-in-picture |
| Audio | denoise / enhance speech / loudness normalise (ffmpeg) · music bed with automatic ducking under speech · **text to speech** (Kokoro-82M, offline) as voiceover or extra track |
| Capture | camera or screen recording in the browser → new project |
| Export | H.264 + AAC MP4 via WebCodecs (Chrome/Edge), 720p/1080p, 24/30/60 fps · copies kept in the project · server-side cut-only fallback |

See `docs/feature-map.md` for the competitor feature matrix and what is in / out of scope.

## Run it

Requirements: macOS/Linux, Python 3.11+, [uv](https://docs.astral.sh/uv/), ffmpeg, bun (or npm), Chrome/Edge for export.

```bash
# backend (first run downloads the Whisper model, ~1.6 GB, into ~/.cache/huggingface)
cd server && uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt kokoro-onnx soundfile sentencepiece
mkdir -p models && cd models && \
  curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx && \
  curl -LO https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin && cd ..
.venv/bin/uvicorn main:app --port 8787 --reload

# frontend
bun install && bun run dev     # http://localhost:5174 (proxies /api and /media to 8787)
```

Environment: `OPENCAP_WHISPER` (model name, default `large-v3-turbo`; use `small` on weak machines), `OPENCAP_COMPUTE` (`int8` default), `OPENCAP_DATA` (project storage, default `server/data`).

## How it is built

- `src/captions/presets.ts` — style presets. Each is the six-field decomposition found in the research: font, placement, reveal, entrance, emphasis, box. Defaults are the measured medians across 45 Captions.ai 9:16 previews (band centre 67 %, 2-word chunks, 125 ms blur-pop, inactive words 40 %).
- `src/captions/engine.ts` — deterministic canvas renderer: same (time, cards, style) gives the same pixels in preview and export.
- `src/lib/compositor.ts` — one frame: cover crop + zoom + B-roll + captions + overlays.
- `src/lib/export.ts` — seeks the source per frame, draws, encodes with `VideoEncoder`/`AudioEncoder`, muxes with mp4-muxer; splices audio around cuts and mixes the music bed with ducking.
- `server/main.py` — FastAPI: upload/probe/transcode, Whisper job, audio tools, assets, TTS, translation, renders, per-project state.
- `server/translate.py` — runs Argos language packs directly on CTranslate2 + SentencePiece (no torch).

## Optional: voice cloning

`POST /api/clone` turns a few seconds of your own speech into an AI twin with [F5-TTS](https://github.com/SWivid/F5-TTS) (MIT, runs on Apple MPS / CUDA / CPU). It is a plugin because it needs torch plus a ~1.4 GB model, so the API venv stays small:

```bash
# any venv with f5-tts works; put it (or a symlink to one that already has torch) at server/.venv-clone
cd server && uv venv .venv-clone && uv pip install --python .venv-clone/bin/python f5-tts
# or: export OPENCAP_CLONE_CLI=/path/to/bin/f5-tts_infer-cli
```

Restart the API; the Audio panel's voice list gains **Clone my voice (F5-TTS)**. Pick 3–15 s of clean speech from the clip as the reference (its transcript words are passed as `ref_text`, so no extra ASR model is needed), type the text, Generate. The first run downloads `F5TTS_v1_Base` + the Vocos vocoder into `~/.cache/huggingface`. Request: `{projectId, text, refStart, refEnd, speed}` → `{url, duration}`, cached by content hash like `/api/tts`.

## Limits

- Export uses WebCodecs: Chrome and Edge today; Safari 17+ for video only. Firefox falls back to the server cut.
- Whisper runs on CPU with int8; a 60 s clip takes ~15–25 s on an M-series Mac.
- Translation redistributes translated words evenly inside each caption card (word-level alignment across languages is not attempted).
- AI avatars, eye-contact correction and prompt-driven editing are out of scope without paid models.
