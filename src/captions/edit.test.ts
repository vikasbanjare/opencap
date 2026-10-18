import { expect, test } from 'bun:test'
import { chunkWords } from './chunk'
import { PRESETS } from './presets'
import { setCardText, moveCard, retimeCard, splitCard, mergeNext, hideCard, addCaption, idxOf } from './edit'
import type { Word } from './types'

const style = { ...PRESETS[0], chunk: { maxWords: 2, maxChars: 30, gapBreak: 0.6 } }
const W = (text: string, start: number, end: number): Word => ({ text, start, end })
const base = () => [W('one', 0, .4), W('two', .4, .8), W('three', 1, 1.4), W('four', 1.4, 1.8)]
const texts = (ws: Word[]) => chunkWords(ws, style, 3).map(c => c.words.map(w => w.text).join(' '))

test('edit text keeps span and neighbours', () => {
  const ws = base(); const c = chunkWords(ws, style, 3)[0]
  const out = setCardText(ws, c, 'hello big world')
  expect(texts(out)).toEqual(['hello big world', 'three four'])
  expect(out[0].start).toBe(0); expect(out[2].end).toBeCloseTo(.8)
})
test('move, stretch, split, merge, hide, add', () => {
  let ws = base(); let cards = chunkWords(ws, style, 3)
  ws = moveCard(ws, idxOf(ws, cards[1]), .2); expect(ws[2].start).toBeCloseTo(1.2)
  cards = chunkWords(ws, style, 3)
  ws = retimeCard(ws, idxOf(ws, cards[0]), 0, 1.0); cards = chunkWords(ws, style, 3)
  expect(cards[0].end).toBeCloseTo(1.0); expect(ws[1].end).toBeLessThanOrEqual(1.0 + 1e-9)
  ws = mergeNext(ws, cards[0], cards[1]); expect(texts(ws)).toEqual(['one two three four'])
  ws = splitCard(ws, chunkWords(ws, style, 3)[0], 3); expect(texts(ws)).toEqual(['one two three', 'four'])
  ws = hideCard(ws, chunkWords(ws, style, 3)[1]); expect(texts(ws)).toEqual(['one two three'])
  ws = addCaption(ws, 2.5, 'the end'); expect(texts(ws)).toEqual(['one two three', 'the end'])
})
