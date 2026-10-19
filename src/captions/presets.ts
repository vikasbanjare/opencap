import type { Anim, CaptionStyle } from './types'
import { DEFAULT_ANIM } from './engine'

// Defaults = the modal values measured across 45 Captions.ai 9:16 previews
// (band centre 67 %, blur-pop 125 ms, inactive 40 %, 2-word chunks).
const base: CaptionStyle = {
  id: 'base', name: 'Base', tags: [],
  font: { family: 'Inter', weight: 800, italic: false, size: 64, case: 'sentence', letterSpacing: 0 },
  layout: { anchorY: 0.67, anchorX: 0.5, maxWidth: 0.8, lineHeight: 1.15, align: 'center' },
  reveal: { mode: 'whole', inactiveOpacity: 0.4, wordMs: 100, hollowInactive: false },
  entrance: { durationMs: 125, blurPx: 6, scaleFrom: 1.1, ease: 'easeOut', riseP: 0 },
  exit: { mode: 'cut', ms: 80 },
  anim: DEFAULT_ANIM,
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
  // ===== Premium styles from captions-ai-research/caption-motion-patterns.md (Parts 1 and 3) =====
  // ponytail: scene accents (collages, B-roll frames, type-on titles) are out of scope; only the caption band is encoded.
  mk({ id: 'prism-pro', name: 'Prism Pro', tags: ['Business', 'New'] }, {
    font: { family: 'Inter', weight: 400, size: 44, case: 'sentence' },
    layout: { anchorY: 0.08, anchorX: 0.06, maxWidth: 0.8, align: 'left' },
    reveal: { mode: 'append', inactiveOpacity: 0, wordMs: 80 },
    entrance: { durationMs: 125, blurPx: 0, scaleFrom: 1.04 },
    emphasis: { mode: 'auto', color: '#F5D27A', weightDelta: 300, italic: true, sizeRatio: 1.6 },
    stroke: 0, shadow: { blur: 8, opacity: 0.15, offsetY: 2 },
    chunk: { maxWords: 3, maxChars: 22 },
  }),
  mk({ id: 'paper-ii', name: 'Paper II', tags: ['Trending', 'Polished', 'Educational', 'Lifestyle'] }, {
    font: { family: 'Poppins', weight: 600, size: 48, case: 'sentence' },
    layout: { anchorY: 0.75 },
    reveal: { mode: 'wordFill', inactiveOpacity: 0.45, wordMs: 80 },
    entrance: { durationMs: 80, blurPx: 2, scaleFrom: 1.0 },
    emphasis: { mode: 'none' },
    colors: { text: '#1A1A1A', stroke: '#000000' }, stroke: 0,
    shadow: { blur: 8, opacity: 0.2, offsetY: 3 },
    box: { mode: 'pill', fill: 'rgba(242,242,242,0.92)', radius: 999, padX: 0.5, padY: 0.3 },
    chunk: { maxWords: 3, maxChars: 22 },
  }),
  mk({ id: 'impact-ii', name: 'Impact II', tags: ['Trending', 'Bold', 'Business'] }, {
    font: { family: 'Bebas Neue', weight: 400, size: 84, case: 'upper', letterSpacing: 1 },
    layout: { anchorY: 0.70 },
    entrance: { durationMs: 125, blurPx: 6, scaleFrom: 1.15 },
    emphasis: { mode: 'auto', color: '#FFFFFF', sizeRatio: 1.6 },
    colors: { text: '#35D0FF', stroke: '#000000' }, stroke: 2,
    chunk: { maxWords: 2, maxChars: 16 },
  }),
  mk({ id: 'y2k', name: 'Y2K', tags: ['New', 'Trending', 'Bold', 'Entertainment'] }, {
    font: { family: 'Inter', weight: 400, size: 40, case: 'sentence' },
    layout: { anchorY: 0.28, anchorX: 0.08, maxWidth: 0.7, align: 'left' },
    reveal: { mode: 'append', inactiveOpacity: 0, wordMs: 0 },
    entrance: { durationMs: 0, blurPx: 0, scaleFrom: 1.0 },
    emphasis: { mode: 'none' },
    colors: { text: '#E6FF00', stroke: '#000000' }, stroke: 0, shadow: { blur: 0, opacity: 0, offsetY: 0 },
    chunk: { maxWords: 4, maxChars: 24 },
  }),
  mk({ id: 'form', name: 'Form', tags: ['New', 'Trending', 'Bold', 'Motivation'] }, {
    font: { family: 'Inter', weight: 500, size: 46, case: 'sentence' },
    layout: { anchorY: 0.72 },
    entrance: { durationMs: 80, blurPx: 3, scaleFrom: 1.0 },
    emphasis: { mode: 'auto', weightDelta: 300, italic: true, sizeRatio: 1.3 },
    stroke: 0, shadow: { blur: 8, opacity: 0.3, offsetY: 2 },
    chunk: { maxWords: 3, maxChars: 22 },
  }),
  mk({ id: 'ember', name: 'Ember', tags: ['Trending', 'Motivation', 'Entertainment'] }, {
    font: { family: 'Inter', weight: 400, size: 50, case: 'sentence' },
    layout: { anchorY: 0.70 },
    entrance: { durationMs: 100, blurPx: 0, scaleFrom: 1.0 },
    emphasis: { mode: 'auto', color: '#E8403A', weightDelta: 200 },
    colors: { text: '#F2E6C8', stroke: '#000000' }, stroke: 0, shadow: { blur: 10, opacity: 0.4, offsetY: 2 },
    chunk: { maxWords: 2, maxChars: 14 },
  }),
  mk({ id: 'clarity', name: 'Clarity', tags: ['Minimal'] }, {
    font: { family: 'Inter', weight: 600, size: 44, case: 'sentence' },
    layout: { anchorY: 0.68 },
    reveal: { mode: 'lineStack' },
    entrance: { durationMs: 130, blurPx: 3, scaleFrom: 1.0 },
    exit: { mode: 'fade', ms: 100 },
    emphasis: { mode: 'auto', color: '#2F6BFF' },
    stroke: 1,
    chunk: { maxWords: 5, maxChars: 28 },
  }),
  mk({ id: 'ignite', name: 'Ignite', tags: ['Trending', 'Business', 'Motivation', 'New'] }, {
    font: { family: 'Inter', weight: 400, size: 44, case: 'sentence' },
    layout: { anchorY: 0.50 },
    reveal: { mode: 'append', inactiveOpacity: 0, wordMs: 100 },
    entrance: { durationMs: 100, blurPx: 4, scaleFrom: 1.0 },
    emphasis: { mode: 'auto', color: '#FF2A2A', weightDelta: 300 },
    stroke: 0, shadow: { blur: 8, opacity: 0.4, offsetY: 2 },
    chunk: { maxWords: 4, maxChars: 24 },
  }),
  mk({ id: 'recess', name: 'Recess', tags: ['Minimal', 'Motivation', 'Educational'] }, {
    font: { family: 'Inter', weight: 600, size: 44, case: 'sentence' },
    layout: { anchorY: 0.88 },
    entrance: { durationMs: 130, blurPx: 3, scaleFrom: 1.0 },
    exit: { mode: 'fade', ms: 100 },
    emphasis: { mode: 'none' }, stroke: 0,
    chunk: { maxWords: 4, maxChars: 26 },
  }),
  mk({ id: 'align', name: 'Align', tags: ['Minimal', 'Business'] }, {
    font: { family: 'Space Mono', weight: 700, size: 36, case: 'upper' },
    layout: { anchorY: 0.59 },
    reveal: { mode: 'append', inactiveOpacity: 0 },
    entrance: { durationMs: 67, blurPx: 0, scaleFrom: 1.0 },
    emphasis: { mode: 'none' },
    colors: { text: '#0A0A0A', stroke: '#000000' }, stroke: 0, shadow: { blur: 0, opacity: 0, offsetY: 0 },
    box: { mode: 'bar', fill: '#FFFFFF', radius: 0, padX: 0.5, padY: 0.3 },
    chunk: { maxWords: 3, maxChars: 20 },
  }),
  mk({ id: 'analog', name: 'Analog', tags: ['Lifestyle'] }, {
    font: { family: 'Nunito', weight: 800, size: 48, case: 'lower' },
    layout: { anchorY: 0.47 },
    reveal: { mode: 'append', inactiveOpacity: 0, wordMs: 100 },
    entrance: { durationMs: 100, blurPx: 0, scaleFrom: 1.0, riseP: 0.004 },
    emphasis: { mode: 'auto', sizeRatio: 1.3 },
    stroke: 0, shadow: { blur: 10, opacity: 0.35, offsetY: 2 },
    chunk: { maxWords: 3, maxChars: 20 },
  }),
  mk({ id: 'bloom', name: 'Bloom', tags: ['Lifestyle', 'Minimal'] }, {
    font: { family: 'Nunito', weight: 700, size: 40, case: 'lower' },
    layout: { anchorY: 0.67 },
    reveal: { mode: 'append', inactiveOpacity: 0 },
    entrance: { durationMs: 80, blurPx: 0, scaleFrom: 1.0 },
    emphasis: { mode: 'auto', sizeRatio: 1.4 },
    stroke: 0, shadow: { blur: 8, opacity: 0.3, offsetY: 2 },
    chunk: { maxWords: 3, maxChars: 20 },
  }),
  mk({ id: 'blueprint', name: 'Blueprint', tags: ['Business', 'Educational'] }, {
    font: { family: 'Inter', weight: 700, size: 46, case: 'upper' },
    layout: { anchorY: 0.69 },
    reveal: { mode: 'wordFill', inactiveOpacity: 0.5, wordMs: 130 },
    entrance: { durationMs: 80, blurPx: 0, scaleFrom: 1.0 },
    emphasis: { mode: 'auto', underline: true },
    stroke: 0,
    chunk: { maxWords: 3, maxChars: 20 },
  }),
  mk({ id: 'byline', name: 'Byline', tags: ['Minimal', 'Business'] }, {
    font: { family: 'Inter', weight: 500, size: 40, case: 'sentence' },
    layout: { anchorY: 0.65 },
    entrance: { durationMs: 100, blurPx: 0, scaleFrom: 1.0 },
    emphasis: { mode: 'auto', sizeRatio: 1.5 },
    stroke: 0, shadow: { blur: 8, opacity: 0.4, offsetY: 2 },
    chunk: { maxWords: 3, maxChars: 22 },
  }),
  mk({ id: 'cinematic-ii', name: 'Cinematic II', tags: ['Entertainment'] }, {
    font: { family: 'Playfair Display', weight: 400, size: 48, case: 'sentence' },
    layout: { anchorY: 0.73 },
    entrance: { durationMs: 0, blurPx: 0, scaleFrom: 1.0 },
    emphasis: { mode: 'none' },
    colors: { text: '#F4C542', stroke: '#000000' }, stroke: 1,
    chunk: { maxWords: 3, maxChars: 22 },
  }),
  mk({ id: 'evo', name: 'Evo', tags: ['Business', 'Bold'] }, {
    font: { family: 'Inter', weight: 500, size: 40, case: 'sentence' },
    layout: { anchorY: 0.12 },
    reveal: { mode: 'append', inactiveOpacity: 0, wordMs: 100 },
    entrance: { durationMs: 100, blurPx: 4, scaleFrom: 1.0 },
    emphasis: { mode: 'auto', weightDelta: 300, italic: true, sizeRatio: 1.3 },
    stroke: 0, shadow: { blur: 8, opacity: 0.3, offsetY: 2 },
    chunk: { maxWords: 4, maxChars: 24 },
  }),
  mk({ id: 'film', name: 'Film', tags: ['Entertainment', 'Lifestyle'] }, {
    font: { family: 'EB Garamond', weight: 500, size: 42, case: 'sentence' },
    layout: { anchorY: 0.67 },
    entrance: { durationMs: 0, blurPx: 0, scaleFrom: 1.0 },
    emphasis: { mode: 'none' },
    colors: { text: '#F4C542', stroke: '#000000' }, stroke: 0, shadow: { blur: 6, opacity: 0.5, offsetY: 1 },
    chunk: { maxWords: 3, maxChars: 22 },
  }),
  mk({ id: 'growth', name: 'Growth', tags: ['Business', 'Bold'] }, {
    font: { family: 'Inter', weight: 800, size: 52, case: 'upper' },
    layout: { anchorY: 0.50 },
    reveal: { mode: 'lineStack' },
    entrance: { durationMs: 80, blurPx: 0, scaleFrom: 1.0 },
    emphasis: { mode: 'auto', color: '#E8302A', sizeRatio: 1.6 },
    stroke: 0, shadow: { blur: 8, opacity: 0.4, offsetY: 2 },
    chunk: { maxWords: 4, maxChars: 22 },
  }),
  mk({ id: 'kai', name: 'Kai', tags: ['Lifestyle', 'Trending'] }, {
    font: { family: 'Nunito', weight: 700, size: 46, case: 'lower' },
    layout: { anchorY: 0.52 },
    reveal: { mode: 'wordFill', inactiveOpacity: 0.6, wordMs: 0 },
    entrance: { durationMs: 80, blurPx: 0, scaleFrom: 1.0 },
    emphasis: { mode: 'none' }, stroke: 0,
    chunk: { maxWords: 3, maxChars: 22 },
  }),
  mk({ id: 'linen', name: 'Linen', tags: ['Lifestyle', 'Minimal'] }, {
    font: { family: 'Playfair Display', weight: 400, italic: true, size: 44, case: 'sentence' },
    layout: { anchorY: 0.73 },
    entrance: { durationMs: 100, blurPx: 0, scaleFrom: 1.0 },
    exit: { mode: 'fade', ms: 100 },
    emphasis: { mode: 'none' },
    colors: { text: '#3A2A2A', stroke: '#000000' }, stroke: 0, shadow: { blur: 0, opacity: 0, offsetY: 0 },
    box: { mode: 'pill', fill: '#F3DDD0', radius: 4, padX: 0.5, padY: 0.3 },
    chunk: { maxWords: 4, maxChars: 26 },
  }),
  mk({ id: 'lumen', name: 'Lumen', tags: ['Business', 'Minimal'] }, {
    font: { family: 'Inter', weight: 600, size: 40, case: 'sentence' },
    layout: { anchorY: 0.68, anchorX: 0.06, maxWidth: 0.88, align: 'left' },
    reveal: { mode: 'append', inactiveOpacity: 0 },
    entrance: { durationMs: 60, blurPx: 6, scaleFrom: 1.0 },
    emphasis: { mode: 'none' },
    stroke: 0, shadow: { blur: 0, opacity: 0, offsetY: 0 },
    box: { mode: 'bar', fill: '#3D332E', radius: 0, padX: 0.5, padY: 0.3 },
    chunk: { maxWords: 4, maxChars: 26 },
  }),
  mk({ id: 'magazine', name: 'Magazine', tags: ['Lifestyle', 'Entertainment'] }, {
    font: { family: 'Inter', weight: 600, size: 44, case: 'sentence' },
    layout: { anchorY: 0.48 },
    reveal: { mode: 'append', inactiveOpacity: 0, wordMs: 130 },
    entrance: { durationMs: 130, blurPx: 0, scaleFrom: 1.0 },
    emphasis: { mode: 'auto', color: '#B14CFF' },
    stroke: 0, shadow: { blur: 8, opacity: 0.4, offsetY: 2 },
    chunk: { maxWords: 3, maxChars: 22 },
  }),
  mk({ id: 'neon', name: 'Neon', tags: ['Entertainment', 'Bold'] }, {
    font: { family: 'Nunito', weight: 800, size: 46, case: 'sentence' },
    layout: { anchorY: 0.70 },
    reveal: { mode: 'append', inactiveOpacity: 0 },
    entrance: { durationMs: 80, blurPx: 0, scaleFrom: 1.0 },
    emphasis: { mode: 'auto', color: '#FF4FD8', glowPx: 10 },
    stroke: 0, shadow: { blur: 10, opacity: 0.4, offsetY: 2 },
    chunk: { maxWords: 4, maxChars: 24 },
  }),
  mk({ id: 'orbit', name: 'Orbit', tags: ['Lifestyle', 'Trending'] }, {
    font: { family: 'Playfair Display', weight: 400, italic: true, size: 44, case: 'sentence' },
    layout: { anchorY: 0.68 },
    entrance: { durationMs: 150, blurPx: 0, scaleFrom: 0.9, ease: 'easeOutBack' },
    emphasis: { mode: 'auto', italic: true, weightDelta: 300 },
    colors: { text: '#FFFFFF', stroke: '#000000' }, stroke: 0, shadow: { blur: 0, opacity: 0, offsetY: 0 },
    box: { mode: 'pill', fill: '#2F5BBF', radius: 999, padX: 0.6, padY: 0.3 },
    chunk: { maxWords: 3, maxChars: 22 },
  }),
  mk({ id: 'rebel', name: 'Rebel', tags: ['Bold', 'Entertainment'] }, {
    font: { family: 'Playfair Display', weight: 700, size: 46, case: 'upper' },
    layout: { anchorY: 0.64 },
    reveal: { mode: 'append', inactiveOpacity: 0 },
    entrance: { durationMs: 40, blurPx: 0, scaleFrom: 1.0 },
    emphasis: { mode: 'auto', color: '#FFE000' },
    colors: { text: '#FFFFFF', stroke: '#000000' }, stroke: 0, shadow: { blur: 0, opacity: 0, offsetY: 0 },
    box: { mode: 'bar', fill: '#0A0A0A', radius: 0, padX: 0.4, padY: 0.25 },
    chunk: { maxWords: 3, maxChars: 20 },
  }),
  mk({ id: 'rocket', name: 'Rocket', tags: ['Entertainment', 'Bold'] }, {
    font: { family: 'Oswald', weight: 700, size: 60, case: 'upper' },
    layout: { anchorY: 0.60 },
    reveal: { mode: 'wordFill', inactiveOpacity: 1, wordMs: 80 },
    entrance: { durationMs: 80, blurPx: 0, scaleFrom: 1.0 },
    emphasis: { mode: 'none' },
    colors: { text: '#FFFFFF', stroke: '#000000' }, stroke: 2,
    chunk: { maxWords: 3, maxChars: 18 },
  }),
  mk({ id: 'sketch', name: 'Sketch', tags: ['Educational', 'Lifestyle'] }, {
    font: { family: 'Permanent Marker', weight: 400, size: 48, case: 'sentence' },
    layout: { anchorY: 0.64 },
    reveal: { mode: 'append', inactiveOpacity: 0 },
    entrance: { durationMs: 60, blurPx: 0, scaleFrom: 1.0 },
    emphasis: { mode: 'none' },
    stroke: 0, shadow: { blur: 8, opacity: 0.4, offsetY: 2 },
    chunk: { maxWords: 3, maxChars: 20 },
  }),
  mk({ id: 'stack', name: 'Stack', tags: ['Business', 'Bold'] }, {
    font: { family: 'Nunito', weight: 700, size: 40, case: 'sentence' },
    layout: { anchorY: 0.67 },
    reveal: { mode: 'append', inactiveOpacity: 0 },
    entrance: { durationMs: 80, blurPx: 0, scaleFrom: 1.0 },
    emphasis: { mode: 'auto', sizeRatio: 1.3 },
    stroke: 0, shadow: { blur: 8, opacity: 0.3, offsetY: 2 },
    chunk: { maxWords: 3, maxChars: 20 },
  }),
  mk({ id: 'story', name: 'Story', tags: ['Lifestyle', 'Educational'] }, {
    font: { family: 'EB Garamond', weight: 500, size: 48, case: 'sentence' },
    layout: { anchorY: 0.54 },
    reveal: { mode: 'append', inactiveOpacity: 0 },
    entrance: { durationMs: 80, blurPx: 0, scaleFrom: 1.0 },
    emphasis: { mode: 'auto', color: '#FFD84A', italic: true },
    stroke: 0, shadow: { blur: 8, opacity: 0.4, offsetY: 2 },
    chunk: { maxWords: 4, maxChars: 26 },
  }),
  mk({ id: 'vinyl-ii', name: 'Vinyl II', tags: ['Lifestyle', 'Bold'] }, {
    font: { family: 'Inter', weight: 700, size: 42, case: 'sentence' },
    layout: { anchorY: 0.65 },
    reveal: { mode: 'append', inactiveOpacity: 0 },
    entrance: { durationMs: 60, blurPx: 0, scaleFrom: 1.0 },
    emphasis: { mode: 'auto', color: '#FF4A1C' },
    colors: { text: '#1A1A1A', stroke: '#000000' }, stroke: 0, shadow: { blur: 0, opacity: 0, offsetY: 0 },
    box: { mode: 'bar', fill: '#F3EBDD', radius: 0, padX: 0.5, padY: 0.3 },
    chunk: { maxWords: 4, maxChars: 24 },
  }),
  mk({ id: 'vista', name: 'Vista', tags: ['Business', 'Minimal'] }, {
    font: { family: 'EB Garamond', weight: 500, size: 42, case: 'sentence' },
    layout: { anchorY: 0.67 },
    reveal: { mode: 'append', inactiveOpacity: 0 },
    entrance: { durationMs: 80, blurPx: 0, scaleFrom: 1.0 },
    emphasis: { mode: 'none' },
    stroke: 0, shadow: { blur: 8, opacity: 0.4, offsetY: 2 },
    chunk: { maxWords: 4, maxChars: 26 },
  }),
  mk({ id: 'zine', name: 'Zine', tags: ['Entertainment', 'Educational'] }, {
    font: { family: 'Permanent Marker', weight: 400, italic: true, size: 44, case: 'upper' },
    layout: { anchorY: 0.62 },
    reveal: { mode: 'lineStack' },
    entrance: { durationMs: 60, blurPx: 0, scaleFrom: 1.0 },
    emphasis: { mode: 'none' },
    stroke: 0, shadow: { blur: 8, opacity: 0.4, offsetY: 2 },
    chunk: { maxWords: 4, maxChars: 22 },
  }),
  // ===== Viral: motion families common across caption tools (Submagic, CapCut, VEED, Captions) =====
  // ponytail: not measured from previews like the premium set; tuned by eye to be clearly distinct.
  mk({ id: 'hype', name: 'Hype', tags: ['Viral', 'Bold'] }, {
    font: { family: 'Montserrat', weight: 900, size: 80, case: 'upper' },
    emphasis: { mode: 'auto', color: '#39FF14' }, stroke: 7, shadow: { blur: 0, opacity: 0, offsetY: 0 },
    entrance: { durationMs: 0, blurPx: 0, scaleFrom: 1 },
    anim: { word: 'pop', stagger: 0, wordMs: 200, active: 'color', activeColor: '#FFE600' },
    chunk: { maxWords: 3, maxChars: 18 },
  }),
  mk({ id: 'beast', name: 'Beast', tags: ['Viral', 'Bold', 'Entertainment'] }, {
    font: { family: 'Luckiest Guy', weight: 400, size: 92, case: 'upper', letterSpacing: 1 },
    emphasis: { mode: 'auto', color: '#FF3B3B' }, stroke: 8, shadow: { blur: 0, opacity: 0, offsetY: 6 },
    entrance: { durationMs: 0, blurPx: 0, scaleFrom: 1 },
    anim: { word: 'bounce', stagger: 70, wordMs: 450, active: 'scale', activeScale: 1.18 },
    chunk: { maxWords: 2, maxChars: 14 },
  }),
  mk({ id: 'karaoke', name: 'Karaoke', tags: ['Viral', 'Trending'] }, {
    font: { family: 'Lilita One', weight: 400, size: 74, case: 'upper' },
    emphasis: { mode: 'none' }, stroke: 6, entrance: { durationMs: 120, blurPx: 0, scaleFrom: 0.9, ease: 'easeOutBack' },
    anim: { active: 'sweep', activeColor: '#00E5FF' },
    chunk: { maxWords: 4, maxChars: 22 },
  }),
  mk({ id: 'highlighter', name: 'Highlighter', tags: ['Viral', 'Business'] }, {
    font: { family: 'Archivo Black', weight: 400, size: 60, case: 'upper' },
    emphasis: { mode: 'none' }, stroke: 0, shadow: { blur: 12, opacity: 0.5, offsetY: 3 },
    anim: { active: 'marker', activeColor: '#FFE14D', word: 'slideUp', stagger: 40 },
    chunk: { maxWords: 3, maxChars: 20 },
  }),
  mk({ id: 'typewriter', name: 'Typewriter', tags: ['Viral', 'Minimal'] }, {
    font: { family: 'Space Mono', weight: 700, size: 46, case: 'as-is' },
    layout: { anchorX: 0.08, align: 'left', maxWidth: 0.84 },
    emphasis: { mode: 'auto', color: '#7CFFB2' }, stroke: 0, shadow: { blur: 10, opacity: 0.6, offsetY: 2 },
    entrance: { durationMs: 0, blurPx: 0, scaleFrom: 1 },
    anim: { word: 'typewriter', stagger: 140, wordMs: 260 },
    chunk: { maxWords: 5, maxChars: 30 },
  }),
  mk({ id: 'wave', name: 'Wave', tags: ['Viral', 'Lifestyle'] }, {
    font: { family: 'Fredoka', weight: 700, size: 66, case: 'lower' },
    reveal: { mode: 'wordFill', inactiveOpacity: 0.45, wordMs: 80 },
    emphasis: { mode: 'none' }, stroke: 4, colors: { text: '#FFFFFF', stroke: '#3B1D5A' },
    anim: { loop: 'wave', active: 'color', activeColor: '#FF7AD9' },
    chunk: { maxWords: 3, maxChars: 20 },
  }),
  mk({ id: 'comic', name: 'Comic', tags: ['Viral', 'Entertainment'] }, {
    font: { family: 'Bangers', weight: 400, size: 88, case: 'upper', letterSpacing: 2 },
    emphasis: { mode: 'auto', color: '#FFD600' }, stroke: 7, shadow: { blur: 0, opacity: 0.9, offsetY: 6 },
    entrance: { durationMs: 220, blurPx: 0, scaleFrom: 0.6, ease: 'easeOutBack' },
    anim: { word: 'spin', stagger: 60, wordMs: 320, loop: 'shake', rotateFrom: -8 },
    chunk: { maxWords: 3, maxChars: 18 },
  }),
  mk({ id: 'glow-up', name: 'Glow Up', tags: ['Viral', 'Trending'] }, {
    font: { family: 'Unbounded', weight: 700, size: 52, case: 'upper' },
    reveal: { mode: 'append', inactiveOpacity: 0 },
    emphasis: { mode: 'none' }, stroke: 0,
    anim: { word: 'zoom', wordMs: 220, active: 'glow', activeColor: '#C084FC' },
    chunk: { maxWords: 3, maxChars: 18 },
  }),
  mk({ id: 'slide-in', name: 'Slide In', tags: ['Viral', 'Business'] }, {
    font: { family: 'Kanit', weight: 800, italic: true, size: 66, case: 'upper' },
    emphasis: { mode: 'auto', color: '#00FFA3' }, stroke: 3,
    entrance: { durationMs: 260, blurPx: 4, scaleFrom: 1, ease: 'easeOut' },
    anim: { word: 'slideLeft', stagger: 70, wordMs: 260, slideX: -0.12 },
    chunk: { maxWords: 3, maxChars: 20 },
  }),
  mk({ id: 'elastic', name: 'Elastic', tags: ['Viral', 'Bold'] }, {
    font: { family: 'Rubik', weight: 900, size: 70, case: 'upper' },
    emphasis: { mode: 'auto', color: '#FF8A00' }, stroke: 5,
    entrance: { durationMs: 0, blurPx: 0, scaleFrom: 1 },
    anim: { word: 'stretch', stagger: 60, wordMs: 360, active: 'lift' },
    chunk: { maxWords: 3, maxChars: 18 },
  }),
  mk({ id: 'retro', name: 'Retro', tags: ['Viral', 'Lifestyle'] }, {
    font: { family: 'Righteous', weight: 400, size: 66, case: 'upper' },
    colors: { text: '#FFD7A8', stroke: '#6B2B00' }, stroke: 5, emphasis: { mode: 'auto', color: '#FF5E3A' },
    shadow: { blur: 0, opacity: 0.8, offsetY: 5 },
    anim: { word: 'drop', stagger: 80, wordMs: 380 },
    chunk: { maxWords: 3, maxChars: 20 },
  }),
  mk({ id: 'editorial', name: 'Editorial', tags: ['Viral', 'Minimal'] }, {
    font: { family: 'DM Serif Display', weight: 400, size: 62, case: 'sentence' },
    emphasis: { mode: 'auto', color: '#F5C66A', italic: true }, stroke: 0, shadow: { blur: 14, opacity: 0.5, offsetY: 2 },
    exit: { mode: 'fade', ms: 160 },
    anim: { word: 'blur', stagger: 110, wordMs: 380 },
    chunk: { maxWords: 4, maxChars: 26 },
  }),
  mk({ id: 'bubble', name: 'Bubble', tags: ['Viral', 'Entertainment'] }, {
    font: { family: 'Fredoka', weight: 700, size: 54, case: 'lower' },
    colors: { text: '#1B1B1B', stroke: '#000000' }, stroke: 0, emphasis: { mode: 'auto', color: '#FF4D8D' },
    box: { mode: 'pill', fill: '#FFFFFF', radius: 999, padX: 0.55, padY: 0.3 },
    entrance: { durationMs: 260, blurPx: 0, scaleFrom: 0.5, ease: 'easeOutBack' },
    anim: { active: 'scale', activeScale: 1.14 },
    chunk: { maxWords: 3, maxChars: 20 },
  }),
  mk({ id: 'flip', name: 'Flip', tags: ['Viral', 'Bold'] }, {
    font: { family: 'Unbounded', weight: 900, size: 54, case: 'upper' },
    emphasis: { mode: 'none' }, stroke: 4,
    entrance: { durationMs: 0, blurPx: 0, scaleFrom: 1 },
    anim: { word: 'flip', stagger: 55, wordMs: 300, active: 'color', activeColor: '#22D3EE' },
    chunk: { maxWords: 3, maxChars: 18 },
  }),
  mk({ id: 'scribble', name: 'Scribble', tags: ['Viral', 'Educational'] }, {
    font: { family: 'Permanent Marker', weight: 400, size: 66, case: 'sentence' },
    emphasis: { mode: 'auto', color: '#FF4D4D' }, stroke: 4,
    anim: { word: 'pop', stagger: 60, wordMs: 240, loop: 'jitter' },
    chunk: { maxWords: 3, maxChars: 20 },
  }),
  mk({ id: 'drift', name: 'Drift', tags: ['Viral', 'Lifestyle'] }, {
    font: { family: 'Rubik', weight: 700, size: 58, case: 'lower' },
    emphasis: { mode: 'auto', color: '#7CFFB2' }, stroke: 0, shadow: { blur: 14, opacity: 0.6, offsetY: 3 },
    reveal: { mode: 'append', inactiveOpacity: 0 },
    anim: { word: 'slideUp', wordMs: 300, loop: 'float', active: 'underline', activeColor: '#7CFFB2' },
    chunk: { maxWords: 4, maxChars: 24 },
  }),
]

// Motion per existing style. Research-backed where caption-motion-patterns.md describes it
// (Analog rise, Ignite/Evo blur-in, Film/Lens type-on, Blueprint underline, Magazine flash, Rocket lavender→white).
const MOTION: Record<string, Partial<Anim>> = {
  pulse: { word: 'blur', active: 'glow', activeColor: '#19C6FF' },
  performance: { word: 'zoom', wordMs: 200, active: 'color', activeColor: '#EEFF00' },
  impact: { loop: 'pulse' },
  prime: { active: 'lift' },
  paper: { active: 'scale', activeScale: 1.08 },
  pop: { word: 'pop', stagger: 70 },
  grit: { word: 'slideLeft' },
  lift: { word: 'slideUp' },
  archive: { active: 'scale', activeScale: 1.1 },
  volt: { word: 'stretch', stagger: 50 },
  velocity: { word: 'slideLeft', wordMs: 160 },
  elevate: { word: 'blur', stagger: 90, wordMs: 320 },
  sonnet: { word: 'slideUp', wordMs: 340 },
  chalk: { word: 'typewriter', wordMs: 200, loop: 'jitter' },
  cinematic: { word: 'blur', stagger: 0, wordMs: 420 },
  lens: { word: 'typewriter', wordMs: 220 },
  core: { word: 'slideUp' },
  'prism-pro': { word: 'drop', wordMs: 300 },
  'paper-ii': { active: 'scale', activeScale: 1.06 },
  'impact-ii': { word: 'zoom', stagger: 0, wordMs: 160 },
  y2k: { loop: 'float' },
  form: { word: 'slideUp', stagger: 50 },
  ember: { word: 'blur', stagger: 80, loop: 'float' },
  clarity: { word: 'slideUp' },
  ignite: { word: 'blur', active: 'color', activeColor: '#FF2A2A' },
  align: { word: 'typewriter', wordMs: 240 },
  analog: { word: 'slideUp', wordMs: 120 },
  bloom: { word: 'pop' },
  blueprint: { active: 'underline', activeColor: '#4DA3FF' },
  byline: { word: 'blur', stagger: 70 },
  'cinematic-ii': { word: 'flip', stagger: 40 },
  evo: { word: 'blur', wordMs: 160 },
  film: { word: 'typewriter', stagger: 160, wordMs: 260 },
  growth: { word: 'drop' },
  kai: { word: 'pop' },
  linen: { word: 'slideUp', stagger: 60 },
  magazine: { active: 'color', activeColor: '#B14CFF' },
  neon: { loop: 'pulse', active: 'glow', activeColor: '#FF4FD8' },
  rebel: { word: 'stretch', loop: 'jitter' },
  rocket: { active: 'color', activeColor: '#FFFFFF' },
  sketch: { word: 'typewriter', loop: 'jitter' },
  stack: { word: 'pop' },
  story: { word: 'blur', wordMs: 300 },
  'vinyl-ii': { word: 'slideUp' },
  vista: { word: 'blur', wordMs: 400 },
  zine: { word: 'pop', loop: 'jitter' },
}
for (const p of PRESETS) if (MOTION[p.id]) p.anim = { ...p.anim, ...MOTION[p.id] }
PRESETS.find(p => p.id === 'blueprint')!.emphasis.underline = false
PRESETS.find(p => p.id === 'rocket')!.colors.text = '#B9A8FF'

// Moving highlight boxes are attached after construction so the base stays box-free.
PRESETS.find(p => p.id === 'focus')!.emphasis.box = { fill: '#FFFFFF', radius: 6, padX: 0.3, padY: 0.12 }
PRESETS.find(p => p.id === 'focus')!.colors.text = '#FFFFFF'
PRESETS.find(p => p.id === 'lift')!.emphasis.box = { fill: '#5FD39A', radius: 10, padX: 0.3, padY: 0.12 }
PRESETS.find(p => p.id === 'kai')!.emphasis.box = { fill: '#3FC9B0', radius: 999, padX: 0.3, padY: 0.12 }

// ===== Basic presets: the 67 flat Captions.ai caption styles (captions-ai-research/caption-styles.json) =====
// Colour slots per research Part 4: 0 text, 1 active/keyword, 2 stroke or container.
// ponytail: the endpoint gives colours and timing only, not fonts or motion. Each preset gets one of these
// looks (stable per name) so no two neighbours look alike; colours, reveal and entrance speed are theirs.
import BASIC from './basic-styles.json'
type Look = { font: Partial<CaptionStyle['font']>; anim: Partial<Anim>; size: number }
const LOOKS: Look[] = [
  { font: { family: 'Montserrat', weight: 900, case: 'upper' }, anim: { word: 'pop', stagger: 50 }, size: 64 },
  { font: { family: 'Luckiest Guy', weight: 400, case: 'upper' }, anim: { word: 'bounce', wordMs: 420, active: 'scale' }, size: 70 },
  { font: { family: 'Lilita One', weight: 400, case: 'upper' }, anim: { active: 'sweep' }, size: 66 },
  { font: { family: 'Archivo Black', weight: 400, case: 'upper' }, anim: { active: 'marker' }, size: 56 },
  { font: { family: 'Fredoka', weight: 700, case: 'lower' }, anim: { loop: 'wave' }, size: 62 },
  { font: { family: 'Bangers', weight: 400, case: 'upper', letterSpacing: 2 }, anim: { word: 'spin', wordMs: 300 }, size: 76 },
  { font: { family: 'Kanit', weight: 800, italic: true, case: 'upper' }, anim: { word: 'slideLeft' }, size: 60 },
  { font: { family: 'Rubik', weight: 900, case: 'upper' }, anim: { word: 'stretch', wordMs: 340 }, size: 62 },
  { font: { family: 'Poppins', weight: 700, case: 'sentence' }, anim: { word: 'slideUp', active: 'lift' }, size: 58 },
  { font: { family: 'Unbounded', weight: 700, case: 'upper' }, anim: { word: 'zoom' }, size: 48 },
  { font: { family: 'DM Serif Display', weight: 400, case: 'sentence' }, anim: { word: 'blur', wordMs: 340 }, size: 60 },
  { font: { family: 'Righteous', weight: 400, case: 'upper' }, anim: { word: 'drop', wordMs: 360 }, size: 60 },
]
const lum = (hex: string) => { const n = parseInt(hex.slice(1, 7), 16); return (0.2126 * (n >> 16) + 0.7152 * ((n >> 8) & 255) + 0.0722 * (n & 255)) / 255 }
BASIC.forEach((b: { id: string; name: string; colors: string[]; reveal: string; entranceMs: number; tags: string[] }, i: number) => {
  const [c0, c1, c2] = b.colors
  const look = LOOKS[i % LOOKS.length]
  const dark2 = lum(c2) < 0.35
  const accent = c1.toUpperCase() !== c0.toUpperCase() ? c1 : null
  const anim: Partial<Anim> = { ...look.anim }
  if (anim.active === 'sweep' || anim.active === 'marker') anim.activeColor = accent ?? '#FFE600'
  else if (accent) { anim.active = anim.active === 'scale' || anim.active === 'lift' ? anim.active : 'color'; anim.activeColor = accent }
  PRESETS.push(mk({ id: b.id, name: b.name, tags: ['Basic', ...b.tags] }, {
    font: { ...look.font, size: look.size },
    layout: { anchorY: 0.72 },
    reveal: b.reveal === 'word' ? { mode: 'wordFill', inactiveOpacity: 0.4, wordMs: 80 } : { mode: 'whole' },
    entrance: b.entranceMs >= 400 ? { durationMs: 350, blurPx: 0, scaleFrom: 0.7, ease: 'easeOutBack' } : { durationMs: Math.max(40, b.entranceMs), blurPx: 0, scaleFrom: 1.0 },
    emphasis: accent ? { mode: 'auto', color: accent } : { mode: 'none' },
    colors: { text: c0, stroke: dark2 ? c2 : '#000000', shadow: dark2 ? c2 : '#000000' },
    stroke: dark2 ? 4 : 2,
    anim,
    chunk: { maxWords: 3, maxChars: 20 },
  }))
})

// ===== VEED and Kapwing presets (captions-ai-research/veed-kapwing-styles.json) =====
// Researched specs mapped onto the renderer; styles that duplicate an existing Pulse look are left out (skip: true).
import EXTRA from './veed-kapwing-styles.json'
type Spec = { name: string; skip?: boolean; font: string; weight: number; italic: boolean; case: CaptionStyle['font']['case']; text: string; stroke: string | null; strokePx: number
  shadow: 'none' | 'soft' | 'hard'; box: 'none' | 'pill' | 'bar' | 'line'; boxFill: string | null; position: 'top' | 'center' | 'bottom'; reveal: CaptionStyle['reveal']['mode']
  wordsPerCard: number; highlight: string; highlightColor: string | null; wordIn: string }
const slug = (n: string) => n.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
for (const [src, list] of [['VEED', (EXTRA as { veed: Spec[] }).veed], ['Kapwing', (EXTRA as { kapwing: Spec[] }).kapwing]] as const) {
  for (const x of list) {
    if (x.skip) continue
    const hot = x.highlightColor ?? '#FFE600'
    const anim: Partial<Anim> = { word: x.wordIn === 'fade' ? 'none' : (x.wordIn as Anim['word']) ?? 'none', stagger: 60 }
    if (['color', 'scale', 'sweep', 'glow', 'underline'].includes(x.highlight)) { anim.active = x.highlight as Anim['active']; anim.activeColor = hot }
    PRESETS.push(mk({ id: `${src.toLowerCase()}-${slug(x.name)}`, name: x.name, tags: [src] }, {
      font: { family: x.font, weight: x.weight, italic: x.italic, case: x.case, size: x.wordsPerCard <= 2 ? 76 : x.wordsPerCard === 3 ? 64 : 52 },
      layout: { anchorY: x.position === 'top' ? 0.2 : x.position === 'center' ? 0.5 : 0.78 },
      reveal: { mode: x.reveal, inactiveOpacity: x.reveal === 'wordFill' ? 0.45 : 0.4, wordMs: 90 },
      entrance: x.wordIn === 'fade' ? { durationMs: 140, blurPx: 0, scaleFrom: 1 } : { durationMs: 0, blurPx: 0, scaleFrom: 1 },
      emphasis: x.highlight === 'box' ? { mode: 'none', box: { fill: hot, radius: 10, padX: 0.25, padY: 0.1 } } : { mode: 'none' },
      colors: { text: x.text, stroke: x.stroke ?? '#000000', shadow: '#000000' },
      stroke: x.stroke ? x.strokePx : 0,
      shadow: x.shadow === 'none' ? { blur: 0, opacity: 0, offsetY: 0 } : x.shadow === 'hard' ? { blur: 0, opacity: 0.9, offsetY: 5 } : { blur: 12, opacity: 0.5, offsetY: 2 },
      box: x.box === 'none' ? { mode: 'none' } : { mode: x.box === 'line' ? 'linePill' : x.box, fill: x.boxFill ?? '#000000', radius: x.box === 'pill' ? 14 : 4, padX: 0.4, padY: 0.2 },
      anim,
      chunk: { maxWords: x.wordsPerCard, maxChars: x.wordsPerCard * 8 + 4 },
    }))
  }
}

export const GOOGLE_FONTS = ['Inter:wght@400;500;600;700;800;900', 'Oswald:wght@500;700', 'Montserrat:wght@600;800;900',
  'Bebas Neue', 'Poppins:wght@500;600;700', 'Nunito:wght@600;700;800', 'Playfair Display:ital,wght@0,400;0,700;1,400',
  'EB Garamond:ital,wght@0,500;1,500', 'Caveat:wght@700', 'Space Mono:wght@700', 'Anton', 'Permanent Marker', 'Bangers', 'Luckiest Guy', 'Archivo Black', 'Lilita One', 'Righteous', 'Fredoka:wght@600;700', 'DM Serif Display', 'Unbounded:wght@700;900', 'Kanit:ital,wght@1,800', 'Rubik:wght@700;900', 'Archivo:wght@800', 'Arimo:ital,wght@0,400;0,700;1,700', 'Baloo 2:wght@800', 'Bowlby One', 'Coda:wght@800', 'Comic Neue:ital,wght@1,700', 'Courier Prime:wght@700', 'Creepster', 'Dancing Script:wght@700', 'Fira Sans:wght@600', 'Inconsolata:wght@500', 'Kalam:wght@400', 'Monoton', 'Pixelify Sans:wght@600', 'Source Code Pro:wght@500', 'Source Sans 3:wght@600', 'Tilt Neon']

export const ALL_TAGS = [...new Set(PRESETS.flatMap(p => p.tags))].sort()
export const presetById = (id: string) => PRESETS.find(p => p.id === id) ?? PRESETS[0]
