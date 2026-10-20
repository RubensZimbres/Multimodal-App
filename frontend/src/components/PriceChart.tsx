import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { PricePoint } from '../lib/types'

export function PriceChart({ ticker, points }: { ticker: string; points: PricePoint[] }) {
  if (points.length < 2) return null
  const first = points[0].close
  const last = points[points.length - 1].close
  const change = ((last - first) / first) * 100
  return (
    <figure className="chart">
      <figcaption>
        {ticker} weekly close · {points[0].date} → {points[points.length - 1].date}{' '}
        <span className={change >= 0 ? 'up' : 'down'}>
          {change >= 0 ? '+' : ''}
          {change.toFixed(1)}%
        </span>
      </figcaption>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={40} stroke="var(--muted)" />
          <YAxis domain={['auto', 'auto']} tick={{ fontSize: 11 }} width={48} stroke="var(--muted)" />
          <Tooltip
            contentStyle={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
            formatter={(v) => [`$${Number(v).toFixed(2)}`, 'Close']}
          />
          <Line type="monotone" dataKey="close" stroke="var(--accent)" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </figure>
  )
}
