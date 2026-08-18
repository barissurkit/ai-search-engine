import { useState } from 'react'
import { AppHeader } from './components/AppHeader'
import { ResearchView } from './components/ResearchView'
import { SearchComposer } from './components/SearchComposer'
import { SuggestionChip } from './components/SuggestionChip'
import { useResearch } from './features/research/useResearch'
import './app/app.css'

const suggestions = [
  'How does Retrieval-Augmented Generation work?',
  'Compare vector databases for semantic search',
  'What are the latest developments in local AI models?',
  'Summarize the key ideas behind quantum computing',
]

function App() {
  const [query, setQuery] = useState('')
  const { state, start, stop, reset } = useResearch()

  const beginResearch = (submittedQuery: string) => {
    setQuery(submittedQuery)
    start(submittedQuery)
  }

  const returnToLanding = () => {
    reset()
    setQuery('')
  }

  return (
    <div className="app-shell">
      <AppHeader />
      {state.status !== 'idle' ? <ResearchView state={state} onStop={stop} onNewSearch={returnToLanding} /> : <main className="landing-page">
        <section className="hero" aria-labelledby="welcome-title">
          <p className="eyebrow">AI-powered research</p>
          <h1 id="welcome-title">What do you want to understand?</h1>
          <p className="intro">Search the web and get answers grounded in real sources.</p>
          <SearchComposer query={query} onQueryChange={setQuery} onSubmit={beginResearch} autoFocus />
          <div className="suggestions" aria-label="Example searches">
            <p className="suggestions-label">Try asking</p>
            <div className="suggestion-list">
              {suggestions.map((suggestion) => (
                <SuggestionChip key={suggestion} query={suggestion} onSelect={setQuery} />
              ))}
            </div>
          </div>
        </section>
        <footer className="landing-footer">AI Search helps you start with a better question.</footer>
      </main>}
    </div>
  )
}

export default App
