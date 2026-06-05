export interface AppTheme {
  id: string
  name: string
  swatch: string
  vars: Record<string, string>
}

export const THEMES: AppTheme[] = [
  {
    id: 'magenta',
    name: 'Magenta',
    swatch: '#a3007c',
    vars: {
      '--brand-primary':      '#a3007c',
      '--brand-dark':         '#7a005d',
      '--brand-darkest':      '#4d003a',
      '--brand-light':        '#d4a0c3',
      '--brand-lightest':     '#f3e3ed',
      '--brand-50':           '#fdf2f9',
      '--surface-page':       '#e8e4f7',
      '--shadow-focus-brand': '0 0 0 3px rgba(163, 0, 124, 0.25)',
      '--brand-backdrop':     'rgba(77, 0, 58, 0.3)',
      '--status-overdue':     '#4d003a',
    },
  },
  {
    id: 'violet',
    name: 'Violet',
    swatch: '#7c3aed',
    vars: {
      '--brand-primary':      '#7c3aed',
      '--brand-dark':         '#6d28d9',
      '--brand-darkest':      '#4c1d95',
      '--brand-light':        '#c4b5fd',
      '--brand-lightest':     '#ede9fe',
      '--brand-50':           '#f5f3ff',
      '--surface-page':       '#eae6fc',
      '--shadow-focus-brand': '0 0 0 3px rgba(124, 58, 237, 0.25)',
      '--brand-backdrop':     'rgba(76, 29, 149, 0.3)',
      '--status-overdue':     '#4c1d95',
    },
  },
  {
    id: 'indigo',
    name: 'Indigo',
    swatch: '#4338ca',
    vars: {
      '--brand-primary':      '#4338ca',
      '--brand-dark':         '#3730a3',
      '--brand-darkest':      '#312e81',
      '--brand-light':        '#a5b4fc',
      '--brand-lightest':     '#e0e7ff',
      '--brand-50':           '#eef2ff',
      '--surface-page':       '#e2e6fb',
      '--shadow-focus-brand': '0 0 0 3px rgba(67, 56, 202, 0.25)',
      '--brand-backdrop':     'rgba(49, 46, 129, 0.3)',
      '--status-overdue':     '#312e81',
    },
  },
  {
    id: 'ocean',
    name: 'Ocean',
    swatch: '#0369a1',
    vars: {
      '--brand-primary':      '#0369a1',
      '--brand-dark':         '#075985',
      '--brand-darkest':      '#0c4a6e',
      '--brand-light':        '#7dd3fc',
      '--brand-lightest':     '#e0f2fe',
      '--brand-50':           '#f0f9ff',
      '--surface-page':       '#dceefb',
      '--shadow-focus-brand': '0 0 0 3px rgba(3, 105, 161, 0.25)',
      '--brand-backdrop':     'rgba(12, 74, 110, 0.3)',
      '--status-overdue':     '#0c4a6e',
    },
  },
  {
    id: 'teal',
    name: 'Teal',
    swatch: '#0d9488',
    vars: {
      '--brand-primary':      '#0d9488',
      '--brand-dark':         '#0f766e',
      '--brand-darkest':      '#134e4a',
      '--brand-light':        '#5eead4',
      '--brand-lightest':     '#ccfbf1',
      '--brand-50':           '#f0fdfa',
      '--surface-page':       '#d6f5f1',
      '--shadow-focus-brand': '0 0 0 3px rgba(13, 148, 136, 0.25)',
      '--brand-backdrop':     'rgba(19, 78, 74, 0.3)',
      '--status-overdue':     '#134e4a',
    },
  },
  {
    id: 'forest',
    name: 'Forest',
    swatch: '#16a34a',
    vars: {
      '--brand-primary':      '#16a34a',
      '--brand-dark':         '#15803d',
      '--brand-darkest':      '#14532d',
      '--brand-light':        '#86efac',
      '--brand-lightest':     '#dcfce7',
      '--brand-50':           '#f0fdf4',
      '--surface-page':       '#ddf5e6',
      '--shadow-focus-brand': '0 0 0 3px rgba(22, 163, 74, 0.25)',
      '--brand-backdrop':     'rgba(20, 83, 45, 0.3)',
      '--status-overdue':     '#14532d',
    },
  },
  {
    id: 'amber',
    name: 'Amber',
    swatch: '#d97706',
    vars: {
      '--brand-primary':      '#d97706',
      '--brand-dark':         '#b45309',
      '--brand-darkest':      '#78350f',
      '--brand-light':        '#fcd34d',
      '--brand-lightest':     '#fef3c7',
      '--brand-50':           '#fffbeb',
      '--surface-page':       '#fdf0c2',
      '--shadow-focus-brand': '0 0 0 3px rgba(217, 119, 6, 0.25)',
      '--brand-backdrop':     'rgba(120, 53, 15, 0.3)',
      '--status-overdue':     '#78350f',
    },
  },
  {
    id: 'sunset',
    name: 'Sunset',
    swatch: '#ea580c',
    vars: {
      '--brand-primary':      '#ea580c',
      '--brand-dark':         '#c2410c',
      '--brand-darkest':      '#7c2d12',
      '--brand-light':        '#fdba74',
      '--brand-lightest':     '#ffedd5',
      '--brand-50':           '#fff7ed',
      '--surface-page':       '#fde8d0',
      '--shadow-focus-brand': '0 0 0 3px rgba(234, 88, 12, 0.25)',
      '--brand-backdrop':     'rgba(124, 45, 18, 0.3)',
      '--status-overdue':     '#7c2d12',
    },
  },
  {
    id: 'rose',
    name: 'Rose',
    swatch: '#e11d48',
    vars: {
      '--brand-primary':      '#e11d48',
      '--brand-dark':         '#be123c',
      '--brand-darkest':      '#881337',
      '--brand-light':        '#fda4af',
      '--brand-lightest':     '#ffe4e6',
      '--brand-50':           '#fff1f2',
      '--surface-page':       '#fce4e8',
      '--shadow-focus-brand': '0 0 0 3px rgba(225, 29, 72, 0.25)',
      '--brand-backdrop':     'rgba(136, 19, 55, 0.3)',
      '--status-overdue':     '#881337',
    },
  },
  {
    id: 'slate',
    name: 'Slate',
    swatch: '#475569',
    vars: {
      '--brand-primary':      '#475569',
      '--brand-dark':         '#334155',
      '--brand-darkest':      '#1e293b',
      '--brand-light':        '#94a3b8',
      '--brand-lightest':     '#e2e8f0',
      '--brand-50':           '#f8fafc',
      '--surface-page':       '#e3e8f0',
      '--shadow-focus-brand': '0 0 0 3px rgba(71, 85, 105, 0.25)',
      '--brand-backdrop':     'rgba(30, 41, 59, 0.3)',
      '--status-overdue':     '#1e293b',
    },
  },
]

export const DEFAULT_THEME_ID = 'magenta'

export function applyTheme(themeId: string): void {
  const theme = THEMES.find(t => t.id === themeId) ?? THEMES[0]
  const root = document.documentElement
  for (const [key, value] of Object.entries(theme.vars)) {
    root.style.setProperty(key, value)
  }
}

export function getActiveThemeId(): string {
  return localStorage.getItem('app_theme') ?? DEFAULT_THEME_ID
}
