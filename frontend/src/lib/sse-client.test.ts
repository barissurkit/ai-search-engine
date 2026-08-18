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
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(new Response(streamFrom([])))
    await streamAnswer('q', { signal: controller.signal, fetchImpl, onEvent: () => undefined })
    expect(fetchImpl.mock.calls[0]?.[1]?.signal).toBe(controller.signal)
  })
})
