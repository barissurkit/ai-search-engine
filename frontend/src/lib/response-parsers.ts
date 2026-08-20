import type { CitationSource, RagAnswer } from '../types/api'
import { ApiClientError } from './api-client'

function isRecord(value: unknown): value is Record<string, unknown> { return typeof value === 'object' && value !== null }

export function parseCitationSource(value: unknown): CitationSource {
  if (!isRecord(value) || typeof value.citation_number !== 'number') throw new ApiClientError('Citation source had an invalid shape.')
  if (value.title !== null && value.title !== undefined && typeof value.title !== 'string') throw new ApiClientError('Citation source had an invalid title.')
  const sourceType = value.source_type === 'file' ? 'file' : value.source_type === 'web' ? 'web' : undefined
  if (sourceType !== 'file' && typeof value.url !== 'string') throw new ApiClientError('Citation source had an invalid shape.')
  if (value.document_id !== null && value.document_id !== undefined && typeof value.document_id !== 'string') throw new ApiClientError('Citation source had an invalid document ID.')
  if (value.filename !== null && value.filename !== undefined && typeof value.filename !== 'string') throw new ApiClientError('Citation source had an invalid filename.')
  if (value.page_number !== null && value.page_number !== undefined && typeof value.page_number !== 'number') throw new ApiClientError('Citation source had an invalid page number.')
  return { citation_number: value.citation_number, url: typeof value.url === 'string' ? value.url : '', title: value.title ?? null, ...(sourceType ? { source_type: sourceType } : {}), ...(value.document_id !== undefined ? { document_id: value.document_id ?? null } : {}), ...(value.filename !== undefined ? { filename: value.filename ?? null } : {}), ...(value.page_number !== undefined ? { page_number: value.page_number ?? null } : {}) }
}

export function parseRagAnswer(value: unknown): RagAnswer {
  if (!isRecord(value) || typeof value.query !== 'string' || typeof value.answer !== 'string' || !Array.isArray(value.sources)) throw new ApiClientError('Answer response had an invalid shape.')
  return { query: value.query, answer: value.answer, sources: value.sources.map(parseCitationSource) }
}

export function parseCitationSources(value: unknown): CitationSource[] {
  if (!Array.isArray(value)) throw new ApiClientError('Stream sources had an invalid shape.')
  return value.map(parseCitationSource)
}
