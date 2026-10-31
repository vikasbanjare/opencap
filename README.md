---
title: Pulse by aifloh
emoji: 🎬
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: 6.30.0
python_version: '3.12'
app_file: app.py
pinned: false
short_description: Free AI captions and video editor
---

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

## Studio: the full AI production suite

The home page is **Studio**, an open rebuild of the Spark Station tool set. `docs/sparkstation-spec.md` and `docs/sparkstation-spec-addendum.md` list every input and output it copies. There are 52 tools in 10 groups. Every tool is declared once in `server/studio/tools.py` (inputs, outputs, pipeline), and the web app renders its form from that.

| Group | Tools |
|---|---|
| **Film Studio** | One project carried through **Script** (write from a logline or import Fountain/FDX/PDF; parsed into scenes and dialogue) → **Cast** (every speaking role cast, locked with a voice and a 4-angle turnaround) → **Scenes** (shot breakdown under the 180° rule, key frames with locked faces, image-to-video, dialogue voiced per character) → **Score** (cue sheet per scene: mood, BPM, key, instruments; plus SFX) → **Final cut** (title, credits, ducked mix, subtitles, loudness target) |
| Pre-production | Story Builder (intent locks → outline → draft + production pack; Fountain/FDX/CSV/MD/JSON) · Script Doctor (score /100, 6 axes with cited lines, 16 dimensions, setup/payoff ledger, production footprint) · Storyboard Builder (shot list → style frame → 9-panel pages, PDF/PNG/CSV) · Budget Estimator (line items, take multipliers, 5 currencies) |
| Casting & continuity | Casting Director (2/4/6/8 candidates, 20 styles, lock your pick) · Characters & Elements (identity, expression, wardrobe, location, prop locks; `@Name` in any prompt) · Expression sheet |
| Image suite | Generation · Multi-Angles · Multi-Shots · Relight · Age Progression · Reimagine Scene · Skin Realism · Palette Studio · Background Change · Upscale · Inpaint (mask painter) · Face Swap · Virtual Try-On · Model Photoshoot · Draw to Paint (sketch canvas) · Color Grading (presets + sliders, local pixel maths) |
| Video | Video Generation: start/end frame, reference clip, camera rig (body, lens, focal length, aperture), 24 camera moves, style presets, audio, multi-model take comparison |
| Voice, music & sound | Voice (30 Gemini voices, 6 style presets, Kokoro offline) · Music (timestamped sections, vocals + lyrics, seed) · Sound Effects · Lip Sync |
| Ad Factory | Micro Ad Factory (8-step agent pipeline, 9:16 + 16:9 together, end plate, QC with auto-retake below threshold) · Ecommerce Image Studio (23 scenarios) · Ecommerce Video Studio (14) · UGC Ads Studio (17 formats) · Video Batch Generation (CSV/Excel rows → queued ads + report) |
| Post-production | Video Editor (the Pulse editor) · Contextual Dubbing (idiomatic adaptation timed to the original lines, per-speaker voices, original ducked underneath, optional lip-sync) · Subtitle Creator (rhythm, line length, sound-cue tags, profanity censoring, 38 languages, 12 styles; burned-in/soft-track MP4, ASS karaoke, SRT, VTT, TXT, JSON) |
| Package & distribute | Video Intelligence (key frames → highlights → teaser/trailer/reel) · Thumbnail Creator (16 templates, all sizes at once) · Poster Creation (16 genre styles, 6 formats) · Adapt (16 image sizes, extend canvas or smart crop) · Video Reframe (14 ratios, auto subject placement) · Comics Generator (12 styles, editable panel plan, flipbook, PDF) · Visual Explainer (120+ commands) |
| Prompt & quality | Prompt Assistant · Prompt Studio templates · Reverse Prompt Engineer · Quality Analyzer (5-axis score against the brief and locked characters) |

Results can be sent from any tool to the next one (an image becomes the first frame of a video, a shot list becomes a storyboard, a plan becomes a render). Everything lands in the **Assets library** and per-tool **History**, and every model call is logged on **Usage & spend**.

**Free by default.** With no paid keys, every tool runs on free, commercially usable open models. Text and vision use Qwen3-VL-4B on the Space's ZeroGPU. Images, edits, video, music, SFX, upscaling, background removal and lip sync use public ZeroGPU Spaces. Voice uses Kokoro. `server/studio/free.py` lists them, and `docs/gap-report.md` covers limits and what's still missing. Set `HF_TOKEN` as a Space secret to use your own GPU quota, `OPENCAP_PASSWORD` to require a password, and `OPENCAP_FREE=0` to turn the free tier off.

**Models are pluggable.** `server/studio/providers.py` routes each capability (text, vision, image, edit, video, TTS, music, SFX, upscale, face swap, try-on, inpaint, background removal, lip sync) to one of these providers:

| Provider | Env var | Covers |
|---|---|---|
| fal.ai | `FAL_KEY` | Flux, Imagen 4, Seedream, Nano Banana, Kling, Veo 3, Seedance, Hailuo, upscalers, face swap, Kolors try-on, Flux Fill, BiRefNet, Stable Audio/Lyria, sync-lipsync |
| OpenAI | `OPENAI_API_KEY` | GPT-5 text and vision, gpt-image-1 (generate, edit, inpaint), Sora 2, TTS |
| Google | `GEMINI_API_KEY` | Gemini text and vision, Gemini image, Veo 3, Gemini TTS voices |
| ElevenLabs | `ELEVENLABS_API_KEY` | voices, music, sound effects |
| Replicate | `REPLICATE_API_TOKEN` | Flux, Kling, Real-ESRGAN, background removal |

Keys can be set as environment variables or pasted under **Models & keys**, where you also pick the provider and model per capability. Keys pasted there are saved to `server/studio-settings.json`, which is outside the public `/media` folder and is gitignored; `OPENCAP_STUDIO_SETTINGS` moves it. **With no keys every tool still runs**, using a local `mock` provider that makes labelled placeholder images, video and audio, so the whole pipeline can be tried for free. These parts are always local and free: grading, crops, layouts, PDFs, reframing, subtitles (Whisper), Kokoro voice and all ffmpeg assembly.

**Research behind the tools.** Each tool follows the documented practice for its craft. The provider contracts were checked against the providers' current docs on 2026-10-28.

| Doc | What it holds |
|---|---|
| `docs/tool-research.md` | Prompting guides for Veo, Kling, Seedance and GPT Image (cinematography first, one camera move per segment), character-consistency pipelines, studio coverage format and Black List scoring, Save the Cat and other beat targets, breakdowns and per-second AI pricing with keep rates, shot grammar, short-form ad structure and platform safe zones, Netflix/BBC timed-text rules, trailer structure, thumbnail and poster conventions, scoring by emotion and loudness targets, VLM-as-judge QC, and colour science (skin-protected teal & orange, bleach bypass, halation) |
| `docs/provider-contracts.md` | Endpoints, model ids, parameter enums and output shapes for each provider, with the dated retirements (Sora API, Veo on the Gemini API, gpt-image-1) |

**Theme.** The **Models, keys & theme** page and the sidebar swatches switch between 6 palettes, with custom accents and corner radius saved in your browser. Each palette is one entry in `src/studio/themes.ts`, so you can add or change one there; nothing in the CSS hard-codes a colour.

API: `GET /api/studio/tools` returns the catalogue. `POST /api/studio/tools/{id}/run` takes multipart fields and files and returns a job; poll `GET /api/studio/jobs/{id}`. The other routes are `/api/studio/assets`, `/characters`, `/films`, `/settings` and `/usage`.

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
