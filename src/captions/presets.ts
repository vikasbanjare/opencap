import type { CaptionStyle } from './types'

// Defaults = the modal values measured across 45 Captions.ai 9:16 previews
// (band centre 67 %, blur-pop 125 ms, inactive 40 %, 2-word chunks).
const base: CaptionStyle = {
  id: 'base', name: 'Base', tags: [],
  font: { family: 'Inter', weight: 800, italic: false, size: 64, case: 'sentence', letterSpacing: 0 },
  layout: { anchorY: 0.67, anchorX: 0.5, maxWidth: 0.8, lineHeight: 1.15, align: 'center' },
  reveal: { mode: 'whole', inactiveOpacity: 0.4, wordMs: 100, hollowInactive: false },
  entrance: { durationMs: 125, blurPx: 6, scaleFrom: 1.1, ease: 'easeOut', riseP: 0 },
  exit: { mode: 'cut', ms: 80 },
  emphasis: { mode: 'auto', color: null, weightDelta: 0, italic: false, sizeRatio: 1, glowPx: 0, underline: false, box: null },
  colors: { text: '#FFFFFF', stroke: '#000000', shadow: '#000000' },
  stroke: 2,
  shadow: { blur: 8, opacity: 0.4, offsetY: 2 },
  box: { mode: 'none', fill: '#F2F2F2', radius: 999, padX: 0.5, padY: 0.3, outline: 0, outlineColor: '#000' },
  chunk: { maxWords: 2, maxChars: 18, gapBreak: 0.6 },
}

type Deep = { [K in keyof CaptionStyle]?: CaptionStyle[K] extends object ? Partial<CaptionStyle[K]> : CaptionStyle[K] }
const mk = (p: { id: string; name: string; tags: string[] }, deep: Deep = {}): CaptionStyle => {
  const s: CaptionStyle = JSON.parse(JSON.stringify({ ...base, ...p }))
  for (const k of Object.keys(deep) as (keyof CaptionStyle)[]) {
    const v = deep[k]
    ;(s as unknown as Record<string, unknown>)[k] = v !== null && typeof v === 'object' ? { ...(base[k] as object), ...(v as object) } : v
  }
  return s
}

export const PRESETS: CaptionStyle[] = [
  // --- Lectec SOP (the user's channel style) ---
  mk({ id: 'lectec', name: 'Lectec SOP', tags: ['Bold', 'Brand'] }, {
    font: { family: 'Anton', weight: 400, size: 96, case: 'lower' },
    layout: { anchorY: 0.80 },
    colors: { text: '#FFCE00', stroke: '#000000' }, stroke: 6,
    shadow: { blur: 12, opacity: 0.6, offsetY: 3 },
    emphasis: { mode: 'auto', color: '#1BFF00', weightDelta: 0, sizeRatio: 1.0 },
    chunk: { maxWords: 3, maxChars: 22 },
  }),
  // --- Bold karaoke (Pulse / Performance) ---
  mk({ id: 'pulse', name: 'Pulse', tags: ['Bold', 'Trending'] }, {
    font: { family: 'Oswald', weight: 700, size: 76, case: 'upper' },
    reveal: { mode: 'lineStack' },
    emphasis: { mode: 'auto', color: '#19C6FF', glowPx: 8 },
    chunk: { maxWords: 4, maxChars: 20 },
  }),
  mk({ id: 'performance', name: 'Performance', tags: ['Bold', 'Motivation'] }, {
    font: { family: 'Montserrat', weight: 800, size: 60, case: 'upper' },
    reveal: { mode: 'lineStack' },
    entrance: { durationMs: 130, blurPx: 8, scaleFrom: 1.0 },
    emphasis: { mode: 'auto', color: '#EEFF00', sizeRatio: 1.6, glowPx: 8 },
    chunk: { maxWords: 4, maxChars: 22 },
  }),
  // --- Impact: blur-pop, alternating colour ---
  mk({ id: 'impact', name: 'Impact', tags: ['Bold', 'Business'] }, {
    font: { family: 'Bebas Neue', weight: 400, size: 88, case: 'upper', letterSpacing: 1 },
    entrance: { durationMs: 125, blurPx: 6, scaleFrom: 1.15 },
    emphasis: { mode: 'auto', color: '#35D0FF', sizeRatio: 1.0 },
    chunk: { maxWords: 2, maxChars: 16 },
  }),
  // --- Prime: word-fill soft fade ---
  mk({ id: 'prime', name: 'Prime', tags: ['Minimal', 'Business'] }, {
    font: { family: 'Inter', weight: 900, size: 64, case: 'sentence' },
    layout: { anchorY: 0.72 },
    reveal: { mode: 'wordFill', inactiveOpacity: 0.35, wordMs: 100 },
    entrance: { durationMs: 100, blurPx: 0, scaleFrom: 1.0 },
    emphasis: { mode: 'none' }, stroke: 1,
    chunk: { maxWords: 3, maxChars: 20 },
  }),
  // --- Paper: word-fill inside a white pill ---
  mk({ id: 'paper', name: 'Paper', tags: ['Minimal', 'Educational'] }, {
    font: { family: 'Poppins', weight: 600, size: 52, case: 'sentence' },
    layout: { anchorY: 0.75 },
    reveal: { mode: 'wordFill', inactiveOpacity: 0.45, wordMs: 80 },
    entrance: { durationMs: 80, blurPx: 2, scaleFrom: 1.0 },
    emphasis: { mode: 'none' },
    colors: { text: '#1A1A1A', stroke: '#000000' }, stroke: 0,
    shadow: { blur: 10, opacity: 0.2, offsetY: 4 },
    box: { mode: 'pill', fill: '#F2F2F2', radius: 999, padX: 0.5, padY: 0.3 },
    chunk: { maxWords: 4, maxChars: 24 },
  }),
  // --- Pop: lowercase pill with black outline, easeOutBack ---
  mk({ id: 'pop', name: 'Pop', tags: ['Entertainment', 'Trending'] }, {
    font: { family: 'Nunito', weight: 700, size: 46, case: 'lower' },
    layout: { anchorY: 0.78 },
    entrance: { durationMs: 150, blurPx: 0, scaleFrom: 0.8, ease: 'easeOutBack' },
    emphasis: { mode: 'auto', weightDelta: 200, italic: false },
    colors: { text: '#111111', stroke: '#000000' }, stroke: 0,
    shadow: { blur: 0, opacity: 0.0, offsetY: 0 },
    box: { mode: 'pill', fill: '#FFFFFF', radius: 999, padX: 0.6, padY: 0.3, outline: 3, outlineColor: '#000000' },
    chunk: { maxWords: 3, maxChars: 20 },
  }),
  // --- Grit: pre-sized accent bar, words append left-aligned ---
  mk({ id: 'grit', name: 'Grit', tags: ['Bold', 'Motivation'] }, {
    font: { family: 'Inter', weight: 800, size: 44, case: 'upper' },
    layout: { anchorY: 0.68, anchorX: 0.06, maxWidth: 0.7, align: 'left' },
    reveal: { mode: 'append', inactiveOpacity: 0 },
    entrance: { durationMs: 60, blurPx: 6, scaleFrom: 1.0 },
    emphasis: { mode: 'none' },
    colors: { text: '#0A0A0A', stroke: '#000000' }, stroke: 0,
    shadow: { blur: 0, opacity: 0, offsetY: 0 },
    box: { mode: 'bar', fill: '#5CE6A5', radius: 0, padX: 0.4, padY: 0.25 },
    chunk: { maxWords: 4, maxChars: 24 },
  }),
  // --- Focus: moving white box on the active word ---
  mk({ id: 'focus', name: 'Focus', tags: ['Business', 'Minimal'] }, {
    font: { family: 'Inter', weight: 600, size: 44, case: 'lower' },
    layout: { anchorY: 0.70 },
    reveal: { mode: 'wordFill', inactiveOpacity: 0.6, wordMs: 0 },
    entrance: { durationMs: 100, blurPx: 0, scaleFrom: 1.0 },
    emphasis: { mode: 'none' },
    stroke: 0, shadow: { blur: 6, opacity: 0.5, offsetY: 1 },
    chunk: { maxWords: 3, maxChars: 22 },
  }),
  // --- Lift: mint pill jumps word to word ---
  mk({ id: 'lift', name: 'Lift', tags: ['Business', 'Trending'] }, {
    font: { family: 'Inter', weight: 600, size: 48, case: 'lower' },
    layout: { anchorY: 0.74 },
    reveal: { mode: 'wordFill', inactiveOpacity: 0.6, wordMs: 0 },
    entrance: { durationMs: 100, blurPx: 0, scaleFrom: 1.0 },
    emphasis: { mode: 'none' }, stroke: 0,
    chunk: { maxWords: 4, maxChars: 24 },
  }),
  // --- Archive: hollow inactive words ---
  mk({ id: 'archive', name: 'Archive', tags: ['Minimal'] }, {
    font: { family: 'Oswald', weight: 700, size: 70, case: 'upper' },
    layout: { anchorY: 0.64 },
    reveal: { mode: 'wordFill', inactiveOpacity: 1, wordMs: 80, hollowInactive: true },
    entrance: { durationMs: 80, blurPx: 0, scaleFrom: 1.0 },
    emphasis: { mode: 'none' }, stroke: 0,
    chunk: { maxWords: 3, maxChars: 18 },
  }),
  // --- Volt: lime bold italic keyword ---
  mk({ id: 'volt', name: 'Volt', tags: ['Bold', 'Business'] }, {
    font: { family: 'Poppins', weight: 500, size: 56, case: 'sentence' },
    layout: { anchorY: 0.70 },
    entrance: { durationMs: 130, blurPx: 6, scaleFrom: 1.0 },
    emphasis: { mode: 'auto', color: '#B8FF2E', weightDelta: 300, italic: true, sizeRatio: 1.3 },
    stroke: 1,
    chunk: { maxWords: 3, maxChars: 22 },
  }),
  // --- Velocity: yellow keyword, heavy italic ---
  mk({ id: 'velocity', name: 'Velocity', tags: ['Bold', 'Business'] }, {
    font: { family: 'Inter', weight: 900, italic: true, size: 56, case: 'upper' },
    layout: { anchorY: 0.72 },
    reveal: { mode: 'append', inactiveOpacity: 0 },
    entrance: { durationMs: 40, blurPx: 0, scaleFrom: 1.0 },
    emphasis: { mode: 'auto', color: '#FFE500' },
    chunk: { maxWords: 3, maxChars: 20 },
  }),
  // --- Elevate: light serif, italic emphasis, fade in/out ---
  mk({ id: 'elevate', name: 'Elevate', tags: ['Minimal', 'Lifestyle'] }, {
    font: { family: 'Playfair Display', weight: 400, size: 56, case: 'sentence' },
    layout: { anchorY: 0.70 },
    entrance: { durationMs: 120, blurPx: 4, scaleFrom: 1.0 },
    exit: { mode: 'fade', ms: 80 },
    emphasis: { mode: 'auto', italic: true },
    stroke: 0, shadow: { blur: 10, opacity: 0.35, offsetY: 2 },
    chunk: { maxWords: 4, maxChars: 26 },
  }),
  // --- Sonnet: serif word-by-word fade ---
  mk({ id: 'sonnet', name: 'Sonnet', tags: ['Minimal', 'Motivation'] }, {
    font: { family: 'EB Garamond', weight: 500, size: 56, case: 'sentence' },
    layout: { anchorY: 0.82 },
    reveal: { mode: 'append', inactiveOpacity: 0, wordMs: 130 },
    entrance: { durationMs: 130, blurPx: 0, scaleFrom: 1.0 },
    emphasis: { mode: 'auto', italic: true },
    stroke: 0, shadow: { blur: 10, opacity: 0.4, offsetY: 2 },
    chunk: { maxWords: 4, maxChars: 28 },
  }),
  // --- Chalk: handwritten, yellow keyword, dark line pill ---
  mk({ id: 'chalk', name: 'Chalk', tags: ['Educational'] }, {
    font: { family: 'Caveat', weight: 700, size: 64, case: 'sentence' },
    layout: { anchorY: 0.73 },
    reveal: { mode: 'append', inactiveOpacity: 0, wordMs: 80 },
    entrance: { durationMs: 80, blurPx: 0, scaleFrom: 1.0 },
    emphasis: { mode: 'auto', color: '#FFD400', sizeRatio: 1.4 },
    stroke: 0, shadow: { blur: 0, opacity: 0, offsetY: 0 },
    box: { mode: 'linePill', fill: 'rgba(34,34,34,0.85)', radius: 8, padX: 0.4, padY: 0.2 },
    chunk: { maxWords: 4, maxChars: 24 },
  }),
  // --- Cinematic: yellow serif, instant ---
  mk({ id: 'cinematic', name: 'Cinematic', tags: ['Entertainment'] }, {
    font: { family: 'Playfair Display', weight: 700, size: 50, case: 'sentence' },
    layout: { anchorY: 0.80 },
    entrance: { durationMs: 0, blurPx: 0, scaleFrom: 1.0 },
    emphasis: { mode: 'none' },
    colors: { text: '#F4C542', stroke: '#000000' }, stroke: 1,
    chunk: { maxWords: 3, maxChars: 22 },
  }),
  // --- Lens: monospace in a black bar ---
  mk({ id: 'lens', name: 'Lens', tags: ['Entertainment', 'Lifestyle'] }, {
    font: { family: 'Space Mono', weight: 700, size: 38, case: 'upper' },
    layout: { anchorY: 0.70, anchorX: 0.08, maxWidth: 0.7, align: 'left' },
    reveal: { mode: 'append', inactiveOpacity: 0 },
    entrance: { durationMs: 40, blurPx: 0, scaleFrom: 1.0 },
    emphasis: { mode: 'none' }, stroke: 0, shadow: { blur: 0, opacity: 0, offsetY: 0 },
    box: { mode: 'bar', fill: '#0A0A0A', radius: 0, padX: 0.5, padY: 0.3 },
    chunk: { maxWords: 4, maxChars: 24 },
  }),
  // --- Core: regular white, red keyword ---
  mk({ id: 'core', name: 'Core', tags: ['Educational', 'Minimal'] }, {
    font: { family: 'Inter', weight: 500, size: 50, case: 'sentence' },
    layout: { anchorY: 0.69 },
    reveal: { mode: 'append', inactiveOpacity: 0 },
    entrance: { durationMs: 60, blurPx: 0, scaleFrom: 1.0 },
    emphasis: { mode: 'auto', color: '#E8302A', weightDelta: 200 },
    stroke: 0, shadow: { blur: 8, opacity: 0.5, offsetY: 1 },
    chunk: { maxWords: 4, maxChars: 26 },
  }),
]

// Moving highlight boxes are attached after construction so the base stays box-free.
PRESETS.find(p => p.id === 'focus')!.emphasis.box = { fill: '#FFFFFF', radius: 6, padX: 0.3, padY: 0.12 }
PRESETS.find(p => p.id === 'focus')!.colors.text = '#FFFFFF'
PRESETS.find(p => p.id === 'lift')!.emphasis.box = { fill: '#5FD39A', radius: 10, padX: 0.3, padY: 0.12 }

export const GOOGLE_FONTS = ['Inter:wght@400;500;600;700;800;900', 'Oswald:wght@500;700', 'Montserrat:wght@600;800;900',
  'Bebas Neue', 'Poppins:wght@500;600;700', 'Nunito:wght@600;700;800', 'Playfair Display:ital,wght@0,400;0,700;1,400',
  'EB Garamond:ital,wght@0,500;1,500', 'Caveat:wght@700', 'Space Mono:wght@700', 'Anton']

export const presetById = (id: string) => PRESETS.find(p => p.id === id) ?? PRESETS[0]
