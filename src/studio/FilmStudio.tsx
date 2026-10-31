import { useCallback, useEffect, useState } from 'react'
import { studio, type Film } from './api'

const STAGES = [
  { tool: 'film_script', label: 'Script', icon: '📜', done: (f: Film) => f.scenes.length > 0 },
  { tool: 'film_cast', label: 'Cast', icon: '🎭', done: (f: Film) => f.cast.length > 0 },
  { tool: 'film_scenes', label: 'Scenes', icon: '🎬', done: (f: Film) => f.scenes.some(s => s.cut) },
  { tool: 'film_score', label: 'Score', icon: '🎼', done: (f: Film) => f.score.length > 0 },
  { tool: 'film_final', label: 'Final cut', icon: '🏁', done: (f: Film) => !!f.final },
]
const GENRES = ['Drama', 'Thriller', 'Comedy', 'Horror', 'Action', 'Romance', 'Sci-Fi', 'Fantasy', 'Crime', 'Mystery', 'Family', 'Documentary', 'Musical', 'Microdrama']

/** Film projects: script → cast → scenes → score → final cut. Each stage opens its tool with the project preselected. */
export function FilmStudio({ filmId, openFilm, runStage }: { filmId: string | null; openFilm: (id: string | null) => void; runStage: (tool: string, film: string) => void }) {
  const [films, setFilms] = useState<Film[] | null>(null)
  const [film, setFilm] = useState<Film | null>(null)
  const [draft, setDraft] = useState({ title: '', logline: '', genre: 'Drama', aspect: '16:9' })
  const load = useCallback(() => { studio.films().then(setFilms).catch(() => setFilms([])); if (filmId) studio.film(filmId).then(setFilm).catch(() => setFilm(null)) }, [filmId])
  useEffect(() => { load() }, [load])

  if (filmId && film) {
    const next = STAGES.find(s => !s.done(film))
    return (
      <div className="page film">
        <header className="tool-head"><span className="tile lg" style={{ '--hue': '#ef4444' } as React.CSSProperties}>🎬</span>
          <div><h1>{film.title}</h1><p className="muted">{film.genre} · {film.aspect} · {film.logline || 'No logline yet'}</p></div></header>
        <div className="stepper">{STAGES.map((s, i) => (
          <button key={s.tool} className={`step ${s.done(film) ? 'done' : ''} ${next?.tool === s.tool ? 'next' : ''}`} onClick={() => runStage(s.tool, film.id)}>
            <span className="n">{s.done(film) ? '✓' : i + 1}</span><span>{s.icon} {s.label}</span></button>
        ))}</div>
        {next && <p className="muted">Next: <button className="primary" onClick={() => runStage(next.tool, film.id)}>{next.icon} Run {next.label} →</button></p>}
        {film.final && <div className="card"><h3>Final cut <span className="muted">{film.final.duration}s</span></h3><video className="final" src={film.final.url} controls />
          <div className="row"><a className="btn primary" href={film.final.url} download>Download MP4</a><a className="btn" href={film.final.srt} download>Subtitles (SRT)</a></div></div>}
        {film.cast.length > 0 && <div className="card"><h3>Cast</h3><div className="cast-row">{film.cast.map(c => (
          <div key={c.name} className="cast-card"><img src={c.ref} alt={c.name} /><strong>{c.name}</strong><span className="muted small">🎙 {c.voice}</span><span className="small">{c.description}</span></div>))}</div></div>}
        {film.scenes.length > 0 && <div className="card"><h3>Scenes <span className="muted">{film.scenes.length}</span></h3>
          {film.scenes.map(s => (
            <div key={s.n} className="scene">
              <div className="scene-head"><strong>{s.n}. {s.heading}</strong>{s.duration && <span className="muted small">{s.duration}s</span>}</div>
              <div className="scene-body">
                <div className="scene-text"><p>{s.action}</p>{s.dialogue.map((d, i) => <p key={i} className="dlg"><b>{d.character}</b> {d.paren && <i>{d.paren} </i>}{d.line}</p>)}</div>
                <div className="scene-media">
                  {s.cut ? <video src={s.cut} controls /> : <div className="ph muted small">Not shot yet</div>}
                  {s.shots && <div className="shots">{s.shots.map((sh, i) => sh.frame && <img key={i} src={sh.frame} title={`${sh.shot}: ${sh.description}`} alt="" />)}</div>}
                  {s.score && <audio src={s.score} controls />}
                </div>
              </div>
            </div>
          ))}</div>}
        <div className="row"><button className="ghost" onClick={() => openFilm(null)}>← All films</button>
          <button className="ghost danger" onClick={() => confirm(`Delete ${film.title}?`) && studio.deleteFilm(film.id).then(() => openFilm(null))}>Delete project</button></div>
      </div>
    )
  }
  return (
    <div className="page film">
      <header className="tool-head"><span className="tile lg" style={{ '--hue': '#ef4444' } as React.CSSProperties}>🎬</span>
        <div><h1>Film Studio</h1><p className="muted">One project, script to screen. Write or import the screenplay, cast and lock every role, shoot each scene with the locked cast and their voices, score it scene by scene, and assemble the final cut with titles, credits and subtitles.</p></div></header>
      <div className="card new-film">
        <h3>New film</h3>
        <div className="fgrid">
          <div className="fld"><label>Title</label><input value={draft.title} onChange={e => setDraft({ ...draft, title: e.target.value })} placeholder="The Last Train" /></div>
          <div className="fld"><label>Genre</label><select value={draft.genre} onChange={e => setDraft({ ...draft, genre: e.target.value })}>{GENRES.map(g => <option key={g}>{g}</option>)}</select></div>
          <div className="fld wide"><label>Logline</label><textarea rows={2} value={draft.logline} onChange={e => setDraft({ ...draft, logline: e.target.value })} placeholder="A signal operator gets a call from a train that vanished in 1984." /></div>
          <div className="fld"><label>Aspect</label><select value={draft.aspect} onChange={e => setDraft({ ...draft, aspect: e.target.value })}>{['16:9', '21:9', '9:16', '1:1', '4:5'].map(a => <option key={a}>{a}</option>)}</select></div>
        </div>
        <div className="row"><button className="primary" disabled={!draft.title} onClick={async () => { const f = await studio.createFilm(draft); runStage('film_script', f.id) }}>Create & write the script →</button></div>
      </div>
      <div className="film-grid">{films?.map(f => (
        <button key={f.id} className="film-card" onClick={() => openFilm(f.id)}>
          <div className="poster">{f.cast[0]?.ref ? <img src={f.cast[0].ref} alt="" /> : <span>🎬</span>}</div>
          <strong>{f.title}</strong><span className="muted small">{f.genre} · {f.scenes.length} scenes · {f.cast.length} cast</span>
          <span className="mini-steps">{STAGES.map(s => <i key={s.tool} className={s.done(f) ? 'on' : ''} title={s.label} />)}</span>
        </button>
      ))}</div>
    </div>
  )
}
