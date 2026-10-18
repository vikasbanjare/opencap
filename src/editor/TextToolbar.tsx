import { useEditor } from '../store'
import { FONTS } from './Panels'
import { DEFAULT_ANIM } from '../captions/engine'
import { hideCard, idxOf, splitCard } from '../captions/edit'
import type { Card, CaptionStyle, TextCase } from '../captions/types'

const CASES: TextCase[] = ['as-is', 'sentence', 'upper', 'lower']
const CASE_LABEL: Record<TextCase, string> = { 'as-is': 'Aa', sentence: 'Aa.', upper: 'AA', lower: 'aa' }

/** Floating toolbar over the stage while a caption is selected: the everyday text controls in one place. */
export function TextToolbar({ card }: { card?: Card }) {
  const s = useEditor(), st = s.style
  const up = (f: (x: CaptionStyle) => void) => s.setStyle(x => { const c: CaptionStyle = JSON.parse(JSON.stringify(x)); f(c); return c })
  const hot = st.anim?.activeColor ?? st.emphasis.color ?? '#FFE600'
  const bold = st.font.weight >= 700
  return (
    <div className="text-toolbar" onPointerDown={e => e.stopPropagation()}>
      <select title="Font" value={st.font.family} onChange={e => up(x => { x.font.family = e.target.value })} style={{ fontFamily: st.font.family }}>
        {FONTS.map(f => <option key={f} style={{ fontFamily: f }}>{f}</option>)}
      </select>
      <div className="seg" title="Size">
        <button onClick={() => up(x => { x.font.size = Math.max(20, x.font.size - 4) })}>−</button>
        <span className="mono">{st.font.size}</span>
        <button onClick={() => up(x => { x.font.size = Math.min(220, x.font.size + 4) })}>+</button>
      </div>
      <span className="sep" />
      <label className="swatch" title="Text colour"><span style={{ background: st.colors.text }} />A<input type="color" value={st.colors.text} onChange={e => up(x => { x.colors.text = e.target.value })} /></label>
      <label className="swatch" title="Highlight colour (keyword and spoken word)"><span style={{ background: hot }} />✦<input type="color" value={hot.slice(0, 7)} onChange={e => up(x => { x.emphasis.color = e.target.value; x.anim = { ...DEFAULT_ANIM, ...x.anim, activeColor: e.target.value } })} /></label>
      <label className="swatch" title="Outline"><span style={{ background: st.stroke ? st.colors.stroke : 'transparent', outline: '1px dashed #bbb' }} />O<input type="color" value={st.colors.stroke.slice(0, 7)} onChange={e => up(x => { x.colors.stroke = e.target.value; if (!x.stroke) x.stroke = 4 })} /></label>
      <button className={`tb ${st.stroke ? 'on' : ''}`} title="Outline on/off" onClick={() => up(x => { x.stroke = x.stroke ? 0 : 4 })}>◌</button>
      <label className="swatch" title="Background box"><span style={{ background: st.box.mode !== 'none' ? st.box.fill : 'transparent', outline: '1px dashed #bbb' }} />▭<input type="color" value={st.box.fill.startsWith('#') ? st.box.fill.slice(0, 7) : '#000000'} onChange={e => up(x => { x.box.fill = e.target.value; if (x.box.mode === 'none') x.box.mode = 'pill' })} /></label>
      <span className="sep" />
      <button className={`tb ${bold ? 'on' : ''}`} title="Bold" style={{ fontWeight: 800 }} onClick={() => up(x => { x.font.weight = bold ? 400 : 800 })}>B</button>
      <button className={`tb ${st.font.italic ? 'on' : ''}`} title="Italic" style={{ fontStyle: 'italic', fontFamily: 'Georgia, serif' }} onClick={() => up(x => { x.font.italic = !x.font.italic })}>I</button>
      <button className="tb" title="Letter case" onClick={() => up(x => { x.font.case = CASES[(CASES.indexOf(x.font.case) + 1) % CASES.length] })}>{CASE_LABEL[st.font.case]}</button>
      <button className={`tb ${st.layout.align === 'left' ? 'on' : ''}`} title="Align left" onClick={() => up(x => { x.layout.align = 'left'; x.layout.anchorX = 0.06 })}>⇤</button>
      <button className={`tb ${st.layout.align === 'center' ? 'on' : ''}`} title="Align centre" onClick={() => up(x => { x.layout.align = 'center'; x.layout.anchorX = 0.5 })}>↔</button>
      <span className="sep" />
      <button className="tb text" disabled={!card} title="Retype this caption (Enter)" onClick={() => card && s.set({ editCard: idxOf(s.words, card)[0] })}>Edit text</button>
      <button className="tb text" disabled={!card || card.words.length < 2} title="Split this caption in two" onClick={() => card && s.setWords(ws => splitCard(ws, card))}>Split</button>
      <button className="tb text danger" disabled={!card} title="Remove this caption, keep the video (Delete)" onClick={() => { if (card) { s.setWords(ws => hideCard(ws, card)); s.set({ capSel: false }) } }}>Delete</button>
    </div>
  )
}
