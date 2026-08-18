import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('App', () => {
  it('renders the AI Search brand', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: 'AI Search' })).toBeInTheDocument()
    expect(screen.getByLabelText('AI Search home')).toBeInTheDocument()
  })
})
