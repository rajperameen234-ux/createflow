/**
 * CreateFlow design system.
 *
 * Direction: a neutral graphite studio rather than a coloured "AI" theme.
 * Surfaces are near-black and separated by hairlines, not by glow or gradient.
 * Exactly one accent (a warm brass) carries meaning: primary action, active
 * state, focus. Nothing else is allowed to be colourful.
 */
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // neutral studio greys
        base: {
          1000: '#08080A',
          950: '#0C0C0F',
          900: '#111114',
          850: '#16161A',
          800: '#1B1B20',
          750: '#212127',
          700: '#2A2A31',
          600: '#3A3A43',
          500: '#565660',
        },
        fg: {
          DEFAULT: '#F4F4F5',
          muted: '#A2A2AD',
          faint: '#6E6E7A',
          ghost: '#4A4A54',
        },
        // the single accent
        brass: {
          50: '#FDF6E7',
          100: '#F8E9C8',
          200: '#F0D69C',
          300: '#E8C070',
          400: '#DEAC50',
          500: '#C9922F',
          600: '#A2761F',
        },
        state: {
          ok: '#4ADE80',
          okDim: '#14532D',
          warn: '#FBBF24',
          warnDim: '#422006',
          err: '#F87171',
          errDim: '#4C1D1D',
          info: '#60A5FA',
          infoDim: '#172554',
        },
      },
      fontFamily: {
        sans: ['Inter', 'Segoe UI', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Cascadia Code', 'Consolas', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem', letterSpacing: '0.01em' }],
        xs: ['0.75rem', { lineHeight: '1.1rem' }],
        sm: ['0.8125rem', { lineHeight: '1.25rem' }],
        base: ['0.875rem', { lineHeight: '1.45rem' }],
        lg: ['1rem', { lineHeight: '1.5rem' }],
        xl: ['1.25rem', { lineHeight: '1.75rem', letterSpacing: '-0.011em' }],
        '2xl': ['1.5rem', { lineHeight: '2rem', letterSpacing: '-0.018em' }],
        '3xl': ['1.875rem', { lineHeight: '2.25rem', letterSpacing: '-0.022em' }],
        '4xl': ['2.25rem', { lineHeight: '2.5rem', letterSpacing: '-0.028em' }],
      },
      borderRadius: {
        xs: '3px',
        sm: '5px',
        DEFAULT: '7px',
        md: '8px',
        lg: '10px',
        xl: '14px',
      },
      spacing: {
        rail: '13.5rem',
        gutter: '1.5rem',
      },
      boxShadow: {
        hairline: 'inset 0 0 0 1px rgba(255,255,255,0.06)',
        pop: '0 1px 2px rgba(0,0,0,0.4), 0 12px 32px -8px rgba(0,0,0,0.6)',
        lift: '0 2px 4px rgba(0,0,0,0.3), 0 18px 44px -14px rgba(0,0,0,0.7)',
        canvas: 'inset 0 0 0 1px rgba(255,255,255,0.05), 0 30px 80px -40px rgba(0,0,0,0.9)',
      },
      transitionTimingFunction: {
        out: 'cubic-bezier(0.16, 1, 0.3, 1)',
      },
      keyframes: {
        'fade-rise': {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to: { opacity: '1', transform: 'none' },
        },
        'fade-in': { from: { opacity: '0' }, to: { opacity: '1' } },
        'scale-in': {
          from: { opacity: '0', transform: 'scale(0.985)' },
          to: { opacity: '1', transform: 'none' },
        },
        'sheen': {
          '0%': { transform: 'translateX(-120%)' },
          '100%': { transform: 'translateX(320%)' },
        },
        'bar-grow': { from: { transform: 'scaleX(0)' }, to: { transform: 'scaleX(1)' } },
      },
      animation: {
        'fade-rise': 'fade-rise 260ms cubic-bezier(0.16,1,0.3,1) both',
        'fade-in': 'fade-in 200ms ease-out both',
        'scale-in': 'scale-in 180ms cubic-bezier(0.16,1,0.3,1) both',
        sheen: 'sheen 1.5s cubic-bezier(0.4,0,0.2,1) infinite',
        'bar-grow': 'bar-grow 320ms cubic-bezier(0.16,1,0.3,1) both',
      },
    },
  },
  plugins: [],
}