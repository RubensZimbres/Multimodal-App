export interface MediaRef {
  uri: string
  mime_type: string
}

export interface DemoAsset extends MediaRef {
  key: string
  title: string
  preview_url: string
}

export interface DemoSet {
  company: string
  ticker: string
  assets: DemoAsset[]
}

export interface PricePoint {
  date: string
  close: number
  volume: number
}

export interface Ratio {
  key: string
  name: string
  unit: string
  current: number | null
  prior: number | null
  change: number | null
  better_when: 'higher' | 'lower'
  basis: string
  improved: boolean | null
}

export interface RatioReport {
  ratios: Ratio[]
  checks: string[]
  notes: string[]
}

export interface UploadTicket {
  upload_url: string
  uri: string
  mime_type: string
  headers: Record<string, string>
}

export type AnalysisEvent =
  | { type: 'status'; message: string }
  | { type: 'tool_call'; name: string; args: Record<string, unknown> }
  | { type: 'data'; kind: 'prices'; payload: PricePoint[] }
  | { type: 'data'; kind: 'ratios'; payload: RatioReport }
  | { type: 'data'; kind: 'statement'; payload: Record<string, unknown> }
  | { type: 'delta'; text: string }
  | { type: 'done'; model?: string }
  | { type: 'error'; message: string }

export type SectionKey = 'market' | 'statement' | 'pricing' | 'earnings_call' | 'marketing'
