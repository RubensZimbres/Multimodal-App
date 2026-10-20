export function formatValue(value: number | null, unit: string): string {
  if (value === null) return '—'
  if (unit === '%') return `${value.toFixed(1)}%`
  if (unit === 'x') return `${value.toFixed(2)}×`
  return value.toLocaleString('en-US', { maximumFractionDigits: 0 })
}
