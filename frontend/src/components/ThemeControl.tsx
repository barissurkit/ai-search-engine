import { useEffect, useRef, useState } from 'react'
import type { ThemePreference } from '../lib/theme'

const options: Array<{ value: ThemePreference; label: string }> = [
  { value: 'system', label: 'System' },
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
]

export function ThemeControl({ preference, onChange }: { preference: ThemePreference; onChange: (value: ThemePreference) => void }) {
  const [open, setOpen] = useState(false)
  const controlRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const closeOutside = (event: MouseEvent) => { if (!controlRef.current?.contains(event.target as Node)) setOpen(false) }
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === 'Escape') { setOpen(false); triggerRef.current?.focus() } }
    document.addEventListener('mousedown', closeOutside)
    document.addEventListener('keydown', closeOnEscape)
    menuRef.current?.querySelector<HTMLButtonElement>('button')?.focus()
    return () => { document.removeEventListener('mousedown', closeOutside); document.removeEventListener('keydown', closeOnEscape) }
  }, [open])

  const selected = options.find((option) => option.value === preference)?.label ?? 'System'
  return <div className="theme-control" ref={controlRef}>
    {open && <div className="theme-menu" ref={menuRef} role="menu" aria-label="Settings">
      <p className="settings-heading">Appearance</p>
      <p className="settings-label">Theme</p>
      {options.map((option) => <button key={option.value} type="button" role="menuitemradio" aria-checked={preference === option.value} onClick={() => { onChange(option.value); setOpen(false) }}><span>{option.label}</span>{preference === option.value && <span aria-hidden="true">✓</span>}</button>)}
    </div>}
    <button className="theme-trigger" ref={triggerRef} type="button" aria-haspopup="menu" aria-expanded={open} aria-label={`Settings. Theme: ${selected}`} onClick={() => setOpen((value) => !value)}>
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 8.25a3.75 3.75 0 1 0 0 7.5 3.75 3.75 0 0 0 0-7.5Zm0-5.25v2.1m0 13.8V21m9-9h-2.1M5.1 12H3m15.36-6.36-1.49 1.49M7.13 16.87l-1.49 1.49m0-12.72 1.49 1.49m9.74 9.74 1.49 1.49" /></svg>
      <span className="settings-trigger-label">Settings</span><span className="theme-chevron" aria-hidden="true">⌃</span>
    </button>
  </div>
}
