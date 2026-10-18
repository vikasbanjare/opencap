import type { Card, CaptionStyle, Overlay, ZoomKey } from '../captions/types'
import { drawCaptions } from '../captions/engine'
import { zoomAt } from './timeline'

export type FrameInput = {
  src: CanvasImageSource & { videoWidth?: number; videoHeight?: number }
  srcW: number; srcH: number
  t: number                       // source time
  cards: Card[]; style: CaptionStyle; captionsOn: boolean
  overlays: Overlay[]
  zooms: ZoomKey[]
  pan: number
  images: Map<string, HTMLImageElement>
  videos?: Map<string, HTMLVideoElement>
}

/** Visible video overlays at t with the source time each should show. */
export const videoOverlaysAt = (overlays: Overlay[], t: number) =>
  overlays.filter(o => o.kind === 'video' && o.src && t >= o.start && t < o.end).map(o => ({ o, srcT: (t - o.start) % Math.max(0.1, o.srcDuration ?? 1e9) }))

/** Draw one composed frame (reframe crop + zoom + captions + overlays). Used by preview and export alike. */
export function drawFrame(ctx: CanvasRenderingContext2D, W: number, H: number, f: FrameInput) {
  const cardEnd = (time: number) => f.cards.find(c => Math.abs(c.start - time) < 1e-3)?.end ?? time + 1
  const z = zoomAt(f.t, f.zooms, cardEnd)
  // cover-crop the source into the output aspect, panned horizontally/vertically by `pan`
  const outR = W / H, srcR = f.srcW / f.srcH
  let sw = f.srcW, sh = f.srcH
  if (srcR > outR) sw = f.srcH * outR; else sh = f.srcW / outR
  sw /= z; sh /= z
  const sx = (f.srcW - sw) * (srcR > outR ? f.pan : 0.5) + (srcR > outR ? 0 : 0)
  const sy = (f.srcH - sh) * (srcR > outR ? 0.5 : f.pan)
  ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H)
  try { ctx.drawImage(f.src, sx, sy, sw, sh, 0, 0, W, H) } catch { /* frame not ready */ }
  // full-frame B-roll replaces the picture (cover crop, same zoom), pip is drawn with the other overlays
  for (const { o } of videoOverlaysAt(f.overlays, f.t)) {
    const el = f.videos?.get(o.src!); if (!el || el.readyState < 2 || o.fit === 'pip') continue
    const vw = el.videoWidth, vh = el.videoHeight, r = vw / vh
    let cw = vw, ch = vh; if (r > outR) cw = vh * outR; else ch = vw / outR
    try { ctx.drawImage(el, (vw - cw) / 2, (vh - ch) / 2, cw, ch, 0, 0, W, H) } catch { /* not ready */ }
  }
  if (f.captionsOn) drawCaptions(ctx, f.t, f.cards, f.style, W, H)
  drawOverlays(ctx, W, H, f)
}

function drawOverlays(ctx: CanvasRenderingContext2D, W: number, H: number, f: FrameInput) {
  const k = W / 1080
  for (const o of f.overlays) {
    if (f.t < o.start || f.t >= o.end) continue
    const age = f.t - o.start
    const p = Math.min(1, age / 0.25)
    const s = 1 + 1.70158 * Math.pow(p - 1, 3) + 1.70158 * Math.pow(p - 1, 2) + Math.pow(p - 1, 3) // easeOutBack
    ctx.save(); ctx.globalAlpha = Math.min(1, age / 0.08)
    const x = o.x * W, y = o.y * H
    ctx.translate(x, y); ctx.scale(s, s); ctx.translate(-x, -y)
    if (o.kind === 'video' && o.src) {
      if (o.fit !== 'pip') { ctx.restore(); continue }
      const el = f.videos?.get(o.src)
      if (el && el.readyState >= 2) {
        const w = (o.w ?? 0.45) * W, h = w * el.videoHeight / el.videoWidth
        ctx.save(); const r = 24 * k; const X = x - w / 2, Y = y - h / 2
        ctx.beginPath(); ctx.moveTo(X + r, Y); ctx.arcTo(X + w, Y, X + w, Y + h, r); ctx.arcTo(X + w, Y + h, X, Y + h, r); ctx.arcTo(X, Y + h, X, Y, r); ctx.arcTo(X, Y, X + w, Y, r); ctx.closePath()
        ctx.shadowColor = 'rgba(0,0,0,.5)'; ctx.shadowBlur = 24 * k; ctx.fillStyle = '#000'; ctx.fill(); ctx.shadowColor = 'transparent'; ctx.clip()
        try { ctx.drawImage(el, X, Y, w, h) } catch { /* not ready */ }
        ctx.restore()
      }
    } else if (o.kind === 'image' && o.src) {
      const img = f.images.get(o.src)
      if (img && img.complete) { const w = (o.w ?? 0.4) * W, h = w * img.naturalHeight / img.naturalWidth; ctx.drawImage(img, x - w / 2, y - h / 2, w, h) }
    } else {
      ctx.font = `${o.kind === 'emoji' ? 400 : 800} ${o.size * k}px "${o.font}", "Apple Color Emoji", "Segoe UI Emoji", sans-serif`
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle'
      if (o.kind === 'text') { ctx.lineJoin = 'round'; ctx.lineWidth = 6 * k; ctx.strokeStyle = '#000'; ctx.strokeText(o.text ?? '', x, y) }
      ctx.fillStyle = o.color; ctx.fillText(o.text ?? '', x, y)
    }
    ctx.restore()
  }
}

/** On-screen box of an element in canvas pixels (centre x/y, width, height); matches drawOverlays. */
export function overlayBox(ctx: CanvasRenderingContext2D, o: Overlay, W: number, H: number, images: Map<string, HTMLImageElement>, videos?: Map<string, HTMLVideoElement>) {
  const k = W / 1080, x = o.x * W, y = o.y * H
  if (o.kind === 'video') { const el = videos?.get(o.src ?? ''); const w = (o.w ?? 0.45) * W; return { x, y, w, h: el?.videoWidth ? w * el.videoHeight / el.videoWidth : w * 9 / 16 } }
  if (o.kind === 'image') { const img = images.get(o.src ?? ''); const w = (o.w ?? 0.4) * W; return { x, y, w, h: img?.naturalWidth ? w * img.naturalHeight / img.naturalWidth : w } }
  ctx.save(); ctx.font = `${o.kind === 'emoji' ? 400 : 800} ${o.size * k}px "${o.font}", "Apple Color Emoji", sans-serif`
  const w = ctx.measureText(o.text ?? '').width; ctx.restore()
  return { x, y, w: Math.max(w, o.size * k * 0.6), h: o.size * k * 1.15 }
}
