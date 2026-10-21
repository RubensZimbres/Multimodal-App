import { getIdToken } from './firebase'
import { createSseParser } from './sse'
import type { AnalysisEvent, DemoSet, MediaRef, UploadTicket } from './types'

export const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function headers(): Promise<HeadersInit> {
  const token = await getIdToken()
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
}

async function errorFrom(resp: Response): Promise<ApiError> {
  let message = `${resp.status} ${resp.statusText}`
  try {
    const body = await resp.json()
    if (typeof body.detail === 'string') message = body.detail
    else if (Array.isArray(body.detail)) message = body.detail.map((d: { msg: string }) => d.msg).join('; ')
  } catch {
    return new ApiError(resp.status, message)
  }
  return new ApiError(resp.status, message)
}

export async function getDemo(): Promise<DemoSet> {
  const resp = await fetch(`${API_BASE}/api/demo`)
  if (!resp.ok) throw await errorFrom(resp)
  return resp.json()
}

export async function streamAnalysis(
  path: string,
  body: unknown,
  onEvent: (event: AnalysisEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const resp = await fetch(`${API_BASE}/api/analyses/${path}`, {
    method: 'POST',
    headers: await headers(),
    body: JSON.stringify(body),
    signal,
  })
  if (!resp.ok || !resp.body) throw await errorFrom(resp)

  const parser = createSseParser(({ event, data }) => {
    onEvent({ type: event, ...JSON.parse(data) } as AnalysisEvent)
  })
  const reader = resp.body.pipeThrough(new TextDecoderStream()).getReader()
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    parser.push(value)
  }
  parser.end()
}

export async function uploadFile(file: File): Promise<MediaRef> {
  const resp = await fetch(`${API_BASE}/api/uploads`, {
    method: 'POST',
    headers: await headers(),
    body: JSON.stringify({
      filename: file.name,
      mime_type: file.type || 'application/octet-stream',
      size: file.size,
    }),
  })
  if (!resp.ok) throw await errorFrom(resp)
  const ticket: UploadTicket = await resp.json()

  const put = await fetch(ticket.upload_url, { method: 'PUT', headers: ticket.headers, body: file })
  if (!put.ok) throw new ApiError(put.status, `Upload failed (${put.status})`)
  return { uri: ticket.uri, mime_type: ticket.mime_type }
}
