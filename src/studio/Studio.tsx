import { useCallback, useEffect, useMemo, useState } from 'react'
import { studio, waitJob, type Asset, type Catalogue, type Character, type Field, type Job, type Output, type SettingsView, type Tool, type Usage } from './api'
import { FieldInput, LibraryPicker, Preview, toFormData, visible, type MediaVal } from './Fields'
import { Brand } from '../ui/Logo'
import { CAT_HUE, THEMES, loadPrefs, savePrefs, themeVars, type ThemePrefs } from './themes'
import { FilmStudio } from './FilmStudio'
import './studio.css'

type View = 'hub' | 'tool' | 'characters' | 'library' | 'usage' | 'settings' | 'film'
type Handoff = { tool: string; set: Record<string, unknown> }

const MEDIA = ['image', 'images', 'video', 'audio', 'media']
const accepts = (t: Tool, kind: string) => t.inputs.find(f => MEDIA.includes(f.type) && (f.type === 'media' || f.type === kind || (f.type === 'images' && kind === 'image')))
const readUrl = () => { const q = new URLSearchParams(location.search); return { view: (q.get('studio') as View) || 'hub', tool: q.get('tool') || q.get('film') } }

export function Studio({ onOpenEditor }: { onOpenEditor: () => void }) {
  const [cat, setCat] = useState<Catalogue | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [{ view, tool }, setNav] = useState(readUrl)
  const [chars, setChars] = useState<Character[]>([])
  const [handoff, setHandoff] = useState<Handoff | null>(null)
  const [nonce, setNonce] = useState(0) // remounts the tool form on each hand-off, not when the hand-off is consumed
  const [prefs, setPrefsState] = useState<ThemePrefs>(loadPrefs)
  const setPrefs = (p: ThemePrefs) => { setPrefsState(p); savePrefs(p) }
  const [lockDraft, setLockDraft] = useState<Partial<Character> & { refUrl?: string } | null>(null)
  const reloadChars = useCallback(() => studio.characters().then(setChars).catch(() => null), [])
  useEffect(() => { studio.catalogue().then(setCat).catch(e => setErr(`Studio server is not reachable (${e.message}).`)); reloadChars() }, [reloadChars])
  useEffect(() => { const f = () => setNav(readUrl()); addEventListener('popstate', f); return () => removeEventListener('popstate', f) }, [])

  const go = (v: View, t?: string | null) => {
    const u = new URL(location.href); u.searchParams.set('studio', v); u.searchParams.delete('tool'); u.searchParams.delete('film')
    if (t) u.searchParams.set(v === 'film' ? 'film' : 'tool', t)
    history.pushState(null, '', u); setNav({ view: v, tool: t ?? null }); scrollTo(0, 0)
  }
  const open = (t: Tool) => { if (t.link === 'editor') onOpenEditor(); else if (t.link === 'characters') go('characters'); else go('tool', t.id) }
  const send = (h: Handoff) => { setHandoff(h); setNonce(n => n + 1); go('tool', h.tool) }
  const lock = (d: Partial<Character> & { refUrl?: string }) => { setLockDraft(d); go('characters') }

  const current = cat?.tools.find(t => t.id === tool)
  return (
    <div className="studio" style={themeVars(prefs) as React.CSSProperties}>
      <aside className="st-side">
        <div className="st-brand" onClick={() => go('hub')}><Brand size={22} /><span className="tag">Studio</span></div>
        <nav>
          <button className={view === 'hub' ? 'on' : ''} onClick={() => go('hub')}>🏠 Home</button>
          <button className={view === 'film' ? 'on' : ''} onClick={() => go('film')}>🎬 Film Studio projects</button>
          {cat?.categories.map(c => (
            <details key={c.id} open={current?.category === c.id}>
              <summary style={{ '--hue': CAT_HUE[c.id] } as React.CSSProperties}><span className="sw" />{c.name}</summary>
              {cat.tools.filter(t => t.category === c.id).map(t => (
                <button key={t.id} className={t.id === tool && view === 'tool' ? 'on' : ''} onClick={() => open(t)}><span className="ic">{t.icon}</span>{t.name.replace('Resize & Repurpose · ', '')}</button>
              ))}
            </details>
          ))}
          <hr />
          <button className={view === 'characters' ? 'on' : ''} onClick={() => go('characters')}>🔒 Characters & Elements</button>
          <button className={view === 'library' ? 'on' : ''} onClick={() => go('library')}>🗃️ Assets library</button>
          <button className={view === 'usage' ? 'on' : ''} onClick={() => go('usage')}>📊 Usage & spend</button>
          <button className={view === 'settings' ? 'on' : ''} onClick={() => go('settings')}>⚙️ Models, keys & theme</button>
        </nav>
        <div className="theme-pick">
          <span className="muted small">Theme · {THEMES.find(t => t.id === prefs.id)?.name}</span>
          <div className="sws">{THEMES.map(t => <button key={t.id} title={t.name} className={`sw-btn ${prefs.id === t.id ? 'on' : ''}`}
            style={{ '--a': t.bg, '--b': t.accent } as React.CSSProperties} onClick={() => setPrefs({ ...prefs, id: t.id, accent: undefined, accent2: undefined })} />)}</div>
        </div>
      </aside>
      <main className="st-main">
        {err && <p className="notice">{err}</p>}
        {!cat ? <p className="muted">Loading…</p> :
          view === 'tool' && current ? <ToolPage key={`${current.id}:${nonce}`} tool={current} cat={cat} chars={chars}
            preset={handoff?.tool === current.id ? handoff.set : undefined} onSend={send} onLock={lock} onConsumed={() => setHandoff(null)} /> :
          view === 'film' ? <FilmStudio filmId={tool} openFilm={id => go('film', id)} runStage={(t, id) => send({ tool: t, set: { film: id } })} /> :
          view === 'characters' ? <Characters chars={chars} reload={reloadChars} draft={lockDraft} clearDraft={() => setLockDraft(null)} /> :
          view === 'library' ? <Library cat={cat} onSend={send} /> :
          view === 'usage' ? <UsagePage /> :
          view === 'settings' ? <SettingsPage prefs={prefs} setPrefs={setPrefs} /> :
          <Hub cat={cat} open={open} go={go} />}
      </main>
    </div>
  )
}

// ---------- hub ----------

function Hub({ cat, open, go }: { cat: Catalogue; open: (t: Tool) => void; go: (v: View, t?: string | null) => void }) {
  const [persona, setPersona] = useState<string | null>(null)
  const [recent, setRecent] = useState<Job[]>([])
  const [q, setQ] = useState('')
  useEffect(() => { studio.jobs().then(j => setRecent(j.slice(0, 8))).catch(() => null) }, [])
  const p = cat.personas.find(x => x.id === persona)
  const match = (t: Tool) => (!p || p.tools.includes(t.id)) && (!q || `${t.name} ${t.tagline} ${t.description}`.toLowerCase().includes(q.toLowerCase()))
  return (
    <div className="hub">
      <section className="st-hero">
        <span className="eyebrow">Your AI production crew</span>
        <h1>Every role on set.<br /><em>Played by one studio.</em></h1>
        <p>Script doctor, casting director, cinematographer, colourist, sound designer and ad director in one model-agnostic pipeline. Characters stay locked, every output can be QC'd, and context carries from tool to tool.</p>
        <div className="row">
          <button className="primary" onClick={() => go('film')}>🎬 Make a film →</button>
          <button onClick={() => open(cat.tools.find(t => t.id === 'story_builder')!)}>Start with a story</button>
          <button onClick={() => open(cat.tools.find(t => t.id === 'micro_ad_factory')!)}>Make an ad</button>
          <input className="search" placeholder={`Search ${cat.tools.length} tools…`} value={q} onChange={e => setQ(e.target.value)} />
        </div>
        <div className="hero-stats">
          <div><strong>{cat.tools.length}</strong><span>tools</span></div>
          <div><strong>{cat.categories.length}</strong><span>production stages</span></div>
          <div><strong>5</strong><span>continuity locks</span></div>
          <div><strong>5</strong><span>model providers, or none</span></div>
        </div>
      </section>
      <div className="personas">
        <button className={!persona ? 'on' : ''} onClick={() => setPersona(null)}>All tools</button>
        {cat.personas.map(x => <button key={x.id} className={persona === x.id ? 'on' : ''} onClick={() => setPersona(x.id)}>{x.icon} {x.name}</button>)}
      </div>
      {p && <p className="persona-pitch">{p.pitch}</p>}
      {recent.length > 0 && !p && !q && (
        <section>
          <div className="section-head"><h2>Recent</h2></div>
          <div className="recent">{recent.map(j => { const o = j.outputs.find(o => o.url && o.kind !== 'file'); const t = cat.tools.find(t => t.id === j.tool)
            return <button key={j.id} className="recent-item" onClick={() => t && open(t)}>{o?.url ? <Preview url={o.url} name={o.url} /> : <span className="big-ic">{t?.icon}</span>}<span>{j.toolName}</span><span className={`st-dot s-${j.status}`} /></button> })}</div>
        </section>
      )}
      {cat.categories.map(c => {
        const ts = cat.tools.filter(t => t.category === c.id && match(t))
        if (!ts.length) return null
        return (
          <section key={c.id}>
            <div className="section-head"><h2>{c.name}</h2><span className="muted">{c.blurb}</span></div>
            <div className="tool-grid">{ts.map(t => (
              <button key={t.id} className="tool-card" style={{ '--hue': CAT_HUE[t.category] } as React.CSSProperties} onClick={() => open(t)}>
                <span className="tile">{t.icon}</span><strong>{t.name}</strong><span className="muted">{t.tagline}</span>
              </button>
            ))}</div>
          </section>
        )
      })}
    </div>
  )
}

// ---------- tool page ----------

function ToolPage({ tool, cat, chars, preset, onSend, onLock, onConsumed }: { tool: Tool; cat: Catalogue; chars: Character[]; preset?: Record<string, unknown>; onSend: (h: Handoff) => void; onLock: (d: Partial<Character> & { refUrl?: string }) => void; onConsumed: () => void }) {
  // seed defaults so conditional fields (showIf) see the initial choice
  const [values, setValues] = useState<Record<string, unknown>>(() => ({ ...Object.fromEntries(tool.inputs.filter(f => f.default !== undefined).map(f => [f.id, f.default])), ...preset }))
  const [job, setJob] = useState<Job | null>(null)
  const [history, setHistory] = useState<Job[]>([])
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const loadHistory = useCallback(() => studio.jobs(tool.id).then(setHistory).catch(() => null), [tool.id])
  useEffect(() => { loadHistory(); if (preset) onConsumed() }, [loadHistory]) // eslint-disable-line react-hooks/exhaustive-deps
  const set = (id: string, v: unknown) => setValues(s => ({ ...s, [id]: v }))

  const groups = useMemo(() => {
    const g: [string, Field[]][] = []
    for (const f of tool.inputs) { const k = f.group ?? ''; const hit = g.find(x => x[0] === k); if (hit) hit[1].push(f); else g.push([k, [f]]) }
    return g.sort((a, b) => (a[0] === '' ? -1 : b[0] === '' ? 1 : 0))
  }, [tool])

  const run = async () => {
    const missing = tool.inputs.find(f => f.required && visible(f, values) && f.type !== 'toggle' && [undefined, null, '', []].some(e => JSON.stringify(values[f.id] ?? f.default ?? '') === JSON.stringify(e)))
    if (missing) { setErr(`${missing.label} is required`); return }
    setErr(null); setBusy(true)
    try {
      const j = await studio.run(tool.id, toFormData(tool.inputs, values)); setJob(j)
      const done = await waitJob(j.id, setJob); setJob(done); loadHistory()
    } catch (e) { setErr(String(e)) } finally { setBusy(false) }
  }
  const applyNext = (n: { tool: string; set: Record<string, unknown> }) => {
    if (n.tool === tool.id) { setValues(s => ({ ...s, ...n.set })); scrollTo({ top: 0, behavior: 'smooth' }) } else onSend(n)
  }

  return (
    <div className="tool-page">
      <header className="tool-head">
        <span className="tile lg" style={{ '--hue': CAT_HUE[tool.category] } as React.CSSProperties}>{tool.icon}</span>
        <div><h1>{tool.name}</h1><p className="muted">{tool.description}</p></div>
      </header>
      <div className="tool-cols">
        <form className="tool-form" onSubmit={e => { e.preventDefault(); run() }}>
          {groups.map(([g, fs]) => {
            const shown = fs.filter(f => visible(f, values))
            if (!shown.length) return null
            const body = shown.map(f => (
              <div key={f.id} className={`fld ${['textarea', 'chips', 'images', 'image', 'video', 'media', 'audio', 'characters', 'mask', 'sketch'].includes(f.type) ? 'wide' : ''}`}>
                <label>{f.label}{f.required && <span className="req">*</span>}</label>
                <FieldInput f={f} value={values[f.id]} onChange={v => set(f.id, v)} characters={chars} values={values} />
                {f.help && <span className="help">{f.help}</span>}
              </div>
            ))
            return g ? <details key={g} className="fgroup" open={g === 'Camera rig' || g === 'Intent locks'}><summary>{g}</summary><div className="fgrid">{body}</div></details> : <div key="main" className="fgrid">{body}</div>
          })}
          {err && <p className="notice">{err}</p>}
          <div className="run-bar">
            <button className="primary big" disabled={busy} type="submit">{busy ? job?.progress || 'Working…' : `Generate`}</button>
            <span className="muted small">Uses: {tool.caps.join(', ') || 'local tools only'}</span>
          </div>
        </form>
        <section className="tool-out">
          {job ? <JobView job={job} cat={cat} onSend={onSend} onLock={onLock} onNext={applyNext} /> : <div className="empty-out"><span className="big-ic">{tool.icon}</span><p className="muted">Results appear here. Every run is saved to History and the Assets library.</p></div>}
          {history.length > 0 && (
            <div className="st-history">
              <h4>History <span className="muted">{history.length}</span></h4>
              {history.map(h => (
                <div key={h.id} className={`hist ${job?.id === h.id ? 'on' : ''}`} onClick={() => setJob(h)}>
                  <span className={`st-dot s-${h.status}`} />
                  <span className="hist-t">{summary(h)}</span>
                  <span className="muted small">{new Date(h.created * 1000).toLocaleString()}</span>
                  <button className="icon danger" title="Delete" onClick={e => { e.stopPropagation(); studio.deleteJob(h.id).then(loadHistory); if (job?.id === h.id) setJob(null) }}>×</button>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

const summary = (j: Job) => { const v = Object.values(j.params).find(x => typeof x === 'string' && x.length > 3 && !x.startsWith('/media')) as string | undefined; return v ? v.slice(0, 70) : j.toolName }

function JobView({ job, cat, onSend, onLock, onNext }: { job: Job; cat: Catalogue; onSend: (h: Handoff) => void; onLock: (d: Partial<Character> & { refUrl?: string }) => void; onNext: (n: { tool: string; set: Record<string, unknown> }) => void }) {
  const pages = job.outputs.filter(o => o.kind === 'image' && /^Page \d+/.test(o.label ?? ''))
  const [reader, setReader] = useState<'scroll' | 'flip' | null>(null)
  const usd = job.usage.reduce((a, u) => a + u.usd, 0)
  const providers = [...new Set(job.usage.map(u => `${u.provider}${u.provider === 'mock' ? '' : ` · ${u.model}`}`))]
  return (
    <div className="job">
      <div className="job-head">
        <span className={`st-dot s-${job.status}`} /><strong>{job.status === 'running' ? job.progress : job.status === 'error' ? 'Failed' : 'Done'}</strong>
        {typeof job.params.film === 'string' && <a className="btn" href={`?studio=film&film=${job.params.film}`}>🎬 Open project</a>}
        {job.finished && <span className="muted small">{(job.finished - job.created).toFixed(0)} s</span>}
        <span className="muted small">{job.usage.length} model calls · ${usd.toFixed(2)}</span>
        {providers.includes('mock') && <span className="pill warn">placeholder outputs — add a key in Models & keys</span>}
      </div>
      {job.status === 'running' && <div className="bar indet"><span /></div>}
      {job.error && <p className="notice">{job.error}</p>}
      {pages.length > 1 && <div className="row"><button className={reader === 'scroll' ? 'on' : ''} onClick={() => setReader(reader === 'scroll' ? null : 'scroll')}>📜 Scroll</button><button className={reader === 'flip' ? 'on' : ''} onClick={() => setReader(reader === 'flip' ? null : 'flip')}>📖 Flipbook</button></div>}
      {reader && <Reader pages={pages} mode={reader} />}
      <div className="outs">
        {job.outputs.map((o, i) => <OutputCard key={i} o={o} cat={cat} onSend={onSend} onLock={onLock} onNext={onNext} />)}
      </div>
    </div>
  )
}

function Reader({ pages, mode }: { pages: Output[]; mode: 'scroll' | 'flip' }) {
  const [i, setI] = useState(0)
  if (mode === 'scroll') return <div className="reader-scroll">{pages.map((p, k) => <div key={k}><h4>{p.label}</h4><img src={p.url} alt={p.label} /></div>)}</div>
  return (
    <div className="reader-flip">
      <img src={pages[i].url} alt={pages[i].label} />
      <div className="row"><button disabled={!i} onClick={() => setI(i - 1)}>‹ Prev</button>{pages.map((_, k) => <span key={k} className={`pdot ${k === i ? 'on' : ''}`} onClick={() => setI(k)} />)}<button disabled={i === pages.length - 1} onClick={() => setI(i + 1)}>Next ›</button></div>
    </div>
  )
}

type OutX = Output & { copy?: boolean; next?: { tool: string; set: Record<string, unknown>; label?: string }; qc?: { composite: number; scores: Record<string, number>; issues?: string[]; verdict?: string }; lock?: { name: string; description: string } }

function OutputCard({ o: raw, cat, onSend, onLock, onNext }: { o: Output; cat: Catalogue; onSend: (h: Handoff) => void; onLock: (d: Partial<Character> & { refUrl?: string }) => void; onNext: (n: { tool: string; set: Record<string, unknown> }) => void }) {
  const o = raw as OutX
  const [menu, setMenu] = useState(false)
  const targets = o.url && o.kind !== 'file' ? cat.tools.filter(t => !t.link && accepts(t, o.kind)) : []
  const sendTo = (t: Tool) => { const f = accepts(t, o.kind)!; onSend({ tool: t.id, set: { [f.id]: [{ url: o.url, preview: o.url, name: o.name ?? 'asset' } as MediaVal] } }) }
  const nextBtn = o.next && <button className="primary" onClick={() => onNext(o.next!)}>{o.next.label ?? (o.next.tool === 'story_builder' ? 'Edit & draft' : 'Use this →')}</button>
  return (
    <div className={`out out-${o.kind}`}>
      {o.label && <div className="out-label">{o.label}</div>}
      {o.kind === 'image' && <a href={o.url} target="_blank" rel="noreferrer"><img src={o.url} alt={o.label} /></a>}
      {o.kind === 'video' && <video src={o.url} controls playsInline />}
      {o.kind === 'audio' && <audio src={o.url} controls />}
      {o.kind === 'file' && <a className="file" href={o.url} download={o.label || o.name}>📄 {o.label || o.name}</a>}
      {o.kind === 'text' && <pre className="out-text">{o.text}</pre>}
      {o.kind === 'json' && <JsonView data={o.data} />}
      {o.qc && <div className={`qc ${o.qc.composite >= 7 ? 'ok' : 'bad'}`}><strong>QC {o.qc.composite}/10</strong>{o.qc.verdict && <span> · {o.qc.verdict}</span>}
        <span className="muted small">{Object.entries(o.qc.scores ?? {}).map(([k, v]) => `${k} ${v}`).join(' · ')}</span>{o.qc.issues?.map((s, i) => <span key={i} className="small warn">⚠ {s}</span>)}</div>}
      <div className="out-actions">
        {nextBtn}
        {o.copy && o.text && <button onClick={() => navigator.clipboard.writeText(o.text!)}>Copy</button>}
        {o.url && o.kind !== 'file' && <a className="btn" href={o.url} download>Download</a>}
        {o.kind === 'image' && <button onClick={() => onLock({ name: o.lock?.name, description: o.lock?.description, refUrl: o.url })}>🔒 Lock as character</button>}
        {targets.length > 0 && <span className="send">
          <button onClick={() => setMenu(!menu)}>Send to… ▾</button>
          {menu && <div className="menu">{targets.map(t => <button key={t.id} onClick={() => sendTo(t)}>{t.icon} {t.name}</button>)}</div>}
        </span>}
      </div>
    </div>
  )
}

function JsonView({ data }: { data: unknown }): React.ReactElement {
  if (data == null) return <span className="muted">—</span>
  if (typeof data !== 'object') return <span>{String(data)}</span>
  if (Array.isArray(data)) {
    if (data.length && data.every(r => r && typeof r === 'object' && !Array.isArray(r))) {
      const cols = [...new Set(data.flatMap(r => Object.keys(r as object)))]
      return <div className="tbl-wrap"><table className="tbl"><thead><tr>{cols.map(c => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>{data.map((r, i) => <tr key={i}>{cols.map(c => <td key={c}><JsonView data={(r as Record<string, unknown>)[c]} /></td>)}</tr>)}</tbody></table></div>
    }
    return <ul className="jl">{data.map((x, i) => <li key={i}><JsonView data={x} /></li>)}</ul>
  }
  return <dl className="kv">{Object.entries(data as object).map(([k, v]) => <div key={k}><dt>{k}</dt><dd><JsonView data={v} /></dd></div>)}</dl>
}

// ---------- characters ----------

function Characters({ chars, reload, draft, clearDraft }: { chars: Character[]; reload: () => void; draft: (Partial<Character> & { refUrl?: string }) | null; clearDraft: () => void }) {
  const [edit, setEdit] = useState<(Partial<Character> & { refUrl?: string }) | null>(draft)
  const [files, setFiles] = useState<File[]>([])
  const [lib, setLib] = useState(false)
  const [extra, setExtra] = useState<string[]>(draft?.refUrl ? [draft.refUrl] : [])
  useEffect(() => { if (draft) clearDraft() }, []) // eslint-disable-line react-hooks/exhaustive-deps
  const save = async () => {
    const fd = new FormData()
    for (const k of ['id', 'name', 'description', 'wardrobe', 'personality', 'voice', 'role'] as const) if (edit?.[k]) fd.append(k, String(edit[k]))
    files.forEach(f => fd.append('refs', f)); extra.forEach(u => fd.append('refs@url', u))
    await studio.saveCharacter(fd); setEdit(null); setFiles([]); setExtra([]); reload()
  }
  return (
    <div className="page">
      <header className="tool-head"><span className="tile lg">🔒</span><div><h1>Characters & Elements</h1>
        <p className="muted">Five continuity locks. Give each Element a name and reference images: a character (identity, expressions), wardrobe, location or prop. Select it in any tool, or type <code>@Name</code> in a prompt, and the references and description ride along on every generation.</p></div></header>
      <div className="row"><button className="primary" onClick={() => { setEdit({ role: 'Character' }); setExtra([]); setFiles([]) }}>+ New element</button></div>
      {edit && (
        <div className="card char-edit">
          <div className="fgrid">
            <div className="fld"><label>Name</label><input value={edit.name ?? ''} onChange={e => setEdit({ ...edit, name: e.target.value })} placeholder="Ananya" /></div>
            <div className="fld"><label>Lock type</label><select value={edit.role ?? 'Character'} onChange={e => setEdit({ ...edit, role: e.target.value })}>{['Character', 'Wardrobe', 'Location', 'Prop / product', 'Style'].map(r => <option key={r}>{r}</option>)}</select></div>
            <div className="fld wide"><label>Identity / description</label><textarea rows={3} value={edit.description ?? ''} onChange={e => setEdit({ ...edit, description: e.target.value })} placeholder="28, sharp eyes, short curly hair, small scar over left brow" /></div>
            <div className="fld"><label>Wardrobe</label><input value={edit.wardrobe ?? ''} onChange={e => setEdit({ ...edit, wardrobe: e.target.value })} /></div>
            <div className="fld"><label>Manner / expression range</label><input value={edit.personality ?? ''} onChange={e => setEdit({ ...edit, personality: e.target.value })} /></div>
            <div className="fld"><label>Voice</label><input value={edit.voice ?? ''} onChange={e => setEdit({ ...edit, voice: e.target.value })} placeholder="Kore, warm" /></div>
            <div className="fld wide"><label>Reference images</label>
              <div className="media-in">
                {[...(edit.refs ?? []), ...extra].map(u => <div key={u} className="media-thumb"><img src={u} alt="" /></div>)}
                {files.map((f, i) => <div key={i} className="media-thumb"><img src={URL.createObjectURL(f)} alt="" /></div>)}
                <div className="media-add"><label className="btn">Upload<input type="file" accept="image/*" multiple hidden onChange={e => setFiles([...files, ...(e.target.files ?? [])])} /></label>
                  <button type="button" className="ghost" onClick={() => setLib(true)}>From library</button></div>
              </div>
            </div>
          </div>
          <div className="row"><button className="primary" onClick={save} disabled={!edit.name}>Save & lock</button><button className="ghost" onClick={() => setEdit(null)}>Cancel</button></div>
          {lib && <LibraryPicker kind="image" onClose={() => setLib(false)} onPick={a => { setLib(false); setExtra([...extra, a.url!]) }} />}
        </div>
      )}
      <div className="char-grid">
        {chars.map(c => (
          <div key={c.id} className="card char">
            <div className="char-refs">{c.refs.slice(0, 4).map(u => <img key={u} src={u} alt="" />)}{!c.refs.length && <span className="big-ic">👤</span>}</div>
            <strong>@{c.name}</strong><span className="muted small">{c.role ?? 'Character'} · {c.refs.length} refs</span>
            <span className="small">{c.description}</span>
            <div className="row"><button onClick={() => { setEdit(c); setExtra([]); setFiles([]) }}>Edit</button>
              <button className="ghost danger" onClick={() => confirm(`Delete ${c.name}?`) && studio.deleteCharacter(c.id).then(reload)}>Delete</button></div>
          </div>
        ))}
        {!chars.length && !edit && <p className="muted">No elements yet. Cast one in Casting Director and press "Lock as character", or create one here.</p>}
      </div>
    </div>
  )
}

// ---------- library ----------

function Library({ cat, onSend }: { cat: Catalogue; onSend: (h: Handoff) => void }) {
  const [items, setItems] = useState<Asset[]>([])
  const [kind, setKind] = useState('')
  const [sel, setSel] = useState<Asset | null>(null)
  const load = useCallback(() => studio.assets(kind || undefined).then(setItems).catch(() => null), [kind])
  useEffect(() => { load() }, [load])
  return (
    <div className="page">
      <header className="tool-head"><span className="tile lg">🗃️</span><div><h1>Assets library</h1><p className="muted">Every upload and generation, across tools. Open one to send it to another tool.</p></div></header>
      <div className="row">
        {['', 'image', 'video', 'audio', 'file'].map(k => <button key={k} className={kind === k ? 'on' : ''} onClick={() => setKind(k)}>{k || 'All'}</button>)}
        <span style={{ flex: 1 }} />
        <label className="btn primary">Upload<input type="file" hidden multiple onChange={async e => { for (const f of e.target.files ?? []) await studio.upload(f); load() }} /></label>
      </div>
      <div className="lib-grid big">
        {items.map((a, i) => (
          <button key={i} className="lib-item" onClick={() => setSel(a)}>
            {a.kind === 'file' ? <span className="file">📄 {a.label || a.name}</span> : <Preview url={a.url!} name={a.url} />}
            <span>{a.toolName}{a.label ? ` · ${a.label}` : ''}</span>
          </button>
        ))}
      </div>
      {sel && <div className="modal" onClick={() => setSel(null)}><div className="modal-card" onClick={e => e.stopPropagation()}>
        <div className="modal-head"><h3>{sel.toolName} <span className="muted">{sel.label}</span></h3><button className="icon" onClick={() => setSel(null)}>×</button></div>
        <OutputCard o={sel} cat={cat} onSend={h => { setSel(null); onSend(h) }} onLock={() => null} onNext={n => onSend(n)} />
      </div></div>}
    </div>
  )
}

// ---------- usage ----------

function UsagePage() {
  const [u, setU] = useState<Usage | null>(null)
  useEffect(() => { studio.usage().then(setU).catch(() => null) }, [])
  if (!u) return <p className="muted">Loading…</p>
  return (
    <div className="page">
      <header className="tool-head"><span className="tile lg">📊</span><div><h1>Usage & spend</h1><p className="muted">Every model call, by provider, capability and tool. Costs are estimates from a static rate table; placeholder (mock) calls are free.</p></div></header>
      <div className="stats"><div className="stat"><span>Estimated spend</span><strong>${u.totalUsd.toFixed(2)}</strong></div><div className="stat"><span>Model calls</span><strong>{u.calls}</strong></div></div>
      <div className="usage-cols">
        {([['By provider', u.byProvider], ['By capability', u.byCap], ['By tool', u.byTool]] as const).map(([t, rows]) => (
          <div key={t} className="card"><h4>{t}</h4><JsonView data={rows.map(r => ({ [t.split(' ')[1]]: r.key, calls: r.calls, usd: `$${r.usd.toFixed(2)}` }))} /></div>
        ))}
      </div>
    </div>
  )
}

// ---------- settings ----------

function SettingsPage({ prefs, setPrefs }: { prefs: ThemePrefs; setPrefs: (p: ThemePrefs) => void }) {
  const [s, setS] = useState<SettingsView | null>(null)
  const [keys, setKeys] = useState<Record<string, string>>({})
  const [saved, setSaved] = useState(false)
  useEffect(() => { studio.settings().then(setS).catch(() => null) }, [])
  if (!s) return <p className="muted">Loading…</p>
  const save = async (p: Parameters<typeof studio.saveSettings>[0]) => { setS(await studio.saveSettings(p)); setSaved(true); setTimeout(() => setSaved(false), 1500) }
  return (
    <div className="page">
      <header className="tool-head"><span className="tile lg">⚙️</span><div><h1>Models, keys & theme</h1>
        <p className="muted">Studio is model-agnostic: each capability is routed to a provider. With no keys, every tool still runs with placeholder outputs so you can try the whole pipeline. Keys can also be set as environment variables on the server. Keys entered here are stored in the server's data folder.</p></div></header>
      <div className="card">
        <h4>Appearance</h4>
        <div className="theme-grid">{THEMES.map(t => (
          <button key={t.id} className={`theme-card ${prefs.id === t.id ? 'on' : ''}`} onClick={() => setPrefs({ ...prefs, id: t.id, accent: undefined, accent2: undefined })}>
            <span className="prev" style={{ background: `linear-gradient(135deg, ${t.surface}, ${t.bg})`, border: `1px solid ${t.line}` }}><i style={{ background: t.accent }} /><i style={{ background: t.accent2 }} /><i style={{ background: t.fg }} /></span>
            <strong>{t.name}</strong><span className="muted small">{t.dark ? 'Dark' : 'Light'}</span>
          </button>))}</div>
        <div className="row">
          <label>Accent <input type="color" value={prefs.accent ?? THEMES.find(t => t.id === prefs.id)!.accent} onChange={e => setPrefs({ ...prefs, accent: e.target.value })} /></label>
          <label>Second accent <input type="color" value={prefs.accent2 ?? THEMES.find(t => t.id === prefs.id)!.accent2} onChange={e => setPrefs({ ...prefs, accent2: e.target.value })} /></label>
          <label>Corner radius <input type="range" min={0} max={22} value={prefs.radius ?? 12} onChange={e => setPrefs({ ...prefs, radius: +e.target.value })} /></label>
          <button className="ghost" onClick={() => setPrefs({ id: prefs.id })}>Reset</button>
        </div>
        <p className="muted small">Saved in this browser. To change the built-in palettes, edit <code>src/studio/themes.ts</code>.</p>
      </div>
      <div className="card">
        <h4>Providers {saved && <span className="pill ok">saved</span>}</h4>
        {s.providers.map(p => (
          <div key={p.id} className="prov">
            <strong>{p.id}</strong><span className={`pill ${p.configured ? 'ok' : ''}`}>{p.configured ? (p.fromEnv ? 'from env' : 'configured') : 'no key'}</span>
            <span className="muted small">{p.caps.join(', ')}</span>
            <input type="password" placeholder={`${p.env}`} value={keys[p.id] ?? ''} onChange={e => setKeys({ ...keys, [p.id]: e.target.value })} />
            <button onClick={() => save({ keys: { [p.id]: keys[p.id] ?? '' } }).then(() => setKeys({ ...keys, [p.id]: '' }))}>{keys[p.id] ? 'Save' : 'Clear'}</button>
          </div>
        ))}
      </div>
      <div className="card">
        <h4>Routing per capability</h4>
        <div className="tbl-wrap"><table className="tbl"><thead><tr><th>Capability</th><th>Provider</th><th>Model</th><th>Active now</th></tr></thead><tbody>
          {s.caps.map(c => (
            <tr key={c.id}>
              <td>{c.label}</td>
              <td><select value={c.route.provider} onChange={e => save({ routes: { [c.id]: { provider: e.target.value } } })}>
                <option value="auto">Auto</option>{Object.keys(c.options).map(p => <option key={p} value={p}>{p}</option>)}</select></td>
              <td>{c.route.provider !== 'auto' && c.options[c.route.provider] ? <select value={c.route.model ?? c.options[c.route.provider][0]} onChange={e => save({ routes: { [c.id]: { provider: c.route.provider, model: e.target.value } } })}>
                {c.options[c.route.provider].map(m => <option key={m}>{m}</option>)}</select> : <span className="muted">best available</span>}</td>
              <td><span className={`pill ${c.active.provider === 'mock' ? 'warn' : 'ok'}`}>{c.active.provider}</span> <span className="muted small">{c.active.model}</span></td>
            </tr>
          ))}
        </tbody></table></div>
      </div>
    </div>
  )
}
