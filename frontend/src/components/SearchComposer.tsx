import { useEffect, useRef } from 'react'
import type { ConversationDocument } from '../features/conversations/types'

interface SearchComposerProps {
  query: string
  onQueryChange: (query: string) => void
  onSubmit: (query: string) => void
  disabled?: boolean
  autoFocus?: boolean
  placeholder?: string
  onAttach?: (file: File) => void
  documents?: ConversationDocument[]
  mode?: 'web' | 'files' | 'hybrid'
  onModeChange?: (mode: 'web' | 'files' | 'hybrid') => void
  onRemoveDocument?: (id: string) => void
  removingDocumentId?: string | null
}

const maxTextareaHeight = 176

export function SearchComposer({ query, onQueryChange, onSubmit, disabled = false, autoFocus = false, placeholder = 'Search and ask anything', onAttach, documents = [], mode = 'web', onModeChange, onRemoveDocument, removingDocumentId }: SearchComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const textarea = textareaRef.current
    if (!textarea) return
    textarea.style.height = 'auto'
    textarea.style.height = `${Math.min(Math.max(textarea.scrollHeight, 44), maxTextareaHeight)}px`
  }, [query])

  const submit = () => {
    const trimmedQuery = query.trim()
    if (!trimmedQuery || disabled) return
    onSubmit(trimmedQuery)
  }
  const ready = documents.some((document) => document.status === 'ready')

  return (
    <form className="search-composer" onSubmit={(event) => { event.preventDefault(); submit() }}>
      {onModeChange && <div className="source-modes" aria-label="Source mode">{([['web', 'Web'], ['files', 'Files'], ['hybrid', 'Web + Files']] as const).map(([value, label]) => <button key={value} type="button" className={mode === value ? 'selected' : ''} disabled={value !== 'web' && !ready} onClick={() => onModeChange(value)}>{label}</button>)}</div>}
      {documents.map((document) => <span className={`document-chip ${document.status}`} key={document.id}>{document.filename}<small>{document.status === 'uploading' ? 'Uploading…' : document.status === 'ready' ? 'Ready' : 'Upload failed'}</small><button type="button" aria-label={`Remove ${document.filename}`} disabled={removingDocumentId === document.id} onClick={() => onRemoveDocument?.(document.id)}>×</button></span>)}
      <label className="sr-only" htmlFor="search-query">Search the web</label>
      <textarea
        ref={textareaRef}
        id="search-query"
        name="query"
        value={query}
        onChange={(event) => onQueryChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault()
            submit()
          }
        }}
        placeholder={placeholder}
        rows={1}
        disabled={disabled}
        autoFocus={autoFocus}
      />
      {onAttach && <label className="attachment-button" aria-label="Attach file">+<input type="file" accept=".pdf,.txt,.md,.docx" onChange={(event) => { const file = event.target.files?.[0]; if (file) onAttach(file); event.currentTarget.value = '' }} /></label>}
      <button type="submit" aria-label="Submit search" disabled={disabled || !query.trim()}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h13M13 6l6 6-6 6" /></svg>
      </button>
    </form>
  )
}
