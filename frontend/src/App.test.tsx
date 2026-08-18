import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'

afterEach(cleanup)

describe('App', () => {
  it('renders the brand, hero, and accessible search composer', () => {
    render(<App />)
    expect(screen.getByRole('link', { name: 'AI Search home' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'What do you want to understand?' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Search the web' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Submit search' })).toBeDisabled()
  })

  it('accepts text and populates the composer from a suggestion', () => {
    render(<App />)
    const textarea = screen.getByRole('textbox', { name: 'Search the web' })
    fireEvent.change(textarea, { target: { value: 'Explain neural networks' } })
    expect(textarea).toHaveValue('Explain neural networks')
    fireEvent.click(screen.getByRole('button', { name: 'How does Retrieval-Augmented Generation work?' }))
    expect(textarea).toHaveValue('How does Retrieval-Augmented Generation work?')
  })

  it('handles Enter locally without making a network request', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    render(<App />)
    const textarea = screen.getByRole('textbox', { name: 'Search the web' })
    fireEvent.change(textarea, { target: { value: 'A local-only search intent' } })
    fireEvent.keyDown(textarea, { key: 'Enter' })
    expect(fetchSpy).not.toHaveBeenCalled()
    fetchSpy.mockRestore()
  })

  it('allows Shift+Enter without submitting', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    render(<App />)
    const textarea = screen.getByRole('textbox', { name: 'Search the web' })
    fireEvent.change(textarea, { target: { value: 'First line' } })
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true })
    fireEvent.change(textarea, { target: { value: 'First line\nSecond line' } })
    expect(textarea).toHaveValue('First line\nSecond line')
    expect(fetchSpy).not.toHaveBeenCalled()
    fetchSpy.mockRestore()
  })

  it('keeps empty submission as a no-op', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    render(<App />)
    fireEvent.submit(screen.getByRole('textbox', { name: 'Search the web' }).closest('form')!)
    expect(fetchSpy).not.toHaveBeenCalled()
    fetchSpy.mockRestore()
  })
})
