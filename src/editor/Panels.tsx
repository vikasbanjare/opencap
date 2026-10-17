import { useEffect, useMemo, useState } from 'react'
import { useEditor, aspectSize, type Aspect } from '../store'
import { PRESETS } from '../captions/presets'
import type { Card, CaptionStyle, Overlay } from '../captions/types'
import { fillerIndices, silenceCuts, mergeCuts, autoZooms, cutsFromWords, fmtTime } from '../lib/timeline'
import { api, download } from '../lib/api'
import { exportMp4, webCodecsOk } from '../lib/export'
import { imageCache } from './Preview'

const FONTS = ['Inter', 'Oswald', 'Montserrat', 'Bebas Neue', 'Poppins', 'Nunito', 'Playfair Display', 'EB Garamond', 'Caveat', 'Space Mono', 'Anton']

// ---------------- Captions ----------------
export function CaptionsPanel({ cards, seek }: { cards: Card[]; seek: (t: number) => void }) {
  const s = useEditor()
  const [editing, setEditing] = useState<number | null>(null)
  const [gap, setGap] = useState(0.8)
  const fillers = useMemo(() => fillerIndices(s.words).filter(i => !s.words[i].deleted), [s.words])
  const deletedN = s.words.filter(w => w.deleted).length
  const status = s.project?.transcribeStatus

  if (!s.words.length) return (
    <div className="panel">
      <h3>Captions</h3>
      <p className="muted">{status === 'running' ? 'Transcribing with Whisper… this page refreshes itself when it finishes.' : status === 'error' ? `Transcription failed: ${s.project?.transcribeError}` : 'No transcript yet.'}</p>
      {status !== 'running' && <button onClick={() => s.project && api.retranscribe(s.project.id)}>Transcribe again</button>}
    </div>
  )

  const toggleDelete = (i: number) => s.setWords(ws => ws.map((w, j) => j === i ? { ...w, deleted: !w.deleted } : w))
  const toggleEmph = (i: number) => s.setWords(ws => ws.map((w, j) => j === i ? { ...w, emph: !w.emph } : w))
  const edit = (i: number, text: string) => { s.setWords(ws => ws.map((w, j) => j === i ? { ...w, text } : w)); setEditing(null) }

  return (
    <div className="panel">
      <h3>Captions <span className="muted">{s.words.length} words · {cards.length} cards · {s.project?.language}</span></h3>
      <div className="row wrap">
        <button disabled={!fillers.length} onClick={() => s.setWords(ws => ws.map((w, i) => fillers.includes(i) ? { ...w, deleted: true } : w))}>Remove fillers ({fillers.length})</button>
        <button onClick={() => s.set({ cuts: mergeCuts([...s.cuts, ...silenceCuts(s.words, gap, 0.15, s.project?.duration)]) })}>Cut silences &gt; <input type="number" step="0.1" min="0.3" value={gap} onChange={e => setGap(+e.target.value)} style={{ width: 48 }} />s</button>
        <button disabled={!deletedN} onClick={() => s.setWords(ws => ws.map(w => ({ ...w, deleted: false })))}>Restore {deletedN} words</button>
        <label className="chk"><input type="checkbox" checked={s.captionsOn} onChange={e => s.set({ captionsOn: e.target.checked })} /> show captions</label>
      </div>
      <div className="row">
        <label>Words / card <input type="range" min={1} max={6} value={s.style.chunk.maxWords} onChange={e => s.setStyle(st => ({ ...st, chunk: { ...st.chunk, maxWords: +e.target.value } }))} /> {s.style.chunk.maxWords}</label>
        <label>Max chars <input type="range" min={8} max={40} value={s.style.chunk.maxChars} onChange={e => s.setStyle(st => ({ ...st, chunk: { ...st.chunk, maxChars: +e.target.value } }))} /> {s.style.chunk.maxChars}</label>
      </div>
      <p className="muted small">Click a word to seek. Double-click to edit. Delete/Backspace removes it from the video (text-based cut). E marks the keyword.</p>
      <div className="transcript" tabIndex={0} onKeyDown={e => {
        if (s.selected == null) return
        if (e.key === 'Delete' || e.key === 'Backspace') { e.preventDefault(); toggleDelete(s.selected) }
        if (e.key.toLowerCase() === 'e') { e.preventDefault(); toggleEmph(s.selected) }
      }}>
        {cards.map(card => (
          <span key={card.id} className="card-group">{' '}
            {card.words.map(w => {
              const i = s.words.indexOf(w)
              const active = s.time >= w.start && s.time < w.end
              return editing === i
                ? <input key={i} autoFocus defaultValue={w.text} className="word-edit" onBlur={e => edit(i, e.target.value)} onKeyDown={e => { if (e.key === 'Enter') edit(i, (e.target as HTMLInputElement).value); if (e.key === 'Escape') setEditing(null) }} />
                : <span key={i} className={`word ${active ? 'active' : ''} ${i === s.selected ? 'sel' : ''} ${w.emph || card.words[card.emphIndex] === w ? 'emph' : ''} ${(w.p ?? 1) < 0.5 ? 'lowconf' : ''}`}
                  onClick={() => { s.set({ selected: i }); seek(w.start) }} onDoubleClick={() => setEditing(i)} title={`${fmtTime(w.start)} · p=${w.p ?? '?'}`}>{w.text}</span>
            }).flatMap(el => [el, ' '])}
          </span>
        ))}
        {s.words.some(w => w.deleted) && <details><summary className="muted">deleted words</summary>
          {s.words.map((w, i) => w.deleted && <span key={i} className="word deleted" onClick={() => toggleDelete(i)}>{w.text}</span>)}</details>}
      </div>
    </div>
  )
}

// ---------------- Style ----------------
export function StylePanel({ cards }: { cards: Card[] }) {
  const s = useEditor()
  const st = s.style
  const up = (f: (x: CaptionStyle) => void) => s.setStyle(x => { const c = JSON.parse(JSON.stringify(x)); f(c); return c })
  return (
    <div className="panel">
      <h3>Style</h3>
      <div className="presets">
        {PRESETS.map(p => <button key={p.id} className={`preset ${st.id === p.id ? 'on' : ''}`} onClick={() => s.pickPreset(p.id)}>
          <span style={{ fontFamily: p.font.family, fontWeight: p.font.weight, fontStyle: p.font.italic ? 'italic' : 'normal', color: p.box.mode === 'none' ? p.colors.text : p.colors.text, background: p.box.mode !== 'none' ? p.box.fill : 'transparent', padding: p.box.mode !== 'none' ? '2px 8px' : 0, borderRadius: p.box.radius > 20 ? 999 : 4, textTransform: p.font.case === 'upper' ? 'uppercase' : p.font.case === 'lower' ? 'lowercase' : 'none' }}>{p.name}</span>
          <small>{p.tags.join(' · ')}</small>
        </button>)}
      </div>
      <h4>Text</h4>
      <div className="grid2">
        <label>Font <select value={st.font.family} onChange={e => up(x => { x.font.family = e.target.value })}>{FONTS.map(f => <option key={f}>{f}</option>)}</select></label>
        <label>Weight <input type="range" min={300} max={900} step={100} value={st.font.weight} onChange={e => up(x => { x.font.weight = +e.target.value })} /></label>
        <label>Size <input type="range" min={24} max={140} value={st.font.size} onChange={e => up(x => { x.font.size = +e.target.value })} /> {st.font.size}</label>
        <label>Case <select value={st.font.case} onChange={e => up(x => { x.font.case = e.target.value as CaptionStyle['font']['case'] })}><option value="as-is">as spoken</option><option value="sentence">Sentence</option><option value="upper">UPPER</option><option value="lower">lower</option></select></label>
        <label>Colour <input type="color" value={st.colors.text} onChange={e => up(x => { x.colors.text = e.target.value })} /></label>
        <label>Stroke <input type="range" min={0} max={10} value={st.stroke} onChange={e => up(x => { x.stroke = +e.target.value })} /> {st.stroke}</label>
        <label>Shadow <input type="range" min={0} max={1} step={0.05} value={st.shadow.opacity} onChange={e => up(x => { x.shadow.opacity = +e.target.value })} /></label>
        <label>Italic <input type="checkbox" checked={st.font.italic} onChange={e => up(x => { x.font.italic = e.target.checked })} /></label>
      </div>
      <h4>Placement</h4>
      <div className="grid2">
        <label>Height <input type="range" min={0.1} max={0.95} step={0.01} value={st.layout.anchorY} onChange={e => up(x => { x.layout.anchorY = +e.target.value })} /> {(st.layout.anchorY * 100).toFixed(0)}%</label>
        <label>Max width <input type="range" min={0.4} max={0.95} step={0.01} value={st.layout.maxWidth} onChange={e => up(x => { x.layout.maxWidth = +e.target.value })} /></label>
        <label>Align <select value={st.layout.align} onChange={e => up(x => { x.layout.align = e.target.value as 'left' | 'center'; x.layout.anchorX = e.target.value === 'left' ? 0.06 : 0.5 })}><option value="center">center</option><option value="left">left</option></select></label>
      </div>
      <h4>Motion</h4>
      <div className="grid2">
        <label>Reveal <select value={st.reveal.mode} onChange={e => up(x => { x.reveal.mode = e.target.value as CaptionStyle['reveal']['mode'] })}><option value="whole">whole chunk</option><option value="wordFill">word fill (karaoke)</option><option value="append">word by word</option><option value="lineStack">line stack</option></select></label>
        <label>Inactive opacity <input type="range" min={0} max={1} step={0.05} value={st.reveal.inactiveOpacity} onChange={e => up(x => { x.reveal.inactiveOpacity = +e.target.value })} /></label>
        <label>Entrance ms <input type="range" min={0} max={400} step={10} value={st.entrance.durationMs} onChange={e => up(x => { x.entrance.durationMs = +e.target.value })} /> {st.entrance.durationMs}</label>
        <label>Blur px <input type="range" min={0} max={12} value={st.entrance.blurPx} onChange={e => up(x => { x.entrance.blurPx = +e.target.value })} /></label>
        <label>Scale from <input type="range" min={0.6} max={1.4} step={0.05} value={st.entrance.scaleFrom} onChange={e => up(x => { x.entrance.scaleFrom = +e.target.value })} /> {st.entrance.scaleFrom.toFixed(2)}</label>
        <label>Ease <select value={st.entrance.ease} onChange={e => up(x => { x.entrance.ease = e.target.value as CaptionStyle['entrance']['ease'] })}><option>easeOut</option><option>easeOutBack</option><option>easeInOut</option><option>linear</option></select></label>
        <label>Exit <select value={st.exit.mode} onChange={e => up(x => { x.exit.mode = e.target.value as 'cut' | 'fade' })}><option value="cut">cut</option><option value="fade">fade</option></select></label>
        <label>Hollow inactive <input type="checkbox" checked={st.reveal.hollowInactive} onChange={e => up(x => { x.reveal.hollowInactive = e.target.checked })} /></label>
      </div>
      <h4>Keyword emphasis</h4>
      <div className="grid2">
        <label>Mode <select value={st.emphasis.mode} onChange={e => up(x => { x.emphasis.mode = e.target.value as 'auto' | 'none' })}><option value="auto">auto (1 per card)</option><option value="none">off</option></select></label>
        <label>Colour <input type="color" value={st.emphasis.color ?? st.colors.text} onChange={e => up(x => { x.emphasis.color = e.target.value })} /> <button className="mini" onClick={() => up(x => { x.emphasis.color = null })}>same</button></label>
        <label>Size ratio <input type="range" min={1} max={2} step={0.1} value={st.emphasis.sizeRatio} onChange={e => up(x => { x.emphasis.sizeRatio = +e.target.value })} /> {st.emphasis.sizeRatio.toFixed(1)}</label>
        <label>Bolder <input type="checkbox" checked={st.emphasis.weightDelta > 0} onChange={e => up(x => { x.emphasis.weightDelta = e.target.checked ? 300 : 0 })} /></label>
        <label>Italic <input type="checkbox" checked={st.emphasis.italic} onChange={e => up(x => { x.emphasis.italic = e.target.checked })} /></label>
        <label>Glow <input type="range" min={0} max={20} value={st.emphasis.glowPx} onChange={e => up(x => { x.emphasis.glowPx = +e.target.value })} /></label>
        <label>Underline <input type="checkbox" checked={st.emphasis.underline} onChange={e => up(x => { x.emphasis.underline = e.target.checked })} /></label>
        <label>Highlight box <input type="checkbox" checked={!!st.emphasis.box} onChange={e => up(x => { x.emphasis.box = e.target.checked ? { fill: '#FFFFFF', radius: 6, padX: 0.3, padY: 0.12 } : null })} />
          {st.emphasis.box && <input type="color" value={st.emphasis.box.fill} onChange={e => up(x => { x.emphasis.box!.fill = e.target.value })} />}</label>
      </div>
      <h4>Box</h4>
      <div className="grid2">
        <label>Mode <select value={st.box.mode} onChange={e => up(x => { x.box.mode = e.target.value as CaptionStyle['box']['mode'] })}><option value="none">none</option><option value="pill">pill</option><option value="bar">bar</option><option value="linePill">per line</option></select></label>
        <label>Fill <input type="color" value={st.box.fill.startsWith('#') ? st.box.fill : '#222222'} onChange={e => up(x => { x.box.fill = e.target.value })} /></label>
        <label>Radius <input type="range" min={0} max={60} value={Math.min(60, st.box.radius)} onChange={e => up(x => { x.box.radius = +e.target.value >= 60 ? 999 : +e.target.value })} /></label>
        <label>Outline <input type="range" min={0} max={6} value={st.box.outline} onChange={e => up(x => { x.box.outline = +e.target.value })} /></label>
      </div>
      <h4>Auto zoom <span className="muted">(punch-in on emphasis cards)</span></h4>
      <label className="chk"><input type="checkbox" checked={s.autoZoom} onChange={e => s.set({ autoZoom: e.target.checked, zooms: e.target.checked ? autoZooms(cards) : [] })} /> punch in 6 % over 250 ms on every other keyword card</label>
    </div>
  )
}

// ---------------- Elements ----------------
export function ElementsPanel() {
  const s = useEditor()
  const t = s.time
  const add = (o: Partial<Overlay> & { kind: Overlay['kind'] }) => s.addOverlay({ id: Math.random().toString(36).slice(2, 8), x: 0.5, y: 0.3, size: 64, color: '#FFFFFF', font: 'Inter', start: t, end: Math.min((s.project?.duration ?? t + 2), t + 2), text: '', ...o })
  const sel = s.overlays.find(o => o.id === s.selectedOverlay)
  const EMOJI = ['🔥', '😂', '👀', '💰', '✅', '❌', '👉', '🚀', '💡', '⚠️', '❤️', '🤯', '🎯', '📈', '🏆', '✨']
  return (
    <div className="panel">
      <h3>Elements</h3>
      <div className="row wrap">
        <button onClick={() => add({ kind: 'text', text: 'Your text' })}>+ Text</button>
        <label className="btn">+ Image<input type="file" accept="image/*" hidden onChange={e => { const f = e.target.files?.[0]; if (!f) return; const url = URL.createObjectURL(f); const im = new Image(); im.src = url; imageCache.set(url, im); add({ kind: 'image', src: url, w: 0.4 }) }} /></label>
      </div>
      <div className="emoji">{EMOJI.map(e => <button key={e} onClick={() => add({ kind: 'emoji', text: e, size: 120 })}>{e}</button>)}</div>
      <p className="muted small">Drag elements on the preview. They pop in with easeOutBack (pattern G sticker pop).</p>
      {sel && <div className="grid2">
        {sel.kind !== 'image' && <label>Text <input value={sel.text} onChange={e => s.updateOverlay(sel.id, { text: e.target.value })} /></label>}
        {sel.kind === 'text' && <label>Font <select value={sel.font} onChange={e => s.updateOverlay(sel.id, { font: e.target.value })}>{FONTS.map(f => <option key={f}>{f}</option>)}</select></label>}
        <label>Size <input type="range" min={20} max={300} value={sel.size} onChange={e => s.updateOverlay(sel.id, { size: +e.target.value })} /></label>
        {sel.kind === 'text' && <label>Colour <input type="color" value={sel.color} onChange={e => s.updateOverlay(sel.id, { color: e.target.value })} /></label>}
        {sel.kind === 'image' && <label>Width <input type="range" min={0.1} max={1} step={0.01} value={sel.w ?? 0.4} onChange={e => s.updateOverlay(sel.id, { w: +e.target.value })} /></label>}
        <label>Start <input type="number" step={0.1} value={sel.start.toFixed(1)} onChange={e => s.updateOverlay(sel.id, { start: +e.target.value })} /></label>
        <label>End <input type="number" step={0.1} value={sel.end.toFixed(1)} onChange={e => s.updateOverlay(sel.id, { end: +e.target.value })} /></label>
        <button onClick={() => s.updateOverlay(sel.id, { start: t })}>start = playhead</button>
        <button onClick={() => s.updateOverlay(sel.id, { end: t })}>end = playhead</button>
        <button className="danger" onClick={() => s.removeOverlay(sel.id)}>Delete element</button>
      </div>}
      <ul className="list">{s.overlays.map(o => <li key={o.id} className={o.id === s.selectedOverlay ? 'on' : ''} onClick={() => s.set({ selectedOverlay: o.id })}>{o.kind === 'image' ? '🖼 image' : o.text} <span className="muted">{fmtTime(o.start)}–{fmtTime(o.end)}</span></li>)}</ul>
    </div>
  )
}

// ---------------- Audio ----------------
export function AudioPanel() {
  const s = useEditor()
  const [busy, setBusy] = useState<string | null>(null)
  const run = async (tool: 'denoise' | 'normalize' | 'enhance') => { if (!s.project) return; setBusy(tool); try { const r = await api.audioTool(s.project.id, tool); s.set({ audioUrl: r.url }) } catch (e) { alert(String(e)) } finally { setBusy(null) } }
  return (
    <div className="panel">
      <h3>Audio</h3>
      <p className="muted small">Processed with ffmpeg on your machine. The result replaces the soundtrack in the export; listen below.</p>
      <div className="row wrap">
        <button disabled={!!busy} onClick={() => run('denoise')}>{busy === 'denoise' ? '…' : 'Denoise'}</button>
        <button disabled={!!busy} onClick={() => run('enhance')}>{busy === 'enhance' ? '…' : 'Enhance speech'}</button>
        <button disabled={!!busy} onClick={() => run('normalize')}>{busy === 'normalize' ? '…' : 'Normalise loudness'}</button>
        {s.audioUrl && <button onClick={() => s.set({ audioUrl: null })}>Use original</button>}
      </div>
      {s.audioUrl && <audio controls src={s.audioUrl} style={{ width: '100%', marginTop: 8 }} />}
      <h4>Transcription</h4>
      <div className="row"><button onClick={() => s.project && api.retranscribe(s.project.id).then(() => location.reload())}>Re-run Whisper</button>
        <select onChange={e => s.project && api.retranscribe(s.project.id, e.target.value).then(() => location.reload())} defaultValue=""><option value="" disabled>force language…</option>{['en', 'hi', 'es', 'fr', 'de', 'pt', 'ja', 'ko', 'zh', 'ar', 'ru', 'it'].map(l => <option key={l}>{l}</option>)}</select></div>
    </div>
  )
}

// ---------------- Export ----------------
export function ExportPanel({ cards }: { cards: Card[] }) {
  const s = useEditor()
  const [prog, setProg] = useState<{ p: number; msg: string } | null>(null)
  const [res, setRes] = useState(1080)
  const [fps, setFps] = useState(30)
  const [ctrl, setCtrl] = useState<AbortController | null>(null)
  const [renders, setRenders] = useState<{ url: string; name: string; size: number }[]>([])
  useEffect(() => { if (s.project) api.renders(s.project.id).then(setRenders).catch(() => setRenders([])) }, [s.project])
  const cuts = mergeCuts([...s.cuts, ...cutsFromWords(s.words)])
  const size = s.project ? aspectSize(s.aspect, s.project, res === 1080 ? 1920 : 1280) : { w: 1080, h: 1920 }
  const srtCards = cards.map(c => ({ start: c.start, end: c.end, text: c.words.map(w => w.text).join(' ') }))

  const go = async () => {
    if (!s.project) return
    const ac = new AbortController(); setCtrl(ac)
    try {
      await document.fonts.ready
      await Promise.all([s.style.font.family, ...s.overlays.map(o => o.font)].map(f => document.fonts.load(`700 40px "${f}"`).catch(() => null)))
      const blob = await exportMp4({
        videoUrl: s.project.playUrl, audioUrl: s.audioUrl, cuts, duration: s.project.duration, fps, W: size.w, H: size.h,
        frame: { cards, style: s.style, captionsOn: s.captionsOn, overlays: s.overlays, zooms: s.zooms, pan: s.pan, images: imageCache },
        onProgress: (p, msg) => setProg({ p, msg }), signal: ac.signal,
      })
      download(blob, `${(s.project.name || 'video').replace(/\.[^.]+$/, '')}-opencap.mp4`)
      setProg({ p: 1, msg: `done · ${(blob.size / 1e6).toFixed(1)} MB · saving a copy to the project…` })
      const saved = await api.saveRender(s.project.id, blob).catch(() => null)
      setProg({ p: 1, msg: `done · ${(blob.size / 1e6).toFixed(1)} MB${saved ? ` · saved as ${saved.name}` : ''}` })
      setRenders(await api.renders(s.project.id).catch(() => []))
    } catch (e) { setProg({ p: 0, msg: `failed: ${String(e)}` }) } finally { setCtrl(null) }
  }
  return (
    <div className="panel">
      <h3>Export</h3>
      <div className="grid2">
        <label>Aspect <select value={s.aspect} onChange={e => s.set({ aspect: e.target.value as Aspect })}><option value="source">source</option><option value="9:16">9:16 Shorts</option><option value="1:1">1:1</option><option value="4:5">4:5</option><option value="16:9">16:9</option></select></label>
        {s.aspect !== 'source' && <label>Crop position <input type="range" min={0} max={1} step={0.01} value={s.pan} onChange={e => s.set({ pan: +e.target.value })} /></label>}
        <label>Resolution <select value={res} onChange={e => setRes(+e.target.value)}><option value={1080}>1080</option><option value={720}>720</option></select></label>
        <label>FPS <select value={fps} onChange={e => setFps(+e.target.value)}><option value={30}>30</option><option value={24}>24</option><option value={60}>60</option></select></label>
      </div>
      <p className="muted small">{size.w}×{size.h} · {fmtTime(s.project ? (s.project.duration - cuts.reduce((n, c) => n + c.end - c.start, 0)) : 0)} after {cuts.length} cuts · H.264 + AAC rendered in your browser (WebCodecs), nothing uploaded.</p>
      {!webCodecsOk() && <p className="warn">This browser lacks WebCodecs. Use Chrome/Edge, or the server fallback below (cuts only, no captions).</p>}
      <div className="row">
        {!ctrl ? <button className="primary" onClick={go} disabled={!webCodecsOk()}>Export MP4</button> : <button className="danger" onClick={() => ctrl.abort()}>Cancel</button>}
        <button onClick={() => api.srt(srtCards, 'srt').then(t => download(new Blob([t]), 'captions.srt'))}>SRT</button>
        <button onClick={() => api.srt(srtCards, 'vtt').then(t => download(new Blob([t]), 'captions.vtt'))}>VTT</button>
        <button onClick={() => s.project && api.exportServer(s.project.id, cuts).then(r => download(r.url, 'cut.mp4'))}>Server cut (no captions)</button>
      </div>
      {prog && <div className="progress"><div style={{ width: `${prog.p * 100}%` }} /><span>{prog.msg}</span></div>}
      {renders.length > 0 && <><h4>Previous renders</h4><ul className="list">{renders.map(r => <li key={r.name}><a href={r.url} download>{r.name}</a><span className="muted">{(r.size / 1e6).toFixed(1)} MB</span></li>)}</ul></>}
    </div>
  )
}
