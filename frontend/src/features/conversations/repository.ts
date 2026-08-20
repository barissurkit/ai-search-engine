import type { Conversation } from './types'

export interface ConversationRepository {
  list(): Promise<Conversation[]>
  get(id: string): Promise<Conversation | undefined>
  put(conversation: Conversation): Promise<void>
  delete(id: string): Promise<void>
}

const memory = new Map<string, Conversation>()
const DB_NAME = 'ai-search-conversations'
const STORE = 'conversations'

function sort(conversations: Conversation[]) { return conversations.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)) }
function request<T>(value: IDBRequest<T>): Promise<T> { return new Promise((resolve, reject) => { value.onsuccess = () => resolve(value.result); value.onerror = () => reject(value.error) }) }

export function createConversationRepository(): ConversationRepository {
  if (typeof indexedDB === 'undefined') return {
    async list() { return sort([...memory.values()].map((item) => ({ ...item, documents: item.documents ?? [] }))) }, async get(id) { const item = memory.get(id); return item && { ...item, documents: item.documents ?? [] } }, async put(value) { memory.set(value.id, value) }, async delete(id) { memory.delete(id) },
  }
  const db = new Promise<IDBDatabase>((resolve, reject) => {
    const open = indexedDB.open(DB_NAME, 2)
    open.onupgradeneeded = () => { if (!open.result.objectStoreNames.contains(STORE)) open.result.createObjectStore(STORE, { keyPath: 'id' }) }
    open.onsuccess = () => resolve(open.result); open.onerror = () => reject(open.error)
  })
  return {
    async list() { const database = await db; return sort((await request(database.transaction(STORE).objectStore(STORE).getAll())).map((item) => ({ ...item, documents: item.documents ?? [] }))) },
    async get(id) { const database = await db; const item = await request(database.transaction(STORE).objectStore(STORE).get(id)); return item && { ...item, documents: item.documents ?? [] } },
    async put(value) { const database = await db; await request(database.transaction(STORE, 'readwrite').objectStore(STORE).put(value)) },
    async delete(id) { const database = await db; await request(database.transaction(STORE, 'readwrite').objectStore(STORE).delete(id)) },
  }
}
