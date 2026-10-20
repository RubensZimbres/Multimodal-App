import { initialState, reducer, type AnalysisState } from './useAnalysis'

test('accumulates a streamed analysis', () => {
  let s: AnalysisState = reducer(initialState, { type: 'start' })
  s = reducer(s, { type: 'tool_call', name: 'get_stock_quote', args: { ticker: 'AAPL' } })
  s = reducer(s, { type: 'data', kind: 'prices', payload: [{ date: '2024-01-01', close: 1, volume: 1 }] })
  s = reducer(s, { type: 'delta', text: 'Hello ' })
  s = reducer(s, { type: 'delta', text: 'world' })
  s = reducer(s, { type: 'done', model: 'gemini-x' })

  expect(s.phase).toBe('done')
  expect(s.text).toBe('Hello world')
  expect(s.toolCalls).toHaveLength(1)
  expect(s.prices).toHaveLength(1)
  expect(s.model).toBe('gemini-x')
})

test('restarting clears the previous result', () => {
  const finished = { ...initialState, phase: 'done' as const, text: 'old', error: 'x' }
  const s = reducer(finished, { type: 'start' })
  expect(s).toMatchObject({ phase: 'running', text: '' })
  expect(s.error).toBeUndefined()
})

test('server error events end the run', () => {
  const s = reducer(reducer(initialState, { type: 'start' }), { type: 'error', message: 'quota' })
  expect(s).toMatchObject({ phase: 'error', error: 'quota' })
})
