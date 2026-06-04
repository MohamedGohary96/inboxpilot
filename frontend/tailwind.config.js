/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,ts}'],
  theme: {
    extend: {
      colors: {
        brand: {
          primary:  '#a3007c',
          dark:     '#7a005d',
          darkest:  '#4d003a',
          light:    '#d4a0c3',
          lightest: '#f3e3ed',
          50:       '#fdf2f9',
        },
        surface: {
          page: '#e8e4f7',
          card: '#ffffff',
          sunk: '#f9fafb',
        },
        grey: {
          900: '#111827',
          800: '#1f2937',
          700: '#374151',
          600: '#4b5563',
          500: '#6b7280',
          400: '#9ca3af',
          300: '#d1d5db',
          200: '#e5e7eb',
          100: '#f3f4f6',
          50:  '#f9fafb',
        },
        status: {
          overdue:   '#4d003a',
          'due-soon': '#F59E0B',
          replied:   '#10B981',
          dismissed: '#6B7280',
        },
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'Helvetica', 'Arial', 'sans-serif'],
        mono: ['"SF Mono"', 'Consolas', 'Monaco', 'monospace'],
      },
      fontSize: {
        title:      ['20px', { lineHeight: '1.2', fontWeight: '700', letterSpacing: '-0.01em' }],
        heading:    ['17px', { lineHeight: '1.3', fontWeight: '700' }],
        subheading: ['14px', { lineHeight: '1.4', fontWeight: '700' }],
        body:       ['13px', { lineHeight: '1.5' }],
        caption:    ['12px', { lineHeight: '1.4' }],
        micro:      ['11px', { lineHeight: '1.3' }],
      },
      maxWidth: {
        workbench: '1240px',
      },
      borderRadius: {
        DEFAULT: '8px',
        lg:      '12px',
        xl:      '16px',
        pill:    '9999px',
      },
      boxShadow: {
        card:         '0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04)',
        'card-hover': '0 4px 12px rgba(0,0,0,0.08), 0 2px 4px rgba(0,0,0,0.04)',
        dropdown:     '0 4px 16px rgba(0,0,0,0.12)',
        toast:        '0 8px 24px rgba(0,0,0,0.15)',
        'focus-brand':'0 0 0 3px rgba(163, 0, 124, 0.25)',
      },
    },
  },
  plugins: [],
}
