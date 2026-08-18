import { describe, expect, it, vi } from 'vitest'
import { apiUrl } from './api-config'
import { getAnswer } from './api-client'

describe('API client', () => {
  it('builds an API URL from the configured base URL', () => {
    expect(apiUrl('api/v1/answer', 'https://api.example.com/')).toBe('https://api.example.com/api/v1/answer')
  })
  it('normalizes non-success responses', async () => {
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(new Response('', { status: 502 }))
    await expect(getAnswer('test', { fetchImpl })).rejects.toMatchObject({ name: 'ApiClientError', status: 502 })
  })
  it('passes an AbortSignal to requests', async () => {
    const controller = new AbortController()
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({ query: 'q', answer: 'a', sources: [] })))
    await getAnswer('q', { signal: controller.signal, fetchImpl })
    expect(fetchImpl.mock.calls[0]?.[1]?.signal).toBe(controller.signal)
  })
})
