import { useEffect, useRef } from 'react'

interface SearchComposerProps {
  query: string
  onQueryChange: (query: string) => void
  onSubmit: (query: string) => void
  disabled?: boolean
  autoFocus?: boolean
}

const maxTextareaHeight = 176

export function SearchComposer({ query, onQueryChange, onSubmit, disabled = false, autoFocus = false }: SearchComposerProps) {
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

  return (
    <form className="search-composer" onSubmit={(event) => { event.preventDefault(); submit() }}>
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
        placeholder="Search and ask anything"
        rows={1}
        disabled={disabled}
        autoFocus={autoFocus}
      />
      <button type="submit" aria-label="Submit search" disabled={disabled || !query.trim()}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h13M13 6l6 6-6 6" /></svg>
      </button>
    </form>
  )
}
