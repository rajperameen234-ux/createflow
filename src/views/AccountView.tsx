import { useState } from 'react'
import { CloudCog, Database, HardDrive, LogIn, LogOut, ShieldCheck, UserPlus } from 'lucide-react'
import type { HealthResponse } from '../types'
import { useSession } from '../lib/session'
import { Notice, Pill, SectionHeading, Spinner, StatusDot } from '../components/ui'

interface Props {
  health: HealthResponse | null
  onRefresh: () => void
}

export function AccountView({ health, onRefresh }: Props) {
  const session = useSession()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [confirmation, setConfirmation] = useState(false)

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setError(null)
    setConfirmation(false)
    if (!session.configured) {
      setError('Supabase env vars are missing in this frontend build.')
      return
    }
    if (!email.trim() || password.length < 6) {
      setError('Enter an email address and a password of at least 6 characters.')
      return
    }
    setBusy(true)
    try {
      if (mode === 'signin') {
        await session.signIn(email.trim(), password)
      } else {
        const outcome = await session.signUp(email.trim(), password)
        setConfirmation(outcome.needsConfirmation)
      }
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const cloudReady = Boolean(health?.cloud_configured)

  return (
    <div className="space-y-6">
      <SectionHeading
        eyebrow="Account"
        title="Account and cloud"
        description="Sign in to save projects, keep generated files in private storage and download them with short-lived signed URLs."
      />

      {!session.configured ? (
        <Notice tone="warning" title="Supabase is not configured in this frontend build">
          Set <code className="font-mono">VITE_SUPABASE_URL</code> and{' '}
          <code className="font-mono">VITE_SUPABASE_ANON_KEY</code> in{' '}
          <code className="font-mono">frontend/.env</code>, then restart the dev server. Only the
          publishable key belongs there — never the secret key.
        </Notice>
      ) : null}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,24rem)_minmax(0,1fr)]">
        <div className="surface p-4">
          {session.token ? (
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-md border border-state-ok/25 bg-state-ok/10 text-state-ok">
                  <ShieldCheck className="h-4 w-4" aria-hidden />
                </span>
                <div className="min-w-0">
                  <p className="text-[13px] font-medium text-fg">Signed in</p>
                  <p className="truncate text-xs text-fg-muted">{session.email}</p>
                </div>
              </div>
              <StatusDot tone="ok">Projects save to your account</StatusDot>
              <button type="button" className="btn-secondary w-full" onClick={() => void session.signOut()}>
                <LogOut className="h-3.5 w-3.5" aria-hidden />
                Sign out
              </button>
              <p className="text-2xs leading-relaxed text-fg-ghost">
                Row level security scopes every row to your user id, and the API checks ownership
                before any project is read, changed or downloaded.
              </p>
            </div>
          ) : (
            <form className="space-y-4" onSubmit={submit} noValidate>
              <div>
                <p className="text-[13px] font-medium text-fg">
                  {mode === 'signin' ? 'Sign in' : 'Create an account'}
                </p>
                <p className="mt-1 text-2xs text-fg-ghost">
                  {mode === 'signin'
                    ? 'Use the account that owns your projects.'
                    : 'Accounts are created through Supabase Auth.'}
                </p>
              </div>

              <label className="block space-y-1.5">
                <span className="field-label">Email</span>
                <input
                  className="field"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@studio.com"
                />
              </label>

              <label className="block space-y-1.5">
                <span className="field-label">Password</span>
                <input
                  className="field"
                  type="password"
                  autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 6 characters"
                />
              </label>

              {error ? <Notice tone="error">{error}</Notice> : null}
              {confirmation ? (
                <Notice tone="success" title="Check your inbox">
                  Confirm the address from the email Supabase sent, then sign in.
                </Notice>
              ) : null}

              <button type="submit" className="btn-primary w-full" disabled={busy}>
                {busy ? (
                  <Spinner />
                ) : mode === 'signin' ? (
                  <LogIn className="h-3.5 w-3.5" aria-hidden />
                ) : (
                  <UserPlus className="h-3.5 w-3.5" aria-hidden />
                )}
                {mode === 'signin' ? 'Sign in' : 'Create account'}
              </button>

              <button
                type="button"
                className="btn-ghost w-full text-xs"
                onClick={() => {
                  setMode(mode === 'signin' ? 'signup' : 'signin')
                  setError(null)
                }}
              >
                {mode === 'signin' ? 'Need an account? Sign up' : 'Already registered? Sign in'}
              </button>
            </form>
          )}
        </div>

        <div className="space-y-4">
          <div className="surface p-4">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-[13px] font-medium text-fg">Connection</h3>
              <button type="button" className="btn-ghost btn-sm" onClick={onRefresh}>
                Refresh
              </button>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between border-b border-white/[0.06] pb-2">
                <StatusDot tone={cloudReady ? 'ok' : 'warn'}>
                  Supabase {cloudReady ? 'connected' : 'not configured'}
                </StatusDot>
                <span className="num">{health?.version ?? '—'}</span>
              </div>
              <div className="flex flex-wrap gap-1.5 pt-1">
                {health
                  ? Object.entries(health.capabilities).map(([key, value]) => (
                      <Pill key={key} tone={value === true ? 'success' : 'neutral'}>
                        {key.replace(/_/g, ' ')}
                      </Pill>
                    ))
                  : (
                    <span className="text-2xs text-fg-ghost">Waiting for /api/health.</span>
                  )}
              </div>
            </div>
          </div>

          <div className="surface p-4">
            <div className="mb-3 flex items-center gap-2">
              <Database className="h-3.5 w-3.5 text-fg-ghost" aria-hidden />
              <h3 className="text-[13px] font-medium text-fg">Where your work lives</h3>
            </div>
            <ul className="space-y-2.5">
              {[
                <HardDrive key="a" />,
                <ShieldCheck key="b" />,
                <CloudCog key="c" />,
              ].map((icon, i) => (
                <li key={i} className="flex items-start gap-2.5 text-xs leading-relaxed text-fg-muted">
                  <span className="mt-[1px] shrink-0 text-fg-ghost">{icon}</span>
                  {[
                    <>
                      Supabase Storage bucket <code className="font-mono">createflow-assets</code>,
                      private by default, reached through short-lived signed URLs.
                    </>,
                    <>
                      Row level security restricts <code className="font-mono">projects</code> and{' '}
                      <code className="font-mono">generated_assets</code> to their owner.
                    </>,
                    <>
                      Nothing is kept in localStorage or IndexedDB. Temporary files are removed after
                      upload or when they expire.
                    </>,
                  ][i]}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}