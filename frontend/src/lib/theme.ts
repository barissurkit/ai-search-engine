import { useEffect, useState } from 'react'

export type ThemePreference = 'system' | 'light' | 'dark'
export const THEME_KEY = 'ai-search-theme'
export function readTheme(): ThemePreference { const value = localStorage.getItem(THEME_KEY); return value === 'light' || value === 'dark' || value === 'system' ? value : 'system' }
const media = () => window.matchMedia?.('(prefers-color-scheme: dark)')
export function resolvedTheme(preference: ThemePreference, dark = media()?.matches ?? false) { return preference === 'system' ? (dark ? 'dark' : 'light') : preference }
export function useTheme() {
  const [preference, setPreferenceState] = useState<ThemePreference>(readTheme)
  const [systemDark, setSystemDark] = useState(() => media()?.matches ?? false)
  useEffect(() => { const query = media(); if (!query?.addEventListener) return; const listener = () => setSystemDark(query.matches); query.addEventListener('change', listener); return () => query.removeEventListener('change', listener) }, [])
  const theme = resolvedTheme(preference, systemDark)
  useEffect(() => { document.documentElement.dataset.theme = theme }, [theme])
  const setPreference = (value: ThemePreference) => { localStorage.setItem(THEME_KEY, value); setPreferenceState(value) }
  return { preference, theme, setPreference }
}
