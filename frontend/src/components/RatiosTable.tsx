import { formatValue } from '../lib/format'
import type { Ratio, RatioReport } from '../lib/types'

function Trend({ ratio }: { ratio: Ratio }) {
  if (ratio.improved === null) return <span className="trend">—</span>
  return (
    <span className={`trend ${ratio.improved ? 'up' : 'down'}`}>
      {ratio.improved ? '▲ better' : '▼ worse'}
    </span>
  )
}

export function RatiosTable({ report, unit }: { report: RatioReport; unit?: string }) {
  return (
    <div className="ratios">
      <table>
        <thead>
          <tr>
            <th>Ratio</th>
            <th>Current</th>
            <th>Prior</th>
            <th>Trend</th>
          </tr>
        </thead>
        <tbody>
          {report.ratios.map((r) => (
            <tr key={r.key} title={r.basis}>
              <td>{r.name}</td>
              <td>{formatValue(r.current, r.unit)}</td>
              <td>{formatValue(r.prior, r.unit)}</td>
              <td>
                <Trend ratio={r} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="hint">
        Computed in code from figures Gemini extracted{unit ? ` (amounts in ${unit})` : ''}. Hover a row for
        the periods compared.
      </p>
      {report.checks.map((c) => (
        <p key={c} className="warning">
          ⚠ {c}
        </p>
      ))}
      {report.notes.map((n) => (
        <p key={n} className="hint">
          {n}
        </p>
      ))}
    </div>
  )
}
