import type { Anim, Card, CaptionStyle, Ease, Word, WordIn } from './types'

export const DEFAULT_ANIM: Anim = { word: 'none', wordMs: 220, stagger: 60, active: 'none', activeColor: null, activeScale: 1.15, loop: 'none', slideX: 0, rotateFrom: 0 }

const clamp01 = (p: number) => Math.min(1, Math.max(0, p))
const bounceOut = (p: number) => {
  const n = 7.5625, d = 2.75
  if (p < 1 / d) return n * p * p
  if (p < 2 / d) return n * (p -= 1.5 / d) * p + 0.75
  if (p < 2.5 / d) return n * (p -= 2.25 / d) * p + 0.9375
  return n * (p -= 2.625 / d) * p + 0.984375
}
const lum = (c: string) => { const m = /^#([0-9a-f]{6})/i.exec(c); if (!m) return 1; const n = parseInt(m[1], 16); return (0.2126 * (n >> 16) + 0.7152 * ((n >> 8) & 255) + 0.0722 * (n & 255)) / 255 }

type Tx = { dx: number; dy: number; sx: number; sy: number; rot: number; a: number; blur: number; chars: number }
/** Per-word entrance at progress q (0..1); f = font px. */
function wordIn(kind: WordIn, q: number, f: number): Tx {
  const o: Tx = { dx: 0, dy: 0, sx: 1, sy: 1, rot: 0, a: 1, blur: 0, chars: 1 }
  if (kind === 'none' || q >= 1) return o
  const e = ease('easeOut', q), b = ease('easeOutBack', q), fast = Math.min(1, q * 3)
  switch (kind) {
    case 'pop': o.sx = o.sy = 0.3 + 0.7 * b; o.a = fast; break
    case 'bounce': o.dy = -(1 - bounceOut(q)) * f * 0.9; o.a = Math.min(1, q * 4); break
    case 'slideUp': o.dy = (1 - e) * f * 0.6; o.a = e; break
    case 'drop': o.dy = -(1 - b) * f * 0.7; o.a = fast; break
    case 'slideLeft': o.dx = (1 - e) * f * 1.4; o.a = e; break
    case 'zoom': o.sx = o.sy = 1 + (1 - e) * 1.6; o.a = e; break
    case 'blur': o.blur = (1 - e) * f * 0.25; o.a = e; break
    case 'typewriter': o.chars = q; break
    case 'flip': o.sy = Math.max(0.02, b); o.a = fast; break
    case 'stretch': o.sx = 1 + (1 - b) * 0.8; o.sy = 0.4 + 0.6 * b; o.a = fast; break
    case 'spin': o.rot = -(1 - b) * 0.6; o.sx = o.sy = 0.5 + 0.5 * b; o.a = fast; break
  }
  return o
}
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

type Laid = { word: Word; text: string; x: number; y: number; w: number; slot: number; line: number; emph: boolean }
type Layout = { items: Laid[]; lines: { x: number; y: number; w: number; h: number }[]; box: { x: number; y: number; w: number; h: number }; fontPx: number }

const fontStr = (s: CaptionStyle, k: number, emph: boolean) => {
  const w = emph ? Math.min(900, s.font.weight + s.emphasis.weightDelta) : s.font.weight
  const it = (s.font.italic || (emph && s.emphasis.italic)) ? 'italic ' : ''
  const px = s.font.size * k * (emph ? s.emphasis.sizeRatio : 1)
  return `${it}${w} ${px}px "${s.font.family}", sans-serif`
}

const cache = new Map<string, Layout>()
if (typeof document !== 'undefined') document.fonts?.addEventListener('loadingdone', () => cache.clear())

export function layoutCard(ctx: CanvasRenderingContext2D, card: Card, s: CaptionStyle, W: number, H: number): Layout {
  // re-measure once the real font has loaded, or widths from the fallback font stick (words collide)
  const ready = typeof document === 'undefined' || document.fonts?.check(`${s.font.weight} 20px "${s.font.family}"`)
  const key = `${ready}|${card.id}|${s.id}|${W}x${H}|${card.words.map(w => w.text).join(' ')}|${card.emphIndex}|${JSON.stringify(s.font)}|${JSON.stringify(s.emphasis)}|${JSON.stringify(s.layout)}|${s.anim?.active}${s.anim?.activeScale}`
  const hit = cache.get(key); if (hit) return hit
  const k = W / 1080
  const fontPx = s.font.size * k
  const space = fontPx * 0.28
  const maxW = s.layout.maxWidth * W
  const lineH = fontPx * s.layout.lineHeight * (s.emphasis.sizeRatio > 1 && card.emphIndex >= 0 ? Math.max(1, (s.emphasis.sizeRatio + 1) / 2) : 1)
  // styles that enlarge the spoken word get room for it, so neighbours never overlap
  const grow = s.anim?.active === 'scale' ? Math.max(1, s.anim.activeScale ?? 1.15) : 1
  // measure
  const items: Laid[] = card.words.map((word, i) => {
    const emph = i === card.emphIndex && s.emphasis.mode !== 'none'
    ctx.font = fontStr(s, k, emph)
    const text = applyCase(word.text, s.font.case, i === 0)
    const w = ctx.measureText(text).width + s.font.letterSpacing * k * text.length
    return { word, text, x: 0, y: 0, w, slot: w * grow, line: 0, emph }
  })
  // wrap
  const lines: Laid[][] = [[]]
  let lw = 0
  for (const it of items) {
    const add = (lines[lines.length - 1].length ? space : 0) + it.slot
    if (lw + add > maxW && lines[lines.length - 1].length) { lines.push([]); lw = 0 }
    lines[lines.length - 1].push(it); lw += (lines[lines.length - 1].length > 1 ? space : 0) + it.slot
    it.line = lines.length - 1
  }
  // position (anchorY is the block centre)
  const totalH = lines.length * lineH
  const top = s.layout.anchorY * H - totalH / 2
  const lineBoxes: Layout['lines'] = []
  let maxLineW = 0
  lines.forEach((ln, li) => {
    const w = ln.reduce((n, it) => n + it.slot, 0) + space * (ln.length - 1)
    maxLineW = Math.max(maxLineW, w)
    const x0 = s.layout.align === 'left' ? s.layout.anchorX * W : s.layout.anchorX * W - w / 2
    let x = x0
    for (const it of ln) { it.x = x + (it.slot - it.w) / 2; it.y = top + li * lineH + lineH / 2; x += it.slot + space }
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
    const A: Anim = { ...DEFAULT_ANIM, ...(s.anim ?? {}) }   // styles saved before animations existed have no anim
    const scale = s.entrance.scaleFrom + (1 - s.entrance.scaleFrom) * p
    const blur = s.entrance.blurPx * (1 - p) * k
    const L = layoutCard(ctx, card, s, W, H)
    const cx = L.box.x + L.box.w / 2, cy = L.box.y + L.box.h / 2
    ctx.save()
    ctx.globalAlpha = alpha
    let floatY = 0
    if (A.loop === 'float') floatY = Math.sin(t * 2.2) * L.fontPx * 0.06
    ctx.translate(cx + A.slideX * (1 - p) * W, cy + s.entrance.riseP * (1 - p) * H + floatY)
    if (A.rotateFrom) ctx.rotate(A.rotateFrom * (1 - p) * Math.PI / 180)
    ctx.scale(scale, scale); ctx.translate(-cx, -cy)
    if (blur > 0.3) ctx.filter = `blur(${blur.toFixed(1)}px)`   // boxes; words set their own filter
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
    const f = L.fontPx
    const hot = A.activeColor ?? s.emphasis.color ?? '#FFE600'
    const cardBlur = blur > 0.3 ? blur : 0
    L.items.forEach((it, i) => {
      const st = wordState(it.word, t, s)
      if (st === 'hidden') return
      // entrance: staggered from the card start in whole mode, else from the spoken time
      const t0 = s.reveal.mode === 'whole' ? card.start + i * A.stagger / 1000 : it.word.start
      const q = (t - t0) * 1000 / Math.max(1, A.wordMs)
      if (A.word !== 'none' && st !== 'inactive' && q < 0) return
      const tx = wordIn(A.word, st === 'inactive' ? 1 : clamp01(q), f)
      const speaking = t >= it.word.start && t < it.word.end
      const ap = speaking ? clamp01((t - it.word.start) / 0.08) : 0
      if (A.active === 'scale') { const m = 1 + (A.activeScale - 1) * ap; tx.sx *= m; tx.sy *= m }
      if (A.active === 'lift') tx.dy -= f * 0.15 * ap
      // loops
      if (A.loop === 'wave') tx.dy += Math.sin(t * 7 + i * 0.9) * f * 0.08
      if (A.loop === 'shake' && it.emph) { tx.dx += Math.sin(t * 55) * f * 0.035; tx.dy += Math.cos(t * 47) * f * 0.035 }
      if (A.loop === 'pulse' && it.emph) { const m = 1 + 0.08 * Math.sin(t * 9); tx.sx *= m; tx.sy *= m }
      if (A.loop === 'jitter') tx.rot += (((Math.floor(t * 8) * 7 + i * 13) % 7) - 3) * 0.014   // hand-drawn boil at 8 fps

      ctx.font = fontStr(s, k, it.emph)
      let fill = s.colors.text
      if (it.emph && s.emphasis.color) fill = s.emphasis.color
      if (A.active === 'color' && speaking) fill = hot
      if (s.emphasis.box && i === activeIdx) fill = '#111111'
      let a = 1
      if (st === 'inactive') a = s.reveal.inactiveOpacity
      if (st === 'activating') a = s.reveal.inactiveOpacity + (1 - s.reveal.inactiveOpacity) * wordProgress(it.word, t, s)
      const text = tx.chars < 1 ? it.text.slice(0, Math.ceil(it.text.length * tx.chars)) : it.text
      if (!text) return
      ctx.save(); ctx.globalAlpha = alpha * a * tx.a
      const wx = it.x + it.w / 2
      ctx.translate(wx + tx.dx, it.y + tx.dy); if (tx.rot) ctx.rotate(tx.rot); ctx.scale(tx.sx, tx.sy); ctx.translate(-wx, -it.y)
      const b = Math.max(cardBlur, tx.blur)
      ctx.filter = b > 0.3 ? `blur(${b.toFixed(1)}px)` : 'none'
      if (s.font.letterSpacing) (ctx as CanvasRenderingContext2D & { letterSpacing: string }).letterSpacing = `${s.font.letterSpacing * k}px`
      // highlighter behind the spoken word, growing left to right
      if (A.active === 'marker' && speaking) {
        const g = clamp01((t - it.word.start) / 0.12), px = f * 0.18
        rrect(ctx, it.x - px, it.y - f * 0.6, (it.w + px * 2) * g, f * 1.2, f * 0.18); ctx.fillStyle = hot; ctx.fill()
        fill = lum(hot) > 0.6 ? '#111111' : '#FFFFFF'
      }
      if (st === 'inactive' && s.reveal.hollowInactive) {
        ctx.lineWidth = Math.max(1, 2 * k); ctx.strokeStyle = fill; ctx.strokeText(text, it.x, it.y)
      } else {
        const markerOn = A.active === 'marker' && speaking
        if (s.shadow.opacity > 0 && s.box.mode === 'none' && !markerOn) { ctx.shadowColor = `rgba(0,0,0,${s.shadow.opacity})`; ctx.shadowBlur = s.shadow.blur * k; ctx.shadowOffsetY = s.shadow.offsetY * k }
        if (s.stroke > 0 && !markerOn) { ctx.lineJoin = 'round'; ctx.lineWidth = s.stroke * 2 * k; ctx.strokeStyle = s.colors.stroke; ctx.strokeText(text, it.x, it.y) }
        ctx.shadowColor = 'transparent'
        if (it.emph && s.emphasis.glowPx) { ctx.shadowColor = fill; ctx.shadowBlur = s.emphasis.glowPx * k }
        if (A.active === 'glow' && speaking) { fill = hot; ctx.shadowColor = hot; ctx.shadowBlur = 22 * k * ap }
        // karaoke sweep: words already sung stay lit, the current one fills left to right
        const sung = A.active === 'sweep' && t >= it.word.end
        ctx.fillStyle = sung ? hot : fill; ctx.fillText(text, it.x, it.y)
        if (A.active === 'sweep' && speaking) {
          const g = clamp01((t - it.word.start) / Math.max(0.05, it.word.end - it.word.start))
          ctx.save(); ctx.beginPath(); ctx.rect(it.x - 2, it.y - f, it.w * g + 2, f * 2); ctx.clip(); ctx.fillStyle = hot; ctx.fillText(text, it.x, it.y); ctx.restore()
        }
        if (it.emph && s.emphasis.underline) { ctx.fillRect(it.x, it.y + f * 0.55, it.w, Math.max(2, 3 * k)) }
        if (A.active === 'underline' && speaking) { ctx.shadowColor = 'transparent'; ctx.fillStyle = hot; ctx.fillRect(it.x, it.y + f * 0.58, it.w * clamp01((t - it.word.start) / 0.13), Math.max(2, 5 * k)) }
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
