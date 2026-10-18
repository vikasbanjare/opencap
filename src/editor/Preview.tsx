import { useEffect, useMemo, useRef } from 'react'
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

  // overlay drag
  const toFrame = (e: React.PointerEvent) => { const r = canvasRef.current!.getBoundingClientRect(); return { x: (e.clientX - r.left) / r.width, y: (e.clientY - r.top) / r.height } }
  const onDown = (e: React.PointerEvent) => {
    const p = toFrame(e)
    const hit = [...s.overlays].reverse().find(o => (o.kind !== 'video' || o.fit === 'pip') && Math.abs(o.x - p.x) < 0.15 && Math.abs(o.y - p.y) < 0.1 && s.time >= o.start && s.time < o.end)
    if (hit) { dragging.current = { id: hit.id, dx: hit.x - p.x, dy: hit.y - p.y }; s.set({ selectedOverlay: hit.id, tab: 'elements' }); (e.target as Element).setPointerCapture(e.pointerId) }
  }
  const onMove = (e: React.PointerEvent) => { if (!dragging.current) return; const p = toFrame(e); s.updateOverlay(dragging.current.id, { x: Math.min(1, Math.max(0, p.x + dragging.current.dx)), y: Math.min(1, Math.max(0, p.y + dragging.current.dy)) }) }
  const onUp = () => { dragging.current = null }

  return (
    <div className="preview">
      <video ref={videoRef} src={s.project?.playUrl} playsInline preload="auto" crossOrigin="anonymous" style={{ display: 'none' }}
        onPlay={() => s.set({ playing: true })} onPause={() => s.set({ playing: false })} onEnded={() => s.set({ playing: false })} />
      {s.audioUrl && <audio ref={altRef} src={s.audioUrl} preload="auto" />}
      {s.music && <audio ref={musicRef} src={s.music.url} preload="auto" />}
      <canvas ref={canvasRef} width={size.w} height={size.h} style={{ aspectRatio: `${size.w}/${size.h}` }}
        onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} />
    </div>
  )
}
