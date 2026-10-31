# Spark Station: Product Spec for Rebuilding an Open-Source Equivalent

Source: the public marketing pages of https://www.sparkstation.ai, fetched 2026-10-28 with TinyFish `fetch_content`. The pages covered are the home page, 23 tool pages, 5 persona pages, `faq.html` and `/login`. `/home` returned `login_required`, so no app UI was reachable.

Conventions:
- Text in "quotes" or in lists marked *verbatim* is copied from the site as published.
- **[Inference]** marks anything I deduced. The site does not state it.
- **[Conflict]** marks places where two pages disagree. Rebuild from the dedicated tool page, which is usually newer and more detailed.
- In-app names seen in the FAQ: **Image Studio**, **Videos** module, **Voice** module, **Music** module, **Elements** library, **Assets** library, **Prompt Studio**, **Reverse Prompt Engineer**, **Tools** module (contains Video Editor). The marketing pages also mention a live route, `/micro-ads/home`.

---

## 0. Platform overview (home page)

- Positioning: "AI filmmaking platform that replaces a full crew, script doctor, casting director, cinematographer, colorist, sound designer, ad director, with one model-agnostic pipeline." Script to screen.
- Model wall on the home page, *verbatim*: "Google Veo, Kling AI, Seedance, GPT, Claude, Gemini, Omini". The FAQ adds "OpenAI Sora".
- Stated pillars:
  1. **Character Continuity**: lock face, voice and wardrobe once (note that the home page says "voice" as well).
  2. **Automatic Quality Checks**: "Visual consistency, audio sync, timing and brand alignment are reviewed automatically as your project renders."
  3. **Model-Agnostic**: "switching per task and per scene".
  4. Built by creators.
  5. **Seamless, Minimal-Touch Automation**: "casting, continuity, grading and QC happen automatically in sequence. You review and approve at the moments that count."
  6. **Enterprise Transparency & Control**: per-seat permissions, per-project token and spend tracking, model-access controls, centralized asset management.
- "Quality guardrails" chain (home FAQ): **Story Builder** locks intent → **Script Doctor** reviews pacing, dialogue and continuity → **Prompt Improvement** fixes a raw prompt → **Quality Analyzer** checks outputs against the brief and the locked characters.
- Camera: "Every video generation includes a camera rig with lens, focal length and aperture controls, plus cinematic camera movements such as dolly, orbit, crane and push."
- Marketing flow: "Script (written automatically, straight into a shot list) → Cast (a model or spokesperson) → Shoot (every angle, directed by AI) → QC (checked automatically before an ad ships)".
- Plans:
  - Individual: start free, no card, no seat minimums, pay-as-you-grow token pricing, you own outputs, every module and model from one account.
  - Enterprise: custom packages and volume pricing, asset usage rights and licensing control, content indemnification and IP terms, per-seat permissions, model-access and spend controls, centralized brand asset library, dedicated onboarding.
- Login page: "Sign in with Google or your username and password." Fields are "Username / Email" and "Password", plus a "New to Spark Station?" sign-up link and Terms/Privacy consent. The login carousel caption reads: "CHARACTER CONTINUITY · One face. Every scene. Forever."

---

## 1. AI Image Suite (Image Studio), `ai-image-generation.html`

**Purpose:** generate cinematic stills from text, then edit, upscale, relight, restyle and retouch them with character identity locked. The page claims "16 image tools in one connected suite".

**Inputs:** "Text prompt, reference image, sketch, or an existing frame to edit." The FAQ adds: "pick a model and settings, then describe what you want in the prompt. You can also reference saved Elements with @."

**Models, *verbatim*:** GPT Image, Flux 1.1 Pro, Gemini, Seedance, Omini, Ideogram.

**Resolution:** "512px, 1024px and up to 4K". The FAQ says formats and resolutions "vary by model".

**Export:** PNG / JPG / WEBP, "ready to hand straight to the Video Suite" as first frames.

**Sub-tools.** These are the module tiles and FAQ entries. The page says 16 tools but names only these:

| Sub-tool | Description (site) |
|---|---|
| Image Generation | Text → image. Sample: "A weary detective at dusk, neon rain, 35mm." |
| Turn-to-Model / Model Photoshoot | "Flat product → styled on-model shot." See §12 |
| Multi-Angles | "One face, front · 3-quarter · profile"; "same subject from different camera angles while maintaining the subject's identity" |
| Multi-Shots | "generate multiple framed shots from a single prompt… different coverage of the same scene" |
| Relight | "Daylight → golden-hour, one slider"; "change the lighting direction or lighting appearance" |
| Virtual Try-On | "Same model, three wardrobes." See §11 |
| Draw-to-Paint | "Napkin sketch → finished key frame." See §13 |
| Inpaint | "Removed the wires, seamlessly." See §9 |
| Upscaler | "SD frame → 4K, no artefacts." See §8 |
| Color Grading | "Teal-orange · noir · pastel." See §14 |
| Age Progression | "Same character, age 8 → 60" |
| Reimagine Scene | "Same blocking, new world"; restyle while retaining composition |
| Skin Realism | "Pore-level detail, no plastic sheen" |
| Face Swap | See §10 |
| Casting Director | See §7 |
| Palette Studio | "helps establish and maintain a consistent colour palette across your visual content" |
| Background change | Mentioned only in the FAQ as a sub-tool |

**Workflow:** design the look (pre-production) → build coverage (multi-angle, multi-shot) → finish the frame (inpaint, relight, grade, upscale, skin realism) → hand off to motion as first frames for Video. The FAQ says: "After generating, you can open any result to refine it with a sub-tool."

**Continuity:** Identity Lock, Expression Continuity, Wardrobe Continuity, Location Consistency, Prop Consistency (see §3).

---

## 2. AI Video Generator ("Videos" module), `ai-video-generation.html`

**Purpose:** prompt, or prompt plus reference image or video, to a directed cinematic clip, across multiple models.

**Sub-features:**
- **Prompt Assistant** (FAQ also calls it "Improve prompt" or "Prompt Improvement"): "instant readout of what your prompt is missing, camera direction, lighting, pacing, with a rewritten version you can accept, edit or reject."
- **Camera Rig:** "Choose a camera body, lens character, focal length and aperture." The labels are plain language, e.g. "a 35mm lens labelled 'Natural Cinematic'". The choice is "translated into your prompt for you". **[Inference]** The rig is a UI that produces prompt fragments.
- **Camera Movement Library:** "Preview cinematic moves before you use them, pans, tilts, dollies and specialty moves, then tap to add." Moves named across the pages: pan, tilt, dolly, orbit, crane, push, whip pan. Sample captions use: Push + Reveal, Handheld Push In, Slow Push In, Track + Whip Pan, Orbit + Crane, Dolly In, Continuous Push, Macro Drift, Dolly Out, Orbit, Continuous Zoom.
- **Multi-Model Studio:** "Generate the same prompt across multiple leading AI video models and pick the take."
- **Style Presets:** "from cinematic realism to anime to region-specific looks". The full list is not published.
- **Flexible Output & Native Audio:** optional AI audio, "on by default".

**Controls (step 4):** "Choose the AI model, aspect ratio, duration, resolution, and whether to generate audio."
- Aspect ratios: **16:9 · 9:16 · 21:9 · 4:3 · 1:1 · 3:4**
- Duration: **up to 15 seconds**
- Resolution: **480p · 720p · 1080p · 4K**
- Audio: AI-generated, on by default
- Models: "Google Veo, ByteDance Seedance, Gemini Omni Flash and OpenAI Sora". The home page and FAQ also list Kling.

**Inputs:** prompt (typed or pasted from a script), optional reference image or clip. A locked character from §3 carries into video.

**Output:** a clip that "will appear in your history when it's finished". **[Inference]** MP4, since the FAQ lists MP4 as the video format.

---

## 3. Character & Scene Continuity (5 locks), `ai-character-consistency.html`

**Purpose:** five independent, persistent locks that apply across images and video.

1. **Character Identity:** face, bone structure and distinguishing features. "Set once, from the Casting Director lineup."
2. **Expression Continuity:** emotional range without reshaping the face. The page shows "nine real emotional states".
3. **Costume & Wardrobe Continuity:** garment shape, color, texture, accessories ("continuity binder").
4. **Location Consistency:** architecture, props, lighting logic, layout. Works for real and invented locations.
5. **Property & Object Consistency:** a hero prop or product (hardware, stitching, strap length, label, packaging).

**Workflow:** cast and lock identity → lock the expression range → lock wardrobe and location ("Set a specific outfit and a specific set once, and reuse both across every angle") → lock props and generate.

**How it is implemented in the app (FAQ):** the **Elements library**. "Open Elements and create a new Element by naming it and adding reference images of your character", then "type @ followed by the Element's name" in Image Studio or Videos prompts. Elements can hold "characters, objects, or styles". Assets can be added "to an Element". Elements persist across projects.

**[Inference]** For a rebuild: an Element is a named record holding reference images and a type (character, object, style, location, wardrobe). An `@mention` in the prompt injects the reference images and descriptors into the model call. The five locks are probably Element types or attributes, not separate engines.

---

## 4. AI Ad Generator / Ad Factory (5 studios), `ai-ad-generator.html`

Hero sample: "Input · Product Data: Philips Air Purifier · Series 800i → Output · Finished Ad: 15s · 9:16 & 16:9 · QC 7.4/10 ✓".

### 4.1 Micro Ad Factory (autonomous video ad)
- **Inputs:** "product images and key specs, category, brand, size, audience, platform, tone". Persona pages say it can also start from "a single product link".
- **Output:** a 15-second video ad in **9:16 and 16:9 rendered simultaneously**, with an end plate.
- **8-step agent pipeline, *verbatim*:**
  1. Product understanding: "category, USP, target emotion and brand tone"
  2. Audience mapping: "target group, platform norms, cultural context and attention patterns"
  3. Script & dialogue: "15-second narrative arc, voiceover text and on-screen dialogue lines"
  4. Model & casting: "AI talent, age, look and style"
  5. Costume & styling: "wardrobe, colour palette and styling"
  6. Location & set design: "virtual set, lighting mood, background and scene environment"
  7. Visual creation, shot by shot: "composition, motion and product placement"
  8. End plate creation: "product name, price, caption and CTA overlay"
- **Optional QC and auto-regeneration:** composite score across five dimensions: **Prompt adherence, Physics & realism, Visual quality, Brand alignment, Platform fit**. Example scores are 8.2 / 6.8 / 7.9 / 7.6 / 6.7, composite 7.4/10 "Approved". The threshold is configurable from 0 to 10. If the score falls below the threshold, the ad is regenerated automatically.
- Claimed stats: 3.2× CTR, 138× lower cost, 98% pass QC on the first or second try, 5 minutes, 100,000+ videos/month. Comparison table: agency ₹2-5L, AI-assisted ₹25-30K.
- Sample tags (platform · category): YouTube, LinkedIn, Facebook, Instagram, Instagram Reels, TikTok, Facebook Stories, YouTube Shorts × Food & Beverage, Electronics, Home Decor, Apparels, Fashion, Food.

### 4.2 Ecommerce Image Studio
Flow: pick a scenario → upload product images → one-click generate. Scenario library, *verbatim*:
- **Model try-on:** Studio try-on (flat clothing → model on studio bg); Lifestyle try-on (flat clothing + optional texture ref); Accessories on-model (glasses, jewellery, hats, headphones); Try-on with your own model (product + real model photo, "preserves the exact face").
- **Lifestyle & usage:** Handheld display; Usage demo; Scene composite; Flat lay; 360° multi-angle grid (front, side, rear, sole/back); Outdoor lifestyle (beach, café, park, street).
- **Marketing assets:** Dynamic VFX poster; Technical schematic (dimension arrows, comparison objects: coin, hand, phone); Promo banner (multi-product, headline, CTA, pricing, multi-language); Colorway variants (swatches); Gift packaging; Technical infographic (blueprint overlay, callouts, part labels, sketch title box); Before & after; Zoom detail shot; Ingredient explosion; Unboxing reveal; Clean hero shot (lifestyle → white or minimal studio).

### 4.3 Ecommerce Video Studio
Scenarios, with inputs → output:
- **360° View:** Product 360° Studio (4 product angles → studio rotation); 360° + Interior Reveal (exterior angles + interior details); 180° + Texture Zoom (detail shot + 3/4 angle + top/flat view).
- **Try-On:** Clothing try-on (flat-lay + optional model ref); Accessories try-on (multiple angle shots); Accessories action sequence (product + model portrait + wearing reference).
- **Showcase:** Multi-angle fashion showcase (front, side and back model shots → one continuous showcase).
- **Lifestyle:** Handheld product display (white-bg product + lifestyle ref); Product ad storyboard (two lifestyle images → storyboarded sequence); Product usage demo; Scene compositing (product + room placement + character ref).
- **Before & After:** Before & after results.
- **Post-Production:** Remove elements (source video → unwanted elements removed).

### 4.4 UGC Ads Studio: 17 formats in 6 categories
Flow: "Pick a format, add product details, generate."
- **Selfie & Talking Head:** UGC; Direct-to-camera; UGC Addiction
- **Testimonial & Story:** "This gadget saved me"; Couple sharing at home
- **Unboxing & Reveal:** Unboxing; Unboxing ASMR; Reboxing; Gift unboxing
- **Try-On:** Virtual try-on sneakers; UGC virtual try-on
- **Tutorial & How-To:** Secret hack reveal; Before and after; Tutorial
- **Cinematic & Brand:** Hyper Motion; TV Spot; Wild Card

### 4.5 Video Batch Generation
- Upload an **Excel or CSV** file. Each row is queued automatically and gets a **batch ID**.
- Status per item: **queued → processing → QC → complete**.
- **Required column:** `product_name`. **Optional columns:** product category, brand, specification, product image URLs, ad type, target audience, ad duration, end-plate image.
- Each row runs through the same pipeline as a single ad (Micro Ad Factory).

Shared workflow: pick a studio → add product (images, name, category, brand, specs, audience, platform) → generate (vertical and horizontal in one run) → optional QC → deliver.

---

## 5. AI Pre-Production (4 stages), `ai-preproduction-tools.html`

Data flow: Story Builder → **Production Pack** → Script Doctor → **Coverage + Production Footprint** → Storyboard Builder → **Shot List + Style Frame** → Budget Estimator → **Line-by-line Budget**.

### 5.1 Story Builder
- **Input:** a brief that is "typed, pasted or read from a file", in the language of your choice.
- **Forms:** "Two dozen forms" (24). Chips on the page: Short film, Feature screenplay, Series bible, Microdrama series, Ad film, Documentary, Novel, Comic script. The full list from the FAQ: short film, feature screenplay, TV episode or pilot, series bible, microdrama series, vertical short; documentary, advertising and music-video forms; art and experimental films; prose from flash fiction to novel; stage plays, audio drama, comic scripts.
- **Structures** per form: "from three acts to two halves around an interval to pieces where nothing needs to happen at all".
- **Steps:**
  1. **Read my intent:** form, structure, what must happen, what must never happen, all locked before anything is written.
  2. **Outline:** editable.
  3. **Draft & review:** each part is written with the earlier parts in context and checked against intent. An "independent review lists what to fix".
  4. **Handoff:** a production pack plus exports.
- **Production pack fields:** Title, logline & runtime; Cast; Wardrobe; Locations; Props; Lighting & palette; Camera & lenses; Scenes.
- **Exports:** **Fountain, FDX, CSV, Markdown, JSON**.
- **Extras:** translate into another language "as a linked copy"; "talk it through in the writers' room" (**[Inference]** a chat panel); find versions in **History**.

### 5.2 Script Doctor (script coverage)
- **Input:** paste a script or upload a file, pick a genre, and choose which analysis dimensions to run.
- **16 dimensions, *verbatim*:** Script Score (core); Scoring Traceability (NEW); Character Arc Integrity (NEW); Setup / Payoff Ledger (NEW); Story Timeline & Scene Utility (NEW); Audience Retention; Cliffhanger Analysis; Emotional Heatmap; Pacing Rhythm; Dialogue / Action Balance; Character Screen-Time; Theme / Motif Consistency; Genre-Convention Adherence; Structural Beat-Mapping; Production Footprint (NEW); Casting Suggestions. **[Conflict]** The spec strip on the same page says "24 dimensions".
- **Score:** an overall score out of 100 (example 73) with axes **Structure, Pacing, Originality, Character Depth, Dialogue, Theme** (example 85/80/65/60/75/70). Each axis has a weight, a confidence level and the cited script line, "sorted so the highest-leverage rewrite target sits at the top".
- **Setup/Payoff Ledger:** each thread is tagged (e.g. EARNED) and gets a description.
- **Character Arc Integrity** includes "a relationship map".
- **Production Footprint:** interior/exterior split, dialogue/action/mixed scene mix, number of distinct locations, flags for stunts, pyrotechnics and VFX-dependent sequences.

### 5.3 Storyboard Builder
- **Input:** story, script, synopsis or bare concept.
- **Steps:**
  1. **Story:** break the input into a shot list, picking up cast and locations automatically.
  2. **Look:** pick an art style and draw one **style frame**, which is attached to every character sheet and panel.
  3. **Board:** one panel per shot, laid out page by page in the board's aspect ratio. Any panel can be redrawn individually.
- **Art styles:** Pencil Sketch, Watercolour, Ink & Wash, Graphic Novel, Cinematic Photoreal.
- **Shot grammar examples:** Wide Establishing Shot, Medium Shot, Insert Shot, Two-Shot, Close-Up, Over-the-Shoulder.
- **Output:** 9-panel pages. Export as **PDF, PNG pages, CSV shot list**.

### 5.4 Budget Estimator
- **Input:** describe the project (film, ad, series, micro drama; length, languages, quality level) or upload the script.
- **Stages costed:** Pre-Production, Production, Post-Production, Distribution, People, Contingency. The page also claims "9 costed categories".
- **What it counts:** Episodes & minutes; Quality level; Dubbed & subtitled languages; Extra sizes; Trailers, teasers & recaps; Thumbnails & posters.
- **Take multiplier:** it "counts the takes a usable shot really needs at each quality level, and more when there are recurring characters, lip-synced dialogue or action". The FAQ calls this "per-second cost and wastage modelling".
- Persona pages say voice-over, music, SFX and dubbing are each priced as line items "per finished minute".
- **Currencies:** USD, INR, AED, GBP, EUR. Any number can be edited, with instant recalculation. Versions can be saved. **Export: CSV, Word, PDF.** Turnaround is "~60s".

---

## 6. AI Voice Generation (Voice module), `ai-voice-generation.html`

- **Fields:** **Script** (text); **Model**; **Voice** (picked in a "Choose a Voice" modal); **Language** (free text with autocomplete, default "English (US)"); **Style Instructions** (free text, default "Read aloud in a warm, welcoming tone").
- **Models (4):** Gemini 2.5 Flash Lite (Preview); **Gemini 3.1 Flash TTS (Preview, default)**; Gemini 2.5 Pro TTS; Gemini 2.5 Flash TTS.
- **Style presets (6):** Measured, Ad Voice, Documentary, News Anchor, Casual, ASMR.
- **Voices (30: 14 female, 16 male).** The modal has a search box, All/Female/Male filter pills and a ▶ preview per voice. Names, *verbatim*:
  - Gendered sample: Achernar (F), Achird (M), Aoede (F), Algenib (M), Autonoe (F), Charon (M), Despina (F), Erinome (F), Fenrir (M), Kore (F), Puck (M), Pulcherrima (F), Schedar (M), Sulafat (F), Zubenelgenubi (M).
  - Remaining 15, gender not stated: Algieba, Alnilam, Callirrhoe, Enceladus, Gacrux, Iapetus, Laomedeia, Leda, Orus, Rasalgethi, Sadachbia, Sadaltager, Umbriel, Vindemiatrix, Zephyr.
  - **[Inference]** These are the Gemini TTS prebuilt voice names, so a rebuild can map them 1:1.
- **History:** List and Grid views, plus Refresh. Each row shows a title, the transcript, and chips for voice, language, duration and model. Actions: play, download, copy-transcript, edit (rename), delete.
- **Output:** an audio clip. The format is not stated (**[Inference]** WAV or MP3).

---

## 7. AI Casting Director, `ai-casting-director.html`

- **Inputs:** story or scene text; character description (age, look, wardrobe, defining features); optional reference image (PNG, JPG, WEBP); visual style; candidate count.
- **Candidates per run:** 2 · 4 · 6 · 8.
- **Image models:** GPT Image, Flux 1.1 Pro.
- **Resolution:** 512 · 1024 · 2048 px.
- **Styles (20+):** "Live-action realism, cinematic and documentary looks, 2D and 3D animation, anime, cartoon, comic-book, storybook, fantasy, mascot, creature, stop-motion and concept-art, or Auto". Sample labels: Cinematic Realism, Documentary Realism, Anime, Mascot Design, Fantasy, Realistic Casting.
- **Flow:** describe → pick style and count → review the side-by-side lineup and regenerate → **lock** your pick. The locked identity feeds the Character Continuity Lock (§3) for image and video, and is handed to UGC Ads Studio and Ecommerce Video Studio.
- **[Inference]** Locking creates a character Element.

---

## 8. Upscale, `ai-upscale.html`

- **Input:** a source image (drag, drop, browse or Ctrl+V paste).
- **Controls:** output size **2x** (quick bump) or **4x** ("print-ready or high-DPI outputs"); **number of variations** per run.
- **Output:** the upscaled image(s). The FAQ elsewhere says "up to 4K".
- Upscale is placed at the end of the workflow: Virtual Try-On and Model Photoshoot point to it.

## 9. Inpaint, `ai-inpaint.html`

- **Input:** an image (drag, drop, browse, paste) → **paint a mask** → a **short text prompt** for the masked area → generate.
- Example prompts, *verbatim*: "Add a clock here", "Place a rose", "A decorative item", "Place a bunch of bananas", "Ghost".
- Used for both removal (describe the background to fill) and addition. It matches lighting and perspective.

## 10. Face Swap, `ai-face-swap.html`

- **Inputs:** a **target image** and a **reference portrait**.
- **Output:** the swapped image, preserving the original scene lighting and the subject's expression. There is no manual masking.
- The page shows a responsible-use notice (rights and consent, no impersonation).

## 11. Virtual Try-On, `ai-virtual-try-on.html`

- **Inputs:** a **character photo** and **one or more garment images** (PNG, JPG, WEBP). Several garments can go in one run.
- **Output:** a **full grid of outfit variations** ("a full grid of poses"). Next step: Upscale the keepers.

## 12. Model Photoshoot (formerly Turn-to-Model), `ai-model-photoshoot.html`

- **Inputs:**
  - **Person reference** (required; PNG or JPG; a single, clear, well-lit face).
  - **Apparel references** (optional; jackets, tops, bottoms, shoes, accessories).
  - **Location references** (optional; they override the preset environment).
  - **Shoot Options:** a photo-count **slider**.
  - **[Inference]** A style picker. The site says "the in-app picker offers more range than shown".
- **Observed styles:** Neon night, Golden hour outdoor, High contrast B&W, High fashion editorial.
- **Output:** a set of styled fashion photos in one run, "multiple looks and formats".

## 13. Draw to Paint, `ai-draw-to-paint.html`

- **Start modes:** **Upload Media** (PNG, JPEG, WebP) or **Create Blank**.
- **Canvas ratio:** 16:9 (Widescreen), 9:16 (Vertical), 1:1 (Square), 4:3 (Classic), 3:4 (Portrait).
- **Action:** sketch, annotate or compose on the canvas → generate a polished image. Tagline: "sketch, annotate and compose on any image. AI generates your vision in seconds."
- **[Inference]** There is likely an optional text prompt alongside the sketch. It is not stated.

## 14. Color Grading, `ai-color-grading.html`

- **Input:** an image.
- **Presets:** Natural, B&W Film, Split Tone, Soft Skin, Cinematic, 16mm Film, Old Lens, None. The site notes one more preset with an illegible label.
- **Color Correct panel sliders:** Temp, Hue, Saturation, Contrast, Split Tone.
- **Toggleable groups**, each with sub-controls: Soften Details, Bloom, Halation, Lens Instructions, Exposure, Film Grain.
- **Before/after compare** → generate. The grade is not a LUT import (no .cube files).
- **[Inference]** "Generate" and "Lens Instructions" suggest the grade is applied by a model, at least partly, rather than purely by pixel math.

---

## 15. Video Editor (in the "Tools" module), `ai-video-editor.html`

- **Media:** upload video, audio or images to the project bin. Uploads are resumable and deduplicated. Each file gets a proxy, waveform and filmstrip. The library spans projects and supports user folders.
- **Projects:** autosave with named versions. There are "6 project formats" (**[Inference]** aspect presets; persona pages list 16:9, 9:16, 1:1, 4:5).
- **Timeline:** multi-track (T1 titles, V1 video, A1 audio). Tools: Select, Razor, Snapping, Ripple, Markers, per-track Mute · Solo · Lock, J · K · L shuttle, Scene cuts (scene detection marks cuts), remove silences from a clip's waveform in one step.
- **Transitions (28):** fades to black or white, wipes and slides in 4 directions, smooth pushes, circle, rectangle and diagonal reveals, radial wipe, pixelate, dissolve. Examples shown: Fade, Dissolve, Wipe left, Smooth right, Circle open, Pixelize. The preview "uses the same maths as the export".
- **Colour looks (12):** examples None, Cinematic, Teal, Warm, Vintage, Noir, plus "mono" in the FAQ.
- **Inspector, per clip:**
  - Picture: position, scale, rotation, crop, flip; Ken Burns for stills; opacity; speed 0.1×–8×; colour controls, blur, sharpen, vignette, green-screen key.
  - Audio: volume, pan, EQ, denoise, clarity, echo.
  - Everything can be keyframed.
- **Text:** 7 presets: Title, Lower third, Subtitle, Chapter card, Quote, Credits roll, Caption. 19 bundled fonts, with in and out animation.
- **Transcripts:** **ElevenLabs Scribe** or **OpenAI Whisper**, word-timed. You can search, delete words to cut them, remove filler words, set in and out points, turn a line into a title, lay down a captions track, and export SRT or VTT.
- **AI:** each paid button shows its credit cost first.
  - **Copilot:** a plain-language request returns proposed edits (splits, trims, moves, deletions, titles, transitions, markers) that you review and apply. Model choice: "Gemini, GPT-5.6 Luna or Claude Opus 5.5".
  - **Watch:** Gemini logs every shot (what is said, what is on screen). The log is searchable and the Copilot reads it.
  - **Motion graphics:** 10 presets (listed: Opening title, Lower third, Logo reveal, Kinetic quote, Animated chart, Map route, End card). Describe it, the AI designs it, you iterate, and it lands as a clip, optionally with a transparent background.
  - **Voice-over:** generated with ElevenLabs and added to the bin.
- **Export:** rendered server-side, so you keep editing; an ETA is shown and you are notified when it is done.
  - Video: MP4 (H.264 + AAC). Audio only: WAV, MP3, AAC.
  - Sizes: 540p, 720p, 1080p, 1440p, 2160p.
  - Quality: draft, high ("High (CRF 19, recommended)"), master.
  - Loudness targets: "-14 LUFS, YouTube and social", podcasts, broadcast.
  - Also: captions as SRT or VTT, the cut as an EDL.
- **Hand-off package:** a zip containing the timeline (XML for Premiere Pro and DaVinci Resolve, FCPXML for Final Cut Pro), titles, and the media (originals or proxies).
- **Pricing:** editing, saving and exporting are free. The AI features use credits.
- **[Conflict]** The persona pages describe an older editor: "unlimited tracks, linked audio, Split/Delete/Marker/Loop toolbar, six transition styles set independently in and out per clip, per-clip properties (opacity, scale, crop, filter presets, brightness/contrast/saturation/vignette), 12 fonts, live aspect-ratio switcher 16:9, 9:16, 1:1, 4:5". They also say "local MP4" export and "Send to Editor" with manual format (XML, FCPXML, EDL) and frame-rate choice. On that path cut points, track order and markers carry over, but transitions and per-clip audio levels do not.

## 16. Subtitle Creator, `ai-subtitle-creator.html`

- **Input:** a video or audio file up to **10 hours and 5GB**, in one pass with no chunking. Alternatively, **Import SRT/VTT** to skip transcription. Button: "Extract audio & transcribe".
- **Privacy:** the video is processed on the device; only the extracted, compressed audio goes off-device.
- **Transcription options:**
  - Word-level timestamps; speaker labels.
  - **Caption rhythm, 7 modes:** Sentence, line, 1/2/3/4/6-word bursts.
  - **Max chars per line:** default 42, adjustable 20–60.
  - **Custom vocabulary hint.**
  - **Sound-cue tags** ((laughter)/(applause)/(music)) and **profanity censoring**, each toggled independently.
  - **Sync tools:** shift all cues, snap to playhead, auto-fit to detected audio length.
- **Translation:** 60+ languages in one batch. Each language becomes its own editable tab with identical timestamps. RTL layout applies automatically for Arabic, Hebrew, Persian and Urdu. Translation is idiomatic, and proper nouns, numbers and speaker tags are preserved. Listed languages: English (source), Hindi, Tamil, Telugu, Malayalam, Kannada, Marathi, Gujarati, Bengali, Punjabi, Urdu, Spanish, French, German, Italian, Portuguese, Russian, Chinese, Japanese, Korean, Arabic, Turkish, Vietnamese, Thai, Indonesian, "+38 more, including Nepali, Sinhala, Swahili, Hebrew, Persian, Ukrainian and Filipino". The FAQ adds Odia and Assamese. **[Conflict]** Persona pages and the editor page say "32 additional languages / 33 total". The dedicated page says 60+.
- **Style presets (12):**
  - OTT & Theatrical: Cinema Standard, Lower Third.
  - Reels & Social: Bold Pop, Punch Green, Neon Glow, Podcast Yellow, Karaoke Fill, Comic Punch, Underline Beat.
  - Corporate & Documentary: Clean Broadcast, Subtle Box, Typewriter.
- **Custom style controls:** font (19 families), weight, case, size, letter spacing, line height, fill color, stroke, drop shadow, background box, **6 word-highlight modes** (including karaoke fill and reveal-as-spoken), **5 entrance animations**, alignment, position. Sizes are a percentage of frame height. Custom presets can be saved.
- **Aspect ratios:** 16:9, 9:16, 1:1, 4:5.
- **Finish options:**
  - **Burn in:** re-encodes in the browser, capped near 2GB. Quality presets Fast, Balanced, Best. A live estimate (resolution, duration, time range) is shown first.
  - **Soft subtitle track:** stream copy, under one second, lossless.
- **Export formats (6):** burned-in MP4; MP4 with soft track; caption-layer project file (cues, word timings and style, re-openable; the site labels it "SS" and also lists JSON); ASS (styled, with karaoke tags); SRT and WebVTT; TXT (no timecodes).
- **[Inference]** The architecture is browser-side ffmpeg.wasm for audio extraction and burn-in, plus a server-side ASR call.

## 17. Thumbnail Creator, `ai-thumbnail-creator.html`

- **Input:** a topic or description of what the thumbnail is for. Optionally a reference image, or key frames from Video Intelligence for the collage styles.
- **Step 1, Style.** "Auto (best fit for topic)" is the default. 16 templates in 5 categories:
  - **Face & Reaction:** Auto, Reaction Close-Up, Curiosity Hook, Vibrant Everyday
  - **Object & Product:** Hero Object, Bright & Clean
  - **Comparison & Proof:** Before/After Split, Versus Color-Block, Big Number/Stat
  - **Mood & Atmosphere:** Minimalist Clean, Cinematic Dark, Neon Dark Mode
  - **Collage & Multi-Frame:** Grid Collage, Overlapping Photo Stack, Main + Inset, plus "Upload reference image…"
  - The collage templates can use extracted video key frames. The others work from the topic alone.
- **Step 2, Size:** 16:9 YouTube & Facebook; 9:16 Shorts/Reels/Stories/TikTok; 1:1 Instagram & Facebook Feed; 16:9 LinkedIn Video "with a mirrored safe zone". All sizes are generated together.

## 18. Poster Creation, `ai-poster-creation.html`

- **Input:** any uploaded video (no length limit). It "uses the strongest key frames found inside it".
- **Style.** "Auto (random each time)" is the default: a genre-matched style picked at random. 16 templates in 5 genre categories:
  - **Thriller & Drama:** Auto, Neo-Noir, High-Contrast Thriller, Prestige Drama
  - **Action & Sci-Fi:** Blockbuster Action, Sci-Fi / Tech-Noir, Gritty Dystopian
  - **Comedy & Feel-Good:** Sun-Drenched Indie, Bright Comedy, Pastel Romance
  - **Horror & Fantasy:** Horror Minimalist, Epic Fantasy, Folk Horror
  - **Documentary & Minimal:** Documentary Realism, Minimalist Art-House, Retro Pulp
  - **Custom:** Upload reference poster…
- **Formats (6, generated together):** Theatrical 2:3; Vertical Social 9:16; Square 1:1; Landscape 16:9; Cover Banner (Facebook or Twitter/X cover); Print (A4 portrait).
- **[Inference]** Title and credit text are not mentioned as inputs. A rebuild would likely need them.

## 19. Resize & Repurpose, `ai-resize-and-repurpose.html`

### Adapt (images)
- **Steps:** upload image → pick sizes (16-tile grid, multi-select, **Select all**, running count) → **Adaptation Method** → **Subject Focus** → generate.
- **Sizes:** 16 sizes across 27 placements, grouped into 9 ratio cards:
  - 9:16 Vertical/Stories (YouTube, Instagram, TikTok, Facebook, X, +1)
  - 1:1 Square (Instagram, Facebook, X, YouTube, LinkedIn, Pinterest)
  - 16:9 Landscape (YouTube, X)
  - 1.91:1 Link preview (Instagram, Facebook, LinkedIn)
  - 4:5 Portrait feed (Facebook, Instagram, LinkedIn)
  - 2:3 Tall Pin (Pinterest)
  - 4:15 Skyscraper banner, 6:5 Rectangle banner, 8.09:1 Leaderboard banner (Display)
  - **[Inference]** The pixel sizes are probably IAB 160×600, 300×250 and 728×90.
- **Method:** **Extend canvas** (default; generative outpaint that keeps 100% of the original) or **Smart crop**.
- **Subject focus:** Left / **Center (default)** / Right.

### Video Reframe
- **Input:** MP4, MOV, MKV, MXF, MTS. Up to 20 sizes per run.
- **Ratios (14):**
  - Social: 9:16 · 4:5 · 1:1 · 2:3 · 3:4
  - Broadcast: 16:9 · 4:3 · 3:2 · 5:4
  - Cinema: 1.85:1 · 1.9:1 · 2:1 · 21:9 · 2.39:1
- **Output resolution:** 480p for a quick test, 720p for delivery.
- **Placement:** **Auto** (default; reads the video scene by scene, with an optional editable "scene reading" before the run); **Centre**; or a custom position via slider, fixed for the whole video.
- **Compare and Checks:** side-by-side review against the source. Each size can be regenerated or resumed.

## 20. AI Video Intelligence, `ai-video-intelligence.html`

- **Input:** long-form uploaded or linked video (match, stream, event, dailies). No pre-editing needed.
- **Pipeline stage names:** **Frame Extractor → Key Frames → Key Moments & Highlights (scored for narrative or excitement) → Generate**.
- **Create Reel.** Parameters:
  - **Mode:** Teaser (15–30s, "A handful of moments. Withholds the story."), Trailer (60–90s, "Full beat arc, rising intensity."), Reel (15–60s, "Punchy highlight cut for social").
  - **Genre (9):** Documentary, Drama, Horror, Action, Thriller, Comedy, Romance, Sci-Fi, Fantasy.
  - **Target audience (5):** Kids, Gen-Z / Youth, Young Adults, Family / General Audience, Mature / Older Audience.
  - **Length:** the headline says "you choose the mode, genre and length".
  - An AI editor picks the segments.
- **Create Thumbnail** from key frames: Grid Collage, Overlapping Photo Stack, Main + Inset, Upload reference image. Sizes: YouTube 16:9, Shorts/Reels/TikTok 9:16, Instagram Feed 1:1, LinkedIn 16:9 with mirrored safe zone.
- **Poster Creation** from the same frames. Uses: Premiere Announcement, Event Recap, Highlight Package Key Art.
- FAQ names for sub-features: "Highlights Reel", "Teaser & Trailer Generator".

## 21. AI Comics Generator, `ai-comics-generator.html`

- **Step 1, inputs:** story, script or premise; art style (1 of 12); page count (no limit); panels-per-page band **3-4 / 5-6 / 7-8** (the AI chooses the exact count and layout per page); orientation **Portrait / Landscape / Vertical Scroll**; optional **Character Reference Photo** ("used in every page prompt for consistency").
- **Step 2, plan editor:** each page has an AI-written synopsis and a title. Each panel has **Scene**, **Characters**, **Camera**, **SFX** (e.g. "KRA-BOOM!", "BEEP BEEP") and multiple **dialogue lines**, each with type, speaker and text. Pages and panels can be added or removed. All of it is editable before rendering. Example: "The Shadow King" (Noir B&W).
- **Step 3:** render all pages in one pass.
- **Step 4:** read in **Scroll** mode (page titles shown) or **Flipbook** mode (prev/next, page dots). **Export PDF.**
- **Styles (12):** Manga (Japanese B&W ink, screen-tones); Webtoon (Korean full-colour, vertical scroll); American Comics (Ben-Day dots, primary colours); European BD (clear-line, Tintin/Moebius); Graphic Novel (painterly); Noir B&W; Dark Fantasy; Sci-Fi Epic (neon, widescreen); Retro Pop Art (Lichtenstein dots); Watercolor; Cartoon Adventure (Saturday-morning thick outlines); Pixel Comic.

## 22. Visual Explainer Studio, `ai-visual-explainer-studio.html` (free, no login, BYO OpenAI key)

- **Start modes:** Topic mode (type a topic, paste notes, upload a doc or PDF, or a photo of handwritten notes; PDF parsing and OCR run locally in the browser) or **Photo mode** (restyle an uploaded photo).
- **Commands:** 109 in 8 categories, with counts. Only the named examples are listed here.
  - **Study Formats (4):** Cheat Sheet, Blueprint, Flashcards, Mind Map.
  - **Visual Learning (12):** Flowchart, Infographic, Roadmap, Timeline, Comic Explainer, Classroom Poster, Chart/Graph, Dashboard, …
  - **Notes & Study Styles (8):** Handwritten Notes, Sketchnote, Whiteboard, Blackboard/Chalkboard, Doodle Notes, …
  - **Technical & Object Viz (15):** X-Ray, Cutaway, Exploded View, Cross-Section, Isometric, System Diagram, Wireframe, …
  - **Comparison & Decision (9):** Compare (A vs B), Pros & Cons, Myth vs Fact, Decision Tree, Comparison Matrix, SWOT Analysis, …
  - **Planning (8):** 30-Day Plan, Action Plan, Step-by-Step, Strategy Map, Funnel, Org Chart, …
  - **Creative Visualization (11):** Comic Panel, Storyboard, Pencil Sketch, Poster, Diorama, Miniature World, Fantasy Map, Album Cover, Moodboard/Scrapbook, …
  - **Photo Style Transform (42):** Action Figure, Anime, Studio Ghibli-Style, plus Toy, Plushie, Clay, Building-Block, Pixel Art, 8-Bit, Manga, Cartoon, Stylized 3D, Photorealistic, Cinematic, Film Noir, Cyberpunk, Steampunk, Fantasy World, Medieval, Vintage, Polaroid, Oil Painting, Watercolor, Macro, Fisheye, Sticker, Emoji, Logo, Colorize, Restore, Upscale, Remove Background, Change Background, Vinyl Figure, Collectible Doll Box, Trading Card, Caricature, Royal Portrait, Vaporwave, Double Exposure, Historical Era, Retro VHS Cover. The page also mentions Claymation.
  - Dual-mode commands, which work on a topic or a photo: X-Ray, Blueprint, Exploded View, Cutaway, Diorama.
- **Prompt template, *verbatim*:** `Turn "{topic}" into a {command}. {command instructions}`
- **Generation:** the OpenAI Images API is called directly from the browser with the user's key; the browser can optionally remember the key. Without a key, "Copy the engineered prompt" and paste the resulting image back. Results are saved to an in-browser library or downloaded.
- **Aspect ratios:** the page says "6 aspect ratios" but does not list them.

## 23. Cross-tool helpers mentioned only in the FAQ and home page

These are not covered by the tool pages above. Build them as shared services.

- **Prompt Studio:** "production-ready prompt templates that users can adapt". Also used to "refine your prompt before generating".
- **Prompt Improvement / Prompt Assistant / "Improve prompt":** an LLM rewrite of a raw prompt, with accept, edit or reject.
- **Reverse Prompt Engineer:** "upload an image to get a prompt that can recreate its style". The home page says it turns "any reference image or video into a working prompt for the model you choose".
- **Quality Analyzer:** "checks generated content against the brief and locked characters and can flag consistency or brand-alignment issues". The Micro Ad Factory QC uses five scored axes (§4.1).
- **Sound effects:** the FAQ says "Spark Station provides AI-generated sound effects". There is no dedicated page.
- **Dubbing:** appears only as a Budget Estimator line item.

---

## 24. Persona pages: which tools each bundles

All five pages use a "6 connected stages, 14 tools, one login" frame, and each says every tool has its own free-to-start entry point. The 14 tools are: Story Builder, Script Doctor, Storyboard Builder, Budget Estimator, Casting Director, Character & Scene Consistency, AI Image Generation, AI Video Generation, Video Editor, Subtitle Creator, AI Video Intelligence, Thumbnail Creator, Poster Creation, Resize & Repurpose. The Ad Factory studios count as additional tools on some pages.

| Persona | Stage 1 | Stage 2 | Stage 3 | Stage 4 | Stage 5 | Stage 6 | Headline stats |
|---|---|---|---|---|---|---|---|
| **Filmmakers** | Ideate: Story Builder (Fountain/FDX) | Plan: Script Doctor, Storyboard Builder, Budget Estimator | Cast & lock: Casting Director, 5 locks | Generate: Image Suite, Video Gen (genre samples: Sci-fi, Horror, Courtroom drama, Action/thriller, Fantasy, Crime/heist) | Edit/caption: Video Editor (NLE handoff), Subtitle Creator | Package: Video Intelligence, Thumbnail, Poster, Resize | 6 stages, 14 tools, 5 locks, 3 NLE formats, 33 subtitle languages |
| **Marketers** | Generate on-brand creative: Image + Video (Product shots, Lifestyle scenes, Video hero clips, B-roll) | Lock brand look: Casting Director, 5 locks (spokesperson, mascot, hero product) | Build ads at scale: Ad Factory, 5 studios | Edit, caption & localize | Auto-cut highlights: VI, Thumbnail, Poster | Resize: Adapt + Video Reframe | 5 Ad Factory studios; 3.2× CTR, 138×, 98%, 100k+/mo |
| **Ecommerce** | Product & model imagery (Virtual Try-On, Upscaler, Relight, Color Grading, Palette Studio; multi-angle) | Keep every SKU consistent (Object + Wardrobe locks emphasized) | Catalog scale: Ecommerce Image/Video Studio, UGC, Micro Ad Factory (from "a single product link"), Video Batch Generation | Edit/caption/localize listing video | Auto-cut listing video + thumbnail/key art | Resize for every marketplace | same as Marketers |
| **Social creators** | Generate B-roll, cutaways, channel art, promo stills | Persona consistency (host, avatar, mascot) | **Auto-cut shorts: Video Intelligence** (core unlock) | Edit, caption & polish | **Thumbnails & key art** (own stage) | Resize | 3 auto-cut modes, 16 thumbnail styles |
| **Influencers** | **UGC Ads Studio** (17 formats, 6 categories) | Personal brand (Identity + Expression locks emphasized; others for signature look, home set, recurring branded item such as a mic or ring light) | Scale deals: Micro Ad Factory + Video Batch Generation (rows per partner product or affiliate code) | Auto-cut + thumbnails + key art | Edit, caption & localize | Resize for platform and brand spec | 17 UGC formats |

Every persona page also includes the note that voice and music are "priced as line items in Budget Estimator… Dedicated AI Voice and AI Music pages… still being built". That note is stale: the Voice (§6) and Music pages now exist.

---

## 25. AI Music Generation (Music module), `ai-music-generation.html`

(Listed out of order here so the tool sections stay grouped by suite.)

- **Model picker** ("Choose Model" modal, Google · Lyria):
  - **Lyria 2** (V2): 30s, Negative prompt, Instrumental only, Seed.
  - **Lyria 3 Clip** (V3 · ⚡1): 30s, optional Vocals, Seed.
  - **Lyria 3 Pro** (PRO · ⚡2 · **Default**): "Up to ~3 min · full song structure · vocals · timed lyrics", Seed.
  - **[Inference]** The ⚡1 and ⚡2 labels are relative credit-cost badges.
- **Prompt field:** genre, mood, instruments, BPM, key. Helper chips insert syntax: **+Timestamp, +BPM, +Key, +Intensity, +Instrumental**. Timestamp syntax example, *verbatim*: `[0:00-0:20]: intro music, bass at lowfi and a mix of violin and flute`. Another example: `travelling bgm [0:00-0:30]`.
- **Negative prompt:** Lyria 2 only.
- **Vocal Mode** toggle: Instrumental / With vocals. With vocals, a **"Vocal instructions / lyrics"** field appears (placeholder "e.g. verse & chorus lyrics, vocal style, language…"; helper text "Folded into the prompt at generation. Tip: you can specify the language here too (e.g. 'in Spanish')").
- **Output Mode:** random (blank seed) or **Fixed seed** (any number).
- **Generation History:** List and Grid views, plus Refresh. Each row shows the title, prompt, chips (instrumental/vocals, duration, model) and a **Lyrics file** download for vocal tracks on Lyria 3 Pro. Actions: play, download, edit, delete. Example rows: "Ravanan Test" (instrumental, 1:44) and "My Way" (vocals, 2:59).

---

## 26. Cross-cutting platform features (for the data model)

| Feature | Evidence | Notes for a rebuild |
|---|---|---|
| **Accounts / auth** | Google sign-in, or username/email + password; Forgot Password; multi-device | Standard OAuth plus password auth |
| **Projects** | Video Editor projects autosave with named versions; Story Builder History and versions; Budget versions; Ad batch IDs; per-project token tracking for enterprise | **[Inference]** A project container scopes assets, Elements and spend |
| **Elements library** (character locking) | Named Elements with reference images (characters, objects, styles), referenced via `@Name` in Image and Video prompts, reusable across projects; Casting Director "lock" | Core entity; five lock types (§3) |
| **Assets library** | All uploads and generations; preview, download, "add to an Element"; downloads are JPG, PNG, MP4; Video Editor library with folders, resumable dedup uploads | Object storage plus metadata |
| **History** per module | Videos, Voice, Music, Story Builder, Comics generation history | A per-tool generation log with params |
| **Tokens / credits** | Most actions consume tokens; cost depends on model, resolution and duration; an estimate is shown before generating; usage history and billing page; unused tokens "typically carried forward"; failed generations can be refunded via support; Video Editor editing and export are free, AI buttons show their cost | A cost-estimate API per action plus a ledger |
| **Enterprise controls** | Per-seat permissions, model-access controls, per-project and per-seat spend, central brand asset library | RBAC plus model allowlists |
| **QC / Quality Analyzer** | Ad QC with 5 axes and a 0–10 threshold with auto-regeneration; Quality Analyzer checks against the brief and locked characters; home page says "visual consistency, audio sync, timing and brand alignment" | An LLM/VLM judge with a scoring rubric |
| **Prompt tooling** | Prompt Assistant / Improve prompt, Prompt Studio templates, Reverse Prompt Engineer (image or video → prompt) | Shared LLM services |
| **Model orchestration** | Per task and per scene model routing; models named across pages: Veo, Sora, Kling, Seedance, Gemini Omni Flash, GPT Image, Flux 1.1 Pro, Gemini, Omini, Ideogram, Gemini TTS ×4, Lyria ×3, ElevenLabs (Scribe, voice-over), OpenAI Whisper, Copilot LLMs (Gemini, GPT-5.6 Luna, Claude Opus 5.5) | Provider-adapter layer |
| **Data handling** | Uploaded images, faces and voices are not used to train foundation models; users own their outputs; commercial use is allowed under the ToU; Acceptable Use Policy | Policy pages |
| **Free tool** | Visual Explainer Studio: no login, BYO OpenAI key, runs in the browser | Static client app |

### Inter-tool links (graph)
- Story Builder production pack → Storyboard Builder (cast, places, look) and the downstream tools; Script Doctor footprint → next draft and Budget; Budget reads the script.
- Casting Director lock → Elements / Character Identity → Image Suite, Video Generator, UGC Ads Studio, Ecommerce Video Studio.
- Image Suite stills → Video Generator first frames. Virtual Try-On and Model Photoshoot → Upscale.
- Video Intelligence key frames → Thumbnail Creator (collage templates) and Poster Creation.
- Subtitle Creator ↔ Video Editor (captions and transcripts; the editor links to Subtitle Creator for translation).
- Any output → Resize & Repurpose (Adapt / Video Reframe).
- Ad Factory: Micro Ad Factory pipeline reused per row by Video Batch Generation; QC loop.

### Known inconsistencies on the site
- Subtitle languages: 60+ on the dedicated page, "32 additional / 33" on the persona and editor pages.
- Video Editor: the dedicated page says 28 transitions, 19 fonts and server render. Persona pages say 6 transition styles, 12 fonts and local MP4 export.
- Script Doctor: 16 dimensions in the list, "24 dimensions" in the spec strip.
- Image models: the Image page lists GPT Image, Flux 1.1 Pro, Gemini, Seedance, Omini, Ideogram. Casting Director lists only GPT Image and Flux 1.1 Pro.
- Video max duration is 15s on the tool page. The FAQ says "short video clips" and that longer runtimes cost more.
