import { useEffect, useRef, useState } from 'react'
import { idxOf, moveCard, retimeCard, setCardText } from '../captions/edit'
import type { Word } from '../captions/types'
import { useEditor } from '../store'
import type { Card } from '../captions/types'
import { cutsFromWords, mergeCuts, fmtTime } from '../lib/timeline'
import { Icon } from '../ui/icons'

const HUES = ['#a78bfa', '#f9a8d4', '#67e8f9', '#fdba74', '#bef264', '#c4b5fd']

// track geometry (px)
const RULER = 20, CAP_Y = 26, CAP_H = 34, AUD_Y = 68, AUD_H = 54, EL_Y = 130, EL_H = 24, H = 162, EDGE = 7

type Nb = { idx: number[]; ws: number; we: number; end: number }
const MIN = 0.15   // shortest a caption may get when a neighbour pushes into it

/** Move or stretch a caption; pushing into a neighbour trims that neighbour instead of stopping dead. */
function applyCardDrag(d: Extract<Drag, { kind: 'card' }>, dt: number): Word[] {
  const loS = d.prev ? d.prev.ws + MIN : 0, hiE = d.next ? d.next.end - MIN : d.dur
  let start = d.ws, end = d.b, ws = d.orig
  if (d.mode === 'move') { const k = Math.min(hiE - d.b, Math.max(loS - d.ws, dt)); ws = moveCard(ws, d.idx, k); start = d.ws + k; end = d.b + k }
  else if (d.mode === 'l') { start = Math.min(d.we - 0.1, Math.max(loS, d.ws + dt)); ws = retimeCard(ws, d.idx, start, d.b, true) }
  else { end = Math.min(hiE, Math.max(d.ws + MIN, d.b + dt)); ws = retimeCard(ws, d.idx, d.ws, end) }
  if (d.prev && start < d.prev.end) ws = retimeCard(ws, d.prev.idx, d.prev.ws, start)
  if (d.next && end > d.next.ws) ws = retimeCard(ws, d.next.idx, end, d.next.end, true)
  return ws
}

type Drag =
  | { kind: 'card'; mode: 'move' | 'l' | 'r'; idx: number[]; orig: Word[]; ws: number; we: number; a: number; b: number; prev?: Nb; next?: Nb; dur: number; x0: number; moved: boolean }
  | { kind: 'ov'; mode: 'move' | 'l' | 'r'; id: string; s0: number; e0: number; x0: number; moved: boolean }
  | { kind: 'cut'; t0: number }

export function Timeline({ cards, seek, toggle, outDur }: { cards: Card[]; seek: (t: number) => void; toggle: () => void; outDur: number }) {
  const s = useEditor()
  const ref = useRef<HTMLCanvasElement>(null)
  const wrap = useRef<HTMLDivElement>(null)
  const [peaks, setPeaks] = useState<number[]>([])
  const [pps, setPps] = useState(60) // pixels per second
  const drag = useRef<Drag | null>(null)
  const [rubber, setRubber] = useState<{ a: number; b: number } | null>(null)
  const [editing, setEditing] = useState<{ card: Card; text: string } | null>(null)

  useEffect(() => { if (s.project) fetch(s.project.peaksUrl).then(r => r.json()).then(setPeaks).catch(() => setPeaks([])) }, [s.project])
  useEffect(() => { if (s.project && wrap.current) setPps(Math.max(20, (wrap.current.clientWidth - 20) / s.project.duration)) }, [s.project])

  const dur = s.project?.duration ?? 1
  const W = Math.max(300, Math.round(dur * pps))
  const cuts = mergeCuts([...s.cuts, ...cutsFromWords(s.words)])
  const selCard = s.selected != null ? cards.find(c => c.words.some(w => s.words.indexOf(w) === s.selected)) : undefined

  useEffect(() => {
    const c = ref.current; if (!c) return
    const dpr = window.devicePixelRatio || 1
    c.width = W * dpr; c.height = H * dpr; c.style.width = W + 'px'; c.style.height = H + 'px'
    const ctx = c.getContext('2d')!; ctx.scale(dpr, dpr)
    ctx.fillStyle = '#ffffff'; ctx.fillRect(0, 0, W, H)
    // track lanes
    ctx.fillStyle = '#f7f7f9'
    ctx.fillRect(0, CAP_Y - 3, W, CAP_H + 6); ctx.fillRect(0, AUD_Y - 3, W, AUD_H + 6); ctx.fillRect(0, EL_Y - 3, W, EL_H + 6)
    // ruler
    ctx.fillStyle = '#9b9ba4'; ctx.font = '10px Inter, system-ui'
    const step = pps > 120 ? 0.5 : pps > 50 ? 1 : pps > 20 ? 2 : 5
    for (let t = 0; t <= dur; t += step) { const x = t * pps; ctx.fillRect(x, 0, 1, 6); if (Math.round(t / step) % 2 === 0) ctx.fillText(fmtTime(t), x + 3, 14) }
    // cuts (under everything else)
    for (const cu of cuts) { ctx.fillStyle = 'rgba(229,72,77,.12)'; ctx.fillRect(cu.start * pps, RULER, (cu.end - cu.start) * pps, H - RULER); ctx.fillStyle = 'rgba(229,72,77,.55)'; ctx.fillRect(cu.start * pps, RULER, 1, H - RULER); ctx.fillRect(cu.end * pps - 1, RULER, 1, H - RULER) }
    // caption blocks
    const rr = (x: number, y: number, w: number, h: number, r: number) => { ctx.beginPath(); ctx.roundRect(x, y, Math.max(2, w), h, r) }
    cards.forEach((card, ci) => {
      const x = card.start * pps, w = (card.end - card.start) * pps - 2, on = card === selCard
      rr(x, CAP_Y, w, CAP_H, 7); ctx.fillStyle = on ? '#ede4ff' : HUES[ci % HUES.length] + '55'; ctx.fill()
      ctx.lineWidth = on ? 2 : 1; ctx.strokeStyle = on ? '#7c3aed' : HUES[ci % HUES.length]; ctx.stroke()
      if (w > 24) {
        ctx.save(); ctx.beginPath(); ctx.rect(x + 6, CAP_Y, w - 12, CAP_H); ctx.clip()
        ctx.fillStyle = '#2b2b33'; ctx.font = `${on ? 600 : 500} 11.5px Inter, system-ui`
        ctx.fillText(card.words.map(w => w.text).join(' '), x + 7, CAP_Y + CAP_H / 2 + 4); ctx.restore()
      }
      if (on) { ctx.fillStyle = '#7c3aed'; ctx.fillRect(x + 1, CAP_Y + 9, 3, CAP_H - 18); ctx.fillRect(x + w - 4, CAP_Y + 9, 3, CAP_H - 18) } // stretch grips
    })
    // waveform + word ticks
    const mid = AUD_Y + AUD_H / 2 - 6
    if (peaks.length) { ctx.fillStyle = '#cfcfd8'; for (let i = 0; i < peaks.length; i++) { const x = i / 20 * pps, h = peaks[i] * (AUD_H / 2 - 8); ctx.fillRect(x, mid - h, Math.max(1, pps / 20), h * 2) } }
    for (const w of s.words) { if (w.added) continue; ctx.fillStyle = w.deleted ? 'rgba(229,72,77,.7)' : '#a78bfa'; ctx.fillRect(w.start * pps, AUD_Y + AUD_H - 8, Math.max(2, (w.end - w.start) * pps - 1), 5) }
    // elements
    s.overlays.forEach(o => {
      const x = o.start * pps, w = (o.end - o.start) * pps, on = o.id === s.selectedOverlay
      rr(x, EL_Y, w, EL_H, 6); ctx.fillStyle = on ? '#fde68a' : '#fef3c7'; ctx.fill(); ctx.lineWidth = on ? 2 : 1; ctx.strokeStyle = on ? '#d97706' : '#f5c35b'; ctx.stroke()
      ctx.save(); ctx.beginPath(); ctx.rect(x + 5, EL_Y, Math.max(0, w - 10), EL_H); ctx.clip(); ctx.fillStyle = '#7a4a00'; ctx.font = '500 11px Inter, system-ui'
      ctx.fillText(o.kind === 'video' ? `B-roll (${o.fit})` : o.kind === 'image' ? 'Image' : o.text ?? '', x + 6, EL_Y + EL_H / 2 + 4); ctx.restore()
    })
    // zoom punch-ins
    s.zooms.forEach(z => { ctx.fillStyle = '#06b6d4'; ctx.beginPath(); ctx.arc(z.time * pps, CAP_Y - 7, 3, 0, Math.PI * 2); ctx.fill() })
    if (rubber) { ctx.fillStyle = 'rgba(229,72,77,.25)'; ctx.fillRect(Math.min(rubber.a, rubber.b) * pps, RULER, Math.abs(rubber.b - rubber.a) * pps, H - RULER) }
    // playhead
    ctx.fillStyle = '#111111'; ctx.fillRect(s.time * pps - 1, 0, 2, H); ctx.beginPath(); ctx.moveTo(s.time * pps - 6, 0); ctx.lineTo(s.time * pps + 6, 0); ctx.lineTo(s.time * pps, 8); ctx.fill()
  }, [W, pps, peaks, cards, s.words, s.cuts, s.overlays, s.zooms, s.time, s.selected, s.selectedOverlay, rubber, cuts, dur, selCard])

  // keep the playhead in view while playing
  useEffect(() => { const el = wrap.current; if (!el || !s.playing) return; const x = s.time * pps; if (x < el.scrollLeft || x > el.scrollLeft + el.clientWidth - 40) el.scrollLeft = x - 40 }, [s.time, s.playing, pps])

  const at = (e: React.PointerEvent | React.MouseEvent) => { const r = ref.current!.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top } }
  const tOf = (x: number) => Math.min(dur, Math.max(0, x / pps))
  const edge = (x: number, a: number, b: number): 'l' | 'r' | 'move' => Math.abs(x - a * pps) < EDGE ? 'l' : Math.abs(x - b * pps) < EDGE ? 'r' : 'move'
  const hit = (x: number, y: number) => {
    const t = x / pps
    // the block under the pointer wins; where two blocks touch, that decides whose edge you grab
    if (y >= CAP_Y && y <= CAP_Y + CAP_H) { const card = cards.find(c => t >= c.start && t < c.end) ?? cards.find(c => t >= c.start - EDGE / pps && t <= c.end + EDGE / pps); if (card) return { card, mode: edge(x, card.start, card.end) } }
    if (y >= EL_Y && y <= EL_Y + EL_H) { const o = [...s.overlays].reverse().find(o => t >= o.start - EDGE / pps && t <= o.end + EDGE / pps); if (o) return { o, mode: edge(x, o.start, o.end) } }
    return null
  }

  const onDown = (e: React.PointerEvent) => {
    const { x, y } = at(e), t = tOf(x)
    ;(e.target as Element).setPointerCapture(e.pointerId)
    if (e.shiftKey) { drag.current = { kind: 'cut', t0: t }; setRubber({ a: t, b: t }); return }
    const h = hit(x, y)
    if (h && 'card' in h && h.card) {
      const i = cards.indexOf(h.card), idx = idxOf(s.words, h.card)
      const nb = (c?: Card): Nb | undefined => c && { idx: idxOf(s.words, c), ws: c.words[0].start, we: c.words[c.words.length - 1].end, end: c.end }
      drag.current = { kind: 'card', mode: h.mode, idx, orig: s.words, ws: h.card.words[0].start, we: h.card.words[h.card.words.length - 1].end, a: h.card.start, b: h.card.end, prev: nb(cards[i - 1]), next: nb(cards[i + 1]), dur, x0: x, moved: false }
      s.set({ selected: idx[0], capSel: true, selectedOverlay: null }); return
    }
    if (h && 'o' in h && h.o) { drag.current = { kind: 'ov', mode: h.mode, id: h.o.id, s0: h.o.start, e0: h.o.end, x0: x, moved: false }; s.set({ selectedOverlay: h.o.id, capSel: false }); return }
    const wi = s.words.findIndex(w => t >= w.start && t < w.end)
    s.set({ selected: wi >= 0 ? wi : null, capSel: false, selectedOverlay: null })
    seek(t)
  }
  const onMove = (e: React.PointerEvent) => {
    const { x, y } = at(e), d = drag.current
    if (!d) { const h = hit(x, y); ref.current!.style.cursor = h ? (h.mode === 'move' ? 'grab' : 'ew-resize') : e.shiftKey ? 'crosshair' : 'default'; return }
    if (d.kind === 'cut') { setRubber({ a: d.t0, b: tOf(x) }); return }
    if (Math.abs(x - d.x0) < 3 && !d.moved) return
    d.moved = true; ref.current!.style.cursor = d.mode === 'move' ? 'grabbing' : 'ew-resize'
    const dt = (x - d.x0) / pps
    if (d.kind === 'card') s.setWords(() => applyCardDrag(d, dt))
    else {
      const len = d.e0 - d.s0
      if (d.mode === 'move') { const st = Math.min(dur - len, Math.max(0, d.s0 + dt)); s.updateOverlay(d.id, { start: st, end: st + len }) }
      else if (d.mode === 'l') s.updateOverlay(d.id, { start: Math.min(d.e0 - 0.1, Math.max(0, d.s0 + dt)) })
      else s.updateOverlay(d.id, { end: Math.min(dur, Math.max(d.s0 + 0.1, d.e0 + dt)) })
    }
  }
  const onUp = (e: React.PointerEvent) => {
    const d = drag.current; drag.current = null
    if (d?.kind === 'cut') { if (rubber && Math.abs(rubber.b - rubber.a) > 0.05) s.set({ cuts: mergeCuts([...s.cuts, { start: Math.min(rubber.a, rubber.b), end: Math.max(rubber.a, rubber.b) }]) }); setRubber(null); return }
    if (d && !d.moved) seek(tOf(at(e).x))   // a click on a block selects it and moves the playhead there
  }
  const onDbl = (e: React.MouseEvent) => {
    const { x, y } = at(e), h = hit(x, y)
    if (h && 'card' in h && h.card) setEditing({ card: h.card, text: h.card.words.map(w => w.text).join(' ') })
  }
  const commit = () => { if (editing) s.setWords(ws => setCardText(ws, editing.card, editing.text)); setEditing(null) }
  // a double-click from elsewhere (canvas, list) can ask the timeline to open its editor
  useEffect(() => { if (s.editCard == null) return; const c = cards.find(c => s.words.indexOf(c.words[0]) === s.editCard); if (c && wrap.current) wrap.current.scrollLeft = c.start * pps - 60 }, [s.editCard]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="timeline">
      <div className="tl-tools">
        <div className="tl-left">
          <span className="hint" title="Drag a caption to move it, drag its edges to stretch, double-click to retype. Shift-drag anywhere to cut the video.">{Icon.scissors} Shift-drag to cut</span>
          {s.cuts.length > 0 && <button className="ghost" onClick={() => s.set({ cuts: [] })}>Clear cuts ({s.cuts.length})</button>}
        </div>
        <div className="tl-transport">
          <button className="icon" title="Back 5 s" onClick={() => seek(Math.max(0, s.time - 5))}>{Icon.rewind}</button>
          <button className="play" title="Play / pause (space)" onClick={toggle}>{s.playing ? Icon.pause : Icon.play}</button>
          <button className="icon" title="Forward 5 s" onClick={() => seek(Math.min(dur, s.time + 5))}>{Icon.forward}</button>
          <span className="mono time">{fmtTime(s.time)} <span className="muted">/ {fmtTime(outDur)}</span></span>
        </div>
        <div className="tl-right">
          <button className="icon" title="Zoom out" onClick={() => setPps(p => Math.max(10, p / 1.5))}>{Icon.zoomOut}</button>
          <input type="range" min={10} max={600} value={pps} onChange={e => setPps(+e.target.value)} />
          <button className="icon" title="Zoom in" onClick={() => setPps(p => Math.min(600, p * 1.5))}>{Icon.zoomIn}</button>
          <button className="ghost" onClick={() => wrap.current && s.project && setPps(Math.max(20, (wrap.current.clientWidth - 20) / s.project.duration))}>Fit</button>
        </div>
      </div>
      <div className="tl-body">
        <div className="tl-labels">
          <span style={{ top: CAP_Y, height: CAP_H }}>{Icon.captions}Captions</span>
          <span style={{ top: AUD_Y, height: AUD_H }}>{Icon.audio}Audio</span>
          <span style={{ top: EL_Y, height: EL_H }}>{Icon.elements}Elements</span>
        </div>
        <div className="tl-scroll" ref={wrap}>
          <canvas ref={ref} onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onDoubleClick={onDbl} />
          {editing && <input className="tl-edit" autoFocus onFocus={e => e.target.select()} value={editing.text}
            style={{ left: editing.card.start * pps, top: CAP_Y - 2, width: Math.max(180, (editing.card.end - editing.card.start) * pps) }}
            onChange={e => setEditing({ ...editing, text: e.target.value })} onBlur={commit}
            onKeyDown={e => { if (e.key === 'Enter') commit(); if (e.key === 'Escape') setEditing(null) }} />}
        </div>
      </div>
    </div>
  )
}
