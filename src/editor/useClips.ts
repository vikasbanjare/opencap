import { useEffect, useState } from 'react'
import { useEditor } from '../store'
import { api } from '../lib/api'
import { clipWords, remapDoc, segsOf, segLen, type Seg } from '../lib/clips'

const uid = () => Math.random().toString(36).slice(2, 10)

/** Clip operations: every change re-renders the timeline video on the server, then edits are carried across. */
export function useClips() {
  const s = useEditor()
  const [busy, setBusy] = useState<string | null>(null)
  const [sel, setSel] = useState<string | null>(null)
  const segs = s.project ? segsOf(s.project) : []

  const apply = async (next: Omit<Seg, 'start'>[], label: string) => {
    const st = useEditor.getState(); if (!st.project || busy) return
    const before = segsOf(st.project)
    setBusy(label)
    try {
      const m = await api.assemble(st.project.id, next)
      const now = useEditor.getState()
      const r = remapDoc(now, before, m.segments!, m.duration)
      // clip edits re-render the video, so they start a fresh undo history
      now.set({ project: { ...now.project!, ...m }, ...r, past: [], future: [], selected: null, capSel: false })
      await addPendingWords()
    } catch (e) { alert(`Could not rebuild the video: ${e}`) } finally { setBusy(null) }
  }

  /** Words of clips whose transcription finished since they were added. */
  const addPendingWords = async () => {
    const st = useEditor.getState(); const p = st.project; if (!p?.clips) return
    for (const c of p.clips) {
      if (st.clipWords.includes(c.id) || c.transcribeStatus !== 'done') continue
      const tr = await api.clipTranscript(p.id, c.id).catch(() => null); if (!tr) continue
      const cur = useEditor.getState()
      const add = clipWords(tr, c.id, segsOf(cur.project!))
      cur.set({ words: [...cur.words, ...add].sort((a, b) => a.start - b.start), clipWords: [...cur.clipWords, c.id] })
    }
  }

  // poll while a clip is still being transcribed
  const pending = s.project?.clips?.some(c => c.transcribeStatus === 'running')
  useEffect(() => {
    if (!pending || !s.project) return
    const id = setInterval(async () => {
      const m = await api.get(s.project!.id).catch(() => null); if (!m) return
      const cur = useEditor.getState(); cur.set({ project: { ...cur.project!, clips: m.clips } })
      if (!m.clips?.some(c => c.transcribeStatus === 'running')) { clearInterval(id); addPendingWords() }
    }, 2500)
    return () => clearInterval(id)
  }, [pending, s.project?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  const strip = (x: Seg[]) => x.map(({ start: _s, ...r }) => r)   // eslint-disable-line @typescript-eslint/no-unused-vars
  const addFile = async (file: File) => {
    const p = useEditor.getState().project; if (!p) return
    setBusy('Uploading clip…')
    try {
      const c = await api.addClip(p.id, file)
      const cur = useEditor.getState(); cur.set({ project: { ...cur.project!, clips: [...(cur.project!.clips ?? []), c] } })
      setBusy(null)
      await apply([...strip(segsOf(cur.project!)), { id: uid(), clip: c.id, in: 0, out: c.duration, transition: 'fade', tdur: 0.5 }], 'Adding clip…')
    } catch (e) { setBusy(null); alert(`Could not add that clip: ${e}`) }
  }
  const split = (t = useEditor.getState().time) => {
    const sg = segs.find(x => t > x.start + 0.2 && t < x.start + segLen(x) - 0.2); if (!sg) return
    const at = sg.in + (t - sg.start)
    const next = segs.flatMap(x => x.id !== sg.id ? [x] : [{ ...x, out: at }, { ...x, id: uid(), in: at, transition: 'none' }])
    apply(strip(next), 'Splitting…')
  }
  const remove = (id: string) => { if (segs.length < 2) return; setSel(null); apply(strip(segs.filter(x => x.id !== id)), 'Removing clip…') }
  const move = (id: string, to: number) => {
    const from = segs.findIndex(x => x.id === id); if (from < 0 || from === to) return
    const next = segs.slice(); const [x] = next.splice(from, 1); next.splice(Math.min(to, next.length), 0, x)
    apply(strip(next), 'Reordering…')
  }
  const setTransition = (id: string, transition: string, tdur?: number) =>
    apply(strip(segs.map(x => x.id === id ? { ...x, transition, tdur: tdur ?? x.tdur } : x)), 'Applying transition…')

  return { segs, busy, sel, setSel, addFile, split, remove, move, setTransition }
}
export type ClipOps = ReturnType<typeof useClips>
