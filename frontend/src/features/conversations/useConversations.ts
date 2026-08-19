import { useCallback, useEffect, useRef, useState } from 'react'
import { streamAnswer } from '../../lib/sse-client'
import type { RagStreamEvent } from '../../types/api'
import { createConversationRepository, type ConversationRepository } from './repository'
import { conversationTitle, sendableHistory, type Conversation, type ConversationMessage } from './types'

const repository = createConversationRepository()
const id = () => crypto.randomUUID()
const now = () => new Date().toISOString()
const abortError = (error: unknown) => error instanceof DOMException && error.name === 'AbortError'

export function useConversations(repo: ConversationRepository = repository) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [active, setActive] = useState<Conversation | null>(null)
  const activeRef = useRef<Conversation | null>(null)
  const controller = useRef<AbortController | null>(null)
  const requestId = useRef(0)
  useEffect(() => { activeRef.current = active }, [active])
  const save = useCallback((conversation: Conversation) => { setActive(conversation); setConversations((items) => [conversation, ...items.filter((item) => item.id !== conversation.id)].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))); void repo.put(conversation) }, [repo])
  const load = useCallback(async (conversationId: string | null) => { if (!conversationId) { setActive(null); return }; setActive(await repo.get(conversationId) ?? null) }, [repo])
  useEffect(() => { void repo.list().then(setConversations) }, [repo])
  useEffect(() => () => controller.current?.abort(), [])
  const submit = useCallback((query: string) => {
    const trimmed = query.trim(); if (!trimmed || controller.current) return
    const timestamp = now(); const base = active ?? { id: id(), title: conversationTitle(trimmed), createdAt: timestamp, updatedAt: timestamp, messages: [] }
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
    void streamAnswer(trimmed, { signal: signal.signal, history, onEvent: update }).then(() => { if (serial === requestId.current) controller.current = null }).catch((error: unknown) => { if (serial !== requestId.current || abortError(error)) return; controller.current = null; update({ type: 'error', message: 'We could not complete this search. Please try again.' }) })
  }, [active, save])
  const stop = useCallback(() => { const current = activeRef.current; if (!controller.current || !current) return; requestId.current += 1; controller.current.abort(); controller.current = null; const messages: ConversationMessage[] = current.messages.map((message) => message.status === 'streaming' ? { ...message, status: 'stopped' as const, progressStage: null } : message); save({ ...current, updatedAt: now(), messages }) }, [save])
  const abandon = useCallback(() => { requestId.current += 1; controller.current?.abort(); controller.current = null; setActive(null) }, [])
  const remove = useCallback(async (conversationId: string) => { await repo.delete(conversationId); setConversations((items) => items.filter((item) => item.id !== conversationId)); if (active?.id === conversationId) setActive(null) }, [active, repo])
  return { conversations, active, load, submit, stop, abandon, remove, isStreaming: active?.messages.some((message) => message.status === 'streaming') ?? false }
}
