// Caption data model + style schema. Style fields map 1:1 onto the patterns in
// captions-ai-research/caption-motion-patterns.md (A placement, B word-fill, C blur-pop,
// D emphasis, E boxes, F parked title, G accents).

export type Word = {
  text: string; start: number; end: number; p?: number
  deleted?: boolean   // removed from the video (text-based cut)
  emph?: boolean      // keyword of its caption
  brk?: boolean       // a new caption starts at this word
  glue?: boolean      // never start a new caption here (merged captions)
  hide?: boolean      // keep the video, show no caption for this word
  color?: string      // per-word colour override
  cardEnd?: number    // on the last word of a caption: when that caption leaves the screen
  added?: boolean     // typed in by the user, not spoken
}

export type Card = {
  id: string
  words: Word[]        // in order, deleted words already removed
  start: number        // seconds, source time
  end: number
  lines: Word[][]      // layout lines
  emphIndex: number    // index into words, -1 = none
}

export type Ease = 'linear' | 'easeOut' | 'easeOutBack' | 'easeInOut'
export type TextCase = 'upper' | 'lower' | 'sentence' | 'as-is'
export type RevealMode = 'whole' | 'wordFill' | 'append' | 'lineStack'
export type BoxMode = 'none' | 'pill' | 'bar' | 'linePill'
/** How each word enters (whole mode: staggered from the card start; other modes: when the word is spoken). */
export type WordIn = 'none' | 'pop' | 'bounce' | 'slideUp' | 'drop' | 'slideLeft' | 'zoom' | 'blur' | 'typewriter' | 'flip' | 'stretch' | 'spin'
/** What happens to the word being spoken right now. */
export type ActiveFx = 'none' | 'color' | 'scale' | 'lift' | 'glow' | 'sweep' | 'marker' | 'underline'
/** Continuous motion while the card is on screen (shake and pulse act on the keyword only). */
export type LoopFx = 'none' | 'wave' | 'shake' | 'pulse' | 'float' | 'jitter'
export type Anim = {
  word: WordIn; wordMs: number; stagger: number
  active: ActiveFx; activeColor: string | null; activeScale: number
  loop: LoopFx
  slideX: number      // card slides in from this fraction of frame width
  rotateFrom: number  // card rotates in from this many degrees
}

export type CaptionStyle = {
  id: string
  name: string
  tags: string[]
  font: { family: string; weight: number; italic: boolean; size: number; case: TextCase; letterSpacing: number }
  layout: { anchorY: number; anchorX: number; maxWidth: number; lineHeight: number; align: 'left' | 'center' }
  reveal: { mode: RevealMode; inactiveOpacity: number; wordMs: number; hollowInactive: boolean }
  entrance: { durationMs: number; blurPx: number; scaleFrom: number; ease: Ease; riseP: number }
  exit: { mode: 'cut' | 'fade'; ms: number }
  anim: Anim
  emphasis: {
    mode: 'auto' | 'none'
    color: string | null       // null = keep text colour
    weightDelta: number        // +300 = bold
    italic: boolean
    sizeRatio: number
    glowPx: number
    underline: boolean
    box: { fill: string; radius: number; padX: number; padY: number } | null   // moving highlight box (Focus/Lift/Kai)
  }
  colors: { text: string; stroke: string; shadow: string }
  stroke: number
  shadow: { blur: number; opacity: number; offsetY: number }
  box: { mode: BoxMode; fill: string; radius: number; padX: number; padY: number; outline: number; outlineColor: string }
  chunk: { maxWords: number; maxChars: number; gapBreak: number }
}

export type Cut = { start: number; end: number }

export type ZoomKey = { time: number; scale: number; durationMs: number } // punch-in at a card start

export type Overlay = {
  id: string
  kind: 'text' | 'emoji' | 'image' | 'video'
  text?: string
  src?: string
  fit?: 'cover' | 'pip'         // video: full-frame B-roll or picture-in-picture
  srcDuration?: number
  muted?: boolean
  x: number; y: number          // 0..1 of frame
  w?: number                    // 0..1 of frame width (image / pip)
  size: number                  // px at 1080 width
  color: string
  font: string
  start: number; end: number
}

export type Music = { url: string; name: string; gainDb: number; duck: boolean; duckDb: number; start: number }
