# Provider contracts (verified 2026-10-28)

What every adapter in `server/studio/providers.py` actually has to send and read, checked against the
providers' own docs and model pages on 2026-10-28. Section 1 is the verified contract per provider and
capability. Section 2 lists every place where `providers.py` disagrees with it, with the exact fix.

Sources were the fal model pages (`https://fal.ai/models/<id>/llms.txt`, the same schema as `/api`),
developers.openai.com (the docs moved there from platform.openai.com), ai.google.dev, elevenlabs.io/docs
and the replicate.com model pages (`/llms.txt`). The pages quoted in the tables were all read on this date.

## Summary: what is broken today

The following break hard, with a 4xx/404 or a dead endpoint, on the current defaults:

| # | Provider / cap | Why |
|---|---|---|
| D1 | OpenAI image/edit/inpaint | `gpt-image-1` was **shut down 2026-10-23** |
| D2 | OpenAI video | **Videos API and all `sora-2*` models shut down 2026-09-24**, with no replacement |
| D3 | Gemini video | **Every Veo model on the Gemini API is shut down** (`veo-3.0-*` on 2026-06-30, `veo-3.1-*-preview` on 2026-10-22). `predictLongRunning` is gone. The replacement is `gemini-omni-1.1-flash` on the Interactions API |
| D4 | fal video, Veo | `duration` is sent as `"5s"`. Only `"4s"`, `"6s"` and `"8s"` are allowed (422) |
| D5 | fal video, Hailuo-02 | `duration` is sent as `"5"`. Only `"6"` and `"10"` are allowed (422) |
| D6 | fal video, Kling 2.1 master | Any duration other than 5 or 10 (for example `"8"`) gives a 422 |
| D7 | fal faceswap | `fal-ai/face-swap` no longer exists (its model page returns 404) |
| D8 | Replicate bg_remove | `851-labs/background-remover` is not an official model, so `/v1/models/{o}/{n}/predictions` rejects it |
| D9 | Replicate video, Kling | `kwaivgi/kling-v2.1` requires `start_image`, so text-to-video always fails |
| D10 | Replicate video, MiniMax | The image is sent as `start_image`, but the field is `first_frame_image`, so the image is silently dropped |

These are on a shutdown clock and fail soon: `gpt-5`/`gpt-5-mini` (2026-12-11), ElevenLabs default voices
such as Rachel (2026-12-31), `gpt-4.1` (2027-01-14), `gpt-4o-mini-tts` (2027-01-06),
`gemini-2.5-flash-image` (2027-03-15) and `gemini-3.1-flash-tts-preview` (2026-11-17).

---

## 1. Verified contracts

### 1.1 fal.ai (queue API)

**Transport (all fal models)**: source https://fal.ai/docs/documentation/model-apis/inference/queue

| Item | Contract |
|---|---|
| Submit | `POST https://queue.fal.run/{endpoint_id}` with a JSON body holding the model input |
| Auth | `Authorization: Key $FAL_KEY` |
| Submit response | `{request_id, response_url, status_url, cancel_url, queue_position}` |
| Status | `GET status_url` returns `status` ∈ `IN_QUEUE` / `IN_PROGRESS` / `COMPLETED`. There is no FAILED status. A failure is `COMPLETED` plus `error` and `error_type` |
| Result | `GET response_url` |
| URL note | status and response URLs use only `owner/app` (for example `fal-ai/kling-video/requests/{id}`). If you build them yourself with the full endpoint path you get a 405, so always use the URLs that come back |
| File inputs | Any `*_url` field accepts an https URL **or a base64 `data:` URI**. For large files fal recommends uploading to its storage or CDN |

**Image**

| Endpoint id | Key inputs (exact) | Output | Source |
|---|---|---|---|
| `fal-ai/flux/dev` | `prompt`, `image_size` (enum or `{width,height}`), `num_images` 1–4, `seed`, `guidance_scale`, `output_format`. **No `aspect_ratio`, no `negative_prompt`** | `images[].url` | fal.ai/models/fal-ai/flux/dev |
| `fal-ai/flux-pro/v1.1-ultra` | `prompt`, `aspect_ratio` (default `16:9`; the documented enum is 21:9, 16:9, 4:3, 3:2, 1:1, 2:3, 3:4, 9:16, 9:21), `num_images` 1–4, `seed`, `raw`, `safety_tolerance`. **No `image_size`** | `images[].url` | fal.ai/models/fal-ai/flux-pro/v1.1-ultra |
| `fal-ai/imagen4/preview` | The model page still loads, but its schema (`llms.txt`) returns 404. Google shut down Imagen 4 on its own API on 2026-08-17. **Treat as retired** | n/a | fal.ai/models/fal-ai/imagen4/preview |
| `fal-ai/bytedance/seedream/v4/text-to-image` | `prompt`, `image_size` (960²–4096²), `num_images` 1–6, `max_images`, `seed`. **No `aspect_ratio`** | `images[].url` | fal.ai/models/fal-ai/bytedance/seedream/v4/text-to-image |
| `fal-ai/nano-banana` | `prompt`, `num_images` 1–4, `seed`, `aspect_ratio` (21:9, 16:9, 3:2, 4:3, 5:4, 1:1, 4:5, 3:4, 2:3, 9:16), `output_format` | `images[].url`, `description` | fal.ai/models/fal-ai/nano-banana |
| Newer: `fal-ai/nano-banana-2`, `google/nano-banana-2.1`, `fal-ai/flux-2-pro`, `fal-ai/bytedance/seedream/v4.5/text-to-image`, `bytedance/seedream/v5/...` | All exist on fal now | | fal.ai/explore/google, fal.ai search |

**Edit**

| Endpoint id | Key inputs | Output | Source |
|---|---|---|---|
| `fal-ai/nano-banana/edit`, `fal-ai/nano-banana-2/edit` | `prompt`, **`image_urls`** (list), `num_images` 1–4, `aspect_ratio` (adds `auto`, 4:1, 1:4, 8:1, 1:8 on v2), `resolution` `0.5K`/`1K`/`2K`/`4K` (v2) | `images[].url` | fal.ai/models/fal-ai/nano-banana-2/edit |
| `fal-ai/bytedance/seedream/v4/edit` | `prompt`, **`image_urls`** (required, up to 10), `image_size`, `num_images` 1–6 | `images[].url` | fal.ai/models/fal-ai/bytedance/seedream/v4/edit |
| `fal-ai/flux-pro/kontext` | `prompt`, **`image_url`** (single, required), `aspect_ratio` (enum above), `num_images` 1–4 | `images[].url` | fal.ai/models/fal-ai/flux-pro/kontext |

**Video**

Image-to-video naming per family: base `fal-ai/kling-video/<ver>/<tier>` with `/text-to-video` or
`/image-to-video`; `fal-ai/veo3` (text) and `fal-ai/veo3/image-to-video`;
`fal-ai/bytedance/seedance/v1/pro/{text,image}-to-video`; `fal-ai/minimax/hailuo-02/standard/{text,image}-to-video`.

| Endpoint id | duration | aspect_ratio | image field(s) | audio | Output | Source |
|---|---|---|---|---|---|---|
| `fal-ai/kling-video/v2.1/master/text-to-video` | `"5"` or `"10"` (string) | 16:9, 9:16, 1:1 | n/a | none | `video.url` | fal.ai/models/fal-ai/kling-video/v2.1/master/text-to-video |
| `fal-ai/kling-video/v2.1/master/image-to-video` | `"5"` or `"10"` | **none** | `image_url`. **No end-frame field** | none | `video.url` | …/v2.1/master/image-to-video |
| `fal-ai/kling-video/v3/pro/text-to-video` (current Kling) | `"3"`…`"15"` | 16:9, 9:16, 1:1 | n/a | `generate_audio` (default true) | `video.url` | …/v3/pro/text-to-video |
| `fal-ai/kling-video/v3/pro/image-to-video` | `"3"`…`"15"` | none | **`start_image_url`** (required), `end_image_url` | `generate_audio` | `video.url` | …/v3/pro/image-to-video |
| `fal-ai/veo3` (text) | **`"4s"`, `"6s"`, `"8s"`** | 16:9, 9:16 | n/a | `generate_audio` (default true) | `video.url` | fal.ai/models/fal-ai/veo3 |
| `fal-ai/veo3/image-to-video` | `"4s"`, `"6s"`, `"8s"` | auto, 16:9, 9:16 | `image_url` | `generate_audio` | `video.url` | …/veo3/image-to-video |
| `fal-ai/veo3.1`, `/image-to-video`, `/first-last-frame-to-video` (and `fal-ai/veo3.1/fast/...`) | `"4s"`, `"6s"`, `"8s"` | 16:9, 9:16 (plus auto for i2v) | `image_url`, or **`first_frame_url` and `last_frame_url`** for first-last-frame | `generate_audio`; `resolution` 720p, 1080p or 4k | `video.url` | …/veo3.1/* |
| `fal-ai/bytedance/seedance/v1/pro/image-to-video` | `"2"`…`"12"` | 21:9, 16:9, 4:3, 1:1, 3:4, 9:16, auto | `image_url`, `end_image_url` | none | `video.url` | …/seedance/v1/pro/image-to-video |
| `bytedance/seedance-2.0/{text,image}-to-video` (current; **no `fal-ai/` prefix**) | `"auto"`, `"4"`…`"15"` | auto, 21:9, 16:9, 4:3, 1:1, 3:4, 9:16 | `image_url`, `end_image_url` | `generate_audio` | `video.url` | fal.ai/models/bytedance/seedance-2.0/* |
| `fal-ai/minimax/hailuo-02/standard/text-to-video` | **`"6"` or `"10"`** | **none** | n/a | none | `video.url` | …/hailuo-02/standard/text-to-video |
| `fal-ai/minimax/hailuo-02/standard/image-to-video` | `"6"` or `"10"` | none | `image_url`, `end_image_url` | none | `video.url` | …/hailuo-02/standard/image-to-video |

**Audio and utilities**

| Endpoint id | Inputs | Output | Source |
|---|---|---|---|
| `fal-ai/elevenlabs/tts/multilingual-v2` | `text`, `voice` (name, default `"Rachel"`), `speed` 0.7–1.2, `stability`, `similarity_boost` | `audio.url` | …/elevenlabs/tts/multilingual-v2 |
| `fal-ai/stable-audio` | `prompt`, **`seconds_total` 0–47**, `steps` | **`audio_file.url`** | …/stable-audio |
| `fal-ai/lyria2` | `prompt`, `negative_prompt`, `seed` (fixed ~30 s, no duration field) | `audio.url` (wav) | …/lyria2 |
| `fal-ai/clarity-upscaler` | `image_url`, `upscale_factor` 1–4, `prompt` | `image.url` | …/clarity-upscaler |
| `fal-ai/esrgan` | `image_url`, `scale` 1–8, `model` | `image.url` | …/esrgan |
| `fal-ai/video-upscaler` | `video_url`, `scale` 1–8 | `video.url` | …/video-upscaler |
| `fal-ai/face-swap` | **404, gone** | n/a | n/a |
| `easel-ai/advanced-face-swap` (replacement) | `face_image_0` (required), `gender_0` (required: male, female or non-binary), `target_image`, `workflow_type` (required: user_hair or target_hair), `face_image_1`, `upscale` | `image.url` | fal.ai/models/easel-ai/advanced-face-swap |
| `fal-ai/kling/v1-5/kolors-virtual-try-on` | `human_image_url`, `garment_image_url` | `image.url` | …/kolors-virtual-try-on |
| `fal-ai/flux-pro/v1/fill` | `image_url`, `mask_url` (same dimensions), `prompt`, `num_images` | `images[].url` | …/flux-pro/v1/fill |
| `fal-ai/birefnet` | `image_url`, `model`, `output_mask`, `output_format` | `image.url` (+ optional `mask_image`) | …/birefnet |
| `fal-ai/sync-lipsync` | `video_url`, `audio_url`, `model` (default lipsync-1.9.0-beta), `sync_mode` | `video.url` | …/sync-lipsync |

### 1.2 OpenAI

Auth: `Authorization: Bearer $OPENAI_API_KEY`, base `https://api.openai.com/v1`.
Sources: https://developers.openai.com/api/docs/deprecations, /docs/models, /docs/guides/image-generation, /docs/guides/text-to-speech.

| Cap | Endpoint | Current model ids | Params | Output |
|---|---|---|---|---|
| llm/vision | `POST /chat/completions` | `gpt-6-luna` (cheap), `gpt-6.1-terra`, `gpt-6.1-sol`, `gpt-6-astra`. Deprecated: `gpt-5`, `gpt-5-mini` (shut down 2026-12-11, replaced by `gpt-5.6-*`), `gpt-4.1` (2027-01-14, replaced by `gpt-6-luna`) | `messages`, `response_format:{type:json_object}`. Image parts as `{"type":"image_url","image_url":{"url":data_uri}}` | `choices[0].message.content` |
| image | `POST /images/generations` (JSON) | **`gpt-image-2.5-flare`** (fast), **`gpt-image-2.5-sunburst`** (editing precision), `gpt-image-2`. `gpt-image-1` was **shut down 2026-10-23**; `gpt-image-1.5` and `gpt-image-1-mini` shut down 2026-12-01 | `prompt`, `n`, `size` (`1024x1024`, `1536x1024`, `1024x1536`, `auto`, or any `WxH` with both edges multiples of 16, ratio ≤ 3:1, edges ≤ 3840, 655,360–8,294,400 px), `quality` low/medium/high/xhigh/max/auto, `output_format`, `background` | `data[].b64_json` (always base64) |
| edit | `POST /images/edits` (multipart) | same | repeated `image[]` file parts, optional `mask` file, `prompt`, `n`, `size`. **The mask must have an alpha channel and the same format and size as the image** (alpha 0 marks where to edit). Omit `input_fidelity` for gpt-image-2 | `data[].b64_json` |
| video | `POST /videos` | **Shut down 2026-09-24 (Videos API + `sora-2`, `sora-2-pro`), no replacement** | n/a | n/a |
| tts | `POST /audio/speech` (JSON, binary response) | `gpt-4o-mini-tts`, `tts-1`, `tts-1-hd`, **all deprecated with shutdown 2027-01-06**. The replacement `gpt-realtime-2.1-mini` is Realtime-API only and not usable on `/audio/speech` | `model`, `input`, `voice` ∈ alloy, ash, ballad, coral, echo, fable, nova, onyx, sage, shimmer, verse, marin, cedar (marin or cedar recommended), `speed`, `response_format` (default mp3) | audio bytes |

### 1.3 Google Gemini API

Base `https://generativelanguage.googleapis.com/v1beta`. Auth is `x-goog-api-key: $KEY` (docs) or `?key=`.
Sources: https://ai.google.dev/gemini-api/docs/deprecations, /api/generate-content, /gemini-api/docs/image-generation, /gemini-api/docs/omni, /gemini-api/docs/speech-generation, /api/interactions-api.

| Cap | Endpoint | Current model ids | Request | Output |
|---|---|---|---|---|
| llm/vision | `POST /models/{m}:generateContent` (still supported; docs now also show `/interactions`) | `gemini-3.8-flash`, `gemini-3.6-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-pro-preview`. `gemini-2.5-flash` and `gemini-2.5-pro` are **restricted to prior users** ("for any new projects use 3.5 Flash-Lite or 3.8 Flash"), so new keys can be refused | `contents[].parts[]` (`text`, `inlineData{mimeType,data}`; snake_case `inline_data` is also accepted), `systemInstruction`, `generationConfig.responseMimeType` | `candidates[0].content.parts[].text` |
| image/edit | `POST /models/{m}:generateContent`, or `POST /interactions` (the docs' primary path) | `gemini-3.1-flash-image` (GA, Nano Banana 2), `gemini-nano-banana-2.1` (newest; documented only with Interactions), `gemini-3-pro-image`, `gemini-3.1-flash-lite-image`. **`gemini-2.5-flash-image` shuts down 2027-03-15** | generateContent: `generationConfig.responseModalities:["IMAGE"]` or `["TEXT","IMAGE"]`, **`generationConfig.imageConfig.aspectRatio`** ∈ 1:1, 1:4, 4:1, 1:8, 8:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9, `imageConfig.imageSize` ∈ 512, 1K, 2K, 4K | `candidates[0].content.parts[].inlineData.data` (camelCase in responses) |
| video | **`POST /interactions`**. `models/veo-*:predictLongRunning` is dead | **`gemini-omni-1.1-flash`**. All Veo ids are shut down on the Gemini API | `{"model","input": str or [{"type":"image","data":b64,"mime_type"},{"type":"text","text"}], "response_format":{"type":"video","aspect_ratio":"16:9"or"9:16","resolution":"360p","720p","1080p"or"4k","delivery":"uri"}, "generation_config":{"video_config":{"task":"text_to_video"or"image_to_video"}}}`. Two images give first/last-frame interpolation. No duration field and no negative prompt | `steps[type=model_output].content[type=video]` with `.data` (base64) or `.uri` (download with the key). `status` ∈ in_progress, completed, failed, …; poll with `GET /interactions/{id}` |
| tts | `POST /interactions` (generateContent `speechConfig` still exists) | **`gemini-3.8-flash-tts`**, `gemini-3.8-flash-lite-tts`. **`gemini-3.1-flash-tts-preview` does exist** but shuts down 2026-11-17; `gemini-2.5-flash-preview-tts` and `gemini-2.5-pro-preview-tts` also shut down 2026-11-17 | `input:[{"type":"user_input","content":[{"type":"text","text":…,"annotations":[{"type":"speech_metadata","style":…}]}]}]`, `response_format:{"type":"audio"}`, `generation_config.speech_config:[{"voice":"Kore"}]` (an array for one speaker, `{speakers:[…]}` for several). generateContent form: `generationConfig.speechConfig.voiceConfig.prebuiltVoiceConfig.voiceName`. Voices: Zephyr, Puck, Charon, Kore, Fenrir, Leda, Orus, Aoede, Callirrhoe, Autonoe, Enceladus, Iapetus, Umbriel, Algieba, Despina, Erinome, Algenib, Rasalgethi, Laomedeia, Achernar, Alnilam, Schedar, Gacrux, Pulcherrima, Achird, Zubenelgenubi, Vindemiatrix, Sadachbia, Sadaltager, Sulafat | `steps[].content[type=audio].data`, base64 **WAV** (24 kHz mono) by default |
| music | `lyria-3.5` (GA), `lyria-3-pro-preview` | n/a | n/a | n/a |

### 1.4 ElevenLabs

Base `https://api.elevenlabs.io/v1`, auth `xi-api-key`. Sources: elevenlabs.io/docs/api-reference/text-to-speech/convert, /music/compose, /text-to-sound-effects/convert, /docs/overview/models, /docs/overview/capabilities/voices.

| Cap | Endpoint | Body | Models | Output |
|---|---|---|---|---|
| tts | `POST /text-to-speech/{voice_id}` (`?output_format=`, default `mp3_44100_128`) | `text`, `model_id` (default `eleven_multilingual_v2`), `voice_settings{stability, similarity_boost, style, speed}`, `seed`, `language_code` | `eleven_v3`, `eleven_multilingual_v2`, `eleven_flash_v2_5`, `eleven_flash_v2`. **`eleven_turbo_v2_5` is deprecated (use `eleven_flash_v2_5`)**. `eleven_v4` and `eleven_v4_turbo` are only on the Text-to-Dialogue API | audio bytes (mp3) |
| voices | `GET /v2/voices` | n/a | **"All our Default voices will expire on December 31, 2026"**, and that includes Rachel `21m00Tcm4TlvDq8ikWAM` | n/a |
| music | `POST /music` | `prompt` (≤ 4100 chars) or `composition_plan`, **`music_length_ms` 3000–600000**, `model_id` (default `music_v1`), `force_instrumental`, `seed` | `music_v2_5` (best), `music_v2`, `music_v1` ("outclassed") | audio bytes (mp3_48000_192 for v2 under `auto`) |
| sfx | `POST /sound-generation` | `text`, **`duration_seconds` 0.5–30** (or null for auto), `prompt_influence` 0–1, `loop`, `model_id` (default `eleven_text_to_sound_v2`) | `eleven_text_to_sound_v2` | audio bytes (mp3) |

### 1.5 Replicate

Auth `Authorization: Bearer $REPLICATE_API_TOKEN`. Sources: replicate.com/docs/topics/models/official-models,
/docs/topics/predictions/create-a-prediction, /docs/topics/predictions/input-files, /collections/official and the model `llms.txt` pages.

| Item | Contract |
|---|---|
| Official models | `POST https://api.replicate.com/v1/models/{owner}/{name}/predictions` with body `{"input":{…}}` and no version. **Only official models** |
| Community models | `POST https://api.replicate.com/v1/predictions` with `{"version": "<version id>", "input": {…}}` |
| Sync | `Prefer: wait` (60 s default, `wait=N`). Returns the prediction; poll `urls.get` until `succeeded`, `failed` or `canceled` |
| File inputs | URL, or a data URI (**recommended only below 1 MB**) |

| Model | Official? | Inputs | Output |
|---|---|---|---|
| `black-forest-labs/flux-schnell` | yes | `prompt`, `aspect_ratio`, `num_outputs`, `seed`, `output_format`, `megapixels` | array of URLs |
| `black-forest-labs/flux-1.1-pro` | yes | `prompt`, `aspect_ratio`, `seed`, `width`/`height` (with `custom`), `safety_tolerance`. **No `num_outputs`** (one image) | URL string |
| `kwaivgi/kling-v2.1` | yes | `prompt`, **`start_image` (required)**, `end_image` (pro only), `mode`, `duration` (int 5/10), `negative_prompt`. **No `aspect_ratio`** | URL string |
| `kwaivgi/kling-v3-video` (current) | yes | `prompt`, `start_image` (optional), `end_image`, `aspect_ratio` (16:9, 9:16, 1:1), `duration` int 3–15, `mode`, `generate_audio`, `negative_prompt` | URL string |
| `minimax/video-01` | yes | `prompt`, **`first_frame_image`**, `prompt_optimizer`, `subject_reference`. **No duration or aspect** (6 s) | URL string |
| `minimax/hailuo-2.3` (current) | yes | `prompt`, `first_frame_image`, `duration` int 6/10, `resolution` 768p/1080p, `prompt_optimizer` | URL string |
| `nightmareai/real-esrgan` | yes (in the official collection) | `image`, `scale`, `face_enhance` | URL string |
| `851-labs/background-remover` | **no** | `image`, `threshold`, `background_type`, `format` | URL string |
| `bria/remove-background` (replacement) | yes | `image` or `image_url`, `preserve_alpha` | URL string |

---

## 2. Discrepancies in providers.py

Each item shows the current code, what is wrong, and the fix. The numbers match the summary table.

### D1. OpenAI image/edit/inpaint: `gpt-image-1` is shut down

```python
"openai": {... "image": ["gpt-image-1"], "edit": ["gpt-image-1"], "inpaint": ["gpt-image-1"], ...}
```
`gpt-image-1` was shut down on 2026-10-23, so every OpenAI image call now fails. The fix:
```python
"image": ["gpt-image-2.5-flare", "gpt-image-2.5-sunburst", "gpt-image-2"],
"edit": ["gpt-image-2.5-sunburst", "gpt-image-2.5-flare", "gpt-image-2"],
"inpaint": ["gpt-image-2.5-sunburst", "gpt-image-2"],
```
Optional: newer GPT Image models accept exact sizes, so `_size` can follow the aspect ratio instead of snapping to three sizes:
```python
@staticmethod
def _size(aspect):
    exact = {"16:9": "1536x864", "9:16": "864x1536", "1:1": "1024x1024", "4:5": "1024x1280", "3:4": "960x1280",
             "4:3": "1280x960", "21:9": "1680x720", "2:3": "1024x1536", "3:2": "1536x1024"}
    return exact.get(aspect, "auto")
```
(All edges are multiples of 16 and every size is at least 655,360 px.)

### D2. OpenAI video: the Sora/Videos API no longer exists

```python
"openai": {..., "video": ["sora-2", "sora-2-pro"], ...}
PREFER = {..., "video": ["fal", "gemini", "openai", "replicate"]}
```
OpenAI shut down the Videos API and every `sora-2*` id on 2026-09-24 and named no replacement.
`OpenAI.video` always fails. The fix: drop the capability so the router never chooses it.
```python
"openai": {"llm": [...], "vision": [...], "image": [...], "edit": [...], "inpaint": [...], "tts": ["gpt-4o-mini-tts"]},
PREFER = {..., "video": ["fal", "gemini", "replicate"]}
```
Then delete `OpenAI.video`. Without it, `_call` falls back to the mock, but the route never reaches it anyway.

### D3. Gemini video: Veo and `predictLongRunning` are gone

```python
"gemini": {..., "video": ["veo-3.0-generate-001", "veo-3.0-fast-generate-001"]}
op = http("POST", f"{Gemini.B}/models/{model}:predictLongRunning?key=...", None, {"instances": [inst], "parameters": {...}})
```
`veo-3.0-*` were shut down on 2026-06-30 and `veo-3.1-*-preview` on 2026-10-22. Google's replacement is
`gemini-omni-1.1-flash` on the Interactions API, which has a different request and response shape. The fix:
```python
"gemini": {..., "video": ["gemini-omni-1.1-flash"]},

@staticmethod
def video(r, model, prompt, image, aspect, duration, end_image, audio):
    key = r.s.key("gemini"); h = {"x-goog-api-key": key}
    parts = []
    for p in [x for x in (image, end_image) if x]:      # two images give first/last-frame interpolation
        parts.append({"type": "image", "data": base64.b64encode(p.read_bytes()).decode(),
                      "mime_type": mimetypes.guess_type(p.name)[0] or "image/png"})
    text = prompt + (f" The clip is about {int(duration)} seconds long." if duration else "")
    if not audio: text += " No dialogue, no music."      # Omni always generates audio; steer it with the prompt
    if image: text = ("<FIRST_FRAME> <LAST_FRAME> " if end_image else "<FIRST_FRAME> ") + text
    parts.append({"type": "text", "text": text})
    body = {"model": model, "input": parts, "background": True,
            "response_format": {"type": "video", "aspect_ratio": "9:16" if aspect in ("9:16", "4:5", "3:4", "2:3") else "16:9",
                                "delivery": "uri"}}
    it = http("POST", f"{Gemini.B}/interactions", h, body)
    for _ in range(900):
        if it.get("status") in ("completed", "failed", "cancelled", "incomplete"):
            break
        time.sleep(5); it = http("GET", f"{Gemini.B}/interactions/{it['id']}", h)
    if it.get("status") != "completed":
        raise ProviderError(f"gemini omni: {it.get('status')} {json.dumps(it)[:300]}")
    for step in it.get("steps", []):
        if step.get("type") != "model_output": continue
        for c in step.get("content", []):
            if c.get("type") == "video":
                if c.get("data"): return [r.out.save(base64.b64decode(c["data"]), ".mp4")]
                if c.get("uri"):  return [r.out.fetch(c["uri"], ".mp4", headers=h)]
    raise ProviderError("gemini omni returned no video")
```
(With `delivery: "uri"` the docs poll `GET /v1beta/files/{id}` until `state == "ACTIVE"` before downloading.
If the download returns 404 or empty, add that wait step.)

### D4. fal Veo: `duration` format is wrong

```python
args = {..., "duration": str(int(duration)) if "veo" not in model else f"{int(duration)}s"}
```
Veo 3 and 3.1 only accept `"4s"`, `"6s"` or `"8s"`. The router's default of 5 produces `"5s"`, which gets a 422.
D4–D6 share one root cause: each fal family has its own duration enum. Replace the whole
`Fal.video` with per-family rules (this fix also covers D5, D6, D11 and D12):
```python
_FAL_DUR = {  # family substring -> allowed seconds and how to format them
    "veo3":     ([4, 6, 8], lambda s: f"{s}s"),
    "kling-video/v2": ([5, 10], str),
    "kling-video/v3": (list(range(3, 16)), str),
    "kling-video/o3": (list(range(3, 16)), str),
    "seedance/v1":    (list(range(2, 13)), str),
    "seedance-2":     (list(range(4, 16)), str),
    "hailuo":   ([6, 10], str),
}
_FAL_NO_ASPECT = ("hailuo",)                     # Hailuo takes no aspect_ratio
_FAL_I2V_NO_ASPECT = ("kling-video/",)           # Kling i2v follows the image

@staticmethod
def video(r, model, prompt, image, aspect, duration, end_image, audio):
    m = model.rstrip("/")
    allowed, fmt = next((v for k, v in _FAL_DUR.items() if k in m), ([5], str))
    args = {"prompt": prompt, "duration": fmt(min(allowed, key=lambda s: abs(s - duration)))}
    if not any(k in m for k in _FAL_NO_ASPECT) and not (image and any(k in m for k in _FAL_I2V_NO_ASPECT)):
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
            if end_image and not any(k in m for k in ("veo3", "kling-video/v2")):   # seedance, hailuo, kling v3
                args["end_image_url"] = data_uri(end_image)
    elif "veo3" not in m:
        m += "/text-to-video"
    return Fal._files(r, Fal._run(r, m, args), ".mp4", kinds=("video",))
```

### D5. fal Hailuo-02: wrong duration, and it takes no aspect_ratio

Current code: the same `duration` line as D4, plus `"aspect_ratio": aspect`.
Hailuo-02 Standard only accepts `"6"` or `"10"` (default 5 gives a 422) and has no `aspect_ratio` field.
The `_FAL_DUR["hailuo"]` and `_FAL_NO_ASPECT` rules in the D4 code fix both.

### D6. fal Kling 2.1 master: wrong durations, and an end frame it does not support

```python
"duration": str(int(duration))
if end_image: args["tail_image_url"] = args["end_image_url"] = data_uri(end_image)
```
Kling 2.1 master only accepts `"5"` or `"10"`. Its image-to-video endpoint has no `aspect_ratio` and
no end-frame field (`tail_image_url` is not in the schema), so the end image is silently dropped.
The D4 code fixes both. If end frames matter, use the v3 default (D11).

### D7. fal faceswap: the model is gone

```python
"faceswap": ["fal-ai/face-swap"],
return Fal._files(r, Fal._run(r, model, {"base_image_url": data_uri(target), "swap_image_url": data_uri(face)}), kinds=("image",))
```
`fal-ai/face-swap` returns 404. The replacement on fal is `easel-ai/advanced-face-swap`, which has a different schema with three required fields. The fix:
```python
"faceswap": ["easel-ai/advanced-face-swap"],

@staticmethod
def faceswap(r, model, target, face, gender="non-binary", keep_hair="target"):
    args = {"face_image_0": data_uri(face), "gender_0": gender, "target_image": data_uri(target),
            "workflow_type": "target_hair" if keep_hair == "target" else "user_hair", "upscale": True}
    return Fal._files(r, Fal._run(r, model, args), kinds=("image",))
```
(Optionally pass `gender` and `keep_hair` through `Router.faceswap(**kw)`.)

### D8. Replicate bg_remove: the model is not official

```python
"bg_remove": ["851-labs/background-remover"]
p = http("POST", f"https://api.replicate.com/v1/models/{model}/predictions", h, {"input": inp})
```
`851-labs/background-remover` is not in Replicate's official collection. The `/v1/models/{owner}/{name}/predictions`
endpoint only runs official models; community models need `POST /v1/predictions` with a `version`. The fix:
switch to an official model.
```python
"bg_remove": ["bria/remove-background", "recraft-ai/recraft-remove-background"],

@staticmethod
def bg_remove(r, model, image):
    return Replicate._run(r, model, {"image": data_uri(image), "preserve_alpha": True} if model.startswith("bria/") else {"image": data_uri(image)})
```
To keep supporting community models, accept an `owner/name:version` id:
```python
url, body = (("https://api.replicate.com/v1/predictions", {"version": model.split(":", 1)[1], "input": inp}) if ":" in model
             else (f"https://api.replicate.com/v1/models/{model}/predictions", {"input": inp}))
p = http("POST", url, h, body)
```

### D9. Replicate video, `kwaivgi/kling-v2.1`: the start image is required and the aspect field does not exist

```python
"video": ["kwaivgi/kling-v2.1", "minimax/video-01"]
return Replicate._run(r, model, {"prompt": prompt, "aspect_ratio": aspect, "duration": int(duration), **({"start_image": data_uri(image)} if image else {})})
```
`kling-v2.1` is image-to-video only, so a text-only prompt fails. It has no `aspect_ratio` and only accepts duration 5 or 10.
The fix: default to `kwaivgi/kling-v3-video` (text or image to video, 3–15 s, audio, end frame) and build
the inputs per model. This also covers D10:
```python
"video": ["kwaivgi/kling-v3-video", "minimax/hailuo-2.3", "kwaivgi/kling-v2.1", "minimax/video-01"],

@staticmethod
def video(r, model, prompt, image, aspect, duration, end_image, audio):
    if model.startswith("minimax/"):
        inp = {"prompt": prompt, **({"first_frame_image": data_uri(image)} if image else {})}
        if "hailuo" in model: inp["duration"] = 10 if duration > 8 else 6
    else:  # kwaivgi/kling-*
        v3 = "v3" in model
        inp = {"prompt": prompt, "duration": max(3, min(15, int(duration))) if v3 else (10 if duration > 7 else 5)}
        if image: inp["start_image"] = data_uri(image)
        elif not v3: raise ProviderError("kling-v2.1 on Replicate needs a start image")
        if end_image and v3: inp["end_image"] = data_uri(end_image)
        if v3:
            inp["generate_audio"] = bool(audio)
            if not image: inp["aspect_ratio"] = aspect if aspect in ("16:9", "9:16", "1:1") else "16:9"
    return Replicate._run(r, model, inp)
```

### D10. Replicate `minimax/video-01`: wrong image field name, and fields that do not exist

The current code is the same as D9: it sends `start_image`, `aspect_ratio` and `duration`.
`minimax/video-01` takes `first_frame_image` and has no duration or aspect fields, so the image is
silently ignored. The D9 code fixes this, and `minimax/hailuo-2.3` is the newer official model.

### D11. fal video defaults are a generation behind (not broken)

```python
"video": ["fal-ai/kling-video/v2.1/master", "fal-ai/veo3", "fal-ai/bytedance/seedance/v1/pro", "fal-ai/minimax/hailuo-02/standard"],
```
These still work once D4–D6 are fixed. The current families are listed below, and all of them work with the D4 code:
```python
"video": ["fal-ai/kling-video/v3/pro", "fal-ai/veo3.1", "fal-ai/veo3.1/fast", "bytedance/seedance-2.0",
          "fal-ai/bytedance/seedance/v1/pro", "fal-ai/minimax/hailuo-02/standard"],
```
Note that Seedance 2.0 has **no `fal-ai/` prefix** (`bytedance/seedance-2.0/{text,image}-to-video`), and Kling v3
image-to-video uses **`start_image_url`**, not `image_url`.

### D12. fal video: `generate_audio` is only sent for Veo

```python
if "veo" in model: args["generate_audio"] = bool(audio)
```
Kling v3, Kling O3 and Seedance 2.0 default `generate_audio` to `true`. Not sending it means you pay
for, or get, audio the user did not ask for. The D4 code sends it for every family that has the field.

### D13. fal image: fields one model rejects are mixed with fields the next model ignores

```python
args = {"prompt": prompt, "num_images": n, "image_size": {"width": w, "height": h}, "aspect_ratio": aspect}
```
- `flux/dev` and `seedream/v4` take `image_size`; `flux-pro/v1.1-ultra` and `nano-banana` take `aspect_ratio`.
  Sending both mostly works because fal ignores unknown fields, but Ultra's documented enum has no `4:5`.
- `negative_prompt` is not a field on Flux or Nano Banana, so the user's negative prompt is silently ignored there.
- `num_images` caps are 1–4 (Flux, Nano Banana) and 1–6 (Seedream).

The fix:
```python
@staticmethod
def image(r, model, prompt, aspect, n, negative, seed):
    w, h = ASPECTS.get(aspect, (1024, 1024))
    args = {"prompt": prompt, "num_images": max(1, min(4, n))}
    if any(k in model for k in ("flux/dev", "flux/schnell", "seedream", "flux-2")):
        args["image_size"] = {"width": w, "height": h}
    else:
        args["aspect_ratio"] = aspect if aspect in ("21:9", "16:9", "4:3", "3:2", "1:1", "2:3", "3:4", "9:16") or "nano-banana" in model else "1:1"
    if negative:
        if "imagen" in model: args["negative_prompt"] = negative
        else: args["prompt"] += f"\nAvoid: {negative}"
    if seed is not None: args["seed"] = int(seed)
    return Fal._files(r, Fal._run(r, model, args), kinds=("images", "image"))
```
Also replace `fal-ai/imagen4/preview`: its schema page returns 404, and Google retired Imagen 4 on 2026-08-17. Suggested list:
```python
"image": ["fal-ai/flux/dev", "fal-ai/nano-banana-2", "fal-ai/flux-pro/v1.1-ultra", "fal-ai/flux-2-pro",
          "fal-ai/bytedance/seedream/v4.5/text-to-image"],
"edit": ["fal-ai/nano-banana-2/edit", "fal-ai/bytedance/seedream/v4/edit", "fal-ai/flux-pro/kontext"],
```
(The Seedream v4.5 and Flux-2 ids appear on fal's model and explore pages; their schemas were not read in this pass.)

### D14. fal music/sfx: `stable-audio` caps at 47 s

```python
{"prompt": prompt, "seconds_total": int(duration), "duration": int(duration)}
```
`seconds_total` must be 0–47, so a longer track is a 422. `lyria2` has no duration field (it always makes
about 30 s). The fix:
```python
args = {"prompt": prompt}
if "stable-audio" in model: args["seconds_total"] = max(1, min(47, int(duration)))
```

### D15. fal queue: the failure check can never fire

```python
if st.get("status") in ("FAILED", "ERROR"):
```
fal has no FAILED or ERROR status. A failed request is `COMPLETED` with an `error` field. It still errors
today, because the follow-up GET on `response_url` returns a 4xx, but the provider's message is lost. The fix:
```python
if st.get("status") == "COMPLETED":
    if st.get("error"): raise ProviderError(f"fal {model}: {st.get('error_type')}: {st['error']}")
    return http("GET", resp_url, h)
```

### D16. OpenAI llm: the defaults are being retired

```python
"llm": ["gpt-5-mini", "gpt-5", "gpt-4.1"], "vision": ["gpt-5-mini", "gpt-4.1"]
```
`gpt-5` and `gpt-5-mini` shut down on 2026-12-11, and `gpt-4.1` on 2027-01-14. The current models also work on
`/v1/chat/completions` (per the model pages), so the call needs no other change. The fix:
```python
"llm": ["gpt-6-luna", "gpt-6.1-terra", "gpt-6.1-sol"], "vision": ["gpt-6.1-terra", "gpt-6-luna"],
```

### D17. OpenAI inpaint: the mask can mismatch the image format

```python
m = ImageOps.invert(Image.open(mask).convert("L").resize(Image.open(image).size))
rgba = Image.open(image).convert("RGBA"); rgba.putalpha(m)
...
return OpenAI.edit(r, model, prompt, [image], "1:1", 1, mask=mp)
```
The alpha logic is correct: white-on-black is inverted, so the area to paint becomes alpha 0. But OpenAI
requires the mask and the image to have **the same format and size**. When the source is a JPEG, the request
pairs a JPEG image with a PNG mask and can be rejected. `"1:1"` also forces a square output for any input. The fix:
```python
src = r.out.path(".png"); Image.open(image).convert("RGB").save(src)
...
return OpenAI.edit(r, model, prompt, [src], "auto", 1, mask=mp)
```
and let `_size("auto")` return `"auto"`. The D1 `_size` already does that.

### D18. OpenAI tts: the model is deprecated and the voice default is weak

```python
{"model": model, "input": text, "voice": voice or "alloy", "speed": speed}
```
This still works, but every `/audio/speech` model shuts down on 2027-01-06, and the replacement
(`gpt-realtime-2.1-mini`) only runs on the Realtime API. OpenAI now recommends the `marin` or `cedar` voice. The fix for now:
```python
"voice": voice if voice in {"alloy","ash","ballad","coral","echo","fable","nova","onyx","sage","shimmer","verse","marin","cedar"} else "marin"
```
Also put ElevenLabs and Gemini ahead of OpenAI in `PREFER["tts"]` (ElevenLabs is already first). Plan to remove OpenAI
TTS before 2027-01-06, or move it to the Realtime API.

### D19. Gemini llm/vision: the 2.5 models are restricted to existing users, and the system prompt is not a system instruction

```python
"gemini": {"llm": ["gemini-2.5-flash", "gemini-2.5-pro"], "vision": ["gemini-2.5-flash"], ...}
parts = ([{"text": system}] if system else []) + [{"text": prompt}] + ...
```
Google limits Gemini 2.5 access to users who already used it, so a new API key can be refused. The system
prompt is sent as an ordinary user text part. The fix:
```python
"llm": ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-3.1-pro-preview"], "vision": ["gemini-3.8-flash"],

@staticmethod
def _gen(r, model, parts, cfg=None, system=""):
    body = {"contents": [{"role": "user", "parts": parts}], **({"generationConfig": cfg} if cfg else {})}
    if system: body["systemInstruction"] = {"parts": [{"text": system}]}
    return http("POST", f"{Gemini.B}/models/{model}:generateContent", {"x-goog-api-key": r.s.key("gemini")}, body)

# in llm():
parts = [{"text": prompt}] + [Gemini._inline(p) for p in images]
res = Gemini._gen(r, model, parts, {"responseMimeType": "application/json"} if json_mode else None, system)
```

### D20. Gemini image/edit: the model is old and the aspect ratio only goes into the prompt

```python
"image": ["gemini-2.5-flash-image"], "edit": ["gemini-2.5-flash-image"]
res = Gemini._gen(r, model, [{"text": f"{prompt}\nAspect ratio {aspect}."}] + ..., {"responseModalities": ["IMAGE", "TEXT"]})
```
`gemini-2.5-flash-image` shuts down on 2027-03-15. The API has a real aspect-ratio field
(`generationConfig.imageConfig.aspectRatio`), so the text hint is unreliable. The rest is correct: reading
`inlineData` or `inline_data` and `responseModalities` both match the docs. The fix:
```python
"image": ["gemini-3.1-flash-image", "gemini-3-pro-image", "gemini-2.5-flash-image"],
"edit": ["gemini-3.1-flash-image", "gemini-3-pro-image"],

cfg = {"responseModalities": ["TEXT", "IMAGE"],
       "imageConfig": {"aspectRatio": aspect if aspect in ("1:1","2:3","3:2","3:4","4:3","4:5","5:4","9:16","16:9","21:9") else "1:1"}}
res = Gemini._gen(r, model, [{"text": prompt}] + [Gemini._inline(p) for p in refs], cfg)
```
(`gemini-nano-banana-2.1` is newer, but the docs only show it on `/v1beta/interactions`. Keep generateContent
with `gemini-3.1-flash-image` unless you move image generation to Interactions.)

### D21. Gemini has no TTS adapter

`MODELS["gemini"]` has no `"tts"` entry and `Gemini` has no `tts` method. The capability is available
and cheap. On the question of `gemini-3.1-flash-tts-preview`: **it exists, but shuts down 2026-11-17**. Use
`gemini-3.8-flash-tts` or `gemini-3.8-flash-lite-tts`. The fix:
```python
"gemini": {..., "tts": ["gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts"]},

@staticmethod
def tts(r, model, text, voice, speed):
    voices = {"Zephyr","Puck","Charon","Kore","Fenrir","Leda","Orus","Aoede","Callirrhoe","Autonoe","Enceladus","Iapetus",
              "Umbriel","Algieba","Despina","Erinome","Algenib","Rasalgethi","Laomedeia","Achernar","Alnilam","Schedar",
              "Gacrux","Pulcherrima","Achird","Zubenelgenubi","Vindemiatrix","Sadachbia","Sadaltager","Sulafat"}
    style = "speaking slowly" if speed < 0.9 else "speaking quickly" if speed > 1.15 else "natural, clear"
    body = {"model": model,
            "input": [{"type": "user_input", "content": [{"type": "text", "text": text,
                       "annotations": [{"type": "speech_metadata", "style": style}]}]}],
            "response_format": {"type": "audio"},
            "generation_config": {"speech_config": [{"voice": voice if (voice in voices or voice.startswith("voice_")) else "Kore"}]}}
    it = http("POST", f"{Gemini.B}/interactions", {"x-goog-api-key": r.s.key("gemini")}, body)
    for step in it.get("steps", []):
        for c in step.get("content", []):
            if c.get("type") == "audio" and c.get("data"):
                return [r.out.save(base64.b64decode(c["data"]), ".wav")]
    raise ProviderError("gemini tts returned no audio")
```

### D22. ElevenLabs TTS: hard-coded Rachel, a deprecated model, and speed out of range

```python
"elevenlabs": {"tts": ["eleven_multilingual_v2", "eleven_turbo_v2_5"], ...}
vid = voice if voice and len(voice) > 15 else "21m00Tcm4TlvDq8ikWAM"  # Rachel
{"text": text, "model_id": model, "voice_settings": {"speed": speed}}
```
Three problems:
- ElevenLabs says all default voices, Rachel included, expire on 2026-12-31. Some accounts already lost them.
- `eleven_turbo_v2_5` is deprecated in favour of `eleven_flash_v2_5`.
- `voice_settings.speed` must be 0.7–1.2.

The fix:
```python
"elevenlabs": {"tts": ["eleven_multilingual_v2", "eleven_v3", "eleven_flash_v2_5"], "music": ["music_v2_5", "music_v2", "music_v1"],
               "sfx": ["eleven_text_to_sound_v2"]},

@staticmethod
def _voice(r, voice):
    if voice and len(voice) > 15: return voice
    res = http("GET", f"{ElevenLabs.B.replace('/v1', '/v2')}/voices?page_size=100", ElevenLabs._h(r))
    vs = res.get("voices", [])
    hit = next((v for v in vs if voice and v.get("name", "").lower() == voice.lower()), None) or (vs[0] if vs else None)
    if not hit: raise ProviderError("no ElevenLabs voices on this account; add one or set a voice_id")
    return hit["voice_id"]

@staticmethod
def tts(r, model, text, voice, speed):
    vid = ElevenLabs._voice(r, voice)
    return [r.out.save(http("POST", f"{ElevenLabs.B}/text-to-speech/{vid}", ElevenLabs._h(r),
            {"text": text, "model_id": model, "voice_settings": {"speed": max(0.7, min(1.2, speed))}}, raw=True), ".mp3")]
```
The same Rachel problem affects `Fal.tts` (`voice or "Rachel"`). After 2026-12-31 pass a voice the account
actually has, or treat a missing voice as "use the model default".

### D23. ElevenLabs music: `model_id` is never sent and the length is unclamped

```python
{"prompt": prompt, "music_length_ms": int(duration * 1000)}
```
The `model` argument is ignored, so every request runs on `music_v1`, which ElevenLabs calls "outclassed".
`music_length_ms` must be 3000–600000. The fix:
```python
{"prompt": prompt, "model_id": model, "music_length_ms": max(3000, min(600000, int(duration * 1000)))}
```

### D24. ElevenLabs sound-generation: the cap is out of date and there is no lower bound

```python
{"text": prompt, "duration_seconds": min(22, duration)}
```
The limit is 0.5–30 s, so 22 is stale and anything below 0.5 gets a 422. The `model` argument is also unused. The fix:
```python
{"text": prompt, "model_id": model, "duration_seconds": max(0.5, min(30, float(duration)))}
```

### D25. Replicate: data URIs are too large for images and video frames

```python
{"image": data_uri(image)} / {"start_image": data_uri(image)}
```
Replicate recommends data URIs only for files under 1 MB. Larger photos are slow or rejected. fal
accepts data URIs, but recommends its CDN for big files: `video_url` for upscaling and lipsync can be many MB. The fix for Replicate
is to upload through the Files API (`POST https://api.replicate.com/v1/files`, multipart `content`) and pass `urls.get`:
```python
def _upload(r, p: Path) -> str:
    body, ct = multipart({}, {"content": [p]})
    f = http("POST", "https://api.replicate.com/v1/files", {"Authorization": f"Bearer {r.s.key('replicate')}", "Content-Type": ct}, body)
    return f["urls"]["get"]

def _file(r, p: Path) -> str:
    return data_uri(p) if p.stat().st_size < 900_000 else _upload(r, p)
```
(The Files endpoint was not re-read in this pass; check it against replicate.com/docs/reference/http before you rely on it.)

### D26. Replicate `flux-1.1-pro` ignores `num_outputs`

```python
{"prompt": prompt, "aspect_ratio": aspect, "num_outputs": n, ...}
```
Only `flux-schnell` (and other `-schnell`/`-dev` variants) accept `num_outputs`. `flux-1.1-pro` always
returns one image, so `n > 1` silently gives 1. The fix:
```python
if "schnell" in model or "flux-dev" in model:
    return Replicate._run(r, model, {..., "num_outputs": min(4, n)})
return [p for _ in range(n) for p in Replicate._run(r, model, {"prompt": prompt, "aspect_ratio": aspect, **({"seed": int(seed)} if seed is not None else {})})]
```

---

## 3. What was checked and is correct

- **fal**: the submit URL, the `Key` auth header, using the returned `status_url` and `response_url`, data-URI inputs,
  the `/image-to-video` and `/text-to-video` suffixes for Kling, Seedance and Hailuo, and the bare text endpoint for Veo.
  Output paths match: `images[].url`, `image.url`, `video.url`, `audio.url` and `audio_file.url`. Field names also match
  for nano-banana/edit and seedream/edit (`image_urls`), kontext (`image_url`), kolors try-on, flux fill, birefnet,
  clarity and esrgan (`upscale_factor`/`scale`), video-upscaler and sync-lipsync.
- **OpenAI**: the Bearer auth header, `/chat/completions` with `response_format: json_object` and `image_url` parts, `/images/generations`
  returning `b64_json`, `/images/edits` with repeated `image[]` parts and an alpha-channel `mask`, the inverted mask logic,
  and `/audio/speech` returning mp3 bytes.
- **Gemini**: the `generateContent` path, the `?key=` auth (still accepted), `inline_data` in requests,
  reading both `inlineData` and `inline_data`, `responseModalities`, and `responseMimeType` for JSON.
- **ElevenLabs**: the paths `/v1/text-to-speech/{voice_id}`, `/v1/music` and `/v1/sound-generation`, the `xi-api-key`
  header, and mp3 binary responses by default.
- **Replicate**: `/v1/models/{owner}/{name}/predictions` and `Prefer: wait` for official models, and polling `urls.get`
  until succeeded, failed or canceled. `flux-schnell`, `flux-1.1-pro`, `kling-v2.1`, `minimax/video-01` and
  `nightmareai/real-esrgan` are official. `real-esrgan` inputs (`image`, `scale`) are correct.
