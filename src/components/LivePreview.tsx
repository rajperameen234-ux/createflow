import { useEffect, useMemo, useRef, useState } from 'react'
import { Sparkles } from 'lucide-react'
import type { Brief, PreviewResponse } from '../types'
import { api } from '../api'
import { presetById } from '../lib/presets'

/**
 * Live artboard preview.
 *
 * Everything on screen is derived from the brief and the preset tokens, and the
 * outline below comes from the backend narrative engine — the same engine the
 * deck is built from, so it is a real preview rather than decoration.
 */
export function LivePreview({ brief }: { brief: Brief }) {
  const [preview, setPreview] = useState<PreviewResponse | null>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')
  const abort = useRef<AbortController | null>(null)
  const preset = presetById(brief.style_preset)

  const palette = useMemo(
    () => ({
      primary: brief.primary_color || preset.colors.primary,
      secondary: brief.secondary_color || preset.colors.secondary,
      accent: brief.accent_color || preset.colors.accent,
      paper: preset.colors.paper,
      ink: preset.colors.ink,
    }),
    [brief.primary_color, brief.secondary_color, brief.accent_color, preset],
  )

  useEffect(() => {
    const controller = new AbortController()
    abort.current = controller
    setState('loading')
    const timer = window.setTimeout(() => {
      api
        .preview(brief, controller.signal)
        .then((data) => {
          setPreview(data)
          setState('ready')
        })
        .catch((err: Error) => {
          if (err.name !== 'AbortError') setState('error')
        })
    }, 260)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    brief.project_name,
    brief.topic,
    brief.audience,
    brief.goal,
    brief.tone,
    brief.tagline,
    brief.presentation_length,
    brief.presentation_type,
    brief.style_preset,
    brief.primary_color,
    brief.secondary_color,
    brief.accent_color,
  ])

  const slides = preview?.slides ?? []
  const headline = preview?.headline || brief.project_name || 'Your headline'
  const swatch = preview?.swatch ?? preset.swatch
  const brand = brief.brand_name || brief.project_name

  return (
    <div className="space-y-3">
      <div className="surface overflow-hidden">
        <div className="hairline-b flex items-center justify-between px-3.5 py-2.5">
          <h3 className="text-[13px] font-medium text-fg">Live preview</h3>
          <span className="num">
            {state === 'error' ? 'unavailable' : `${slides.length || brief.presentation_length} slides`}
          </span>
        </div>

        <div
          className="relative aspect-[4/5] w-full overflow-hidden"
          style={{ background: palette.paper }}
        >
          {/* hero band */}
          <div className="relative h-[56%]" style={{ background: palette.primary }}>
            <div
              className="absolute inset-0"
              style={{
                background: `radial-gradient(120% 90% at 82% 18%, ${alpha(palette.accent, 0.34)} 0%, transparent 58%)`,
              }}
            />
            <svg className="absolute -right-[22%] top-[14%] h-[78%] w-[78%]" viewBox="0 0 100 100" aria-hidden>
              {[50, 39, 28, 17].map((r, i) => (
                <circle
                  key={r}
                  cx="50"
                  cy="50"
                  r={r}
                  fill="none"
                  stroke={alpha(palette.accent, 0.8 - i * 0.14)}
                  strokeWidth="0.5"
                />
              ))}
            </svg>

            <div className="relative flex h-full flex-col justify-between p-4">
              <div className="flex items-center gap-2">
                <span
                  className="flex h-7 w-7 items-center justify-center rounded-full border text-[9px] font-bold"
                  style={{ borderColor: palette.accent, color: palette.accent }}
                >
                  {brand.slice(0, 2).toUpperCase()}
                </span>
                <div className="min-w-0 leading-tight">
                  <p
                    className="truncate text-[10px] font-semibold uppercase tracking-[0.12em]"
                    style={{ color: readable(palette.primary, palette.ink) }}
                  >
                    {brand}
                  </p>
                  {brief.tagline ? (
                    <p
                      className="truncate text-[9px] opacity-70"
                      style={{ color: readable(palette.primary, palette.ink) }}
                    >
                      {brief.tagline}
                    </p>
                  ) : null}
                </div>
              </div>
              <div>
                <p
                  className="text-[9px] font-semibold uppercase tracking-[0.22em]"
                  style={{ color: palette.accent }}
                >
                  {brief.presentation_type.replace('_', ' ')}
                </p>
                <p
                  className="mt-1.5 text-[22px] font-semibold leading-[1.1]"
                  style={{ color: readable(palette.primary, palette.ink) }}
                >
                  {headline}
                </p>
                <div
                  className="mt-2.5 h-[2px] w-14 rounded-full"
                  style={{ background: palette.accent }}
                />
              </div>
            </div>
          </div>

          {/* lower panel */}
          <div className="h-[44%] p-4">
            <div className="h-[2px] w-full" style={{ background: palette.accent }} />
            <p
              className="mt-3 text-[9px] font-semibold uppercase tracking-[0.2em]"
              style={{ color: alpha(palette.ink, 0.5) }}
            >
              Package
            </p>
            <div className="mt-2 grid grid-cols-2 gap-1.5">
              {[
                `${brief.presentation_length} slides`,
                'Poster',
                'Social',
                preset.label,
              ].map((item, i) => (
                <div
                  key={item}
                  className="rounded-[4px] border px-2 py-1.5"
                  style={{
                    background: alpha(palette.secondary, 0.45),
                    borderColor: alpha(palette.ink, 0.1),
                  }}
                >
                  <span
                    className="text-[10px] font-bold"
                    style={{ color: i % 2 === 0 ? palette.accent : palette.primary }}
                  >
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <p className="truncate text-[10px]" style={{ color: palette.ink }}>
                    {item}
                  </p>
                </div>
              ))}
            </div>
            <div className="mt-3 flex gap-1">
              {swatch.slice(0, 5).map((c) => (
                <span key={c} className="h-1 flex-1 rounded-full" style={{ background: c }} />
              ))}
            </div>
          </div>

          {state === 'loading' ? (
            <span className="absolute bottom-3 right-4 text-[9px] text-fg-ghost">updating…</span>
          ) : null}
        </div>
      </div>

      {/* outline */}
      <div className="surface overflow-hidden">
        <div className="hairline-b flex items-center justify-between px-3.5 py-2.5">
          <h3 className="text-[13px] font-medium text-fg">Outline</h3>
          {preview ? (
            <span className="num flex items-center gap-1.5">
              <Sparkles className="h-3 w-3 text-brass-400" aria-hidden />
              {preview.elapsed_ms} ms
            </span>
          ) : null}
        </div>
        <ul className="max-h-56 overflow-y-auto">
          {slides.map((slide) => (
            <li
              key={slide.n}
              className="flex items-center gap-2.5 border-b border-white/[0.05] px-3.5 py-2 last:border-b-0"
            >
              <span className="num w-4 shrink-0">{String(slide.n).padStart(2, '0')}</span>
              <span className="min-w-0 flex-1 truncate text-xs text-fg">{slide.title}</span>
              <span className="shrink-0 rounded border border-white/[0.08] px-1.5 py-px text-[9px] uppercase tracking-[0.08em] text-fg-ghost">
                {slide.layout.replace('_', ' ')}
              </span>
            </li>
          ))}
          {slides.length === 0 ? (
            <li className="px-3.5 py-5 text-center text-2xs text-fg-ghost">
              Fill in the brief to see the real outline.
            </li>
          ) : null}
        </ul>
      </div>

      {preview?.theme ? (
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 px-0.5 text-2xs text-fg-ghost">
          <span className="text-fg-muted">{preview.theme.preset_label}</span>
          <span aria-hidden>·</span>
          <span>{preview.theme.heading_font}</span>
          <span aria-hidden>·</span>
          <span>{preview.theme.motif}</span>
        </div>
      ) : null}
    </div>
  )
}

function alpha(hex: string, a: number): string {
  const v = hex.replace('#', '')
  const full =
    v.length === 3
      ? v
          .split('')
          .map((c) => c + c)
          .join('')
      : v
  const r = parseInt(full.slice(0, 2), 16)
  const g = parseInt(full.slice(2, 4), 16)
  const b = parseInt(full.slice(4, 6), 16)
  return `rgba(${r}, ${g}, ${b}, ${a})`
}

function luminance(hex: string): number {
  const v = hex.replace('#', '')
  const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)
  return (
    0.2126 * lin(parseInt(v.slice(0, 2), 16) / 255) +
    0.7152 * lin(parseInt(v.slice(2, 4), 16) / 255) +
    0.0722 * lin(parseInt(v.slice(4, 6), 16) / 255)
  )
}

function readable(background: string, preferred: string): string {
  const lb = luminance(background)
  const lp = luminance(preferred)
  return Math.abs(lp - lb) > 0.35 ? (lb > 0.35 ? '#15151A' : '#FAFAF7') : preferred
}