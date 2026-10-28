import { useEffect, useRef, useState } from 'react'
import { studio, type Asset, type Character, type Field } from './api'

export type Val = string | number | boolean | string[] | File | File[] | null | undefined
export type MediaVal = { file?: File; url?: string; preview: string; name: string }

const opt = (o: Field['options'] extends (infer T)[] | undefined ? T : never) => typeof o === 'string' ? { value: o, label: o } : o
const accept = (t: string) => t === 'image' || t === 'images' ? 'image/*' : t === 'video' ? 'video/*' : t === 'audio' ? 'audio/*' : 'image/*,video/*,audio/*'
const kindOf = (t: string) => t === 'images' ? 'image' : t === 'media' ? undefined : t

export function visible(f: Field, values: Record<string, unknown>) {
  if (!f.showIf) return true
  return Object.entries(f.showIf).every(([k, allowed]) => allowed.includes(values[k] as never))
}

export function FieldInput({ f, value, onChange, characters, values }: { f: Field; value: unknown; onChange: (v: unknown) => void; characters: Character[]; values: Record<string, unknown> }) {
  const v = value ?? f.default ?? ''
  switch (f.type) {
    case 'textarea':
      return <textarea rows={f.id === 'script' || f.id === 'story' ? 9 : 4} value={String(v)} placeholder={f.placeholder} onChange={e => onChange(e.target.value)} />
    case 'select':
      return <select value={String(v)} onChange={e => onChange(e.target.value)}>{f.options?.map(o => { const x = opt(o); return <option key={x.value} value={x.value}>{x.label}</option> })}</select>
    case 'chips': {
      const multi = Array.isArray(f.default)
      const cur = multi ? (Array.isArray(v) ? v as string[] : []) : [String(v)]
      return <div className="chips">{f.options?.map(o => { const x = opt(o); const on = cur.includes(x.value)
        return <button type="button" key={x.value} className={`chip-btn ${on ? 'on' : ''}`} onClick={() => onChange(multi ? (on ? cur.filter(c => c !== x.value) : [...cur, x.value]) : x.value)}>{x.label}</button> })}</div>
    }
    case 'number':
      return <input type="number" value={String(v)} min={f.min} max={f.max} step={f.step} onChange={e => onChange(e.target.value === '' ? '' : Number(e.target.value))} />
    case 'slider':
      return <span className="slider"><input type="range" value={Number(v)} min={f.min} max={f.max} step={f.step ?? 1} onChange={e => onChange(Number(e.target.value))} /><span className="mono">{String(v)}</span></span>
    case 'toggle':
      return <label className="switch"><input type="checkbox" checked={Boolean(v)} onChange={e => onChange(e.target.checked)} /><span /></label>
    case 'color':
      return <input type="color" value={String(v || '#ffffff')} onChange={e => onChange(e.target.value)} />
    case 'character':
      return <select value={String(v)} onChange={e => onChange(e.target.value)}><option value="">None</option>{characters.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
    case 'characters': {
      const cur = Array.isArray(v) ? v as string[] : []
      return <div className="chips">{characters.length ? characters.map(c => <button type="button" key={c.id} className={`chip-btn ${cur.includes(c.id) ? 'on' : ''}`}
        onClick={() => onChange(cur.includes(c.id) ? cur.filter(x => x !== c.id) : [...cur, c.id])}>{c.refs[0] && <img src={c.refs[0]} alt="" />}{c.name}</button>) : <span className="muted small">No locked characters yet. Create one in Characters.</span>}</div>
    }
    case 'image': case 'images': case 'video': case 'audio': case 'media':
      return <MediaInput f={f} value={value as MediaVal[] | undefined} onChange={onChange} />
    case 'mask': {
      const img = (values.image as MediaVal[] | undefined)?.[0]
      return img ? <Painter key={img.preview} mode="mask" bg={img.preview} onChange={b => onChange(b ? [{ file: new File([b], 'mask.png', { type: 'image/png' }), preview: '', name: 'mask.png' }] : undefined)} />
        : <span className="muted small">Add the image first, then paint over it here.</span>
    }
    case 'sketch':
      return <SketchField onChange={b => onChange(b ? [{ file: new File([b], 'sketch.png', { type: 'image/png' }), preview: '', name: 'sketch.png' }] : undefined)} />
    default:
      return <input type="text" value={String(v)} placeholder={f.placeholder} onChange={e => onChange(e.target.value)} />
  }
}

function MediaInput({ f, value, onChange }: { f: Field; value?: MediaVal[]; onChange: (v: MediaVal[]) => void }) {
  const pick = useRef<HTMLInputElement>(null)
  const [lib, setLib] = useState(false)
  const [over, setOver] = useState(false)
  const multi = f.type === 'images'
  const items = value ?? []
  const add = (files: FileList | null) => {
    if (!files?.length) return
    const next = [...files].map(file => ({ file, preview: URL.createObjectURL(file), name: file.name }))
    onChange(multi ? [...items, ...next] : next.slice(0, 1))
  }
  return (
    <div className={`media-in ${over ? 'over' : ''}`} onDragOver={e => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)}
      onDrop={e => { e.preventDefault(); setOver(false); add(e.dataTransfer.files) }}>
      <input ref={pick} type="file" hidden multiple={multi} accept={accept(f.type)} onChange={e => { add(e.target.files); e.target.value = '' }} />
      {items.map((m, i) => (
        <div key={i} className="media-thumb">
          <Preview url={m.preview} name={m.name} />
          <button type="button" className="x" title="Remove" onClick={() => onChange(items.filter((_, k) => k !== i))}>×</button>
        </div>
      ))}
      {(multi || !items.length) && (
        <div className="media-add">
          <button type="button" onClick={() => pick.current?.click()}>Upload</button>
          <button type="button" className="ghost" onClick={() => setLib(true)}>From library</button>
          <span className="muted small">or drop a file</span>
        </div>
      )}
      {lib && <LibraryPicker kind={kindOf(f.type)} onClose={() => setLib(false)} onPick={a => { setLib(false); const m = { url: a.url!, preview: a.url!, name: a.name || a.toolName || 'asset' }; onChange(multi ? [...items, m] : [m]) }} />}
    </div>
  )
}

export function Preview({ url, name }: { url: string; name?: string }) {
  const n = (name || url).toLowerCase()
  if (/\.(mp4|webm|mov|mkv)(\?|$)/.test(n) || n.startsWith('video')) return <video src={url} muted playsInline loop autoPlay />
  if (/\.(mp3|wav|m4a|aac|ogg|flac)(\?|$)/.test(n)) return <div className="audio-chip">♪ {name}</div>
  return <img src={url} alt={name} />
}

export function LibraryPicker({ kind, onPick, onClose }: { kind?: string; onPick: (a: Asset) => void; onClose: () => void }) {
  const [items, setItems] = useState<Asset[] | null>(null)
  useEffect(() => { studio.assets(kind).then(setItems).catch(() => setItems([])) }, [kind])
  return (
    <div className="modal" onClick={onClose}>
      <div className="modal-card" onClick={e => e.stopPropagation()}>
        <div className="modal-head"><h3>Pick from library <span className="muted">{kind ?? 'any media'}</span></h3><button className="icon" onClick={onClose}>×</button></div>
        <div className="lib-grid">
          {items?.filter(a => a.url).map((a, i) => (
            <button key={i} className="lib-item" onClick={() => onPick(a)}>
              <Preview url={a.url!} name={a.url} />
              <span>{a.toolName}</span>
            </button>
          ))}
          {items && !items.length && <p className="muted">Nothing here yet. Generated and uploaded files show up in the library.</p>}
          {!items && <p className="muted">Loading…</p>}
        </div>
      </div>
    </div>
  )
}

/** Serialise form values for the run endpoint: files as uploads, library picks as "<id>@url". */
export function toFormData(fields: Field[], values: Record<string, unknown>) {
  const fd = new FormData()
  for (const f of fields) {
    if (!visible(f, values)) continue
    const v = values[f.id] ?? f.default
    if (v == null || v === '') continue
    if (['image', 'images', 'video', 'audio', 'media', 'mask', 'sketch'].includes(f.type)) {
      for (const m of v as MediaVal[]) { if (m.file) fd.append(f.id, m.file); else if (m.url) fd.append(`${f.id}@url`, m.url) }
    } else if (Array.isArray(v)) v.forEach(x => fd.append(f.id, String(x)))
    else fd.append(f.id, String(v))
  }
  return fd
}

const RATIOS: Record<string, [number, number]> = { '16:9 Widescreen': [1344, 756], '9:16 Vertical': [756, 1344], '1:1 Square': [1024, 1024], '4:3 Classic': [1152, 864], '3:4 Portrait': [864, 1152] }

function SketchField({ onChange }: { onChange: (b: Blob | null) => void }) {
  const [bg, setBg] = useState<string | null>(null)
  const [ratio, setRatio] = useState('16:9 Widescreen')
  const pick = useRef<HTMLInputElement>(null)
  return (
    <div className="sketch">
      <div className="row">
        <select value={ratio} onChange={e => { setBg(null); setRatio(e.target.value) }}>{Object.keys(RATIOS).map(r => <option key={r}>{r}</option>)}</select>
        <button type="button" onClick={() => pick.current?.click()}>Upload media</button>
        {bg && <button type="button" className="ghost" onClick={() => setBg(null)}>Blank canvas</button>}
        <input ref={pick} type="file" accept="image/*" hidden onChange={e => { const f = e.target.files?.[0]; if (f) setBg(URL.createObjectURL(f)) }} />
      </div>
      <Painter key={bg ?? ratio} mode="sketch" bg={bg} size={RATIOS[ratio]} onChange={onChange} />
    </div>
  )
}

/** Paint on a canvas. mask: white strokes on black at the image's own size; sketch: coloured strokes over a blank or uploaded background. */
export function Painter({ mode, bg, size, onChange }: { mode: 'mask' | 'sketch'; bg: string | null; size?: [number, number]; onChange: (b: Blob | null) => void }) {
  const view = useRef<HTMLCanvasElement>(null)
  const ink = useRef<HTMLCanvasElement | null>(null)
  const img = useRef<HTMLImageElement | null>(null)
  const [brush, setBrush] = useState(mode === 'mask' ? 48 : 8)
  const [color, setColor] = useState('#111111')
  const [dims, setDims] = useState<[number, number]>(size ?? [1024, 1024])
  const drawing = useRef(false); const last = useRef<[number, number] | null>(null)

  useEffect(() => {
    const setup = (w: number, h: number) => {
      setDims([w, h]); const c = document.createElement('canvas'); c.width = w; c.height = h; ink.current = c; redraw()
    }
    if (bg) { const im = new Image(); im.onload = () => { img.current = im; setup(im.naturalWidth, im.naturalHeight) }; im.src = bg }
    else { img.current = null; setup(...(size ?? [1024, 1024])) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bg])

  const redraw = () => {
    const v = view.current, k = ink.current; if (!v || !k) return
    v.width = k.width; v.height = k.height; const g = v.getContext('2d')!
    g.fillStyle = '#fff'; g.fillRect(0, 0, v.width, v.height)
    if (img.current) g.drawImage(img.current, 0, 0, v.width, v.height)
    g.globalAlpha = mode === 'mask' ? 0.55 : 1; g.drawImage(k, 0, 0); g.globalAlpha = 1
  }
  const export_ = () => {
    const k = ink.current!; const c = document.createElement('canvas'); c.width = k.width; c.height = k.height; const g = c.getContext('2d')!
    if (mode === 'mask') { g.fillStyle = '#000'; g.fillRect(0, 0, c.width, c.height); g.drawImage(k, 0, 0) }
    else { g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height); if (img.current) g.drawImage(img.current, 0, 0, c.width, c.height); g.drawImage(k, 0, 0) }
    c.toBlob(b => onChange(b), 'image/png')
  }
  const at = (e: React.PointerEvent): [number, number] => { const r = view.current!.getBoundingClientRect(); return [(e.clientX - r.left) * dims[0] / r.width, (e.clientY - r.top) * dims[1] / r.height] }
  const stroke = (p: [number, number]) => {
    const g = ink.current!.getContext('2d')!; g.lineCap = 'round'; g.lineJoin = 'round'
    g.strokeStyle = mode === 'mask' ? '#fff' : color; g.lineWidth = brush * dims[0] / 1024
    g.beginPath(); const a = last.current ?? p; g.moveTo(a[0], a[1]); g.lineTo(p[0], p[1]); g.stroke(); last.current = p; redraw()
  }
  return (
    <div className="painter">
      <canvas ref={view} style={{ aspectRatio: `${dims[0]} / ${dims[1]}` }}
        onPointerDown={e => { drawing.current = true; last.current = null; (e.target as Element).setPointerCapture(e.pointerId); stroke(at(e)) }}
        onPointerMove={e => drawing.current && stroke(at(e))}
        onPointerUp={() => { drawing.current = false; export_() }} />
      <div className="row">
        <label>Brush <input type="range" min={2} max={160} value={brush} onChange={e => setBrush(+e.target.value)} /></label>
        {mode === 'sketch' && <input type="color" value={color} onChange={e => setColor(e.target.value)} />}
        <button type="button" className="ghost" onClick={() => { const k = ink.current!; k.getContext('2d')!.clearRect(0, 0, k.width, k.height); redraw(); onChange(null) }}>Clear</button>
      </div>
    </div>
  )
}
