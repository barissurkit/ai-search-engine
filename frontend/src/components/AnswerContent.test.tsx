import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AnswerContent } from './AnswerContent'
import { SourcesSection } from './SourcesSection'

const sources = [
  { citation_number: 1, title: 'First source', url: 'https://one.example.com/article' },
  { citation_number: 2, title: 'Second source', url: 'https://two.example.com/research' },
]

afterEach(cleanup)

describe('AnswerContent', () => {
  it('renders plain text and supported Markdown safely', () => {
    const { container } = render(<AnswerContent answer={'# Heading\n\n**bold** and *italic*\n\n- first\n- second\n\n```ts\nconst x = 1\n```'} sources={sources} />)
    expect(screen.getByRole('heading', { name: 'Heading' })).toBeInTheDocument()
    expect(screen.getByText('bold').tagName).toBe('STRONG')
    expect(screen.getByRole('list')).toBeInTheDocument()
    expect(container.querySelector('pre code')).toHaveTextContent('const x = 1')
  })

  it('does not render model HTML as executable DOM', () => {
    const { container } = render(<AnswerContent answer={'<script>window.evil = true</script>\n\nSafe text'} sources={sources} />)
    expect(container.querySelector('script')).toBeNull()
    expect(screen.getByText(/window.evil/)).toBeInTheDocument()
  })

  it('handles incomplete Markdown without crashing', () => {
    render(<AnswerContent answer={'**partial bold\n\n```'} sources={sources} />)
    expect(screen.getByText(/partial bold/)).toBeInTheDocument()
  })

  it('maps valid citations to source controls and leaves invalid markers as text', () => {
    render(<AnswerContent answer={'First [1], second [2], missing [7], malformed [1a].'} sources={sources} />)
    expect(screen.getByRole('button', { name: 'View source 1' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'View source 2' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'View source 7' })).not.toBeInTheDocument()
    expect(screen.getByText(/missing \[7], malformed \[1a]/)).toBeInTheDocument()
  })

  it('maps Unicode citations to the matching sources without creating invalid controls', () => {
    render(<AnswerContent answer={'First 【1】, second 【2】, missing 【7】, malformed 【abc】.'} sources={sources} />)
    expect(screen.getByRole('button', { name: 'View source 1' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'View source 2' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'View source 7' })).not.toBeInTheDocument()
    expect(screen.getByText(/missing 【7】, malformed 【abc】/)).toBeInTheDocument()
  })

  it('scrolls and focuses the matching source card on citation click', () => {
    const scrollIntoView = vi.fn()
    HTMLElement.prototype.scrollIntoView = scrollIntoView
    render(<><AnswerContent answer="See [1]." sources={sources} /><SourcesSection sources={sources} /></>)
    const source = document.getElementById('source-1')!
    const focus = vi.spyOn(source, 'focus')
    fireEvent.click(screen.getByRole('button', { name: 'View source 1' }))
    expect(scrollIntoView).toHaveBeenCalled()
    expect(focus).toHaveBeenCalledWith({ preventScroll: true })
  })

  it('copies the original Markdown text and provides feedback', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })
    render(<AnswerContent answer="**Original markdown**" sources={sources} />)
    fireEvent.click(screen.getByRole('button', { name: 'Copy answer' }))
    await vi.waitFor(() => expect(writeText).toHaveBeenCalledWith('**Original markdown**'))
    await vi.waitFor(() => expect(screen.getByRole('button', { name: 'Copy answer' })).toHaveTextContent('Copied'))
  })

  it('does not crash when clipboard access fails', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('Unavailable'))
    Object.assign(navigator, { clipboard: { writeText } })
    render(<AnswerContent answer="Copy safely" sources={sources} />)
    fireEvent.click(screen.getByRole('button', { name: 'Copy answer' }))
    await vi.waitFor(() => expect(writeText).toHaveBeenCalled())
    expect(screen.getByText('Copy safely')).toBeInTheDocument()
  })
})

describe('SourcesSection', () => {
  it('renders accessible source cards and hostnames', () => {
    const { container } = render(<SourcesSection sources={sources} />)
    expect(screen.getByRole('heading', { name: /Sources · 2/ })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'First source' })).toHaveAttribute('href', 'https://one.example.com/article')
    expect(screen.getByText('one.example.com')).toBeInTheDocument()
    expect(Array.from(container.querySelectorAll('.source-card a')).map((link) => link.textContent)).toEqual(['First source', 'Second source'])
  })

  it('does not render a source section when sources are absent', () => {
    const { container } = render(<SourcesSection sources={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})
