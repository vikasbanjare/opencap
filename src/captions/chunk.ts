import type { Card, CaptionStyle, Word } from './types'

const STOP = new Set('a an the and or but so to of in on at for with is are was were be been it its this that these those i you he she we they me my your our their do did does have has had not no yes if as by from up down out over just like um uh'.split(' '))
const FILLERS = new Set(['um', 'uh', 'uhm', 'hmm', 'mm', 'erm', 'ah', 'like', 'you know', 'sort of', 'kind of', 'i mean', 'basically', 'actually', 'literally', 'right'])

export const isFiller = (w: string) => FILLERS.has(w.toLowerCase().replace(/[^a-z' ]/g, ''))

/** Group words into caption cards. Breaks on max words/chars, long pauses and sentence punctuation. */
export function chunkWords(words: Word[], style: CaptionStyle, duration: number): Card[] {
  const live = words.filter(w => !w.deleted)
  const { maxWords, maxChars, gapBreak } = style.chunk
  const cards: Card[] = []
  let cur: Word[] = []
  const flush = () => {
    if (!cur.length) return
    cards.push({ id: `c${cards.length}`, words: cur, start: cur[0].start, end: cur[cur.length - 1].end, lines: [], emphIndex: -1 })
    cur = []
  }
  for (let i = 0; i < live.length; i++) {
    const w = live[i]
    const prev = cur[cur.length - 1]
    if (prev) {
      const chars = cur.reduce((n, x) => n + x.text.length + 1, 0) + w.text.length
      const gap = w.start - prev.end
      if (cur.length >= maxWords || chars > maxChars || gap > gapBreak || /[.!?]$/.test(prev.text)) flush()
    }
    cur.push(w)
  }
  flush()
  // hold each card until the next one starts (max 1.2 s tail), never under 350 ms
  for (let i = 0; i < cards.length; i++) {
    const next = cards[i + 1]
    const tail = next ? Math.min(next.start, cards[i].end + 1.2) : Math.min(duration, cards[i].end + 1.2)
    const minEnd = cards[i].start + 0.35
    cards[i].end = next ? Math.min(next.start, Math.max(tail, minEnd)) : Math.max(tail, minEnd)
    cards[i].emphIndex = pickEmphasis(cards[i].words)
  }
  return cards
}

/** One keyword per card: an explicit flag wins, else a number, else the longest non-stopword. */
export function pickEmphasis(words: Word[]): number {
  const flagged = words.findIndex(w => w.emph)
  if (flagged >= 0) return flagged
  const num = words.findIndex(w => /\d/.test(w.text))
  if (num >= 0) return num
  let best = -1, bestLen = 0
  words.forEach((w, i) => {
    const t = w.text.toLowerCase().replace(/[^a-z]/g, '')
    if (!STOP.has(t) && t.length > bestLen && t.length >= 4) { best = i; bestLen = t.length }
  })
  return best
}

export const applyCase = (t: string, c: CaptionStyle['font']['case'], first: boolean) =>
  c === 'upper' ? t.toUpperCase() : c === 'lower' ? t.toLowerCase() : c === 'sentence' ? (first ? t[0].toUpperCase() + t.slice(1) : t) : t
