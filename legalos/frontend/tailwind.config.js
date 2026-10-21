/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        obsidian: {
          950: '#090D16', // Base Canvas Void
          900: '#0D1322', // Surface Subtle (Container Canvas)
          850: '#111827', // Surface Container
          800: '#141C30', // Surface Elevated (Cards / Drawers)
          750: '#191F2F', // Glass Surface
          700: '#242A3A', // Elevated Hover / Active Card
          600: '#2F3445', // Highest Container
        },
        brand: {
          50: '#f0f4ff',
          100: '#dbe5ff',
          200: '#bfd2ff',
          300: '#93b4ff',
          400: '#60a5fa',
          500: '#3b82f6', // Sapphire Intelligence Primary
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
          dark: '#090D16'
        },
        risk: {
          low: '#10b981',     // Emerald Compliant
          medium: '#f59e0b',  // Amber Deadline Looming
          high: '#ef4444'     // Ruby Critical Risk
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        'glow-blue': '0 0 20px -3px rgba(59, 130, 246, 0.25)',
        'glow-emerald': '0 0 20px -3px rgba(16, 185, 129, 0.25)',
        'glow-amber': '0 0 20px -3px rgba(245, 158, 11, 0.25)',
        'glow-ruby': '0 0 20px -3px rgba(239, 68, 68, 0.25)',
        'glass-card': '0 8px 32px 0 rgba(0, 0, 0, 0.45)',
      },
      borderColor: {
        'hairline': 'rgba(255, 255, 255, 0.08)',
        'subtle': 'rgba(255, 255, 255, 0.14)',
        'active': 'rgba(59, 130, 246, 0.50)',
      }
    },
  },
  plugins: [],
}

