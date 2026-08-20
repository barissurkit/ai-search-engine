import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ThemeControl } from './ThemeControl'

describe('ThemeControl', () => {
  afterEach(cleanup)

  it('opens a custom menu, selects a preference, and closes with Escape', () => {
    const onChange = vi.fn()
    render(<ThemeControl preference="system" onChange={onChange} />)

    const trigger = screen.getByRole('button', { name: 'Settings. Theme: System' })
    fireEvent.click(trigger)
    expect(screen.getByRole('menu', { name: 'Settings' })).toBeInTheDocument()
    expect(screen.getByRole('menuitemradio', { name: 'System' })).toHaveAttribute('aria-checked', 'true')

    fireEvent.click(screen.getByRole('menuitemradio', { name: 'Dark' }))
    expect(onChange).toHaveBeenCalledWith('dark')
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()

    fireEvent.click(trigger)
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })
})
