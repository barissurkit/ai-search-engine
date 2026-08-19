import type { CitationSource, ProgressStage } from '../../types/api'

export type MessageStatus = 'streaming' | 'complete' | 'stopped' | 'error'
export interface ConversationMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  createdAt: string
  status?: MessageStatus
  sources?: CitationSource[]
  progressStage?: ProgressStage | null
  error?: string | null
}
export interface Conversation {
  id: string
  title: string
  createdAt: string
  updatedAt: string
  messages: ConversationMessage[]
}

export function conversationTitle(query: string): string {
  const normalized = query.trim().replace(/\s+/g, ' ')
  return normalized.length > 56 ? `${normalized.slice(0, 55).trimEnd()}…` : normalized
}

export function sendableHistory(messages: ConversationMessage[]) {
  return messages.filter((message) => message.role === 'user' || message.status === 'complete')
    .map(({ role, content }) => ({ role, content }))
}
