// Inline line icons (24px grid, currentColor), so no icon dependency is needed.
const I = ({ d, fill }: { d: string; fill?: boolean }) => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill={fill ? 'currentColor' : 'none'} stroke={fill ? 'none' : 'currentColor'} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={d} /></svg>
)
export const Icon = {
  captions: <I d="M4 5h16a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1zM10 10.5a2 2 0 1 0 0 3M17 10.5a2 2 0 1 0 0 3" />,
  style: <I d="M12 3a9 9 0 1 0 0 18c1.1 0 1.5-.8 1.5-1.6 0-1-.7-1.4-.7-2.3 0-.9.7-1.6 1.6-1.6H17a4 4 0 0 0 4-4C21 6.6 17 3 12 3zM7.5 11.5h.01M10 7.5h.01M15 7.5h.01" />,
  elements: <I d="M4 4h7v7H4zM13 13h7v7h-7zM17.5 4a3.5 3.5 0 1 1 0 7 3.5 3.5 0 0 1 0-7zM4 20l3.5-6 3.5 6z" />,
  audio: <I d="M9 18V5l12-2v13M9 18a3 3 0 1 1-6 0 3 3 0 0 1 6 0zM21 16a3 3 0 1 1-6 0 3 3 0 0 1 6 0z" />,
  export: <I d="M12 3v12M7 10l5 5 5-5M5 21h14" />,
  back: <I d="M15 18l-6-6 6-6" />,
  play: <I fill d="M8 5.5v13a1 1 0 0 0 1.5.86l10.5-6.5a1 1 0 0 0 0-1.72L9.5 4.64A1 1 0 0 0 8 5.5z" />,
  pause: <I fill d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z" />,
  upload: <I d="M12 16V4M7 9l5-5 5 5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />,
  record: <I fill d="M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10z" />,
  phone: <I d="M7 2h10a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1zM11 18h2" />,
  trash: <I d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" />,
  sparkle: <I fill d="M12 2l1.9 5.6L19.5 9.5l-5.6 1.9L12 17l-1.9-5.6L4.5 9.5l5.6-1.9zM19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9z" />,
}
