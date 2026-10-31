# Studio vs Spark Station: gap report (2026-10-31)

This compares what Studio does against everything in `docs/sparkstation-spec.md` and `docs/sparkstation-spec-addendum.md`.

## Free tier (new)

With no paid keys, every capability now runs at no cost on commercially usable open models (`server/studio/free.py`):

| Capability | Free engine | Licence |
|---|---|---|
| Text, scripts, plans, QC (vision) | Qwen3-VL-4B-Instruct, inside this Space on ZeroGPU | Apache-2.0 |
| Images | FLUX.1-schnell (public ZeroGPU Space) | Apache-2.0 |
| Image edit, inpaint, try-on, face swap | Qwen-Image-Edit (try-on and face swap use side-by-side panels; inpaint composites through your mask) | Apache-2.0 |
| Video (text and image to video, up to 8.5 s) | LTX-Video 0.9.8 distilled | LTXV open weights (free under $10M revenue) |
| Music, songs with lyrics | ACE-Step | Apache-2.0 |
| Sound effects | Stable Audio Open | Stability community (free under $1M revenue) |
| Upscale | Finegrain image enhancer | MIT |
| Background removal | BiRefNet | MIT |
| Lip sync | LatentSync | Apache-2.0 |
| Voice | Kokoro-82M, in this Space | Apache-2.0 |
| Subtitles | faster-whisper, in this Space | MIT |

Limits:
- GPU time comes from Hugging Face's free daily ZeroGPU quota. Set `HF_TOKEN` as a Space secret to use your own account's quota.
- Each public Space can be busy, sleep or change its API. When one fails, the job says so plainly and nothing is billed. Swapping a Space is one line in `SPACES`.
- Quality is below Veo, Kling or GPT Image, most of all for video (short clips at about 768×448).
- Add any paid key later and that capability switches to it automatically. The rest stay free.

## Covered (matches the spec)

- **Film Studio:** Script → Cast → Scenes → Score → Final cut.
- **Pre-production:** Story Builder, Script Doctor, Storyboard Builder, Budget Estimator.
- **Casting and continuity:** Casting Director, the 5 continuity locks, expression sheets, turnaround sheets.
- **Image suite:** all 16 sub-tools, plus background change.
- **Video:** generation with the camera rig, the movement library, multiple models and QC.
- **Voice, music and sound:** voice (30 Gemini voices plus Kokoro), music with lyrics and seed, SFX, lip sync.
- **Ad Factory:** 5 studios, including batch from CSV or Excel.
- **Post-production:** Subtitle Creator, Contextual Dubbing, the Pulse editor.
- **Distribution:** Video Intelligence, Thumbnails, Posters, Adapt, Video Reframe, Comics, Visual Explainer.
- **Helpers:** Prompt Assistant, Prompt Studio, Reverse Prompt Engineer, Quality Analyzer.
- **Platform:** Assets library, History, Usage and spend, model routing, themes.

## Added in this pass

- The Free provider and free-tier status panel (Settings).
- A cost estimate next to every Generate button: "Free", "≈ $x per run" or "Placeholder". The spec says every paid button shows its cost first.
- Optional password for the public site: set `OPENCAP_PASSWORD` as a Space secret.
- NLE hand-off from Film Studio's final cut: a zip with a CMX3600 EDL, an FCPXML, subtitles and the media, like the spec's Premiere / Resolve / Final Cut hand-off.
- Subtitle Creator's custom vocabulary now reaches Whisper (correct spelling of names and jargon).
- One-click prompt helpers. Music gets timestamp, BPM, key, intensity and instrumental. Video gets dialogue, SFX and ambience. Every prompt box gets `@Name` buttons for locked characters.
- PDF reading for Story Builder, Script Doctor, Budget and Visual Explainer (`pypdf` installed).

## Still missing (in rough priority order)

| # | Spark Station feature | Where in the spec | Effort |
|---|---|---|---|
| 1 | Accounts and sign-in (Google, email), with per-user projects and history | §0, §26 | Large: needs a database and auth |
| 2 | Video Editor **Copilot**: plain-language edit requests returning proposed splits, trims, titles and transitions | §15 | Medium (LLM over the Pulse timeline) |
| 3 | Editor **Watch** shot log, searchable by what is said and shown | §15 | Medium (vision LLM over key frames) |
| 4 | **Motion graphics** presets: opening title, lower third, logo reveal, kinetic quote, animated chart, map route, end card | §15 | Medium |
| 5 | Story Builder **writers' room** chat, and translation as a linked copy | §5.1 | Small to medium |
| 6 | Saved **versions** for Story Builder and Budget, and Budget export to Word (.docx) | §5.1, §5.4 | Small |
| 7 | Voice picker with **preview samples** and gender filter | §6 | Small |
| 8 | Camera-move **preview clips** in the movement library | §2 | Small (needs 24 short demo clips) |
| 9 | Subtitle **speaker labels**, plus a caption timeline for snap-to-playhead and shift (the Pulse editor covers part of this) | §16 | Medium |
| 10 | Library **folders**, and "add to an Element" from the library | §26 | Small |
| 11 | **Teams** and enterprise: seats, roles, model allowlists, per-project spend caps, audit log, SSO | §26 and addendum | Large |
| 12 | Real **credits and billing** (a token ledger and top-ups) instead of estimates | §26 | Large |
| 13 | Live video for **Video Intelligence** from a URL (YouTube or stream) instead of an upload | §20 | Small (yt-dlp) |
| 14 | Visual Explainer OCR of **handwritten-note photos** in topic mode | §22 | Small (vision model already available) |

Items 5, 6, 7, 10, 13 and 14 are quick and come next. Items 1, 11 and 12 depend on how the product will be sold.
