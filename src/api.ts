import type {
  Brief,
  FieldProblem,
  GenerateResponse,
  HealthResponse,
  PresetsResponse,
  PreviewResponse,
  ProjectDetail,
  ProjectSummary,
} from './types'
import { ApiError } from './types'

const BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export function assetHref(url: string | null): string {
  if (!url) return ''
  if (/^https?:\/\//i.test(url)) return url
  return `${BASE}${url.startsWith('/') ? '' : '/'}${url}`
}

async function parseError(response: Response): Promise<ApiError> {
  let detail: unknown = null
  try {
    const body = (await response.json()) as { detail?: unknown }
    detail = body?.detail ?? null
  } catch {
    detail = null
  }

  if (typeof detail === 'string') {
    return new ApiError(detail, response.status)
  }
  if (Array.isArray(detail)) {
    const problems: FieldProblem[] = detail.map((item) => {
      const record = item as { field?: string; message?: string; loc?: unknown[] }
      const loc = Array.isArray(record.loc) ? record.loc.slice(1).join('.') : ''
      return { field: record.field ?? loc ?? 'body', message: record.message ?? 'Invalid value' }
    })
    return new ApiError('Some fields need attention.', response.status, problems)
  }
  if (detail && typeof detail === 'object' && 'message' in (detail as Record<string, unknown>)) {
    return new ApiError(String((detail as Record<string, unknown>).message), response.status)
  }
  return new ApiError(
    response.status === 0
      ? 'The API is unreachable. Start the backend on port 8000.'
      : `Request failed with status ${response.status}.`,
    response.status,
  )
}

async function request<T>(
  path: string,
  init: RequestInit & { token?: string | null; signal?: AbortSignal } = {},
): Promise<T> {
  const { token, signal, ...rest } = init
  const headers = new Headers(rest.headers)
  if (!headers.has('Content-Type') && rest.body) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', `Bearer ${token}`)

  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, { ...rest, headers, signal })
  } catch (err) {
    if ((err as Error)?.name === 'AbortError') throw err
    throw new ApiError('The API is unreachable. Start the backend on port 8000.', 0)
  }
  if (!response.ok) throw await parseError(response)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

/**
 * Fetch a generated file with the bearer token attached.
 * Downloads go through fetch (not a plain link) so authenticated storage and
 * signed-URL endpoints work without opening a new tab.
 */
export async function fetchAssetBlob(url: string, token: string | null): Promise<Blob> {
  const headers = new Headers()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(assetHref(url), { headers })
  if (!response.ok) {
    if (response.status === 401 || response.status === 503) {
      throw new Error(
        'the server requires a signed-in session for downloads (Supabase is configured without a token)',
      )
    }
    throw new Error(`download failed with status ${response.status}`)
  }
  return response.blob()
}

export const api = {
  health: () => request<HealthResponse>('/api/health'),

  presets: () => request<PresetsResponse>('/api/presets'),

  preview: (brief: Brief, signal?: AbortSignal) =>
    request<PreviewResponse>('/api/preview', {
      method: 'POST',
      body: JSON.stringify(brief),
      signal,
    }),

  generate: (brief: Brief, token: string | null, signal?: AbortSignal) =>
    request<GenerateResponse>('/api/generate', {
      method: 'POST',
      body: JSON.stringify(brief),
      token,
      signal,
    }),

  projects: (token: string, signal?: AbortSignal) =>
    request<ProjectSummary[]>('/api/projects', { token, signal }),

  project: (id: string, token: string, signal?: AbortSignal) =>
    request<ProjectDetail>(`/api/projects/${encodeURIComponent(id)}`, { token, signal }),

  regenerate: (id: string, token: string, signal?: AbortSignal) =>
    request<GenerateResponse>(`/api/projects/${encodeURIComponent(id)}/regenerate`, {
      method: 'POST',
      token,
      signal,
    }),

  removeProject: (id: string, token: string) =>
    request<{ deleted: boolean; project_id: string; message: string }>(
      `/api/projects/${encodeURIComponent(id)}`,
      { method: 'DELETE', token },
    ),

  signedDownload: (projectId: string, assetId: string, token: string) =>
    request<{ download_url: string; expires_in: number }>(
      `/api/projects/${encodeURIComponent(projectId)}/download/${encodeURIComponent(assetId)}`,
      { token },
    ),

  /** One real slide rendered by the backend from the same outline as the PPTX. */
  slidePreview: async (
    brief: Brief,
    index: number,
    token: string | null,
    signal?: AbortSignal,
  ): Promise<string> => {
    const headers = new Headers({ 'Content-Type': 'application/json' })
    if (token) headers.set('Authorization', `Bearer ${token}`)
    const response = await fetch(`${BASE}/api/slides/preview?index=${index}`, {
      method: 'POST',
      headers,
      body: JSON.stringify(brief),
      signal,
    })
    if (!response.ok) throw await parseError(response)
    return URL.createObjectURL(await response.blob())
  },

  /** Contact sheet of every slide, used as a project thumbnail. */
  slideSheet: async (brief: Brief, token: string | null, signal?: AbortSignal) => {
    const headers = new Headers({ 'Content-Type': 'application/json' })
    if (token) headers.set('Authorization', `Bearer ${token}`)
    const response = await fetch(`${BASE}/api/slides/sheet`, {
      method: 'POST',
      headers,
      body: JSON.stringify(brief),
      signal,
    })
    if (!response.ok) throw await parseError(response)
    return URL.createObjectURL(await response.blob())
  },
}