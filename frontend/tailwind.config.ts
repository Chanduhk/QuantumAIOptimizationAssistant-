import type { Config } from 'tailwindcss';

const token = (name: string) => `hsl(var(--${name}) / <alpha-value>)`;

export default {
  darkMode: 'class',
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Geist', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"Geist Mono"', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      colors: {
        background: token('background'),
        surface: {
          1: token('surface-1'),
          2: token('surface-2'),
          3: token('surface-3'),
        },
        border: token('border'),
        'border-subtle': token('border-subtle'),
        content: {
          primary: token('content-primary'),
          secondary: token('content-secondary'),
          tertiary: token('content-tertiary'),
          muted: token('content-muted'),
        },
        primary: {
          DEFAULT: token('primary'),
          hover: token('primary-hover'),
          foreground: token('primary-foreground'),
          soft: token('primary-soft'),
        },
        quantum: {
          DEFAULT: token('quantum'),
          foreground: token('quantum-foreground'),
        },
        status: {
          success: token('success'),
          warning: token('warning'),
          error: token('error'),
          info: token('info'),
        },
        ring: token('ring'),
      },
      borderRadius: {
        xl: '0.875rem',
        '2xl': '1.125rem',
      },
      boxShadow: {
        card: '0 1px 0 0 hsl(var(--highlight) / 0.04) inset, 0 1px 2px 0 rgb(0 0 0 / 0.12)',
        lift: '0 1px 0 0 hsl(var(--highlight) / 0.05) inset, 0 12px 32px -12px rgb(0 0 0 / 0.45)',
        glow: '0 0 0 1px hsl(var(--primary) / 0.35), 0 8px 28px -8px hsl(var(--primary) / 0.45)',
      },
      keyframes: {
        'fade-up': {
          from: { opacity: '0', transform: 'translateY(6px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          from: { backgroundPosition: '200% 0' },
          to: { backgroundPosition: '-200% 0' },
        },
        orbit: {
          from: { transform: 'rotate(0deg)' },
          to: { transform: 'rotate(360deg)' },
        },
        slide: {
          from: { transform: 'translateX(-100%)' },
          to: { transform: 'translateX(300%)' },
        },
        'pulse-soft': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.45' },
        },
      },
      animation: {
        'fade-up': 'fade-up 360ms cubic-bezier(0.22, 1, 0.36, 1) both',
        shimmer: 'shimmer 1.8s linear infinite',
        orbit: 'orbit 24s linear infinite',
        'orbit-slow': 'orbit 48s linear infinite',
        'pulse-soft': 'pulse-soft 2s ease-in-out infinite',
        slide: 'slide 1.2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
} satisfies Config;
