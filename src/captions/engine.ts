import type { Card, CaptionStyle, Ease, Word } from './types'
import { applyCase } from './chunk'

// All sizes in the style are specified for a 1080 px wide frame; `k` scales to the canvas.

export const ease = (e: Ease, p: number) => {
  p = Math.min(1, Math.max(0, p))
  switch (e) {
    case 'linear': return p
    case 'easeOut': return 1 - Math.pow(1 - p, 3)
    case 'easeInOut': return p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2
    case 'easeOutBack': { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2) }
  }
}

type Laid = { word: Word; text: string; x: number; y: number; w: number; line: number; emph: boolean }
type Layout = { items: Laid[]; lines: { x: number; y: number; w: number; h: number }[]; box: { x: number; y: number; w: number; h: number }; fontPx: number }

const fontStr = (s: CaptionStyle, k: number, emph: boolean) => {
  const w = emph ? Math.min(900, s.font.weight + s.emphasis.weightDelta) : s.font.weight
  const it = (s.font.italic || (emph && s.emphasis.italic)) ? 'italic ' : ''
  const px = s.font.size * k * (emph ? s.emphasis.sizeRatio : 1)
  return `${it}${w} ${px}px "${s.font.family}", sans-serif`
}

const cache = new Map<string, Layout>()

export function layoutCard(ctx: CanvasRenderingContext2D, card: Card, s: CaptionStyle, W: number, H: number): Layout {
  const key = `${card.id}|${s.id}|${W}x${H}|${card.words.map(w => w.text).join(' ')}|${card.emphIndex}|${JSON.stringify(s.font)}|${JSON.stringify(s.emphasis)}|${JSON.stringify(s.layout)}`
  const hit = cache.get(key); if (hit) return hit
  const k = W / 1080
  const fontPx = s.font.size * k
  const space = fontPx * 0.28
  const maxW = s.layout.maxWidth * W
  const lineH = fontPx * s.layout.lineHeight * (s.emphasis.sizeRatio > 1 && card.emphIndex >= 0 ? Math.max(1, (s.emphasis.sizeRatio + 1) / 2) : 1)
  // measure
  const items: Laid[] = card.words.map((word, i) => {
    const emph = i === card.emphIndex && s.emphasis.mode !== 'none'
    ctx.font = fontStr(s, k, emph)
    const text = applyCase(word.text, s.font.case, i === 0)
    return { word, text, x: 0, y: 0, w: ctx.measureText(text).width + s.font.letterSpacing * k * text.length, line: 0, emph }
  })
  // wrap
  const lines: Laid[][] = [[]]
  let lw = 0
  for (const it of items) {
    const add = (lines[lines.length - 1].length ? space : 0) + it.w
    if (lw + add > maxW && lines[lines.length - 1].length) { lines.push([]); lw = 0 }
    lines[lines.length - 1].push(it); lw += (lines[lines.length - 1].length > 1 ? space : 0) + it.w
    it.line = lines.length - 1
  }
  // position (anchorY is the block centre)
  const totalH = lines.length * lineH
  const top = s.layout.anchorY * H - totalH / 2
  const lineBoxes: Layout['lines'] = []
  let maxLineW = 0
  lines.forEach((ln, li) => {
    const w = ln.reduce((n, it) => n + it.w, 0) + space * (ln.length - 1)
    maxLineW = Math.max(maxLineW, w)
    const x0 = s.layout.align === 'left' ? s.layout.anchorX * W : s.layout.anchorX * W - w / 2
    let x = x0
    for (const it of ln) { it.x = x; it.y = top + li * lineH + lineH / 2; x += it.w + space }
    lineBoxes.push({ x: x0, y: top + li * lineH, w, h: lineH })
  })
  const bx = s.layout.align === 'left' ? s.layout.anchorX * W : s.layout.anchorX * W - maxLineW / 2
  const layout: Layout = { items, lines: lineBoxes, box: { x: bx, y: top, w: maxLineW, h: totalH }, fontPx }
  if (cache.size > 400) cache.clear()
  cache.set(key, layout)
  return layout
}

function rrect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  r = Math.min(r, h / 2, w / 2)
  ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r)
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath()
}

/** Draw every card active at source time t. Deterministic: same (t, cards, style) → same pixels, so preview == export. */
export function drawCaptions(ctx: CanvasRenderingContext2D, t: number, cards: Card[], s: CaptionStyle, W: number, H: number) {
  const k = W / 1080
  for (const card of cards) {
    if (t < card.start || t >= card.end) continue
    const age = (t - card.start) * 1000
    const left = (card.end - t) * 1000
    // entrance
    const p = s.entrance.durationMs > 0 ? ease(s.entrance.ease, age / s.entrance.durationMs) : 1
    let alpha = p
    if (s.exit.mode === 'fade' && left < s.exit.ms) alpha = Math.min(alpha, left / s.exit.ms)
    const scale = s.entrance.scaleFrom + (1 - s.entrance.scaleFrom) * p
    const blur = s.entrance.blurPx * (1 - p) * k
    const L = layoutCard(ctx, card, s, W, H)
    const cx = L.box.x + L.box.w / 2, cy = L.box.y + L.box.h / 2
    ctx.save()
    ctx.globalAlpha = alpha
    ctx.translate(cx, cy + s.entrance.riseP * (1 - p) * H); ctx.scale(scale, scale); ctx.translate(-cx, -cy)
    if (blur > 0.3) ctx.filter = `blur(${blur.toFixed(1)}px)`
    ctx.textBaseline = 'middle'; ctx.textAlign = 'left'
    // boxes behind text
    const padX = s.box.padX * L.fontPx, padY = s.box.padY * L.fontPx
    if (s.box.mode === 'pill' || s.box.mode === 'bar') {
      const b = s.box.mode === 'bar' && s.layout.align === 'left'
        ? { x: L.box.x - padX, y: L.box.y - padY, w: s.layout.maxWidth * W + padX * 2, h: L.box.h + padY * 2 }   // pre-sized bar
        : { x: L.box.x - padX, y: L.box.y - padY, w: L.box.w + padX * 2, h: L.box.h + padY * 2 }
      ctx.save()
      if (s.shadow.opacity > 0 && s.box.mode === 'pill') { ctx.shadowColor = `rgba(0,0,0,${s.shadow.opacity})`; ctx.shadowBlur = s.shadow.blur * k; ctx.shadowOffsetY = s.shadow.offsetY * k }
      rrect(ctx, b.x, b.y, b.w, b.h, s.box.radius * k); ctx.fillStyle = s.box.fill; ctx.fill()
      if (s.box.outline) { ctx.lineWidth = s.box.outline * k; ctx.strokeStyle = s.box.outlineColor; ctx.stroke() }
      ctx.restore()
    } else if (s.box.mode === 'linePill') {
      // grows per word in append mode: only cover revealed words
      for (const ln of L.lines) {
        const revealed = L.items.filter(it => it.line === L.lines.indexOf(ln) && wordState(it.word, t, s) !== 'hidden')
        if (!revealed.length) continue
        const x0 = revealed[0].x, x1 = revealed[revealed.length - 1].x + revealed[revealed.length - 1].w
        rrect(ctx, x0 - padX, ln.y - padY * 0.5, x1 - x0 + padX * 2, ln.h + padY, s.box.radius * k); ctx.fillStyle = s.box.fill; ctx.fill()
      }
    }
    // moving highlight box on the active word
    const activeIdx = L.items.findIndex(it => wordState(it.word, t, s) === 'active')
    if (s.emphasis.box && activeIdx >= 0) {
      const it = L.items[activeIdx]
      const px = s.emphasis.box.padX * L.fontPx, py = s.emphasis.box.padY * L.fontPx
      rrect(ctx, it.x - px, it.y - L.fontPx * 0.62 - py, it.w + px * 2, L.fontPx * 1.24 + py * 2, s.emphasis.box.radius * k)
      ctx.fillStyle = s.emphasis.box.fill; ctx.fill()
    }
    // words
    L.items.forEach((it, i) => {
      const st = wordState(it.word, t, s)
      if (st === 'hidden') return
      ctx.font = fontStr(s, k, it.emph)
      let fill = s.colors.text
      if (it.emph && s.emphasis.color) fill = s.emphasis.color
      if (s.emphasis.box && i === activeIdx) fill = '#111111'
      let a = 1
      if (st === 'inactive') a = s.reveal.inactiveOpacity
      if (st === 'activating') a = s.reveal.inactiveOpacity + (1 - s.reveal.inactiveOpacity) * wordProgress(it.word, t, s)
      ctx.save(); ctx.globalAlpha = alpha * a
      if (s.font.letterSpacing) (ctx as CanvasRenderingContext2D & { letterSpacing: string }).letterSpacing = `${s.font.letterSpacing * k}px`
      if (st === 'inactive' && s.reveal.hollowInactive) {
        ctx.lineWidth = Math.max(1, 2 * k); ctx.strokeStyle = fill; ctx.strokeText(it.text, it.x, it.y)
      } else {
        if (s.shadow.opacity > 0 && s.box.mode === 'none') { ctx.shadowColor = `rgba(0,0,0,${s.shadow.opacity})`; ctx.shadowBlur = s.shadow.blur * k; ctx.shadowOffsetY = s.shadow.offsetY * k }
        if (s.stroke > 0) { ctx.lineJoin = 'round'; ctx.lineWidth = s.stroke * 2 * k; ctx.strokeStyle = s.colors.stroke; ctx.strokeText(it.text, it.x, it.y) }
        ctx.shadowColor = 'transparent'
        if (it.emph && s.emphasis.glowPx) { ctx.shadowColor = fill; ctx.shadowBlur = s.emphasis.glowPx * k }
        ctx.fillStyle = fill; ctx.fillText(it.text, it.x, it.y)
        if (it.emph && s.emphasis.underline) { ctx.fillRect(it.x, it.y + L.fontPx * 0.55, it.w, Math.max(2, 3 * k)) }
      }
      ctx.restore()
    })
    ctx.restore()
  }
}

type WState = 'hidden' | 'inactive' | 'activating' | 'active' | 'done'
function wordState(w: Word, t: number, s: CaptionStyle): WState {
  const m = s.reveal.mode
  if (m === 'whole') return t >= w.start && t < w.end ? 'active' : 'done'
  if (m === 'append') return t < w.start ? 'hidden' : t < w.end ? 'active' : 'done'
  if (m === 'lineStack') return t < w.start - 0.05 ? 'hidden' : t < w.end ? 'active' : 'done'
  // wordFill
  if (t < w.start) return 'inactive'
  if (t < w.start + s.reveal.wordMs / 1000) return 'activating'
  return t < w.end ? 'active' : 'done'
}
const wordProgress = (w: Word, t: number, s: CaptionStyle) => s.reveal.wordMs ? Math.min(1, (t - w.start) * 1000 / s.reveal.wordMs) : 1

// line-stack: a line is hidden until its first word starts
export function lineVisible(_: number) { return true }
