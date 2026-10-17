import { useEffect, useRef, useState } from 'react'
import { useEditor } from '../store'
import type { Card } from '../captions/types'
import { cutsFromWords, mergeCuts, fmtTime } from '../lib/timeline'

const HUES = ['#5b8def', '#e06ba1', '#52c7a0', '#f0a143', '#a177ee', '#4fc3f7']

export function Timeline({ cards, seek }: { cards: Card[]; seek: (t: number) => void }) {
  const s = useEditor()
  const ref = useRef<HTMLCanvasElement>(null)
  const wrap = useRef<HTMLDivElement>(null)
  const [peaks, setPeaks] = useState<number[]>([])
  const [pps, setPps] = useState(60) // pixels per second
  const drag = useRef<{ x0: number; t0: number } | null>(null)
  const [rubber, setRubber] = useState<{ a: number; b: number } | null>(null)

  useEffect(() => { if (s.project) fetch(s.project.peaksUrl).then(r => r.json()).then(setPeaks).catch(() => setPeaks([])) }, [s.project])
  useEffect(() => { if (s.project && wrap.current) setPps(Math.max(20, (wrap.current.clientWidth - 20) / s.project.duration)) }, [s.project])

  const dur = s.project?.duration ?? 1
  const W = Math.max(300, Math.round(dur * pps)), H = 150
  const cuts = mergeCuts([...s.cuts, ...cutsFromWords(s.words)])

  useEffect(() => {
    const c = ref.current; if (!c) return
    const dpr = window.devicePixelRatio || 1
    c.width = W * dpr; c.height = H * dpr; c.style.width = W + 'px'; c.style.height = H + 'px'
    const ctx = c.getContext('2d')!; ctx.scale(dpr, dpr)
    ctx.fillStyle = '#121418'; ctx.fillRect(0, 0, W, H)
    // ruler
    ctx.fillStyle = '#6b7280'; ctx.font = '10px Inter, system-ui'
    const step = pps > 120 ? 0.5 : pps > 50 ? 1 : pps > 20 ? 2 : 5
    for (let t = 0; t <= dur; t += step) { const x = t * pps; ctx.fillRect(x, 0, 1, 6); if (Math.round(t / step) % 2 === 0) ctx.fillText(fmtTime(t), x + 3, 14) }
    // waveform
    if (peaks.length) {
      ctx.fillStyle = '#2f3542'
      const n = peaks.length, mid = 60
      for (let i = 0; i < n; i++) { const x = i / 20 * pps, h = peaks[i] * 36; ctx.fillRect(x, mid - h, Math.max(1, pps / 20), h * 2) }
    }
    // words by card
    cards.forEach((card, ci) => {
      ctx.fillStyle = HUES[ci % HUES.length]
      for (const w of card.words) { const x = w.start * pps, ww = Math.max(2, (w.end - w.start) * pps - 1); ctx.globalAlpha = 0.85; ctx.fillRect(x, 100, ww, 22) }
      ctx.globalAlpha = 1
      if (card.emphIndex >= 0) { const w = card.words[card.emphIndex]; ctx.fillStyle = '#fff'; ctx.fillRect(w.start * pps, 98, Math.max(2, (w.end - w.start) * pps - 1), 2) }
    })
    // deleted words
    ctx.fillStyle = 'rgba(239,68,68,.55)'
    for (const w of s.words) if (w.deleted) ctx.fillRect(w.start * pps, 100, Math.max(2, (w.end - w.start) * pps - 1), 22)
    // cuts
    for (const cu of cuts) { ctx.fillStyle = 'rgba(239,68,68,.18)'; ctx.fillRect(cu.start * pps, 20, (cu.end - cu.start) * pps, H - 20); ctx.fillStyle = 'rgba(239,68,68,.6)'; ctx.fillRect(cu.start * pps, 20, 1, H - 20); ctx.fillRect(cu.end * pps - 1, 20, 1, H - 20) }
    // overlays
    s.overlays.forEach(o => { ctx.fillStyle = o.id === s.selectedOverlay ? '#fbbf24' : '#d97706'; ctx.fillRect(o.start * pps, 128, Math.max(2, (o.end - o.start) * pps), 12) })
    // zooms
    s.zooms.forEach(z => { ctx.fillStyle = '#22d3ee'; ctx.fillRect(z.time * pps, 92, 2, 6) })
    // selection
    if (s.selected != null && s.words[s.selected]) { const w = s.words[s.selected]; ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.strokeRect(w.start * pps, 99, Math.max(2, (w.end - w.start) * pps - 1), 24) }
    if (rubber) { ctx.fillStyle = 'rgba(239,68,68,.3)'; ctx.fillRect(Math.min(rubber.a, rubber.b) * pps, 20, Math.abs(rubber.b - rubber.a) * pps, H - 20) }
    // playhead
    ctx.fillStyle = '#f43f5e'; ctx.fillRect(s.time * pps - 1, 0, 2, H)
  }, [W, H, pps, peaks, cards, s.words, s.cuts, s.overlays, s.zooms, s.time, s.selected, s.selectedOverlay, rubber, cuts, dur])

  // keep the playhead in view while playing
  useEffect(() => { const el = wrap.current; if (!el || !s.playing) return; const x = s.time * pps; if (x < el.scrollLeft || x > el.scrollLeft + el.clientWidth - 40) el.scrollLeft = x - 40 }, [s.time, s.playing, pps])

  const tAt = (e: React.PointerEvent) => { const r = ref.current!.getBoundingClientRect(); return Math.min(dur, Math.max(0, (e.clientX - r.left) / pps)) }
  const onDown = (e: React.PointerEvent) => {
    const t = tAt(e)
    if (e.shiftKey) { drag.current = { x0: e.clientX, t0: t }; setRubber({ a: t, b: t }); (e.target as Element).setPointerCapture(e.pointerId); return }
    const wi = s.words.findIndex(w => t >= w.start && t < w.end)
    s.set({ selected: wi >= 0 ? wi : null })
    seek(t)
  }
  const onMove = (e: React.PointerEvent) => { if (drag.current) setRubber({ a: drag.current.t0, b: tAt(e) }) }
  const onUp = () => { if (drag.current && rubber && Math.abs(rubber.b - rubber.a) > 0.05) s.set({ cuts: mergeCuts([...s.cuts, { start: Math.min(rubber.a, rubber.b), end: Math.max(rubber.a, rubber.b) }]) }); drag.current = null; setRubber(null) }

  return (
    <div className="timeline">
      <div className="tl-tools">
        <span className="muted">click = seek · shift-drag = cut · Delete = remove word · E = keyword</span>
        <span style={{ flex: 1 }} />
        <button onClick={() => setPps(p => Math.max(10, p / 1.5))}>−</button>
        <button onClick={() => setPps(p => Math.min(600, p * 1.5))}>+</button>
        {s.cuts.length > 0 && <button onClick={() => s.set({ cuts: [] })}>clear cuts ({s.cuts.length})</button>}
      </div>
      <div className="tl-scroll" ref={wrap}>
        <canvas ref={ref} onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} />
      </div>
    </div>
  )
}
