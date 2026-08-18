import type { ResearchState } from '../features/research/useResearch'
import { AnswerContent } from './AnswerContent'
import { SourcesSection } from './SourcesSection'

const progressLabels = {
  searching: 'Searching the web',
  ingesting: 'Reading sources',
  retrieving: 'Finding relevant evidence',
  generating: 'Generating answer',
} as const

interface ResearchViewProps { state: ResearchState; onStop: () => void; onNewSearch: () => void }

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
        {state.status === 'running' && state.progressStage === 'generating' && !state.answer && <p className="answer-pending">Preparing your answer…</p>}
        <AnswerContent answer={state.answer} sources={state.sources} />
        {state.status === 'completed' && !state.wasCancelled && !state.answer && <p className="empty-answer" role="status">No answer was generated.</p>}
        <SourcesSection sources={state.sources} />
      </div>
    </main>
  )
}
