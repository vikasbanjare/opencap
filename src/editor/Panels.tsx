import { useEffect, useMemo, useState } from 'react'
import { useEditor, aspectSize, mediaCache, ensureMedia, type Aspect } from '../store'
import { PRESETS, ALL_TAGS } from '../captions/presets'
import type { Card, CaptionStyle, Overlay, Word } from '../captions/types'
import { fillerIndices, silenceCuts, mergeCuts, autoZooms, cutsFromWords, fmtTime } from '../lib/timeline'
import { api, download } from '../lib/api'
import { exportMp4, webCodecsOk } from '../lib/export'

const FONTS = ['Inter', 'Oswald', 'Montserrat', 'Bebas Neue', 'Poppins', 'Nunito', 'Playfair Display', 'EB Garamond', 'Caveat', 'Space Mono', 'Anton', 'Permanent Marker']
const LANGS: Record<string, string> = { en: 'English', es: 'Spanish', fr: 'French', de: 'German', pt: 'Portuguese', it: 'Italian', hi: 'Hindi', ar: 'Arabic', zh: 'Chinese', ja: 'Japanese', ko: 'Korean', ru: 'Russian', tr: 'Turkish', id: 'Indonesian', nl: 'Dutch', pl: 'Polish', uk: 'Ukrainian', vi: 'Vietnamese', th: 'Thai', sv: 'Swedish' }

// ---------------- Captions ----------------
export function CaptionsPanel({ cards, seek }: { cards: Card[]; seek: (t: number) => void }) {
  const s = useEditor()
  const [editing, setEditing] = useState<number | null>(null)
  const [gap, setGap] = useState(0.8)
  const [langs, setLangs] = useState<string[]>([])
  const [busy, setBusy] = useState<string | null>(null)
  useEffect(() => { api.translateLanguages().then(r => setLangs(r.available)).catch(() => setLangs([])) }, [])
  const fillers = useMemo(() => fillerIndices(s.words).filter(i => !s.words[i].deleted), [s.words])
  const deletedN = s.words.filter(w => w.deleted).length
  const status = s.project?.transcribeStatus

  if (!s.words.length) return (
    <div className="panel">
      <h3>Captions</h3>
      <p className="muted">{status === 'running' ? 'Transcribing with Whisper… this page refreshes itself when it finishes (a 30 s clip takes ~15 s; the first clip after the server starts can take a minute while the model loads).' : status === 'error' ? `Transcription failed: ${s.project?.transcribeError}` : 'No transcript yet.'}</p>
      {status !== 'running' && <button onClick={() => s.project && api.retranscribe(s.project.id)}>Transcribe again</button>}
    </div>
  )

  const toggleDelete = (i: number) => s.setWords(ws => ws.map((w, j) => j === i ? { ...w, deleted: !w.deleted } : w))
  const toggleEmph = (i: number) => s.setWords(ws => ws.map((w, j) => j === i ? { ...w, emph: !w.emph } : w))
  const edit = (i: number, text: string) => { s.setWords(ws => ws.map((w, j) => j === i ? { ...w, text } : w)); setEditing(null) }
  const autoEdit = () => {
    s.setWords(ws => ws.map((w, i) => fillers.includes(i) ? { ...w, deleted: true } : w))
    s.set({ cuts: mergeCuts([...s.cuts, ...silenceCuts(s.words, 0.8, 0.15, s.project?.duration)]), autoZoom: true, zooms: autoZooms(cards) })
  }
  const translate = async (target: string) => {
    if (!s.project || !target) return
    setBusy(target)
    try {
      // translate whole sentences (consecutive cards up to . ! ?) so the MT model sees context,
      // then spread the translated words evenly over each sentence's time span
      const groups: Card[][] = [[]]
      for (const c of cards) { groups[groups.length - 1].push(c); if (/[.!?]$/.test(c.words[c.words.length - 1].text)) groups.push([]) }
      const sents = groups.filter(g => g.length)
      const r = await api.translate(sents.map(g => g.flatMap(c => c.words.map(w => w.text)).join(' ')), s.project.language ?? 'en', target)
      const out: Word[] = []
      sents.forEach((g, gi) => {
        const toks = r.texts[gi].split(/\s+/).filter(Boolean)
        const t0 = g[0].words[0].start, t1 = g[g.length - 1].words[g[g.length - 1].words.length - 1].end
        const span = (t1 - t0) / Math.max(1, toks.length)
        toks.forEach((t, k) => out.push({ text: t, start: t0 + k * span, end: t0 + (k + 1) * span }))
      })
      localStorage.setItem(`opencap:${s.project.id}:original`, JSON.stringify(s.words))
      s.setWords(() => out)
    } catch (e) { alert(String(e)) } finally { setBusy(null) }
  }
  const original = s.project && localStorage.getItem(`opencap:${s.project.id}:original`)

  return (
    <div className="panel">
      <h3>Captions <span className="muted">{s.words.length} words · {cards.length} cards · {s.project?.language}</span></h3>
      <div className="row wrap">
        <button className="primary" onClick={autoEdit} title="remove fillers, cut silences over 0.8 s, add punch-ins">✦ Auto edit</button>
        <button disabled={!fillers.length} onClick={() => s.setWords(ws => ws.map((w, i) => fillers.includes(i) ? { ...w, deleted: true } : w))}>Remove fillers ({fillers.length})</button>
        <button onClick={() => s.set({ cuts: mergeCuts([...s.cuts, ...silenceCuts(s.words, gap, 0.15, s.project?.duration)]) })}>Cut silences &gt; <input type="number" step="0.1" min="0.3" value={gap} onChange={e => setGap(+e.target.value)} style={{ width: 48 }} />s</button>
        <button disabled={!deletedN} onClick={() => s.setWords(ws => ws.map(w => ({ ...w, deleted: false })))}>Restore {deletedN} words</button>
        <label className="chk"><input type="checkbox" checked={s.captionsOn} onChange={e => s.set({ captionsOn: e.target.checked })} /> show captions</label>
      </div>
      <div className="row">
        <label>Words / card <input type="range" min={1} max={6} value={s.style.chunk.maxWords} onChange={e => s.setStyle(st => ({ ...st, chunk: { ...st.chunk, maxWords: +e.target.value } }))} /> {s.style.chunk.maxWords}</label>
        <label>Max chars <input type="range" min={8} max={40} value={s.style.chunk.maxChars} onChange={e => s.setStyle(st => ({ ...st, chunk: { ...st.chunk, maxChars: +e.target.value } }))} /> {s.style.chunk.maxChars}</label>
      </div>
      <div className="row">
        <label>Translate to <select disabled={!!busy || !langs.length} defaultValue="" onChange={e => translate(e.target.value)}><option value="" disabled>{busy ? `translating → ${busy}…` : langs.length ? 'choose language' : 'translation unavailable'}</option>{langs.filter(l => l !== (s.project?.language ?? 'en')).map(l => <option key={l} value={l}>{LANGS[l] ?? l}</option>)}</select></label>
        {original && <button onClick={() => { s.setWords(() => JSON.parse(original)); localStorage.removeItem(`opencap:${s.project!.id}:original`) }}>Revert to original</button>}
      </div>
      <p className="muted small">Click a word to seek. Double-click to edit. Delete/Backspace removes it from the video (text-based cut). E marks the keyword. Translation runs offline; the first use of a language downloads its pack.</p>
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
  const [q, setQ] = useState(''); const [tag, setTag] = useState('')
  const shown = PRESETS.filter(p => (!tag || p.tags.includes(tag)) && (!q || p.name.toLowerCase().includes(q.toLowerCase())))
  return (
    <div className="panel">
      <h3>Style <span className="muted">{shown.length} of {PRESETS.length}</span></h3>
      <input placeholder="Search styles" value={q} onChange={e => setQ(e.target.value)} style={{ width: '100%', marginBottom: 6 }} />
      <div className="tags">
        <button className={`mini ${tag === '' ? 'on' : ''}`} onClick={() => setTag('')}>All</button>
        {ALL_TAGS.map(t => <button key={t} className={`mini ${tag === t ? 'on' : ''}`} onClick={() => setTag(tag === t ? '' : t)}>{t}</button>)}
      </div>
      <div className="presets">
        {shown.map(p => <button key={p.id} className={`preset ${st.id === p.id ? 'on' : ''}`} onClick={() => s.pickPreset(p.id)}>
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
  const [busy, setBusy] = useState(false)
  const EMOJI = ['🔥', '😂', '👀', '💰', '✅', '❌', '👉', '🚀', '💡', '⚠️', '❤️', '🤯', '🎯', '📈', '🏆', '✨']
  const uploadMedia = async (f: File | undefined, kind: 'image' | 'video') => {
    if (!f || !s.project) return
    setBusy(true)
    try {
      const a = await api.uploadAsset(s.project.id, f)
      const o: Overlay = { id: Math.random().toString(36).slice(2, 8), kind, src: a.url, x: 0.5, y: kind === 'video' ? 0.5 : 0.3, w: kind === 'video' ? 0.45 : 0.4, size: 64, color: '#fff', font: 'Inter', start: t, end: Math.min(s.project.duration, t + (kind === 'video' ? Math.min(a.duration ?? 3, 3) : 2)), fit: 'cover', srcDuration: a.duration }
      ensureMedia(o); s.addOverlay(o)
    } catch (e) { alert(String(e)) } finally { setBusy(false) }
  }
  return (
    <div className="panel">
      <h3>Elements</h3>
      <div className="row wrap">
        <button onClick={() => add({ kind: 'text', text: 'Your text' })}>+ Text</button>
        <label className="btn">+ Image<input type="file" accept="image/*" hidden onChange={e => uploadMedia(e.target.files?.[0], 'image')} /></label>
        <label className="btn">{busy ? '…' : '+ B-roll clip'}<input type="file" accept="video/*" hidden onChange={e => uploadMedia(e.target.files?.[0], 'video')} /></label>
      </div>
      <div className="emoji">{EMOJI.map(e => <button key={e} onClick={() => add({ kind: 'emoji', text: e, size: 120 })}>{e}</button>)}</div>
      <p className="muted small">B-roll clips drop in at the playhead: full frame replaces the picture while the speaker's audio continues (Captions.ai style); picture-in-picture floats over it. Drag elements on the preview.</p>
      {sel && <div className="grid2">
        {(sel.kind === 'text' || sel.kind === 'emoji') && <label>Text <input value={sel.text} onChange={e => s.updateOverlay(sel.id, { text: e.target.value })} /></label>}
        {sel.kind === 'text' && <label>Font <select value={sel.font} onChange={e => s.updateOverlay(sel.id, { font: e.target.value })}>{FONTS.map(f => <option key={f}>{f}</option>)}</select></label>}
        {(sel.kind === 'text' || sel.kind === 'emoji') && <label>Size <input type="range" min={20} max={300} value={sel.size} onChange={e => s.updateOverlay(sel.id, { size: +e.target.value })} /></label>}
        {sel.kind === 'text' && <label>Colour <input type="color" value={sel.color} onChange={e => s.updateOverlay(sel.id, { color: e.target.value })} /></label>}
        {sel.kind === 'video' && <label>Fit <select value={sel.fit ?? 'cover'} onChange={e => s.updateOverlay(sel.id, { fit: e.target.value as 'cover' | 'pip' })}><option value="cover">full frame</option><option value="pip">picture in picture</option></select></label>}
        {(sel.kind === 'image' || (sel.kind === 'video' && sel.fit === 'pip')) && <label>Width <input type="range" min={0.1} max={1} step={0.01} value={sel.w ?? 0.4} onChange={e => s.updateOverlay(sel.id, { w: +e.target.value })} /></label>}
        <label>Start <input type="number" step={0.1} value={sel.start.toFixed(1)} onChange={e => s.updateOverlay(sel.id, { start: +e.target.value })} /></label>
        <label>End <input type="number" step={0.1} value={sel.end.toFixed(1)} onChange={e => s.updateOverlay(sel.id, { end: +e.target.value })} /></label>
        <button onClick={() => s.updateOverlay(sel.id, { start: t })}>start = playhead</button>
        <button onClick={() => s.updateOverlay(sel.id, { end: t })}>end = playhead</button>
        <button className="danger" onClick={() => s.removeOverlay(sel.id)}>Delete element</button>
      </div>}
      <ul className="list">{s.overlays.map(o => <li key={o.id} className={o.id === s.selectedOverlay ? 'on' : ''} onClick={() => s.set({ selectedOverlay: o.id })}>{o.kind === 'image' ? '🖼 image' : o.kind === 'video' ? `🎞 B-roll (${o.fit})` : o.text} <span className="muted">{fmtTime(o.start)}–{fmtTime(o.end)}</span></li>)}</ul>
    </div>
  )
}

// ---------------- Audio ----------------
export function AudioPanel({ cards }: { cards: Card[] }) {
  const s = useEditor()
  const [busy, setBusy] = useState<string | null>(null)
  const [voices, setVoices] = useState<{ voices: string[]; ready: boolean; clone: boolean } | null>(null)
  const [voice, setVoice] = useState('af_heart')
  const [speed, setSpeed] = useState(1)
  const [ref, setRef] = useState({ start: 0, end: 10 })
  const [ttsText, setTtsText] = useState('')
  const [tts, setTts] = useState<{ url: string; duration: number } | null>(null)
  useEffect(() => { api.ttsVoices().then(setVoices).catch(() => setVoices({ voices: [], ready: false, clone: false })) }, [])
  useEffect(() => { if (!ttsText && cards.length) setTtsText(cards.map(c => c.words.map(w => w.text).join(' ')).join(' ')) }, [cards, ttsText])
  const run = async (tool: 'denoise' | 'normalize' | 'enhance') => { if (!s.project) return; setBusy(tool); try { const r = await api.audioTool(s.project.id, tool); s.set({ audioUrl: r.url }) } catch (e) { alert(String(e)) } finally { setBusy(null) } }
  const addMusic = async (f: File | undefined) => { if (!f || !s.project) return; setBusy('music'); try { const a = await api.uploadAsset(s.project.id, f); s.set({ music: { url: a.url, name: a.name, gainDb: -16, duck: true, duckDb: -10, start: 0 } }) } catch (e) { alert(String(e)) } finally { setBusy(null) } }
  const speak = async () => { setBusy('tts'); try { setTts(voice === 'clone' ? await api.clone(s.project!.id, ttsText, ref.start, ref.end, speed) : await api.tts(ttsText, voice, speed)) } catch (e) { alert(String(e)) } finally { setBusy(null) } }
  return (
    <div className="panel">
      <h3>Audio</h3>
      <h4>Clean up <span className="muted">(ffmpeg, local)</span></h4>
      <div className="row wrap">
        <button disabled={!!busy} onClick={() => run('denoise')}>{busy === 'denoise' ? '…' : 'Denoise'}</button>
        <button disabled={!!busy} onClick={() => run('enhance')}>{busy === 'enhance' ? '…' : 'Enhance speech'}</button>
        <button disabled={!!busy} onClick={() => run('normalize')}>{busy === 'normalize' ? '…' : 'Normalise loudness'}</button>
        {s.audioUrl && <button onClick={() => s.set({ audioUrl: null })}>Use original</button>}
      </div>
      {s.audioUrl && <p className="muted small">Using processed track {s.audioUrl.split('/').pop()} in preview and export.</p>}

      <h4>Music bed</h4>
      <div className="row wrap">
        <label className="btn">{busy === 'music' ? '…' : '+ Add music file'}<input type="file" accept="audio/*" hidden onChange={e => addMusic(e.target.files?.[0])} /></label>
        {s.music && <button onClick={() => s.set({ music: null })}>Remove</button>}
      </div>
      {s.music && <div className="grid2">
        <label>Level <input type="range" min={-40} max={0} value={s.music.gainDb} onChange={e => s.set({ music: { ...s.music!, gainDb: +e.target.value } })} /> {s.music.gainDb} dB</label>
        <label>Duck under speech <input type="checkbox" checked={s.music.duck} onChange={e => s.set({ music: { ...s.music!, duck: e.target.checked } })} /></label>
        <label>Duck by <input type="range" min={-24} max={0} value={s.music.duckDb} onChange={e => s.set({ music: { ...s.music!, duckDb: +e.target.value } })} /> {s.music.duckDb} dB</label>
        <label>Starts at <input type="number" step={0.1} value={s.music.start} onChange={e => s.set({ music: { ...s.music!, start: +e.target.value } })} /> s</label>
        <span className="muted small">{s.music.name}</span>
      </div>}

      <h4>Text to speech <span className="muted">(Kokoro-82M, offline)</span></h4>
      {voices && !voices.ready && <p className="warn small">Kokoro model not downloaded yet: put kokoro-v1.0.onnx and voices-v1.0.bin in server/models/.</p>}
      <textarea value={ttsText} onChange={e => setTtsText(e.target.value)} rows={4} style={{ width: '100%' }} />
      <div className="row wrap">
        <select value={voice} onChange={e => setVoice(e.target.value)}>
          {(voices?.voices ?? ['af_heart']).map(v => <option key={v}>{v}</option>)}
          {voices?.clone && <option value="clone">Clone my voice (F5-TTS)</option>}
        </select>
        {voice === 'clone' && <label>Reference <input type="number" step={0.5} min={0} value={ref.start} onChange={e => setRef({ ...ref, start: +e.target.value })} style={{ width: 60 }} /> – <input type="number" step={0.5} min={0} value={ref.end} onChange={e => setRef({ ...ref, end: +e.target.value })} style={{ width: 60 }} /> s <span className="muted small">(3–15 s of your clean speech; first run downloads ~1.4 GB)</span></label>}
        <label>Speed <input type="range" min={0.6} max={1.5} step={0.05} value={speed} onChange={e => setSpeed(+e.target.value)} /> {speed.toFixed(2)}</label>
        <button disabled={!!busy || !ttsText.trim()} onClick={speak}>{busy === 'tts' ? 'generating…' : 'Generate'}</button>
      </div>
      {tts && <div>
        <audio controls src={tts.url} style={{ width: '100%' }} />
        <div className="row wrap">
          <button onClick={() => s.set({ audioUrl: tts.url })}>Use as voiceover (replace audio)</button>
          <button onClick={() => s.set({ music: { url: tts.url, name: 'voiceover', gainDb: 0, duck: false, duckDb: 0, start: s.time } })}>Place at playhead as extra track</button>
          <a className="btn" href={tts.url} download>Download wav</a>
        </div>
      </div>}
      {voices && !voices.clone && <p className="muted small">Voice cloning (AI twin) is an optional plugin: install F5-TTS into server/.venv-clone, see README.</p>}

      <h4>Transcription</h4>
      <div className="row"><button onClick={() => s.project && api.retranscribe(s.project.id).then(() => location.reload())}>Re-run Whisper</button>
        <select onChange={e => s.project && api.retranscribe(s.project.id, e.target.value).then(() => location.reload())} defaultValue=""><option value="" disabled>force language…</option>{Object.keys(LANGS).map(l => <option key={l} value={l}>{LANGS[l]}</option>)}</select></div>
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
        videoUrl: s.project.playUrl, audioUrl: s.audioUrl, music: s.music, words: s.words, cuts, duration: s.project.duration, fps, W: size.w, H: size.h,
        frame: { cards, style: s.style, captionsOn: s.captionsOn, overlays: s.overlays, zooms: s.zooms, pan: s.pan, images: mediaCache.images, videos: mediaCache.videos },
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
