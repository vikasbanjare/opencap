# Editor gap analysis: OpenCap vs VEED and Captions.ai

Audited 2026-10-18 against the VEED editor (veed.io/edit) and the Captions.ai flow.
Status: **this pass** = built now, **later** = worth doing next, **out** = needs paid models or cloud.

## Caption editing (the core gap)

| Gap | VEED / Captions.ai | OpenCap before | Status |
|---|---|---|---|
| Caption list editor: one text box per caption with its time range | Subtitles panel lists every line, type to edit | only a word-by-word transcript, double-click a word | this pass |
| Captions as blocks on the timeline | dedicated subtitle track | coloured word ticks, not selectable | this pass |
| Drag a caption block to move it in time | yes | no | this pass |
| Drag a block's edge to stretch or shorten it | yes | no | this pass |
| Double-click a caption on the timeline to retype it | yes | no | this pass |
| Click a caption on the video to select it, double-click to edit | yes | no | this pass |
| Drag captions on the video to reposition | yes | only via a slider in Style | this pass |
| Corner handle on the video to resize caption text | yes | only via a slider | this pass |
| Split, merge, add, delete a caption without cutting the video | yes | deleting a word always cut the video | this pass |
| Per-word colour (Captions.ai "highlight words") | yes | only one auto keyword colour | this pass |
| Contextual text toolbar: font, size, colour, bold, italic, case, align | floating toolbar over the canvas | buried under 134 preset thumbnails | this pass |
| Style panel split into Presets and Customize | yes | one long scroll | this pass |

## Editor basics

| Gap | Status |
|---|---|
| Undo / redo (buttons + Cmd/Ctrl+Z, Shift+Cmd+Z) | this pass |
| Rename project from the editor | this pass |
| Track labels on the timeline (Captions, Audio, Elements) | this pass |
| Move and stretch text/emoji/B-roll elements on the timeline | this pass |
| Escape clears selection; Delete removes the selected caption or element | this pass |
| Keyboard shortcut sheet | later |
| Resize handles for image/emoji elements on the canvas | later |
| Multiple source clips on one timeline (append, reorder, split clip) | later |
| Transitions between clips | later |
| Stock video/music library | out (needs API keys) |
| AI B-roll, AI avatars, eye contact, AI voice beyond F5-TTS | out |
| Cloud projects, sharing links, collaboration | out (local-only by design) |
