import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ConversationThread } from './ConversationThread'

const conversation = { id: 'conversation-a', title: 'A', createdAt: 'now', updatedAt: 'now', documents: [], messages: [
  { id: 'assistant-old', role: 'assistant' as const, content: 'Old [1] and 【1】', createdAt: 'now', status: 'complete' as const, sources: [{ citation_number: 1, title: 'Old web', url: 'https://old.example' }] },
  { id: 'assistant-new', role: 'assistant' as const, content: 'New [1] and [2]', createdAt: 'now', status: 'complete' as const, sources: [{ citation_number: 1, title: null, url: '', source_type: 'file' as const, filename: 'new.pdf', page_number: 2 }, { citation_number: 2, title: 'New web', url: 'https://new.example' }] },
] }
afterEach(cleanup)
describe('ConversationThread source scope', () => {
  it('keeps citation numbering scoped to each assistant message, including historical Unicode citations', () => {
    const select = vi.fn(); render(<ConversationThread conversation={conversation} onStop={() => undefined} onCitationSelect={select} />)
    const citations = screen.getAllByRole('button', { name: 'View source 1' })
    fireEvent.click(citations[0]); expect(select).toHaveBeenLastCalledWith('assistant-old', 1)
    fireEvent.click(citations[1]); expect(select).toHaveBeenLastCalledWith('assistant-old', 1)
    fireEvent.click(citations[2]); expect(select).toHaveBeenLastCalledWith('assistant-new', 1)
    fireEvent.click(screen.getByRole('button', { name: 'View source 2' })); expect(select).toHaveBeenLastCalledWith('assistant-new', 2)
  })
})
