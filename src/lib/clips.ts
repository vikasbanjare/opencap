import type { Cut, Overlay, Word, ZoomKey } from '../captions/types'

export type Seg = { id: string; clip: string; in: number; out: number; transition: string; tdur: number; start: number }
export type Clip = { id: string; file: string; name?: string; duration: number; hasAudio?: boolean; transcribeStatus?: string }

export const TRANSITIONS: [string, string][] = [['none', 'Cut'], ['fade', 'Crossfade'], ['black', 'Dip to black'], ['white', 'Dip to white'], ['dissolve', 'Dissolve'],
  ['slide', 'Slide'], ['slideup', 'Slide up'], ['wipe', 'Wipe'], ['circle', 'Circle'], ['zoom', 'Zoom'], ['blur', 'Blur'], ['pixel', 'Pixelate']]

/** Segments of a project; before any clip edit the whole upload is one segment. */
export const segsOf = (m: { segments?: Seg[]; duration: number }): Seg[] =>
  m.segments?.length ? m.segments : [{ id: 'base', clip: 'source', in: 0, out: m.duration, transition: 'none', tdur: 0.5, start: 0 }]

export const segLen = (s: Seg) => s.out - s.in

/** Map a moment on the old timeline to the new one through its source time; null if that moment is gone. */
export function remapTime(t: number, from: Seg[], to: Seg[]): number | null {
  const o = [...from].reverse().find(s => t >= s.start - 1e-6 && t < s.start + segLen(s) + 1e-6)
  if (!o) return null
  const src = o.in + (t - o.start)
  const n = to.find(s => s.clip === o.clip && src >= s.in - 1e-6 && src < s.out + 1e-6)
  return n ? n.start + (src - n.in) : null
}

/** Carry captions, cuts, elements and zooms across a clip edit. */
export function remapDoc(d: { words: Word[]; cuts: Cut[]; overlays: Overlay[]; zooms: ZoomKey[] }, from: Seg[], to: Seg[], duration: number) {
  const m = (t: number) => remapTime(t, from, to)
  const words: Word[] = []
  for (const w of d.words) {
    const s = m(w.start); if (s == null) continue
    const e = m(Math.max(w.start, w.end - 1e-3)) ?? s + (w.end - w.start)
    const ce = w.cardEnd != null ? m(w.cardEnd - 1e-3) ?? undefined : undefined
    words.push({ ...w, start: s, end: Math.max(s + 0.02, e), cardEnd: ce })
  }
  words.sort((a, b) => a.start - b.start)
  // captions never run across a clip boundary
  for (const sg of to) { const i = words.findIndex(w => w.start >= sg.start - 1e-6); if (i >= 0) words[i] = { ...words[i], brk: true, glue: false } }
  const cuts = d.cuts.flatMap(c => { const a = m(c.start), b = m(Math.max(c.start, c.end - 1e-3)); return a != null && b != null && b > a ? [{ start: a, end: b }] : [] })
  const overlays = d.overlays.map(o => { const s = m(o.start); const st = s ?? Math.min(o.start, Math.max(0, duration - 0.5)); return { ...o, start: st, end: Math.min(duration, st + (o.end - o.start)) } })
  const zooms = d.zooms.flatMap(z => { const t = m(z.time); return t == null ? [] : [{ ...z, time: t }] })
  return { words, cuts, overlays, zooms }
}

/** Words of a freshly transcribed clip, placed wherever that clip appears on the timeline. */
export function clipWords(transcript: { words: Word[] }, clip: string, segs: Seg[]): Word[] {
  const out: Word[] = []
  for (const sg of segs.filter(s => s.clip === clip)) {
    const ws = transcript.words.filter(w => w.start >= sg.in && w.start < sg.out).map(w => ({ ...w, start: sg.start + w.start - sg.in, end: sg.start + Math.min(w.end, sg.out) - sg.in }))
    if (ws.length) ws[0] = { ...ws[0], brk: true }
    out.push(...ws)
  }
  return out
}
