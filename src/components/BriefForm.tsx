import { useMemo, useState } from 'react'
import {
  AlertCircle,
  ChevronDown,
  Loader2,
  Minus,
  Palette,
  Plus,
  RotateCcw,
  Sparkles,
  Trash2,
  Upload,
  Wand2,
} from 'lucide-react'
import type { Brief, StylePresetId } from '../types'
import {
  DEFAULT_BRIEF,
  FIELD_LABELS,
  PRESENTATION_TYPES,
  PRESETS,
  TONE_SUGGESTIONS,
  presetById,
  type ValidationErrors,
} from '../lib/presets'
import { Field, Notice } from './ui'

const MAX_LOGO_BYTES = 4 * 1024 * 1024

interface Props {
  brief: Brief
  onChange: (brief: Brief) => void
  onSubmit: () => void
  busy: boolean
  errors: ValidationErrors
  serverProblems: Record<string, string>
  generalError: string | null
  phase: string | null
}

export function BriefForm({
  brief,
  onChange,
  onSubmit,
  busy,
  errors,
  serverProblems,
  generalError,
  phase,
}: Props) {
  const [open, setOpen] = useState({ story: true, look: true, brand: true, extra: false })
  const [logoPreview, setLogoPreview] = useState<string | null>(null)
  const [logoError, setLogoError] = useState<string | null>(null)

  const set = <K extends keyof Brief>(key: K, value: Brief[K]) =>
    onChange({ ...brief, [key]: value })

  const merged = useMemo(
    () => ({ ...errors, ...serverProblems }),
    [errors, serverProblems],
  )
  const invalidCount = Object.keys(merged).length

  const applyPreset = (id: StylePresetId) => {
    const preset = presetById(id)
    onChange({
      ...brief,
      style_preset: id,
      visual_style: preset.label,
      primary_color: preset.colors.primary,
      secondary_color: preset.colors.secondary,
      accent_color: preset.colors.accent,
    })
  }

  const handleLogo = async (file: File | null) => {
    setLogoError(null)
    if (!file) {
      set('logo_data_url', null)
      setLogoPreview(null)
      return
    }
    if (file.size > MAX_LOGO_BYTES) return setLogoError('Logo must be 4 MB or smaller.')
    if (!['image/png', 'image/jpeg', 'image/svg+xml', 'image/webp'].includes(file.type)) {
      return setLogoError('Use a PNG, JPG, WebP or SVG file.')
    }
    const reader = new FileReader()
    reader.onload = () => {
      const data = reader.result as string
      setLogoPreview(data)
      set('logo_data_url', data)
    }
    reader.onerror = () => setLogoError('The logo file could not be read.')
    reader.readAsDataURL(file)
  }

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault()
        onSubmit()
      }}
      noValidate
    >
      {generalError ? (
        <Notice tone="error" title="Generation blocked">
          {generalError}
        </Notice>
      ) : null}

      {/* ==========================================================
          Brief
          ========================================================== */}
      <Section
        step="01"
        title="The brief"
        subtitle="What the project is, who it serves, what it must achieve."
        open={open.story}
        onToggle={() => setOpen((s) => ({ ...s, story: !s.story }))}
      >
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={FIELD_LABELS.project_name} required error={merged.project_name} htmlFor="f-name">
              <input
                id="f-name"
                data-invalid={Boolean(merged.project_name)}
                className={`field ${merged.project_name ? 'field-invalid' : ''}`}
                value={brief.project_name}
                onChange={(e) => set('project_name', e.target.value)}
                placeholder="Bean House Coffee"
                maxLength={90}
              />
            </Field>
            <Field label={FIELD_LABELS.presentation_type} required htmlFor="f-type">
              <div className="relative">
                <select
                  id="f-type"
                  className="field cursor-pointer appearance-none pr-8"
                  value={brief.presentation_type}
                  onChange={(e) =>
                    set('presentation_type', e.target.value as Brief['presentation_type'])
                  }
                >
                  {PRESENTATION_TYPES.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.label} — {t.hint}
                    </option>
                  ))}
                </select>
                <ChevronDown
                  className="pointer-events-none absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-fg-ghost"
                  aria-hidden
                />
              </div>
            </Field>
          </div>

          <Field
            label={FIELD_LABELS.topic}
            required
            hint={`${brief.topic.length} / 1200`}
            error={merged.topic}
            htmlFor="f-topic"
          >
            <textarea
              id="f-topic"
              data-invalid={Boolean(merged.topic)}
              className={`field min-h-[112px] resize-y leading-relaxed ${
                merged.topic ? 'field-invalid' : ''
              }`}
              value={brief.topic}
              onChange={(e) => set('topic', e.target.value)}
              placeholder="Launching a modern coffee shop on the high street, built for people who want a carefully made cup and a calm place to sit for an hour."
              maxLength={1200}
            />
            <p className="field-help">
              This becomes the deck narrative, the poster headline and the social caption.
            </p>
          </Field>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={FIELD_LABELS.audience} required error={merged.audience} htmlFor="f-aud">
              <input
                id="f-aud"
                data-invalid={Boolean(merged.audience)}
                className={`field ${merged.audience ? 'field-invalid' : ''}`}
                value={brief.audience}
                onChange={(e) => set('audience', e.target.value)}
                placeholder="Young adults and local customers"
                maxLength={400}
              />
            </Field>
            <Field label={FIELD_LABELS.goal} required error={merged.goal} htmlFor="f-goal">
              <input
                id="f-goal"
                data-invalid={Boolean(merged.goal)}
                className={`field ${merged.goal ? 'field-invalid' : ''}`}
                value={brief.goal}
                onChange={(e) => set('goal', e.target.value)}
                placeholder="Fill 60 seats on weekday mornings in the first quarter"
                maxLength={400}
              />
            </Field>
          </div>

          <Field label={FIELD_LABELS.tone} required error={merged.tone} htmlFor="f-tone">
            <input
              id="f-tone"
              data-invalid={Boolean(merged.tone)}
              className={`field ${merged.tone ? 'field-invalid' : ''}`}
              value={brief.tone}
              onChange={(e) => set('tone', e.target.value)}
              placeholder="Premium, friendly, modern"
              maxLength={200}
              list="tone-suggestions"
            />
            <datalist id="tone-suggestions">
              {TONE_SUGGESTIONS.map((t) => (
                <option key={t} value={t} />
              ))}
            </datalist>
            <div className="flex flex-wrap gap-1.5 pt-1.5">
              {TONE_SUGGESTIONS.map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => set('tone', t)}
                  className={`rounded border px-2 py-1 text-2xs transition-colors ${
                    brief.tone === t
                      ? 'border-brass-400/40 bg-brass-400/10 text-brass-300'
                      : 'border-white/[0.09] text-fg-muted hover:border-white/20 hover:text-fg'
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </Field>

          <Field
            label={FIELD_LABELS.presentation_length}
            hint="5 – 16 slides"
            error={merged.presentation_length}
          >
            <div className="flex items-center gap-3">
              <button
                type="button"
                className="btn-secondary !h-8 !w-8 !px-0"
                onClick={() => set('presentation_length', Math.max(5, brief.presentation_length - 1))}
                aria-label="Fewer slides"
              >
                <Minus className="h-3 w-3" aria-hidden />
              </button>
              <input
                type="range"
                min={5}
                max={16}
                value={brief.presentation_length}
                onChange={(e) => set('presentation_length', Number(e.target.value))}
                className="h-1 flex-1 cursor-pointer appearance-none rounded-full bg-white/[0.09] accent-brass-400"
                aria-label="Number of slides"
              />
              <button
                type="button"
                className="btn-secondary !h-8 !w-8 !px-0"
                onClick={() => set('presentation_length', Math.min(16, brief.presentation_length + 1))}
                aria-label="More slides"
              >
                <Plus className="h-3 w-3" aria-hidden />
              </button>
              <span className="num w-14 shrink-0 text-right">
                {brief.presentation_length} slides
              </span>
            </div>
          </Field>
        </div>
      </Section>

      {/* ==========================================================
          Visual style
          ========================================================== */}
      <Section
        step="02"
        title="Visual style"
        subtitle="A starting identity. Every colour stays editable afterwards."
        open={open.look}
        onToggle={() => setOpen((s) => ({ ...s, look: !s.look }))}
      >
        <div className="space-y-4">
          <div className="grid gap-2 sm:grid-cols-2">
            {PRESETS.map((preset) => {
              const active = preset.id === brief.style_preset
              return (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => applyPreset(preset.id)}
                  aria-pressed={active}
                  className={`group overflow-hidden rounded-md border p-3 text-left transition-all duration-150 ${
                    active
                      ? 'border-brass-400/50 bg-brass-400/[0.06]'
                      : 'border-white/[0.08] hover:border-white/[0.18]'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-[13px] font-medium text-fg">{preset.label}</p>
                    <span
                      className={`mt-0.5 h-2 w-2 rounded-full border ${
                        active ? 'border-brass-400 bg-brass-400' : 'border-white/20'
                      }`}
                      aria-hidden
                    />
                  </div>
                  <div className="mt-2 flex h-5 overflow-hidden rounded-[3px]">
                    {preset.swatch.map((color) => (
                      <span key={color} className="flex-1" style={{ background: color }} />
                    ))}
                  </div>
                  <p className="mt-2 text-2xs leading-relaxed text-fg-muted">
                    {preset.motif}
                  </p>
                </button>
              )
            })}
          </div>

          <Field label={FIELD_LABELS.visual_style} hint="free text">
            <input
              className="field"
              value={brief.visual_style}
              onChange={(e) => set('visual_style', e.target.value)}
              placeholder="Editorial luxury"
              maxLength={120}
            />
          </Field>

          <div className="grid gap-4 sm:grid-cols-3">
            <ColorField
              label={FIELD_LABELS.primary_color}
              value={brief.primary_color}
              error={merged.primary_color}
              onChange={(v) => set('primary_color', v)}
            />
            <ColorField
              label={FIELD_LABELS.secondary_color}
              value={brief.secondary_color}
              error={merged.secondary_color}
              onChange={(v) => set('secondary_color', v)}
            />
            <ColorField
              label={FIELD_LABELS.accent_color}
              value={brief.accent_color ?? ''}
              error={merged.accent_color}
              onChange={(v) => set('accent_color', v || null)}
              optional
            />
          </div>

          <div className="flex items-start gap-2 rounded-md border border-white/[0.07] bg-white/[0.02] px-3 py-2.5">
            <Palette className="mt-[2px] h-3.5 w-3.5 shrink-0 text-brass-400" aria-hidden />
            <p className="text-2xs leading-relaxed text-fg-muted">
              Contrast is enforced by the backend, so text stays legible whatever palette you pick.
            </p>
          </div>
        </div>
      </Section>

      {/* ==========================================================
          Brand
          ========================================================== */}
      <Section
        step="03"
        title="Brand"
        subtitle="Identity applied consistently across all four outputs."
        open={open.brand}
        onToggle={() => setOpen((s) => ({ ...s, brand: !s.brand }))}
      >
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              label={FIELD_LABELS.brand_name}
              hint="defaults to project name"
              error={merged.brand_name}
              htmlFor="f-brand"
            >
              <input
                id="f-brand"
                className="field"
                value={brief.brand_name}
                onChange={(e) => set('brand_name', e.target.value)}
                placeholder="Bean House Coffee"
                maxLength={90}
              />
            </Field>
            <Field
              label={FIELD_LABELS.tagline}
              hint={`${brief.tagline.length}/160`}
              error={merged.tagline}
              htmlFor="f-tagline"
            >
              <input
                id="f-tagline"
                className={`field ${merged.tagline ? 'field-invalid' : ''}`}
                value={brief.tagline}
                onChange={(e) => set('tagline', e.target.value)}
                placeholder="Slow mornings, poured with intent."
                maxLength={160}
              />
            </Field>
          </div>

          <Field
            label={FIELD_LABELS.logo_data_url}
            hint="optional · max 4 MB"
            error={logoError ?? merged.logo_data_url}
          >
            <div className="flex flex-wrap items-center gap-2">
              <label className="btn-secondary btn-sm cursor-pointer">
                <Upload className="h-3 w-3" aria-hidden />
                {brief.logo_data_url ? 'Replace' : 'Upload'}
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp,image/svg+xml"
                  className="hidden"
                  onChange={(e) => void handleLogo(e.target.files?.[0] ?? null)}
                />
              </label>
              {brief.logo_data_url ? (
                <button
                  type="button"
                  className="btn-ghost btn-sm"
                  onClick={() => {
                    set('logo_data_url', null)
                    setLogoPreview(null)
                  }}
                >
                  <Trash2 className="h-3 w-3" aria-hidden />
                  Remove
                </button>
              ) : null}
              {logoPreview ? (
                <span className="flex items-center gap-2 rounded border border-white/[0.09] bg-white/[0.03] px-2 py-1">
                  <img src={logoPreview} alt="" className="h-6 w-6 rounded object-contain" />
                  <span className="text-2xs text-fg-muted">Ready</span>
                </span>
              ) : (
                <span className="text-2xs text-fg-ghost">
                  No logo? A monogram lockup is drawn in your brand colours.
                </span>
              )}
            </div>
          </Field>
        </div>
      </Section>

      {/* ==========================================================
          Extra
          ========================================================== */}
      <Section
        step="04"
        title="Extra instructions"
        subtitle="Optional constraints applied to copy and layout."
        open={open.extra}
        onToggle={() => setOpen((s) => ({ ...s, extra: !s.extra }))}
      >
        <Field
          label={FIELD_LABELS.extra_instructions}
          hint={`${brief.extra_instructions.length}/2000`}
          error={merged.extra_instructions}
          htmlFor="f-extra"
        >
          <textarea
            id="f-extra"
            className="field min-h-[92px] resize-y leading-relaxed"
            value={brief.extra_instructions}
            onChange={(e) => set('extra_instructions', e.target.value)}
            placeholder="Avoid discount-led messaging. Keep language warm and unhurried."
            maxLength={2000}
          />
        </Field>
      </Section>

      {/* ==========================================================
          Action bar
          ========================================================== */}
      <div className="surface sticky bottom-3 z-10 flex flex-col gap-3 p-3 shadow-lift sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-center gap-2">
          <Wand2 className="h-3.5 w-3.5 shrink-0 text-brass-400" aria-hidden />
          <p className="truncate text-2xs text-fg-muted">
            Produces <span className="text-fg">deck, poster, social graphic and vector mark</span>
            {invalidCount ? ` · ${invalidCount} field(s) need attention` : ''}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            className="btn-ghost btn-sm"
            onClick={() => onChange({ ...DEFAULT_BRIEF })}
            disabled={busy}
          >
            <RotateCcw className="h-3 w-3" aria-hidden />
            Reset
          </button>
          <button type="submit" className="btn-primary flex-1 sm:flex-none" disabled={busy}>
            {busy ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
            ) : (
              <Sparkles className="h-3.5 w-3.5" aria-hidden />
            )}
            {busy ? (phase ?? 'Generating…') : 'Generate package'}
          </button>
        </div>
      </div>
    </form>
  )
}

function Section({
  step,
  title,
  subtitle,
  open,
  onToggle,
  children,
}: {
  step: string
  title: string
  subtitle: string
  open: boolean
  onToggle: () => void
  children: React.ReactNode
}) {
  return (
    <section className="surface overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-white/[0.02]"
      >
        <span className="num w-5 shrink-0 text-brass-400/80">{step}</span>
        <span className="min-w-0 flex-1">
          <span className="block text-[13px] font-medium text-fg">{title}</span>
          <span className="mt-0.5 block text-2xs text-fg-ghost">{subtitle}</span>
        </span>
        <ChevronDown
          className={`h-3.5 w-3.5 shrink-0 text-fg-ghost transition-transform duration-200 ${
            open ? 'rotate-180' : ''
          }`}
          aria-hidden
        />
      </button>
      {open ? (
        <div className="border-t border-white/[0.07] px-4 py-4 animate-fade-in">{children}</div>
      ) : null}
    </section>
  )
}

function ColorField({
  label,
  value,
  onChange,
  error,
  optional,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  error?: string
  optional?: boolean
}) {
  const safe = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(value)
  return (
    <Field label={label} hint={optional ? 'optional' : undefined} error={error}>
      <div className="flex items-center gap-2">
        <label
          className="relative h-8 w-8 shrink-0 cursor-pointer overflow-hidden rounded border border-white/15"
          style={{ background: safe ? value : '#1B1B20' }}
        >
          <input
            type="color"
            value={safe ? value : '#1B1B20'}
            onChange={(e) => onChange(e.target.value.toUpperCase())}
            className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
            aria-label={`${label} picker`}
          />
        </label>
        <input
          className={`field font-mono text-xs uppercase ${error ? 'field-invalid' : ''}`}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={optional ? 'Auto' : '#000000'}
          maxLength={7}
        />
      </div>
    </Field>
  )
}

export function BriefErrorSummary({ errors }: { errors: ValidationErrors }) {
  const entries = Object.entries(errors)
  if (!entries.length) return null
  return (
    <Notice tone="error" title={`${entries.length} field${entries.length > 1 ? 's' : ''} need attention`}>
      <ul className="mt-1 space-y-1">
        {entries.slice(0, 6).map(([field, message]) => (
          <li key={field} className="flex items-start gap-1.5">
            <AlertCircle className="mt-[2px] h-3 w-3 shrink-0" aria-hidden />
            <span>
              <span className="font-medium text-fg">{FIELD_LABELS[field] ?? field}</span> — {message}
            </span>
          </li>
        ))}
      </ul>
    </Notice>
  )
}