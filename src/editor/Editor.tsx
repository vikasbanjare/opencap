import { useCallback, useEffect, useMemo, useRef } from 'react'
import { useEditor } from '../store'
import { chunkWords } from '../captions/chunk'
import { Preview } from './Preview'
import { Timeline } from './Timeline'
import { CaptionsPanel, StylePanel, ElementsPanel, AudioPanel, ExportPanel } from './Panels'
import { api, type ProjectMeta } from '../lib/api'
import { fmtTime, outDuration, mergeCuts, cutsFromWords } from '../lib/timeline'

export function Editor({ project, onBack }: { project: ProjectMeta; onBack: () => void }) {
  const s = useEditor()
  const videoRef = useRef<HTMLVideoElement>(null)
  useEffect(() => { s.load(project) /* eslint-disable-line react-hooks/exhaustive-deps */ }, [project.id])

  // poll while transcribing
  useEffect(() => {
    if (project.transcribeStatus !== 'running') return
    const id = setInterval(async () => {
      const st = await api.status(project.id)
      if (st.transcribeStatus !== 'running') { clearInterval(id); const m = await api.get(project.id); s.load(m) }
    }, 2000)
    return () => clearInterval(id)
  }, [project.id, project.transcribeStatus]) // eslint-disable-line react-hooks/exhaustive-deps

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
  const tabs: [typeof s.tab, string][] = [['captions', 'Captions'], ['style', 'Style'], ['elements', 'Elements'], ['audio', 'Audio'], ['export', 'Export']]
  return (
    <div className="editor">
      <header>
        <button onClick={onBack}>← Projects</button>
        <strong>{project.name}</strong>
        <span className="muted">{project.width}×{project.height} · {project.fps} fps · {fmtTime(project.duration)}{cuts.length ? ` → ${fmtTime(outDuration(cuts, project.duration))}` : ''}</span>
        <span style={{ flex: 1 }} />
        <button onClick={toggle}>{s.playing ? '❚❚ Pause' : '▶ Play'}</button>
        <span className="mono">{fmtTime(s.time)}</span>
      </header>
      <div className="body">
        <nav className="tabs">{tabs.map(([k, l]) => <button key={k} className={s.tab === k ? 'on' : ''} onClick={() => s.set({ tab: k })}>{l}</button>)}</nav>
        <aside>
          {s.tab === 'captions' && <CaptionsPanel cards={cards} seek={seek} />}
          {s.tab === 'style' && <StylePanel cards={cards} />}
          {s.tab === 'elements' && <ElementsPanel />}
          {s.tab === 'audio' && <AudioPanel />}
          {s.tab === 'export' && <ExportPanel cards={cards} />}
        </aside>
        <main><Preview cards={cards} videoRef={videoRef} /></main>
      </div>
      <Timeline cards={cards} seek={seek} />
    </div>
  )
}
