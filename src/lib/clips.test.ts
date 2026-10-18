import { expect, test } from 'bun:test'
import { remapTime, remapDoc, clipWords, type Seg } from './clips'

const S = (id: string, clip: string, a: number, b: number, start: number): Seg => ({ id, clip, in: a, out: b, transition: 'none', tdur: 0.5, start })
test('reorder and split carry times by source', () => {
  const before = [S('a', 'source', 0, 10, 0)]
  const after = [S('b', 'source', 5, 10, 0), S('a', 'source', 0, 5, 5)]   // split at 5, second half moved first
  expect(remapTime(2, before, after)).toBeCloseTo(7)
  expect(remapTime(6, before, after)).toBeCloseTo(1)
  expect(remapTime(2, before, [S('b', 'source', 5, 10, 0)])).toBeNull()   // first half deleted
})
test('words follow their clip and new clip words land in place', () => {
  const before = [S('a', 'source', 0, 4, 0), S('c', 'x', 0, 3, 4)]
  const after = [S('c', 'x', 0, 3, 0), S('a', 'source', 0, 4, 3)]
  const r = remapDoc({ words: [{ text: 'hi', start: 1, end: 1.5 }, { text: 'yo', start: 5, end: 5.4 }], cuts: [], overlays: [], zooms: [] }, before, after, 7)
  expect(r.words.map(w => [w.text, +w.start.toFixed(2)])).toEqual([['yo', 1], ['hi', 4]])
  expect(clipWords({ words: [{ text: 'a', start: 0.5, end: 1 }, { text: 'gone', start: 3.5, end: 4 }] }, 'x', after).map(w => w.start)).toEqual([0.5])
})
