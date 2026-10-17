import { useEffect, useState } from 'react'
import { api, type ProjectMeta } from './lib/api'
import { Editor } from './editor/Editor'
import { fmtTime } from './lib/timeline'

export default function App() {
  const [projects, setProjects] = useState<ProjectMeta[]>([])
  const [open, setOpen] = useState<ProjectMeta | null>(null)
  const [upl, setUpl] = useState<number | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const refresh = () => api.list().then(setProjects).catch(e => setErr(`API not reachable: ${e.message}. Start the server (see README).`))
  useEffect(() => { refresh() }, [])
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
      <h1>OpenCap <span className="muted">free, local AI captions &amp; video editor</span></h1>
      <label className="drop" onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); onFiles(e.dataTransfer.files) }}>
        <input type="file" accept="video/*,audio/*" hidden onChange={e => onFiles(e.target.files)} />
        {upl == null ? <><strong>Drop a video</strong> or click to choose<br /><span className="muted">mp4 · mov · mkv · webm — stays on this machine. Whisper transcribes it automatically.</span></> : <>Uploading {(upl * 100).toFixed(0)}%</>}
      </label>
      <label className="btn record">
        <input type="file" accept="video/*" capture="user" hidden onChange={e => onFiles(e.target.files)} />📷 Record with camera (mobile)
      </label>
      {err && <p className="warn">{err}</p>}
      <h2>Projects</h2>
      <ul className="projects">
        {projects.map(p => <li key={p.id}>
          <button className="link" onClick={() => api.get(p.id).then(setOpen)}>{p.name}</button>
          <span className="muted">{p.width}×{p.height} · {fmtTime(p.duration)} · {p.transcribeStatus === 'running' ? 'transcribing…' : p.transcribeStatus === 'error' ? 'transcription failed' : p.language ?? ''}</span>
          <button className="mini danger" onClick={() => { if (confirm(`Delete ${p.name}?`)) api.remove(p.id).then(refresh) }}>delete</button>
        </li>)}
        {!projects.length && <li className="muted">No projects yet.</li>}
      </ul>
    </div>
  )
}
