import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { SourcesSection } from './SourcesSection'

describe('SourcesSection file compatibility', () => {
  afterEach(cleanup)
  it('renders a PDF source without creating an external link', () => {
    render(<SourcesSection sources={[{ citation_number: 1, url: 'file://report', title: 'report.pdf', source_type: 'file', filename: 'report.pdf', page_number: 2 }]} />)
    expect(screen.getByText('report.pdf')).toBeInTheDocument()
    expect(screen.getByText('Page 2')).toBeInTheDocument()
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })

  it('does not show a page label for a non-paginated file', () => {
    render(<SourcesSection sources={[{ citation_number: 1, url: 'file://notes', title: null, source_type: 'file', filename: 'notes.docx', page_number: null }]} />)
    expect(screen.getByText('notes.docx')).toBeInTheDocument()
    expect(screen.queryByText(/Page/)).not.toBeInTheDocument()
  })
})
