import { render, screen } from '@testing-library/react'
import { formatValue } from '../lib/format'
import { RatiosTable } from './RatiosTable'

test('formats by unit', () => {
  expect(formatValue(46.578, '%')).toBe('46.6%')
  expect(formatValue(1.0371, 'x')).toBe('1.04×')
  expect(formatValue(104590, 'millions')).toBe('104,590')
  expect(formatValue(null, '%')).toBe('—')
})

test('shows trend direction, checks and notes', () => {
  render(
    <RatiosTable
      report={{
        ratios: [
          {
            key: 'financial_leverage',
            name: 'Financial leverage',
            unit: 'x',
            current: 4.55,
            prior: 5.67,
            change: -1.12,
            better_when: 'lower',
            basis: 'Mar vs Sep',
            improved: true,
          },
        ],
        checks: ['assets do not balance'],
        notes: ['Balance sheet compared with September'],
      }}
    />,
  )
  expect(screen.getByText('▲ better')).toBeInTheDocument()
  expect(screen.getByText(/assets do not balance/)).toBeInTheDocument()
  expect(screen.getByText('Balance sheet compared with September')).toBeInTheDocument()
})
