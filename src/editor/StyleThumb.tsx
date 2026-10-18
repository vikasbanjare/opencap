import { useEffect, useRef } from 'react'
import { drawCaptions } from '../captions/engine'
import type { CaptionStyle, Card } from '../captions/types'

// A sample caption drawn by the real renderer, so the thumbnail is exactly what the video will show.
const LOOP = 2.8, REST = 1.4
const CARD: Card = {
  id: 'thumb', start: 0, end: 2.4, lines: [], emphIndex: 3,
  words: ([['Make', 0.1, 0.45], ['every', 0.45, 0.75], ['word', 0.75, 1.1], ['pop', 1.1, 1.7]] as const).map(([text, start, end]) => ({ text, start, end })),
}

export function StyleThumb({ style, portrait = false }: { style: CaptionStyle; portrait?: boolean }) {
  const W = portrait ? 270 : 320, H = portrait ? 480 : 180
  const ref = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const c = ref.current!, ctx = c.getContext('2d')!, el = c.parentElement!
    const s: CaptionStyle = { ...style, font: { ...style.font, size: Math.min(150, style.font.size * (portrait ? 1.25 : 1.9)) },
      layout: { ...style.layout, anchorY: portrait ? 0.68 : 0.55, maxWidth: portrait ? 0.86 : 0.9, anchorX: style.layout.align === 'left' ? 0.06 : 0.5 } }
    let raf = 0, t0 = 0, hover = false
    const draw = (t: number) => {
      const g = ctx.createLinearGradient(0, 0, W * 0.4, H); g.addColorStop(0, portrait ? '#3b3350' : '#2b2140'); g.addColorStop(1, portrait ? '#14171f' : '#0e1a26')
      ctx.fillStyle = g; ctx.fillRect(0, 0, W, H)
      if (portrait) { // a soft "subject" glow so the tile reads like a frame of footage
        const r = ctx.createRadialGradient(W * 0.5, H * 0.38, 10, W * 0.5, H * 0.38, W * 0.55); r.addColorStop(0, 'rgba(255,190,150,.35)'); r.addColorStop(1, 'rgba(255,190,150,0)')
        ctx.fillStyle = r; ctx.fillRect(0, 0, W, H)
      }
      drawCaptions(ctx, t, [CARD], s, W, H)
    }
    const loop = () => { draw(((performance.now() - t0) / 1000) % LOOP); if (hover) raf = requestAnimationFrame(loop) }
    const enter = () => { hover = true; t0 = performance.now(); cancelAnimationFrame(raf); loop() }
    const leave = () => { hover = false; cancelAnimationFrame(raf); draw(REST) }
    draw(REST)
    document.fonts.load(`${style.font.weight} 40px "${style.font.family}"`).catch(() => null).then(() => { if (!hover) draw(REST) })
    el.addEventListener('mouseenter', enter); el.addEventListener('mouseleave', leave)
    return () => { cancelAnimationFrame(raf); el.removeEventListener('mouseenter', enter); el.removeEventListener('mouseleave', leave) }
  }, [style, portrait, W, H])
  return <canvas ref={ref} width={W} height={H} />
}
