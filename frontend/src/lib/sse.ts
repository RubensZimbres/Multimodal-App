export interface SseMessage {
  event: string
  data: string
}

export function createSseParser(onMessage: (msg: SseMessage) => void) {
  let buffer = ''

  const flush = (block: string) => {
    let event = 'message'
    const data: string[] = []
    for (const line of block.split('\n')) {
      if (line.startsWith(':')) continue
      const idx = line.indexOf(':')
      const field = idx === -1 ? line : line.slice(0, idx)
      let value = idx === -1 ? '' : line.slice(idx + 1)
      if (value.startsWith(' ')) value = value.slice(1)
      if (field === 'event') event = value
      else if (field === 'data') data.push(value)
    }
    if (data.length) onMessage({ event, data: data.join('\n') })
  }

  return {
    push(chunk: string) {
      buffer += chunk.replace(/\r\n?/g, '\n')
      let idx: number
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        flush(buffer.slice(0, idx))
        buffer = buffer.slice(idx + 2)
      }
    },
    end() {
      if (buffer.trim()) flush(buffer)
      buffer = ''
    },
  }
}
