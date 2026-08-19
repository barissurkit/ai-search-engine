import type { ConversationHistoryTurn, RagStreamEvent, ProgressStage } from '../types/api'
import { apiUrl } from './api-config'
import { ApiClientError } from './api-client'
import { parseCitationSources } from './response-parsers'

const stages = new Set<ProgressStage>(['searching', 'ingesting', 'retrieving', 'generating'])

export class SseParseError extends ApiClientError { constructor(message: string) { super(message); this.name = 'SseParseError' } }

function isRecord(value: unknown): value is Record<string, unknown> { return typeof value === 'object' && value !== null }

export function parseSseEvent(frame: string): RagStreamEvent | null {
  const lines = frame.replace(/\r/g, '').split('\n')
  let eventName = 'message'
  const data: string[] = []
  for (const line of lines) {
    if (line.startsWith(':') || line === '') continue
    const separator = line.indexOf(':')
    const field = separator === -1 ? line : line.slice(0, separator)
    const value = separator === -1 ? '' : line.slice(separator + 1).replace(/^ /, '')
    if (field === 'event') eventName = value
    if (field === 'data') data.push(value)
  }
  if (!['progress', 'delta', 'sources', 'complete', 'error'].includes(eventName)) return null
  let payload: unknown
  try { payload = JSON.parse(data.join('\n')) } catch { throw new SseParseError(`Malformed JSON in ${eventName} SSE event.`) }
  if (!isRecord(payload)) throw new SseParseError(`${eventName} SSE event had an invalid shape.`)
  switch (eventName) {
    case 'progress': if (typeof payload.stage === 'string' && stages.has(payload.stage as ProgressStage)) return { type: 'progress', stage: payload.stage as ProgressStage }; break
    case 'delta': if (typeof payload.text === 'string') return { type: 'delta', text: payload.text }; break
    case 'sources': return { type: 'sources', sources: parseCitationSources(payload.sources) }
    case 'complete': return { type: 'complete' }
    case 'error': if (typeof payload.message === 'string') return { type: 'error', message: payload.message }; break
  }
  throw new SseParseError(`${eventName} SSE event had an invalid shape.`)
}

export interface StreamAnswerOptions { signal?: AbortSignal; onEvent: (event: RagStreamEvent) => void; fetchImpl?: typeof fetch; history?: ConversationHistoryTurn[] }

export async function streamAnswer(query: string, options: StreamAnswerOptions): Promise<void> {
  const response = await (options.fetchImpl ?? fetch)(apiUrl('/api/v1/answer/stream'), {
    method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' }, body: JSON.stringify({ query, ...(options.history?.length ? { history: options.history } : {}) }), signal: options.signal,
  })
  if (!response.ok) throw new ApiClientError(`Answer stream failed with status ${response.status}.`, response.status)
  if (!response.body) throw new ApiClientError('Answer stream did not include a response body.')
  const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = ''
  while (true) {
    const { done, value } = await reader.read(); buffer += decoder.decode(value, { stream: !done })
    const frames = buffer.split(/\r?\n\r?\n/); buffer = frames.pop() ?? ''
    for (const frame of frames) { const event = parseSseEvent(frame); if (event) options.onEvent(event) }
    if (done) break
  }
  if (buffer.trim() !== '') { const event = parseSseEvent(buffer); if (event) options.onEvent(event) }
}
