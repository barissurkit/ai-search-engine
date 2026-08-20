import { afterEach, describe, expect, it } from 'vitest'
import { readTheme, resolvedTheme, THEME_KEY } from './theme'
afterEach(() => localStorage.clear())
describe('theme preferences', () => {
  it('defaults invalid and missing values to System', () => { expect(readTheme()).toBe('system'); localStorage.setItem(THEME_KEY, 'other'); expect(readTheme()).toBe('system') })
  it('restores each persisted preference', () => { for (const value of ['light', 'dark', 'system']) { localStorage.setItem(THEME_KEY, value); expect(readTheme()).toBe(value) } })
  it('resolves System against OS while manual choices override it', () => { expect(resolvedTheme('system', false)).toBe('light'); expect(resolvedTheme('system', true)).toBe('dark'); expect(resolvedTheme('light', true)).toBe('light'); expect(resolvedTheme('dark', false)).toBe('dark') })
})
