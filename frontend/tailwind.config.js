/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './lib/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        fintech: {
          bg: '#090D16',
          card: '#101726',
          cardHover: '#162034',
          panel: '#0D1424',
          border: '#1E293B',
          borderLight: '#334155',
          text: '#F8FAFC',
          muted: '#94A3B8',
          accent: '#6366F1',
          accentHover: '#4F46E5',
          emerald: '#10B981',
          emeraldMuted: 'rgba(16, 185, 129, 0.15)',
          amber: '#F59E0B',
          amberMuted: 'rgba(245, 158, 11, 0.15)',
          rose: '#EF4444',
          roseMuted: 'rgba(239, 68, 68, 0.15)',
          cyan: '#06B6D4',
          cyanMuted: 'rgba(6, 182, 212, 0.15)',
          purple: '#8B5CF6',
          purpleMuted: 'rgba(139, 92, 246, 0.15)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'SFMono-Regular', 'Menlo', 'Monaco', 'monospace'],
      },
      boxShadow: {
        'fintech-card': '0 4px 20px -2px rgba(0, 0, 0, 0.5), 0 2px 6px -1px rgba(0, 0, 0, 0.3)',
        'fintech-glow': '0 0 25px -5px rgba(99, 102, 241, 0.35)',
        'fintech-glow-emerald': '0 0 25px -5px rgba(16, 185, 129, 0.35)',
        'fintech-glow-rose': '0 0 25px -5px rgba(239, 68, 68, 0.35)',
      },
    },
  },
  plugins: [],
};
