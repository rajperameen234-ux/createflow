import type { StylePresetId, PresentationTypeId, Brief } from '../types'

export interface PresetOption {
  id: StylePresetId
  label: string
  description: string
  motif: string
  headingFont: string
  bodyFont: string
  dark: boolean
  colors: { primary: string; secondary: string; accent: string; paper: string; ink: string }
  swatch: string[]
}

export const PRESETS: PresetOption[] = [
  {
    id: 'editorial_luxury',
    label: 'Editorial Luxury',
    description: 'Serif headlines, generous margins, quiet gold rules and archival tone.',
    motif: 'Arcs & foil rules',
    headingFont: 'Georgia',
    bodyFont: 'Calibri',
    dark: false,
    colors: {
      primary: '#3A2418',
      secondary: '#EFE3D0',
      accent: '#C9A227',
      paper: '#FAF6EF',
      ink: '#20140D',
    },
    swatch: ['#3A2418', '#6B4A32', '#A8875C', '#C9A227', '#EFE3D0'],
  },
  {
    id: 'modern_minimal',
    label: 'Modern Minimal',
    description: 'Neutral canvas, one confident accent, tight grid and small caps labels.',
    motif: 'Hairline grid',
    headingFont: 'Segoe UI Semibold',
    bodyFont: 'Segoe UI',
    dark: false,
    colors: {
      primary: '#111827',
      secondary: '#F3F4F6',
      accent: '#4F46E5',
      paper: '#FFFFFF',
      ink: '#111827',
    },
    swatch: ['#111827', '#374151', '#9CA3AF', '#4F46E5', '#F3F4F6'],
  },
  {
    id: 'bold_creative',
    label: 'Bold Creative',
    description: 'Saturated colour blocking, oversized type and energetic diagonals.',
    motif: 'Colour blocks',
    headingFont: 'Arial Black',
    bodyFont: 'Arial',
    dark: false,
    colors: {
      primary: '#1B1464',
      secondary: '#FFD166',
      accent: '#EF476F',
      paper: '#FFF9F2',
      ink: '#14102E',
    },
    swatch: ['#1B1464', '#4B3FC4', '#EF476F', '#FFD166', '#FFF9F2'],
  },
  {
    id: 'corporate_premium',
    label: 'Corporate Premium',
    description: 'Structured blues, disciplined alignment and confident data framing.',
    motif: 'Ledger lines',
    headingFont: 'Segoe UI Semibold',
    bodyFont: 'Segoe UI',
    dark: false,
    colors: {
      primary: '#0B3C6B',
      secondary: '#E8EEF5',
      accent: '#2E8BC0',
      paper: '#FAFCFE',
      ink: '#0E2338',
    },
    swatch: ['#0B3C6B', '#2E6CA0', '#2E8BC0', '#8FBBD6', '#E8EEF5'],
  },
  {
    id: 'dark_cinematic',
    label: 'Dark Cinematic',
    description: 'Near-black stage, luminous accent and wide letter-spaced titles.',
    motif: 'Spotlight bloom',
    headingFont: 'Segoe UI Light',
    bodyFont: 'Segoe UI',
    dark: true,
    colors: {
      primary: '#0A0A12',
      secondary: '#1C1C2B',
      accent: '#7C6BFF',
      paper: '#101018',
      ink: '#F2F2F7',
    },
    swatch: ['#0A0A12', '#23233A', '#4B4A7A', '#7C6BFF', '#B9B2FF'],
  },
  {
    id: 'playful_colorful',
    label: 'Playful Colorful',
    description: 'Warm candy palette, rounded shapes and friendly short copy.',
    motif: 'Confetti dots',
    headingFont: 'Arial Rounded MT Bold',
    bodyFont: 'Arial',
    dark: false,
    colors: {
      primary: '#EF476F',
      secondary: '#FFF3E0',
      accent: '#06D6A0',
      paper: '#FFFBF5',
      ink: '#22223B',
    },
    swatch: ['#EF476F', '#FF7B54', '#FFD166', '#06D6A0', '#FFF3E0'],
  },
]

export const PRESENTATION_TYPES: { id: PresentationTypeId; label: string; hint: string }[] = [
  { id: 'marketing', label: 'Marketing', hint: 'Launch, campaign, offer' },
  { id: 'business_pitch', label: 'Business pitch', hint: 'Investors, partners' },
  { id: 'educational', label: 'Educational', hint: 'Teaching, training' },
  { id: 'portfolio', label: 'Portfolio', hint: 'Work showcase' },
  { id: 'report', label: 'Report', hint: 'Findings, review' },
]

export const TONE_SUGGESTIONS = [
  'Premium, friendly, modern',
  'Bold and energetic',
  'Calm and reassuring',
  'Technical and precise',
  'Warm and conversational',
  'Authoritative and concise',
]

export const DEFAULT_BRIEF: Brief = {
  project_name: 'Bean House Coffee',
  topic:
    'Launching a modern coffee shop on the high street, built for people who want a carefully made cup and a calm place to sit for an hour.',
  audience: 'Young adults and local customers within a 10-minute walk',
  goal: 'Fill 60 seats on weekday mornings during the first quarter of trading',
  tone: 'Premium, friendly, modern',
  presentation_length: 8,
  presentation_type: 'marketing',
  visual_style: 'Editorial luxury',
  style_preset: 'editorial_luxury',
  primary_color: '#3A2418',
  secondary_color: '#E8DCC8',
  accent_color: '#C9A227',
  brand_name: 'Bean House Coffee',
  tagline: 'Slow mornings, poured with intent.',
  extra_instructions: 'Keep the language warm and unhurried. Avoid discount-led messaging.',
  logo_data_url: null,
}

export const FIELD_LABELS: Record<string, string> = {
  project_name: 'Project name',
  topic: 'Creative brief',
  audience: 'Target audience',
  goal: 'Primary goal',
  tone: 'Tone of voice',
  presentation_length: 'Presentation length',
  presentation_type: 'Presentation type',
  visual_style: 'Visual style',
  style_preset: 'Style preset',
  primary_color: 'Primary colour',
  secondary_color: 'Secondary colour',
  accent_color: 'Accent colour',
  brand_name: 'Brand name',
  tagline: 'Tagline',
  extra_instructions: 'Additional instructions',
  logo_data_url: 'Logo',
}

export function presetById(id: StylePresetId): PresetOption {
  return PRESETS.find((p) => p.id === id) ?? PRESETS[0]
}

const HEX = /^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/

export interface ValidationErrors {
  [field: string]: string
}

export function validateBrief(brief: Brief): ValidationErrors {
  const errors: ValidationErrors = {}
  if (brief.project_name.trim().length < 2) {
    errors.project_name = 'Give the project a name of at least 2 characters.'
  }
  if (brief.topic.trim().length < 10) {
    errors.topic = 'Describe the brief in at least 10 characters so the copy has substance.'
  }
  if (brief.audience.trim().length < 3) errors.audience = 'Name who this is for.'
  if (brief.goal.trim().length < 3) errors.goal = 'State the one outcome this work should drive.'
  if (brief.tone.trim().length < 3) errors.tone = 'Describe the voice.'
  if (brief.presentation_length < 5 || brief.presentation_length > 16) {
    errors.presentation_length = 'Choose between 5 and 16 slides.'
  }
  if (!HEX.test(brief.primary_color)) errors.primary_color = 'Use a hex colour such as #3A2418.'
  if (!HEX.test(brief.secondary_color)) {
    errors.secondary_color = 'Use a hex colour such as #E8DCC8.'
  }
  if (brief.accent_color && !HEX.test(brief.accent_color)) {
    errors.accent_color = 'Use a hex colour such as #C9A227.'
  }
  if (brief.tagline.length > 160) errors.tagline = 'Keep the tagline under 160 characters.'
  if (brief.extra_instructions.length > 2000) {
    errors.extra_instructions = 'Keep additional instructions under 2000 characters.'
  }
  return errors
}