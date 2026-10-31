# Spark Station Spec: Addendum (missed features, app routes, film pipeline)

Companion to `sparkstation-spec.md`. Researched 2026-10-28 with TinyFish `fetch_content` and `search`. The same conventions apply: "quotes" are verbatim, **[Inference]** marks my deductions, **[Not found]** marks things I looked for and could not find.

## 0. Bottom line on "movie script, cast, scene and score"

**[Not found]** No public page, sitemap entry, press article, FAQ answer or reachable app route names a separate "Movie Script", "Cast", "Scene" or "Score" tool, and no film-pipeline module by those names either. I checked:
- **Sitemap:** 32 URLs. They are exactly the 23 tool pages, 5 persona pages, the home page and 3 legal pages. Nothing new.
- **qa.sparkstation.ai:** a staging mirror that appeared in search. Its sitemap and home page are identical to production.
- **About 70 guessed URLs and app routes.** Every `ai-*.html` guess in the brief returned 404. So did `/blog`, `/docs`, `/help`, `/pricing`, `/features`, `/studio`, `/film`, `/movie(s)`, `/script(s)`, `/scenes`, `/cast`, `/score`, `/workflows/{movie-script,script,cast,scene,score,movie-maker,film-pipeline,scene-builder,microdrama,…}` and `/tools/{movie-script,scene-builder,music-score,film-score,casting,script-writer,sound-effects,dubbing,lip-sync}`.
- **Eleven press and social sources** (§4).

What does exist is a four-step **marketing flow, "Script → Cast → Shoot → QC"**, on the home page, plus one existing tool per step. The four words most likely map to existing tools as follows (see §5):

| User's word | Existing Spark Station tool | Already in main spec |
|---|---|---|
| Movie script | Story Builder (app route `/workflows/story-board-builder-pro`) + Script Doctor ("Script Score") | §5.1, §5.2 |
| Cast | Casting Director (`/images/casting-director`) + the 5 locks | §3, §7 |
| Scene | Storyboard Builder, Multi-Shots, Reimagine Scene, Location lock, Video Generation | §1, §3, §5.3, §2 |
| Score | AI Music Generation ("This one scores a scene", Lyria). The other candidate is Script Doctor's "Script Score" | §25, §5.2 |

**[Inference]** If the user has seen these as named tabs, they live inside the logged-in app, most likely as stages of the Story Builder workflow (`/workflows/story-board-builder-pro`), and no public source describes them. To confirm, someone needs a logged-in session, or the app's JS bundle (see §6).

---

## 1. NEW: In-app route map (from the "Try" buttons' `login?next=` targets)

None of these were in the main spec. Each returned `login_required` when probed directly, which confirms the route exists. Unknown routes return 404.

| Tool (marketing name) | App route |
|---|---|
| App home | `/home` |
| Story Builder | `/workflows/story-board-builder-pro` (note: not `/tools/story-builder`, which is 404) |
| Script Doctor | `/tools/script-doctor-pro` |
| Storyboard Builder | `/tools/storyboard-builder` (the pre-production page also links `/tools/storyboard-creator`, which returns 404, a dead link) |
| Budget Estimator | `/tools/budget-estimator-pro` |
| Casting Director | `/images/casting-director` |
| Character Identity lock | `/images/character-identity` |
| Expression lock | `/images/expression-continuity` |
| Wardrobe lock | `/images/costume-wardrobe-continuity` |
| Location lock | `/images/location-consistency` |
| Object/prop lock | `/images/property-object-consistency` |
| Image Studio | `/images` |
| Multi-Shots | `/images/multi-shots` (route confirmed by probe) |
| Reimagine Scene | `/images/reimagine-scene` (route confirmed by probe) |
| Upscale | `/images/upscale` |
| Inpaint | `/images/inpaint` |
| Face Swap | `/images/face-swap` |
| Virtual Try-On | `/images/virtual-tryon` |
| Model Photoshoot | `/images/turn-to-model` |
| Draw to Paint | `/images/draw-to-paint` |
| Color Grading | `/images/color-grading` |
| Videos module | `/videos-pro` (`/videos` returns 404) |
| Voice module | `/voice` |
| Music module | `/music` |
| Elements library | `/elements` |
| Assets library | `/assets` |
| Projects | `/projects` (exists; no public description) |
| Video Editor | `/tools/video-editor-pro` |
| Subtitle Creator | `/tools/caption-studio` (in-app name **Caption Studio**) |
| Thumbnail Creator | `/tools/thumbnail-creator` |
| Adapt (image resize) | `/tools/adapt` |
| Video Reframe | `/tools/video-reframe-pro` |
| Video Intelligence | `/workflows/video-intelligence` |
| Comics Generator | `/workflows/comics-generator` (also `/comics-generator`) |
| Ad Factory home | `/micro-ads/home` |
| Ecommerce Image Studio | `/micro-ads/ecommerce-image-studio` |
| Video Batch Generation | `/micro-ads/video-batch-generation` |
| Wallet & billing | `/billing` → `/billing/usage` (one unauthenticated fetch rendered "Wallet & billing ↻ Refresh Loading…") |

The robots.txt disallows `/login /signin /auth/ /account/ /api/ /admin/ /app/`.

The rebuild should organise its routes into the same three namespaces: `tools/*` for single-step utilities, `workflows/*` for multi-stage pipelines, and `images/*` for Image Studio sub-tools. The `-pro` suffix suggests these are second-generation versions **[Inference]**.

Source: CTA `href`s on https://www.sparkstation.ai/ai-preproduction-tools.html, `/for-filmmakers.html`, `/ai-character-consistency.html`, all the tool pages, plus my own route probes.

---

## 2. NEW: Contextual Dubbing (AI dubbing and lip-sync localisation)

- **Purpose:** localise a finished production into another language while keeping the performance, the lip movements and the cultural idiom. It is not word-for-word translation.
- **Evidence:**
  - YouTube "SparkStation | Contextual Dubbing Trailer" (https://www.youtube.com/watch?v=cy7Wc2Km_BU). The description, verbatim: "Live Hindi Production → AI-Contextualized Dubbing for Western Microdramas".
  - Press (TOI, digitalterminal): "60+ languages at production fidelity: The performance travels and not just the words - lip movements, emotional beats and local idioms. Six weeks of localisation becomes one day."
  - Fossbytes: "supports more than 60 languages, even with localized lip movements".
  - Entrackr: "localisation in more than 60 languages, including changes to lip movements, emotional delivery and local expressions".
- **Inputs [Inference]:** a source video (with its dialogue track or script), a target language or languages, and optionally a voice per character (from the Voice module or a locked character voice).
- **Steps [Inference]:** transcribe, then contextual translation (adapting idioms rather than translating literally), then TTS or voice-clone in the target language with emotional delivery matched to the original, then lip-sync re-render of the mouth region, then subtitle export via Caption Studio.
- **Outputs:** a dubbed, lip-synced video per language.
- **Models:** none named. **[Inference]** Gemini TTS (Voice module) and ElevenLabs (already used for voice-over in the Video Editor) are the likely TTS layer. The lip-sync model is unknown.
- **Links:** Subtitle Creator (60+ languages), Voice module, Budget Estimator (the "Dubbed & subtitled languages" line item), Ad Factory localisation ("localise a campaign into twelve languages", enterprise page).
- **Status:** no marketing page, no app route found (`/dubbing` and `/tools/dubbing` are 404), and no FAQ entry. Dubbing appears in the main spec only as a budget line.

## 3. NEW: Enterprise and support details (talk-to-sales.html, general-support.html)

These were not captured in the main spec.
- **Plans:** Individual (credits), **Teams** ("self-serve seats on shared capacity"), and Enterprise (annual agreement, "pooled credits and seats", quoted after a scoping call). Press: "credits for creators, seat-based SaaS for studios and brands, and enterprise licensing with API access".
- **Enterprise features, verbatim headings:** SSO & SAML (role-based access, automatic de-provisioning, "a record of who generated what"); Pooled credits (per-team caps, spend reporting); Priority capacity ("Reserved GPU throughput and higher concurrency"); Unlimited seats; **API & automation** ("Batch product imagery, localise a campaign into twelve languages, or wire generation into your DAM"); Named support (signed DPA).
- **Compliance:** SOC 2 Type II, GDPR aligned, India DPDP Act, signed DPA on request, contractual indemnity, "Model provenance on request".
- **Security:** workspace isolation ("Assets, character sheets, brand kits and model configurations stay inside your tenant"), per-project visibility, an exportable "audit trail of generations, approvals and exports" with configurable retention, and private cloud or VPC on larger deals.
- **Consent tracking:** "The platform records which assets were cast from a real reference, so that is auditable." For a rebuild, store a `cast_from_real_reference` flag plus consent metadata on each Element.
- **Approvals:** "approvals" appear in the audit trail, so there is a review/approve step on outputs **[Inference]**.
- **Rollout:** beta from 29 Aug 2026, GA 1 Oct 2026, enterprise API tier 1 Nov 2026 (press).
- **Support:** a request form with topic categories "Billing & Plans", "Privacy & Data" and "Enterprise & Business" (others not captured). Replies "within one business day, Monday to Friday IST". Email contact@sparkstation.ai. Account deletion removes data "from active systems within 30 days".

## 4. Press and video sources checked

| Source | What it adds |
|---|---|
| bignewsnetwork / outlookbusiness (PNN, 31 Aug 2026) | Workflow list: "scripting, storyboarding, casting, location design, asset generation, multi-angle shot creation, music and dialogue production, editing, captioning, rendering and distribution"; NLE exports to Premiere Pro, Final Cut Pro, DaVinci Resolve |
| fossbytes.com (1 Sep 2026) | Adds "costumes", "localized lip movements", "templates" for creators |
| digitalterminal.in (31 Aug 2026) | Same press release: "asset generation including casting, locations, costumes, multi-angle shots, music and dialogue"; "5 locked elements: Face, expression, wardrobe, location & props" |
| timesofindia (31 Aug 2026) | Routing granularity: "a face, a crowd, a camera move, a voice, a language" |
| afaqs, entrackr | Same facts; the 5 locks "carry them across multiple scenes" |
| LinkedIn (Sourav P.) | Demo reel spanning four genres (neon noir, war desert, fantasy dragon, stop-motion puppets), "one continuous reel" |
| YouTube @sparkstationai (≈31 videos) | **"SparkStation Product Demo"** = the home-page tour video (https://www.youtube.com/watch?v=Dc2zcpSJDK0). Its description, partial and verbatim: "SparkStation is an AI-native creative operating system designed to democratize creative production. It combines intelligent automation with human control, en…" (the rest was truncated and the transcript was not reachable). Also "Yugra / The King Returns" (a mythology short film made on the platform), "Just One Small Change", "Contextual Dubbing Trailer" |
| Instagram / Facebook reels | Taglines only: "90% lower production cost · ~24 hours · 60+ languages" |

**Home-page tour:** `#tour` is a poster button (`playHero()`) whose fallback image is the YouTube thumbnail of `Dc2zcpSJDK0`. There is no iframe in the static HTML.

## 5. Script → Cast → Scene → Score pipeline (consolidated)

This is everything public, stitched end to end. Stage names follow the user's words, and the tools come from the main spec.

1. **Script.** Tool: Story Builder (`/workflows/story-board-builder-pro`).
   - In: a brief (typed, pasted or uploaded, in any language), one of 24 forms (Short film, Feature screenplay, TV episode/pilot, Series bible, Microdrama series, Vertical short, Documentary, Ad film, Music video, Novel, Stage play, Audio drama, Comic script…) and a structure.
   - Steps: Read my intent (lock what must and must never happen) → Outline → Draft & review → Handoff.
   - Out: a script plus a **Production Pack** (Title/logline/runtime, Cast, Wardrobe, Locations, Props, Lighting & palette, Camera & lenses, Scenes). Exports: Fountain, FDX, CSV, MD, JSON.
   - Then **Script Doctor** (`/tools/script-doctor-pro`) scores the draft: 16 dimensions, "Script Score" out of 100 over Structure/Pacing/Originality/Character Depth/Dialogue/Theme, plus a Production Footprint and Casting Suggestions.
   - **Budget Estimator** prices the result.
2. **Cast.** Tool: Casting Director (`/images/casting-director`).
   - In: the Production Pack cast entries or Script Doctor's Casting Suggestions, a character description, an optional reference image, a style (20+), a count (2/4/6/8), a model (GPT Image / Flux 1.1 Pro) and a resolution (512/1024/2048).
   - Out: a lineup. You lock one pick, which becomes an Element under the Identity lock.
   - The other 4 locks (Expression, Wardrobe, Location, Object) hold the rest of the Production Pack (Wardrobe, Locations, Props). Elements are referenced with `@Name`.
   - Voice: pick one of 30 Gemini TTS voices per character **[Inference: per-character voice binding, since the home page says it locks "face, voice and wardrobe"]**.
3. **Scene.**
   - Storyboard Builder (`/tools/storyboard-builder`): Story (shot list with cast and locations auto-detected) → Look (art style + style frame) → Board (9-panel pages; PDF/PNG/CSV).
   - Image Studio stills per shot: Multi-Shots (coverage of one scene), Multi-Angles, Reimagine Scene ("Same blocking, new world"), relight, grade.
   - Then Video Generation (`/videos-pro`): first frame from a still, camera rig (lens, focal length, aperture) plus moves (dolly, orbit, crane, push), ≤15s clips, model routed per scene (Veo, Kling, Seedance, Sora…).
   - Dialogue comes from the Voice module. Quality Analyzer checks against the brief and the locks.
4. **Score.** Tool: AI Music Generation (`/music`), Google Lyria 2 / 3 Clip / 3 Pro.
   - Scene-targeted scoring with timestamp syntax `[0:00-0:20]: …`, plus helper tags +Timestamp/+BPM/+Key/+Intensity/+Instrumental, vocals with lyrics (timed-lyrics file on 3 Pro), and a fixed seed.
   - FAQ: "The music workflow is designed to generate music according to the mood and timing of your scene."
   - SFX: "Spark Station provides AI-generated sound effects" (no page or route found).
5. **Finish (after score):** Video Editor (`/tools/video-editor-pro`; NLE handoff to Premiere/FCP/Resolve), Caption Studio (60+ languages), Contextual Dubbing (§2), Video Intelligence (trailer/teaser/reel), Thumbnail, Poster, Adapt/Reframe.

**Data carried through [Inference]:** the Production Pack is the project's source of truth. Its Cast entries become Elements, its Scenes become shot-list rows, and the shot rows drive the stills, clips, voice lines and music cues by timestamp. Script Doctor's Production Footprint and the Budget read the same object.

**[Not found]:**
- Any automatic "one-click script → finished film" run (the Micro Ad Factory does this for ads only).
- Any per-scene score or cue sheet generated from the script.
- Any "scene" object with its own UI.
- Whether Story Builder's in-app stages are literally labelled Script / Cast / Scenes / Score.

## 6. What would close the gaps

- **Logged-in access** to `/workflows/story-board-builder-pro`, `/projects` and `/home`. All three are currently `login_required`.
- **The app's JS bundle.** Its route table would list every module. TinyFish's cleaned HTML strips `<script>` tags. A metered `run_web_automation` run could read `document.scripts`, but I did not spend wallet credits without your approval.
- **The transcript of the Product Demo video** `Dc2zcpSJDK0`. YouTube's page text was not reachable.
