import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { RagStreamEvent } from './types/api'

const streamAnswerMock = vi.hoisted(() => vi.fn())
vi.mock('./lib/sse-client', () => ({ streamAnswer: streamAnswerMock }))

import App from './App'

interface StreamCall { query: string; onEvent: (event: RagStreamEvent) => void; signal?: AbortSignal }
function latestCall(): StreamCall {
  const [query, options] = streamAnswerMock.mock.calls.at(-1) as [string, Omit<StreamCall, 'query'>]
  return { query, ...options }
}
function emit(event: RagStreamEvent) { act(() => { latestCall().onEvent(event) }) }

afterEach(() => { cleanup(); streamAnswerMock.mockReset(); history.replaceState({}, '', '/') })

describe('App', () => {
  it('renders the brand, hero, and accessible composer', () => {
    render(<App />)
    expect(screen.getByRole('link', { name: 'AI Search home' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'What do you want to understand?' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Search the web' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Submit search' })).toBeDisabled()
  })

  it('preserves input, suggestions, and keyboard submit behavior', () => {
    streamAnswerMock.mockResolvedValue(undefined)
    render(<App />)
    const textarea = screen.getByRole('textbox', { name: 'Search the web' })
    fireEvent.change(textarea, { target: { value: 'First line\nSecond line' } })
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true })
    expect(textarea).toHaveValue('First line\nSecond line')
    fireEvent.click(screen.getByRole('button', { name: 'How does Retrieval-Augmented Generation work?' }))
    fireEvent.keyDown(textarea, { key: 'Enter' })
    expect(latestCall().query).toBe('How does Retrieval-Augmented Generation work?')
  })

  it('does not start a stream for an empty query', () => {
    render(<App />)
    fireEvent.submit(screen.getByRole('textbox', { name: 'Search the web' }).closest('form')!)
    expect(streamAnswerMock).not.toHaveBeenCalled()
  })

  it('shows the submitted query and progress labels', () => {
    streamAnswerMock.mockResolvedValue(undefined)
    render(<App />)
    fireEvent.change(screen.getByRole('textbox', { name: 'Search the web' }), { target: { value: 'Explain RAG' } })
    fireEvent.submit(screen.getByRole('textbox', { name: 'Search the web' }).closest('form')!)
    expect(screen.getByText('Explain RAG')).toBeInTheDocument()
    emit({ type: 'progress', stage: 'searching' }); expect(screen.getByRole('status')).toHaveTextContent('Searching the web')
    emit({ type: 'progress', stage: 'ingesting' }); expect(screen.getByRole('status')).toHaveTextContent('Reading sources')
    emit({ type: 'progress', stage: 'retrieving' }); expect(screen.getByRole('status')).toHaveTextContent('Finding relevant evidence')
    emit({ type: 'progress', stage: 'generating' }); expect(screen.getByRole('status')).toHaveTextContent('Generating answer')
  })

  it('appends deltas in order and completes the stream', () => {
    streamAnswerMock.mockResolvedValue(undefined)
    render(<App />)
    fireEvent.change(screen.getByRole('textbox', { name: 'Search the web' }), { target: { value: 'Question' } })
    fireEvent.submit(screen.getByRole('textbox', { name: 'Search the web' }).closest('form')!)
    emit({ type: 'delta', text: 'First ' }); emit({ type: 'delta', text: 'second.' })
    expect(screen.getByLabelText('Answer')).toHaveTextContent('First second.')
    emit({ type: 'complete' })
    expect(screen.queryByRole('button', { name: 'Stop' })).not.toBeInTheDocument()
  })

  it('renders source previews from the stream', () => {
    streamAnswerMock.mockResolvedValue(undefined)
    render(<App />)
    fireEvent.change(screen.getByRole('textbox', { name: 'Search the web' }), { target: { value: 'Sources' } })
    fireEvent.submit(screen.getByRole('textbox', { name: 'Search the web' }).closest('form')!)
    emit({ type: 'sources', sources: [{ citation_number: 1, title: 'Example source', url: 'https://example.com/article' }] })
    expect(screen.getByRole('link', { name: 'Example source' })).toHaveAttribute('href', 'https://example.com/article')
  })

  it('shows a safe stream error without treating it as success', () => {
    streamAnswerMock.mockResolvedValue(undefined)
    render(<App />)
    fireEvent.change(screen.getByRole('textbox', { name: 'Search the web' }), { target: { value: 'Failure' } })
    fireEvent.submit(screen.getByRole('textbox', { name: 'Search the web' }).closest('form')!)
    emit({ type: 'error', message: 'The answer service is unavailable.' })
    expect(screen.getByRole('alert')).toHaveTextContent('The answer service is unavailable.')
    expect(screen.queryByRole('button', { name: 'Stop' })).not.toBeInTheDocument()
  })

  it('shows generating feedback before the first answer delta', () => {
    streamAnswerMock.mockResolvedValue(undefined)
    render(<App />)
    fireEvent.change(screen.getByRole('textbox', { name: 'Search the web' }), { target: { value: 'Generating' } })
    fireEvent.submit(screen.getByRole('textbox', { name: 'Search the web' }).closest('form')!)
    emit({ type: 'progress', stage: 'generating' })
    expect(screen.getByText('Preparing your answer…')).toBeInTheDocument()
    expect(screen.queryByLabelText('Answer')).not.toBeInTheDocument()
  })

  it('keeps a partial answer visible alongside an error', () => {
    streamAnswerMock.mockResolvedValue(undefined)
    render(<App />)
    fireEvent.change(screen.getByRole('textbox', { name: 'Search the web' }), { target: { value: 'Partial' } })
    fireEvent.submit(screen.getByRole('textbox', { name: 'Search the web' }).closest('form')!)
    emit({ type: 'delta', text: 'Partial answer' })
    emit({ type: 'error', message: 'The answer service is unavailable.' })
    expect(screen.getByLabelText('Answer')).toHaveTextContent('Partial answer')
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })

  it('shows a defensive fallback when a stream completes without an answer', () => {
    streamAnswerMock.mockResolvedValue(undefined)
    render(<App />)
    fireEvent.change(screen.getByRole('textbox', { name: 'Search the web' }), { target: { value: 'Empty' } })
    fireEvent.submit(screen.getByRole('textbox', { name: 'Search the web' }).closest('form')!)
    emit({ type: 'complete' })
    expect(screen.getByText('No answer was generated.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Copy answer' })).not.toBeInTheDocument()
  })

  it('stops the active request without displaying a generic error', () => {
    streamAnswerMock.mockImplementation((_query: string, { signal }: Omit<StreamCall, 'query'>) => new Promise((_, reject) => signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))))
    render(<App />)
    fireEvent.change(screen.getByRole('textbox', { name: 'Search the web' }), { target: { value: 'Cancel me' } })
    fireEvent.submit(screen.getByRole('textbox', { name: 'Search the web' }).closest('form')!)
    const { signal } = latestCall()
    fireEvent.click(screen.getByRole('button', { name: 'Stop' }))
    expect(signal?.aborted).toBe(true)
    expect(screen.getByText('Research stopped. Your partial answer is preserved.')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('returns to the landing page for a new search', () => {
    streamAnswerMock.mockResolvedValue(undefined)
    render(<App />)
    fireEvent.change(screen.getByRole('textbox', { name: 'Search the web' }), { target: { value: 'One query' } })
    fireEvent.submit(screen.getByRole('textbox', { name: 'Search the web' }).closest('form')!)
    fireEvent.click(screen.getByRole('button', { name: 'New search' }))
    expect(screen.getByRole('heading', { name: 'What do you want to understand?' })).toBeInTheDocument()
  })

  it('aborts an active request when returning to a new search', () => {
    streamAnswerMock.mockImplementation((_query: string, { signal }: Omit<StreamCall, 'query'>) => new Promise(() => signal))
    render(<App />)
    fireEvent.change(screen.getByRole('textbox', { name: 'Search the web' }), { target: { value: 'Abort me' } })
    fireEvent.submit(screen.getByRole('textbox', { name: 'Search the web' }).closest('form')!)
    const { signal } = latestCall()
    fireEvent.click(screen.getByRole('button', { name: 'New search' }))
    expect(signal?.aborted).toBe(true)
    expect(screen.getByRole('textbox', { name: 'Search the web' })).toHaveValue('')
  })

  it('ignores late events from a cancelled or reset request', () => {
    streamAnswerMock.mockResolvedValue(undefined)
    render(<App />)
    fireEvent.change(screen.getByRole('textbox', { name: 'Search the web' }), { target: { value: 'Old query' } })
    fireEvent.submit(screen.getByRole('textbox', { name: 'Search the web' }).closest('form')!)
    const oldCall = latestCall()
    fireEvent.click(screen.getByRole('button', { name: 'New search' }))
    act(() => { oldCall.onEvent({ type: 'delta', text: 'This must not appear.' }) })
    expect(screen.queryByText('This must not appear.')).not.toBeInTheDocument()
    expect(streamAnswerMock).toHaveBeenCalledTimes(1)
  })

})
