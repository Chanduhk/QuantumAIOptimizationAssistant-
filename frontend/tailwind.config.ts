import type { Config } from 'tailwindcss';

export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
      colors: {
        background: "hsl(var(--background))",
        surface: {
          1: "hsl(var(--surface-1))",
          2: "hsl(var(--surface-2))",
          3: "hsl(var(--surface-3))",
        },
        border: "hsl(var(--border))",
        "border-subtle": "hsl(var(--border-subtle))",
        content: {
          primary: "hsl(var(--content-primary))",
          secondary: "hsl(var(--content-secondary))",
          tertiary: "hsl(var(--content-tertiary))",
          muted: "hsl(var(--content-muted))",
        },
        primary: {
          DEFAULT: "hsl(var(--primary))",
          hover: "hsl(var(--primary-hover))",
          foreground: "hsl(var(--primary-foreground))",
        },
        quantum: {
          DEFAULT: "hsl(var(--quantum))",
          foreground: "hsl(var(--quantum-foreground))",
        },
        status: {
          success: "hsl(var(--success))",
          warning: "hsl(var(--warning))",
          error: "hsl(var(--error))",
          info: "hsl(var(--info))",
        },
        ring: "hsl(var(--ring))",
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      boxShadow: {
        'stardust': '0 0 1px 1px rgba(255, 255, 255, 0.08)',
        'celestial': '0 8px 32px 0 rgba(2, 6, 18, 0.36)',
        'glass': '0 4px 24px -1px rgba(0, 0, 0, 0.25), inset 0 1px 0 0 rgba(255, 255, 255, 0.06)',
      }
    },
  },
  plugins: [],
} satisfies Config;
