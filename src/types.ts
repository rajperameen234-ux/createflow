/** Shared API types mirroring the FastAPI schemas. */

export type StylePresetId =
  | 'editorial_luxury'
  | 'modern_minimal'
  | 'bold_creative'
  | 'corporate_premium'
  | 'dark_cinematic'
  | 'playful_colorful'

export type PresentationTypeId =
  | 'educational'
  | 'business_pitch'
  | 'marketing'
  | 'portfolio'
  | 'report'

export type AssetKind = 'presentation' | 'poster' | 'social' | 'svg'

export interface PresetSpec {
  id: StylePresetId
  label: string
  description: string
  motif: string
  heading_font: string
  body_font: string
  dark_canvas: boolean
  default_primary: string
  default_secondary: string
  default_accent: string
  paper: string
  ink: string
  swatch: string[]
}

export interface PresetsResponse {
  presets: PresetSpec[]
  presentation_types: PresentationTypeId[]
  layouts: string[]
}

export interface Brief {
  project_name: string
  topic: string
  audience: string
  goal: string
  tone: string
  presentation_length: number
  presentation_type: PresentationTypeId
  visual_style: string
  style_preset: StylePresetId
  primary_color: string
  secondary_color: string
  accent_color?: string | null
  brand_name: string
  tagline: string
  extra_instructions: string
  logo_data_url?: string | null
}

export interface ThemeSummary {
  preset: StylePresetId
  preset_label: string
  primary_color: string
  secondary_color: string
  accent_color: string
  ink: string
  paper: string
  heading_font: string
  body_font: string
  motif: string
}

export interface Asset {
  id: string | null
  kind: AssetKind
  filename: string
  content_type: string
  size_bytes: number
  width: number | null
  height: number | null
  download_url: string | null
  storage_path: string | null
  cloud_saved: boolean
  checksum: string | null
}

export interface GenerateResponse {
  project_id: string | null
  cloud_saved: boolean
  cloud_mode: 'cloud' | 'local-development' | 'cloud-error'
  cloud_message: string
  theme: ThemeSummary
  slide_count: number
  assets: Asset[]
  notes: string[]
  created_at: string
}

export interface PreviewResponse {
  theme: ThemeSummary
  swatch: string[]
  slides: { n: number; layout: string; title: string; kicker: string }[]
  slide_count: number
  headline: string
  elapsed_ms: number
}

export interface HealthResponse {
  status: string
  version: string
  cloud_configured: boolean
  cloud_message: string
  auth_required: boolean
  fonts: string[]
  slide_layouts: string[]
  capabilities: Record<string, boolean | string[]>
}

export interface ProjectSummary {
  id: string
  project_name: string
  topic: string
  style_preset: StylePresetId
  primary_color: string
  secondary_color: string
  brand_name: string
  tagline: string
  slide_count: number
  asset_count: number
  created_at: string
  updated_at?: string | null
}

export interface ProjectDetail extends ProjectSummary {
  goal: string
  audience: string
  tone: string
  presentation_type: PresentationTypeId
  visual_style: string
  extra_instructions: string
  brief: Record<string, unknown>
  assets: Asset[]
}

export interface FieldProblem {
  field: string
  message: string
}

export class ApiError extends Error {
  status: number
  problems: FieldProblem[]

  constructor(message: string, status: number, problems: FieldProblem[] = []) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.problems = problems
  }
}