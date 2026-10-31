# Tool research: what "professional" means for each Spark Station tool

Written 2026-10-28 for `server/studio/tools.py`. Each section has three parts: the key facts and numbers, an **Apply to our tools** list that names the function to change, and the source links. Product context comes from `docs/sparkstation-spec.md`.

How the sources were rated:
- **[Official]** is vendor documentation or a guild or standards body.
- **[Industry]** is a trade publication or a working practitioner.
- **[3P]** is a third-party blog or reseller. Use these for direction only, and check the numbers before you hard-code them.
- Prices change monthly. Every price below is dated and should live in a config table, not in code.

> **Breaking change found during research:** OpenAI shut down the Sora 2 models and the Videos API on **24 Sep 2026**, and there is no one-to-one replacement API (costgoat.com, quoting OpenAI). The spec's model wall still lists "OpenAI Sora". Remove Sora from `model_field("video")` routing and from the `compare` options in `t_video`, or keep it only as a historical rate. The Sora 2 *prompting* guidance is still useful because it is model-agnostic.

---

## 0. Cross-cutting fixes, since several tools share them

| Problem in code | Why it matters | Fix |
|---|---|---|
| `camera_prompt()` adds the rig as a tail (`". shot on …; camera movement: a, then b"`) | Veo's formula puts **cinematography first**. Sora and Seedance both say to use **one camera move per shot**. Chained moves get dropped or garbled. | Lead with shot size, angle and move. Allow one move per ≤5 s segment, and use timestamped segments for more. |
| `t_video` adds `f". {resolution}."` to the prompt | Sora guide: resolution, duration and character references are **API parameters only**, and prose cannot change them | Remove it. Pass resolution as a parameter. |
| `t_music` adds `" Seed 123."` to the prompt text | A seed in prose does nothing | Pass the seed as an API parameter, or drop it. |
| "Strength 60%", "intensity 60%" and hex colours in `t_relight`, `t_reimagine` and `t_skin` | Image and video models do not read percentages or hex codes reliably | Map each slider to words ("subtle", "moderate", "strong"), or to a real API parameter where one exists (FLUX/Seedream `strength`, gpt-image `input_fidelity`) |
| Generic quality tokens in `PROMPT_TEMPLATES` ("4k", "cinematic colour grade", "high detail") | The Seedance methodology lists `8k, masterpiece, highly detailed` and a bare `cinematic` as junk. OpenAI says camera and lighting terms steer realism "more reliably than generic 8K/ultra-detailed". | Replace them with specific lens, film stock and light terms |
| `qc_score()` judges a video from **one middle frame** | It cannot see temporal consistency, morphing or identity drift | Sample 8–16 frames, add metric checks and use rubric anchors (§12) |
| "No X" phrasing in negatives | Veo: write "a desolate landscape with no buildings" in the positive prompt, or list the nouns ("wall, frame") in the negative field. Avoid "no"/"don't". | Turn the `negative` field into a noun list and keep "no …" out of positive prompts |

---

## 1. Video prompting (Veo 3.1, Kling, Seedance, Sora 2)

### Key facts

**Veo 3.1 (Google) [Official]**
- Five-part formula: **[Cinematography] + [Subject] + [Action] + [Context] + [Style & Ambiance]**. The guide calls cinematography "the most powerful tool for conveying tone and emotion."
- Audio has its own syntax. Put dialogue in quotes (`A woman says, "We have to leave now."`), and use `SFX: thunder cracks in the distance` and `Ambient noise: the quiet hum of a starship bridge`. Google recommends describing audio in **separate sentences**.
- Specs (Gemini API): 720p/1080p/4K. Durations are **4, 6 or 8 s**, and must be **8 s** for 1080p, 4K or reference images. Aspect is 16:9 or 9:16. Up to **3 reference images** ("ingredients": `reference_type="asset"`) of one person, character or product. First and last frame: pass `image` plus `lastFrame`. Extension adds **7 s** per call, up to 20 times, to a total of 148 s, and continues from the final second (24 frames). Voice cannot be extended unless it is present in the last second.
- **Timestamp prompting** gives multi-shot pacing inside one 8 s clip: `[00:00-00:02] Medium shot from behind… [00:02-00:04] Reverse shot… SFX: …`.
- First/last-frame workflow: make both frames with Gemini 2.5 Flash Image, then prompt the transition ("The camera performs a smooth 180-degree arc shot…").
- Camera vocabulary from Vertex: static, pan, tilt, dolly in/out, truck L/R, **pedestal** up/down, zoom (lens, not camera), crane, aerial/drone, handheld, whip pan, arc. Lens effects: wide, telephoto, shallow/deep DOF, lens flare, **rack focus**, fisheye, dolly zoom. Editing terms are understood: "match cut", "jump cut", "montage", "split diopter".

**Sora 2 (OpenAI; API retired, guidance still applies) [Official]**
- "Brief it like a cinematographer who has never seen your storyboard." Each shot has one camera setup, one subject action and one lighting recipe.
- Describe motion **in beats and counts**: "takes four steps to the window, pauses, and pulls the curtain in the final second."
- Name **3–5 palette anchors** ("amber, cream, walnut brown") to keep colour stable across clips. Reuse the same character phrasing across shots.
- Shorter clips follow instructions better. Two 4 s clips stitched together often beat one 8 s clip.
- Dialogue goes in a separate `Dialogue:` block with labelled speakers. A 4 s shot fits 1–2 short exchanges and an 8 s shot fits a few more.
- Image input is the first-frame anchor and must match the output resolution. To iterate, change **one thing at a time** ("same shot, switch to 85 mm").
- "Ultra-detailed" format for hero shots: Format & Look → Lenses & Filtration → Grade/Palette → Lighting & Atmosphere → Location & Framing → Wardrobe/Props → Sound → timed shot list → Camera notes → Finishing.

**Kling [Official formula + 3P for 3.0]**
- Kling's own formula: **Subject (description) + Subject Movement + Scene (description) + (Camera language + Lighting + Atmosphere)**.
- Kling 3.0 / 3.0 Omni [3P]: clips of 3–15 s, up to 6 labelled shots ("Shot 1 (5s): …"), Elements referenced with `@Name`, and native multilingual audio with lip-sync. Practitioners suggest 80–150 words. The "motion intensity 0–3" claim is unverified, so do not ship it.
- Elements work best when built from **four angles**: front, ¾ left, ¾ right and back (§3).

**Seedance 2.0 (ByteDance) [3P distillation of the official BytePlus/Volcano guides]**
- Order: subject + action → scene → light/colour → camera → style → quality → constraints. "The first 10–15 tokens carry the most attention weight."
- The time-axis storyboard is the strongest technique. **Three segments are most stable** (hook 0–3 s / body / CTA). Five or more segments collapse.
- Line 1 gives orientation and ratio. Line 2 states the `Overall audio atmosphere:`. Each scene needs **colour + material + light**. Use **one camera move per segment**. Name a camera body at the end. Use **3–5 specific negatives**, because more makes the output stiff.
- **Image-to-video: never re-describe the subject.** Write only motion, camera, audio and style. Re-describing causes identity drift.
- In reference mode, **bind `@image1` again in every time segment**. Use letters (A/B/C) for multiple characters. Sweet spot is 4–5 total assets, against a maximum of 9 images, 3 videos and 3 audio files.
- On-screen text of 4 words or fewer renders about 90% of the time and 5–8 words about 50%. Add longer text in post.
- Durations 4–15 s, with **5 and 10 s the most stable**. First/last-frame mode (`role_mode=frame`) cannot use reference video or audio.

### Apply to our tools
1. **`camera_prompt()` → `direct_shot(rig, model)`**. Emit a *leading* cinematography clause and keep at most one move:
   ```
   {shot_size}, {angle}, {single_move} on a {focal}mm {lens_character} lens, {aperture_feel}.
   ```
   If the user picked several `movement` values, split them across timestamped segments, about 2–4 s each. Never chain them with "then" inside one segment.
2. **`t_video`**: build the prompt from a per-model template. Field order is cinematography, subject, action in beats, context (colour + material + light), style, then the audio block.
   ```
   [VEO]   {cinematography}. {subject}, {action beats}. {context}. {style}; palette: {3-5 colours}.
           Dialogue: {SPEAKER} says, "{line}". SFX: {sfx}. Ambient noise: {ambience}.
   [KLING] {subject + description}, {movement}. {scene}. {camera language}, {lighting}, {atmosphere}.
           Shot 1 ({d}s): … Shot 2 ({d}s): …          (≤6 shots; @Element names for refs)
   [SEEDANCE] {Vertical|Horizontal} video {ratio}. Overall audio atmosphere: {…}.
           [0-3s] {shot}. {@imageA verbs}. {colour+material+light}. {one move}. Sound: {…}
           [3-7s] Cut to … [7-10s] …  Shot on {camera}. {style}. {3-5 negatives}.
   ```
   - When `image` (I2V) is set, **remove the cast description** that `ctx.cast()` injects for Seedance and Kling, and send motion, camera and audio only.
   - Snap `duration` to what each model accepts: Veo {4, 6, 8}, forced to 8 when refs are present or resolution is 1080p+; Seedance 5 or 10 preferred; Kling 5/10/15. Show this in the UI instead of a free 2–15 slider.
   - When `characters` have refs and the model supports native references (Veo ingredients ≤3, Kling Elements, Seedance `@image`), **pass the refs natively**. Only fall back to "generate a first frame" when the model has no reference support. That fallback is today's only path.
   - `ref_video`: describe **3–5 frames** and say what transfers (camera motion, edit pacing, grade) and what does not (identity, text, logo).
2a. **`improve_prompt()`**: stop guessing gaps with keywords. Ask the LLM to return structured slots: `{cinematography, subject, action_beats[], context{colour,material,light}, style, palette[3-5], audio{dialogue[],sfx,ambient}, negatives[≤5]}`. Render the slots with the template above. Reject banned tokens.
3. **`PROMPT_TEMPLATES` / `t_prompt_studio`**: rewrite the eight templates in the five-part order and remove "4k" and the bare "cinematic". For example, "Action beat" becomes `Low-angle tracking shot on a 24mm lens, {subject} {action in 3 beats}, {location: colour+material+light}, handheld energy, motion blur on fast limbs. SFX: {…}`.
4. **`MOVES`** list: add `Pedestal Up/Down`, `Rack Focus`, `Arc 180°` and `Locked-off`. Show "Dolly Zoom" with a warning, because it is "not officially supported" by Veo.

### Sources
- [Official] Google Cloud, *Ultimate prompting guide for Veo 3.1* — https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1
- [Official] Vertex/Agent Platform video prompt guide — https://cloud.google.com/vertex-ai/generative-ai/docs/video/video-gen-prompt-guide
- [Official] Gemini API Veo 3.1 docs (refs, lastFrame, extension, durations) — https://aistudio.google.com/docs/veo
- [Official] Veo reference-to-video — https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/generate-videos-from-references
- [Official] OpenAI Cookbook, *Sora 2 Prompting Guide* (Mar 2026) — https://cookbook.openai.com/examples/sora/sora2_prompting_guide
- [Official] Kling text-to-video prompt guide — https://kling.ai/quickstart/text-to-video-prompt-guide
- [3P] Kling 3.0 guide — https://seavidgen.com/blog/kling-3-0-prompt-complete-guide
- [3P] Seedance 2.0 methodology (cites BytePlus 2222480) — https://github.com/scotti1i/seedance-2.0-superprompt/blob/main/seedance/methodology.md
- [Official, JS-rendered] BytePlus Seedance 2.0 prompt guide — https://docs.byteplus.com/en/docs/modelark/seedance-2-0-prompt-guide
- [3P] Sora API shutdown — https://costgoat.com/pricing/sora

---

## 2. Image prompting and editing (gpt-image, Nano Banana, FLUX, Seedream)

### Key facts
- **Gemini 2.5 Flash Image (Nano Banana) [Official]**: "Describe the scene, don't just list keywords." The photoreal template is: `A photorealistic [shot type] of [subject], [action/expression], set in [environment]. Illuminated by [lighting], creating a [mood] atmosphere. Captured with [camera/lens], emphasizing [textures]. [aspect] format.`
  - For edits: `Using the provided image, change only the [element] to [new]. Keep everything else exactly the same, preserving the original style, lighting, and composition.`
  - With several inputs, the **output takes the aspect ratio of the last image**. Pass a reference image of the right size to force a ratio.
- **gpt-image-1.5 [Official]**:
  - Use the order *scene → subject → key details → constraints*, and state the intended use (ad, UI, infographic).
  - Put literal text in **quotes or ALL CAPS**, and spell tricky words letter by letter.
  - With several images, reference each by **index and role** ("Image 1: product… Image 2: style reference").
  - For edits, write "change only X" and **repeat the preserve list on every iteration**. Use `input_fidelity="high"` for identity.
  - For character consistency, make a "character anchor" image first, then edit from it with a bullet list headed "Character Consistency: same tunic, same facial features…"
- **FLUX (BFL) [Official]**: Kontext handles iterative edits with strong character consistency. Text edit syntax is `Replace '[old]' with '[new]'`. Coloured **annotation boxes** in the input target local edits. FLUX.2 supports **up to 10 reference images** and 4 MP output. Kontext output is ~1 MP, at ratios from 3:7 to 7:3.
- **Seedream 4.0/4.5 [3P from BytePlus guide]**: write natural-language sentences, not tag lists. Formula: `[Subject]+[Action]+[Environment]+[Style]+[Technical]+[Text content]`. Edit pattern: **action + object + target feature + constraints**. The *sequential* mode generates N consistent images in one call ("Generate 6 character sheets… Image 1: neutral pose; Image 2: action pose; Image 3: side profile; Image 4: back view…"). It is billed by `max_images`, so the number in the prompt must match it. Up to 10 reference images. Text works best at 1–10 words, at ≥2048 px.

### Apply to our tools
1. **`t_image`**: build `scene → subject → details → constraints → "Use: {style preset as intended use}"`. Today the style is a tail `". Style: X"`. Put user text in quotes. Index the references: `"Image 1 is {character name} identity reference; Image 2 is style reference."`
2. **`t_relight`**: replace `intensity {n}%` and the hex colour with words. Template: `Using the provided image, change only the lighting to {light} coming from {direction}, {soft|hard} quality, {warm amber|cool blue|…} colour. Keep subject, pose, expression, identity, composition and background geometry exactly the same.`
3. **`t_reimagine`**: map `strength` to three phrasings, and to the model's `strength`/`prompt_strength` parameter when the route supports one: `<40` "subtle restyle, keep materials recognisable", `40–75` "restyle surfaces, keep blocking and silhouettes", `>75` "full world transformation, keep only the camera, blocking and poses."
4. **`t_skin`**: same mapping. Add gpt-image's natural-photo phrasing: "honest and unposed, real skin texture, pores, fine vellus hair, no glamorisation, no heavy retouching." Use `input_fidelity=high` where routed to gpt-image.
5. **`t_palette`**: do the re-grade **deterministically** (Reinhard Lab mean/std transfer, or a 3D LUT fitted from palette clusters) instead of an AI edit. An AI edit can change content, which the tool promises not to do.
6. **`t_bg`** (described mode): `Place the subject from Image 1 into {background}. Match perspective, horizon height, light direction and colour temperature; add soft contact shadows; no haloing; keep the subject's edges and identity unchanged.`
7. **`t_ecom_image`**: add marketplace rules ("pure white background, product ~85% of frame", as already in the list). For labels add "preserve label legibility exactly; do not restyle the product." For the 360° grid, use a Seedream-sequential style prompt that names each view.
8. **`t_explainer`** and the infographic commands: route to gpt-image-1.5 at `quality="high"`, which is OpenAI's own advice for dense text.

### Sources
- [Official] Google Developers Blog, *How to prompt Gemini 2.5 Flash Image* — https://developers.googleblog.com/en/how-to-prompt-gemini-2-5-flash-image-generation-for-the-best-results/
- [Official] OpenAI Cookbook, *gpt-image-1.5 Prompting Guide* — https://developers.openai.com/cookbook/examples/multimodal/image-gen-1.5-prompting_guide
- [Official] BFL, FLUX.1 Kontext image editing — https://docs.bfl.ml/kontext/kontext_image_editing ; FLUX.2 — https://bfl.ai/blog/flux-2
- [3P] Seedream 4.0–5.0 tutorial — https://wavespeed.ai/blog/posts/seedream-4-0-to-5-0-complete-tutorial-image-generation-editing/
- [Official] BytePlus Seedream 4.0–4.5 prompt guide — https://docs.byteplus.com/en/docs/ModelArk/1829186

---

## 3. Character consistency across shots

### Key facts
- **Commercial "reference" systems:**
  - **Veo "Ingredients"**: up to 3 asset images of one subject, and the clip is forced to 8 s.
  - **Kling Elements**: a reusable library entry built from ~4 angle images (front, ¾ L, ¾ R, back) and called with `@Name`. Identity goes in the element, and behaviour and camera go in the text.
  - **Runway Gen-4 References**: up to **3 active references**, tagged with `@name` and shareable across a workspace. The best reference images have **natural, even lighting, moderate quality and a neutral expression**. "Describe the subject's shoes or pants to get a full-body shot."
  - **Sora Characters**: a 2–4 s, 720–1080p clip. At most 2 characters per generation (now retired).
- **Failure modes** (from the Kling guide):
  - Missing angles make clothing and labels change when the subject turns.
  - In very wide shots the face is only a few dozen pixels, so keep identity beats to MCU/CU.
  - Similar-looking characters blur together unless each has its own element.
- **Open pipelines (concepts to mirror):**
  - **IP-Adapter**: decoupled image cross-attention that injects reference features.
  - **InstantID**: ArcFace face embedding plus landmark ControlNet, so identity holds from one photo.
  - **PuLID**: a contrastive ID loss that keeps identity without breaking prompt-following.
  - **PhotoMaker**: stacked ID embedding from several photos.
  - **StoryDiffusion / ConsiStory**: consistent self-attention across a batch of story frames.
  - These share four principles: (a) a clean, multi-angle identity source, (b) separate identity from scene, (c) a **fixed seed and fixed style anchors** for repeatable variation, and (d) measure identity with a **face-embedding cosine** (ArcFace) instead of by eye.
- **Moderation** [3P, Seedance]: reference images showing a recognisable face *and* most of the body are often blocked. Keep a headshot and a separate half-body or back view.

### Apply to our tools
1. **`t_casting`**: after the user locks a candidate, auto-generate a **character sheet**, which becomes the lock:
   ```
   Character reference sheet of {name}: {description}. Neutral mid-grey seamless background,
   even soft frontal light, neutral expression, same outfit in every view, 85mm, eye level.
   Views: front headshot; three-quarter left; three-quarter right; left profile; back of head and shoulders;
   waist-up front. Identical face, hairline, eye colour, moles/scars and wardrobe in every view.
   ```
   Store the views as separate ref files, because ref slots take files, not grids. Record the `seed`. Feed 3 of them, as front, ¾ and profile, into Veo ingredients, Kling Elements or Runway refs.
2. **`ctx.cast()`** (used by every tool): send the **minimum** refs per model (Veo ≤3, Runway ≤3, Seedance 4–5 total), chosen by shot size. Use a headshot for CU and front plus full-body for WS. Add a **canonical identity sentence** that is reused word for word across shots, which Sora recommends. For I2V models, drop the sentence (§1).
3. **`t_angles`**: use the four-angle set as the default (`Front, ¾ L, ¾ R, Back`), because Kling's guidance says that set is the minimum. Add "same focal length and camera distance, same lighting setup, neutral background" so the views can be compared.
4. **`t_expressions`**: use change-only edit phrasing: `Using Image 1, change only the facial expression to {emotion}: {FACS cues, e.g. "inner brows raised, lip corners pulled down"}. Keep face shape, eyes, skin, hair, wardrobe, lighting and framing identical.` Concrete muscle cues beat the bare emotion word, the same "externalise emotion" rule Seedance gives.
5. **Identity metric**: add `identity_score(img, refs)`, the cosine similarity of ArcFace/InsightFace embeddings between the output's largest face and each ref. Use it inside `qc_score()` (§12) and as a gate in `t_shots`, `t_video` and `micro_ad`. Calibrate the threshold on your own data. About 0.4–0.5 cosine is a typical starting point for buffalo_l-class models.

### Sources
- [Official] Veo reference images — https://aistudio.google.com/docs/veo ; https://deepmind.google/models/veo/
- [Official] Runway, *Creating with Gen-4 Image References* — https://help.runwayml.com/hc/en-us/articles/40042718905875-Creating-with-Gen-4-Image-References
- [3P] Kling 3.0 Omni Elements (four-image workflow) — https://invideo.io/blog/kling-omni-elements/
- [Official] Sora Characters API — https://cookbook.openai.com/examples/sora/sora2_prompting_guide
- Papers: IP-Adapter https://arxiv.org/abs/2308.06721 · InstantID https://arxiv.org/abs/2401.07519 · PuLID https://arxiv.org/abs/2404.16022 · PhotoMaker https://arxiv.org/abs/2312.04461 · StoryDiffusion https://arxiv.org/abs/2405.01434 · ConsiStory https://arxiv.org/abs/2402.03286 · ArcFace https://arxiv.org/abs/1801.07698

---

## 4. Screenwriting, coverage and formats

### Key facts
- **Coverage format** [Industry, Final Draft and StudioBinder]:
  - The cover page lists title, writer, genre, locations, **page count**, submitter and attachments, then a **logline** and a short verdict.
  - Then come a **ratings grid** (premise, structure, characterisation, dialogue, production value, each **Poor → Excellent**), an optional **budget estimate**, a **1–3 page synopsis**, **comments** (strengths and problems), and the **verdict: Pass / Consider / Recommend**. Finer grades such as "Strong Consider" exist.
  - Many companies **rate the writer separately** from the script. "Recommend" is rare, and "Pass" is the most common verdict.
- **Black List evaluations** [Official]: scores run 1–10 overall with component scores. "Your overall score is **not** the simple average of your component scores"; it reflects how likely the reader is to pass the script up the chain. An 8 or higher is the tier that matters to the industry [3P].
- **Save the Cat beats** (110-page feature):

  | Beat | Page | % of runtime |
  |---|---|---|
  | Opening Image | 1 | 0–1% |
  | Theme Stated | 5 | 5% |
  | Set-Up | 1–10 | 0–10% |
  | Catalyst | 12 | 10% |
  | Debate | 12–25 | 10–23% |
  | Break into Two | 25 | 23% |
  | B Story | 30 | 27% |
  | Fun & Games | 30–55 | 27–50% |
  | Midpoint | 55 | 50% |
  | Bad Guys Close In | 55–75 | 50–68% |
  | All Is Lost | 75 | 68% |
  | Dark Night of the Soul | 75–85 | 68–77% |
  | Break into Three | 85 | 77% |
  | Finale | 85–110 | 77–100% |
  | Final Image | 110 | 100% |
- **Other models:**
  - **Three acts**: 25% / 50% / 25%.
  - **Hero's Journey** (Vogler's 12 stages): Ordinary World → Call → Refusal → Mentor → Crossing the Threshold → Tests/Allies/Enemies → Approach → Ordeal (~midpoint) → Reward → Road Back → Resurrection → Return with the Elixir.
  - **Kishōtenketsu**: *ki* (introduction) → *shō* (development) → *ten* (twist or juxtaposition, not conflict) → *ketsu* (reconciliation). It suits slice-of-life and ad films.
  - **TV**: a cold open plus 4–5 acts that each end on an act-out.
- **Pacing heuristics:**
  - One screenplay page is about one minute of screen time.
  - Scenes typically run 1–3 pages, so a feature has roughly 40–60 scenes. A dialogue scene over 3 pages is worth flagging.
  - Breakdown and scheduling measure scenes in **eighths of a page**.
  - Setup and payoff: every planted object, line or skill needs a payoff later on screen. Unpaid setups and unseeded payoffs are coverage notes.
- **Fountain syntax** [Official]:
  - Scene headings start with `INT`, `EXT`, `EST`, `INT./EXT`, `INT/EXT` or `I/E`, or are forced with a leading `.`. Optional scene numbers look like `#12A#`.
  - Character names are ALL CAPS with a blank line before them. Use `@` to force mixed case, and extensions such as `(O.S.)` or `(V.O.)` are allowed.
  - Parentheticals are `(…)` lines under the character. Dual dialogue puts `^` after the second character name.
  - Transitions are ALL CAPS ending in `TO:`, or forced with `>`. Lyrics start with `~`.
  - Emphasis is `*italic*`, `**bold**` and `_underline_`. Other syntax: `===` page break, `# section`, `= synopsis`, `[[note]]`, `/* boneyard */`, `>centered<`.
  - The title page is `Key: value` lines (Title, Credit, Author, Source, Draft date, Contact) followed by a blank line.
- **FDX** is XML. The root is `<FinalDraft DocumentType="Script" Template="No" Version="…">`, then `<Content>` holds `<Paragraph Type="Scene Heading|Action|Character|Parenthetical|Dialogue|Transition|Shot|General">` with `<Text>` runs. The optional `<TitlePage>` repeats the Content/Paragraph structure. Scene numbers are a `Number` attribute on Scene Heading paragraphs.

### Apply to our tools
1. **`t_story` (outline stage)**: for the chosen `structure`, compute target positions from `runtime` (page ≈ minute) and require the LLM to fill each beat with its target page or minute:
   `beats=[{"beat":"Catalyst","target_min":round(0.10*T,1),"summary":...}]`. For Kishōtenketsu, use four beats at ~25% each. For "Problem → solution → proof (ad)", use seconds (§7).
2. **`t_story` (draft stage)**: extend the schema with `parentheticals`, `transitions` and a `setups:[{id,plant_scene,payoff_scene}]` ledger. The independent review must check each `must` and `never` line and every unpaid setup.
3. **`fountain()`**: write a full title page (`Title`, `Credit: Written by`, `Author`, `Draft date`). Emit parentheticals on their own line under the character. Emit transitions as `CUT TO:`. Force odd headings with `.`. Add `#n#` scene numbers. Uppercase character names only on the cue line.
4. **`fdx()`**: emit `Parenthetical` and `Transition` paragraphs, add a `<TitlePage>`, and put scene numbers in the `Number` attribute.
5. **`t_doctor`**: match the industry report structure:
   ```json
   {"logline":"","synopsis":"(1 page)","grid":{"Premise":"Excellent|Good|Fair|Poor","Structure":..,"Characterization":..,"Dialogue":..,"Production value":..},
    "blacklist_style":{"overall":1-10,"premise":1-10,"plot":1-10,"character":1-10,"dialogue":1-10,"setting":1-10},
    "verdict_script":"Pass|Consider|Recommend","verdict_writer":"Pass|Consider|Recommend",
    "comments":{"strengths":[],"problems":[{"note":"","evidence":"p.X quoted line","fix":""}]}, "budget_tier":"micro|low|mid|high"}
   ```
   - Tell the model that **overall is a holistic judgement, not a mean**, following the Black List.
   - Compute the *deterministic* stats in Python, not with the LLM: page count (about 55 lines per page), scene lengths in eighths, scenes longer than 3 pages, dialogue-to-action line ratio, speaking-line count per character (screen-time) and INT/EXT/DAY/NIGHT counts.
   - Map beat positions found in the script against the Save the Cat percentages to give a "Structural Beat-Mapping" score.

### Sources
- [Industry] Final Draft, *What Is Script Coverage?* (Sep 2026) — https://www.finaldraft.com/blog/what-is-script-coverage-a-guide-for-screenwriters
- [Industry] StudioBinder, coverage guide — https://www.studiobinder.com/blog/script-coverage-complete-guide/
- [Official] Black List help (overall ≠ average) — https://help.blcklst.com/kb/guide/en/writers-pROPvK6l0J/Steps/2683802,2853550,2733421,2733422,2733425,2748743
- [Industry] Save the Cat beats with pages — https://www.studiobinder.com/blog/save-the-cat-beat-sheet/ ; https://reedsy.com/blog/guide/story-structure/save-the-cat-beat-sheet/
- [Official] Fountain syntax — https://fountain.io/syntax/
- [3P] Fountain vs FDX structure — https://laper.ai/blog/fountain-format-vs-fdx-screenplay-files/ ; Final Draft KB — https://kb.finaldraft.com/

---

## 5. Production breakdown and AI budgeting

### Key facts
- **Breakdown colour code** [Industry, Wikipedia scheme as reproduced by ScreenWeaver, Filmustage and UNC]:

  | Element | Mark |
  |---|---|
  | Cast (speaking) | Red |
  | Stunts | Orange |
  | Silent extras / bits | Yellow |
  | Atmosphere extras | Green |
  | Special effects | Blue |
  | Props | Purple |
  | Vehicles / animals | Pink |
  | Sound / music | Brown |
  | Wardrobe | Circle |
  | Make-up | Asterisk |
  | Special equipment | Box |
  | Production notes | Underline |

  Each scene gets one breakdown sheet: number, INT/EXT, set, D/N, **pages in eighths**, **script day** (e.g. N4) and synopsis.
- **Stripboard**: one strip per scene, coloured by INT/EXT and D/N. The common default is white for INT day, yellow for EXT day, blue for INT night and green for EXT night. Strips are sorted to group locations and night work and to keep cast days short.
- **On an AI production** [3P, ScreenWeaver], each column changes meaning:
  - Cast becomes *character refs to build once*.
  - Locations become *location refs plus time of day and light*.
  - Props and wardrobe become *details that drift and must be in refs or prompts*.
  - Stunts and VFX become *the shots that need the most rerolls*.
  - Eighths become a *clip count*.
- **Video generation prices, Oct 2026** (USD per generated second):

  | Model | Price | Note | Source |
  |---|---|---|---|
  | Veo 3.1 Lite | $0.05 (720p) / $0.08 (1080p) | — | Gemini API |
  | Veo 3.1 Fast | $0.10 / $0.12 / $0.30 (720p / 1080p / 4K) | — | Gemini API |
  | Veo 3.1 Standard | $0.40 / $0.40 / $0.60 | Vertex video-only is about half ($0.20) | Gemini API |
  | Gemini Omni Flash | ~$0.10 (720p) | billed as tokens | Gemini API |
  | Kling 3.0 | $0.084 (720p, no audio) · $0.112 (1080p, no audio) · $0.126 / $0.168 (720p / 1080p with audio) · $0.42 (4K) | official API; prepaid packages from $700 | aivideocosts.fyi |
  | Kling 3.0 Turbo | $0.14 (1080p, with audio) | — | aivideocosts.fyi |
  | Kling 2.6 / 2.5 Turbo | $0.042 (720p) / $0.07 (1080p) | — | aivideocosts.fyi |
  | Seedance 2.0 (direct) | $0.78 (4K) | below 4K BytePlus bills per token | BytePlus |
  | Seedance 2.0 (resellers) | ~$0.15–0.20 (720p) · ~$0.37–0.51 (1080p) | — | resellers |
  | Seedance 1 Pro (fal) | ≈$0.62 per 5 s 1080p clip | `tokens = h×w×fps×s/1024`, $2.50 per M | fal |
  | Sora 2 / 2 Pro (retired) | $0.10 (720p) · $0.30–0.70 | API shut down 24 Sep 2026 | historical |

- **Wastage**: you pay for every reroll and for the seconds you trim.
  - Worked example [3P, WaveSpeed]: of 100 Veo Fast clips, 90 complete and 54 pass review, so $1.60 per *accepted* clip against a $0.96 sticker. Adding 2 minutes of review per clip at $36/h brings it to **$3.60 per accepted clip**.
  - A practitioner's Kling clip [3P, mesmer] kept 2.5 of 5 s, so a usable second cost $0.28 against the $0.168 list price. Keep rates of 50% or 33% double or triple the cost.
  - Plan on keep rates of about 60% for product, still and slow shots, 30–40% for dialogue and lip-sync, and 20–30% for action, hands or multi-character shots. Measure your own rates and store them.
- **Audio prices** [Official, Oct 2026]:
  - ElevenLabs TTS v4/v3: $0.08 per 1K characters, about $0.08 per minute. Flash/Turbo: $0.04.
  - ElevenLabs Music: $0.15 per minute. SFX: $0.12 per minute. Voice isolator and changer: $0.12 per minute.
  - ElevenLabs Dubbing v1: $0.33 per minute with watermark, $0.50 without. Dubbing v2, which keeps voice and emotion, is $2.20 per minute.
  - ElevenLabs Scribe STT: $0.22 per hour.
  - Lyria 3.5 full song: $0.08 per song. Lyria 3 Clip (30 s): $0.04.
  - Gemini Flash TTS: about $0.002 per 10 s of audio.
  - Images: Gemini image at ~$0.034 (1K) to $0.151 (4K). Seedream 4.0 at $0.027 and 4.5 at $0.04 through a reseller.

### Apply to our tools
1. **`RATES` / `QUALITY` / `t_budget`**: split every line into **compute** and **labour**.
   - Compute should come from a `PRICES` table keyed by `(model, resolution, audio)` in $/s, with a date stamp. For example, Standard routes to Veo Fast 1080p at $0.12/s, Premium to Kling 3.0 1080p with audio at $0.168/s, and Cinema to Veo Standard at $0.40/s.
   - Formula: `cost = finished_seconds × $/s ÷ keep_rate`, with `keep_rate` per shot class (static 0.6, dialogue 0.35, action 0.25). Today a flat $900 per finished minute is applied. That is roughly 10–30× real compute ($7–24 per minute of raw generation) unless it is meant to include labour, so label it.
   - Fold the `recurring`, `lipsync` and `action` toggles into the shot-class mix instead of multipliers stacked on `takes`.
   - Voice: AI VO costs ≈ $0.08 × (words ÷ 150) per minute, not $30. Price a human VO line separately.
   - Dubbing: offer v1 ($0.50/min) or v2 ($2.20/min) per language.
   - Music: $0.15/min, or $0.08 per Lyria song.
   - Subtitles: STT at $0.22/h plus translation tokens.
2. **`t_budget`** bug: `minutes = minutes or pages` never uses the script length, because `minutes` defaults to 5. Use the page count whenever a script is uploaded. A screenplay page has about 55 lines or ~180–250 words.
3. **`t_doctor` → `production_footprint`**: give a real breakdown, one row per scene: `{scene, int_ext, d_n, eighths, script_day, cast[], silent[], atmos[], props[], wardrobe[], vfx[], stunts[], vehicles[], animals[], sound[], notes[]}`. Pass it to `t_budget`, which should count clips as `ceil(eighths×60/8 ÷ avg_shot_len)` with a 3–4 s average shot. Also emit a **stripboard CSV** with the INT/EXT×D/N colour.

### Sources
- [Industry] ScreenWeaver, breakdown process and AI column mapping (Oct 2026) — https://www.screenweaver.ai/blog/script-breakdown-complete-process
- [Industry] Filmustage, breakdown symbols and colours — https://filmustage.com/blog/script-breakdown-symbols-and-color-codes-a-complete-guide/ ; UNC breakdown sheet — https://medialab.web.unc.edu/wp-content/uploads/sites/17062/2018/06/scriptbreak.pdf
- [Official] Vertex / Agent Platform pricing (Veo) — https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing ; Gemini API pricing — https://ai.google.dev/gemini-api/docs/pricing
- [3P] Veo pricing and accepted-clip maths — https://wavespeed.ai/blog/cost-and-billing/google-veo-3-pricing/
- [3P] Per-second table (official and reseller rows, Oct 2026) — https://aivideocosts.fyi/ ; usable-second maths — https://mesmer.tools/blog/kling-ai-pricing
- [Official] fal Seedance / Kling pages — https://fal.ai/models/fal-ai/bytedance/seedance/v1/pro/text-to-video ; https://fal.ai/models/fal-ai/kling-video/v2.6/pro/text-to-video
- [Official] ElevenLabs API pricing — https://elevenlabs.io/pricing/api

---

## 6. Storyboarding and shot grammar

### Key facts
- **Shot list columns** [Industry, StudioBinder]: scene #, shot #, description, **shot size**, **angle**, **movement**, **equipment**, **lens / focal length**, frame rate, cast and notes. Group shots into **setups** (same lighting) for efficiency.
- **180° rule**: keep the camera on one side of the axis between two characters, or along a direction of travel. Screen direction and eyelines then stay consistent (in *Heat*, Pacino looks camera right and De Niro camera left).
  - You can cross the line on purpose to disorient.
  - You can reset it with a **neutral shot on the axis**, a visible **camera move across the line**, or a **cutaway**.
  - For groups, think "stage play, camera in the seats".
  - For vehicles, keep the direction of travel consistent across cuts.
- **30° rule**: a cut to the same subject should change the angle by at least 30°, or change shot size clearly, to avoid a jump cut.
- **Coverage pattern for a dialogue scene**: master or wide → two-shot → over-the-shoulder pair → matching singles (MCU, then CU) → inserts and cutaways. Shot-reverse-shot keeps the eyeline opposite and the frame size matched.

### Apply to our tools
1. **`t_storyboard` (plan stage)**: extend the shot schema to
   `{"n","scene","shot_size":"EWS|WS|FS|MS|MCU|CU|ECU|INSERT","angle":"eye|low|high|overhead|dutch|POV|OTS","movement":"static|pan|tilt|dolly in|…","lens_mm":35,"duration_s":3,"cast":[],"location":"","axis_side":"A|B","screen_direction":"L→R|R→L","eyeline":"camera left|right","purpose":"establish|react|reveal|insert"}`.
   - Instruct the model to follow the 180° rule and to *flag* any deliberate crossing.
   - Instruct it to use standard dialogue coverage and to keep consecutive shots of the same subject ≥30° or one shot size apart.
   - Add `duration_s` and `lens_mm` columns to the CSV.
2. **`t_storyboard` (board stage)**: put the axis and eyeline in each panel prompt ("{character} on frame left looking camera right"), so panels respect screen direction. Reuse the style frame as Image 1 and the character refs as Image 2+, with index labels as in §2.
3. **`t_shots` (Multi-Shots)**: add the same axis and eyeline text, and for reverse shots add "camera on the same side of the action line". Do not let the first generated shot become the key frame by accident (`key = key or p`). Generate the WS master first, then use it as Image 1 for every other size.
4. **`t_comics`**: panel `camera` should vary by rule. Do not use the same shot size in consecutive panels unless it is intentional, and give each page an establishing panel.

### Sources
- [Industry] StudioBinder, 180° rule — https://www.studiobinder.com/blog/what-is-the-180-degree-rule-film/
- [Industry] StudioBinder, how to make a shot list — https://www.studiobinder.com/blog/how-to-make-a-shot-list/
- [Official] Vertex video prompt guide (shot-size and angle vocabulary) — https://cloud.google.com/vertex-ai/generative-ai/docs/video/video-gen-prompt-guide

---

## 7. Ad creative (short-form)

### Key facts
- **Structure**:
  - Hook in the first 1–3 s (TikTok: "the scroll decision happens almost immediately"; trailer analytics show drop-off within 6 s).
  - Then problem → solution or demo → proof (social proof, results, specs) → CTA and end card.
  - Hooks that work: an unexpected visual, a direct question, a contrarian claim, the **end result first**, or someone talking straight to camera with urgency.
  - Hooks that fail: logo cards, slow establishing shots and build-ups.
- **TikTok**:
  - Sound is on by default, so silent ads "read as broken". Always add captions anyway.
  - Native, phone-shot and jump-cut footage often beats studio polish.
  - Creative fatigues in 1–2 weeks, so produce in batches of *distinct* concepts with a different hook, format and narrator.
  - Judge hold rate at 2 s and 6 s.
  - Seedance agrees: three segments, hook 0–3 s, body, CTA.
- **Safe zones**:

  | Placement | Keep key elements out of | Source |
  |---|---|---|
  | Meta 9:16 (Stories, Reels, Feed 9:16, FB in-stream reels) | top ≈14% (270 px), bottom ≈35% (670 px), sides ≈6% (65 px) | Meta Help gives no numbers in-page; figures are 3P, Mar 2026 |
  | Meta Reels with disclaimers | bottom 40% | Meta Help |
  | TikTok organic | top ~6% (108 px), bottom ~17% (320 px), right ~11% (120 px) | 3P; ads need extra bottom room for CTA and "Sponsored" |
  | YouTube Shorts | top ~10%, bottom ~30% | 3P; Shorts are now up to 3 min |
  | Instagram feed non-9:16 | bottom and sides | Meta Help |

  On Meta, a taller-than-9:16 screen may zoom the creative or letterbox it in black.
- **Sizes**:
  - 9:16 at 1080×1920 for Reels, TikTok and Shorts. 4:5 at 1080×1350 for feed. 1:1 at 1080×1080. 16:9 at 1920×1080.
  - LinkedIn video ads run **3 s–30 min**, at aspect 9:16 to 16:9, with a minimum of 360×640 for vertical.
- **End card**: 1.5–3 s with logo, product, offer or price and one CTA verb, inside the safe zone. Meta asks for one message and one CTA. YouTube end screens use the last 5–20 s, with up to 4 elements, on videos of 25 s or more.
- **UGC formats**: talking head or testimonial, unboxing (ASMR), "TikTok made me buy it", before/after, tutorial or hack, try-on, POV, reaction/stitch, and a problem-agitate-solve rant. Brief creators loosely, because "a creator given a script produces content that sounds like a script."

### Apply to our tools
1. **`micro_ad` planner prompt**: require a beat plan with seconds and roles, scaled to `duration`:
   ```
   HOOK 0–{0.15D}s (pattern interrupt, result-first or direct question; on-screen text ≤4 words)
   PROBLEM {…}s · SOLUTION/DEMO {…}s (product clearly visible, accurate) · PROOF {…}s (stat, review, before/after)
   CTA + END CARD last {max(1.5, 0.15D)}s (logo, price, one verb)
   ```
   - Return `caption_lines` per beat (≤4 words each) and a VO line per beat that fits its duration at about 2.5 words per second.
   - Time the VO per shot instead of laying one TTS file over the whole cut.
2. **`micro_ad.render` and `M.end_plate`**: lay out text using platform safe-zone masks. Add `SAFE = {"Instagram Reels":(0.14,0.35,0.06), "Facebook Stories":(0.14,0.35,0.06), "TikTok":(0.06,0.20,0.11), "YouTube Shorts":(0.10,0.30,0.06)}`. Burn captions by default, centred above the bottom reservation.
3. **`qc_score` platform-fit axis**: check mechanically that the hook has motion or a face in the first second, that captions are present, that text sits inside the safe zone and that the end card holds for 1.5 s or more.
4. **`t_ugc`**: give each format its own beat template instead of a generic 3-beat plan. For example, *Unboxing*: hands and box sound (0–2 s), reveal, first-use reaction, close detail, CTA. *Testimonial*: "I was skeptical…" hook, problem, result, proof, CTA. Prompt for phone realism ("shot on iPhone, handheld, natural window light, slight exposure shifts, jump cuts"). Always burn captions.
5. **`t_batch`**: generate **distinct hooks** per row (2–3 variants) rather than one, because fatigue makes hook volume the constraint.

### Sources
- [Official] Meta Business Help, text overlays and safe zone — https://www.facebook.com/business/help/980593475366490
- [3P] Meta unified safe zone numbers (Mar 2026) — https://blog.adnabu.com/meta-ads/meta-safe-zones/ ; https://kive.ai/learn/meta-ad-sizes
- [3P] TikTok safe zone — https://www.pod2reels.com/blog/tiktok-safe-zone-guide
- [Industry] TikTok creative best practices (summarising TikTok Ads Manager docs) — https://www.clarigital.com/codex/paid-advertising/tiktok-ads/tiktok-creative-best-practices/
- [Official] LinkedIn video ad specs — https://business.linkedin.com/advertise/ads/sponsored-content/video-ads/specs
- [3P] YouTube Shorts safe zone — https://www.muzecmo.com/tools/safe-zones/youtube-shorts/ ; [Official] YouTube end screens — https://support.google.com/youtube/answer/6388789

---

## 8. Subtitles (Netflix, BBC, ASS)

### Key facts
- **Netflix [Official]**:
  - **42 characters per line** for English and **2 lines maximum**. Keep to one line unless the text exceeds the limit.
  - Line breaks should form a **bottom-heavy pyramid**, but avoid one or two words on the top line. Break after punctuation, before conjunctions and before prepositions.
  - Never split an article from its noun, an adjective from its noun, a first name from a last name, a subject pronoun from its verb, a prepositional verb from its preposition, or a verb from its auxiliary, reflexive or negation.
  - Reading speed is **up to 20 cps for adult content and 17 for children's**.
  - Duration is **at least 5/6 s (20 frames at 24 fps) and at most 7 s**.
  - Timing:
    - The in-time is within 1–2 frames of the audio.
    - The out-time is about **0.5 s after the audio** when no subtitle follows.
    - Gaps are **exactly 2 frames, or 0.5 s or more**. Gaps of 3–11 frames at 24 fps must be closed ("chaining").
    - Snap to shot changes within half a second, keeping a 2-frame gap from the cut.
    - A subtitle may cross a shot change only when the dialogue does.
  - Centre-justified, at the top or bottom of the frame, and moved to avoid burned-in text.
- **BBC [Official]**:
  - 160–180 wpm, or about **0.33 s per word** as a minimum on screen.
  - Online line width: 68% of 16:9 width, or 90% for 4:3, 1:1 and 9:16. The guide's equivalence: 37 characters at 75% width in 16:9 ≈ **25 characters at 90% width in 9:16**.
  - **2 lines for landscape and square, up to 3 lines for vertical**.
  - Do not lead speech by more than 1.5 s or hang after it by more than 1.5 s. A gap between subtitles should be at least 1 s, ideally 1.5 s.
- **ASS karaoke [Official, Aegisub]**:
  - `\k<cs>` uses **centiseconds**. The syllable shows the **SecondaryColour** before its highlight and switches to **PrimaryColour** when it starts.
  - `\K` and `\kf` sweep left to right over the syllable's duration. `\ko` makes the outline appear when the syllable starts.
  - Each syllable's start is the *sum of the preceding \k durations*, so gaps between words must be encoded as `\k` too.

### Apply to our tools
1. **`write_ass` karaoke bug**: today it uses `\k(end−start)` for each word, which drops the silences between words, so highlights drift early. Fix it by putting a leading `{\k(w0.start−cue.start)}` before the first word, then for each word `\k` = `(next.start − this.start)` × 100. The last word uses `(word.end − word.start)`. Offer `\kf` as a "sweep" option.
2. **`cues_from_words`**: implement real segmentation.
   - Allow up to `max_lines` lines (2, or 3 for 9:16) of `max_chars` each.
   - Choose breaks with the Netflix rules: a penalty table for forbidden splits and a preference for a bottom-heavy line.
   - Enforce `cps ≤ 20` (17 for kids) by merging or extending, and clamp duration to 0.833–7 s.
   - Extend the out-time by 0.5 s when there is room. Chain gaps under 0.5 s to 2 frames, using the video's fps.
   - Optionally snap to shot changes by reusing `M.motion_scores` or a scene detector.
   - Rhythms of 1–4 words are fine for social "word-pop" styles. Skip CPS checks only for those.
3. **`write_ass` position**: on 9:16 output, `MarginV = 8% of h` puts bottom captions inside the TikTok/Reels UI band (bottom 17–35%). Use `MarginV ≈ 0.22·h` for TikTok and `0.36·h` for Reels/Shorts on bottom-aligned presets. Centre styles (alignment 5) are already safe. Default `max_chars` to about 25 for 9:16 and 42 for 16:9.
4. **`t_subtitles` translation**: translate **with the timings**, sending cue durations and asking for CPS-compliant condensation ("keep ≤20 cps for each cue; condense rather than paraphrase"). Re-run line breaking per language, and use the BBC/Netflix language-specific limits (e.g. CJK ~16 characters per line) when they are known.

### Sources
- [Official] Netflix, Timed Text Style Guide: General Requirements — https://partnerhelp.netflixstudios.com/hc/en-us/articles/215758617-Timed-Text-Style-Guide-General-Requirements
- [Official] Netflix, English (USA) Timed Text Style Guide — https://partnerhelp.netflixstudios.com/hc/en-us/articles/217350977-English-USA-Timed-Text-Style-Guide
- [Official] Netflix, Subtitle Timing Guidelines — https://partnerhelp.netflixstudios.com/hc/en-us/articles/360051554394-Timed-Text-Style-Guide-Subtitle-Timing-Guidelines
- [Official] BBC Subtitle Guidelines — https://www.bbc.co.uk/accessibility/forproducts/guides/subtitles/
- [Official] Aegisub ASS override tags (karaoke) — https://aegisub.org/docs/latest/ass_tags/

---

## 9. Trailers, teasers and highlight detection

### Key facts
- **Trailer acts** [Industry, Derek Lieu, trailer editor on *The Matrix* trailers]:
  1. **Cold open**: straight into action and ends on a hook. Sparse, percussive music.
  2. **Introduction**: premise and exposition, often as rhetorical questions. Light, "driving" music sits under the dialogue.
  3. **Escalation**: the antagonist or problem appears, with a run of "GET READY…" moments. Sections end on a question, a fade to black or a music edit.
  4. **Climax**: music takes over and the best shots come in rapid succession. Ends at the peak with the **title card**.
  5. **Button / stinger** (optional): one last joke or beat after the title.
  - "Trailers start big and end big." The first **6 seconds** decide retention.
- **Teaser vs trailer**: a teaser runs 15–60 s and withholds plot, built on mood, one image and the title. A trailer runs about 2–2.5 min and covers the full act arc. The 60–90 s "trailer" in our `REEL_MODES` matches social cutdowns. Spec §20 also allows it.
- **Highlight signals** [academic]:
  - The classic affective-arousal model combines **motion activity**, **shot-cut density** and **audio energy** into a smoothed excitement curve (Hanjalic & Xu 2005, summarised in the AI video editing survey).
  - Other cues: face presence and size, speech or laughter, music onsets, and peaks in loudness or spectral flux.
  - Modern work adds query-based scoring (QVHighlights / Moment-DETR). A VLM can label candidate segments, but the candidates should come from the signal curve.
  - Scene and shot detection (e.g. PySceneDetect's content detector) gives clean in- and out-points, so cuts never land mid-shot.

### Apply to our tools
1. **`key_frames()`**: replace `motion×1.5 + sharpness` with a weighted, smoothed arousal curve: `z(motion) + z(audio_RMS) + z(cut_density) + 0.5·z(face_area) + 0.3·z(sharpness)`. Compute audio RMS with ffmpeg `astats` or `ebur128` at 0.5 s windows and face area with an OpenCV or MediaPipe detector. Detect shot boundaries first, and pick at most one moment per shot.
2. **`t_vi`**:
   - Cut on **shot boundaries** instead of fixed `seg` windows centred on a frame.
   - For *Trailer*, assign moments to acts by narrative position and score: cold open = a high-arousal moment from the first third. Intro = low-arousal dialogue moments. Escalation = rising arousal. Climax = top-k in rapid 0.5–1.5 s cuts. Then title card, then an optional button.
   - Ask the VLM to tag each candidate with `{act_role, has_dialogue_hook, spoiler_risk}`.
   - For *Teaser*, cap at 3–6 moments and never use the climax or ending.
   - Cut to the music bed's beats: detect onsets with `librosa`, or at minimum use the `music` file's BPM.
   - Add title-card and end-card generation through `M.end_plate`.
3. **Shot lengths**: a trailer's average shot length falls from 2–3 s in the intro to under 1 s in the climax. Use a schedule instead of the fixed `seg = 3.0`.

### Sources
- [Industry] Derek Lieu, *The Matrix and Movie Trailer 3-Act Structure* — https://derek-lieu.medium.com/the-matrix-and-movie-trailer-3-act-structure-b06a68e01214
- [Industry] Save the Cat, trailers and the beat sheet — https://savethecat.com/about-the-beats/movie-trailers-and-the-blake-snyder-beat-sheet
- [Academic] *AI video editing: A survey* (motion, cut frequency and audio energy for highlights) — https://www.preprints.org/frontend/manuscript/475c485b3e9f8287c3ba32512484b666/download_pub
- [Academic] Scene detection and keyframe policies — https://arxiv.org/abs/2506.00667 ; QVHighlights/Moment-DETR — https://arxiv.org/abs/2107.09609
- Hanjalic & Xu, "Affective video content representation and modeling", IEEE TMM 2005 (DOI 10.1109/TMM.2004.840618)

---

## 10. Thumbnails and posters

### Key facts
- **YouTube [Official]**:
  - Thumbnails are 1280×720 (16:9) and must be under 2 MB. Anything below 720p makes A/B tests downscale every variant to 480p.
  - **Test & Compare** runs up to **3** thumbnails and picks the winner by **watch-time share**, not CTR. Tests take up to 2 weeks, and options that are too similar end "inconclusive".
  - Shorts cannot be A/B tested.
- **vidIQ study of 500 breakouts [Industry, Jun 2026]**:
  - Faces appear in 69% of all breakouts, 75% of the top 100 and **80% of the top 50**.
  - High contrast is flat at about 56% and does not rise with performance.
  - 72% use overlay text. The median is 5 words among those with text, and most use **3 words or fewer**.
  - Only 5% use an exaggerated expression. The common winner has a face filling about **1/3 of the frame**, one focal point and a short bold hook placed opposite the face.
  - Avoid the bottom-right corner, where the duration badge sits.
- **Poster / billing block [Industry, quoting the DGA and WGA agreements]**:
  - The billing block is ultra-condensed capitals at the bottom of the one-sheet. The US one-sheet is 27×40 in (8100×12000 px at 300 dpi), and the block spans about 90% of the width.
  - Order: presentation credits → possessory ("A … Film") → above-title cast → [Title] → cast → casting, costume, editor, production design, DP, music → executive producers / producers → writers ("&" means a team, "and" means separate) → **"Directed by"** (last) → bottom bar (logos, rating, URL, date).
  - The director's credit must be **at least 15% of the title's type size** in paid ads, and 35% on outdoor ads that carry other names. Writer credits match the producer or director size and are also at least 15%. Block type usually runs 15–35% of the title's letter height.
  - Teasers may omit credits.

### Apply to our tools
1. **`t_thumb`**:
   - Default to producing **3 distinct concepts** for Test & Compare (face-led, object-led, text-led), not size variants of one concept.
   - Prompt template: `{shot}: {subject's face} filling ~1/3 of frame on the {left|right}, genuine {emotion} expression, one focal point, clean background with strong figure–ground separation; empty {opposite side} for a 2–4 word hook; nothing important in the bottom-right corner.`
   - Enforce `len(title.split()) ≤ 4` with a warning.
   - Always typeset the text ourselves (`overlay=True`), placed opposite the face.
   - Export JPG under 2 MB at 1280×720 or larger.
2. **`t_poster` / `M.overlay_title`**:
   - Add an optional **billing block** generator. Fields: presenter, cast[], crew{casting, costume, editor, pd, dp, music}, producers, writers, director. Typeset it in a condensed font (OFL options: Saira Extra Condensed, Antonio, Bebas Neue) at ≥15% of the title's cap height, spanning 90% width.
   - Fix the "Print A4 portrait" ratio label, which is 1:1.414, not 3:4.
   - Add a "Theatrical one-sheet 27×40" format (0.675).
   - Generate the art with **negative space for title and block** ("lower 25% darker and uncluttered for credits").
3. **`THUMB_SIZES`**: the "LinkedIn (mirrored safe zone)" label has no source. Use LinkedIn's documented 16:9, 1:1 and 4:5.

### Sources
- [Official] YouTube Help, A/B test titles and thumbnails — https://support.google.com/youtube/answer/16391400
- [Industry] vidIQ thumbnail study (Jun 2026) — https://vidiq.com/research/youtube-thumbnail-study/
- [Industry] Billing block rules quoting DGA Art. 8-203 and WGA Sch. A ¶22 — https://endcredits.pro/billing-block/ ; DGA credits — https://www.dga.org/The-Guild/Departments/Credits ; StudioBinder poster credits — https://www.studiobinder.com/blog/movie-poster-credits-template/

---

## 11. Music for picture

### Key facts
- **Lyria 3.5 [Official]**:
  - Lead with **genre** (era and region help, e.g. "early 1990s boom-bap"). Then name instruments and textures, then **BPM** ("slow tempo around 72 BPM") and **key/scale** ("in D minor"), then mood adjectives.
  - Give structure as tags or arrows (`[Intro] -> [Verse 1] -> [Chorus] …`). Lyria also understands timing markers ("build to a beat drop at 12 seconds") and dynamics ("drop to silence before an explosive chorus").
  - Lyrics go under a `Lyrics:` header with section tags, and backing vocals in parentheses. Lyria generates vocals by default, so say "Instrumental only" when you want none.
  - Lyria RealTime uses **weighted prompts** for live steering.
- **ElevenLabs Music [Official]**:
  - A prompt implicitly answers five things: **genre, mood, instrumentation, tempo and production era**. Anything left open "the model answers with the most average choice".
  - Studio vocabulary works: *sidechained, close-mic'd, bone-dry, tape saturation, plate reverb*.
  - Narrate the arrangement in order ("start with **just**…, then bring in…").
  - Loops are defined by exclusion ("four bars, no melody, just drums").
  - Timing cues work: "lyrics begin at 15 seconds", "instrumental only after 1:45".
  - **Composition plans** are up to 30 chunks of 3–120 s each, each with `positive_styles` and `negative_styles` and `context_adherence`. The first chunk sets the genre, so give it 6–7 styles. Styles must be in English.
  - The model "holds a stated BPM and key precisely enough to layer."
- **Scoring by emotion** (heuristics from music-emotion research, e.g. Juslin & Laukka 2003):

  | Scene | BPM | Mode / harmony | Texture |
  |---|---|---|---|
  | Tension / suspense | 60–90 | minor; pedal tones and ostinato | low strings tremolo |
  | Action | 120–170 | minor or modal | driving percussion, staccato brass |
  | Sadness | 50–75 | minor | sparse piano or strings, legato |
  | Joy / comedy | 110–140 | major | pizzicato and bright winds |
  | Romance | 60–85 | major or Lydian | warm strings |
  | Wonder | 70–100 | major / Lydian | swelling pads and choir |
  | Horror | free time | atonal | clusters, sub drones |
  | Ad / product | 100–128 | major | clear 4-bar phrasing and a sting on the CTA |

  Score *under* dialogue, keep the mid-range (1–4 kHz) clear, and duck the bed about 10–15 dB under VO.
- **Loudness targets**: Netflix uses −27 LKFS dialogue-gated ±2 LU. Broadcast EBU R128 uses −23 LUFS. Online and social platforms normalise around −14 LUFS. Keep true peak at −1 to −2 dBTP.

### Apply to our tools
1. **`t_music`**:
   - Restructure the prompt as `{genre/era}. {instruments & production}. {BPM} BPM, in {key}. Mood: {…}. Structure: [Intro]->…; timing cues. {Instrumental only | Lyrics:\n…}`.
   - Move `seed` to the API.
   - Turn `negative` into an **exclusion phrase** ("no drums, just piano") for Lyria, and into `negative_styles` for ElevenLabs.
   - For the "pro" tier on ElevenLabs, build a **composition plan** from timestamp sections such as `[0:00-0:20]`, which the UI already suggests.
2. **New helper `score_for_scene(scene)`**, used by `micro_ad`, `t_vi` and the editor's music track: map tone or genre to the BPM, mode and texture table above. Return the cue length aligned to cut points, e.g. "the chorus kicks in at {CTA time}s".
3. **`M.mix`**: target the platform loudness (−14 LUFS for social, −23 for broadcast) with ffmpeg `loudnorm`. Duck music under VO with `sidechaincompress` or a fixed −12 dB. Today `t_vi` uses `music_db=-10` with no ducking.

### Sources
- [Official] Gemini API, *Lyria prompt guide* (Sep 2026) — https://ai.google.dev/gemini-api/docs/lyria-prompt-guide
- [Official] Vertex Lyria prompt guide — https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/music/music-gen-prompt-guide
- [Official] ElevenLabs Music best practices — https://elevenlabs.io/docs/overview/capabilities/music/best-practices ; composition plans — https://elevenlabs.io/docs/eleven-api/guides/how-to/music/composition-plans
- [Industry] Netflix loudness (−27 LKFS, 2 LU window) — https://www.production-expert.com/production-expert-1/how-to-optimise-an-audio-mix-for-delivery-to-netflix
- Juslin & Laukka (2003), "Communication of emotions in vocal expression and music performance", *Psychological Bulletin* 129(5)

---

## 12. AI QC: VLM-as-judge for generated media

### Key facts
- **Dimensions that matter** (benchmarks):
  - **VBench** splits quality into 16 dimensions, including *subject consistency*, *background consistency*, *temporal flickering*, *motion smoothness*, *dynamic degree*, *aesthetic* and *imaging quality*, *spatial relationship* and others, each with its own metric and human validation.
  - **VideoScore** (EMNLP 2024) is trained on 37.6K human-rated videos across visual quality, temporal consistency, dynamic degree, text-to-video alignment and factual consistency. Its Spearman correlation is **77.1**, about 50 points above earlier metrics.
- **Prompt adherence**: break the brief into **atomic yes/no questions** (TIFA, and Davidsonian Scene Graph with dependency-ordered questions so answers stay consistent), then score the share answered "yes". VQAScore, the VLM's P("Yes") for "Does this figure show {prompt}?", beats CLIP-style similarity.
- **Judge reliability** (MT-Bench):
  - Known biases are **position**, **verbosity** and **self-enhancement**, plus weak reasoning.
  - Fixes: swap the order and average, give a reference or rubric, and ask for reasoning before the score.
  - Strong judges reach about 80% agreement with humans, the same as human–human agreement.
  - G-Eval adds two more: chain-of-thought steps per criterion, and a **probability-weighted score** (an expectation over score tokens) instead of one sampled integer.
- **Practical reliability recipe**:
  - Write **anchored rubrics** for each axis, with what a 2, 5 and 8 look like.
  - Score at temperature 0 and require evidence (frame index and the issue).
  - Use **metric gates** for what a VLM judges poorly: ArcFace identity cosine, frame-to-frame DINO/CLIP similarity for flicker, OCR for on-screen text and logos, and blur or sharpness.
  - Take the median of 3 runs, or both orderings for pairwise comparisons.
  - Calibrate the thresholds against about 100 human-labelled outputs.

### Apply to our tools
1. **`qc_score()`**: rewrite it as a pipeline.
   ```
   frames = sample(video, n=12)              # first, last, and evenly spaced; images: [img]
   checks = {
     "identity":   min(arcface_cos(face(f), refs)) per frame          # gate: < τ_id → fail
     "flicker":    mean(1 - cos(clip(f_i), clip(f_{i+1})))            # VBench-style temporal
     "sharpness":  M.sharpness percentile
     "text":       OCR(frames) vs expected on-screen text/logo        # ads & posters
     "safe_zone":  text boxes ∩ platform UI mask                      # §7
   }
   questions = llm("Decompose the brief into ≤12 atomic yes/no visual questions (DSG): entities, attributes, actions, relations, counts, text.")
   adherence = mean(vlm_yes_prob(q, frames))                           # VQAScore-style
   rubric = vlm_json(frames, anchored rubric for: Visual quality, Temporal consistency, Motion realism/physics, Artefacts (hands, faces, morphing, text), Brand & platform fit;
                     "cite frame numbers; score 1–10; 2=…, 5=…, 8=…", temperature=0) × 3 runs → median
   composite = weighted mean; verdict = fail if any gate fails, regardless of composite
   ```
   - Return `issues` with `frame` and `fix` fields that `micro_ad` can feed into the retake prompt, for example "hands morph at frame 7 → simplify the action and add 'hands stay still'".
2. **`t_qc`**: show the gates separately from the composite. Expose `identity`, `adherence` (the share of questions passed, with the list of failed questions) and the axis scores.
3. **`micro_ad` retake loop**: on a QC fail, **change the prompt** following the failure, as Sora advises: freeze the camera, simplify the action, clear the background. Then retake only the failing *shot*, not the whole aspect render as `render(ar, attempt)` does now. Keep the best-scoring take rather than the last one.
4. **Mock mode**: say plainly in the UI that heuristic scores are not QC. Today a sharpness-based score can mark a clip "Approved".

### Sources
- VBench — https://arxiv.org/abs/2311.17982 · VideoScore — https://arxiv.org/abs/2406.15252 · EvalCrafter — https://arxiv.org/abs/2310.11440
- TIFA — https://arxiv.org/abs/2303.11897 · Davidsonian Scene Graph — https://arxiv.org/abs/2310.18235 · VQAScore — https://arxiv.org/abs/2404.01291
- MT-Bench, LLM-as-a-judge biases — https://arxiv.org/abs/2306.05685 · G-Eval — https://arxiv.org/abs/2303.16634
- ArcFace — https://arxiv.org/abs/1801.07698

---

## 13. Colour grading looks

### Key facts
- **Teal & orange**: skin sits on the orange "skin-tone line" of the vectorscope, and teal is its complement. The grade pushes **shadows and backgrounds toward teal or cyan** and **highlights and skin toward orange**, *while protecting skin hue* with a hue or luma qualifier. Saturation rises a little in the skin and teal bands only, and contrast increases moderately. Colourists build it with lift toward teal, gain toward orange, then a secondary on skin. A pure luma split also shifts mid-tone skin, and that is the usual amateur mistake.
- **Bleach bypass** (skip-bleach): silver stays in the emulsion, like **a black-and-white image laid over the colour image**. The result is **lower saturation** (about −30 to −60%), **higher contrast**, deeper blacks, harsher highlights and more apparent grain. Colourists describe "crushed mids, slightly crushed blacks". A digital recipe: blend a desaturated, contrast-boosted luma copy over the colour image in overlay or soft-light at 40–70%, then add a gentle S-curve and a touch of grain. Good emulations restrain the clipping.
- **16mm**: a smaller negative means **coarser, more visible grain** (about 2× the 35mm grain size at the same output resolution), softer resolution, more **halation**, slight **gate weave** (sub-pixel jitter), gentle vignette, lifted blacks and warmer, lower-saturation colour.
- **Halation**: light passes through the emulsion, reflects off the film base and re-exposes the **red-sensitive bottom layer**. You get a **red-to-orange glow around bright, high-contrast edges** such as practicals, specular highlights and skin against backlight. Anti-halation backing reduces it, and some stocks (e.g. CineStill 800T) remove that layer. Halation differs from bloom, which is a neutral glow.

### Apply to our tools
1. **`M.GRADE_PRESETS` / `M.grade`**:
   - *Teal & Orange*: add a skin-protect mask, hue around 10–50° in HSV with moderate saturation, and apply the split only outside it. Push shadow hue to about 180–195° and highlight hue to about 25–35°. Suggested preset: `{"split": 60, "contrast": 15, "saturation": 5, "skin_protect": 1}`.
   - **Add *Bleach Bypass***: `{"bypass": 60, "contrast": 30, "saturation": -45, "grain": 20}`, where `bypass` overlays the luma of a contrast-boosted greyscale copy at `bypass/100`.
   - *16mm Film*: grain `size` should scale with resolution (about 2 px at 1080p, against about 1 px for 35mm), plus `softness 15`, `weave 0.3 px`, `vignette 20` and lifted blacks (+3%).
   - **Halation**: threshold luminance at about 0.8, blur radius 0.5–1.5% of width (today it is `max(h,w)/60`, about 1.7%), tint R:G:B ≈ 1.0 : 0.35 : 0.05, and **screen**-blend instead of adding. Apply it *before* grain.
2. **Sliders**: add `skin_protect` and `bypass`, and offer `grain_size` as an advanced option. Stay deterministic. The AI "lens" pass in `t_grade` is fine for flares, but must not alter the grade.
3. **Video**: run the same `M.grade` per frame with ffmpeg, or export a `.cube` LUT from the preset (colour parts only; grain and halation as filters). A video colour grade is in the spec but missing from the tools.

### Sources
- [Industry] Lift Gamma Gain forum, teal blockbuster look (shadows teal, highlights orange, then secondaries) — http://www.liftgammagain.com/forum/index.php?threads/teal-blockbuster-film-look-i-need-some-help.17352/
- [Industry] Colorist Foundry, Bleach Bypass — https://coloristfoundry.com/filmverse-docs/filmverse-arsenal-1-0-0/fine-tuning-the-look/saturation-density/bleach-bypass/ ; LGG skip-bleach thread — https://www.liftgammagain.com/forum/index.php?threads/how-to-get-the-skip-bleach-look.3824/
- [Industry] Dehancer, halation effect — https://blog.dehancer.com/2021/03/29/halation-effect-what-is-it-and-why-is-it-important-for-the-film-emulation/ ; Photrio discussion of the halation mechanism — https://www.photrio.com/forum/threads/about-blooming-and-halation.208370/
- [Official] Sora 2 "ultra-detailed" grade vocabulary (halation, Pro-Mist, split tone) — https://cookbook.openai.com/examples/sora/sora2_prompting_guide

---

## 14. Smaller tool notes

- **`t_reframe`**: `M.saliency_x` gives *one* crop centre for the whole video. Detect shots, track the face or subject per shot, smooth the path (EMA or a 1 € filter) and allow a cut-to-centre on shot changes. That is the standard auto-reframe approach.
- **`t_adapt`**: also take the platform safe-zone masks from §7, so "Stories 9:16" output keeps text out of the top 14% and bottom 35%.
- **`t_lipsync`**: for still images, generate the talking clip with the dialogue in the prompt (Veo or Kling native audio) when no separate VO is needed. Use the lipsync model only for dubbing. Keep each line short enough to fit the clip (§1: 4 s ≈ 1–2 short lines).
- **`t_voice`**: Gemini TTS takes style as natural language, so the presets work. Add pacing marks (commas, ellipses) and for ad VO aim for about **150 wpm**, or 2.5 words per second, so lines fit shot durations. ElevenLabs v3/v4 supports audio tags such as `[whispers]` or `[laughs]`.
- **`t_ecom_video`**: for the 360° spin, use first and last frames of the same product angle for a seamless loop, plus "locked-off turntable, constant rotation speed, studio cyc". Seedance and Veo both support a first/last frame mode.

---

## 15. Priority list (impact × effort)

1. `qc_score`: multi-frame sampling, ArcFace identity gate, DSG questions and anchored rubric with median of 3 (§12).
2. `t_video` and `camera_prompt`: per-model templates with cinematography first and one move per segment. Resolution, duration and seed go to the API, not prose (§1).
3. Native reference routing in `ctx.cast` / `t_video` (Veo ingredients ≤3, Kling Elements, Seedance `@image` rebound per segment), and no subject re-description in I2V (§1, §3).
4. A `t_casting` character sheet (4–6 angles, neutral grey, even light) stored as the lock (§3).
5. `t_budget`: a dated `PRICES` table ($/s by model, resolution and audio) with `keep_rate` per shot class. Split compute and labour. Fix the `minutes or pages` bug (§5).
6. Remove Sora from routing (API shut down 24 Sep 2026).
7. `cues_from_words` / `write_ass`: Netflix segmentation (42 characters, 2 lines, ≤20 cps, 0.833–7 s, 2-frame chaining). Fix the karaoke timing. Move captions out of the 9:16 UI zones (§8).
8. `micro_ad`: a hook/problem/solution/proof/CTA beat plan in seconds, per-beat VO timing, safe-zone end plate, shot-level retakes with prompt changes (§7, §12).
9. `t_vi` / `key_frames`: an arousal curve from motion, audio RMS, cut density and faces, cutting on shot boundaries, with trailer acts and a title card (§9).
10. `t_doctor`: industry coverage format (grid, Pass/Consider/Recommend for script and writer, Black List-style 1–10 with overall ≠ mean), plus deterministic page and scene stats (§4).
11. `t_story`: beat targets computed from runtime for each structure, and a setup/payoff ledger. Fuller `fountain()` and `fdx()` (parentheticals, transitions, title page, scene numbers) (§4).
12. `t_storyboard` / `t_shots`: shot schema with size, angle, lens, duration, axis side and screen direction. Generate the master first and keep the 180° and 30° rules (§6).
13. `M.grade`: skin-protected teal-orange, a new bleach bypass, physically motivated halation, and grain size by format (§13).
14. `t_thumb` and `t_poster`: three distinct concepts for Test & Compare, a face about 1/3 of the frame with ≤4 words, and a billing block at ≥15% of title height (§10).
15. `t_music` and `M.mix`: Lyria/ElevenLabs prompt order (genre → instruments → BPM/key → structure), ElevenLabs composition plans, an emotion→BPM/mode helper, loudness normalisation and VO ducking (§11).
