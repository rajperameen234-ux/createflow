import { useCallback, useEffect, useRef, useState } from 'react'
import {
  FolderOpen,
  LayoutGrid,
  LogOut,
  Palette,
  Plus,
  UserRound,
} from 'lucide-react'
import type { Brief, GenerateResponse, HealthResponse, ProjectDetail, ProjectSummary } from './types'
import { ApiError } from './types'
import { api } from './api'
import { DEFAULT_BRIEF, validateBrief, type ValidationErrors } from './lib/presets'
import { useSession } from './lib/session'
import { BriefErrorSummary, BriefForm } from './components/BriefForm'
import { LivePreview } from './components/LivePreview'
import { ResultsStudio } from './components/ResultsStudio'
import {
  Notice,
  SectionHeading,
  Skeleton,
  StatusDot,
} from './components/ui'
import { AccountView } from './views/AccountView'
import { BrandView } from './views/BrandView'

type View = 'create' | 'projects' | 'brand' | 'account'

const NAV = [
  { id: 'create' as const, label: 'New project', icon: Plus },
  { id: 'projects' as const, label: 'Projects', icon: FolderOpen },
  { id: 'brand' as const, label: 'Style system', icon: Palette },
  { id: 'account' as const, label: 'Account', icon: UserRound },
]

const GEN_STEPS = [
  'Reading the brief',
  'Building the narrative outline',
  'Composing the deck',
  'Rendering poster and social graphic',
  'Uploading to cloud',
]

export default function App() {
  const session = useSession()
  const [view, setView] = useState<View>('create')
  const [brief, setBrief] = useState<Brief>(DEFAULT_BRIEF)
  const [errors, setErrors] = useState<ValidationErrors>({})
  const [serverProblems, setServerProblems] = useState<Record<string, string>>({})
  const [generalError, setGeneralError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [phase, setPhase] = useState<string | null>(null)
  const [stepIndex, setStepIndex] = useState(0)
  const [result, setResult] = useState<GenerateResponse | null>(null)
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [healthError, setHealthError] = useState<string | null>(null)
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null)
  const [projectsError, setProjectsError] = useState<string | null>(null)
  const [selected, setSelected] = useState<ProjectDetail | null>(null)
  const [projectLoading, setProjectLoading] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const cloudReady = Boolean(health?.cloud_configured)

  const refreshHealth = useCallback(() => {
    void api
      .health()
      .then((data) => {
        setHealth(data)
        setHealthError(null)
      })
      .catch((err: Error) => {
        setHealth(null)
        setHealthError(err.message)
      })
  }, [])

  useEffect(refreshHealth, [refreshHealth])

  useEffect(() => {
    if (view !== 'projects') return
    if (!session.token) {
      setProjects([])
      setProjectsError(null)
      return
    }
    const controller = new AbortController()
    setProjectsError(null)
    api
      .projects(session.token, controller.signal)
      .then(setProjects)
      .catch((err: Error) => {
        if (err.name === 'AbortError') return
        setProjects([])
        setProjectsError(err.message)
      })
    return () => controller.abort()
  }, [view, session.token])

  const runGeneration = useCallback(
    async (payload: Brief) => {
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      setBusy(true)
      setGeneralError(null)
      setServerProblems({})
      setStepIndex(0)

      let step = 0
      const ticker = window.setInterval(() => {
        step = Math.min(step + 1, GEN_STEPS.length - 1)
        setStepIndex(step)
        setPhase(GEN_STEPS[step])
      }, 850)

      try {
        const data = await api.generate(payload, session.token, controller.signal)
        setResult(data)
        refreshHealth()
        return data
      } catch (err) {
        if ((err as Error)?.name === 'AbortError') return null
        if (err instanceof ApiError && err.problems.length) {
          const mapped: Record<string, string> = {}
          err.problems.forEach((problem) => {
            mapped[problem.field] = problem.message
          })
          setServerProblems(mapped)
          setGeneralError('The API rejected some fields. Review the highlighted inputs.')
        } else {
          setGeneralError((err as Error).message)
        }
        return null
      } finally {
        window.clearInterval(ticker)
        setBusy(false)
        setPhase(null)
        setStepIndex(0)
      }
    },
    [refreshHealth, session.token],
  )

  const handleSubmit = useCallback(() => {
    const found = validateBrief(brief)
    setErrors(found)
    if (Object.keys(found).length) {
      setGeneralError('Complete the highlighted fields before generating.')
      window.setTimeout(() => {
        document
          .querySelector('[data-invalid="true"]')
          ?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }, 40)
      return
    }
    setGeneralError(null)
    void runGeneration(brief)
  }, [brief, runGeneration])

  const loadProject = useCallback(
    async (id: string) => {
      if (!session.token) return
      setProjectLoading(true)
      setResult(null)
      try {
        const detail = await api.project(id, session.token)
        setSelected(detail)
        setBrief({
          ...DEFAULT_BRIEF,
          ...(detail.brief as Partial<Brief>),
          project_name: detail.project_name,
          topic: detail.topic,
          audience: detail.audience,
          goal: detail.goal,
          tone: detail.tone,
          presentation_type: detail.presentation_type,
          presentation_length: detail.slide_count || DEFAULT_BRIEF.presentation_length,
          visual_style: detail.visual_style,
          style_preset: detail.style_preset,
          primary_color: detail.primary_color,
          secondary_color: detail.secondary_color,
          brand_name: detail.brand_name,
          tagline: detail.tagline,
          extra_instructions: detail.extra_instructions,
        })
        setView('create')
      } catch (err) {
        setGeneralError((err as Error).message)
      } finally {
        setProjectLoading(false)
      }
    },
    [session.token],
  )

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[var(--cf-rail)_1fr]">
      {/* ---------------------------------------------------------------
          Rail: narrow, quiet, always in the same place
          --------------------------------------------------------------- */}
      <aside className="sticky top-0 z-30 border-b border-white/[0.07] bg-base-1000 lg:h-screen lg:border-b-0 lg:border-r">
        <div className="flex h-full flex-col px-3 py-3">
          <a
            href="#main"
            className="mb-5 flex items-center gap-2.5 rounded-md px-2 py-1.5"
          >
            <span className="flex h-6 w-6 items-center justify-center rounded-[5px] bg-brass-400 text-[11px] font-bold text-base-1000">
              CF
            </span>
            <span className="flex min-w-0 flex-col leading-none">
              <span className="text-[13px] font-semibold tracking-[-0.01em] text-fg">
                CreateFlow
              </span>
              <span className="mt-[3px] text-[10px] text-fg-ghost">Creative studio</span>
            </span>
          </a>

          <nav className="-mx-1 flex gap-0.5 overflow-x-auto pb-1 lg:flex-col lg:overflow-visible">
            {NAV.map((item) => {
              const Icon = item.icon
              const active = view === item.id
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setView(item.id)}
                  aria-current={active ? 'page' : undefined}
                  className={`rail-item shrink-0 ${active ? 'rail-item-active' : ''}`}
                >
                  <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden />
                  {item.label}
                  {item.id === 'projects' && projects?.length ? (
                    <span className="num ml-auto rounded border border-white/[0.09] px-1">
                      {projects.length}
                    </span>
                  ) : null}
                </button>
              )
            })}
          </nav>

          <div className="mt-auto hidden space-y-3 px-2 pt-6 lg:block">
            <div className="hairline-t space-y-2 pt-3">
              <StatusDot tone={cloudReady ? 'ok' : 'warn'}>
                {cloudReady ? 'Cloud connected' : 'Local mode'}
              </StatusDot>
              <p className="text-[10px] leading-relaxed text-fg-ghost">
                {cloudReady
                  ? 'Projects and files persist to Supabase.'
                  : 'Generation works locally. Nothing is saved until Supabase is configured.'}
              </p>
            </div>

            {session.email ? (
              <div className="hairline-t space-y-1.5 pt-3">
                <p className="truncate text-[11px] text-fg-muted">{session.email}</p>
                <button
                  type="button"
                  className="btn-ghost btn-sm w-full justify-start !px-1.5"
                  onClick={() => void session.signOut()}
                >
                  <LogOut className="h-3 w-3" aria-hidden />
                  Sign out
                </button>
              </div>
            ) : (
              <button
                type="button"
                className="btn-secondary btn-sm w-full"
                onClick={() => setView('account')}
              >
                Sign in
              </button>
            )}
          </div>
        </div>
      </aside>

      <div className="min-w-0">
        {/* -----------------------------------------------------------
            Top bar: contextual, one row, no decoration
            ----------------------------------------------------------- */}
        <header className="sticky top-0 z-20 hairline-b bg-base-1000/85 backdrop-blur-xl">
          <div className="flex h-[var(--cf-topbar)] items-center gap-3 px-4 sm:px-6">
            <div className="min-w-0 flex-1">
              <h2 className="truncate text-[13px] font-medium text-fg">
                {view === 'create'
                  ? result
                    ? result.assets[0]?.filename.replace(/\.(pptx|png|svg)$/i, '') || brief.project_name
                    : brief.project_name || 'Untitled project'
                  : NAV.find((n) => n.id === view)?.label}
              </h2>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <StatusDot tone={cloudReady ? 'ok' : 'idle'}>
                {health?.version ? `API ${health.version}` : 'API offline'}
              </StatusDot>
              {view !== 'create' ? (
                <button
                  type="button"
                  className="btn-secondary btn-sm"
                  onClick={() => {
                    setResult(null)
                    setView('create')
                  }}
                >
                  <Plus className="h-3 w-3" aria-hidden />
                  New
                </button>
              ) : null}
            </div>
          </div>
        </header>

        <main id="main" className="px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <div className="mx-auto w-full max-w-[1500px] space-y-5">
            {healthError ? (
              <Notice
                tone="error"
                title="Backend unreachable"
                action={
                  <button type="button" className="btn-secondary btn-sm" onClick={refreshHealth}>
                    Retry
                  </button>
                }
              >
                {healthError}
              </Notice>
            ) : null}

            {health && !health.cloud_configured ? (
              <Notice tone="warning" title="Cloud saving is off">
                {health.cloud_message} You can still generate a full package — the files are
                temporary and labelled as such.
              </Notice>
            ) : null}

            {view === 'create' ? (
              result ? (
                <ResultsStudio
                  result={result}
                  brief={brief}
                  token={session.token}
                  regenerating={busy}
                  onRegenerate={() => void runGeneration(brief)}
                  onEditBrief={() => setResult(null)}
                />
              ) : (
                <div className="space-y-6">
                  <SectionHeading
                    eyebrow="Creative brief"
                    title="New project"
                    description="One brief produces an editable deck, a poster, a social graphic and a vector mark that share a single visual identity."
                  />

                  <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_23rem]">
                    <div className="min-w-0 space-y-4">
                      {Object.keys(errors).length || Object.keys(serverProblems).length ? (
                        <BriefErrorSummary errors={{ ...errors, ...serverProblems }} />
                      ) : null}
                      <BriefForm
                        brief={brief}
                        onChange={setBrief}
                        onSubmit={handleSubmit}
                        busy={busy}
                        errors={errors}
                        serverProblems={serverProblems}
                        generalError={generalError}
                        phase={phase}
                      />
                    </div>

                    <aside className="space-y-4 xl:sticky xl:top-[calc(var(--cf-topbar)+1.5rem)]">
                      {busy ? (
                        <div className="surface p-4">
                          <div className="mb-3 flex items-center gap-2">
                            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brass-400" />
                            <p className="text-sm font-medium text-fg">{phase ?? 'Working'}</p>
                          </div>
                          <ProgressStepsInline steps={GEN_STEPS} activeIndex={stepIndex} />
                        </div>
                      ) : null}
                      <LivePreview brief={brief} />
                    </aside>
                  </div>
                </div>
              )
            ) : null}

            {view === 'projects' ? (
              <div className="space-y-6">
                <SectionHeading
                  eyebrow="Library"
                  title="Projects"
                  description={
                    session.token
                      ? 'Every package saved to your Supabase account.'
                      : 'Sign in to load the projects saved to your account.'
                  }
                />

                {!session.configured ? (
                  <Notice tone="warning" title="Supabase is not configured">
                    Add <code className="font-mono">VITE_SUPABASE_URL</code> and{' '}
                    <code className="font-mono">VITE_SUPABASE_ANON_KEY</code> to{' '}
                    <code className="font-mono">frontend/.env</code>, then restart the dev server.
                  </Notice>
                ) : null}

                {session.configured && !session.token ? (
                  <Notice tone="info" title="Sign in to continue">
                    Use the Account panel to sign in with your Supabase credentials.
                  </Notice>
                ) : null}

                {projectsError ? (
                  <Notice tone="error" title="Could not load projects">
                    {projectsError}
                  </Notice>
                ) : null}

                {projectLoading ? (
                  <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                    {[0, 1, 2].map((i) => (
                      <Skeleton key={i} className="h-44" />
                    ))}
                  </div>
                ) : null}

                {projects && projects.length === 0 && session.token ? (
                  <Notice tone="info" title="No saved projects yet">
                    Generate a package while signed in and it will appear here with its slides and
                    files.
                  </Notice>
                ) : null}

                {projects && projects.length > 0 ? (
                  <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                    {projects.map((project) => (
                      <button
                        key={project.id}
                        type="button"
                        onClick={() => void loadProject(project.id)}
                        className="surface group overflow-hidden text-left transition-colors duration-150 hover:border-white/[0.16]"
                      >
                        <ProjectThumb project={project} />
                        <div className="space-y-2 border-t border-white/[0.07] p-3.5">
                          <p className="truncate text-sm font-medium text-fg">
                            {project.project_name}
                          </p>
                          <p className="line-clamp-2 text-xs leading-relaxed text-fg-muted">
                            {project.topic}
                          </p>
                          <div className="flex items-center gap-2 pt-1">
                            <span className="num">{project.slide_count} slides</span>
                            <span className="text-fg-ghost">·</span>
                            <span className="num">{project.asset_count} files</span>
                            <span className="num ml-auto">
                              {new Date(project.created_at).toLocaleDateString()}
                            </span>
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                ) : null}

                {selected ? (
                  <Notice tone="success" title={`Loaded “${selected.project_name}”`}>
                    The brief is open in the editor.{' '}
                    <button
                      type="button"
                      className="underline underline-offset-2"
                      onClick={() => setSelected(null)}
                    >
                      Dismiss
                    </button>
                  </Notice>
                ) : null}
              </div>
            ) : null}

            {view === 'brand' ? <BrandView health={health} /> : null}
            {view === 'account' ? <AccountView health={health} onRefresh={refreshHealth} /> : null}
          </div>
        </main>
      </div>
    </div>
  )
}

function ProgressStepsInline({ steps, activeIndex }: { steps: string[]; activeIndex: number }) {
  return (
    <ol className="space-y-0">
      {steps.map((step, i) => {
        const done = i < activeIndex
        const active = i === activeIndex
        return (
          <li key={step} className="relative flex gap-2.5 pb-3 last:pb-0">
            {i < steps.length - 1 ? (
              <span
                aria-hidden
                className={`absolute left-[6px] top-3.5 h-full w-px ${
                  done ? 'bg-state-ok/30' : 'bg-white/[0.07]'
                }`}
              />
            ) : null}
            <span
              className={`relative z-10 mt-[3px] h-[13px] w-[13px] shrink-0 rounded-full border ${
                done
                  ? 'border-state-ok/40 bg-state-ok/15'
                  : active
                    ? 'border-brass-400/50 bg-brass-400/20'
                    : 'border-white/[0.10]'
              }`}
            />
            <span
              className={`text-xs ${active ? 'font-medium text-fg' : done ? 'text-fg-muted' : 'text-fg-ghost'}`}
            >
              {step}
            </span>
          </li>
        )
      })}
    </ol>
  )
}

function ProjectThumb({ project }: { project: ProjectSummary }) {
  const [sheet, setSheet] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    let url: string | null = null
    void api
      .slideSheet(
        {
          project_name: project.project_name,
          topic: project.topic,
          // The library returns summaries; the thumbnail only needs the fields
          // it actually renders, so the rest fall back to sensible defaults.
          audience: 'Local customers',
          goal: 'Grow the business',
          tone: 'Professional',
          presentation_length: project.slide_count || 8,
          presentation_type: 'marketing',
          visual_style: '',
          style_preset: project.style_preset,
          primary_color: project.primary_color,
          secondary_color: project.secondary_color,
          accent_color: null,
          brand_name: project.brand_name,
          tagline: project.tagline,
          extra_instructions: '',
        },
        null,
        controller.signal,
      )
      .then((objectUrl) => {
        url = objectUrl
        setSheet(objectUrl)
      })
      .catch(() => setSheet(null))
    return () => {
      controller.abort()
      if (url) URL.revokeObjectURL(url)
    }
  }, [project.id, project.style_preset, project.primary_color, project.secondary_color,
      project.slide_count, project.brand_name, project.tagline, project.project_name, project.topic])

  return (
    <div className="artboard relative aspect-[16/7] overflow-hidden bg-base-1000">
      {sheet ? (
        <img
          src={sheet}
          alt=""
          className="h-full w-full object-cover object-top opacity-90 transition-opacity duration-300 group-hover:opacity-100"
        />
      ) : (
        <div className="flex h-full w-full items-center justify-center">
          <LayoutGrid className="h-4 w-4 text-fg-ghost" aria-hidden />
        </div>
      )}
    </div>
  )
}