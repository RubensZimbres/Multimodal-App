import type { User } from 'firebase/auth'
import { Suspense, lazy, useEffect, useMemo, useState } from 'react'
import { AnalysisCard } from './components/AnalysisCard'
import { AuthGate, UserMenu } from './components/AuthGate'
import { RatiosTable } from './components/RatiosTable'
import { SourcePicker } from './components/SourcePicker'
import { useAnalysis } from './hooks/useAnalysis'
import { API_BASE, getDemo } from './lib/api'
import type { DemoSet, MediaRef, SectionKey } from './lib/types'

// Recharts is only needed once a market analysis returns prices.
const PriceChart = lazy(() => import('./components/PriceChart').then((m) => ({ default: m.PriceChart })))

type MediaKey = Exclude<SectionKey, 'market'>

const MEDIA_CARDS: { key: Exclude<MediaKey, 'statement'>; title: string; description: string; accept: string }[] = [
  {
    key: 'pricing',
    title: 'Pricing image',
    description: 'Reads a price table or product image and compares prices across markets.',
    accept: 'image/*',
  },
  {
    key: 'earnings_call',
    title: 'Earnings call',
    description: 'Listens to an earnings call: takeaways, guidance and the tone of each speaker.',
    accept: 'audio/*,video/*',
  },
  {
    key: 'marketing',
    title: 'Marketing video',
    description: 'Watches a campaign video: selling strategy, emotional appeal and audience.',
    accept: 'video/*',
  },
]

function Question({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <label className="question">
      <span>Extra question (optional)</span>
      <textarea rows={2} value={value} maxLength={2000} onChange={(e) => onChange(e.target.value)} />
    </label>
  )
}

function Workspace({ user }: { user: User | null }) {
  const [demo, setDemo] = useState<DemoSet | null>(null)
  const [uploadsEnabled, setUploadsEnabled] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [company, setCompany] = useState('Apple Inc.')
  const [ticker, setTicker] = useState('AAPL')
  const [media, setMedia] = useState<Partial<Record<MediaKey, MediaRef | null>>>({})
  const [questions, setQuestions] = useState<Partial<Record<SectionKey, string>>>({})

  const market = useAnalysis('market')
  const statement = useAnalysis('statement')
  const pricing = useAnalysis('media')
  const earnings = useAnalysis('media')
  const marketing = useAnalysis('media')
  const synthesis = useAnalysis('synthesis')
  const mediaRuns = { pricing, earnings_call: earnings, marketing }

  useEffect(() => {
    getDemo()
      .then((d) => {
        setDemo(d)
        setMedia(Object.fromEntries(d.assets.map((a) => [a.key, { uri: a.uri, mime_type: a.mime_type }])))
      })
      .catch((e: unknown) => setLoadError(`Cannot reach the API at ${API_BASE || 'this origin'}: ${String(e)}`))
    fetch(`${API_BASE}/api/health`)
      .then((r) => r.json())
      .then((h: { uploads?: boolean }) => setUploadsEnabled(Boolean(h.uploads)))
      .catch(() => setUploadsEnabled(false))
  }, [])

  const demoAsset = (key: string) => demo?.assets.find((a) => a.key === key)
  const setMediaFor = (key: MediaKey) => (m: MediaRef | null) => setMedia((prev) => ({ ...prev, [key]: m }))
  const question = (key: SectionKey) => questions[key]?.trim() || undefined
  const setQuestion = (key: SectionKey) => (v: string) => setQuestions((prev) => ({ ...prev, [key]: v }))

  const sections = useMemo(() => {
    const done = {
      market: market.state,
      statement: statement.state,
      pricing: pricing.state,
      earnings_call: earnings.state,
      marketing: marketing.state,
    }
    return Object.fromEntries(
      Object.entries(done)
        .filter(([, s]) => s.phase === 'done' && s.text)
        .map(([k, s]) => [k, s.text]),
    )
  }, [market.state, statement.state, pricing.state, earnings.state, marketing.state])
  const completed = Object.keys(sections).length

  return (
    <>
      <header className="topbar">
        <div className="brand">
          <span className="logo" aria-hidden>
            ◆
          </span>
          Multimodal Analyst
        </div>
        <UserMenu user={user} />
      </header>

      <main>
        <section className="company">
          <label>
            <span>Company</span>
            <input value={company} onChange={(e) => setCompany(e.target.value)} maxLength={120} />
          </label>
          <label>
            <span>Ticker</span>
            <input
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              maxLength={12}
              className="ticker"
            />
          </label>
          {demo && (
            <p className="hint">
              Demo files are {demo.company}&apos;s Q2 FY24 results. Upload your own files to analyze another
              company.
            </p>
          )}
          {loadError && <p className="error-text">{loadError}</p>}
        </section>

        <div className="grid">
          <AnalysisCard
            title="Market & news"
            description="Gemini calls Alpha Vantage tools for quote, fundamentals, 6-month prices and news sentiment."
            state={market.state}
            canRun={Boolean(ticker.trim())}
            onRun={() => market.run({ ticker, question: question('market') })}
            onCancel={market.cancel}
            extra={
              market.state.prices && (
                <Suspense fallback={<p className="hint">Loading chart…</p>}>
                  <PriceChart ticker={ticker} points={market.state.prices} />
                </Suspense>
              )
            }
          >
            <Question value={questions.market ?? ''} onChange={setQuestion('market')} />
          </AnalysisCard>

          <AnalysisCard
            title="Financial statement"
            description="Extracts the figures from a PDF; ratios are computed in code, then explained by Gemini."
            state={statement.state}
            canRun={Boolean(media.statement)}
            onRun={() => media.statement && statement.run({ document: media.statement })}
            onCancel={statement.cancel}
            extra={statement.state.ratios && <RatiosTable report={statement.state.ratios} unit="millions" />}
          >
            <SourcePicker
              demo={demoAsset('statement')}
              accept="application/pdf"
              value={media.statement ?? null}
              onChange={setMediaFor('statement')}
              uploadsEnabled={uploadsEnabled}
            />
          </AnalysisCard>

          {MEDIA_CARDS.map((card) => {
            const run = mediaRuns[card.key]
            const ref = media[card.key]
            return (
              <AnalysisCard
                key={card.key}
                title={card.title}
                description={card.description}
                state={run.state}
                canRun={Boolean(ref && company.trim())}
                onRun={() =>
                  ref &&
                  run.run({ media: [ref], task: card.key, company, question: question(card.key) })
                }
                onCancel={run.cancel}
              >
                <SourcePicker
                  demo={demoAsset(card.key)}
                  accept={card.accept}
                  value={ref ?? null}
                  onChange={setMediaFor(card.key)}
                  uploadsEnabled={uploadsEnabled}
                />
                <Question value={questions[card.key] ?? ''} onChange={setQuestion(card.key)} />
              </AnalysisCard>
            )
          })}
        </div>

        <div className="synthesis">
          <AnalysisCard
            title="Strategic synthesis"
            description={`Cross-checks the analyses for contradictions and recommends strategy changes. ${completed}/5 analyses ready.`}
            state={synthesis.state}
            canRun={completed > 0 && Boolean(company.trim())}
            onRun={() => synthesis.run({ company, sections })}
            onCancel={synthesis.cancel}
            runLabel="Write the report"
          />
        </div>
      </main>
    </>
  )
}

export default function App() {
  return <AuthGate>{(user) => <Workspace user={user} />}</AuthGate>
}
