import { useState } from 'react'
import { Check, Copy, Type } from 'lucide-react'
import { PRESETS, presetById } from '../lib/presets'
import type { Brief, StylePresetId } from '../types'
import { DEFAULT_BRIEF } from '../lib/presets'
import { Notice, Pill, SectionHeading, StatusDot } from '../components/ui'

interface Props {
  health: { fonts: string[] } | null
  onApply?: (brief: Brief) => void
}

/**
 * The style system, shown as the source of truth for brand decisions.
 * Applying a preset writes real values into the brief; nothing here is cosmetic.
 */
export function BrandView({ health, onApply }: Props) {
  const [copied, setCopied] = useState<string | null>(null)
  const [applied, setApplied] = useState<StylePresetId | null>(null)

  const copy = async (value: string, key: string) => {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(key)
      window.setTimeout(() => setCopied(null), 1400)
    } catch {
      setCopied(null)
    }
  }

  const apply = (id: StylePresetId) => {
    const preset = presetById(id)
    onApply?.({
      ...DEFAULT_BRIEF,
      style_preset: preset.id,
      visual_style: preset.label,
      primary_color: preset.colors.primary,
      secondary_color: preset.colors.secondary,
      accent_color: preset.colors.accent,
    })
    setApplied(id)
    window.setTimeout(() => setApplied(null), 1800)
  }

  return (
    <div className="space-y-6">
      <SectionHeading
        eyebrow="Design system"
        title="Style presets"
        description="Six identities. Each defines a palette, a type pairing, a corner language and a background motif that every generated output inherits."
      />

      <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
        {PRESETS.map((preset) => (
          <article key={preset.id} className="surface flex flex-col overflow-hidden">
            <div
              className="relative flex h-28 items-end p-3.5"
              style={{ background: preset.colors.primary }}
            >
              <svg
                className="absolute right-0 top-0 h-full w-1/2 opacity-70"
                viewBox="0 0 100 100"
                aria-hidden
              >
                <circle cx="80" cy="30" r="34" fill="none" stroke={preset.colors.accent} strokeWidth="0.6" />
                <circle cx="80" cy="30" r="24" fill="none" stroke={preset.colors.accent} strokeWidth="0.6" opacity="0.7" />
                <circle cx="80" cy="30" r="14" fill={preset.colors.accent} opacity="0.35" />
              </svg>
              <div className="relative">
                <p className="text-sm font-semibold" style={{ color: preset.colors.paper }}>
                  {preset.label}
                </p>
                <p className="text-2xs" style={{ color: preset.colors.accent }}>
                  {preset.motif}
                </p>
              </div>
            </div>

            <div className="flex flex-1 flex-col gap-3 p-3.5">
              <p className="text-xs leading-relaxed text-fg-muted">{preset.description}</p>

              <div className="flex h-6 overflow-hidden rounded-[3px]">
                {preset.swatch.map((color) => (
                  <button
                    key={color}
                    type="button"
                    onClick={() => void copy(color, color)}
                    title={`Copy ${color}`}
                    className="group relative flex-1 transition-[flex] duration-200 hover:flex-[2]"
                  >
                    {copied === color ? (
                      <span className="absolute inset-0 flex items-center justify-center">
                        <Check className="h-3 w-3 text-white/90" aria-hidden />
                      </span>
                    ) : null}
                  </button>
                ))}
              </div>

              <div className="flex flex-wrap gap-1.5">
                <Pill tone="accent">
                  <Type className="h-3 w-3" aria-hidden />
                  {preset.headingFont}
                </Pill>
                <Pill>{preset.bodyFont}</Pill>
              </div>

              <button
                type="button"
                className="btn-secondary btn-sm mt-auto w-full"
                onClick={() => apply(preset.id)}
                disabled={!onApply}
              >
                {applied === preset.id ? (
                  <>
                    <Check className="h-3 w-3" aria-hidden />
                    Applied to brief
                  </>
                ) : (
                  'Use as default'
                )}
              </button>
            </div>
          </article>
        ))}
      </div>

      <div className="surface p-4">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-[13px] font-medium text-fg">Runtime typefaces</h3>
          <StatusDot tone={health?.fonts?.length ? 'ok' : 'warn'}>
            {health?.fonts?.length ? `${health.fonts.length} detected` : 'none detected'}
          </StatusDot>
        </div>
        <p className="mb-3 text-xs leading-relaxed text-fg-muted">
          Graphics render with system fonts detected on the server. Missing faces fall back to the
          next candidate rather than failing.
        </p>
        <div className="flex flex-wrap gap-1.5">
          {health?.fonts?.length ? (
            health.fonts.map((font) => <Pill key={font}>{font}</Pill>)
          ) : (
            <span className="text-2xs text-fg-ghost">Check /api/health for the font list.</span>
          )}
        </div>
      </div>

      <Notice tone="info" title="Colour is enforced, not suggested">
        Every palette passes through a contrast check before rendering, so headings stay legible on
        the paper and primary colours you choose.
      </Notice>
    </div>
  )
}

export function CopyButton({ value, label }: { value: string; label: string }) {
  const [done, setDone] = useState(false)
  return (
    <button
      type="button"
      className="btn-ghost btn-sm"
      onClick={async () => {
        await navigator.clipboard.writeText(value)
        setDone(true)
        window.setTimeout(() => setDone(false), 1400)
      }}
    >
      {done ? <Check className="h-3 w-3" aria-hidden /> : <Copy className="h-3 w-3" aria-hidden />}
      {done ? 'Copied' : label}
    </button>
  )
}