import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/features/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        base: 'oklch(0.15 0.02 260)',
        surface: 'oklch(0.22 0.03 260)',
        foreground: 'oklch(0.90 0.01 260)',
        accent: 'oklch(0.75 0.15 75)',
        teal: 'oklch(0.55 0.12 150)',
        warning: 'oklch(0.65 0.18 25)',
        border: 'oklch(0.35 0.03 260)',
        muted: 'oklch(0.55 0.02 260)',
        surfaceHover: 'oklch(0.28 0.04 260)',
        accentDim: 'oklch(0.60 0.10 75)',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
        script: ['Courier Prime', 'Courier New', 'monospace'],
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-in-out',
        'slide-in': 'slideIn 0.3s ease-in-out',
        'pulse-accent': 'pulseAccent 2s infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideIn: {
          '0%': { transform: 'translateX(-10px)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        pulseAccent: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.6' },
        },
      },
    },
  },
  plugins: [],
};

export default config;