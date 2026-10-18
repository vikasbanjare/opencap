import { useEffect, useRef } from 'react'
import { drawCaptions } from '../captions/engine'
import type { CaptionStyle, Card } from '../captions/types'

// A sample caption drawn by the real renderer, so the thumbnail is exactly what the video will show.
const W = 320, H = 180, LOOP = 2.8, REST = 1.4
const CARD: Card = {
  id: 'thumb', start: 0, end: 2.4, lines: [], emphIndex: 3,
  words: ([['Make', 0.1, 0.45], ['every', 0.45, 0.75], ['word', 0.75, 1.1], ['pop', 1.1, 1.7]] as const).map(([text, start, end]) => ({ text, start, end })),
}

export function StyleThumb({ style }: { style: CaptionStyle }) {
  const ref = useRef<HTMLCanvasElement>(null)
  useEffect(() => {
    const c = ref.current!, ctx = c.getContext('2d')!, el = c.parentElement!
    const s: CaptionStyle = { ...style, font: { ...style.font, size: Math.min(150, style.font.size * 1.9) },
      layout: { ...style.layout, anchorY: 0.55, maxWidth: 0.9, anchorX: style.layout.align === 'left' ? 0.06 : 0.5 } }
    let raf = 0, t0 = 0, hover = false
    const draw = (t: number) => {
      const g = ctx.createLinearGradient(0, 0, W, H); g.addColorStop(0, '#2b2140'); g.addColorStop(1, '#0e1a26')
      ctx.fillStyle = g; ctx.fillRect(0, 0, W, H)
      drawCaptions(ctx, t, [CARD], s, W, H)
    }
    const loop = () => { draw(((performance.now() - t0) / 1000) % LOOP); if (hover) raf = requestAnimationFrame(loop) }
    const enter = () => { hover = true; t0 = performance.now(); cancelAnimationFrame(raf); loop() }
    const leave = () => { hover = false; cancelAnimationFrame(raf); draw(REST) }
    draw(REST)
    document.fonts.load(`${style.font.weight} 40px "${style.font.family}"`).catch(() => null).then(() => { if (!hover) draw(REST) })
    el.addEventListener('mouseenter', enter); el.addEventListener('mouseleave', leave)
    return () => { cancelAnimationFrame(raf); el.removeEventListener('mouseenter', enter); el.removeEventListener('mouseleave', leave) }
  }, [style])
  return <canvas ref={ref} width={W} height={H} />
}
