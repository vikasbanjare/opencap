import type { Cut, Word, ZoomKey, Card } from '../captions/types'
import { isFiller } from '../captions/chunk'

/** Merge overlapping/adjacent cuts. */
export function mergeCuts(cuts: Cut[]): Cut[] {
  const s = [...cuts].filter(c => c.end > c.start).sort((a, b) => a.start - b.start)
  const out: Cut[] = []
  for (const c of s) {
    const last = out[out.length - 1]
    if (last && c.start <= last.end + 0.001) last.end = Math.max(last.end, c.end)
    else out.push({ ...c })
  }
  return out
}

/** Deleted word runs become cuts; pad so we don't clip the neighbouring word's consonant. */
export function cutsFromWords(words: Word[], pad = 0.04): Cut[] {
  const cuts: Cut[] = []
  for (let i = 0; i < words.length; i++) {
    if (!words[i].deleted) continue
    let j = i
    while (j + 1 < words.length && words[j + 1].deleted) j++
    const prevEnd = i > 0 ? words[i - 1].end : 0
    const nextStart = j + 1 < words.length ? words[j + 1].start : Infinity
    cuts.push({ start: Math.max(prevEnd + pad, words[i].start - pad), end: Math.min(nextStart - pad, words[j].end + pad) })
    i = j
  }
  return cuts
}

export function keptRanges(cuts: Cut[], duration: number): Cut[] {
  const out: Cut[] = []; let t = 0
  for (const c of mergeCuts(cuts)) { if (c.start > t) out.push({ start: t, end: Math.min(c.start, duration) }); t = Math.max(t, c.end) }
  if (t < duration) out.push({ start: t, end: duration })
  return out
}

export const outDuration = (cuts: Cut[], duration: number) => keptRanges(cuts, duration).reduce((n, r) => n + r.end - r.start, 0)

export function outToSrc(tOut: number, cuts: Cut[], duration: number): number {
  let acc = 0
  for (const r of keptRanges(cuts, duration)) {
    const len = r.end - r.start
    if (tOut < acc + len) return r.start + (tOut - acc)
    acc += len
  }
  return duration
}

export function srcToOut(tSrc: number, cuts: Cut[], duration: number): number {
  let acc = 0
  for (const r of keptRanges(cuts, duration)) {
    if (tSrc < r.start) return acc
    if (tSrc < r.end) return acc + (tSrc - r.start)
    acc += r.end - r.start
  }
  return acc
}

export const inCut = (t: number, cuts: Cut[]) => mergeCuts(cuts).find(c => t >= c.start && t < c.end)

export const fillerIndices = (words: Word[]) => words.map((w, i) => (isFiller(w.text) ? i : -1)).filter(i => i >= 0)

/** Gaps between consecutive words longer than minGap → cuts, leaving `keep` seconds of breath on each side. */
export function silenceCuts(words: Word[], minGap: number, keep = 0.15, duration = Infinity): Cut[] {
  const live = words.filter(w => !w.deleted)
  const out: Cut[] = []
  for (let i = 1; i < live.length; i++) {
    const gap = live[i].start - live[i - 1].end
    if (gap > minGap) out.push({ start: live[i - 1].end + keep, end: live[i].start - keep })
  }
  if (live.length && live[0].start > minGap) out.push({ start: 0, end: live[0].start - keep })
  if (live.length && duration - live[live.length - 1].end > minGap) out.push({ start: live[live.length - 1].end + keep, end: duration })
  return out
}

/** Pattern G punch-in: scale eases in over durationMs then holds until the key's end. */
export function zoomAt(t: number, keys: ZoomKey[], cardEnd: (time: number) => number): number {
  for (const z of keys) {
    const end = cardEnd(z.time)
    if (t >= z.time && t < end) {
      const p = Math.min(1, (t - z.time) * 1000 / Math.max(1, z.durationMs))
      return 1 + (z.scale - 1) * (1 - Math.pow(1 - p, 3))
    }
  }
  return 1
}

/** Auto punch-ins: every other card that has an emphasis word, alternating 1.06 / 1.0. */
export const autoZooms = (cards: Card[]): ZoomKey[] =>
  cards.filter((c, i) => c.emphIndex >= 0 && i % 2 === 1).map(c => ({ time: c.start, scale: 1.06, durationMs: 250 }))

export const fmtTime = (t: number) => { const m = Math.floor(t / 60), s = t - m * 60; return `${m}:${s.toFixed(1).padStart(4, '0')}` }
