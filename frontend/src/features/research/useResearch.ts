import { useCallback, useEffect, useReducer, useRef } from 'react'
import { streamAnswer } from '../../lib/sse-client'
import type { CitationSource, ProgressStage, RagStreamEvent } from '../../types/api'

export type ResearchStatus = 'idle' | 'running' | 'completed' | 'error'

export interface ResearchState {
  status: ResearchStatus
  submittedQuery: string
  answer: string
  sources: CitationSource[]
  progressStage: ProgressStage | null
  error: string | null
  wasCancelled: boolean
}

const initialState: ResearchState = { status: 'idle', submittedQuery: '', answer: '', sources: [], progressStage: null, error: null, wasCancelled: false }

type Action =
  | { type: 'start'; query: string }
  | { type: 'event'; event: RagStreamEvent }
  | { type: 'networkError' }
  | { type: 'cancel' }
  | { type: 'reset' }

function reducer(state: ResearchState, action: Action): ResearchState {
  switch (action.type) {
    case 'start': return { ...initialState, status: 'running', submittedQuery: action.query }
    case 'event':
      if (state.status !== 'running') return state
      switch (action.event.type) {
        case 'progress': return { ...state, progressStage: action.event.stage }
        case 'delta': return { ...state, answer: state.answer + action.event.text }
        case 'sources': return { ...state, sources: action.event.sources }
        case 'complete': return { ...state, status: 'completed' }
        case 'error': return { ...state, status: 'error', error: action.event.message }
      }
    case 'networkError': return { ...state, status: 'error', error: 'We could not complete this search. Please try again.' }
    case 'cancel': return { ...state, status: 'completed', wasCancelled: true }
    case 'reset': return initialState
  }
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

export function useResearch() {
  const [state, dispatch] = useReducer(reducer, initialState)
  const controllerRef = useRef<AbortController | null>(null)
  const requestIdRef = useRef(0)

  const stop = useCallback(() => {
    if (!controllerRef.current) return
    requestIdRef.current += 1
    controllerRef.current.abort()
    controllerRef.current = null
    dispatch({ type: 'cancel' })
  }, [])

  const start = useCallback((query: string) => {
    const requestId = requestIdRef.current + 1
    requestIdRef.current = requestId
    controllerRef.current?.abort()
    const controller = new AbortController()
    controllerRef.current = controller
    dispatch({ type: 'start', query })

    void streamAnswer(query, {
      signal: controller.signal,
      onEvent: (event) => {
        if (requestId !== requestIdRef.current) return
        dispatch({ type: 'event', event })
      },
    }).then(() => {
      if (requestId === requestIdRef.current) controllerRef.current = null
    }).catch((error: unknown) => {
      if (requestId !== requestIdRef.current || isAbortError(error)) return
      controllerRef.current = null
      dispatch({ type: 'networkError' })
    })
  }, [])

  const reset = useCallback(() => {
    controllerRef.current?.abort()
    controllerRef.current = null
    requestIdRef.current += 1
    dispatch({ type: 'reset' })
  }, [])

  useEffect(() => () => { controllerRef.current?.abort() }, [])

  return { state, start, stop, reset }
}
