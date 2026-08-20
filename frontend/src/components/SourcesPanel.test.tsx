import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SourcesPanel } from './SourcesPanel'

const sources = [
  { citation_number: 1, title: 'Web report', url: 'https://example.com/report', source_type: 'web' as const },
  { citation_number: 2, title: null, url: '', source_type: 'file' as const, filename: 'report.pdf', page_number: 2 },
  { citation_number: 3, title: null, url: '', source_type: 'file' as const, filename: 'notes.docx', page_number: null },
]
afterEach(cleanup)
describe('SourcesPanel', () => {
  it('shows an empty state and can be closed', () => {
    const close = vi.fn(); render(<SourcesPanel sources={[]} selectedNumber={null} onClose={close} />)
    expect(screen.getByText('No sources yet.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Close sources' })); expect(close).toHaveBeenCalled()
  })
  it('closes with Escape using the same accessible close behavior', () => {
    const close = vi.fn(); render(<SourcesPanel sources={sources} selectedNumber={null} onClose={close} />)
    fireEvent.keyDown(window, { key: 'Escape' }); expect(close).toHaveBeenCalledTimes(1)
  })
  it('filters hybrid sources by tab and renders safe web and URL-less file items', () => {
    render(<SourcesPanel sources={sources} selectedNumber={2} onClose={() => undefined} />)
    expect(screen.getByRole('tab', { name: 'Files' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByText('report.pdf')).toBeInTheDocument(); expect(screen.getByText('Page 2')).toBeInTheDocument(); expect(screen.queryByRole('link')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: 'Web' }))
    expect(screen.getByRole('link', { name: 'Web report' })).toHaveAttribute('rel', 'noreferrer')
    expect(screen.getByRole('link', { name: 'Web report' })).toHaveAttribute('target', '_blank')
  })
  it('marks the selected source without inventing a page for non-paginated files', () => {
    render(<SourcesPanel sources={sources} selectedNumber={3} onClose={() => undefined} />)
    expect(screen.getByText('notes.docx').closest('article')).toHaveClass('selected')
    expect(screen.queryByText('Page 0')).not.toBeInTheDocument()
  })
})
