# Feature map: Captions.ai, Kapwing, VEED → Pulse

Scraped 2026-10-17 from the public tool indexes (`captions.ai`, `kapwing.com/tools`, `veed.io/tools`).
Kapwing lists 342 tool pages, VEED 1,161 (most are SEO variants of the same tool). Grouped below by capability,
with how Pulse implements each **for free, locally, with no API keys**.

| Capability | Captions.ai | Kapwing | VEED | Pulse (free/local) | Status |
|---|---|---|---|---|---|
| Auto captions, word timestamps | ✔ 100+ styles | ✔ subtitles/caption-generator | ✔ add-subtitles, animated-subtitles | faster-whisper large-v3-turbo (CTranslate2, CPU int8), word timestamps + VAD | v1 |
| Caption styles / animations | AI Edit styles (152) | basic presets | basic presets | 20 presets derived from the measured Captions.ai patterns (word-fill, blur-pop, append, line-stack, pills, bars, moving highlight box, hollow inactive, emphasis colour/size/glow) | v1 |
| Caption editor (text, timing, split/merge) | ✔ | ✔ subtitles/editor | ✔ | word list editor, click to delete/emphasise, drag timing on timeline | v1 |
| SRT / VTT export & import | ✔ | ✔ srt/vtt maker, converter | ✔ | /api/subtitles/srt, drop .srt to import | v1 |
| Translate subtitles | ✔ 100+ langs | ✔ subtitles/translator | ✔ | argos-translate offline packages (download on demand) | v2 |
| Text-based editing (delete words = cut video) | ✔ Trim pauses | ✔ smart-cut | ✔ | cuts list + timeline remap; preview skips cuts; export applies | v1 |
| Filler-word removal | ✔ | ✔ smart-cut/filler-words | ✔ | regex over transcript (um, uh, like, you know…) + one-click delete | v1 |
| Silence removal | ✔ | ✔ audio-editor/silence-remover | ✔ | gaps between words > threshold → cuts | v1 |
| Auto zoom / punch-ins | ✔ AI Edit | ✔ keyframing | ✔ | zoom keys at emphasis cards (pattern G: 1.05–1.08 over 250 ms easeOut) | v1 |
| B-roll | ✔ AI b-roll | ✔ | ✔ ai-b-roll-generator | user-uploaded B-roll clips/images placed on the timeline; no stock API (needs keys) | v2 |
| Text / emoji / sticker overlays | ✔ | ✔ add-text, add-sticker, add-emojis | ✔ | overlay layer (text, native emoji, images) drawn by the same canvas engine | v1 |
| Resize / reframe (9:16, 1:1, 16:9) | ✔ | ✔ resize | ✔ | output aspect + crop position in the compositor | v1 |
| Trim / split / merge clips | ✔ | ✔ | ✔ | timeline cuts; merge = multi-source timeline | v1 / v2 |
| Denoise / enhance speech | ✔ Denoise | ✔ denoise, audio-enhancer | ✔ ai-audio-enhancer | ffmpeg afftdn / loudnorm / compressor chain | v1 |
| Music & SFX | ✔ generate | ✔ add-audio | ✔ | user-provided tracks with ducking (sidechain) ; generation needs a model, out of scope | v2 |
| Text to speech | — | ✔ 100+ langs | ✔ | Kokoro-82M ONNX (free, offline, ~330 MB) | v2 |
| Voice clone / AI twin | ✔ AI twin | ✔ | ✔ ai-clone | needs F5-TTS / XTTS (multi-GB models); exposed as an optional plugin endpoint, off by default | v3 |
| Eye-contact correction | ✔ | ✔ adjust/eye-contact | ✔ | no free local model of acceptable quality; not planned | — |
| AI avatars | ✔ | ✔ | ✔ | out of scope | — |
| Background removal / blur | — | ✔ remove-background | ✔ ai-background-remover | MediaPipe selfie segmentation in browser (free) | v3 |
| Screen / webcam recording | ✔ | ✔ record/* | ✔ | getUserMedia / getDisplayMedia + MediaRecorder → upload | v2 |
| Convert / compress | — | ✔ convert/*, compress/* | ✔ | ffmpeg endpoints | v2 |
| Chat / prompt editing | ✔ Text to edit | ✔ ai/video-assistant | ✔ | not planned without an LLM key; rule-based "auto edit" button instead | — |
| Export | ✔ | ✔ | ✔ | client-side WebCodecs (H.264 + AAC via mp4-muxer); server ffmpeg fallback for cuts | v1 |

## Captions.ai specifics worth copying

- Style = font + placement + reveal + entrance + emphasis + box. Every one of the 54 premium styles decomposes into those six fields (see `captions-ai-research/caption-motion-patterns.md`).
- Measured defaults: band centre 67 % of height (9:16), 2 words per chunk, chunk hold 0.5 s median, whole-chunk entrance 80–150 ms blur-pop, inactive words 40 %.
- Four colour slots per basic preset: text, emphasis, stroke/container, glow.

## Kapwing specifics

- Tool index categories: Video Editing, Subtitle/Translate/Transcribe, AI Generators, Audio Tools, Text to Speech, Social Media Editing, Convert & Compress, Image & GIF.
- "Smart Cut" = silence + filler removal, the same two operations Pulse derives from the transcript.

## VEED specifics

- Same core (subtitles, text-based editing, audio enhance) plus a very long tail of AI image filters; Pulse ignores the image-filter tail.
