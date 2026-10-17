import { useEffect, useMemo, useRef } from 'react'
import { useEditor, aspectSize } from '../store'
import { drawFrame } from '../lib/compositor'
import { cutsFromWords, inCut, mergeCuts } from '../lib/timeline'
import type { Card } from '../captions/types'

export const imageCache = new Map<string, HTMLImageElement>()

export function Preview({ cards, videoRef }: { cards: Card[]; videoRef: React.RefObject<HTMLVideoElement | null> }) {
  const s = useEditor()
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const size = useMemo(() => s.project ? aspectSize(s.aspect, s.project, 1920) : { w: 1080, h: 1920 }, [s.aspect, s.project])
  const allCuts = useMemo(() => mergeCuts([...s.cuts, ...cutsFromWords(s.words)]), [s.cuts, s.words])
  const dragging = useRef<{ id: string; dx: number; dy: number } | null>(null)

  // preload overlay images
  useEffect(() => { for (const o of s.overlays) if (o.kind === 'image' && o.src && !imageCache.has(o.src)) { const im = new Image(); im.src = o.src; imageCache.set(o.src, im) } }, [s.overlays])

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
        const ctx = c.getContext('2d')!
        drawFrame(ctx, c.width, c.height, { src: v, srcW: v.videoWidth || s.project.width, srcH: v.videoHeight || s.project.height, t, cards, style: s.style, captionsOn: s.captionsOn, overlays: s.overlays, zooms: s.zooms, pan: s.pan, images: imageCache })
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [cards, s.style, s.overlays, s.zooms, s.pan, s.captionsOn, s.project, allCuts, videoRef])

  // overlay drag
  const toFrame = (e: React.PointerEvent) => { const r = canvasRef.current!.getBoundingClientRect(); return { x: (e.clientX - r.left) / r.width, y: (e.clientY - r.top) / r.height } }
  const onDown = (e: React.PointerEvent) => {
    const p = toFrame(e)
    const hit = [...s.overlays].reverse().find(o => Math.abs(o.x - p.x) < 0.12 && Math.abs(o.y - p.y) < 0.08 && s.time >= o.start && s.time < o.end)
    if (hit) { dragging.current = { id: hit.id, dx: hit.x - p.x, dy: hit.y - p.y }; s.set({ selectedOverlay: hit.id, tab: 'elements' }); (e.target as Element).setPointerCapture(e.pointerId) }
  }
  const onMove = (e: React.PointerEvent) => { if (!dragging.current) return; const p = toFrame(e); s.updateOverlay(dragging.current.id, { x: Math.min(1, Math.max(0, p.x + dragging.current.dx)), y: Math.min(1, Math.max(0, p.y + dragging.current.dy)) }) }
  const onUp = () => { dragging.current = null }

  return (
    <div className="preview">
      <video ref={videoRef} src={s.project?.playUrl} playsInline preload="auto" crossOrigin="anonymous" style={{ display: 'none' }}
        onPlay={() => s.set({ playing: true })} onPause={() => s.set({ playing: false })} onEnded={() => s.set({ playing: false })} />
      <canvas ref={canvasRef} width={size.w} height={size.h} style={{ aspectRatio: `${size.w}/${size.h}` }}
        onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} />
    </div>
  )
}
