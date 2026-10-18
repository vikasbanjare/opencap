import { useEffect, useState } from 'react'
import { api, type ProjectMeta } from './lib/api'
import { Editor } from './editor/Editor'
import { fmtTime } from './lib/timeline'
import { Record } from './Record'
import { Icon } from './ui/icons'

export default function App() {
  const [projects, setProjects] = useState<ProjectMeta[]>([])
  const [open, setOpen] = useState<ProjectMeta | null>(null)
  const [upl, setUpl] = useState<number | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [recording, setRecording] = useState(false)
  const [over, setOver] = useState(false)
  const refresh = () => api.list().then(setProjects).catch(e => setErr(`The OpenCap server is not reachable (${e.message}). Start it, then reload this page.`))
  useEffect(() => { refresh() }, [])
  useEffect(() => { if (!projects.some(p => p.transcribeStatus === 'running')) return; const id = setInterval(refresh, 3000); return () => clearInterval(id) }, [projects])
  // deep link ?p=<id>
  useEffect(() => { const id = new URLSearchParams(location.search).get('p'); if (id) api.get(id).then(setOpen).catch(() => null) }, [])
  useEffect(() => { const u = new URL(location.href); if (open) u.searchParams.set('p', open.id); else u.searchParams.delete('p'); history.replaceState(null, '', u) }, [open])

  const onFiles = async (files: FileList | null) => {
    const f = files?.[0]; if (!f) return
    setUpl(0); setErr(null)
    try { const m = await api.upload(f, setUpl); setOpen(m); refresh() } catch (e) { setErr(String(e)) } finally { setUpl(null) }
  }
  if (open) return <Editor project={open} onBack={() => { setOpen(null); refresh() }} />
  return (
    <div className="home">
      <nav className="home-nav">
        <div className="logo"><span className="logo-mark" />OpenCap</div>
        <span className="pill">Free · private · runs on your Mac</span>
      </nav>
      <section className="hero">
        <h1>Captions that <span className="grad">move</span>.</h1>
        <p className="lede">Drop a video. Whisper writes every word, you pick from 130+ animated caption styles, and the export renders right in your browser.</p>
        <label className={`drop ${over ? 'over' : ''} ${upl != null ? 'busy' : ''}`} onDragOver={e => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)} onDrop={e => { e.preventDefault(); setOver(false); onFiles(e.dataTransfer.files) }}>
          <input type="file" accept="video/*,audio/*" hidden onChange={e => onFiles(e.target.files)} />
          <span className="drop-icon">{Icon.upload}</span>
          {upl == null
            ? <><strong>Drop a video here</strong><span className="muted">or click to browse · mp4, mov, mkv, webm · nothing leaves this computer</span></>
            : <><strong>Uploading {(upl * 100).toFixed(0)}%</strong><span className="bar"><span style={{ width: `${upl * 100}%` }} /></span></>}
        </label>
        <div className="hero-actions">
          <button className="ghost" onClick={() => setRecording(true)}>{Icon.record} Record camera or screen</button>
          <label className="btn ghost">{Icon.phone} Phone camera<input type="file" accept="video/*" capture="user" hidden onChange={e => onFiles(e.target.files)} /></label>
        </div>
        <ul className="features">
          <li>{Icon.sparkle} Word-level captions</li><li>{Icon.style} 130+ animated styles</li><li>{Icon.captions} Edit video by editing text</li><li>{Icon.export} Export in the browser</li>
        </ul>
      </section>
      {recording && <Record onClose={() => setRecording(false)} onDone={f => { setRecording(false); const dt = new DataTransfer(); dt.items.add(f); onFiles(dt.files) }} />}
      {err && <p className="notice">{err}</p>}
      <section className="projects-section">
        <div className="section-head"><h2>Your projects</h2><span className="count">{projects.length}</span></div>
        <div className="project-grid">
          {projects.map(p => (
            <article key={p.id} className="project" onClick={() => api.get(p.id).then(setOpen)}>
              <div className="thumb">
                <video src={`${p.playUrl}#t=1`} muted playsInline preload="metadata" />
                <span className="dur">{fmtTime(p.duration)}</span>
                <span className={`status ${p.transcribeStatus ?? ''}`}>{p.transcribeStatus === 'running' ? 'Transcribing…' : p.transcribeStatus === 'error' ? 'Failed' : 'Ready'}</span>
              </div>
              <div className="meta">
                <div><strong title={p.name}>{p.name}</strong><span className="muted">{p.width}×{p.height}{p.language ? ` · ${p.language.toUpperCase()}` : ''}</span></div>
                <button className="icon danger" title="Delete project" onClick={e => { e.stopPropagation(); if (confirm(`Delete ${p.name}?`)) api.remove(p.id).then(refresh) }}>{Icon.trash}</button>
              </div>
            </article>
          ))}
          {!projects.length && <div className="empty">No projects yet. Your first video will show up here.</div>}
        </div>
      </section>
    </div>
  )
}
