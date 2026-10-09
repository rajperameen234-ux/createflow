import type { ReactNode } from 'react'
import { AlertTriangle, Check, Info, Loader2, X } from 'lucide-react'

export function Spinner({ className = 'h-3.5 w-3.5' }: { className?: string }) {
  return <Loader2 className={`${className} animate-spin`} aria-hidden />
}

export function Card({
  children,
  className = '',
}: {
  children: ReactNode
  className?: string
}) {
  return <div className={`surface ${className}`}>{children}</div>
}

export function SectionHeading({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string
  title: string
  description?: string
  actions?: ReactNode
}) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
      <div className="min-w-0 space-y-1.5">
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <h1 className="title-lg">{title}</h1>
        {description ? (
          <p className="max-w-2xl text-sm leading-relaxed text-fg-muted">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  )
}

type Tone = 'info' | 'success' | 'warning' | 'error'

const TONE: Record<Tone, { box: string; text: string; icon: ReactNode }> = {
  info: {
    box: 'border-state-info/25 bg-state-info/[0.07]',
    text: 'text-state-info',
    icon: <Info className="h-3.5 w-3.5" aria-hidden />,
  },
  success: {
    box: 'border-state-ok/25 bg-state-ok/[0.07]',
    text: 'text-state-ok',
    icon: <Check className="h-3.5 w-3.5" aria-hidden />,
  },
  warning: {
    box: 'border-state-warn/25 bg-state-warn/[0.07]',
    text: 'text-state-warn',
    icon: <AlertTriangle className="h-3.5 w-3.5" aria-hidden />,
  },
  error: {
    box: 'border-state-err/25 bg-state-err/[0.07]',
    text: 'text-state-err',
    icon: <AlertTriangle className="h-3.5 w-3.5" aria-hidden />,
  },
}

export function Notice({
  tone = 'info',
  title,
  children,
  onDismiss,
  action,
}: {
  tone?: Tone
  title?: string
  children: ReactNode
  onDismiss?: () => void
  action?: ReactNode
}) {
  const t = TONE[tone]
  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      className={`flex items-start gap-2.5 rounded-md border px-3 py-2.5 ${t.box} animate-fade-in`}
    >
      <span className={`mt-[3px] shrink-0 ${t.text}`}>{t.icon}</span>
      <div className="min-w-0 flex-1">
        {title ? <p className={`text-sm font-medium ${t.text}`}>{title}</p> : null}
        <div className="text-xs leading-relaxed text-fg-muted">{children}</div>
        {action ? <div className="mt-2">{action}</div> : null}
      </div>
      {onDismiss ? (
        <button
          type="button"
          onClick={onDismiss}
          className="-mr-1 -mt-1 shrink-0 rounded p-1 text-fg-ghost transition hover:bg-white/5 hover:text-fg"
          aria-label="Dismiss"
        >
          <X className="h-3.5 w-3.5" aria-hidden />
        </button>
      ) : null}
    </div>
  )
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon: ReactNode
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <div className="artboard flex flex-col items-center justify-center rounded-lg border border-dashed border-white/[0.09] px-6 py-16 text-center">
      <div className="mb-4 flex h-9 w-9 items-center justify-center rounded-md border border-white/[0.09] bg-white/[0.03] text-fg-muted">
        {icon}
      </div>
      <h3 className="text-base font-medium text-fg">{title}</h3>
      <p className="mt-1.5 max-w-sm text-sm leading-relaxed text-fg-muted">{description}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  )
}

export function Field({
  label,
  hint,
  error,
  children,
  required,
  htmlFor,
}: {
  label: string
  hint?: ReactNode
  error?: string
  children: ReactNode
  required?: boolean
  htmlFor?: string
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-3">
        <label className="field-label" htmlFor={htmlFor}>
          {label}
          {required ? <span className="ml-1 text-brass-400">*</span> : null}
        </label>
        {hint ? <span className="text-2xs text-fg-ghost">{hint}</span> : null}
      </div>
      {children}
      {error ? (
        <p className="field-error" role="alert">
          <AlertTriangle className="mt-[1px] h-3 w-3 shrink-0" aria-hidden />
          {error}
        </p>
      ) : null}
    </div>
  )
}

export type PillTone = 'neutral' | 'accent' | 'success' | 'warning' | 'error'

const PILL: Record<PillTone, string> = {
  neutral: 'border-white/[0.09] bg-white/[0.03] text-fg-muted',
  accent: 'border-brass-400/30 bg-brass-400/10 text-brass-300',
  success: 'border-state-ok/25 bg-state-ok/10 text-state-ok',
  warning: 'border-state-warn/25 bg-state-warn/10 text-state-warn',
  error: 'border-state-err/25 bg-state-err/10 text-state-err',
}

export function Pill({
  children,
  tone = 'neutral',
  className = '',
}: {
  children: ReactNode
  tone?: PillTone
  className?: string
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded border px-1.5 py-0.5 text-2xs font-medium ${PILL[tone]} ${className}`}
    >
      {children}
    </span>
  )
}

export function ProgressSteps({
  steps,
  activeIndex,
}: {
  steps: string[]
  activeIndex: number
}) {
  return (
    <ol className="space-y-0">
      {steps.map((step, i) => {
        const done = i < activeIndex
        const active = i === activeIndex
        return (
          <li key={step} className="relative flex gap-3 pb-4 last:pb-0">
            {i < steps.length - 1 ? (
              <span
                aria-hidden
                className={`absolute left-[7px] top-4 h-full w-px ${
                  done ? 'bg-state-ok/30' : 'bg-white/[0.07]'
                }`}
              />
            ) : null}
            <span
              className={`relative z-10 mt-[3px] flex h-[15px] w-[15px] shrink-0 items-center justify-center rounded-full border text-[9px] font-semibold ${
                done
                  ? 'border-state-ok/40 bg-state-ok/15 text-state-ok'
                  : active
                    ? 'border-brass-400/50 bg-brass-400/15 text-brass-300'
                    : 'border-white/[0.10] bg-base-900 text-fg-ghost'
              }`}
            >
              {done ? <Check className="h-2.5 w-2.5" aria-hidden /> : i + 1}
            </span>
            <span
              className={`text-xs transition-colors ${
                active ? 'font-medium text-fg' : done ? 'text-fg-muted' : 'text-fg-ghost'
              }`}
            >
              {step}
            </span>
          </li>
        )
      })}
    </ol>
  )
}

export function Meter({ value, total }: { value: number; total: number }) {
  const pct = total ? Math.round((value / total) * 100) : 0
  return (
    <div className="h-1 w-full overflow-hidden rounded-full bg-white/[0.07]">
      <div
        className="h-full origin-left rounded-full bg-brass-400 animate-bar-grow"
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

export function KeyValue({ items }: { items: { label: string; value: ReactNode }[] }) {
  return (
    <dl className="space-y-2">
      {items.map((item) => (
        <div key={item.label} className="flex items-baseline justify-between gap-3">
          <dt className="text-2xs text-fg-ghost">{item.label}</dt>
          <dd className="truncate text-right text-2xs font-medium text-fg-muted">{item.value}</dd>
        </div>
      ))}
    </dl>
  )
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`shimmer relative overflow-hidden rounded-md bg-white/[0.04] ${className}`} aria-hidden />
}

/** Small status dot + label used for cloud/auth state in the top bar. */
export function StatusDot({
  tone,
  children,
}: {
  tone: 'ok' | 'warn' | 'idle'
  children: ReactNode
}) {
  const color =
    tone === 'ok' ? 'bg-state-ok' : tone === 'warn' ? 'bg-state-warn' : 'bg-fg-ghost'
  return (
    <span className="inline-flex items-center gap-1.5 text-2xs text-fg-muted">
      <span className={`dot ${color}`} />
      {children}
    </span>
  )
}