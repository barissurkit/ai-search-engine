import { useCallback, useEffect, useRef, useState } from 'react'
import { streamAnswer } from '../../lib/sse-client'
import type { RagStreamEvent } from '../../types/api'
import { createConversationRepository, type ConversationRepository } from './repository'
import { conversationTitle, sendableHistory, type Conversation, type ConversationMessage } from './types'
import { deleteConversationDocuments, deleteDocument, uploadDocument } from '../documents/api'

const repository = createConversationRepository()
const id = () => crypto.randomUUID()
const now = () => new Date().toISOString()
const abortError = (error: unknown) => error instanceof DOMException && error.name === 'AbortError'

export function useConversations(repo: ConversationRepository = repository) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [active, setActive] = useState<Conversation | null>(null)
  const [documentError, setDocumentError] = useState<string | null>(null)
  const [removingDocumentId, setRemovingDocumentId] = useState<string | null>(null)
  const [conversationError, setConversationError] = useState<string | null>(null)
  const [removingConversationId, setRemovingConversationId] = useState<string | null>(null)
  const activeRef = useRef<Conversation | null>(null)
  const controller = useRef<AbortController | null>(null)
  const requestId = useRef(0)
  useEffect(() => { activeRef.current = active }, [active])
  const save = useCallback((conversation: Conversation) => { setActive(conversation); setConversations((items) => [conversation, ...items.filter((item) => item.id !== conversation.id)].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))); void repo.put(conversation) }, [repo])
  const load = useCallback(async (conversationId: string | null) => { if (!conversationId) { setActive(null); return }; setActive(await repo.get(conversationId) ?? null) }, [repo])
  useEffect(() => { void repo.list().then(setConversations) }, [repo])
  useEffect(() => () => controller.current?.abort(), [])
  const submit = useCallback((query: string, sourceMode: 'web' | 'files' | 'hybrid' = 'web') => {
    const trimmed = query.trim(); if (!trimmed || controller.current) return
    const timestamp = now(); const base = active ?? { id: id(), title: conversationTitle(trimmed), createdAt: timestamp, updatedAt: timestamp, messages: [], documents: [] }
    const history = sendableHistory(base.messages)
    const user: ConversationMessage = { id: id(), role: 'user', content: trimmed, createdAt: timestamp }
    const assistant: ConversationMessage = { id: id(), role: 'assistant', content: '', createdAt: timestamp, status: 'streaming', sources: [], progressStage: null }
    let conversation: Conversation = { ...base, updatedAt: timestamp, messages: [...base.messages, user, assistant] }
    save(conversation)
    const serial = ++requestId.current; const signal = new AbortController(); controller.current = signal
    const update = (event: RagStreamEvent) => {
      if (serial !== requestId.current) return
      const messages: ConversationMessage[] = conversation.messages.map((message) => {
        if (message.id !== assistant.id) return message
        if (event.type === 'delta') return { ...message, content: message.content + event.text }
        if (event.type === 'sources') return { ...message, sources: event.sources }
        if (event.type === 'progress') return { ...message, progressStage: event.stage }
        if (event.type === 'complete') return { ...message, status: 'complete' as const, progressStage: null }
        if (event.type === 'error') return { ...message, status: 'error' as const, error: event.message, progressStage: null }
        return message
      })
      conversation = { ...conversation, updatedAt: now(), messages }; save(conversation)
    }
    const documentIds = base.documents.filter((document) => document.status === 'ready').map((document) => document.id)
    void streamAnswer(trimmed, { signal: signal.signal, history, sourceMode, conversationId: sourceMode === 'web' ? undefined : base.id, documentIds: sourceMode === 'web' ? undefined : documentIds, onEvent: update }).then(() => { if (serial === requestId.current) controller.current = null }).catch((error: unknown) => { if (serial !== requestId.current || abortError(error)) return; controller.current = null; update({ type: 'error', message: 'We could not complete this search. Please try again.' }) })
  }, [active, save])
  const stop = useCallback(() => { const current = activeRef.current; if (!controller.current || !current) return; requestId.current += 1; controller.current.abort(); controller.current = null; const messages: ConversationMessage[] = current.messages.map((message) => message.status === 'streaming' ? { ...message, status: 'stopped' as const, progressStage: null } : message); save({ ...current, updatedAt: now(), messages }) }, [save])
  const abandon = useCallback(() => { requestId.current += 1; controller.current?.abort(); controller.current = null; setActive(null) }, [])
  const attach = useCallback(async (file: File) => { const timestamp = now(); const base: Conversation = active ?? { id: id(), title: '', createdAt: timestamp, updatedAt: timestamp, messages: [], documents: [] }; const pending = { id: id(), filename: file.name, mediaType: file.type, pageCount: null, chunkCount: 0, createdAt: timestamp, status: 'uploading' as const }; save({ ...base, documents: [...base.documents, pending], updatedAt: timestamp }); try { const ready = await uploadDocument(base.id, file); save({ ...base, documents: [...base.documents, ready], updatedAt: now() }) } catch { save({ ...base, documents: [...base.documents, { ...pending, status: 'error' as const, error: 'Upload failed' }], updatedAt: now() }) } }, [active, save])
  const removeDocument = useCallback(async (documentId: string) => { const current = activeRef.current; const document = current?.documents.find((item) => item.id === documentId); if (!current || !document || removingDocumentId) return false; setDocumentError(null); setRemovingDocumentId(documentId); try { if (document.status === 'ready') await deleteDocument(current.id, documentId); const documents = current.documents.filter((item) => item.id !== documentId); if (document.status !== 'ready' && current.messages.length === 0 && documents.length === 0) { await repo.delete(current.id); setConversations((items) => items.filter((item) => item.id !== current.id)); setActive(null) } else save({ ...current, documents, updatedAt: now() }); return true } catch { setDocumentError('Could not remove this file. Try again.'); return false } finally { setRemovingDocumentId(null) } }, [removingDocumentId, repo, save])
  const remove = useCallback(async (conversationId: string) => { const current = conversations.find((item) => item.id === conversationId) ?? (activeRef.current?.id === conversationId ? activeRef.current : null); if (!current || removingConversationId) return false; setConversationError(null); setRemovingConversationId(conversationId); try { if (current.documents.some((document) => document.status === 'ready')) await deleteConversationDocuments(conversationId); await repo.delete(conversationId); setConversations((items) => items.filter((item) => item.id !== conversationId)); if (activeRef.current?.id === conversationId) setActive(null); return true } catch { setConversationError('Could not delete this conversation. Try again.'); return false } finally { setRemovingConversationId(null) } }, [conversations, removingConversationId, repo])
  return { conversations, active, load, submit, stop, abandon, remove, attach, removeDocument, documentError, removingDocumentId, conversationError, removingConversationId, isStreaming: active?.messages.some((message) => message.status === 'streaming') ?? false }
}
