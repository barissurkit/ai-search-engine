import type { ResearchState } from '../features/research/useResearch'

const progressLabels = {
  searching: 'Searching the web',
  ingesting: 'Reading sources',
  retrieving: 'Finding relevant evidence',
  generating: 'Generating answer',
} as const

interface ResearchViewProps { state: ResearchState; onStop: () => void; onNewSearch: () => void }

function sourceLabel(title: string | null, url: string): string {
  if (title) return title
  try { return new URL(url).hostname } catch { return url }
}

export function ResearchView({ state, onStop, onNewSearch }: ResearchViewProps) {
  const statusLabel = state.status === 'running' && state.progressStage ? progressLabels[state.progressStage] : null

  return (
    <main className="research-page">
      <div className="research-content">
        <button className="new-search" type="button" onClick={onNewSearch}>New search</button>
        <p className="submitted-query">{state.submittedQuery}</p>
        {state.status === 'running' && (
          <div className="research-status" role="status" aria-live="polite">
            <span className="status-dot" aria-hidden="true" />{statusLabel ?? 'Starting research'}
            <button className="stop-button" type="button" onClick={onStop}>Stop</button>
          </div>
        )}
        {state.wasCancelled && <p className="research-note" role="status">Research stopped. Your partial answer is preserved.</p>}
        {state.error && <p className="research-error" role="alert">{state.error}</p>}
        {(state.answer || state.status === 'running') && <article className="answer-content" aria-label="Answer">{state.answer}</article>}
        {state.sources.length > 0 && (
          <section className="sources-preview" aria-labelledby="sources-title">
            <h2 id="sources-title">Sources</h2>
            <ol>
              {state.sources.map((source) => (
                <li key={`${source.citation_number}-${source.url}`}>
                  <span>{source.citation_number}.</span>
                  <a href={source.url} target="_blank" rel="noreferrer">{sourceLabel(source.title, source.url)}</a>
                </li>
              ))}
            </ol>
          </section>
        )}
      </div>
    </main>
  )
}
