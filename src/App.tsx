import { useEffect, useMemo, useRef, useState } from 'react'
import { api, type ProjectMeta } from './lib/api'
import { Editor } from './editor/Editor'
import { fmtTime } from './lib/timeline'
import { Record } from './Record'
import { Icon } from './ui/icons'
import { Brand } from './ui/Logo'
import { StyleThumb } from './editor/StyleThumb'
import { PRESETS, presetById } from './captions/presets'
import { Studio } from './studio/Studio'

// Start screen follows the "composer" flow: add footage, pick a look, create.
const FEATURED = ['prism-pro', 'paper-ii', 'prime', 'beast', 'karaoke', 'hype', 'highlighter', 'editorial', 'typewriter', 'comic', 'wave', 'impact-ii', 'glow-up', 'retro', 'neon', 'elevate']

// Studio (the tool suite) is the landing page; the captions editor lives at ?app=editor (and ?p=<project>).
export default function App() {
  const [app, setApp] = useState(() => { const q = new URLSearchParams(location.search); return q.get('app') === 'editor' || q.get('p') ? 'editor' : 'studio' })
  useEffect(() => { const f = () => { const q = new URLSearchParams(location.search); setApp(q.get('app') === 'editor' || q.get('p') ? 'editor' : 'studio') }; addEventListener('popstate', f); return () => removeEventListener('popstate', f) }, [])
  const goto = (a: 'editor' | 'studio') => { const u = new URL(location.origin + location.pathname); if (a === 'editor') u.searchParams.set('app', 'editor'); history.pushState(null, '', u); setApp(a) }
  if (app === 'studio') return <Studio onOpenEditor={() => goto('editor')} />
  return <PulseHome onStudio={() => goto('studio')} />
}

function PulseHome({ onStudio }: { onStudio: () => void }) {
  const [projects, setProjects] = useState<ProjectMeta[]>([])
  const [open, setOpen] = useState<ProjectMeta | null>(null)
  const [upl, setUpl] = useState<number | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [recording, setRecording] = useState(false)
  const [over, setOver] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [styleId, setStyleId] = useState('prism-pro')
  const [mode, setMode] = useState<'captions' | 'auto'>('captions')
  const pick = useRef<HTMLInputElement>(null)
  const fileUrl = useMemo(() => file ? URL.createObjectURL(file) : null, [file])
  const featured = useMemo(() => FEATURED.map(presetById).filter(Boolean), [])
  const refresh = () => api.list().then(setProjects).catch(e => setErr(`The Pulse server is not reachable (${e.message}). Start it, then reload this page.`))
  useEffect(() => { refresh() }, [])
  useEffect(() => { if (!projects.some(p => p.transcribeStatus === 'running')) return; const id = setInterval(refresh, 3000); return () => clearInterval(id) }, [projects])
  useEffect(() => { const id = new URLSearchParams(location.search).get('p'); if (id) api.get(id).then(setOpen).catch(() => null) }, [])
  useEffect(() => { const u = new URL(location.href); if (open) u.searchParams.set('p', open.id); else u.searchParams.delete('p'); history.replaceState(null, '', u) }, [open])

  const create = async (f = file) => {
    if (!f) return
    setUpl(0); setErr(null)
    try {
      const m = await api.upload(f, setUpl)
      // the chosen look becomes the project's starting style; auto edit runs once the transcript lands
      await fetch(`/api/projects/${m.id}/state`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ style: presetById(styleId) }) })
      if (mode === 'auto') localStorage.setItem(`opencap:${m.id}:autoedit`, '1')
      setFile(null); setOpen(m); refresh()
    } catch (e) { setErr(String(e)) } finally { setUpl(null) }
  }
  const choose = (files: FileList | null) => { const f = files?.[0]; if (f) setFile(f) }
  const chosen = presetById(styleId)

  if (open) return <Editor project={open} onBack={() => { setOpen(null); refresh() }} />
  return (
    <div className="home">
      <nav className="home-nav">
        <Brand size={26} />
        <button className="pill" onClick={onStudio}>← All Studio tools</button>
        <span className="pill">Free · private · runs on your Mac</span>
      </nav>
      <section className="hero">
        <h1>Captions that edit<br />like a pro would.</h1>

        <div className={`composer ${over ? 'over' : ''}`} onDragOver={e => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)} onDrop={e => { e.preventDefault(); setOver(false); choose(e.dataTransfer.files) }}>
          <input ref={pick} type="file" accept="video/*,audio/*" hidden onChange={e => choose(e.target.files)} />
          <div className="composer-drop" onClick={() => !file && pick.current?.click()}>
            {upl != null ? (
              <div className="uploading"><strong>Uploading {(upl * 100).toFixed(0)}%</strong><span className="bar"><span style={{ width: `${upl * 100}%` }} /></span><span className="muted">Whisper starts transcribing as soon as it lands.</span></div>
            ) : file && fileUrl ? (
              <div className="picked">
                <video src={fileUrl} muted playsInline autoPlay loop />
                <div><strong>{file.name}</strong><span className="muted">{(file.size / 1e6).toFixed(1)} MB · ready</span>
                  <button className="link" onClick={() => pick.current?.click()}>Replace</button></div>
              </div>
            ) : (
              <div className="empty-drop">
                <div className="stack"><span className="card a" /><span className="card b">+</span></div>
                <span>Add footage to start</span>
              </div>
            )}
          </div>
          <div className="composer-bar">
            <button className="icon round" title="Attach a video" onClick={() => pick.current?.click()}>{Icon.clip}</button>
            <button className="icon round" title="Record camera or screen" onClick={() => setRecording(true)}>{Icon.record}</button>
            <span className="chip">{Icon.style}{chosen.name}</span>
            <select className="mode" value={mode} onChange={e => setMode(e.target.value as 'captions' | 'auto')}>
              <option value="captions">Captions</option>
              <option value="auto">Captions + auto edit</option>
            </select>
            <span style={{ flex: 1 }} />
            <button className="create" disabled={!file || upl != null} onClick={() => create()}>Create my video {Icon.arrow}</button>
          </div>
        </div>

        <div className="style-row">
          {featured.map(p => (
            <button key={p.id} className={`style-tile ${p.id === styleId ? 'on' : ''}`} onClick={() => setStyleId(p.id)}>
              <StyleThumb style={p} portrait />
              <span>{p.name}</span>
            </button>
          ))}
          <div className="style-more"><strong>{PRESETS.length - featured.length}+</strong><span>more styles inside the editor</span></div>
        </div>
        <p className="fine">Everything runs on this computer: transcription, styling and export. Nothing is uploaded anywhere.</p>
      </section>
      {recording && <Record onClose={() => setRecording(false)} onDone={f => { setRecording(false); setFile(f) }} />}
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
