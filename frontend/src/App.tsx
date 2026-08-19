import { useEffect, useState } from 'react'
import { AppHeader } from './components/AppHeader'
import { ConversationSidebar } from './components/ConversationSidebar'
import { ConversationThread } from './components/ConversationThread'
import { SearchComposer } from './components/SearchComposer'
import { SuggestionChip } from './components/SuggestionChip'
import { useConversations } from './features/conversations/useConversations'
import './app/app.css'

const suggestions = [
  'How does Retrieval-Augmented Generation work?',
  'Compare vector databases for semantic search',
  'What are the latest developments in local AI models?',
  'Summarize the key ideas behind quantum computing',
]

function App() {
  const [query, setQuery] = useState('')
  const [route, setRoute] = useState(() => location.pathname.match(/^\/c\/([^/]+)$/)?.[1] ?? null)
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem('sidebar-collapsed') === 'true')
  const { conversations, active, load, submit, stop, abandon, remove, isStreaming } = useConversations()
  useEffect(() => { void load(route) }, [load, route])
  useEffect(() => { const listener = () => setRoute(location.pathname.match(/^\/c\/([^/]+)$/)?.[1] ?? null); addEventListener('popstate', listener); return () => removeEventListener('popstate', listener) }, [])
  const navigate = (path: string) => { history.pushState({}, '', path); setRoute(path.match(/^\/c\/([^/]+)$/)?.[1] ?? null) }
  const beginResearch = (submittedQuery: string) => { submit(submittedQuery); setQuery('') }
  useEffect(() => { if (active && route !== active.id) navigate(`/c/${active.id}`) }, [active, route])
  const returnToLanding = () => { abandon(); navigate('/'); setQuery('') }
  const toggle = () => setCollapsed((value) => { localStorage.setItem('sidebar-collapsed', String(!value)); return !value })

  return (
    <div className="workspace-shell">
      <ConversationSidebar conversations={conversations} activeId={active?.id} onNew={returnToLanding} onOpen={(id) => navigate(`/c/${id}`)} onDelete={async (id) => { await remove(id); if (route === id) returnToLanding() }} collapsed={collapsed} onToggle={toggle} />
      <div className="app-shell">
      <AppHeader />
      {active ? <><ConversationThread conversation={active} onStop={stop} /><div className="followup-composer"><SearchComposer query={query} onQueryChange={setQuery} onSubmit={beginResearch} disabled={isStreaming} placeholder="Ask a follow-up..." /></div></> : <main className="landing-page">
        <section className="hero" aria-labelledby="welcome-title">
          <p className="eyebrow">AI-powered research</p>
          <h1 id="welcome-title">What do you want to understand?</h1>
          <p className="intro">Search the web and get answers grounded in real sources.</p>
          <SearchComposer query={query} onQueryChange={setQuery} onSubmit={beginResearch} autoFocus placeholder="Ask anything..." />
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
    </div>
  )
}

export default App
