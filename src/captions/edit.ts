import type { Card, Word } from './types'

// Caption-level edits on the word list. Captions are derived from words, so every edit is a word edit;
// `brk` pins caption boundaries so neighbours do not reflow after a change.

export const idxOf = (words: Word[], card: Card) => card.words.map(w => words.indexOf(w)).filter(i => i >= 0)

/** Pin a caption: it starts at its first word and the caption after it starts where it did. */
function pin(ws: Word[], idx: number[]) {
  ws[idx[0]] = { ...ws[idx[0]], brk: true, glue: false }
  const after = ws.findIndex((w, i) => i > idx[idx.length - 1] && !w.deleted && !w.hide)
  if (after >= 0) ws[after] = { ...ws[after], brk: true, glue: false }
}

/** Replace a caption's text; new words share its time span in proportion to their length. */
export function setCardText(words: Word[], card: Card, text: string): Word[] {
  const idx = idxOf(words, card); if (!idx.length) return words
  const toks = text.trim().split(/\s+/).filter(Boolean)
  const ws = words.slice(); pin(ws, idx)
  const first = ws[idx[0]], last = ws[idx[idx.length - 1]]
  if (!toks.length) { idx.forEach(i => { ws[i] = { ...ws[i], hide: true } }); return ws }
  const t0 = first.start, t1 = last.end, total = toks.reduce((n, t) => n + t.length, 0)
  let t = t0
  const fresh: Word[] = toks.map((tx, k) => {
    const d = (t1 - t0) * tx.length / total, w: Word = { text: tx, start: t, end: t + d, p: 1 }
    const old = card.words[k]; if (old) { w.emph = old.emph; w.color = old.color }
    t += d; return w
  })
  fresh[0].brk = true; for (const w of fresh.slice(1)) w.glue = true   // what you type into one caption stays one caption
  if (last.cardEnd != null) fresh[fresh.length - 1].cardEnd = last.cardEnd
  // the caption's words are contiguous in the live list; deleted/hidden words between them are dropped with them
  return [...ws.slice(0, idx[0]), ...fresh, ...ws.slice(idx[idx.length - 1] + 1)]
}

/** Shift a caption in time by dt seconds (clamped by the caller). */
export function moveCard(words: Word[], idx: number[], dt: number): Word[] {
  const ws = words.slice()
  for (const i of idx) ws[i] = { ...ws[i], start: ws[i].start + dt, end: ws[i].end + dt, cardEnd: ws[i].cardEnd != null ? ws[i].cardEnd! + dt : undefined }
  pin(ws, idx); return ws
}

/** Stretch a caption: words are rescaled from their span to [start, end]; end also becomes the on-screen end. */
export function retimeCard(words: Word[], idx: number[], start: number, end: number, keepEnd = false): Word[] {
  const ws = words.slice(), a = ws[idx[0]].start, b = ws[idx[idx.length - 1]].end
  // keepEnd: the last word stays put (left-edge stretch); otherwise words shift with the start. Never past the caption's end.
  const wordsEnd = Math.min(end, keepEnd ? b : b + (start - a))
  const scale = (wordsEnd - start) / Math.max(1e-3, b - a)
  for (const i of idx) ws[i] = { ...ws[i], start: start + (ws[i].start - a) * scale, end: start + (ws[i].end - a) * scale, cardEnd: undefined }
  const li = idx[idx.length - 1]; ws[li] = { ...ws[li], cardEnd: end }
  pin(ws, idx); return ws
}

/** Split a caption before its k-th word (default: the middle). */
export function splitCard(words: Word[], card: Card, k = Math.ceil(card.words.length / 2)): Word[] {
  const idx = idxOf(words, card); if (idx.length < 2) return words
  const ws = words.slice(); pin(ws, idx)
  k = Math.min(idx.length - 1, Math.max(1, k))
  ws[idx[k]] = { ...ws[idx[k]], brk: true, glue: false }
  return ws
}

/** Merge a caption with the next one. */
export function mergeNext(words: Word[], card: Card, next: Card): Word[] {
  const a = idxOf(words, card), b = idxOf(words, next); if (!a.length || !b.length) return words
  const ws = words.slice(); pin(ws, [...a, ...b])
  ws[a[a.length - 1]] = { ...ws[a[a.length - 1]], cardEnd: undefined }
  for (const i of b) ws[i] = { ...ws[i], brk: false, glue: true }
  return ws
}

/** Remove a caption from the screen but keep the video and audio. */
export const hideCard = (words: Word[], card: Card): Word[] => {
  const idx = new Set(idxOf(words, card)); return words.map((w, i) => idx.has(i) ? { ...w, hide: true } : w)
}

/** Insert a typed caption at time t lasting `dur` seconds. */
export function addCaption(words: Word[], t: number, text: string, dur = 1.5): Word[] {
  const toks = text.trim().split(/\s+/).filter(Boolean); if (!toks.length) return words
  const step = dur / toks.length
  const fresh: Word[] = toks.map((tx, k) => ({ text: tx, start: t + k * step, end: t + (k + 1) * step, p: 1, added: true }))
  fresh[0].brk = true; fresh[fresh.length - 1].cardEnd = t + dur; for (const w of fresh.slice(1)) w.glue = true
  const at = words.findIndex(w => w.start >= t)
  const ws = at < 0 ? [...words, ...fresh] : [...words.slice(0, at), ...fresh, ...words.slice(at)]
  const after = ws.findIndex((w, i) => i > ws.indexOf(fresh[fresh.length - 1]) && !w.deleted && !w.hide)
  if (after >= 0) ws[after] = { ...ws[after], brk: true, glue: false }
  return ws
}
