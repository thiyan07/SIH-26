/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eefbf3',
          100: '#d6f5e2',
          200: '#b3ebc9',
          300: '#86dca9',
          400: '#4fc783',
          500: '#16a34a',
          600: '#15803d',
          700: '#166534',
          800: '#14532d',
          900: '#0f3d20',
        },
      },
    },
  },
  plugins: [],
}
