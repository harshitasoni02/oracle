/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#0D1117',
        surface: '#161B22',
        border: '#30363D',
        muted: '#8B949E',
        gold: '#F0A500',
        'gold-light': '#FFD166',
        silver: '#A0ADB7',
        'silver-light': '#C9D1D9',
        bull: '#3FB950',
        bear: '#F85149',
        neutral: '#8B949E',
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
}
