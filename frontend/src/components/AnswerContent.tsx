import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { CitationSource } from '../types/api'
import { rehypeCitations } from '../lib/citations'

interface AnswerContentProps { answer: string; sources: CitationSource[] }

function CitationReference({ number }: { number: number }) {
  const goToSource = () => {
    const card = document.getElementById(`source-${number}`)
    card?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    card?.focus({ preventScroll: true })
  }
  return <button className="citation-reference" type="button" aria-label={`View source ${number}`} onClick={goToSource}>[{number}]</button>
}

export function AnswerContent({ answer, sources }: AnswerContentProps) {
  if (!answer) return null
  return (
    <section className="answer-section" aria-labelledby="answer-title">
      <div className="section-heading"><h2 id="answer-title">Answer</h2><CopyButton text={answer} /></div>
      <article className="answer-content">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[[rehypeCitations, sources.length]]}
          components={{
            a: ({ href, children }) => <a href={href} target="_blank" rel="noreferrer">{children}</a>,
            sup: ({ node, children, ...props }) => {
              const number = node?.properties.dataCitation
              return typeof number === 'number' ? <CitationReference number={number} /> : <sup {...props}>{children}</sup>
            },
          }}
        >
          {answer}
        </ReactMarkdown>
      </article>
    </section>
  )
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try { await navigator.clipboard?.writeText(text); setCopied(true) } catch { return }
  }
  return <button className="copy-button" type="button" aria-label="Copy answer" onClick={() => { void copy() }}>{copied ? 'Copied' : 'Copy'}</button>
}
