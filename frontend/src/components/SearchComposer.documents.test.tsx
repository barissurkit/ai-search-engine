import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SearchComposer } from './SearchComposer'

const ready = { id: 'ready-a', filename: 'report.pdf', mediaType: 'application/pdf', pageCount: 2, chunkCount: 1, createdAt: 'now', status: 'ready' as const }
const uploading = { ...ready, id: 'uploading-b', filename: 'upload.txt', status: 'uploading' as const }
const failed = { ...ready, id: 'failed-c', filename: 'failed.docx', status: 'error' as const }

describe('SearchComposer documents', () => {
  afterEach(cleanup)
  it('disables file modes without ready documents and renders document states', () => {
    render(<SearchComposer query="" onQueryChange={() => undefined} onSubmit={() => undefined} onModeChange={() => undefined} documents={[uploading, failed]} />)
    expect(screen.getByRole('button', { name: 'Files' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Web + Files' })).toBeDisabled()
    expect(screen.getByText('Uploading…')).toBeInTheDocument()
    expect(screen.getByText('Upload failed')).toBeInTheDocument()
  })

  it('enables file modes and provides a removable ready chip', () => {
    const remove = vi.fn(); const mode = vi.fn()
    render(<SearchComposer query="" onQueryChange={() => undefined} onSubmit={() => undefined} onModeChange={mode} onRemoveDocument={remove} documents={[ready]} />)
    fireEvent.click(screen.getByRole('button', { name: 'Files' }))
    expect(mode).toHaveBeenCalledWith('files')
    fireEvent.click(screen.getByRole('button', { name: 'Remove report.pdf' }))
    expect(remove).toHaveBeenCalledWith('ready-a')
  })
})
