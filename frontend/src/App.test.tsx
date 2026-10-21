import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'

const demo = {
  company: 'Apple Inc.',
  ticker: 'AAPL',
  assets: [
    { key: 'statement', title: 'FY24 Q2', uri: 'gs://b/s.pdf', mime_type: 'application/pdf', preview_url: 'https://x/s.pdf' },
    { key: 'pricing', title: 'Prices', uri: 'gs://b/p.jpeg', mime_type: 'image/jpeg', preview_url: 'https://x/p.jpeg' },
    { key: 'earnings_call', title: 'Call', uri: 'gs://b/c.mp4', mime_type: 'video/mp4', preview_url: 'https://x/c.mp4' },
    { key: 'marketing', title: 'Ad', uri: 'gs://b/m.mp4', mime_type: 'video/mp4', preview_url: 'https://x/m.mp4' },
  ],
}

function sse(events: [string, unknown][]): Response {
  const text = events.map(([e, d]) => `event: ${e}\ndata: ${JSON.stringify(d)}\n\n`).join('')
  const stream = new ReadableStream({
    start(controller) {
      const bytes = new TextEncoder().encode(text)
      controller.enqueue(bytes.slice(0, 17))
      controller.enqueue(bytes.slice(17))
      controller.close()
    },
  })
  return new Response(stream, { headers: { 'Content-Type': 'text/event-stream' } })
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/api/demo')) return json(demo)
    if (url.endsWith('/api/health')) return json({ status: 'ok', uploads: false })
    if (url.endsWith('/api/analyses/statement'))
      return sse([
        ['status', { message: 'Extracting' }],
        ['data', { kind: 'ratios', payload: { ratios: [], checks: [], notes: ['Computed note'] } }],
        ['delta', { text: '## Margins ' }],
        ['delta', { text: 'improved' }],
        ['done', {}],
      ])
    if (url.endsWith('/api/analyses/synthesis')) {
      const body = JSON.parse(String(init?.body))
      return sse([
        ['delta', { text: `Synthesis of ${Object.keys(body.sections).join(',')}` }],
        ['done', { model: 'gemini-test' }],
      ])
    }
    if (url.endsWith('/api/analyses/market')) return json({ detail: 'Invalid ticker symbol' }, 422)
    throw new Error(`unexpected ${url}`)
  })
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => vi.unstubAllGlobals())

test('runs the demo statement analysis and feeds it to the synthesis', async () => {
  const user = userEvent.setup()
  render(<App />)

  const statementCard = await screen.findByRole('region', { name: 'Financial statement' })
  const synthesisCard = screen.getByRole('region', { name: 'Strategic synthesis' })
  expect(within(synthesisCard).getByRole('button', { name: 'Write the report' })).toBeDisabled()

  await waitFor(() => expect(within(statementCard).getByRole('button', { name: 'Run analysis' })).toBeEnabled())
  await user.click(within(statementCard).getByRole('button', { name: 'Run analysis' }))

  expect(await within(statementCard).findByRole('heading', { name: 'Margins improved' })).toBeInTheDocument()
  expect(within(statementCard).getByText('Computed note')).toBeInTheDocument()
  const [, init] = fetchMock.mock.calls.find(([u]) => String(u).endsWith('/statement'))!
  expect(JSON.parse(init.body).document).toEqual({ uri: 'gs://b/s.pdf', mime_type: 'application/pdf' })

  await user.click(within(synthesisCard).getByRole('button', { name: 'Write the report' }))
  expect(await within(synthesisCard).findByText('Synthesis of statement')).toBeInTheDocument()
  expect(within(synthesisCard).getByText('Written by gemini-test')).toBeInTheDocument()
})

test('shows API validation errors', async () => {
  const user = userEvent.setup()
  render(<App />)
  const card = await screen.findByRole('region', { name: 'Market & news' })
  await user.click(within(card).getByRole('button', { name: 'Run analysis' }))
  expect(await within(card).findByRole('alert')).toHaveTextContent('Invalid ticker symbol')
})

test('upload option is disabled when the backend has no bucket', async () => {
  render(<App />)
  const card = await screen.findByRole('region', { name: 'Pricing image' })
  await waitFor(() => expect(within(card).getByRole('radio', { name: 'Demo file' })).toBeChecked())
  expect(within(card).getByRole('radio', { name: 'Upload your own' })).toBeDisabled()
})
