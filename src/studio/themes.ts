// Studio themes. Every colour in studio.css comes from these tokens, so a new look is one entry here.
// The tokens override the app-wide ones (--surface, --fg, …) inside .studio, so shared buttons and inputs follow too.

export type Theme = {
  id: string; name: string; dark: boolean
  bg: string; surface: string; surface2: string; surface3: string; line: string; line2: string
  fg: string; muted: string; dim: string
  accent: string; accentInk: string; accent2: string
  display: string // heading font (loaded in index.html)
}

export const THEMES: Theme[] = [
  { id: 'midnight', name: 'Midnight Studio', dark: true, bg: '#07070d', surface: '#111119', surface2: '#181823', surface3: '#21212f', line: '#24243a', line2: '#32324c',
    fg: '#f3f3f8', muted: '#a0a0b8', dim: '#6c6c86', accent: '#c6f24e', accentInk: '#121707', accent2: '#8b6cff', display: "'Space Grotesk', Inter, sans-serif" },
  { id: 'cinema', name: 'Cinema Gold', dark: true, bg: '#0a0806', surface: '#14100c', surface2: '#1c1711', surface3: '#272017', line: '#2f271c', line2: '#40352a',
    fg: '#f7f1e8', muted: '#b9ab98', dim: '#7d705f', accent: '#f4b43f', accentInk: '#1d1302', accent2: '#ff6a3d', display: "'DM Serif Display', Georgia, serif" },
  { id: 'neon', name: 'Neon Noir', dark: true, bg: '#06060f', surface: '#0f0f1e', surface2: '#161629', surface3: '#1f1f38', line: '#25254a', line2: '#34345f',
    fg: '#f4f2ff', muted: '#a6a3c9', dim: '#6d6a94', accent: '#ff3d9a', accentInk: '#ffffff', accent2: '#22d3ee', display: "'Unbounded', Inter, sans-serif" },
  { id: 'ocean', name: 'Deep Ocean', dark: true, bg: '#04111a', surface: '#0a1b26', surface2: '#0f2431', surface3: '#16303f', line: '#1b3546', line2: '#25475c',
    fg: '#ecf7fb', muted: '#9bbccb', dim: '#5f8394', accent: '#2dd4bf', accentInk: '#03201c', accent2: '#60a5fa', display: "'Space Grotesk', Inter, sans-serif" },
  { id: 'daylight', name: 'Daylight', dark: false, bg: '#f4f4f7', surface: '#ffffff', surface2: '#f7f7fa', surface3: '#ececf2', line: '#e6e6ee', line2: '#d6d6e0',
    fg: '#15151c', muted: '#62627a', dim: '#9898ab', accent: '#2c57e6', accentInk: '#ffffff', accent2: '#7c3aed', display: "'Space Grotesk', Inter, sans-serif" },
  { id: 'paper', name: 'Paper & Ink', dark: false, bg: '#f3efe7', surface: '#fffdf8', surface2: '#f8f4ec', surface3: '#ede7db', line: '#e4dccd', line2: '#d4c9b5',
    fg: '#1d1a16', muted: '#6b6255', dim: '#a1968a', accent: '#c2410c', accentInk: '#ffffff', accent2: '#0f766e', display: "'Playfair Display', Georgia, serif" },
]

export type ThemePrefs = { id: string; accent?: string; accent2?: string; radius?: number }
const KEY = 'pulse:studio:theme'

export function loadPrefs(): ThemePrefs {
  try { return { id: 'midnight', ...JSON.parse(localStorage.getItem(KEY) || '{}') } } catch { return { id: 'midnight' } }
}
export function savePrefs(p: ThemePrefs) { try { localStorage.setItem(KEY, JSON.stringify(p)) } catch { /* private mode */ } }

/** Readable ink (black or white) for a custom accent colour. */
function inkFor(hex: string) {
  const n = parseInt(hex.slice(1), 16); const [r, g, b] = [n >> 16 & 255, n >> 8 & 255, n & 255]
  return (r * 299 + g * 587 + b * 114) / 1000 > 150 ? '#111111' : '#ffffff'
}

export function themeVars(p: ThemePrefs): Record<string, string> {
  const t = THEMES.find(x => x.id === p.id) ?? THEMES[0]
  const accent = p.accent || t.accent
  return {
    '--bg': t.bg, '--stage': t.bg, '--surface': t.surface, '--surface-2': t.surface2, '--surface-3': t.surface3,
    '--line': t.line, '--line-2': t.line2, '--fg': t.fg, '--muted': t.muted, '--dim': t.dim,
    '--accent': accent, '--accent-ink': p.accent ? inkFor(accent) : t.accentInk, '--accent-2': p.accent2 || t.accent2,
    '--lime': accent, '--lime-2': accent, '--lime-ink': p.accent ? inkFor(accent) : t.accentInk,
    '--display': t.display, '--r': `${p.radius ?? 12}px`, '--r-lg': `${Math.round((p.radius ?? 12) * 1.45)}px`,
    colorScheme: t.dark ? 'dark' : 'light',
  }
}

// Category hues for icon tiles; the same in every theme so tools stay recognisable.
export const CAT_HUE: Record<string, string> = {
  preproduction: '#8b6cff', casting: '#ff6b9a', image: '#38bdf8', video: '#f59e0b', audio: '#22c55e',
  ads: '#f97316', post: '#a78bfa', distribution: '#14b8a6', helpers: '#eab308', film: '#ef4444',
}
