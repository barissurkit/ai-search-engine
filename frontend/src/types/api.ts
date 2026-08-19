export interface CitationSource {
  citation_number: number
  url: string
  title: string | null
}

export interface RagAnswer {
  query: string
  answer: string
  sources: CitationSource[]
}

export type ProgressStage = 'searching' | 'ingesting' | 'retrieving' | 'generating'
export type RagStreamEvent =
  | { type: 'progress'; stage: ProgressStage }
  | { type: 'delta'; text: string }
  | { type: 'sources'; sources: CitationSource[] }
  | { type: 'complete' }
  | { type: 'error'; message: string }

export interface ConversationHistoryTurn { role: 'user' | 'assistant'; content: string }
