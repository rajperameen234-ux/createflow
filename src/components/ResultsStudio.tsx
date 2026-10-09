import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Check,
  CloudDownload,
  Download,
  FileImage,
  FileText,
  Layers,
  Loader2,
  Pencil,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  PenTool,
} from 'lucide-react'
import type { Asset, AssetKind, Brief, GenerateResponse } from '../types'
import { api, assetHref, fetchAssetBlob } from '../api'
import { KeyValue, Notice, Pill, StatusDot } from './ui'

interface Props {
  result: GenerateResponse
  brief: Brief
  token: string | null
  regenerating: boolean
  onRegenerate: () => void
  onEditBrief: () => void
}

type Tab = AssetKind

const TABS: { id: Tab; label: string; icon: typeof Layers }[] = [
  { id: 'presentation', label: 'Deck', icon: Layers },
  { id: 'poster', label: 'Poster', icon: FileImage },
  { id: 'social', label: 'Social', icon: FileImage },
  { id: 'svg', label: 'Mark', icon: PenTool },
]

const META: Record<AssetKind, { title: string; meta: string; icon: typeof FileText }> = {
  presentation: {
    title: 'Presentation',
    meta: '16:9 · editable text, shapes and charts · speaker notes',
    icon: FileText,
  },
  poster: {
    title: 'Poster',
    meta: 'A2 portrait · 2480 × 3508 px · 300 dpi',
    icon: FileImage,
  },
  social: {
    title: 'Social graphic',
    meta: 'Square · 1440 × 1440 px',
    icon: FileImage,
  },
  svg: {
    title: 'Vector mark',
    meta: 'Scalable SVG · 1080 × 1080 viewbox',
    icon: PenTool,
  },
}

export function ResultsStudio({
  result,
  brief,
  token,
  regenerating,
  onRegenerate,
  onEditBrief,
}: Props) {
  const assets = useMemo(() => {
    const map = new Map<AssetKind, Asset>()
    result.assets.forEach((asset) => map.set(asset.kind, asset))
    return map
  }, [result.assets])

  const [tab, setTab] = useState<Tab>('presentation')
  const [slide, setSlide] = useState(0)
  const [previews, setPreviews] = useState<string[]>([])
  const [slideUrl, setSlideUrl] = useState<string | null>(null)
  const [previewError, setPreviewError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState<string | null>(null)
  const [downloadError, setDownloadError] = useState<string | null>(null)
  const urls = useRef<string[]>([])
  const activeRef = useRef<HTMLButtonElement>(null)

  const count = Math.max(1, result.slide_count)

  /* Filmstrip: real slides rendered by the backend from the same outline. */
  useEffect(() => {
    const controller = new AbortController()
    let cancelled = false
    setPreviews([])
    setPreviewError(null)

    void Promise.all(
      Array.from({ length: count }, (_, i) =>
        api
          .slidePreview(brief, i, token, controller.signal)
          .then((url) => {
            if (cancelled) {
              URL.revokeObjectURL(url)
              return null
            }
            urls.current.push(url)
            return url
          })
          .catch(() => null),
      ),
    ).then((list) => {
      if (!cancelled) setPreviews(list.filter(Boolean) as string[])
    })

    return () => {
      cancelled = true
      controller.abort()
      urls.current.forEach((url) => URL.revokeObjectURL(url))
      urls.current = []
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [brief, count, token])

  /* Full-size render of the selected slide. */
  useEffect(() => {
    const controller = new AbortController()
    let url: string | null = null
    setSlideUrl(null)
    api
      .slidePreview(brief, slide, token, controller.signal)
      .then((objectUrl) => {
        url = objectUrl
        setSlideUrl(objectUrl)
      })
      .catch((err: Error) => {
        if (err.name !== 'AbortError') setPreviewError(err.message)
      })
    return () => {
      controller.abort()
      if (url) URL.revokeObjectURL(url)
    }
  }, [brief, slide, token])

  useEffect(() => {
    const node = activeRef.current
    node?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' })
  }, [slide])

  const download = useCallback(
    async (asset: Asset) => {
      if (!asset.download_url) return
      setDownloading(asset.filename)
      setDownloadError(null)
      try {
        const blob = await fetchAssetBlob(asset.download_url, token)
        const objectUrl = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = objectUrl
        link.download = asset.filename
        document.body.appendChild(link)
        link.click()
        link.remove()
        window.setTimeout(() => URL.revokeObjectURL(objectUrl), 4000)
      } catch (err) {
        setDownloadError(
          `${asset.filename}: ${(err as Error).message}. Open it in a new tab if the server rejects the request.`,
        )
      } finally {
        setDownloading(null)
      }
    },
    [token],
  )

  const current = assets.get(tab)
  const meta = META[tab]

  const cloud =
    result.cloud_mode === 'cloud'
      ? { tone: 'success' as const, title: 'Saved to your library', body: result.cloud_message }
      : result.cloud_mode === 'cloud-error'
        ? {
            tone: 'error' as const,
            title: 'Generated, but not saved',
            body: `${result.cloud_message} The files below are temporary — download them now.`,
          }
        : {
            tone: 'warning' as const,
            title: 'Temporary generation',
            body: `${result.cloud_message} Sign in with Supabase to keep projects permanently.`,
          }

  return (
    <div className="space-y-5">
      {/* ----------------------------------------------------------------
          Status header
          ---------------------------------------------------------------- */}
      <header className="surface flex flex-col gap-4 p-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <Pill tone="accent">
              <Sparkles className="h-3 w-3" aria-hidden />
              {result.slide_count} slides
            </Pill>
            <Pill>{result.theme.preset_label}</Pill>
            <Pill>
              {result.assets.length} files
            </Pill>
          </div>
          <p className="text-sm text-fg">{cloud.title}</p>
          <p className="max-w-2xl text-xs leading-relaxed text-fg-muted">{cloud.body}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button type="button" className="btn-secondary btn-sm" onClick={onEditBrief}>
            <Pencil className="h-3 w-3" aria-hidden />
            Edit brief
          </button>
          <button
            type="button"
            className="btn-primary btn-sm"
            onClick={onRegenerate}
            disabled={regenerating}
          >
            <RefreshCw className={`h-3 w-3 ${regenerating ? 'animate-spin' : ''}`} aria-hidden />
            {regenerating ? 'Regenerating' : 'Regenerate'}
          </button>
        </div>
      </header>

      {cloud.tone !== 'success' ? <Notice tone={cloud.tone}>{cloud.body}</Notice> : null}

      {/* ----------------------------------------------------------------
          Studio: canvas + inspector
          ---------------------------------------------------------------- */}
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_21rem]">
        <section className="min-w-0 space-y-3">
          <div
            className="flex items-center gap-1 overflow-x-auto border-b border-white/[0.07]"
            role="tablist"
            aria-label="Generated outputs"
          >
            {TABS.filter((t) => assets.has(t.id)).map((t) => {
              const Icon = t.icon
              const active = t.id === tab
              return (
                <button
                  key={t.id}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  onClick={() => setTab(t.id)}
                  className={`tab flex items-center gap-2 ${active ? 'tab-active' : ''}`}
                >
                  <Icon className="h-3.5 w-3.5" aria-hidden />
                  {t.label}
                </button>
              )
            })}
          </div>

          {tab === 'presentation' ? (
            <>
              <div className="artboard surface-canvas flex min-h-[420px] items-center justify-center overflow-hidden rounded-lg bg-base-1000 p-4">
                {slideUrl ? (
                  <img
                    key={slide}
                    src={slideUrl}
                    alt={`Slide ${slide + 1} of ${count}`}
                    className="w-full max-w-5xl rounded-[6px] shadow-lift animate-fade-in"
                    style={{ aspectRatio: '16 / 9' }}
                  />
                ) : previewError ? (
                  <div className="px-6 text-center">
                    <TriangleAlert className="mx-auto mb-2 h-4 w-4 text-state-warn" aria-hidden />
                    <p className="text-sm text-fg">Slide preview unavailable</p>
                    <p className="mt-1 text-xs text-fg-muted">{previewError}</p>
                  </div>
                ) : (
                  <div className="flex w-full max-w-5xl flex-col gap-2">
                    <div className="shimmer aspect-video w-full rounded-md bg-white/[0.03]" />
                    <p className="text-center text-xs text-fg-ghost">Rendering slide…</p>
                  </div>
                )}
              </div>

              <div className="surface flex items-center gap-3 px-3 py-2">
                <span className="num shrink-0">
                  {String(slide + 1).padStart(2, '0')} / {String(count).padStart(2, '0')}
                </span>
                <input
                  type="range"
                  min={0}
                  max={count - 1}
                  value={slide}
                  onChange={(e) => setSlide(Number(e.target.value))}
                  className="h-1 flex-1 cursor-pointer appearance-none rounded-full bg-white/[0.09] accent-brass-400"
                  aria-label="Slide navigation"
                />
                <div className="hidden items-center gap-1 sm:flex">
                  <button
                    type="button"
                    className="btn-ghost btn-sm"
                    onClick={() => setSlide((s) => Math.max(0, s - 1))}
                    disabled={slide === 0}
                  >
                    Prev
                  </button>
                  <button
                    type="button"
                    className="btn-ghost btn-sm"
                    onClick={() => setSlide((s) => Math.min(count - 1, s + 1))}
                    disabled={slide === count - 1}
                  >
                    Next
                  </button>
                </div>
              </div>

              <div className="surface flex gap-2 overflow-x-auto p-2">
                {previews.length === 0
                  ? Array.from({ length: Math.min(count, 8) }).map((_, i) => (
                      <div key={i} className="shimmer h-[74px] w-[132px] shrink-0 rounded-[4px] bg-white/[0.04]" />
                    ))
                  : previews.map((url, i) => (
                      <button
                        key={url}
                        ref={i === slide ? activeRef : undefined}
                        type="button"
                        onClick={() => setSlide(i)}
                        aria-label={`Go to slide ${i + 1}`}
                        aria-current={i === slide}
                        className={`group relative shrink-0 overflow-hidden rounded-[4px] transition ${
                          i === slide
                            ? 'ring-2 ring-brass-400 ring-offset-2 ring-offset-base-900'
                            : 'opacity-55 hover:opacity-90'
                        }`}
                      >
                        <img src={url} alt="" className="h-[74px] w-[132px] object-cover" />
                        <span className="absolute bottom-0.5 left-1 num text-[9px] text-white/70 mix-blend-difference">
                          {i + 1}
                        </span>
                      </button>
                    ))}
              </div>
            </>
          ) : current ? (
            <div className="artboard surface-canvas flex min-h-[420px] items-center justify-center overflow-hidden rounded-lg bg-base-1000 p-6">
              <img
                src={assetHref(current.download_url)}
                alt={meta.title}
                className="max-h-[70vh] w-auto max-w-full rounded-[6px] shadow-lift"
                style={tab === 'social' ? { aspectRatio: '1 / 1' } : undefined}
              />
            </div>
          ) : null}

          <p className="text-2xs leading-relaxed text-fg-ghost">{meta.meta}</p>
        </section>

        {/* --------------------------------------------------------------
            Inspector
            -------------------------------------------------------------- */}
        <aside className="space-y-4">
          <div className="surface overflow-hidden">
            <div className="hairline-b flex items-center justify-between px-3.5 py-2.5">
              <h3 className="text-[13px] font-medium text-fg">Files</h3>
              <StatusDot tone={result.cloud_saved ? 'ok' : 'warn'}>
                {result.cloud_saved ? 'In cloud' : 'Temporary'}
              </StatusDot>
            </div>
            <ul className="divide-y divide-white/[0.06]">
              {result.assets.map((asset) => {
                const Icon = META[asset.kind].icon
                const busy = downloading === asset.filename
                return (
                  <li key={asset.filename} className="p-2.5">
                    <div className="flex items-start gap-2.5">
                      <Icon className="mt-[3px] h-3.5 w-3.5 shrink-0 text-fg-ghost" aria-hidden />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-xs font-medium text-fg">
                          {META[asset.kind].title}
                        </p>
                        <p className="truncate font-mono text-[10px] text-fg-ghost">
                          {asset.filename}
                        </p>
                        <p className="mt-0.5 text-[10px] text-fg-muted">
                          {formatBytes(asset.size_bytes)}
                          {asset.width ? ` · ${asset.width}×${asset.height}` : ''}
                        </p>
                      </div>
                    </div>
                    <div className="mt-2 flex items-center gap-1.5">
                      <button
                        type="button"
                        className="btn-secondary btn-sm flex-1"
                        onClick={() => void download(asset)}
                        disabled={busy}
                      >
                        {busy ? (
                          <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
                        ) : (
                          <Download className="h-3 w-3" aria-hidden />
                        )}
                        Download
                      </button>
                      <a
                        className="btn-ghost btn-sm"
                        href={assetHref(asset.download_url)}
                        target="_blank"
                        rel="noreferrer"
                        title="Open in a new tab"
                      >
                        <CloudDownload className="h-3 w-3" aria-hidden />
                      </a>
                    </div>
                  </li>
                )
              })}
            </ul>
          </div>

          {downloadError ? (
            <Notice tone="warning" onDismiss={() => setDownloadError(null)}>
              {downloadError}
            </Notice>
          ) : null}

          <div className="surface p-3.5">
            <h3 className="mb-3 text-[13px] font-medium text-fg">Visual identity</h3>
            <div className="mb-3 flex gap-1">
              {[
                ['Primary', result.theme.primary_color],
                ['Secondary', result.theme.secondary_color],
                ['Accent', result.theme.accent_color],
                ['Paper', result.theme.paper],
              ].map(([label, value]) => (
                <div key={label} className="min-w-0 flex-1">
                  <div
                    className="h-8 rounded-[4px] border border-white/10"
                    style={{ background: value }}
                    title={`${label} ${value}`}
                  />
                  <p className="mt-1 truncate text-[9px] uppercase tracking-[0.08em] text-fg-ghost">
                    {label}
                  </p>
                  <p className="truncate font-mono text-[9px] text-fg-muted">{value}</p>
                </div>
              ))}
            </div>
            <KeyValue
              items={[
                { label: 'Motif', value: result.theme.motif },
                { label: 'Headings', value: result.theme.heading_font },
                { label: 'Body', value: result.theme.body_font },
                { label: 'Project', value: result.project_id ? 'Saved' : 'Not saved' },
              ]}
            />
          </div>

          {result.notes.length ? (
            <div className="surface p-3.5">
              <h3 className="mb-2.5 text-[13px] font-medium text-fg">Notes</h3>
              <ul className="space-y-2">
                {result.notes.map((note) => (
                  <li key={note} className="flex gap-2 text-2xs leading-relaxed text-fg-muted">
                    <Check className="mt-[3px] h-3 w-3 shrink-0 text-state-ok" aria-hidden />
                    {note}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="surface p-3.5">
            <div className="mb-2 flex items-center gap-2">
              <ShieldCheck className="h-3.5 w-3.5 text-fg-ghost" aria-hidden />
              <h3 className="text-[13px] font-medium text-fg">Delivery</h3>
            </div>
            <p className="text-2xs leading-relaxed text-fg-muted">
              {result.cloud_saved
                ? 'Files live in a private Supabase bucket. Downloads use short-lived signed URLs scoped to your account.'
                : 'Files are served from a temporary workspace and expire after one hour. Download them before closing this tab.'}
            </p>
          </div>
        </aside>
      </div>
    </div>
  )
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}