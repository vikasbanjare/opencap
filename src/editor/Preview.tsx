import { useEffect, useMemo, useRef, useState } from 'react'
import { layoutCard } from '../captions/engine'
import { idxOf, setCardText } from '../captions/edit'
import { useEditor, aspectSize, mediaCache, ensureMedia } from '../store'
import { drawFrame, videoOverlaysAt } from '../lib/compositor'
import { cutsFromWords, inCut, mergeCuts } from '../lib/timeline'
import type { Card } from '../captions/types'

export function Preview({ cards, videoRef }: { cards: Card[]; videoRef: React.RefObject<HTMLVideoElement | null> }) {
  const s = useEditor()
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const musicRef = useRef<HTMLAudioElement>(null)
  const size = useMemo(() => s.project ? aspectSize(s.aspect, s.project, 1920) : { w: 1080, h: 1920 }, [s.aspect, s.project])
  const allCuts = useMemo(() => mergeCuts([...s.cuts, ...cutsFromWords(s.words)]), [s.cuts, s.words])
  const dragging = useRef<{ id: string; dx: number; dy: number } | null>(null)
  const capDrag = useRef<{ mode: 'move' | 'size'; x0: number; y0: number; ax: number; ay: number; size: number; d0: number } | null>(null)
  const [editing, setEditing] = useState<{ card: Card; text: string } | null>(null)
  // caption under the playhead and its box in canvas pixels
  const activeCard = () => cards.find(c => useEditor.getState().time >= c.start && useEditor.getState().time < c.end)
  const capBox = (card: Card) => { const ctx = canvasRef.current!.getContext('2d')!; return layoutCard(ctx, card, s.style, size.w, size.h).box }

  useEffect(() => { s.overlays.forEach(ensureMedia) }, [s.overlays])
  useEffect(() => { document.fonts.load(`${s.style.font.weight} 60px "${s.style.font.family}"`).catch(() => null) }, [s.style.font.family, s.style.font.weight])

  // render loop driven by the video clock
  useEffect(() => {
    let raf = 0
    const tick = () => {
      const v = videoRef.current, c = canvasRef.current
      if (v && c && s.project) {
        let t = v.currentTime
        const cut = inCut(t, allCuts)
        if (cut && !v.paused) { v.currentTime = Math.min(s.project.duration - 0.01, cut.end + 0.001); t = v.currentTime }
        if (Math.abs(t - useEditor.getState().time) > 0.02) useEditor.setState({ time: t })
        // keep B-roll clips in step with the main clock
        const vis = new Set<string>()
        for (const { o, srcT } of videoOverlaysAt(s.overlays, t)) {
          const el = mediaCache.videos.get(o.src!); if (!el) continue
          vis.add(o.src!)
          if (Math.abs(el.currentTime - srcT) > 0.25) el.currentTime = srcT
          if (!v.paused && el.paused) el.play().catch(() => null)
          if (v.paused && !el.paused) el.pause()
        }
        mediaCache.videos.forEach((el, src) => { if (!vis.has(src) && !el.paused) el.pause() })
        // music: follow transport, duck under speech
        const m = musicRef.current
        if (m && s.music) {
          const mt = t - s.music.start
          if (mt < 0 || mt > (m.duration || 1e9)) { if (!m.paused) m.pause() }
          else {
            if (Math.abs(m.currentTime - mt) > 0.3) m.currentTime = mt
            if (!v.paused && m.paused) m.play().catch(() => null)
            if (v.paused && !m.paused) m.pause()
            const speaking = s.words.some(w => !w.deleted && t >= w.start - 0.1 && t < w.end + 0.2)
            const db = s.music.gainDb + (s.music.duck && speaking ? s.music.duckDb : 0)
            m.volume = Math.min(1, Math.pow(10, db / 20))
          }
        }
        const ctx = c.getContext('2d')!
        drawFrame(ctx, c.width, c.height, { src: v, srcW: v.videoWidth || s.project.width, srcH: v.videoHeight || s.project.height, t, cards, style: s.style, captionsOn: s.captionsOn, overlays: s.overlays, zooms: s.zooms, pan: s.pan, images: mediaCache.images, videos: mediaCache.videos })
        // selection frame around the caption (preview only, never exported)
        const card = useEditor.getState().capSel && s.captionsOn ? cards.find(cd => t >= cd.start && t < cd.end) : undefined
        if (card) {
          const b = layoutCard(ctx, card, s.style, c.width, c.height).box, pad = c.width * 0.02, hs = c.width * 0.018
          ctx.save(); ctx.setLineDash([c.width * 0.012, c.width * 0.008]); ctx.lineWidth = Math.max(2, c.width / 400); ctx.strokeStyle = '#7c3aed'
          ctx.strokeRect(b.x - pad, b.y - pad, b.w + pad * 2, b.h + pad * 2); ctx.setLineDash([])
          ctx.fillStyle = '#fff'; ctx.strokeStyle = '#7c3aed'
          for (const [hx, hy] of [[b.x - pad, b.y - pad], [b.x + b.w + pad, b.y - pad], [b.x - pad, b.y + b.h + pad], [b.x + b.w + pad, b.y + b.h + pad]]) { ctx.beginPath(); ctx.rect(hx - hs / 2, hy - hs / 2, hs, hs); ctx.fill(); ctx.stroke() }
          ctx.restore()
        }
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [cards, s.style, s.overlays, s.zooms, s.pan, s.captionsOn, s.project, s.music, s.words, allCuts, videoRef])

  // processed soundtrack (denoised etc.) replaces the video's own audio in preview too
  useEffect(() => { const v = videoRef.current; if (v) v.muted = !!s.audioUrl }, [s.audioUrl, videoRef])
  const altRef = useRef<HTMLAudioElement>(null)
  useEffect(() => {
    const v = videoRef.current, a = altRef.current; if (!v || !a) return
    const sync = () => { if (!s.audioUrl) return; if (Math.abs(a.currentTime - v.currentTime) > 0.25) a.currentTime = v.currentTime; if (!v.paused && a.paused) a.play().catch(() => null); if (v.paused && !a.paused) a.pause() }
    const id = setInterval(sync, 200); return () => clearInterval(id)
  }, [s.audioUrl, videoRef])

  // pointer: elements first, then the caption (move, or resize from its corner), else clear selection
  const toFrame = (e: React.PointerEvent | React.MouseEvent) => { const r = canvasRef.current!.getBoundingClientRect(); return { x: (e.clientX - r.left) / r.width, y: (e.clientY - r.top) / r.height } }
  const capHit = (p: { x: number; y: number }) => {
    const card = s.captionsOn ? activeCard() : undefined; if (!card) return null
    const b = capBox(card), pad = 0.03
    const x0 = b.x / size.w - pad, x1 = (b.x + b.w) / size.w + pad, y0 = b.y / size.h - pad, y1 = (b.y + b.h) / size.h + pad
    if (p.x < x0 || p.x > x1 || p.y < y0 || p.y > y1) return null
    const corner = Math.hypot((p.x - x1) * size.w, (p.y - y1) * size.h) < size.w * 0.05 || Math.hypot((p.x - x0) * size.w, (p.y - y1) * size.h) < size.w * 0.05
    return { card, corner, cx: (x0 + x1) / 2, cy: (y0 + y1) / 2 }
  }
  const onDown = (e: React.PointerEvent) => {
    const p = toFrame(e)
    const hit = [...s.overlays].reverse().find(o => (o.kind !== 'video' || o.fit === 'pip') && Math.abs(o.x - p.x) < 0.15 && Math.abs(o.y - p.y) < 0.1 && s.time >= o.start && s.time < o.end)
    if (hit) { dragging.current = { id: hit.id, dx: hit.x - p.x, dy: hit.y - p.y }; s.set({ selectedOverlay: hit.id, capSel: false, tab: 'elements' }); (e.target as Element).setPointerCapture(e.pointerId); return }
    const ch = capHit(p)
    if (ch) {
      const st = s.style
      capDrag.current = { mode: ch.corner ? 'size' : 'move', x0: p.x, y0: p.y, ax: st.layout.anchorX, ay: st.layout.anchorY, size: st.font.size, d0: Math.max(0.02, Math.hypot((p.x - ch.cx) * size.w, (p.y - ch.cy) * size.h) / size.w) }
      s.set({ capSel: true, selected: idxOf(s.words, ch.card)[0] ?? null, selectedOverlay: null }); (e.target as Element).setPointerCapture(e.pointerId); return
    }
    s.set({ capSel: false, selectedOverlay: null })
  }
  const onMove = (e: React.PointerEvent) => {
    const p = toFrame(e), cd = capDrag.current
    if (cd) {
      if (cd.mode === 'move') s.setStyle(x => ({ ...x, layout: { ...x.layout, anchorY: Math.min(0.95, Math.max(0.05, cd.ay + p.y - cd.y0)), anchorX: Math.min(0.95, Math.max(0.05, cd.ax + p.x - cd.x0)) } }))
      else { const ch = capHit(p) ?? { cx: cd.ax, cy: cd.ay }; const d = Math.hypot((p.x - ch.cx) * size.w, (p.y - ch.cy) * size.h) / size.w; s.setStyle(x => ({ ...x, font: { ...x.font, size: Math.round(Math.min(220, Math.max(20, cd.size * d / cd.d0))) } })) }
      return
    }
    if (!dragging.current) { const ch = capHit(p); canvasRef.current!.style.cursor = ch ? (ch.corner ? 'nwse-resize' : 'move') : 'default'; return }
    s.updateOverlay(dragging.current.id, { x: Math.min(1, Math.max(0, p.x + dragging.current.dx)), y: Math.min(1, Math.max(0, p.y + dragging.current.dy)) })
  }
  const onUp = () => { dragging.current = null; capDrag.current = null }
  const openEditor = (card: Card) => { setEditing({ card, text: card.words.map(w => w.text).join(' ') }) }
  const onDbl = (e: React.MouseEvent) => { const ch = capHit(toFrame(e)); if (ch) openEditor(ch.card) }
  // "Edit text" from the toolbar, list or keyboard: jump to that caption and open the inline editor
  useEffect(() => {
    if (s.editCard == null) return
    const card = cards.find(c => s.words.indexOf(c.words[0]) === s.editCard); s.set({ editCard: null })
    if (!card) return
    const v = videoRef.current; if (v) { v.pause(); v.currentTime = card.start + 0.01 }
    s.set({ time: card.start + 0.01, capSel: true }); openEditor(card)
  }, [s.editCard]) // eslint-disable-line react-hooks/exhaustive-deps
  const commit = () => { if (editing) s.setWords(ws => setCardText(ws, editing.card, editing.text)); setEditing(null) }
  const edBox = editing && canvasRef.current ? (() => {
    const r = canvasRef.current.getBoundingClientRect(), pr = canvasRef.current.parentElement!.getBoundingClientRect(), b = capBox(editing.card), k = r.width / size.w
    return { left: r.left - pr.left + b.x * k - 12, top: r.top - pr.top + b.y * k - 10, width: Math.max(220, b.w * k + 24), fontSize: Math.max(14, Math.min(34, s.style.font.size * k * 0.9)) }
  })() : null

  return (
    <div className="preview">
      <video ref={videoRef} src={s.project?.playUrl} playsInline preload="auto" crossOrigin="anonymous" style={{ display: 'none' }}
        onPlay={() => s.set({ playing: true })} onPause={() => s.set({ playing: false })} onEnded={() => s.set({ playing: false })} />
      {s.audioUrl && <audio ref={altRef} src={s.audioUrl} preload="auto" />}
      {s.music && <audio ref={musicRef} src={s.music.url} preload="auto" />}
      <canvas ref={canvasRef} width={size.w} height={size.h} style={{ aspectRatio: `${size.w}/${size.h}` }}
        onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onDoubleClick={onDbl} />
      {editing && edBox && <textarea className="cap-edit" autoFocus onFocus={e => e.target.select()} value={editing.text} rows={2}
        style={{ left: edBox.left, top: edBox.top, width: edBox.width, fontSize: edBox.fontSize, fontFamily: `"${s.style.font.family}", sans-serif`, fontWeight: s.style.font.weight }}
        onChange={e => setEditing({ ...editing, text: e.target.value })} onBlur={commit}
        onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); commit() } if (e.key === 'Escape') setEditing(null) }} />}
    </div>
  )
}
