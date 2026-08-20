import { describe, expect, it, vi } from 'vitest'
import { SseParseError, parseSseEvent, streamAnswer } from './sse-client'
import type { RagStreamEvent } from '../types/api'

const encoder = new TextEncoder()
function streamFrom(chunks: string[]): ReadableStream<Uint8Array> {
  return new ReadableStream({ start(controller) { for (const chunk of chunks) controller.enqueue(encoder.encode(chunk)); controller.close() } })
}

describe('SSE parsing', () => {
  it('parses each supported event type', () => {
    expect(parseSseEvent('event: progress\ndata: {"stage":"searching"}')).toEqual({ type: 'progress', stage: 'searching' })
    expect(parseSseEvent('event: delta\ndata: {"text":"hello\\nworld \\"✓\\""}')).toEqual({ type: 'delta', text: 'hello\nworld "✓"' })
    expect(parseSseEvent('event: sources\ndata: {"sources":[{"citation_number":1,"url":"https://example.com","title":"Example"}]}')).toEqual({ type: 'sources', sources: [{ citation_number: 1, url: 'https://example.com', title: 'Example' }] })
    expect(parseSseEvent('event: complete\ndata: {}')).toEqual({ type: 'complete' })
    expect(parseSseEvent('event: error\ndata: {"message":"Unavailable"}')).toEqual({ type: 'error', message: 'Unavailable' })
  })
  it('ignores unknown events and rejects malformed JSON', () => {
    expect(parseSseEvent('event: ping\ndata: {}')).toBeNull()
    expect(() => parseSseEvent('event: delta\ndata: {invalid}')).toThrow(SseParseError)
  })
  it('handles event framing across arbitrary network chunks', async () => {
    const received: RagStreamEvent[] = []
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(new Response(streamFrom(['event: progress\ndata: {"stage":"search', 'ing"}\n\nevent: delta\ndata: {"text":"first"}\n\nevent: delta\ndata: {"text":"second"}\n\n']), { headers: { 'Content-Type': 'text/event-stream' } }))
    await streamAnswer('q', { fetchImpl, onEvent: (event) => received.push(event) })
    expect(received).toEqual([{ type: 'progress', stage: 'searching' }, { type: 'delta', text: 'first' }, { type: 'delta', text: 'second' }])
  })
  it('passes AbortSignal to streaming requests', async () => {
    const controller = new AbortController()
    const fetchImpl = vi.fn<typeof fetch>().mockImplementation(async () => new Response(streamFrom([])))
    await streamAnswer('q', { signal: controller.signal, fetchImpl, onEvent: () => undefined })
    expect(fetchImpl.mock.calls[0]?.[1]?.signal).toBe(controller.signal)
  })
  it('serializes web, files, and hybrid scopes without leaking file fields into web requests', async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockImplementation(async () => new Response(streamFrom([])))
    await streamAnswer('web query', { fetchImpl, onEvent: () => undefined })
    await streamAnswer('file query', { fetchImpl, onEvent: () => undefined, sourceMode: 'files', conversationId: 'conversation-b', documentIds: ['ready-b'] })
    await streamAnswer('hybrid query', { fetchImpl, onEvent: () => undefined, sourceMode: 'hybrid', conversationId: 'conversation-b', documentIds: ['ready-b'] })

    expect(JSON.parse(String(fetchImpl.mock.calls[0]?.[1]?.body))).toEqual({ query: 'web query', source_mode: 'web' })
    expect(JSON.parse(String(fetchImpl.mock.calls[1]?.[1]?.body))).toEqual({ query: 'file query', source_mode: 'files', conversation_id: 'conversation-b', document_ids: ['ready-b'] })
    expect(JSON.parse(String(fetchImpl.mock.calls[2]?.[1]?.body))).toEqual({ query: 'hybrid query', source_mode: 'hybrid', conversation_id: 'conversation-b', document_ids: ['ready-b'] })
  })
  it('maps URL-less file source events while preserving document metadata', () => {
    expect(parseSseEvent('event: sources\ndata: {"sources":[{"citation_number":1,"source_type":"file","document_id":"doc-1","filename":"report.pdf","page_number":2}]}')).toEqual({ type: 'sources', sources: [{ citation_number: 1, url: '', title: null, source_type: 'file', document_id: 'doc-1', filename: 'report.pdf', page_number: 2 }] })
  })
})
