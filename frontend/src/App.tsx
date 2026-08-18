import './app/app.css'

function App() {
  return (
    <div className="app-shell">
      <header className="app-header"><a className="brand" href="/" aria-label="AI Search home">AI Search</a></header>
      <main className="app-content">
        <section aria-labelledby="welcome-title">
          <p className="eyebrow">Research, made clear</p>
          <h1 id="welcome-title">AI Search</h1>
          <p className="intro">Ask a question to explore the web with answers grounded in sources.</p>
        </section>
      </main>
    </div>
  )
}

export default App
