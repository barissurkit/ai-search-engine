import type { CitationSource } from '../types/api'

interface SourcesSectionProps { sources: CitationSource[] }

function hostname(url: string): string { try { return new URL(url).hostname } catch { return url } }

export function SourcesSection({ sources }: SourcesSectionProps) {
  if (sources.length === 0) return null
  return (
    <section className="sources-section" aria-labelledby="sources-title">
      <h2 id="sources-title">Sources <span>· {sources.length}</span></h2>
      <div className="source-grid">
        {sources.map((source, index) => <SourceCard key={`${source.citation_number}-${source.url}`} source={source} referenceNumber={index + 1} />)}
      </div>
    </section>
  )
}

function SourceCard({ source, referenceNumber }: { source: CitationSource; referenceNumber: number }) {
  const isFile = source.source_type === 'file'
  const fileLabel = source.filename || 'Document'
  return (
    <article id={`source-${referenceNumber}`} className="source-card" tabIndex={-1}>
      <span className="source-number">{referenceNumber}</span>
      <div>
        {isFile ? <><strong>{fileLabel}</strong>{source.page_number ? <p>Page {source.page_number}</p> : null}</> : <><a href={source.url} target="_blank" rel="noreferrer">{source.title || hostname(source.url)}</a><p>{hostname(source.url)}</p></>}
      </div>
    </article>
  )
}
