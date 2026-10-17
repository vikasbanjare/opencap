import { create } from 'zustand'
import type { CaptionStyle, Cut, Overlay, Word, ZoomKey } from './captions/types'
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
  aspect: Aspect
  pan: number            // 0..1 horizontal crop position when reframing
  audioUrl: string | null
  time: number
  playing: boolean
  selected: number | null
  selectedOverlay: string | null
  tab: 'captions' | 'style' | 'elements' | 'audio' | 'export'
  captionsOn: boolean
  set: (p: Partial<EditorState>) => void
  load: (m: ProjectMeta) => void
  setWords: (f: (w: Word[]) => Word[]) => void
  setStyle: (f: (s: CaptionStyle) => CaptionStyle) => void
  pickPreset: (id: string) => void
  addOverlay: (o: Overlay) => void
  updateOverlay: (id: string, p: Partial<Overlay>) => void
  removeOverlay: (id: string) => void
}

const key = (id: string) => `opencap:${id}`

export const useEditor = create<EditorState>((set, get) => ({
  project: null, words: [], style: PRESETS[0], cuts: [], zooms: [], autoZoom: false, overlays: [], aspect: 'source', pan: 0.5,
  audioUrl: null, time: 0, playing: false, selected: null, selectedOverlay: null, tab: 'captions', captionsOn: true,
  set: p => { set(p); persist(get()) },
  load: m => {
    const saved = localStorage.getItem(key(m.id))
    const base = { project: m, words: m.transcript?.words ?? [], style: PRESETS[0], cuts: [], zooms: [], autoZoom: false, overlays: [], aspect: 'source' as Aspect, pan: 0.5, audioUrl: null, time: 0, playing: false, selected: null, selectedOverlay: null }
    if (saved) {
      try {
        const s = JSON.parse(saved)
        // keep fresh transcript if the saved one is empty (transcription finished after the first open)
        if (!s.words?.length && base.words.length) s.words = base.words
        set({ ...base, ...s, project: m, playing: false }); return
      } catch { /* ignore corrupt */ }
    }
    set(base)
  },
  setWords: f => { set({ words: f(get().words) }); persist(get()) },
  setStyle: f => { set({ style: f(get().style) }); persist(get()) },
  pickPreset: id => { set({ style: JSON.parse(JSON.stringify(presetById(id))) }); persist(get()) },
  addOverlay: o => { set({ overlays: [...get().overlays, o], selectedOverlay: o.id }); persist(get()) },
  updateOverlay: (id, p) => { set({ overlays: get().overlays.map(o => o.id === id ? { ...o, ...p } : o) }); persist(get()) },
  removeOverlay: id => { set({ overlays: get().overlays.filter(o => o.id !== id), selectedOverlay: null }); persist(get()) },
}))

let timer: number | undefined
function persist(s: EditorState) {
  if (!s.project) return
  clearTimeout(timer)
  timer = window.setTimeout(() => {
    const { words, style, cuts, zooms, autoZoom, overlays, aspect, pan, audioUrl, captionsOn } = s
    localStorage.setItem(key(s.project!.id), JSON.stringify({ words, style, cuts, zooms, autoZoom, overlays, aspect, pan, audioUrl, captionsOn }))
  }, 300)
}

export const aspectSize = (a: Aspect, src: { width: number; height: number }, longEdge = 1920): { w: number; h: number } => {
  const r = a === 'source' ? src.width / src.height : a === '9:16' ? 9 / 16 : a === '1:1' ? 1 : a === '4:5' ? 4 / 5 : 16 / 9
  const w = r >= 1 ? longEdge : Math.round(longEdge * r / 2) * 2
  const h = r >= 1 ? Math.round(longEdge / r / 2) * 2 : longEdge
  if (a === 'source') return { w: src.width, h: src.height }
  return { w, h }
}
