import { createSseParser, type SseMessage } from './sse'

function parseAll(chunks: string[]): SseMessage[] {
  const out: SseMessage[] = []
  const p = createSseParser((m) => out.push(m))
  chunks.forEach((c) => p.push(c))
  p.end()
  return out
}

test('parses events split across arbitrary chunk boundaries', () => {
  const body = 'event: status\ndata: {"message":"hi"}\n\nevent: delta\ndata: {"text":"a"}\n\n'
  const whole = parseAll([body])
  const byChar = parseAll(body.split(''))
  expect(whole).toEqual([
    { event: 'status', data: '{"message":"hi"}' },
    { event: 'delta', data: '{"text":"a"}' },
  ])
  expect(byChar).toEqual(whole)
})

test('handles CRLF, comments (pings) and multi-line data', () => {
  const out = parseAll([': ping\r\n\r\nevent: x\r\ndata: one\r\ndata: two\r\n\r\n'])
  expect(out).toEqual([{ event: 'x', data: 'one\ntwo' }])
})

test('flushes a trailing event without a blank line on end()', () => {
  expect(parseAll(['data: last'])).toEqual([{ event: 'message', data: 'last' }])
})
