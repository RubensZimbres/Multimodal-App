import type { ReactNode } from 'react'
import type { AnalysisState } from '../hooks/useAnalysis'
import { Markdown } from './Markdown'

interface Props {
  title: string
  description: string
  state: AnalysisState
  canRun: boolean
  onRun: () => void
  onCancel: () => void
  children?: ReactNode
  extra?: ReactNode
  runLabel?: string
}

export function AnalysisCard({
  title,
  description,
  state,
  canRun,
  onRun,
  onCancel,
  children,
  extra,
  runLabel = 'Run analysis',
}: Props) {
  const running = state.phase === 'running'
  return (
    <section className="card" aria-label={title} aria-busy={running}>
      <header>
        <h2>{title}</h2>
        <p>{description}</p>
      </header>

      {children}

      <div className="actions">
        {running ? (
          <button type="button" className="secondary" onClick={onCancel}>
            Cancel
          </button>
        ) : (
          <button type="button" onClick={onRun} disabled={!canRun}>
            {state.phase === 'idle' ? runLabel : 'Run again'}
          </button>
        )}
        {running && (
          <span className="status" role="status">
            <span className="spinner" aria-hidden /> {state.status}
          </span>
        )}
      </div>

      {state.toolCalls.length > 0 && (
        <ul className="chips" aria-label="Tool calls">
          {state.toolCalls.map((c, i) => (
            <li key={i}>
              {c.name}({Object.values(c.args).join(', ')})
            </li>
          ))}
        </ul>
      )}

      {extra}
      {state.text && <Markdown text={state.text} />}
      {state.phase === 'error' && (
        <p className="error-text" role="alert">
          {state.error}
        </p>
      )}
      {state.model && <p className="hint">Written by {state.model}</p>}
    </section>
  )
}
