import type { CitationSource, RagAnswer } from '../types/api'
import { ApiClientError } from './api-client'

function isRecord(value: unknown): value is Record<string, unknown> { return typeof value === 'object' && value !== null }

export function parseCitationSource(value: unknown): CitationSource {
  if (!isRecord(value) || typeof value.citation_number !== 'number' || typeof value.url !== 'string') throw new ApiClientError('Citation source had an invalid shape.')
  if (value.title !== null && value.title !== undefined && typeof value.title !== 'string') throw new ApiClientError('Citation source had an invalid title.')
  return { citation_number: value.citation_number, url: value.url, title: value.title ?? null }
}

export function parseRagAnswer(value: unknown): RagAnswer {
  if (!isRecord(value) || typeof value.query !== 'string' || typeof value.answer !== 'string' || !Array.isArray(value.sources)) throw new ApiClientError('Answer response had an invalid shape.')
  return { query: value.query, answer: value.answer, sources: value.sources.map(parseCitationSource) }
}

export function parseCitationSources(value: unknown): CitationSource[] {
  if (!Array.isArray(value)) throw new ApiClientError('Stream sources had an invalid shape.')
  return value.map(parseCitationSource)
}
