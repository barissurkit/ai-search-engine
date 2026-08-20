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
    {open && <div className="theme-menu" ref={menuRef} role="menu" aria-label="Theme preference">
      {options.map((option) => <button key={option.value} type="button" role="menuitemradio" aria-checked={preference === option.value} onClick={() => { onChange(option.value); setOpen(false) }}><span>{option.label}</span>{preference === option.value && <span aria-hidden="true">✓</span>}</button>)}
    </div>}
    <button className="theme-trigger" ref={triggerRef} type="button" aria-haspopup="menu" aria-expanded={open} aria-label={`Theme: ${selected}`} onClick={() => setOpen((value) => !value)}><span aria-hidden="true">◐</span>{selected}<span className="theme-chevron" aria-hidden="true">⌄</span></button>
  </div>
}
