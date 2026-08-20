import { useEffect, useMemo, useRef, useState } from 'react'
import type { CitationSource } from '../types/api'

type SourceTab = 'web' | 'files'
interface Props { sources: CitationSource[]; selectedNumber: number | null; onClose: () => void }
function typeOf(source: CitationSource): SourceTab { return source.source_type === 'file' ? 'files' : 'web' }
function hostname(url: string) { try { return new URL(url).hostname } catch { return url } }

export function SourcesPanel({ sources, selectedNumber, onClose }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null)
  const available = useMemo(() => ({ web: sources.some((source) => typeOf(source) === 'web'), files: sources.some((source) => typeOf(source) === 'files') }), [sources])
  const selected = selectedNumber ? sources[selectedNumber - 1] : undefined
  const preferred: SourceTab = selected ? typeOf(selected) : available.web ? 'web' : 'files'
  const [tab, setTab] = useState<SourceTab>(preferred)
  const visible = sources.filter((source) => typeOf(source) === tab)
  useEffect(() => { const close = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }; addEventListener('keydown', close); return () => removeEventListener('keydown', close) }, [onClose])
  return <aside className="sources-panel" aria-label="Sources panel" aria-modal="true">
    <header><h2>Sources <span>· {sources.length}</span></h2><button ref={closeRef} type="button" aria-label="Close sources" onClick={onClose}>×</button></header>
    <div className="sources-tabs" role="tablist" aria-label="Source type"><button type="button" role="tab" aria-selected={tab === 'web'} disabled={!available.web} onClick={() => setTab('web')}>Web</button><button type="button" role="tab" aria-selected={tab === 'files'} disabled={!available.files} onClick={() => setTab('files')}>Files</button></div>
    {sources.length === 0 ? <p className="sources-empty">No sources yet.</p> : <div className="sources-panel-list">{visible.map((source) => {
      const number = sources.indexOf(source) + 1; const file = typeOf(source) === 'files'; const active = selectedNumber === number
      return <article key={`${number}-${source.url}`} className={`sources-panel-item ${active ? 'selected' : ''}`} aria-current={active ? 'true' : undefined} tabIndex={0}>
        <span>{number}</span><div>{file ? <><strong>{source.filename || 'Document'}</strong>{source.page_number ? <p>Page {source.page_number}</p> : null}</> : <><a href={source.url} target="_blank" rel="noreferrer">{source.title || hostname(source.url)}</a><p>{hostname(source.url)}</p></>}</div>
      </article>
    })}</div>}
  </aside>
}
