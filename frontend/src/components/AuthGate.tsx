import type { User } from 'firebase/auth'
import { useEffect, useState, type ReactNode } from 'react'
import { authEnabled, logOut, signIn, watchUser } from '../lib/firebase'

export function AuthGate({ children }: { children: (user: User | null) => ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [ready, setReady] = useState(!authEnabled)
  const [error, setError] = useState<string | null>(null)

  useEffect(
    () =>
      watchUser((u) => {
        setUser(u)
        setReady(true)
      }),
    [],
  )

  if (!ready) return <p className="center">Loading…</p>
  if (authEnabled && !user) {
    return (
      <div className="center signin">
        <h1>Multimodal Analyst</h1>
        <p>Analyze a company from its filings, prices, news, images, audio and video with Gemini.</p>
        <button
          type="button"
          onClick={() => signIn().catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))}
        >
          Sign in with Google
        </button>
        {error && <p className="error-text">{error}</p>}
      </div>
    )
  }
  return <>{children(user)}</>
}

export function UserMenu({ user }: { user: User | null }) {
  if (!user) return <span className="badge">Local dev mode</span>
  return (
    <div className="user">
      <span>{user.displayName ?? user.email}</span>
      <button type="button" className="secondary" onClick={() => logOut()}>
        Sign out
      </button>
    </div>
  )
}
