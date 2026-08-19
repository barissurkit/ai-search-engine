import { describe, expect, it } from 'vitest'
import { conversationTitle, sendableHistory } from './types'

describe('conversation helpers', () => {
  it('creates a deterministic compact title', () => {
    expect(conversationTitle('  A   useful\nquestion  ')).toBe('A useful question')
  })

  it('sends users and only completed assistant turns as follow-up context', () => {
    expect(sendableHistory([
      { id: 'u', role: 'user', content: 'What is RAG?', createdAt: '2026-01-01' },
      { id: 'a', role: 'assistant', content: 'Answer [1]', createdAt: '2026-01-01', status: 'complete' },
      { id: 's', role: 'assistant', content: 'Partial', createdAt: '2026-01-01', status: 'stopped' },
      { id: 'e', role: 'assistant', content: 'Error', createdAt: '2026-01-01', status: 'error' },
    ])).toEqual([{ role: 'user', content: 'What is RAG?' }, { role: 'assistant', content: 'Answer [1]' }])
  })
})
