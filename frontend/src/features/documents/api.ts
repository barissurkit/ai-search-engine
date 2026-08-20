import { apiUrl } from '../../lib/api-config'
import type { ConversationDocument } from '../conversations/types'

export async function uploadDocument(conversationId: string, file: File): Promise<ConversationDocument> {
  const form = new FormData(); form.append('conversation_id', conversationId); form.append('file', file)
  const response = await fetch(apiUrl('/api/v1/documents'), { method: 'POST', body: form })
  if (!response.ok) throw new Error('Upload failed')
  const value = await response.json()
  return { id: value.id, filename: value.filename, mediaType: value.media_type, pageCount: value.page_count, chunkCount: value.chunk_count, createdAt: new Date().toISOString(), status: 'ready' }
}
export async function deleteDocument(conversationId: string, documentId: string) { const response = await fetch(`${apiUrl(`/api/v1/documents/${documentId}`)}?conversation_id=${encodeURIComponent(conversationId)}`, { method: 'DELETE' }); if (!response.ok) throw new Error('Delete failed') }
export async function deleteConversationDocuments(conversationId: string) { const response = await fetch(`${apiUrl('/api/v1/documents')}?conversation_id=${encodeURIComponent(conversationId)}`, { method: 'DELETE' }); if (!response.ok) throw new Error('Conversation cleanup failed') }
