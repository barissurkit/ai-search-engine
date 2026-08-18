import { apiUrl } from './api-config'
import { parseRagAnswer } from './response-parsers'
import type { RagAnswer } from '../types/api'

export class ApiClientError extends Error {
  readonly status: number | undefined

  constructor(message: string, status?: number) {
    super(message)
    this.name = 'ApiClientError'
    this.status = status
  }
}

export interface AnswerRequestOptions { signal?: AbortSignal; fetchImpl?: typeof fetch }

export async function getAnswer(query: string, options: AnswerRequestOptions = {}): Promise<RagAnswer> {
  const response = await (options.fetchImpl ?? fetch)(apiUrl('/api/v1/answer'), {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query }), signal: options.signal,
  })
  if (!response.ok) throw new ApiClientError(`Answer request failed with status ${response.status}.`, response.status)
  try { return parseRagAnswer(await response.json()) } catch (error) {
    if (error instanceof ApiClientError) throw error
    throw new ApiClientError('Answer response had an invalid shape.')
  }
}
