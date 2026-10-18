import { create } from 'zustand'
import type { CaptionStyle, Cut, Music, Overlay, Word, ZoomKey } from './captions/types'
import { PRESETS, presetById } from './captions/presets'
import type { ProjectMeta } from './lib/api'

export type Aspect = 'source' | '9:16' | '1:1' | '16:9' | '4:5'

export type EditorState = {
  project: ProjectMeta | null
  words: Word[]
  style: CaptionStyle
  cuts: Cut[]            // manual + silence cuts (word deletions are derived separately)
  zooms: ZoomKey[]
  autoZoom: boolean
  overlays: Overlay[]
  music: Music | null
  aspect: Aspect
  pan: number            // 0..1 horizontal crop position when reframing
  audioUrl: string | null
  time: number
  playing: boolean
  selected: number | null
  selectedOverlay: string | null
  tab: 'captions' | 'style' | 'elements' | 'audio' | 'export'
  captionsOn: boolean
  capSel: boolean        // a caption is selected on the canvas (shows the text toolbar)
  editCard: number | null // first-word index of the caption being retyped inline
  past: Doc[]; future: Doc[]
  undo: () => void; redo: () => void
  set: (p: Partial<EditorState>) => void
  load: (m: ProjectMeta, serverState?: Record<string, unknown> | null) => void
  setWords: (f: (w: Word[]) => Word[]) => void
  setStyle: (f: (s: CaptionStyle) => CaptionStyle) => void
  pickPreset: (id: string) => void
  addOverlay: (o: Overlay) => void
  updateOverlay: (id: string, p: Partial<Overlay>) => void
  removeOverlay: (id: string) => void
}

const key = (id: string) => `opencap:${id}`

// Undo history covers the document, not UI state (time, tab, selection).
const DOC = ['words', 'style', 'cuts', 'zooms', 'autoZoom', 'overlays', 'music', 'aspect', 'pan', 'audioUrl', 'captionsOn'] as const
type Doc = Pick<EditorState, typeof DOC[number]>
const docOf = (s: EditorState): Doc => Object.fromEntries(DOC.map(k => [k, s[k]])) as Doc
let lastPush = 0
/** Snapshot before a change; bursts within 600 ms (a drag, typing) collapse into one undo step. */
function record(get: () => EditorState, set: (p: Partial<EditorState>) => void) {
  const now = performance.now(); const quick = now - lastPush < 600; lastPush = now
  if (quick) return
  const s = get(); set({ past: [...s.past, docOf(s)].slice(-100), future: [] })
}

export const useEditor = create<EditorState>((set, get) => ({
  project: null, words: [], style: PRESETS[0], cuts: [], zooms: [], autoZoom: false, overlays: [], music: null, aspect: 'source', pan: 0.5,
  audioUrl: null, time: 0, playing: false, selected: null, selectedOverlay: null, tab: 'captions', captionsOn: true,
  capSel: false, editCard: null, past: [], future: [],
  undo: () => { const s = get(); const prev = s.past[s.past.length - 1]; if (!prev) return; lastPush = 0
    set({ ...prev, past: s.past.slice(0, -1), future: [docOf(s), ...s.future] }); persist(get()) },
  redo: () => { const s = get(); const next = s.future[0]; if (!next) return; lastPush = 0
    set({ ...next, future: s.future.slice(1), past: [...s.past, docOf(s)] }); persist(get()) },
  set: p => { if (Object.keys(p).some(k => (DOC as readonly string[]).includes(k))) record(get, set); set(p); persist(get()) },
  load: (m, serverState) => {
    const saved = localStorage.getItem(key(m.id))
    const base = { project: m, words: m.transcript?.words ?? [], style: PRESETS[0], cuts: [], zooms: [], autoZoom: false, overlays: [], music: null, aspect: 'source' as Aspect, pan: 0.5, audioUrl: null, time: 0, playing: false, selected: null, selectedOverlay: null, capSel: false, editCard: null, past: [], future: [] }
    const src = serverState ?? (saved ? JSON.parse(saved) : null)
    if (src) {
      try {
        const s = src as Partial<EditorState>
        // keep fresh transcript if the saved one is empty (transcription finished after the first open)
        if (!s.words?.length && base.words.length) s.words = base.words
        set({ ...base, ...s, project: m, playing: false }); return
      } catch { /* ignore corrupt */ }
    }
    set(base)
  },
  setWords: f => { record(get, set); set({ words: f(get().words) }); persist(get()) },
  setStyle: f => { record(get, set); set({ style: f(get().style) }); persist(get()) },
  pickPreset: id => { record(get, set); set({ style: JSON.parse(JSON.stringify(presetById(id))) }); persist(get()) },
  addOverlay: o => { record(get, set); set({ overlays: [...get().overlays, o], selectedOverlay: o.id }); persist(get()) },
  updateOverlay: (id, p) => { record(get, set); set({ overlays: get().overlays.map(o => o.id === id ? { ...o, ...p } : o) }); persist(get()) },
  removeOverlay: id => { record(get, set); set({ overlays: get().overlays.filter(o => o.id !== id), selectedOverlay: null }); persist(get()) },
}))

let timer: number | undefined
function persist(s: EditorState) {
  if (!s.project) return
  clearTimeout(timer)
  timer = window.setTimeout(() => {
    const { words, style, cuts, zooms, autoZoom, overlays, music, aspect, pan, audioUrl, captionsOn } = s
    const body = JSON.stringify({ words, style, cuts, zooms, autoZoom, overlays: overlays.filter(o => !o.src?.startsWith('blob:')), music, aspect, pan, audioUrl, captionsOn })
    localStorage.setItem(key(s.project!.id), body)
    fetch(`/api/projects/${s.project!.id}/state`, { method: 'PUT', headers: { 'content-type': 'application/json' }, body }).catch(() => null)
  }, 300)
}

export const aspectSize = (a: Aspect, src: { width: number; height: number }, longEdge = 1920): { w: number; h: number } => {
  const r = a === 'source' ? src.width / src.height : a === '9:16' ? 9 / 16 : a === '1:1' ? 1 : a === '4:5' ? 4 / 5 : 16 / 9
  const w = r >= 1 ? longEdge : Math.round(longEdge * r / 2) * 2
  const h = r >= 1 ? Math.round(longEdge / r / 2) * 2 : longEdge
  if (a === 'source') return { w: src.width, h: src.height }
  return { w, h }
}

/** Shared media cache so preview and export draw the same elements. */
export const mediaCache = { images: new Map<string, HTMLImageElement>(), videos: new Map<string, HTMLVideoElement>() }
export function ensureMedia(o: Overlay) {
  if (!o.src) return
  if (o.kind === 'image' && !mediaCache.images.has(o.src)) { const im = new Image(); im.src = o.src; mediaCache.images.set(o.src, im) }
  if (o.kind === 'video' && !mediaCache.videos.has(o.src)) { const v = document.createElement('video'); v.src = o.src; v.muted = true; v.preload = 'auto'; v.playsInline = true; v.loop = true; mediaCache.videos.set(o.src, v) }
}

// dev hook for QA scripts: window.__opencap.getState()/setState()
if (import.meta.env.DEV) (window as unknown as { __opencap: typeof useEditor }).__opencap = useEditor
