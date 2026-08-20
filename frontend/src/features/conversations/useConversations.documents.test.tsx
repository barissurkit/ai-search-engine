import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Conversation, ConversationDocument } from './types'
import type { ConversationRepository } from './repository'

const streamAnswerMock = vi.hoisted(() => vi.fn())
const uploadDocumentMock = vi.hoisted(() => vi.fn())
const deleteDocumentMock = vi.hoisted(() => vi.fn())
const deleteConversationDocumentsMock = vi.hoisted(() => vi.fn())
vi.mock('../../lib/sse-client', () => ({ streamAnswer: streamAnswerMock }))
vi.mock('../documents/api', () => ({ uploadDocument: uploadDocumentMock, deleteDocument: deleteDocumentMock, deleteConversationDocuments: deleteConversationDocumentsMock }))

import { useConversations } from './useConversations'

const ready = (id: string): ConversationDocument => ({ id, filename: `${id}.pdf`, mediaType: 'application/pdf', pageCount: 1, chunkCount: 1, createdAt: 'now', status: 'ready' })
const conversation = (id: string, documents: ConversationDocument[]) => ({ id, title: id, createdAt: 'now', updatedAt: 'now', messages: [], documents })

function repository(items: Conversation[]): ConversationRepository & { put: ReturnType<typeof vi.fn> } {
  const values = new Map(items.map((item) => [item.id, item]))
  return {
    list: vi.fn(async () => [...values.values()]), get: vi.fn(async (id: string) => values.get(id)),
    put: vi.fn(async (item) => { values.set(item.id, item) }), delete: vi.fn(async (id: string) => { values.delete(id) }),
  }
}

function persistentRepositories(items: Conversation[]) {
  const values = new Map(items.map((item) => [item.id, structuredClone(item)]))
  const create = (): ConversationRepository => ({
    list: async () => [...values.values()].map((item) => ({ ...structuredClone(item), documents: item.documents ?? [] })),
    get: async (id) => { const item = values.get(id); return item && { ...structuredClone(item), documents: item.documents ?? [] } },
    put: async (item) => { values.set(item.id, structuredClone(item)) }, delete: async (id) => { values.delete(id) },
  })
  return { create, values }
}

function Harness({ repo, initialId }: { repo: ConversationRepository; initialId: string | null }) {
  const state = useConversations(repo)
  return <>
    <button onClick={() => { void state.load(initialId) }}>load</button>
    <button onClick={() => state.submit('Question', 'web')}>web</button>
    <button onClick={() => state.submit('Question', 'files')}>files</button>
    <button onClick={() => state.submit('Question', 'hybrid')}>hybrid</button>
    <button onClick={() => { void state.attach(new File(['body'], 'draft.pdf', { type: 'application/pdf' })) }}>attach</button>
    <button onClick={() => { const id = state.active?.documents.find((document) => document.status === 'ready')?.id ?? state.active?.documents[0]?.id; if (id) void state.removeDocument(id) }}>remove</button>
    <button onClick={() => { const id = state.active?.id; if (id) void state.remove(id) }}>remove conversation</button>
    <button onClick={() => state.stop()}>stop</button>
    <output data-testid="documents">{JSON.stringify(state.active?.documents ?? [])}</output>
    <output data-testid="error">{state.documentError ?? ''}</output>
    <output data-testid="conversation-error">{state.conversationError ?? ''}</output>
  </>
}

function LastReadyModeHarness({ repo }: { repo: ConversationRepository }) {
  const state = useConversations(repo)
  const [mode, setMode] = useState<'web' | 'files' | 'hybrid'>('files')
  const removeLastReady = () => {
    const id = state.active?.documents.find((document) => document.status === 'ready')?.id
    if (!id) return
    void state.removeDocument(id).then((success) => {
      if (success && state.active?.documents.filter((document) => document.status === 'ready' && document.id !== id).length === 0) setMode('web')
    })
  }
  return <>
    <button onClick={() => { void state.load('conversation-b') }}>load</button>
    <button onClick={removeLastReady}>remove</button>
    <output data-testid="mode">{mode}</output>
    <output data-testid="mode-documents">{JSON.stringify(state.active?.documents ?? [])}</output>
    <output data-testid="error">{state.documentError ?? ''}</output>
  </>
}

async function load(repo: ConversationRepository, id: string | null) {
  render(<Harness repo={repo} initialId={id} />)
  fireEvent.click(screen.getByRole('button', { name: 'load' }))
  await waitFor(() => expect(screen.getByTestId('documents')).not.toHaveTextContent('[]'))
}

afterEach(() => { cleanup(); streamAnswerMock.mockReset().mockResolvedValue(undefined); uploadDocumentMock.mockReset(); deleteDocumentMock.mockReset(); deleteConversationDocumentsMock.mockReset() })

describe('document conversation scope', () => {
  it('sends only active ready document IDs for files and hybrid, excluding upload/error and other conversations', async () => {
    streamAnswerMock.mockResolvedValue(undefined)
    const repo = repository([
      conversation('conversation-a', [ready('doc-a')]),
      conversation('conversation-b', [ready('ready-b'), { ...ready('uploading-b'), status: 'uploading' }, { ...ready('failed-b'), status: 'error' }]),
    ])
    await load(repo, 'conversation-b')
    fireEvent.click(screen.getByRole('button', { name: 'files' }))
    await waitFor(() => expect(streamAnswerMock).toHaveBeenCalledTimes(1))
    fireEvent.click(screen.getByRole('button', { name: 'hybrid' }))
    await waitFor(() => expect(streamAnswerMock).toHaveBeenCalledTimes(2))
    expect(streamAnswerMock.mock.calls[0][1]).toMatchObject({ sourceMode: 'files', conversationId: 'conversation-b', documentIds: ['ready-b'] })
    expect(streamAnswerMock.mock.calls[1][1]).toMatchObject({ sourceMode: 'hybrid', conversationId: 'conversation-b', documentIds: ['ready-b'] })
  })

  it('uses the upload draft conversation scope for the following files request', async () => {
    streamAnswerMock.mockResolvedValue(undefined)
    uploadDocumentMock.mockResolvedValue(ready('server-doc'))
    const repo = repository([])
    render(<Harness repo={repo} initialId={null} />)
    fireEvent.click(screen.getByRole('button', { name: 'attach' }))
    await waitFor(() => expect(uploadDocumentMock).toHaveBeenCalledTimes(1))
    const uploadedConversationId = uploadDocumentMock.mock.calls[0][0]
    await waitFor(() => expect(screen.getByTestId('documents')).toHaveTextContent('server-doc'))
    fireEvent.click(screen.getByRole('button', { name: 'files' }))
    await waitFor(() => expect(streamAnswerMock).toHaveBeenCalledTimes(1))
    expect(streamAnswerMock.mock.calls[0][1]).toMatchObject({ sourceMode: 'files', conversationId: uploadedConversationId, documentIds: ['server-doc'] })
  })

  it('persists successful removal and excludes that document from later file requests', async () => {
    streamAnswerMock.mockResolvedValue(undefined)
    deleteDocumentMock.mockResolvedValue(undefined)
    const repo = repository([conversation('conversation-b', [ready('ready-b')])])
    await load(repo, 'conversation-b')
    fireEvent.click(screen.getByRole('button', { name: 'remove' }))
    await waitFor(() => expect(deleteDocumentMock).toHaveBeenCalledWith('conversation-b', 'ready-b'))
    await waitFor(() => expect(screen.getByTestId('documents')).toHaveTextContent('[]'))
    expect(repo.put).toHaveBeenLastCalledWith(expect.objectContaining({ id: 'conversation-b', documents: [] }))
    fireEvent.click(screen.getByRole('button', { name: 'files' }))
    await waitFor(() => expect(streamAnswerMock).toHaveBeenCalledTimes(1))
    expect(streamAnswerMock.mock.calls[0][1]).toMatchObject({ documentIds: [] })
  })

  it('keeps a failed removal available for retry and prevents a duplicate pending delete', async () => {
    let resolveDelete: (() => void) | undefined
    deleteDocumentMock.mockImplementationOnce(() => new Promise<void>((resolve) => { resolveDelete = resolve })).mockRejectedValueOnce(new Error('failed')).mockResolvedValueOnce(undefined)
    const repo = repository([conversation('conversation-b', [ready('ready-b')])])
    await load(repo, 'conversation-b')
    fireEvent.click(screen.getByRole('button', { name: 'remove' }))
    await waitFor(() => expect(deleteDocumentMock).toHaveBeenCalledTimes(1))
    fireEvent.click(screen.getByRole('button', { name: 'remove' }))
    expect(deleteDocumentMock).toHaveBeenCalledTimes(1)
    await act(async () => { resolveDelete?.() })
    await waitFor(() => expect(screen.getByTestId('documents')).toHaveTextContent('[]'))
  })

  it('keeps the document and exposes an error when deletion fails, then allows a later retry', async () => {
    deleteDocumentMock.mockRejectedValueOnce(new Error('failed')).mockResolvedValueOnce(undefined)
    const repo = repository([conversation('conversation-b', [ready('ready-b')])])
    await load(repo, 'conversation-b')
    fireEvent.click(screen.getByRole('button', { name: 'remove' }))
    await waitFor(() => expect(screen.getByTestId('error')).toHaveTextContent('Could not remove this file. Try again.'))
    expect(screen.getByTestId('documents')).toHaveTextContent('ready-b')
    fireEvent.click(screen.getByRole('button', { name: 'files' }))
    await waitFor(() => expect(streamAnswerMock).toHaveBeenCalledTimes(1))
    expect(streamAnswerMock.mock.calls[0][1]).toMatchObject({ documentIds: ['ready-b'] })
    fireEvent.click(screen.getByRole('button', { name: 'remove' }))
    await waitFor(() => expect(deleteDocumentMock).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(screen.getByTestId('documents')).toHaveTextContent('[]'))
  })

  it('preserves ready documents after stopping a files stream so the next request can reuse them', async () => {
    streamAnswerMock.mockImplementation((_query: string, { signal }: { signal: AbortSignal }) => new Promise((_, reject) => signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))))
    const repo = repository([conversation('conversation-b', [ready('ready-b')])])
    await load(repo, 'conversation-b')
    fireEvent.click(screen.getByRole('button', { name: 'files' }))
    await waitFor(() => expect(streamAnswerMock).toHaveBeenCalledTimes(1))
    fireEvent.click(screen.getByRole('button', { name: 'stop' }))
    expect(screen.getByTestId('documents')).toHaveTextContent('ready-b')
    streamAnswerMock.mockResolvedValue(undefined)
    fireEvent.click(screen.getByRole('button', { name: 'files' }))
    await waitFor(() => expect(streamAnswerMock).toHaveBeenCalledTimes(2))
    expect(streamAnswerMock.mock.calls[1][1]).toMatchObject({ sourceMode: 'files', documentIds: ['ready-b'] })
  })

  it('returns to Web only after successfully removing the last ready document', async () => {
    deleteDocumentMock.mockResolvedValue(undefined)
    render(<LastReadyModeHarness repo={repository([conversation('conversation-b', [ready('ready-b')])])} />)
    fireEvent.click(screen.getByRole('button', { name: 'load' }))
    await waitFor(() => expect(screen.getByTestId('mode-documents')).toHaveTextContent('ready-b'))
    fireEvent.click(screen.getByRole('button', { name: 'remove' }))
    await waitFor(() => expect(screen.getByTestId('mode')).toHaveTextContent('web'))
  })

  it('keeps Files mode when removal of the last ready document fails', async () => {
    deleteDocumentMock.mockRejectedValue(new Error('failed'))
    render(<LastReadyModeHarness repo={repository([conversation('conversation-b', [ready('ready-b')])])} />)
    fireEvent.click(screen.getByRole('button', { name: 'load' }))
    await waitFor(() => expect(screen.getByTestId('mode-documents')).toHaveTextContent('ready-b'))
    fireEvent.click(screen.getByRole('button', { name: 'remove' }))
    await waitFor(() => expect(screen.getByTestId('error')).toHaveTextContent('Could not remove this file. Try again.'))
    expect(screen.getByTestId('mode')).toHaveTextContent('files')
  })

  it('cleans backend document scope before deleting a document conversation, without touching another conversation', async () => {
    deleteConversationDocumentsMock.mockResolvedValue(undefined)
    const repo = repository([conversation('conversation-a', [ready('doc-a')]), conversation('conversation-b', [ready('doc-b')])])
    await load(repo, 'conversation-a')
    fireEvent.click(screen.getByRole('button', { name: 'remove conversation' }))
    await waitFor(() => expect(deleteConversationDocumentsMock).toHaveBeenCalledWith('conversation-a'))
    await waitFor(() => expect(repo.delete).toHaveBeenCalledWith('conversation-a'))
    expect(await repo.get('conversation-a')).toBeUndefined()
    expect(await repo.get('conversation-b')).toEqual(conversation('conversation-b', [ready('doc-b')]))
  })

  it('keeps a conversation local when cleanup fails and permits a retry', async () => {
    deleteConversationDocumentsMock.mockRejectedValueOnce(new Error('cleanup failed')).mockResolvedValueOnce(undefined)
    const repo = repository([conversation('conversation-a', [ready('doc-a')])])
    await load(repo, 'conversation-a')
    fireEvent.click(screen.getByRole('button', { name: 'remove conversation' }))
    await waitFor(() => expect(screen.getByTestId('conversation-error')).toHaveTextContent('Could not delete this conversation. Try again.'))
    expect(await repo.get('conversation-a')).toBeDefined()
    fireEvent.click(screen.getByRole('button', { name: 'remove conversation' }))
    await waitFor(() => expect(deleteConversationDocumentsMock).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(repo.delete).toHaveBeenCalledWith('conversation-a'))
  })

  it('deletes a document-free conversation locally without backend cleanup', async () => {
    const repo = repository([conversation('conversation-a', [])])
    render(<Harness repo={repo} initialId="conversation-a" />)
    fireEvent.click(screen.getByRole('button', { name: 'load' }))
    await waitFor(() => expect(repo.get).toHaveBeenCalledWith('conversation-a'))
    fireEvent.click(screen.getByRole('button', { name: 'remove conversation' }))
    await waitFor(() => expect(repo.delete).toHaveBeenCalledWith('conversation-a'))
    expect(deleteConversationDocumentsMock).not.toHaveBeenCalled()
  })

  it('restores document metadata across a repository reload for Files and Hybrid, without persisting file binaries', async () => {
    streamAnswerMock.mockResolvedValue(undefined)
    const persisted = persistentRepositories([conversation('conversation-a', [{ ...ready('demo-report'), filename: 'report.pdf', pageCount: 3, chunkCount: 5 }])])
    await load(persisted.create(), 'conversation-a')
    expect(screen.getByTestId('documents')).toHaveTextContent('report.pdf')
    expect(screen.getByTestId('documents')).not.toHaveTextContent('File')
    fireEvent.click(screen.getByRole('button', { name: 'files' }))
    await waitFor(() => expect(streamAnswerMock).toHaveBeenCalledTimes(1))
    expect(streamAnswerMock.mock.calls[0][1]).toMatchObject({ conversationId: 'conversation-a', documentIds: ['demo-report'] })
    fireEvent.click(screen.getByRole('button', { name: 'hybrid' }))
    await waitFor(() => expect(streamAnswerMock).toHaveBeenCalledTimes(2))
    expect(streamAnswerMock.mock.calls[1][1]).toMatchObject({ conversationId: 'conversation-a', documentIds: ['demo-report'] })
  })

  it('keeps removed metadata absent after reload and migrates an old document-less conversation', async () => {
    deleteDocumentMock.mockResolvedValue(undefined)
    const persisted = persistentRepositories([conversation('conversation-a', [ready('demo-report')]), { id: 'old-history', title: 'Old', createdAt: 'old', updatedAt: 'old', messages: [] } as unknown as Conversation])
    await load(persisted.create(), 'conversation-a')
    fireEvent.click(screen.getByRole('button', { name: 'remove' }))
    await waitFor(() => expect(screen.getByTestId('documents')).toHaveTextContent('[]'))
    cleanup()
    render(<Harness repo={persisted.create()} initialId="conversation-a" />)
    fireEvent.click(screen.getByRole('button', { name: 'load' }))
    await waitFor(() => expect(screen.getByTestId('documents')).toHaveTextContent('[]'))
    expect((await persisted.create().get('old-history'))?.documents).toEqual([])
  })

  it('removes an empty failed-upload draft locally without inventing backend cleanup', async () => {
    const repo = repository([conversation('draft', [{ ...ready('failed-upload'), status: 'error' }])])
    render(<Harness repo={repo} initialId="draft" />)
    fireEvent.click(screen.getByRole('button', { name: 'load' }))
    await waitFor(() => expect(screen.getByTestId('documents')).toHaveTextContent('failed-upload'))
    fireEvent.click(screen.getByRole('button', { name: 'remove' }))
    await waitFor(() => expect(repo.delete).toHaveBeenCalledWith('draft'))
    expect(deleteDocumentMock).not.toHaveBeenCalled()
    expect(deleteConversationDocumentsMock).not.toHaveBeenCalled()
  })
})
