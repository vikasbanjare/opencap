import type React from 'react'
import { useCallback, useEffect, useMemo, useRef } from 'react'
import { useEditor, type Aspect } from '../store'
import { chunkWords } from '../captions/chunk'
import { Preview } from './Preview'
import { Timeline } from './Timeline'
import { CaptionsPanel, StylePanel, ElementsPanel, AudioPanel, ExportPanel } from './Panels'
import { api, type ProjectMeta } from '../lib/api'
import { fmtTime, outDuration, mergeCuts, cutsFromWords, fillerIndices, silenceCuts, autoZooms } from '../lib/timeline'
import { Icon } from '../ui/icons'

export function Editor({ project, onBack }: { project: ProjectMeta; onBack: () => void }) {
  const s = useEditor()
  const videoRef = useRef<HTMLVideoElement>(null)
  useEffect(() => { api.getState(project.id).then(st => s.load(project, st)).catch(() => s.load(project)) /* eslint-disable-line react-hooks/exhaustive-deps */ }, [project.id])

  // Poll whenever there is no transcript yet and no final answer from the server; the status
  // in hand may be stale (upload reply, "Transcribe again"), so ask the server instead of trusting it.
  const st0 = s.project?.transcribeStatus
  const waiting = s.project?.id === project.id && !s.words.length && st0 !== 'error' && st0 !== 'done'
  useEffect(() => {
    if (!waiting) return
    const id = setInterval(async () => {
      const st = await api.status(project.id).catch(() => null)
      if (!st || st.transcribeStatus === 'running') return
      clearInterval(id); const m = await api.get(project.id); s.load(m, await api.getState(project.id).catch(() => null))
    }, 2000)
    return () => clearInterval(id)
  }, [project.id, waiting]) // eslint-disable-line react-hooks/exhaustive-deps

  const cards = useMemo(() => chunkWords(s.words, s.style, s.project?.duration ?? 0), [s.words, s.style, s.project?.duration])
  const seek = useCallback((t: number) => { const v = videoRef.current; if (v) { v.currentTime = t; s.set({ time: t }) } }, [s])
  const toggle = () => { const v = videoRef.current; if (!v) return; if (v.paused) v.play(); else v.pause() }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).tagName === 'INPUT' || (e.target as HTMLElement).tagName === 'SELECT') return
      if (e.code === 'Space') { e.preventDefault(); toggle() }
      if (e.key === 'ArrowLeft') seek(Math.max(0, s.time - (e.shiftKey ? 1 : 1 / 30)))
      if (e.key === 'ArrowRight') seek(Math.min(project.duration, s.time + (e.shiftKey ? 1 : 1 / 30)))
    }
    window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey)
  })

  const cuts = mergeCuts([...s.cuts, ...cutsFromWords(s.words)])
  // "Captions + auto edit" chosen on the start screen: apply it once, when the transcript arrives
  useEffect(() => {
    const k = `opencap:${project.id}:autoedit`
    if (!s.words.length || !localStorage.getItem(k)) return
    localStorage.removeItem(k)
    const f = fillerIndices(s.words)
    s.setWords(ws => ws.map((w, i) => f.includes(i) ? { ...w, deleted: true } : w))
    s.set({ cuts: mergeCuts([...s.cuts, ...silenceCuts(s.words, 0.8, 0.15, project.duration)]), autoZoom: true, zooms: autoZooms(cards) })
  }, [s.words.length]) // eslint-disable-line react-hooks/exhaustive-deps

  const tabs: [typeof s.tab, string, React.ReactNode][] = [['captions', 'Subtitles', Icon.captions], ['style', 'Styles', Icon.style], ['elements', 'Elements', Icon.elements], ['audio', 'Audio', Icon.audio], ['export', 'Export', Icon.export]]
  const outDur = cuts.length ? outDuration(cuts, project.duration) : project.duration
  return (
    <div className="editor">
      <header className="editor-bar">
        <button className="logo-btn" onClick={onBack} title="All projects"><span className="logo-mark" /></button>
        <button className="icon" onClick={onBack} title="All projects">{Icon.back}</button>
        <div className="title"><strong title={project.name}>{project.name}</strong><span className="muted">{project.width}×{project.height} · {fmtTime(outDur)}{cuts.length ? ` · ${cuts.length} cuts` : ''}</span></div>
        <span style={{ flex: 1 }} />
        <span className="saved">{Icon.check} Saved on this Mac</span>
        <button className="done" onClick={() => s.set({ tab: 'export' })}>{Icon.check} Done</button>
      </header>
      <div className="body">
        <nav className="tabs">{tabs.map(([k, l, ic]) => <button key={k} className={s.tab === k ? 'on' : ''} onClick={() => s.set({ tab: k })}>{ic}<span>{l}</span></button>)}</nav>
        <aside>
          {s.tab === 'captions' && <CaptionsPanel cards={cards} seek={seek} />}
          {s.tab === 'style' && <StylePanel cards={cards} />}
          {s.tab === 'elements' && <ElementsPanel />}
          {s.tab === 'audio' && <AudioPanel cards={cards} />}
          {s.tab === 'export' && <ExportPanel cards={cards} />}
        </aside>
        <main>
          <Preview cards={cards} videoRef={videoRef} />
          <div className="stage-pill">
            <label>{Icon.frame}<select value={s.aspect} onChange={e => s.set({ aspect: e.target.value as Aspect })}>
              <option value="source">Original</option><option value="9:16">Tall portrait (9:16)</option><option value="4:5">Portrait (4:5)</option><option value="1:1">Square (1:1)</option><option value="16:9">Landscape (16:9)</option></select></label>
            <span className="sep" />
            <label className="chk">{Icon.captions}<input type="checkbox" checked={s.captionsOn} onChange={e => s.set({ captionsOn: e.target.checked })} /> Captions</label>
            <span className="sep" />
            <button className="link" onClick={() => s.set({ tab: 'style' })}>{Icon.gear} Style</button>
          </div>
        </main>
      </div>
      <Timeline cards={cards} seek={seek} toggle={toggle} outDur={outDur} />
    </div>
  )
}
