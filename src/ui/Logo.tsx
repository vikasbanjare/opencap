// Pulse by aifloh: the logo mark from the Pulse Premiere plugin (same geometry and gradient).
let n = 0
export function LogoMark({ size = 24 }: { size?: number }) {
  const id = `plsG${++n}`
  return (
    <svg className="pulse-mark" viewBox="0 0 100 112" width={size} height={size * 1.12} aria-hidden="true">
      <defs><linearGradient id={id} x1="14" y1="104" x2="88" y2="12" gradientUnits="userSpaceOnUse">
        <stop offset="0" stopColor="#8FB0FF" /><stop offset="1" stopColor="#2C57E6" /></linearGradient></defs>
      <circle cx="37" cy="14.5" r="10.5" fill={`url(#${id})`} />
      <path d="M27 43a10 10 0 0 1 10-10h12a27 27 0 0 1 0 54h-4v15a9 9 0 0 1 -18 0Z" fill={`url(#${id})`} />
      <line x1="33.5" y1="64" x2="64" y2="45.5" stroke="#fff" strokeWidth="8.5" strokeLinecap="round" />
    </svg>
  )
}
export function Brand({ size = 24, by = true }: { size?: number; by?: boolean }) {
  return <span className="brand"><LogoMark size={size} /><span className="brand-name">Pulse</span>{by && <span className="brand-by">by aifloh</span>}</span>
}
