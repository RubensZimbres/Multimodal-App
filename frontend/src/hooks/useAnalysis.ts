import { useCallback, useReducer, useRef } from 'react'
import { streamAnalysis } from '../lib/api'
import type { AnalysisEvent, PricePoint, RatioReport } from '../lib/types'

export interface AnalysisState {
  phase: 'idle' | 'running' | 'done' | 'error'
  status: string
  toolCalls: { name: string; args: Record<string, unknown> }[]
  text: string
  prices?: PricePoint[]
  ratios?: RatioReport
  model?: string
  error?: string
}

export const initialState: AnalysisState = { phase: 'idle', status: '', toolCalls: [], text: '' }

type Action = { type: 'start' } | { type: 'fail'; message: string } | AnalysisEvent

export function reducer(state: AnalysisState, action: Action): AnalysisState {
  switch (action.type) {
    case 'start':
      return { ...initialState, phase: 'running', status: 'Starting…' }
    case 'status':
      return { ...state, status: action.message }
    case 'tool_call':
      return {
        ...state,
        status: `Calling ${action.name}`,
        toolCalls: [...state.toolCalls, { name: action.name, args: action.args }],
      }
    case 'data':
      if (action.kind === 'prices') return { ...state, prices: action.payload }
      if (action.kind === 'ratios') return { ...state, ratios: action.payload }
      return state
    case 'delta':
      return { ...state, text: state.text + action.text }
    case 'done':
      return { ...state, phase: 'done', status: '', model: action.model }
    case 'error':
    case 'fail':
      return { ...state, phase: 'error', status: '', error: action.message }
  }
}

export function useAnalysis(path: string) {
  const [state, dispatch] = useReducer(reducer, initialState)
  const abort = useRef<AbortController | null>(null)

  const run = useCallback(
    async (body: unknown) => {
      abort.current?.abort()
      const controller = new AbortController()
      abort.current = controller
      dispatch({ type: 'start' })
      let finished = false
      try {
        await streamAnalysis(
          path,
          body,
          (event) => {
            if (event.type === 'done' || event.type === 'error') finished = true
            dispatch(event)
          },
          controller.signal,
        )
        if (!finished) dispatch({ type: 'fail', message: 'The connection closed before the analysis finished' })
      } catch (err) {
        if (controller.signal.aborted) return
        dispatch({ type: 'fail', message: err instanceof Error ? err.message : String(err) })
      }
    },
    [path],
  )

  const cancel = useCallback(() => {
    abort.current?.abort()
    dispatch({ type: 'fail', message: 'Cancelled' })
  }, [])

  return { state, run, cancel }
}
